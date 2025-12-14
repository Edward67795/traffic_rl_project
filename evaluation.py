"""
Improved Model Evaluation Script
Collect complete episode statistics and generate beautiful visualization charts
"""
import os
import sys
import torch
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Add src directory to path
sys.path.append(str(Path(__file__).parent / 'src'))

from environment import SumoTrafficEnv
from agent import DQNAgent

def evaluate_model(
    model_path: str,
    scenarios: list = ["morning_rush", "off_peak"],
    num_episodes: int = 5
):
    """
    Evaluate model performance across different scenarios, collect complete statistics

    Args:
        model_path: Model file path
        scenarios: List of scenarios to test
        num_episodes: Number of to run per scenario
    """
    print(f"Load model: {model_path}")
    print(f"Test scenarios: {scenarios}")
    print(f"Run per scenario {num_episodes}\n")

    results = {}

    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Test scenarios: {scenario}")
        print(f"{'='*60}\n")

        # Create environment (without GUI)
        env = SumoTrafficEnv(
            net_file="networks/single_intersection.net.xml",
            route_file=f"scenarios/{scenario}.rou.xml",
            use_gui=False,
            num_seconds=3600
        )

        state_dim = env.observation_space.shape[0]
        action_dim = env.action_space.n
        agent = DQNAgent(state_dim, action_dim)

        # Load model
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

        # Record complete statistics for each episode
        episode_stats = []

        # Run multiple episodes
        for ep in range(num_episodes):
            state, _ = env.reset()
            done = False
            truncated = False

            # Statistics within single episode
            total_reward = 0
            queue_history = []
            waiting_time_history = []

            step_count = 0
            while not done and not truncated:
                action = agent.select_action(state, training=False)
                next_state, reward, done, truncated, info = env.step(action)

                total_reward += reward
                queue_history.append(info['total_queue'])
                waiting_time_history.append(info['total_waiting_time'])
                state = next_state
                step_count += 1

            # Compute episode-level statistics
            episode_stats.append({
                'reward': total_reward,
                'avg_queue': np.mean(queue_history),
                'max_queue': np.max(queue_history),
                'final_throughput': info['throughput'],
                'total_waiting_time': info['total_waiting_time'],
                'steps': step_count
            })

            print(f"  Episode {ep+1}/{num_episodes}: "
                  f"reward={total_reward:.2f}, "
                  f"avg queue={np.mean(queue_history):.2f}, "
                  f"max queue={np.max(queue_history):.0f}, "
                  f"throughput={info['throughput']}")

        env.close()

        # Aggregate statistics across all episodes
        rewards = [ep['reward'] for ep in episode_stats]
        avg_queues = [ep['avg_queue'] for ep in episode_stats]
        max_queues = [ep['max_queue'] for ep in episode_stats]
        throughputs = [ep['final_throughput'] for ep in episode_stats]
        waiting_times = [ep['total_waiting_time'] for ep in episode_stats]

        results[scenario] = {
            'episode_stats': episode_stats,
            'rewards': rewards,
            'avg_queues': avg_queues,
            'max_queues': max_queues,
            'throughputs': throughputs,
            'waiting_times': waiting_times,
            'summary': {
                'mean_reward': np.mean(rewards),
                'std_reward': np.std(rewards),
                'mean_avg_queue': np.mean(avg_queues),
                'std_avg_queue': np.std(avg_queues),
                'mean_max_queue': np.mean(max_queues),
                'mean_throughput': np.mean(throughputs),
                'std_throughput': np.std(throughputs),
                'mean_waiting_time': np.mean(waiting_times)
            }
        }

        summary = results[scenario]['summary']
        print(f"\n{scenario} Scenario summary:")
        print(f"  Average reward: {summary['mean_reward']:.2f} ± {summary['std_reward']:.2f}")
        print(f"  Average queue length: {summary['mean_avg_queue']:.2f} ± {summary['std_avg_queue']:.2f} vehicles")
        print(f"  Average max queue: {summary['mean_max_queue']:.2f} vehicles")
        print(f"  Average throughput: {summary['mean_throughput']:.2f} ± {summary['std_throughput']:.2f} vehicles")
        print(f"  Average waiting time: {summary['mean_waiting_time']:.0f} seconds")

    # Generate beautiful comparison charts
    print(f"\n{'='*60}")
    print("Generate comparison charts...")
    print(f"{'='*60}\n")

    generate_beautiful_plots(results, model_path)

    return results

