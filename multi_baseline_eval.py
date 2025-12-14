"""
Multi-baseline evaluation script for single-intersection traffic signal control.

Baselines:
- RL_DQN: your trained DQN / Double DQN / Dueling DQN model (depending on how you trained)
- Tabular Q-learning (discretized small state space)
- Tabular Expected SARSA
- Fixed-cycle control (average switching)
- Longest-queue-first control

Supports optional virtual pedestrians via SumoTrafficEnv(enable_pedestrians=True).
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import torch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# make sure we can import src/environment and src/agent
sys.path.append(str(Path(__file__).parent / "src"))

from environment import SumoTrafficEnv
from agent import DQNAgent


# ======================= Controller base class =======================

class BaseController:
    def reset(self):
        """Called at the beginning of each episode."""
        pass

    def select_action(self, state, info: Dict[str, Any]) -> int:
        """Given state and info, return an action index."""
        raise NotImplementedError

    def observe(
        self,
        state,
        info: Dict[str, Any],
        action: int,
        reward: float,
        next_state,
        next_info: Dict[str, Any],
        done: bool
    ):
        """Optional: called after each environment transition (for learning baselines)."""
        pass


# ======================= DQN-based controller =======================

class DQNController(BaseController):
    """Wrapper around your trained DQNAgent for evaluation only."""

    def __init__(self, env: SumoTrafficEnv, model_path: str):
        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n
        self.agent = DQNAgent(state_dim, action_dim)
        self.agent.epsilon = 0.0  # force pure exploitation

        checkpoint = torch.load(model_path, map_location=self.agent.device)
        if isinstance(checkpoint, dict):
            if "q_network" in checkpoint:
                self.agent.q_network.load_state_dict(checkpoint["q_network"])
            elif "model_state_dict" in checkpoint:
                self.agent.q_network.load_state_dict(checkpoint["model_state_dict"])
            else:
                self.agent.q_network.load_state_dict(checkpoint)
        else:
            self.agent.q_network.load_state_dict(checkpoint)
        self.agent.q_network.eval()

    def select_action(self, state, info: Dict[str, Any]) -> int:
        return self.agent.select_action(state, training=False)


# ======================= Fixed cycle controller =======================

class FixedCycleController(BaseController):
    """Fixed cycle: each phase gets a fixed green duration (cycle_time per phase)."""

    def __init__(self, cycle_time: int):
        self.cycle_time = cycle_time

    def select_action(self, state, info: Dict[str, Any]) -> int:
        # info['step'] is in seconds
        step = info["step"]
        phase_index = (step // self.cycle_time) % 2  # 2 phases: 0 or 1
        return int(phase_index)


# ======================= Longest queue controller =======================

class LongestQueueController(BaseController):
    """
    Longest-queue-first: choose phase serving direction with longer queue.
    Phase 0: NS major direction
    Phase 1: EW minor direction
    Uses info['queue_ns'] and info['queue_ew'] (provided by environment).
    """

    def select_action(self, state, info: Dict[str, Any]) -> int:
        queue_ns = info.get("queue_ns", 0)
        queue_ew = info.get("queue_ew", 0)
        # If close, keep current phase to avoid too frequent switching
        if abs(queue_ns - queue_ew) < 2:
            return info["current_phase"]
        return 0 if queue_ns >= queue_ew else 1


# ======================= Tabular RL controller (Q-learning / Expected SARSA) =======================

class TabularController(BaseController):
    """
    Small tabular RL controller on top of a discretized state summary.

    mode:
        - 'q_learning': Q-learning target
        - 'sarsa': Expected SARSA target (using epsilon-greedy policy)
    """

    def __init__(
        self,
        mode: str = "q_learning",
        alpha: float = 0.5,
        gamma: float = 0.95,
        epsilon: float = 0.1
    ):
        assert mode in ("q_learning", "sarsa")
        self.mode = mode
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

        # 2 (phase) * 3 (NS-EW diff bins) * 3 (load bins) = 18 states
        self.num_states = 18
        self.num_actions = 2
        self.Q = np.zeros((self.num_states, self.num_actions), dtype=np.float32)

    def reset(self):
        self.last_state_idx = None
        self.last_action = None

    # discretization helper
    def _discretize(self, info: Dict[str, Any]) -> int:
        phase = int(info["current_phase"])  # 0 or 1
        ns = info.get("queue_ns", 0)
        ew = info.get("queue_ew", 0)
        total = info.get("total_queue", ns + ew)

        diff = ns - ew
        if diff <= -3:
            diff_bin = 0
        elif diff >= 3:
            diff_bin = 2
        else:
            diff_bin = 1

        if total <= 5:
            load_bin = 0
        elif total <= 15:
            load_bin = 1
        else:
            load_bin = 2

        # phase * 9 + diff_bin * 3 + load_bin
        return phase * 9 + diff_bin * 3 + load_bin

    def _epsilon_greedy(self, state_idx: int) -> int:
        if np.random.rand() < self.epsilon:
            return np.random.randint(self.num_actions)
        return int(np.argmax(self.Q[state_idx]))

    def select_action(self, state, info: Dict[str, Any]) -> int:
        s_idx = self._discretize(info)
        a = self._epsilon_greedy(s_idx)
        return a

    def observe(
        self,
        state,
        info: Dict[str, Any],
        action: int,
        reward: float,
        next_state,
        next_info: Dict[str, Any],
        done: bool
    ):
        s_idx = self._discretize(info)
        a = action
        next_s_idx = self._discretize(next_info)

        if self.mode == "q_learning":
            next_q = np.max(self.Q[next_s_idx])
            target = reward + (0.0 if done else self.gamma * next_q)
        else:  # Expected SARSA
            q_next = self.Q[next_s_idx]
            greedy_a = int(np.argmax(q_next))
            # epsilon-greedy behavior policy
            probs = np.ones(self.num_actions) * (self.epsilon / self.num_actions)
            probs[greedy_a] += (1.0 - self.epsilon)
            expected_q = np.sum(probs * q_next)
            target = reward + (0.0 if done else self.gamma * expected_q)

        self.Q[s_idx, a] = (
            (1.0 - self.alpha) * self.Q[s_idx, a] + self.alpha * target
        )


# ======================= Evaluation loop =======================

def run_one_controller(
    env: SumoTrafficEnv,
    controller: BaseController,
    num_episodes: int
) -> Dict[str, Any]:
    """Run given controller in env for num_episodes, collect statistics."""
    episode_stats: List[Dict[str, Any]] = []

    for ep in range(num_episodes):
        state, info = env.reset()
        controller.reset()
        done = False
        truncated = False

        total_reward = 0.0
        queue_history = []
        waiting_time_history = []
        ped_wait_history = []

        while not done and not truncated:
            action = controller.select_action(state, info)
            next_state, reward, done, truncated, next_info = env.step(action)

            controller.observe(state, info, action, reward, next_state, next_info, done)

            total_reward += reward
            queue_history.append(next_info["total_queue"])
            waiting_time_history.append(next_info.get("total_waiting_time", 0.0))

            if "total_ped_wait_time" in next_info:
                ped_wait_history.append(next_info["total_ped_wait_time"])

            state, info = next_state, next_info

        episode_stats.append(
            {
                "reward": total_reward,
                "avg_queue": float(np.mean(queue_history)),
                "max_queue": float(np.max(queue_history)),
                "final_throughput": next_info["throughput"],
                "total_waiting_time": next_info.get("total_waiting_time", 0.0),
                "total_ped_wait_time": next_info.get("total_ped_wait_time", 0.0),
            }
        )

        print(
            f"  Episode {ep+1}/{num_episodes}: "
            f"reward={total_reward:.2f}, "
            f"avg queue={np.mean(queue_history):.2f}, "
            f"max queue={np.max(queue_history):.0f}, "
            f"throughput={next_info['throughput']}"
        )

    # aggregate
    rewards = [e["reward"] for e in episode_stats]
    avg_queues = [e["avg_queue"] for e in episode_stats]
    max_queues = [e["max_queue"] for e in episode_stats]
    throughputs = [e["final_throughput"] for e in episode_stats]
    waiting_times = [e["total_waiting_time"] for e in episode_stats]
    ped_waits = [e["total_ped_wait_time"] for e in episode_stats]

    summary = {
        "mean_reward": float(np.mean(rewards)),
        "std_reward": float(np.std(rewards)),
        "mean_avg_queue": float(np.mean(avg_queues)),
        "mean_max_queue": float(np.mean(max_queues)),
        "mean_throughput": float(np.mean(throughputs)),
        "mean_waiting_time": float(np.mean(waiting_times)),
        "mean_ped_wait_time": float(np.mean(ped_waits)) if ped_waits else 0.0,
    }

    return {
        "episode_stats": episode_stats,
        "summary": summary,
    }


def compare_baselines(
    net_file: str,
    route_files: List[str],
    model_path: str,
    num_episodes: int = 5,
    enable_pedestrians: bool = False
):
    """Evaluate multiple controllers across multiple scenarios."""
    print("=" * 80)
    print(f"Multi-Scenario Baseline Comparison")
    print(f"Scenarios: {route_files}")
    print("=" * 80)

    # Store results for all scenarios
    all_scenarios_results: Dict[str, Dict[str, Any]] = {}

    for route_file in route_files:
        # Extract scenario name from route file
        scenario_name = Path(route_file).stem  # e.g., "morning_rush" or "off_peak"

        print(f"\n{'='*80}")
        print(f"Evaluating Scenario: {scenario_name}")
        print(f"{'='*80}")

        reward_weights = {
            "queue": 0.5,
            "waiting_time": 0.3,
            "co2": 0.1,
            "switch": 0.1,
            "ped_wait": 0.3 if enable_pedestrians else 0.0,
        }

        env = SumoTrafficEnv(
            net_file=net_file,
            route_file=route_file,
            use_gui=False,
            num_seconds=3600,
            reward_weights=reward_weights,
            enable_pedestrians=enable_pedestrians,
        )

        controllers: Dict[str, BaseController] = {}

        # 1. RL DQN (your trained model)
        controllers["DQN"] = DQNController(env, model_path=model_path)

        # 2. Fixed cycle 30s and 60s
        controllers["Fixed_30s"] = FixedCycleController(cycle_time=30)
        controllers["Fixed_60s"] = FixedCycleController(cycle_time=60)

        # 3. Longest queue first
        controllers["LongestQueue"] = LongestQueueController()

        # 4. Tabular Q-learning
        controllers["Tabular_Q"] = TabularController(mode="q_learning")

        # 5. Tabular Expected SARSA
        controllers["Tabular_SARSA"] = TabularController(mode="sarsa")

        scenario_results: Dict[str, Any] = {}
        for name, controller in controllers.items():
            print(f"\n--- Evaluating controller: {name} ---")
            res = run_one_controller(env, controller, num_episodes=num_episodes)
            scenario_results[name] = res
            s = res["summary"]
            print(
                f"[{name}] "
                f"reward={s['mean_reward']:.2f}, "
                f"avg_queue={s['mean_avg_queue']:.2f}, "
                f"max_queue={s['mean_max_queue']:.2f}, "
                f"throughput={s['mean_throughput']:.2f}, "
                f"veh_wait={s['mean_waiting_time']:.1f}, "
                f"ped_wait={s['mean_ped_wait_time']:.1f}"
            )

        env.close()
        all_scenarios_results[scenario_name] = scenario_results

    # Generate beautiful comparison charts
    output_dir = Path(model_path).parent
    os.makedirs(output_dir, exist_ok=True)

    generate_comparison_plots(all_scenarios_results, output_dir)

    return all_scenarios_results


def generate_comparison_plots(all_scenarios_results, output_dir):
    """Generate comprehensive and beautiful comparison charts for multiple scenarios"""

    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.facecolor'] = 'white'

    # Get scenarios and methods
    scenarios = list(all_scenarios_results.keys())
    first_scenario = scenarios[0]
    methods = list(all_scenarios_results[first_scenario].keys())
    n_methods = len(methods)
    n_scenarios = len(scenarios)

    # Color scheme (DQN in green, others in different colors)
    colors = {
        'DQN': '#2ecc71',           # Green for your DQN
        'Fixed_30s': '#e74c3c',     # Red
        'Fixed_60s': '#e67e22',     # Orange
        'LongestQueue': '#3498db',  # Blue
        'Tabular_Q': '#9b59b6',     # Purple
        'Tabular_SARSA': '#95a5a6'  # Gray
    }

    # Create 2x2 subplot layout
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('Multi-Scenario Multi-Baseline Performance Comparison',
                 fontsize=20, fontweight='bold', y=0.995)

    metrics = [
        ('mean_reward', 'Average Reward', 'Reward'),
        ('mean_avg_queue', 'Average Queue Length', 'Queue Length (vehicles)'),
        ('mean_throughput', 'Average Throughput', 'Throughput (vehicles)'),
        ('mean_max_queue', 'Maximum Queue Length', 'Max Queue (vehicles)')
    ]

    # Grouped bar chart for multi-scenario comparison
    for idx, (metric_key, title, ylabel) in enumerate(metrics):
        ax = axes[idx // 2, idx % 2]

        x = np.arange(n_methods)
        width = 0.8 / n_scenarios  # Divide bar width by number of scenarios

        for s_idx, scenario in enumerate(scenarios):
            values = [all_scenarios_results[scenario][m]["summary"][metric_key] for m in methods]
            offset = (s_idx - n_scenarios/2 + 0.5) * width

            bars = ax.bar(x + offset, values, width,
                         label=scenario.replace('_', ' ').title(),
                         color=[colors.get(m, '#34495e') for m in methods],
                         alpha=0.7 + s_idx * 0.15,  # Different opacity for each scenario
                         edgecolor='white',
                         linewidth=1.5)

            # Add value labels on bars (only for small number of scenarios)
            if n_scenarios <= 2:
                for bar, val in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{val:.1f}',
                           ha='center', va='bottom' if height >= 0 else 'top',
                           fontsize=8, fontweight='bold')

        ax.set_xlabel('Method', fontsize=13, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=13, fontweight='bold')
        ax.set_title(title, fontsize=15, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(methods, rotation=15, ha='right', fontsize=10)
        ax.legend(fontsize=10, loc='best')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()

    plot_path = output_dir / 'multi_baseline_comparison.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"\n{'='*80}")
    print(f"✓ Comparison chart saved: {plot_path}")
    print(f"{'='*80}")

    # Also create a summary table visualization
    create_summary_table(all_scenarios_results, output_dir)


def create_summary_table(all_scenarios_results, output_dir):
    """Generate a beautiful summary table comparing all methods across all scenarios"""

    scenarios = list(all_scenarios_results.keys())
    first_scenario = scenarios[0]
    methods = list(all_scenarios_results[first_scenario].keys())

    # Prepare table data with scenario headers
    metrics_info = [
        ('mean_reward', 'Reward', '%.1f'),
        ('mean_avg_queue', 'Avg Queue', '%.2f'),
        ('mean_max_queue', 'Max Queue', '%.1f'),
        ('mean_throughput', 'Throughput', '%.1f'),
        ('mean_waiting_time', 'Wait Time', '%.0f')
    ]

    # Create figure for table (adjust size based on scenarios)
    fig_height = 4 + len(methods) * 0.5
    fig_width = 6 + len(scenarios) * len(metrics_info) * 0.8
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis('off')

    # Build table headers: Method | Scenario1_Metric1 | Scenario1_Metric2 | ... | Scenario2_Metric1 | ...
    col_labels = ['Method']
    for scenario in scenarios:
        scenario_name = scenario.replace('_', ' ').title()
        for _, metric_name, _ in metrics_info:
            col_labels.append(f'{scenario_name}\n{metric_name}')

    # Build table data
    table_data = []
    for method in methods:
        row = [method]
        for scenario in scenarios:
            for metric_key, _, fmt in metrics_info:
                value = all_scenarios_results[scenario][method]["summary"][metric_key]
                row.append(fmt % value)
        table_data.append(row)

    # Create table with beautiful styling
    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]
    )

    # Style the table
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.2)

    # Color scheme matching the bar charts
    colors = {
        'DQN': '#2ecc71',
        'Fixed_30s': '#e74c3c',
        'Fixed_60s': '#e67e22',
        'LongestQueue': '#3498db',
        'Tabular_Q': '#9b59b6',
        'Tabular_SARSA': '#95a5a6'
    }

    # Style header row
    for i in range(len(col_labels)):
        cell = table._cells[(0, i)]
        cell.set_facecolor('#34495e')
        cell.set_text_props(weight='bold', color='white', fontsize=10)
        cell.set_edgecolor('white')
        cell.set_linewidth(2)

    # Style data rows
    for i, method in enumerate(methods):
        # Color the method name cell
        cell = table._cells[(i+1, 0)]
        cell.set_facecolor(colors.get(method, '#ecf0f1'))
        cell.set_text_props(weight='bold', fontsize=10)
        cell.set_edgecolor('white')
        cell.set_linewidth(2)

        # Style data cells - highlight best values per scenario per metric
        for j in range(1, len(col_labels)):
            cell = table._cells[(i+1, j)]
            cell.set_facecolor('#f8f9fa')
            cell.set_edgecolor('white')
            cell.set_linewidth(1.5)

            # Determine which metric this column represents
            col_idx = (j - 1) % len(metrics_info)
            metric_key = metrics_info[col_idx][0]

            # Extract values for this specific column across all methods
            col_values = [float(table_data[k][j]) for k in range(len(methods))]
            current_val = float(table_data[i][j])

            # Highlight best values (green bold)
            if metric_key in ['mean_reward', 'mean_throughput']:  # Higher is better
                if current_val == max(col_values):
                    cell.set_text_props(weight='bold', color='#27ae60')
            else:  # Lower is better (queue, wait time)
                if current_val == min(col_values):
                    cell.set_text_props(weight='bold', color='#27ae60')

    # Add title
    plt.title('Performance Summary Table - All Scenarios & Baselines',
              fontsize=16, fontweight='bold', pad=20)

    # Save table
    table_path = output_dir / 'performance_summary_table.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"✓ Summary table saved: {table_path}")

    # Also save as CSV for easy reference
    csv_path = output_dir / 'performance_summary.csv'
    import csv
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(col_labels)
        writer.writerows(table_data)

    print(f"✓ CSV summary saved: {csv_path}")

    # Also save a simpler version with Ped Wait column included
    simple_csv_path = output_dir / 'performance_summary_with_ped.csv'
    simple_col_labels = ['Scenario', 'Method', 'Avg Reward', 'Avg Queue', 'Max Queue',
                         'Throughput', 'Waiting Time', 'Ped Wait']
    simple_table_data = []

    for scenario in scenarios:
        for method in methods:
            summary = all_scenarios_results[scenario][method]["summary"]
            simple_table_data.append([
                scenario.replace('_', ' ').title(),
                method,
                f"{summary['mean_reward']:.1f}",
                f"{summary['mean_avg_queue']:.2f}",
                f"{summary['mean_max_queue']:.1f}",
                f"{summary['mean_throughput']:.1f}",
                f"{summary['mean_waiting_time']:.0f}",
                f"{summary['mean_ped_wait_time']:.1f}"
            ])

    with open(simple_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(simple_col_labels)
        writer.writerows(simple_table_data)

    print(f"✓ Detailed CSV summary saved: {simple_csv_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-baseline evaluation for traffic signal control"
    )
    parser.add_argument(
        "--net-file",
        type=str,
        default="networks/single_intersection.net.xml",
        help="SUMO network file (.net.xml)",
    )
    parser.add_argument(
        "--route-files",
        type=str,
        nargs='+',
        default=["scenarios/morning_rush.rou.xml", "scenarios/off_peak.rou.xml"],
        help="Route files (.rou.xml) - multiple scenarios",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="Trained RL model path (DQN / Double / Dueling)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=5,
        help="Number of episodes per controller",
    )
    parser.add_argument(
        "--enable-pedestrians",
        action="store_true",
        help="Enable virtual pedestrians in environment",
    )

    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"Error: model file not found: {args.model_path}")
        sys.exit(1)

    compare_baselines(
        net_file=args.net_file,
        route_files=args.route_files,
        model_path=args.model_path,
        num_episodes=args.episodes,
        enable_pedestrians=args.enable_pedestrians,
    )
