import asyncio
import json
import argparse
import time
import random
import os

class NodeProtocol(asyncio.DatagramProtocol):
    def __init__(self, node):
        self.node = node

    def connection_made(self, transport):
        self.node.transport = transport

    def datagram_received(self, data, addr):
        message = json.loads(data.decode())
        asyncio.create_task(self.node.handle_message(message, addr))

class Node:
    def __init__(self, node_id, is_spy=False, p_value=0.0, topology_file='topology.json'):
        self.node_id = node_id
        self.is_spy = is_spy  
        self.p_value = p_value 
        self.seen_set = set()
        self.transport = None
        
        with open(topology_file, 'r') as f:
            topology = json.load(f)
            
        if node_id not in topology:
            raise ValueError(f"Node {node_id} not found in topology.")
            
        my_info = topology[node_id]
        self.ip = my_info['ip']
        self.port = my_info['port']
        
        self.peer_list = {}
        for peer_id, link_data in my_info['neighbors'].items():
            peer_info = topology[peer_id]
            self.peer_list[peer_id] = {
                'ip': peer_info['ip'],
                'port': peer_info['port'],
                'base_delay_ms': link_data['base_delay_ms'],
                'last_seen': None
            }

    def get_peer_by_addr(self, addr):
        for peer_id, info in self.peer_list.items():
            if (info['ip'], info['port']) == addr:
                return peer_id
        return None

    def log_to_simulator(self, packet_id, sender_id, state):
        log_msg = {
            'node': self.node_id,
            'packet_id': packet_id,
            'time': time.time(),
            'sender': sender_id,
            'state': state
        }
        self.transport.sendto(json.dumps(log_msg).encode(), ('127.0.0.1', 4999))

    async def handle_message(self, message, addr):
        packet_id = message.get('packet_id')
        state = message.get('state') 
        
        sender_id = self.get_peer_by_addr(addr)
        
        if sender_id:
            self.peer_list[sender_id]['last_seen'] = time.time()
            
        # --- Deduplication and Loop Resolution ---
        if packet_id in self.seen_set:
            if state == 'Stem':
                message['state'] = 'Fluff'
                await self.broadcast_to_neighbors(message, exclude_peer=sender_id)
            return 
            
        self.seen_set.add(packet_id)
        self.log_to_simulator(packet_id, sender_id, state)
        
        # --- ROUTING LOGIC ---
        if sender_id is None:
            if state == 'Fluff':
                await self.broadcast_to_neighbors(message)
            else:
                candidates = list(self.peer_list.keys())
                if candidates:
                    chosen = random.choice(candidates)
                    await self.send_packet(chosen, message)
                else:
                    message['state'] = 'Fluff'
                    await self.broadcast_to_neighbors(message)
        else:
            # Relay node behavior
            if state == 'Stem':
                if random.random() < self.p_value:
                    candidates = [peer for peer in self.peer_list if peer != sender_id]
                    if candidates:
                        chosen = random.choice(candidates)
                        await self.send_packet(chosen, message)
                    else:
                        message['state'] = 'Fluff'
                        await self.broadcast_to_neighbors(message, exclude_peer=sender_id)
                else:
                    message['state'] = 'Fluff'
                    await self.broadcast_to_neighbors(message, exclude_peer=sender_id)
            else:
                await self.broadcast_to_neighbors(message, exclude_peer=sender_id)

    async def send_packet(self, target_peer_id, message):
        peer_info = self.peer_list[target_peer_id]
        base_delay = peer_info['base_delay_ms']
        
        jitter = random.uniform(-0.2 * base_delay, 0.2 * base_delay)
        
        # --- PHASE 5: Spy Intentional Delay Limitation ---
        intentional_delay = 0
        if self.is_spy:
            # Maximum allowed intentional delay is strictly equal to the base delay of this specific link
            intentional_delay = random.uniform(0, base_delay)
            
        total_delay_ms = base_delay + jitter + intentional_delay
        
        await asyncio.sleep(total_delay_ms / 1000.0) 
        
        payload = json.dumps(message).encode()
        self.transport.sendto(payload, (peer_info['ip'], peer_info['port']))

    async def broadcast_to_neighbors(self, message, exclude_peer=None):
        tasks = []
        for peer_id in self.peer_list:
            if peer_id != exclude_peer:
                tasks.append(asyncio.create_task(self.send_packet(peer_id, message)))
        if tasks:
            await asyncio.gather(*tasks)

    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: NodeProtocol(self),
            local_addr=(self.ip, self.port)
        )
        try:
            while True:
                await asyncio.sleep(3600) 
        finally:
            self.transport.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("node_id", type=str)
    parser.add_argument("--spy", action="store_true")
    parser.add_argument("--p", type=float, default=0.0)
    args = parser.parse_args()
    
    node = Node(args.node_id, is_spy=args.spy, p_value=args.p)
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        pass