"""
Baseline Comparison Script
Compare RL Model vs Fixed-time Traffic Light Control
"""
import os
import sys
import torch
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

sys.path.append(str(Path(__file__).parent / 'src'))

from environment import SumoTrafficEnv
from agent import DQNAgent

def evaluate_baseline(scenario: str, num_episodes: int = 5, cycle_time: int = 60):
    """
    Evaluate fixed-time traffic light baseline

    Args:
        scenario: Scenario name
        num_episodes: Number of episodes to run
        cycle_time: Green light duration per phase (seconds)
    """
    print(f"Evaluate fixed-time traffic light baseline (per phase{cycle_time}seconds green light)")

    env = SumoTrafficEnv(
        net_file="networks/single_intersection.net.xml",
        route_file=f"scenarios/{scenario}.rou.xml",
        use_gui=False,
        num_seconds=3600
    )

    episode_stats = []

    for ep in range(num_episodes):
        state, _ = env.reset()
        done = False
        truncated = False

        total_reward = 0
        queue_history = []
        waiting_time_history = []
        step_count = 0

        # Fixed-time control: switch phase every cycle_time seconds
        current_phase = 0
        phase_timer = 0

        while not done and not truncated:
            # Fixed-time strategy
            if phase_timer >= cycle_time:
                current_phase = 1 - current_phase  # Switch phase
                phase_timer = 0

            action = current_phase
            next_state, reward, done, truncated, info = env.step(action)

            total_reward += reward
            queue_history.append(info['total_queue'])
            waiting_time_history.append(info['total_waiting_time'])
            state = next_state
            step_count += 1
            phase_timer += 1

        episode_stats.append({
            'reward': total_reward,
            'avg_queue': np.mean(queue_history),
            'max_queue': np.max(queue_history),
            'final_throughput': info['throughput'],
            'total_waiting_time': info['total_waiting_time']
        })

        print(f"  Episode {ep+1}/{num_episodes}: "
              f"reward={total_reward:.2f}, "
              f"avg queue={np.mean(queue_history):.2f}, "
              f"max queue={np.max(queue_history):.0f}, "
              f"throughput={info['throughput']}")

    env.close()

    return episode_stats

def evaluate_rl_model(model_path: str, scenario: str, num_episodes: int = 5):
    """Evaluate RL model"""
    print(f"Evaluate RL agent model")

    env = SumoTrafficEnv(
        net_file="networks/single_intersection.net.xml",
        route_file=f"scenarios/{scenario}.rou.xml",
        use_gui=False,
        num_seconds=3600
    )

    # Load model
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n
    agent = DQNAgent(state_dim, action_dim)

    checkpoint = torch.load(model_path, map_location=agent.device)
    if isinstance(checkpoint, dict):
        if 'q_network' in checkpoint:
            agent.q_network.load_state_dict(checkpoint['q_network'])
        elif 'model_state_dict' in checkpoint:
            agent.q_network.load_state_dict(checkpoint['model_state_dict'])
        else:
            agent.q_network.load_state_dict(checkpoint)
    else:
        agent.q_network.load_state_dict(checkpoint)
    agent.q_network.eval()

    episode_stats = []

    for ep in range(num_episodes):
        state, _ = env.reset()
        done = False
        truncated = False

        total_reward = 0
        queue_history = []
        waiting_time_history = []

        while not done and not truncated:
            action = agent.select_action(state, training=False)
            next_state, reward, done, truncated, info = env.step(action)

            total_reward += reward
            queue_history.append(info['total_queue'])
            waiting_time_history.append(info['total_waiting_time'])
            state = next_state

        episode_stats.append({
            'reward': total_reward,
            'avg_queue': np.mean(queue_history),
            'max_queue': np.max(queue_history),
            'final_throughput': info['throughput'],
            'total_waiting_time': info['total_waiting_time']
        })

        print(f"  Episode {ep+1}/{num_episodes}: "
              f"reward={total_reward:.2f}, "
              f"avg queue={np.mean(queue_history):.2f}, "
              f"max queue={np.max(queue_history):.0f}, "
              f"throughput={info['throughput']}")

    env.close()

    return episode_stats

