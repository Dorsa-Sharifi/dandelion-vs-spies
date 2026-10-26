import json
import os
import numpy as np
import matplotlib.pyplot as plt

def load_data(filename='logs/attack_diffusion_logs.json'):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {filename}.")
        return None

def load_summary(filename='logs/attack_summary.json'):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {filename}. Run 2_attack_simulator.py first.")
        return None

def plot_t80_distribution(packet_data):
    """Calculates and plots the mean, median, and standard deviation of T_80%."""
    t80_times = []
    
    first_packet = next(iter(packet_data.values()))
    total_nodes = len(first_packet['rx_times']) # Assumes 100% coverage eventually
    target_80_percent = int(total_nodes * 0.8)

    for pkt_id, data in packet_data.items():
        start_time = data['start_time']
        rx_times = sorted(data['rx_times'].values())
        
        if len(rx_times) >= target_80_percent:
            t80 = rx_times[target_80_percent - 1] - start_time
            t80_times.append(t80)

    if not t80_times:
        print("Not enough data to calculate T_80%.")
        return

    # Calculate statistics
    mean_t80 = np.mean(t80_times)
    median_t80 = np.median(t80_times)
    std_t80 = np.std(t80_times)

    print(f"--- T_80% Statistics ---")
    print(f"Mean:   {mean_t80:.4f} s")
    print(f"Median: {median_t80:.4f} s")
    print(f"StDev:  {std_t80:.4f} s")

    # Plot Histogram
    plt.figure(figsize=(10, 6))
    plt.hist(t80_times, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
    
    # Add statistical lines
    plt.axvline(mean_t80, color='red', linestyle='dashed', linewidth=2, label=f'Mean: {mean_t80:.2f}s')
    plt.axvline(median_t80, color='green', linestyle='dashed', linewidth=2, label=f'Median: {median_t80:.2f}s')
    
    # Highlight standard deviation area
    plt.axvspan(mean_t80 - std_t80, mean_t80 + std_t80, color='yellow', alpha=0.2, label=f'StDev: ±{std_t80:.2f}s')

    plt.title('Distribution of Network Coverage Time ($T_{80\%}$)')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Number of Packets')
    plt.legend()
    plt.grid(axis='y', alpha=0.75)
    
    # Save into the figures folder
    plt.savefig('figures/t80_distribution.png', dpi=300)
    print("Saved 'figures/t80_distribution.png'")
    plt.show()

def plot_attack_comparison():
    """Plots a comparison of the Baseline vs Proposed attack metrics using REAL data."""
    summary = load_summary()
    if not summary:
        return

    labels = ['Baseline (First Spy)', 'Proposed (Triangulation)']
    
    accuracy = [acc * 100 for acc in summary['accuracy']]
    score_adv = summary['score_adv']
    score_honest = summary['score_honest']

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    
    rects1 = ax.bar(x - width, accuracy, width, label='Accuracy (%)', color='cornflowerblue')
    rects2 = ax.bar(x, [s * 100 for s in score_adv], width, label='Attacker Score (Scaled x100)', color='salmon')
    rects3 = ax.bar(x + width, [s * 100 for s in score_honest], width, label='Honest Score (Scaled x100)', color='lightgreen')

    ax.set_ylabel('Scores & Percentages')
    ax.set_title('Attack Algorithm Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    def autolabel(rects, is_percent=False):
        for rect in rects:
            height = rect.get_height()
            label = f'{height:.1f}%' if is_percent else f'{height/100:.4f}'
            ax.annotate(label,
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1, is_percent=True)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    os.makedirs('figures', exist_ok=True)
    plt.savefig('figures/attack_comparison.png', dpi=300)
    print("Saved 'figures/attack_comparison.png'")
    plt.show()

if __name__ == '__main__':
    os.makedirs('figures', exist_ok=True)
    
    data = load_data()
    if data:
        plot_t80_distribution(data)
        plot_attack_comparison()