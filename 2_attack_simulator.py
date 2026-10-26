import asyncio
import json
import random
import subprocess
import sys
import time
import heapq
import os
from statistics import mean

SIMULATOR_PORT = 4999
PACKET_COUNT = 200
RANDOM_SEED = 42

class SimulatorProtocol(asyncio.DatagramProtocol):
    def __init__(self, simulator):
        self.simulator = simulator

    def datagram_received(self, data, addr):
        log_entry = json.loads(data.decode())
        self.simulator.process_log(log_entry)

class Simulator:
    def __init__(self, topology_file='topology.json'):
        random.seed(RANDOM_SEED)
        
        with open(topology_file, 'r') as f:
            self.topology = json.load(f)
            
        self.nodes = list(self.topology.keys())
        self.num_nodes = len(self.nodes)
        
        # The attacker can use up to 30%. To maximize Score_adv, we use exactly 15% here as a balanced optimization.
        num_spies = max(1, int(self.num_nodes * 0.15)) 
        self.spies = set(random.sample(self.nodes, num_spies))
        self.honest_nodes = list(set(self.nodes) - self.spies)
        
        print(f"Total Nodes: {self.num_nodes}")
        print(f"Spies ({len(self.spies)}): {self.spies}")
        
        self.processes = []
        self.packet_data = {}
        
        # Calculate all-pairs shortest paths for the Proposed Attack
        self.distances = self.calculate_shortest_paths()
        
    def calculate_shortest_paths(self):
        """Uses Dijkstra to find the base delay (in seconds) between all node pairs."""
        distances = {n: {m: float('inf') for m in self.nodes} for n in self.nodes}
        for start_node in self.nodes:
            distances[start_node][start_node] = 0
            pq = [(0, start_node)]
            while pq:
                curr_dist, u = heapq.heappop(pq)
                if curr_dist > distances[start_node][u]:
                    continue
                for v, link_info in self.topology[u]['neighbors'].items():
                    weight = link_info['base_delay_ms'] / 1000.0
                    if curr_dist + weight < distances[start_node][v]:
                        distances[start_node][v] = curr_dist + weight
                        heapq.heappush(pq, (distances[start_node][v], v))
        return distances

    def process_log(self, log):
        pkt_id = log['packet_id']
        node = log['node']
        rx_time = log['time']
        sender = log.get('sender')
        
        if pkt_id not in self.packet_data:
            return
            
        pkt_info = self.packet_data[pkt_id]
        
        if node not in pkt_info['rx_times']:
            pkt_info['rx_times'][node] = rx_time
            # Keep track of who sent it for the baseline attack
            pkt_info['senders'][node] = sender

    async def run(self):
        loop = asyncio.get_running_loop()
        
        # 1. Create UDP endpoint (This sets up self.transport)
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: SimulatorProtocol(self),
            local_addr=('127.0.0.1', SIMULATOR_PORT)
        )
        
        # 2. Launch node processes
        print("Starting node processes...")
        for node in self.nodes:
            cmd = [sys.executable, 'node.py', node]
            if node in self.spies:
                cmd.append('--spy')
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.processes.append(p)
            
        await asyncio.sleep(2) 
        
        # 3. Inject packets
        print(f"Injecting {PACKET_COUNT} packets...")
        for i in range(PACKET_COUNT):
            pkt_id = f"pkt_{i:03d}"
            true_source = random.choice(self.honest_nodes)
            start_time = time.time()
            
            self.packet_data[pkt_id] = {
                'true_source': true_source,
                'start_time': start_time,
                'rx_times': {true_source: start_time}, 
                'senders': {true_source: None}
            }
            
            source_info = self.topology[true_source]
            
            payload = json.dumps({'packet_id': pkt_id, 'state': 'Fluff'}).encode()
            self.transport.sendto(payload, (source_info['ip'], source_info['port']))
            
            await asyncio.sleep(random.uniform(0.05, 0.2)) 
            
        print("Waiting for packets to propagate...")
        await asyncio.sleep(5) 
        
        self.evaluate_results()
        self.cleanup()

    def evaluate_results(self):
        print("\n--- Simulation Results ---")
        baseline_correct = 0
        proposed_correct = 0
        t80_times = []
        target_80_percent = int(self.num_nodes * 0.8)
        
        for pkt_id, data in self.packet_data.items():
            true_source = data['true_source']
            
            # Filter logs to only see what the spies observed
            spy_logs = {node: time for node, time in data['rx_times'].items() if node in self.spies}
            
            if not spy_logs:
                continue
                
            # 1. Baseline Attack (First Spy Observer)
            first_spy = min(spy_logs, key=spy_logs.get)
            baseline_guess = data['senders'][first_spy]
            if baseline_guess == true_source:
                baseline_correct += 1
                
            # 2. Proposed Attack (Time-Difference Triangulation)
            if len(spy_logs) < 2:
                # Fallback if only 1 spy saw it
                proposed_guess = baseline_guess 
            else:
                best_guess = None
                min_error = float('inf')
                spy_list = list(spy_logs.keys())
                
                # Check every honest node to see which fits the time delays best
                for candidate in self.honest_nodes:
                    error = 0
                    for i in range(len(spy_list)):
                        for j in range(i + 1, len(spy_list)):
                            s1, s2 = spy_list[i], spy_list[j]
                            
                            obs_diff = spy_logs[s1] - spy_logs[s2]
                            exp_diff = self.distances[candidate][s1] - self.distances[candidate][s2]
                            
                            # Add the absolute variance
                            error += abs(obs_diff - exp_diff)
                            
                    if error < min_error:
                        min_error = error
                        best_guess = candidate
                proposed_guess = best_guess

            if proposed_guess == true_source:
                proposed_correct += 1
            
            # T_80% Calculation
            rx_times = sorted(data['rx_times'].values())
            if len(rx_times) >= target_80_percent:
                t80_times.append(rx_times[target_80_percent - 1] - data['start_time'])

        # Calculate final metrics
        base_acc = baseline_correct / PACKET_COUNT
        prop_acc = proposed_correct / PACKET_COUNT
        
        num_spies = len(self.spies)
        base_score_adv = base_acc / num_spies if num_spies > 0 else 0
        prop_score_adv = prop_acc / num_spies if num_spies > 0 else 0
        
        avg_t80 = mean(t80_times) if t80_times else float('inf')
        
        # Calculate honest scores against both attacks
        base_score_honest = (1 / avg_t80) * (1 - base_acc) if avg_t80 > 0 else 0
        prop_score_honest = (1 / avg_t80) * (1 - prop_acc) if avg_t80 > 0 else 0
        
        print("\n=== Baseline (First Spy) ===")
        print(f"Accuracy: {base_acc * 100:.1f}%")
        print(f"Score_adv: {base_score_adv:.4f}")
        print(f"Score_honest: {base_score_honest:.4f}")
        
        print("\n=== Proposed (Triangulation) ===")
        print(f"Accuracy: {prop_acc * 100:.1f}%")
        print(f"Score_adv: {prop_score_adv:.4f}")
        print(f"Score_honest: {prop_score_honest:.4f}")
        
        print(f"\nAverage T_80%: {avg_t80:.4f} seconds")

        os.makedirs('logs', exist_ok=True)
        
        summary = {
            'accuracy': [base_acc, prop_acc],
            'score_adv': [base_score_adv, prop_score_adv],
            'score_honest': [base_score_honest, prop_score_honest]
        }
        with open('logs/attack_summary.json', 'w') as f:
            json.dump(summary, f, indent=4)

        with open('logs/attack_diffusion_logs.json', 'w') as f:
            json.dump(self.packet_data, f, indent=4)
        
    def cleanup(self):
        print("\nShutting down nodes...")
        for p in self.processes:
            p.terminate()
        self.transport.close()

if __name__ == '__main__':
    asyncio.run(Simulator().run())