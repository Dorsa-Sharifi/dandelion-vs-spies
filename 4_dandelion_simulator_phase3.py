import asyncio
import json
import random
import subprocess
import sys
import time
import heapq
import os
import argparse
from statistics import mean

SIMULATOR_PORT = 4999
PACKET_COUNT = 200

class SimulatorProtocol(asyncio.DatagramProtocol):
    def __init__(self, simulator):
        self.simulator = simulator

    def datagram_received(self, data, addr):
        log_entry = json.loads(data.decode())
        self.simulator.process_log(log_entry)

class Simulator:
    def __init__(self, p_value, seed, topology_file='topology.json'):
        self.p_value = p_value
        self.seed = seed
        random.seed(seed)
        
        with open(topology_file, 'r') as f:
            self.topology = json.load(f)
            
        self.nodes = list(self.topology.keys())
        self.num_nodes = len(self.nodes)
        
        num_spies = max(1, int(self.num_nodes * 0.15)) 
        self.spies = set(random.sample(self.nodes, num_spies))
        self.honest_nodes = list(set(self.nodes) - self.spies)
        
        self.processes = []
        self.packet_data = {}
        self.distances = self.calculate_shortest_paths()
        
    def calculate_shortest_paths(self):
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
        state = log.get('state')
        
        if pkt_id not in self.packet_data:
            return
            
        pkt_info = self.packet_data[pkt_id]
        if node not in pkt_info['rx_times']:
            pkt_info['rx_times'][node] = rx_time
            pkt_info['senders'][node] = sender
            pkt_info['states'][node] = state

    async def run(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: SimulatorProtocol(self),
            local_addr=('127.0.0.1', SIMULATOR_PORT)
        )
        
        for node in self.nodes:
            cmd = [sys.executable, 'node.py', node, '--p', str(self.p_value)]
            if node in self.spies:
                cmd.append('--spy')
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.processes.append(p)
            
        await asyncio.sleep(2) 
        
        for i in range(PACKET_COUNT):
            pkt_id = f"pkt_{i:03d}"
            true_source = random.choice(self.honest_nodes)
            start_time = time.time()
            
            self.packet_data[pkt_id] = {
                'true_source': true_source,
                'start_time': start_time,
                'rx_times': {true_source: start_time}, 
                'senders': {true_source: None},
                'states': {true_source: 'Stem'}
            }
            
            source_info = self.topology[true_source]
            payload = json.dumps({'packet_id': pkt_id, 'state': 'Stem'}).encode()
            self.transport.sendto(payload, (source_info['ip'], source_info['port']))
            
            await asyncio.sleep(random.uniform(0.05, 0.2)) 
            
        await asyncio.sleep(5) 
        self.evaluate_results()
        self.cleanup()

    def evaluate_results(self):
        baseline_correct = 0
        proposed_correct = 0
        t80_times = []
        target_80_percent = int(self.num_nodes * 0.8)
        
        for pkt_id, data in self.packet_data.items():
            true_source = data['true_source']
            spy_logs = {node: time for node, time in data['rx_times'].items() if node in self.spies}
            
            if not spy_logs:
                continue
                
            first_spy = min(spy_logs, key=spy_logs.get)
            baseline_guess = data['senders'][first_spy]
            if baseline_guess == true_source:
                baseline_correct += 1
                
            if len(spy_logs) < 2:
                proposed_guess = baseline_guess 
            else:
                best_guess = None
                min_error = float('inf')
                spy_list = list(spy_logs.keys())
                for candidate in self.honest_nodes:
                    error = 0
                    for i in range(len(spy_list)):
                        for j in range(i + 1, len(spy_list)):
                            s1, s2 = spy_list[i], spy_list[j]
                            obs_diff = spy_logs[s1] - spy_logs[s2]
                            exp_diff = self.distances[candidate][s1] - self.distances[candidate][s2]
                            error += abs(obs_diff - exp_diff)
                    if error < min_error:
                        min_error = error
                        best_guess = candidate
                proposed_guess = best_guess

            if proposed_guess == true_source:
                proposed_correct += 1
            
            rx_times = sorted(data['rx_times'].values())
            if len(rx_times) >= target_80_percent:
                t80_times.append(rx_times[target_80_percent - 1] - data['start_time'])

        base_acc = baseline_correct / PACKET_COUNT
        prop_acc = proposed_correct / PACKET_COUNT
        num_spies = len(self.spies)
        
        avg_t80 = mean(t80_times) if t80_times else float('inf')
        
        # Save to logs folder
        os.makedirs('logs', exist_ok=True)
        log_filename = os.path.join('logs', f'phase3/diffusion_logs_p{self.p_value}_seed{self.seed}.json')
        
        # Create a summary payload
        summary = {
            'config': {'p_value': self.p_value, 'seed': self.seed, 'num_spies': num_spies},
            'results': {
                'baseline_accuracy': base_acc,
                'proposed_accuracy': prop_acc,
                'avg_t80': avg_t80
            },
            'packet_data': self.packet_data
        }
        
        with open(log_filename, 'w') as f:
            json.dump(summary, f, indent=4)
            
        print(f"Run [p={self.p_value}, seed={self.seed}] completed. Acc: {prop_acc*100:.1f}%, T80: {avg_t80:.3f}s. Saved to {log_filename}")

    def cleanup(self):
        for p in self.processes:
            p.terminate()
        self.transport.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--p", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    
    asyncio.run(Simulator(args.p, args.seed).run())