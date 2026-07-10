from portalmind.models.graph import KnowledgeGraph, Node, Edge
from portalmind.models.network import NormalizedEntry
from urllib.parse import urlparse
import json

class SchemaAnalyzer:
    def analyze(self, entries: list[NormalizedEntry], graph: KnowledgeGraph):
        for entry in entries:
            req = entry.request
            parsed_url = urlparse(req.url)
            path = parsed_url.path
            endpoint_id = f"{req.method} {path}"
            
            if req.post_data:
                try:
                    parsed = json.loads(req.post_data)
                    keys = list(parsed.keys()) if isinstance(parsed, dict) else []
                    schema_id = f"ReqSchema:{endpoint_id}"
                    graph.add_node(Node("Schema", schema_id, {"type": "request", "keys": keys}))
                    graph.add_edge(Edge(endpoint_id, schema_id, "HAS_REQUEST_SCHEMA"))
                except:
                    pass
