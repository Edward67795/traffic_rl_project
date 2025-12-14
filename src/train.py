"""
Traffic Signal Control DQN Training Main Program

This script coordinates the entire training process, including:
- Creating and configuring environment
- Initializing DQN agent
- Executing training loop
- Recording logs and saving checkpoints
- Evaluating trained model

Running example:
    python train.py --net_file networks/single_intersection.net.xml \
                    --route_file scenarios/morning_rush.rou.xml \
                    --num_episodes 500

View training curves with TensorBoard:
    tensorboard --logdir runs/
"""

import os
import sys
import argparse
from datetime import datetime
import json
import numpy as np
from tqdm import tqdm

import torch
from torch.utils.tensorboard import SummaryWriter

from environment import SumoTrafficEnv
from agent import DQNAgent


def parse_args():
    """
    Parse command line parameters

    These parameters allow users to customize training configuration without modifying code.
    """
    parser = argparse.ArgumentParser(
        description='Traffic Signal Control DQN Training',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    env_group = parser.add_argument_group('Environment configuration')
    env_group.add_argument(
        '--net_file',
        type=str,
        required=True,
        help='SUMO network file path (.net.xml)'
    )
    env_group.add_argument(
        '--route_file',
        type=str,
        required=True,
        help='Vehicle route file path (.rou.xml)'
    )
    env_group.add_argument(
        '--gui',
        action='store_true',
        help='Enable SUMO graphical interface (for debugging, significantly slows training)'
    )
    env_group.add_argument(
        '--episode_length',
        type=int,
        default=3600,
        help='Simulation duration per episode (seconds)'
    )
    env_group.add_argument(
        '--delta_time',
        type=int,
        default=5,
        help='Decision interval (seconds), i.e., how often to make action decision'
    )
    env_group.add_argument(
        '--yellow_time',
        type=int,
        default=3,
        help='Yellow light duration (seconds)'
    )
    env_group.add_argument(
        '--min_green',
        type=int,
        default=10,
        help='Minimum green light time (seconds)'
    )
    env_group.add_argument(
        '--max_green',
        type=int,
        default=60,
        help='Maximum green light time (seconds)'
    )
    env_group.add_argument(
        '--enable-pedestrians',
        action='store_true',
        help='Enable virtual pedestrian traffic modeling (adds 4 pedestrian features to state)'
    )

    # ======== Training Parameters ========
    train_group = parser.add_argument_group('Training configuration')
    train_group.add_argument(
        '--num_episodes',
        type=int,
        default=500,
        help='Number of training episodes'
    )
    train_group.add_argument(
        '--hidden_dim',
        type=int,
        default=128,
        help='Neural network hidden layer dimension'
    )
    train_group.add_argument(
        '--lr',
        type=float,
        default=1e-3,
        help='Learning rate'
    )
    train_group.add_argument(
        '--gamma',
        type=float,
        default=0.99,
        help='Discount factor (0-1), controls importance of future rewards'
    )
    train_group.add_argument(
        '--batch_size',
        type=int,
        default=64,
        help='Training batch size'
    )
    train_group.add_argument(
        '--buffer_size',
        type=int,
        default=100000,
        help='Experience replay buffer size'
    )
    train_group.add_argument(
        '--target_update',
        type=int,
        default=100,
        help='Target network update frequency (update every N steps)'
    )
    
    explore_group = parser.add_argument_group('Exploration strategy')
    explore_group.add_argument(
        '--epsilon_start',
        type=float,
        default=1.0,
        help='Initial exploration rate (100% random)'
    )
    explore_group.add_argument(
        '--epsilon_end',
        type=float,
        default=0.01,
        help='Final exploration rate (1% random)'
    )
    explore_group.add_argument(
        '--epsilon_decay',
        type=float,
        default=0.995,
        help='Exploration rate decay coefficient'
    )
    
    # ======== Advanced options ========
    advanced_group = parser.add_argument_group('Advanced options')
    advanced_group.add_argument(
        '--use_dueling',
        action='store_true',
        default=True,
        help='Use Dueling DQN architecture'
    )
    advanced_group.add_argument(
        '--use_per',
        action='store_true',
        default=False,
        help='Use prioritized experience replay'
    )
    advanced_group.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed (for experiment reproducibility)'
    )
    
    log_group = parser.add_argument_group('Logging and saving')
    log_group.add_argument(
        '--save_freq',
        type=int,
        default=50,
        help='Checkpoint save frequency (save every N episodes)'
    )
    log_group.add_argument(
        '--log_dir',
        type=str,
        default='runs',
        help='TensorBoard log directory'
    )
    log_group.add_argument(
        '--exp_name',
        type=str,
        default='traffic_dqn',
        help='Experiment name (for log directory naming)'
    )
    
    reward_group = parser.add_argument_group('Reward function weights')
    reward_group.add_argument(
        '--reward_queue',
        type=float,
        default=0.5,
        help='Queue length penalty weight'
    )
    reward_group.add_argument(
        '--reward_wait',
        type=float,
        default=0.3,
        help='Waiting time penalty weight'
    )
    reward_group.add_argument(
        '--reward_co2',
        type=float,
        default=0.1,
        help='CO2 emission penalty weight'
    )
    reward_group.add_argument(
        '--reward_switch',
        type=float,
        default=0.1,
        help='Signal switching penalty weight'
    )
    reward_group.add_argument(
        '--reward_ped_wait',
        type=float,
        default=0.3,
        help='Pedestrian waiting time penalty weight (only used when --enable-pedestrians is set)'
    )

    return parser.parse_args()


