import random
import math
import json

# --- Configuration ---
GRID_SIZE = 1000
MIN_NODES, MAX_NODES = 20, 30
MIN_CLUSTERS, MAX_CLUSTERS = 4, 6
BASE_PORT = 5000  # Starting port for localhost nodes

def generate_topology():
    num_nodes = random.randint(MIN_NODES, MAX_NODES)
    num_clusters = random.randint(MIN_CLUSTERS, MAX_CLUSTERS)
    
    print(f"Generating network with {num_nodes} nodes across {num_clusters} clusters...")

    # 1. Generate Cluster Centers
    # We keep centers a bit away from the edges to allow natural clustering
    centers = [(random.randint(150, 850), random.randint(150, 850)) for _ in range(num_clusters)]

    nodes = {}
    clusters = {i: [] for i in range(num_clusters)}

    # 2. Generate Nodes and Assign to Clusters
    for i in range(num_nodes):
        c_id = i % num_clusters  # Distribute nodes evenly across clusters
        cx, cy = centers[c_id]
        
        # Distribute nodes normally around the cluster center
        x = min(GRID_SIZE, max(0, int(random.gauss(cx, 60))))
        y = min(GRID_SIZE, max(0, int(random.gauss(cy, 60))))
        
        node_id = f"node_{i:02d}"
        nodes[node_id] = {
            'pos': (x, y), 
            'cluster': c_id,
            'ip': '127.0.0.1',
            'port': BASE_PORT + i
        }
        clusters[c_id].append(node_id)

    links = set()

    def add_link(n1, n2):
        if n1 != n2:
            links.add(tuple(sorted([n1, n2])))

    # 3. Create Intra-Cluster Connections (Internal Connectivity)
    # Connecting nodes in a ring guarantees internal connectivity and a base degree of 2
    for c_id, members in clusters.items():
        random.shuffle(members)
        for j in range(len(members)):
            add_link(members[j], members[(j + 1) % len(members)])

    # 4. Create Inter-Cluster Connections (Global Connectivity)
    # We connect Cluster i to i+1, and i to i+2 to ensure robust alternative paths
    for i in range(num_clusters):
        c_current = i
        c_next = (i + 1) % num_clusters
        c_skip = (i + 2) % num_clusters
        
        # Link to the adjacent cluster
        n1 = random.choice(clusters[c_current])
        n2 = random.choice(clusters[c_next])
        add_link(n1, n2)
        
        # Link to another cluster to ensure >= 2 independent paths
        n3 = random.choice(clusters[c_current])
        n4 = random.choice(clusters[c_skip])
        add_link(n3, n4)

    # 5. Calculate Delays and Format Output
    topology_output = {}
    for node, data in nodes.items():
        topology_output[node] = {
            "ip": data['ip'],
            "port": data['port'],
            "pos": data['pos'],
            "cluster": data['cluster'],
            "neighbors": {}
        }

    for n1, n2 in links:
        x1, y1 = nodes[n1]['pos']
        x2, y2 = nodes[n2]['pos']
        
        # Base delay is Euclidean distance (1 unit = 1ms)
        distance = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
        delay = round(distance, 2)
        
        topology_output[n1]["neighbors"][n2] = {"base_delay_ms": delay}
        topology_output[n2]["neighbors"][n1] = {"base_delay_ms": delay}

    # Save to JSON
    with open('topology.json', 'w') as f:
        json.dump(topology_output, f, indent=4)
    print("Topology successfully saved to 'topology.json'.")

if __name__ == "__main__":
    generate_topology()