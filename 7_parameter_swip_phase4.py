import subprocess
import sys
import os

def run_parameter_sweep():
    # As requested: p = 0.9, p = 0.5, p = 0.1
    p_values = [0.9, 0.5, 0.1]
    # As requested: Run at least 5 times with different random seeds
    seeds = [42, 101, 202, 303, 404]
    
    print("Starting Parameter Sweep for Dandelion Protocol...")
    
    for p in p_values:
        print(f"\n================ Evaluating p = {p} ================")
        for seed in seeds:
            print(f"--> Running simulation with seed = {seed}...")
            
            # Execute simulator.py with arguments
            cmd = [sys.executable, '6_dandeliion_aware_attack_simulator_phase4.py', '--p', str(p), '--seed', str(seed)]
            
            # Block until process finishes so ports don't conflict
            subprocess.run(cmd)

    print("\nAll experiments finished successfully! Check the 'logs' folder.")

if __name__ == '__main__':
    # Ensure logs folder exists before starting
    os.makedirs('logs', exist_ok=True)
    run_parameter_sweep()