import asyncio
import json
import random
import subprocess
import sys
import time
from statistics import mean, median, stdev

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
        
        # Max 30% spies
        num_spies = int(self.num_nodes * 0.3)
        self.spies = set(random.sample(self.nodes, num_spies))
        self.honest_nodes = list(set(self.nodes) - self.spies)
        
        print(f"Total Nodes: {self.num_nodes}")
        print(f"Spies ({len(self.spies)}): {self.spies}")
        
        self.processes = []
        self.packet_data = {} # Stores truth and logs for each packet
        
    def process_log(self, log):
        """Processes incoming timestamp logs from nodes."""
        pkt_id = log['packet_id']
        node = log['node']
        rx_time = log['time']
        sender = log.get('sender')
        
        if pkt_id not in self.packet_data:
            return
            
        pkt_info = self.packet_data[pkt_id]
        
        # Record receiving time for T_80% calculation
        if node not in pkt_info['rx_times']:
            pkt_info['rx_times'][node] = rx_time
            
        # Record First Spy Observer
        if node in self.spies:
            if pkt_info['first_spy'] is None or rx_time < pkt_info['first_spy']['time']:
                pkt_info['first_spy'] = {
                    'spy_node': node,
                    'guessed_source': sender,
                    'time': rx_time
                }

    async def run(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: SimulatorProtocol(self),
            local_addr=('127.0.0.1', SIMULATOR_PORT)
        )
        
        # 1. Launch Node Processes
        print("Starting node processes...")
        for node in self.nodes:
            cmd = [sys.executable, 'node.py', node]
            if node in self.spies:
                cmd.append('--spy')
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.processes.append(p)
            
        await asyncio.sleep(2) # Wait for nodes to bind their ports
        
        # 2. Inject 200 Packets
        print(f"Injecting {PACKET_COUNT} packets...")
        for i in range(PACKET_COUNT):
            pkt_id = f"pkt_{i:03d}"
            true_source = random.choice(self.honest_nodes)
            start_time = time.time()
            
            self.packet_data[pkt_id] = {
                'true_source': true_source,
                'start_time': start_time,
                'rx_times': {true_source: start_time}, # Source gets it at t=0
                'first_spy': None
            }
            
            # Send initial packet to the chosen source
            source_info = self.topology[true_source]
            payload = json.dumps({'packet_id': pkt_id, 'state': 'Stem'}).encode()
            self.transport.sendto(payload, (source_info['ip'], source_info['port']))
            
            await asyncio.sleep(random.uniform(0.05, 0.2)) # Random interval between packets
            
        print("Waiting for packets to propagate...")
        await asyncio.sleep(5) 
        
        self.evaluate_results()
        self.cleanup()

    def evaluate_results(self):
        print("\n--- Simulation Results ---")
        correct_guesses = 0
        t80_times = []
        target_80_percent = int(self.num_nodes * 0.8)
        
        for pkt_id, data in self.packet_data.items():
            # 1. Attacker Accuracy (First Spy Observer)
            true_source = data['true_source']
            if data['first_spy']:
                guessed_source = data['first_spy']['guessed_source']
                if guessed_source == true_source:
                    correct_guesses += 1
            
            # 2. T_80% Calculation
            rx_times = sorted(data['rx_times'].values())
            if len(rx_times) >= target_80_percent:
                t80 = rx_times[target_80_percent - 1] - data['start_time']
                t80_times.append(t80)

        # Calculations
        accuracy = correct_guesses / PACKET_COUNT
        score_adv = accuracy / len(self.spies) if len(self.spies) > 0 else 0
        
        avg_t80 = mean(t80_times) if t80_times else float('inf')
        score_honest = (1 / avg_t80) * (1 - accuracy) if avg_t80 > 0 else 0
        
        print(f"Attacker Accuracy: {accuracy * 100:.1f}%")
        print(f"Average T_80%: {avg_t80:.4f} seconds")
        print(f"Score_adv: {score_adv:.4f}")
        print(f"Score_honest: {score_honest:.4f}")

        with open('logs/base_diffusion_logs.json', 'w') as f:
            json.dump(self.packet_data, f, indent=4)
        print("\nAll packet propagation logs saved to 'diffusion_logs.json'")
        
    def cleanup(self):
        print("\nShutting down nodes...")
        for p in self.processes:
            p.terminate()
        self.transport.close()

if __name__ == '__main__':
    asyncio.run(Simulator().run())