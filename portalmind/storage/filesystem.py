from portalmind.models.graph import KnowledgeGraph
import json
import os

class FileSystemStorage:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def export(self, graph: KnowledgeGraph):
        raw_dir = os.path.join(self.output_dir, "knowledge", "raw")
        os.makedirs(raw_dir, exist_ok=True)
        
        # Simple export: dump nodes by type
        endpoints = [n.properties for n in graph.get_nodes_by_type("Endpoint")]
        with open(os.path.join(raw_dir, "network.json"), "w") as f:
            json.dump(endpoints, f, indent=2)
            
        cookies = [n.properties for n in graph.get_nodes_by_type("Cookie")]
        with open(os.path.join(raw_dir, "cookies.json"), "w") as f:
            json.dump(cookies, f, indent=2)
            
        schemas = [n.properties for n in graph.get_nodes_by_type("Schema")]
        with open(os.path.join(raw_dir, "schemas.json"), "w") as f:
            json.dump(schemas, f, indent=2)
