"""
DQN Agent Implementation

This module implements a Deep Q-Network (DQN) Agent for Traffic Signal Control,
incorporating multiple modern improvement techniques:
- Dueling DQN: Separates state value and action advantage to improve learning efficiency
- Double DQN: Reduces Q-value overestimation problem
- Prioritized Experience Replay: More efficient utilization of important experiences
- Target Network: Improves training stability

Author: Traffic RL Team
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
from collections import deque
import random
from typing import Tuple, Optional


class DQN(nn.Module):
    """
    Standard Deep Q-Network

    This is the basic DQN architecture using multi-layer fully connected network
    to map state to Q-values for each action.

    Network structure:
    Input(state_dim) -> FC(128) -> ReLU -> FC(128) -> ReLU -> FC(64) -> ReLU -> Output(action_dim)
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
        """
        Initialize DQN network

        Args:
            state_dim: state space dimension (input size)
            action_dim: action space dimension (output size, i.e., number of Q-values)
            hidden_dim: number of hidden layer neurons
        """
        super(DQN, self).__init__()

        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc4 = nn.Linear(hidden_dim // 2, action_dim)

        self._initialize_weights()

    def _initialize_weights(self):
        """Apply orthogonal initialization to all linear layers"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward propagation

        Args:
            x: state tensor with shape (batch_size, state_dim)

        Returns:
            Q-values for each action with shape (batch_size, action_dim)
        """
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        return self.fc4(x)


class DuelingDQN(nn.Module):
    """
    Dueling DQN network

    This is an improved version of DQN that decomposes Q-values into two parts:
    - State value V(s): value of being in state s, independent of action
    - Action advantage A(s,a): advantage of taking action a in state s relative to average action

    Q(s,a) = V(s) + A(s,a) - mean(A(s,·))

    This decomposition allows the network to better learn which states are valuable,
    even when actions have little impact on state value. Particularly useful for Traffic Signal Control,
    as sometimes keeping current phase vs switching has minimal difference.
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128):
        """
        Initialize Dueling DQN network

        Args:
            state_dim: state space dimension
            action_dim: action space dimension
            hidden_dim: number of hidden layer neurons
        """
        super(DuelingDQN, self).__init__()

        self.feature_layer = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )

        self.value_stream = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )

        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim)
        )

        self._initialize_weights()

    def _initialize_weights(self):
        """Apply orthogonal initialization"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward propagation

        Q-value formula:
        Q(s,a) = V(s) + (A(s,a) - mean(A(s,·)))

        Subtracting the mean of advantages ensures identifiability,
        ensuring unique decomposition of V and A.

        Args:
            x: state tensor

        Returns:
            Q-values for each action
        """
        features = self.feature_layer(x)

        value = self.value_stream(features)
        advantage = self.advantage_stream(features)

        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))

        return q_values


class ReplayBuffer:
    """
    Experience replay buffer

    Stores agent-environment interaction experiences (state, action, reward, next state, done flag).
    During training, randomly samples a batch of experiences to break temporal correlations.

    This is one of the key techniques for stable DQN training:
    1. Break data correlation: random sampling makes training data closer to i.i.d. assumption
    2. Improve data efficiency: each experience can be used multiple times
    3. Smooth learning curve: avoids drastic fluctuations from recent experiences
    """

    def __init__(self, capacity: int = 100000):
        """
        Initialize replay buffer

        Args:
            capacity: maximum buffer capacity, oldest experiences discarded when exceeded
        """
        self.buffer = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """
        Add an experience to the buffer

        Args:
            state: current state
            action: action taken
            reward: reward received
            next_state: next state
            done: whether episode terminated
        """
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple[np.ndarray, ...]:
        """
        Randomly sample a batch of experiences

        Args:
            batch_size: number of samples

        Returns:
            tuple containing states, actions, rewards, next_states, dones
        """
        batch = random.sample(self.buffer, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.int64),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32)
        )

    def __len__(self) -> int:
        """Return current buffer size"""
        return len(self.buffer)


class PrioritizedReplayBuffer:
    """
    Prioritized experience replay buffer

    Unlike standard replay buffer, this version determines sampling priority based on TD error.
    Experiences with large TD errors indicate inaccurate model predictions, thus should be learned more frequently.

    Technical details:
    - Priority: p_i = |δ_i| + ε (δ is TD error, ε is small constant to prevent zero priority)
    - Sampling probability: P(i) = p_i^α / Σ p_j^α (α controls priority sharpness)
    - Importance sampling weight: w_i = (N * P(i))^(-β) (compensates for non-uniform sampling bias)
    """

    def __init__(
        self,
        capacity: int = 100000,
        alpha: float = 0.6,
        beta: float = 0.4,
        beta_increment: float = 0.001
    ):
        """
        Initialize prioritized experience replay buffer

        Args:
            capacity: maximum capacity
            alpha: priority exponent (0=uniform sampling, 1=fully prioritized)
            beta: importance sampling weight exponent (gradually increases to 1)
            beta_increment: beta increment after each sampling
        """
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
    
    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """
        Add new experience

        New experiences are given highest priority, ensuring they are sampled at least once.
        """
        max_priority = self.priorities.max() if self.buffer else 1.0

        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
        else:
            self.buffer[self.position] = (state, action, reward, next_state, done)

        self.priorities[self.position] = max_priority
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int) -> Tuple:
        """
        Sample by priority

        Returns:
            states, actions, rewards, next_states, dones, indices, weights
        """
        if len(self.buffer) < self.capacity:
            priorities = self.priorities[:len(self.buffer)]
        else:
            priorities = self.priorities

        probabilities = priorities ** self.alpha
        probabilities /= probabilities.sum()

        indices = np.random.choice(len(self.buffer), batch_size, p=probabilities)

        weights = (len(self.buffer) * probabilities[indices]) ** (-self.beta)
        weights /= weights.max()

        self.beta = min(1.0, self.beta + self.beta_increment)

        batch = [self.buffer[idx] for idx in indices]
        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.int64),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32),
            indices,
            np.array(weights, dtype=np.float32)
        )

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """
        Update experience priorities

        Args:
            indices: indices of experiences to update
            td_errors: corresponding TD errors
        """
        for idx, td_error in zip(indices, td_errors):
            self.priorities[idx] = abs(td_error) + 1e-6
    
    def __len__(self) -> int:
        return len(self.buffer)


class DQNAgent:
    """
    DQN Agent

    This class integrates all components needed for DQN training:
    - Q-network and target network
    - Experience replay buffer
    - Epsilon-greedy exploration strategy
    - Training loop

    Implements the following key techniques:
    1. Target network: uses separate network to compute target Q-values, updated periodically
    2. Double DQN: uses online network to select action, target network to evaluate Q-value
    3. Gradient clipping: prevents gradient explosion
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 128,
        lr: float = 1e-3,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        buffer_size: int = 100000,
        batch_size: int = 64,
        target_update_freq: int = 100,
        use_prioritized_replay: bool = False,
        use_dueling: bool = True,
        device: str = None
    ):
        """
        Initialize DQN Agent

        Args:
            state_dim: state dimension
            action_dim: number of actions
            hidden_dim: hidden layer size
            lr: learning rate
            gamma: discount factor (importance of future rewards)
            epsilon_start: initial exploration rate
            epsilon_end: minimum exploration rate
            epsilon_decay: exploration rate decay coefficient
            buffer_size: replay buffer size
            batch_size: training batch size
            target_update_freq: target network update frequency
            use_prioritized_replay: whether to use prioritized experience replay
            use_dueling: whether to use Dueling DQN architecture
            device: computing device (cuda or cpu)
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self.use_prioritized_replay = use_prioritized_replay
        
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        print(f"Using device: {self.device}")

        NetworkClass = DuelingDQN if use_dueling else DQN
        self.q_network = NetworkClass(state_dim, action_dim, hidden_dim).to(self.device)
        self.target_network = NetworkClass(state_dim, action_dim, hidden_dim).to(self.device)

        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        self.optimizer = optim.Adam(self.q_network.parameters(), lr=lr)

        if use_prioritized_replay:
            self.replay_buffer = PrioritizedReplayBuffer(buffer_size)
        else:
            self.replay_buffer = ReplayBuffer(buffer_size)

        self.train_step = 0
        self.update_count = 0
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        Select action

        Uses epsilon-greedy strategy:
        - With probability epsilon, randomly select action (exploration)
        - With probability 1-epsilon, select action with maximum Q-value (exploitation)

        Args:
            state: current state
            training: whether in training mode (affects exploration)

        Returns:
            selected action index
        """
        if training and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)

        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)
            return q_values.argmax().item()

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """
        Store an experience to replay buffer
        """
        self.replay_buffer.push(state, action, reward, next_state, done)
    
    def train(self) -> Optional[float]:
        """
        Execute one training step

        Training process:
        1. Sample a batch of experiences from replay buffer
        2. Compute current Q-values
        3. Compute target Q-values (using Double DQN)
        4. Compute TD loss and backpropagate
        5. Periodically update target network

        Returns:
            training loss value, or None if buffer has insufficient data
        """
        if len(self.replay_buffer) < self.batch_size:
            return None

        if self.use_prioritized_replay:
            states, actions, rewards, next_states, dones, indices, weights = \
                self.replay_buffer.sample(self.batch_size)
            weights = torch.FloatTensor(weights).to(self.device)
        else:
            states, actions, rewards, next_states, dones = \
                self.replay_buffer.sample(self.batch_size)
            weights = torch.ones(self.batch_size).to(self.device)

        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)

        current_q = self.q_network(states).gather(1, actions.unsqueeze(1))

        with torch.no_grad():
            next_actions = self.q_network(next_states).argmax(1, keepdim=True)

            next_q = self.target_network(next_states).gather(1, next_actions)

            target_q = rewards.unsqueeze(1) + \
                       (1 - dones.unsqueeze(1)) * self.gamma * next_q

        td_errors = (current_q - target_q).detach().cpu().numpy()

        if self.use_prioritized_replay:
            self.replay_buffer.update_priorities(indices, td_errors.flatten())

        loss = (weights.unsqueeze(1) * (current_q - target_q) ** 2).mean()

        self.optimizer.zero_grad()
        loss.backward()

        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), max_norm=10)

        self.optimizer.step()

        self.train_step += 1

        if self.train_step % self.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())
            self.update_count += 1

        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        return loss.item()
    
    def save(self, path: str):
        """
        Save model checkpoint

        Saved contents include network weights, optimizer state, training progress, etc.,
        to enable resuming training later.

        Args:
            path: save path
        """
        checkpoint = {
            'q_network': self.q_network.state_dict(),
            'target_network': self.target_network.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'train_step': self.train_step,
            'update_count': self.update_count
        }
        torch.save(checkpoint, path)
        print(f"Model saved to: {path}")

    def load(self, path: str):
        """
        Load model checkpoint

        Args:
            path: checkpoint file path
        """
        checkpoint = torch.load(path, map_location=self.device)

        self.q_network.load_state_dict(checkpoint['q_network'])
        self.target_network.load_state_dict(checkpoint['target_network'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint['epsilon']
        self.train_step = checkpoint['train_step']
        self.update_count = checkpoint.get('update_count', 0)

        print(f"Model loaded from {path}")
        print(f"  Training steps: {self.train_step}, Epsilon: {self.epsilon:.4f}")

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """
        Get Q-values for all actions in a given state

        Primarily used for debugging and analysis.

        Args:
            state: state

        Returns:
            array of Q-values
        """
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)
            return q_values.cpu().numpy().flatten()


if __name__ == '__main__':
    print("Testing DQN components...")

    state_dim = 20
    action_dim = 4

    dqn = DQN(state_dim, action_dim)
    test_input = torch.randn(32, state_dim)
    output = dqn(test_input)
    print(f"DQN output shape: {output.shape}")

    dueling_dqn = DuelingDQN(state_dim, action_dim)
    output = dueling_dqn(test_input)
    print(f"Dueling DQN output shape: {output.shape}")

    buffer = ReplayBuffer(1000)
    for i in range(100):
        state = np.random.randn(state_dim).astype(np.float32)
        action = np.random.randint(action_dim)
        reward = np.random.randn()
        next_state = np.random.randn(state_dim).astype(np.float32)
        done = i == 99
        buffer.push(state, action, reward, next_state, done)

    states, actions, rewards, next_states, dones = buffer.sample(32)
    print(f"Sampled state shape: {states.shape}")

    agent = DQNAgent(state_dim, action_dim)
    state = np.random.randn(state_dim).astype(np.float32)
    action = agent.select_action(state)
    print(f"Selected action: {action}")

    print("\nAll components tested successfully!")
