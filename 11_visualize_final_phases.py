import os
import json
import glob
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

def load_sweep_data():
    """Reads all JSON logs from the parameter sweep and groups them by p_value."""
    p_values = [0.9, 0.5, 0.1]
    raw_data = defaultdict(lambda: {'base': [], 'prop': [], 'p4': [], 't80': []})

    for p in p_values:
        # Scan phase4 logs
        files = glob.glob(f'logs/phase4/diffusion_logs_p{p}_seed*.json')
        if not files:
            print(f"Warning: No log files found for p={p} in logs/phase4/.")
            continue
            
        for filepath in files:
            with open(filepath, 'r') as f:
                data = json.load(f)
                res = data['results']
                raw_data[p]['base'].append(res['baseline_accuracy'])
                raw_data[p]['prop'].append(res['proposed_accuracy'])
                raw_data[p]['p4'].append(res.get('phase4_accuracy', 0)) 
                raw_data[p]['t80'].append(res['avg_t80'])
                
    averaged_data = {}
    
    print("\n=== T_80% Statistical Analysis for Dandelion (Phase 4) ===")
    for p in p_values:
        if raw_data[p]['base']:
            # Calculate metrics
            t80_list = raw_data[p]['t80']
            mean_t80 = np.mean(t80_list)
            median_t80 = np.median(t80_list)
            std_t80 = np.std(t80_list)
            
            print(f"p = {p}:")
            print(f"  Mean:   {mean_t80:.3f} s")
            print(f"  Median: {median_t80:.3f} s")
            print(f"  StDev:  {std_t80:.3f} s\n")
            
            averaged_data[p] = {
                'base': np.mean(raw_data[p]['base']) * 100,
                'prop': np.mean(raw_data[p]['prop']) * 100,
                'p4': np.mean(raw_data[p]['p4']) * 100,
                't80': mean_t80
            }
    return averaged_data, p_values


def plot_accuracy_comparison(data, p_values):
    """Generates a grouped bar chart for attack accuracies across different p values."""
    if not data:
        return

    labels = [f'p = {p}' for p in p_values]
    base_acc = [data[p]['base'] for p in p_values]
    prop_acc = [data[p]['prop'] for p in p_values]
    p4_acc = [data[p]['p4'] for p in p_values]

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    
    rects1 = ax.bar(x - width, base_acc, width, label='Baseline (First Spy)', color='lightgray')
    rects2 = ax.bar(x, prop_acc, width, label='Phase 2 (Triangulation)', color='salmon')
    rects3 = ax.bar(x + width, p4_acc, width, label='Phase 4 (Dandelion-Aware)', color='cornflowerblue')

    ax.set_ylabel('Accuracy (%)')
    ax.set_title('Attacker Accuracy vs. Dandelion Parameter (p)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    # Label bars with exact values
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    os.makedirs('figures', exist_ok=True)
    plt.savefig('figures/p_sweep_accuracy.png', dpi=300)
    print("Saved 'figures/p_sweep_accuracy.png'")
    plt.show()

def plot_t80_comparison(data, p_values):
    """Generates a bar chart showing how T_80% changes with p."""
    if not data:
        return

    labels = [f'p = {p}' for p in p_values]
    t80_times = [data[p]['t80'] for p in p_values]

    fig, ax = plt.subplots(figsize=(8, 5))
    
    bars = ax.bar(labels, t80_times, color='mediumseagreen', width=0.5)

    ax.set_ylabel('Time (seconds)')
    ax.set_title('Network Coverage Time ($T_{80\%}$) vs. Dandelion Parameter (p)')
    ax.set_ylim(0, max(t80_times) * 1.2) # Add some headroom

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.3f} s',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom')

    fig.tight_layout()
    plt.savefig('figures/p_sweep_t80.png', dpi=300)
    print("Saved 'figures/p_sweep_t80.png'")
    plt.show()

if __name__ == '__main__':
    data, p_values = load_sweep_data()
    if data:
        print("Data loaded successfully. Generating plots...")
        plot_accuracy_comparison(data, p_values)
        plot_t80_comparison(data, p_values)