def compare_methods(model_path: str, scenarios: list, num_episodes: int = 5):
    """Compare RL model and baseline methods"""

    print("="*80)
    print("Start performance comparison: RL Agent vs Fixed-time Traffic Light")
    print("="*80 + "\n")

    results = {}

    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"Scenario: {scenario}")
        print(f"{'='*80}\n")

        results[scenario] = {}

        # Evaluate baseline (fixed 30 seconds)
        print(f"\n--- Baseline method 1: Fixed 30-second traffic light ---")
        baseline_30s = evaluate_baseline(scenario, num_episodes, cycle_time=30)
        results[scenario]['baseline_30s'] = baseline_30s

        # Evaluate baseline (fixed 60 seconds)
        print(f"\n--- Baseline method 2: Fixed 60-second traffic light ---")
        baseline_60s = evaluate_baseline(scenario, num_episodes, cycle_time=60)
        results[scenario]['baseline_60s'] = baseline_60s

        # Evaluate RL model
        print(f"\n--- RLAgent ---")
        rl_stats = evaluate_rl_model(model_path, scenario, num_episodes)
        results[scenario]['rl'] = rl_stats

        # Print comparison summary
        print(f"\n{'='*80}")
        print(f"{scenario} Comparison Summary:")
        print(f"{'='*80}")

        def compute_stats(stats):
            return {
                'reward': np.mean([s['reward'] for s in stats]),
                'avg_queue': np.mean([s['avg_queue'] for s in stats]),
                'max_queue': np.mean([s['max_queue'] for s in stats]),
                'throughput': np.mean([s['final_throughput'] for s in stats])
            }

        baseline_30s_summary = compute_stats(baseline_30s)
        baseline_60s_summary = compute_stats(baseline_60s)
        rl_summary = compute_stats(rl_stats)

        print(f"\nFixed 30-second traffic light:")
        print(f"  Average reward: {baseline_30s_summary['reward']:.2f}")
        print(f"  avg queue: {baseline_30s_summary['avg_queue']:.2f} vehicles")
        print(f"  Average max queue: {baseline_30s_summary['max_queue']:.2f} vehicles")
        print(f"  Average throughput: {baseline_30s_summary['throughput']:.2f} vehicles")

        print(f"\nFixed 60-second traffic light:")
        print(f"  Average reward: {baseline_60s_summary['reward']:.2f}")
        print(f"  avg queue: {baseline_60s_summary['avg_queue']:.2f} vehicles")
        print(f"  Average max queue: {baseline_60s_summary['max_queue']:.2f} vehicles")
        print(f"  Average throughput: {baseline_60s_summary['throughput']:.2f} vehicles")

        print(f"\nRLAgent:")
        print(f"  Average reward: {rl_summary['reward']:.2f}")
        print(f"  avg queue: {rl_summary['avg_queue']:.2f} vehicles")
        print(f"  Average max queue: {rl_summary['max_queue']:.2f} vehicles")
        print(f"  Average throughput: {rl_summary['throughput']:.2f} vehicles")

        # Calculate improvement percentage
        print(f"\nRL improvement over fixed 30 seconds:")
        queue_improve_30 = (baseline_30s_summary['avg_queue'] - rl_summary['avg_queue']) / baseline_30s_summary['avg_queue'] * 100
        throughput_improve_30 = (rl_summary['throughput'] - baseline_30s_summary['throughput']) / baseline_30s_summary['throughput'] * 100
        print(f"  Queue length reduction: {queue_improve_30:+.1f}%")
        print(f"  Throughput improvement: {throughput_improve_30:+.1f}%")

        print(f"\nRL improvement over fixed 60 seconds:")
        queue_improve_60 = (baseline_60s_summary['avg_queue'] - rl_summary['avg_queue']) / baseline_60s_summary['avg_queue'] * 100
        throughput_improve_60 = (rl_summary['throughput'] - baseline_60s_summary['throughput']) / baseline_60s_summary['throughput'] * 100
        print(f"  Queue length reduction: {queue_improve_60:+.1f}%")
        print(f"  Throughput improvement: {throughput_improve_60:+.1f}%")

        results[scenario]['summaries'] = {
            'baseline_30s': baseline_30s_summary,
            'baseline_60s': baseline_60s_summary,
            'rl': rl_summary
        }

    # Generate comparison charts
    generate_comparison_plots(results, model_path)

    return results

def generate_comparison_plots(results, model_path):
    """Generate beautiful comparison charts"""

    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.facecolor'] = 'white'

    scenarios = list(results.keys())
    n_scenarios = len(scenarios)

    # Create comparison chart
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('RL Agent vs Fixed-time Traffic Light - Performance Comparison',
                 fontsize=20, fontweight='bold', y=0.995)

    metrics = [
        ('reward', 'Average reward', 'Reward'),
        ('avg_queue', 'Average queue length', 'Queue Length (vehicles)'),
        ('throughput', 'Average throughput', 'Throughput (vehicles)'),
        ('max_queue', 'Average max queue', 'Max Queue Length (vehicles)')
    ]

    colors = {
        'baseline_30s': '#E74C3C',  # Red - Fixed 30 seconds
        'baseline_60s': '#F39C12',  # Orange - Fixed 60 seconds
        'rl': '#27AE60'             # Green - RL Agent
    }

    for idx, (metric_key, title_cn, ylabel) in enumerate(metrics):
        ax = axes[idx // 2, idx % 2]

        x = np.arange(n_scenarios)
        width = 0.25

        for i, (method, label) in enumerate([
            ('baseline_30s', 'Fixed 30 seconds'),
            ('baseline_60s', 'Fixed 60 seconds'),
            ('rl', 'RLAgent')
        ]):
            values = [results[s]['summaries'][method][metric_key] for s in scenarios]
            offset = (i - 1) * width

            bars = ax.bar(x + offset, values, width,
                         label=label,
                         color=colors[method],
                         alpha=0.85,
                         edgecolor='white',
                         linewidth=2)

            # Add value labels
            for bar, val in zip(bars, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.1f}',
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold')

        ax.set_xlabel('Traffic scenario', fontsize=13, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=13, fontweight='bold')
        ax.set_title(title_cn, fontsize=15, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace('_', '\n') for s in scenarios],
                          fontsize=11, fontweight='bold')
        ax.legend(fontsize=11, loc='best')
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=1)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    output_dir = Path(model_path).parent
    plot_path = output_dir / 'baseline_comparison.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')

    print(f"\n{'='*80}")
    print(f"✓ Comparison chart saved: {plot_path}")
    print(f"{'='*80}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare RL model and fixed-time baseline")
    parser.add_argument(
        "--model-path",
        type=str,
        default="runs/morning_rush_100ep_20251205_025250/final_model.pt",
        help="RL model file path"
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        nargs='+',
        default=["morning_rush", "off_peak"],
        help="List of scenarios to test"
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=5,
        help="Number of episodes to run per method"
    )

    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"Error: Model file not found {args.model_path}")
        sys.exit(1)

    results = compare_methods(
        model_path=args.model_path,
        scenarios=args.scenarios,
        num_episodes=args.episodes
    )