def set_seed(seed: int):
    """
    Set random seed to ensure experiment reproducibility

    Args:
        seed: random seed
    """
    if seed is not None:
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
        print(f"Random seed set to: {seed}")


def create_log_dir(args) -> str:
    """
    Create log directory

    Directory naming format: {log_dir}/{exp_name}_{timestamp}

    Returns:
        log directory path
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(args.log_dir, f'{args.exp_name}_{timestamp}')
    os.makedirs(log_path, exist_ok=True)
    
    # Save configuration file
    config_path = os.path.join(log_path, 'config.json')
    with open(config_path, 'w') as f:
        json.dump(vars(args), f, indent=2)
    
    print(f"Log directory: {log_path}")
    return log_path


def evaluate_agent(env, agent, num_episodes: int = 5) -> dict:
    """
    Evaluate agent performance

    Run multiple episodes without exploration (epsilon=0),
    collect performance metric statistics.

    Args:
        env: environment
        agent: DQN agent
        num_episodes: number of evaluation episodes

    Returns:
        dictionary containing mean and standard deviation of various metrics
    """
    rewards = []
    queues = []
    waiting_times = []
    throughputs = []
    
    for _ in range(num_episodes):
        state, _ = env.reset()
        episode_reward = 0
        episode_queue = 0
        steps = 0
        
        while True:
            # No exploration, only exploitation
            action = agent.select_action(state, training=False)
            next_state, reward, done, truncated, info = env.step(action)
            
            episode_reward += reward
            episode_queue += info['total_queue']
            steps += 1
            state = next_state
            
            if done or truncated:
                break
        
        rewards.append(episode_reward)
        queues.append(episode_queue / steps)
        waiting_times.append(info.get('total_waiting_time', 0))
        throughputs.append(info.get('throughput', 0))
    
    return {
        'mean_reward': np.mean(rewards),
        'std_reward': np.std(rewards),
        'mean_queue': np.mean(queues),
        'std_queue': np.std(queues),
        'mean_waiting_time': np.mean(waiting_times),
        'mean_throughput': np.mean(throughputs)
    }


def train(args):
    """
    Main training loop

    This function executes the complete training process:
    1. Create environment and agent
    2. Run training loop
    3. Record logs and save model
    """
    set_seed(args.seed)

    log_dir = create_log_dir(args)
    writer = SummaryWriter(log_dir)
    
    # Build reward weight configuration
    reward_weights = {
        'queue': args.reward_queue,
        'waiting_time': args.reward_wait,
        'co2': args.reward_co2,
        'switch': args.reward_switch,
        'ped_wait': args.reward_ped_wait if hasattr(args, 'enable_pedestrians') and args.enable_pedestrians else 0.0
    }

    print("\n" + "="*60)
    print("Create SUMO environment...")
    print("="*60)

    enable_peds = hasattr(args, 'enable_pedestrians') and args.enable_pedestrians
    if enable_peds:
        print("Pedestrian support: ENABLED (state_dim will be 43)")
        print(f"Pedestrian wait reward weight: {reward_weights['ped_wait']}")
    else:
        print("Pedestrian support: DISABLED (state_dim will be 39)")

    env = SumoTrafficEnv(
        net_file=args.net_file,
        route_file=args.route_file,
        use_gui=args.gui,
        num_seconds=args.episode_length,
        delta_time=args.delta_time,
        yellow_time=args.yellow_time,
        min_green=args.min_green,
        max_green=args.max_green,
        reward_weights=reward_weights,
        enable_pedestrians=enable_peds
    )
    
    # Get state and action space dimensions
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n
    
    print(f"State space dimension: {state_dim}")
    print(f"Action space dimension: {action_dim}")
    
    print("\n" + "="*60)
    print("Create DQN agent...")
    print("="*60)
    
    agent = DQNAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=args.hidden_dim,
        lr=args.lr,
        gamma=args.gamma,
        epsilon_start=args.epsilon_start,
        epsilon_end=args.epsilon_end,
        epsilon_decay=args.epsilon_decay,
        buffer_size=args.buffer_size,
        batch_size=args.batch_size,
        target_update_freq=args.target_update,
        use_prioritized_replay=args.use_per,
        use_dueling=args.use_dueling
    )
    
    # Training statistics
    best_reward = float('-inf')
    episode_rewards = []
    episode_queues = []
    
    print("\n" + "="*60)
    print("Start training...")
    print("="*60)
    
    # Main training loop
    for episode in tqdm(range(args.num_episodes), desc='Training progress'):
        # Reset environment
        state, _ = env.reset(seed=args.seed + episode if args.seed else None)
        
        # Episode statistics
        episode_reward = 0
        episode_queue = 0
        episode_loss = 0
        train_count = 0
        step = 0
        
        # Episode inner loop
        while True:
            # Select action
            action = agent.select_action(state, training=True)
            
            # Execute action
            next_state, reward, done, truncated, info = env.step(action)
            
            # Store experience
            agent.store_transition(state, action, reward, next_state, done)
            
            # Training
            loss = agent.train()
            if loss is not None:
                episode_loss += loss
                train_count += 1
            
            # Update statistics
            episode_reward += reward
            episode_queue += info['total_queue']
            step += 1
            
            # State transition
            state = next_state
            
            # Check termination condition
            if done or truncated:
                break
        
        # Episode ended, compute statistics
        avg_queue = episode_queue / step if step > 0 else 0
        avg_loss = episode_loss / train_count if train_count > 0 else 0
        
        episode_rewards.append(episode_reward)
        episode_queues.append(avg_queue)
        
        # Record to TensorBoard
        writer.add_scalar('Reward/episode', episode_reward, episode)
        writer.add_scalar('Queue/average', avg_queue, episode)
        writer.add_scalar('Training/epsilon', agent.epsilon, episode)
        writer.add_scalar('Training/loss', avg_loss, episode)
        writer.add_scalar('Training/buffer_size', len(agent.replay_buffer), episode)
        
        if 'throughput' in info:
            writer.add_scalar('Performance/throughput', info['throughput'], episode)
        if 'total_waiting_time' in info:
            writer.add_scalar('Performance/total_waiting_time', info['total_waiting_time'], episode)
        
        # Check if best model
        if episode_reward > best_reward:
            best_reward = episode_reward
            agent.save(os.path.join(log_dir, 'best_model.pt'))
        
        # Periodically save checkpoint
        if (episode + 1) % args.save_freq == 0:
            agent.save(os.path.join(log_dir, f'checkpoint_ep{episode+1}.pt'))
            
            # Compute average over recent N episodes
            recent_rewards = episode_rewards[-args.save_freq:]
            recent_queues = episode_queues[-args.save_freq:]
            
            print(f'\n[Episode {episode+1}]')
            print(f'  Recent{args.save_freq}episodes average reward: {np.mean(recent_rewards):.2f}')
            print(f'  Recent{args.save_freq}episodes average queue: {np.mean(recent_queues):.2f}')
            print(f'  Current epsilon: {agent.epsilon:.4f}')
            print(f'  Buffer size: {len(agent.replay_buffer)}')
        
        # Periodic evaluation (every 100 episodes)
        if (episode + 1) % 100 == 0:
            print(f'\nEvaluating...')
            eval_results = evaluate_agent(env, agent, num_episodes=3)
            
            writer.add_scalar('Eval/mean_reward', eval_results['mean_reward'], episode)
            writer.add_scalar('Eval/mean_queue', eval_results['mean_queue'], episode)
            
            print(f"  Evaluation reward: {eval_results['mean_reward']:.2f} ± {eval_results['std_reward']:.2f}")
            print(f"  Evaluation queue: {eval_results['mean_queue']:.2f} ± {eval_results['std_queue']:.2f}")
    
    print("\n" + "="*60)
    print("Training completed!")
    print("="*60)

    agent.save(os.path.join(log_dir, 'final_model.pt'))

    print("\nPerforming final evaluation...")
    final_eval = evaluate_agent(env, agent, num_episodes=10)
    
    print(f"\nFinal evaluation results:")
    print(f"  Average reward: {final_eval['mean_reward']:.2f} ± {final_eval['std_reward']:.2f}")
    print(f"  Average queue length: {final_eval['mean_queue']:.2f}")
    print(f"  Average throughput: {final_eval['mean_throughput']:.2f}")

    eval_path = os.path.join(log_dir, 'evaluation_results.json')
    with open(eval_path, 'w') as f:
        json.dump(final_eval, f, indent=2)

    env.close()
    writer.close()

    print(f"\nBest reward: {best_reward:.2f}")
    print(f"Logs and model saved to: {log_dir}")
    print("\nView training curves:")
    print(f"  tensorboard --logdir {args.log_dir}")


def main():
    """Main function"""
    args = parse_args()
    
    # Print configuration summary
    print("\n" + "="*60)
    print("Traffic Signal Control - DQNTraining")
    print("="*60)
    print(f"\nNetwork file: {args.net_file}")
    print(f"Route file: {args.route_file}")
    print(f"Training episodes: {args.num_episodes}")
    print(f"Episode length: {args.episode_length}seconds")
    print(f"Decision interval: {args.delta_time}seconds")
    print(f"Using GPU: {torch.cuda.is_available()}")
    
    if args.gui:
        print("\nWarning: GUI mode enabled, training speed will significantly decrease！")
    
    # Start training
    train(args)


if __name__ == '__main__':
    main()