def generate_beautiful_plots(results, model_path):
    """Generate beautiful comparison charts"""
    scenarios = list(results.keys())

    # Set global style
    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = '#f8f9fa'

    # Define beautiful color scheme
    colors = {
        'morning_rush': '#FF6B6B',  # Coral red - represents busy
        'off_peak': '#4ECDC4',      # Cyan - represents calm
    }

    fig1, axes1 = plt.subplots(2, 2, figsize=(16, 12))
    fig1.suptitle('Model Performance Comparison - Different Traffic Scenarios',
                  fontsize=20, fontweight='bold', y=0.995)

    metrics = [
        ('mean_reward', 'std_reward', 'Average reward', 'Reward', True),
        ('mean_avg_queue', 'std_avg_queue', 'Average queue length', 'Queue Length (vehicles)', False),
        ('mean_throughput', 'std_throughput', 'Average throughput', 'Throughput (vehicles)', False),
        ('mean_waiting_time', None, 'Average waiting time', 'Waiting Time (seconds)', False)
    ]

    for idx, (mean_key, std_key, title_cn, ylabel, show_std) in enumerate(metrics):
        ax = axes1[idx // 2, idx % 2]

        x = np.arange(len(scenarios))
        width = 0.6

        means = [results[s]['summary'][mean_key] for s in scenarios]

        if show_std and std_key:
            stds = [results[s]['summary'][std_key] for s in scenarios]
        else:
            stds = [0] * len(scenarios)

        bars = ax.bar(x, means, width,
                     color=[colors.get(s, '#95A5A6') for s in scenarios],
                     alpha=0.85, edgecolor='white', linewidth=2)

        if show_std and any(s > 0 for s in stds):
            ax.errorbar(x, means, yerr=stds, fmt='none',
                       ecolor='#2C3E50', capsize=8, capthick=2, alpha=0.7)

        ax.set_xlabel('Traffic Scenario', fontsize=13, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=13, fontweight='bold')
        ax.set_title(title_cn, fontsize=15, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace('_', '\n') for s in scenarios],
                          fontsize=11, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=1)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Add value labels on bars
        for i, (bar, mean, std) in enumerate(zip(bars, means, stds)):
            height = bar.get_height()
            if show_std and std > 0:
                label_text = f'{mean:.1f}\n±{std:.1f}'
            else:
                label_text = f'{mean:.1f}'

            ax.text(bar.get_x() + bar.get_width()/2., height,
                   label_text,
                   ha='center', va='bottom', fontsize=11,
                   fontweight='bold', color='#2C3E50')

    plt.tight_layout()
    output_dir = Path(model_path).parent
    plot_path1 = output_dir / 'evaluation_comparison_v2.png'
    plt.savefig(plot_path1, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Key metrics comparison chart saved: {plot_path1}")

    # ========== Episode performance trend ==========
    fig2, axes2 = plt.subplots(2, 2, figsize=(16, 12))
    fig2.suptitle('Episode Performance',
                  fontsize=20, fontweight='bold', y=0.995)

    metric_configs = [
        ('rewards', 'reward', 'Reward', 'o-'),
        ('avg_queues', 'Average queue length', 'Queue Length (vehicles)', 's-'),
        ('throughputs', 'throughput', 'Throughput (vehicles)', '^-'),
        ('max_queues', 'Maximum queue length', 'Max Queue Length (vehicles)', 'D-')
    ]

    for idx, (key, title_cn, ylabel, marker_style) in enumerate(metric_configs):
        ax = axes2[idx // 2, idx % 2]

        for scenario in scenarios:
            values = results[scenario][key]
            episodes = range(1, len(values) + 1)

            ax.plot(episodes, values,
                   marker_style,
                   linewidth=2.5, markersize=9,
                   label=scenario.replace('_', ' ').title(),
                   color=colors.get(scenario, '#95A5A6'),
                   alpha=0.85)

        ax.set_xlabel('Episode', fontsize=13, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=13, fontweight='bold')
        ax.set_title(title_cn, fontsize=15, fontweight='bold', pad=15)
        ax.legend(fontsize=11, loc='best', framealpha=0.9)
        ax.grid(alpha=0.3, linestyle='--', linewidth=1)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plot_path2 = output_dir / 'evaluation_episodes_v2.png'
    plt.savefig(plot_path2, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Episode performance trend chart saved: {plot_path2}")

    print(f"\n{'='*60}")
    print(f"All charts generated！")
    print(f"Saved location: {output_dir}")
    print(f"{'='*60}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate trained model (improved version)")
    parser.add_argument(
        "--model-path",
        type=str,
        default="runs/morning_rush_100ep_20251205_025250/final_model.pt",
        help="Model file path"
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
        help="Number of to run per scenario"
    )

    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"Error: Model file not found {args.model_path}")
        sys.exit(1)

    results = evaluate_model(
        model_path=args.model_path,
        scenarios=args.scenarios,
        num_episodes=args.episodes
    )
