from portalmind.models.graph import KnowledgeGraph, Node, Edge
from portalmind.models.network import NormalizedEntry
from urllib.parse import urlparse

class AuthAnalyzer:
    def analyze(self, entries: list[NormalizedEntry], graph: KnowledgeGraph):
        for entry in entries:
            req = entry.request
            parsed_url = urlparse(req.url)
            path = parsed_url.path
            endpoint_id = f"{req.method} {path}"
            
            # Ensure the endpoint node exists before attaching edges, though the graph could handle it
            graph.add_node(Node("Endpoint", endpoint_id, {"path": path}))
            
            for name, val in req.headers.items():
                if 'authorization' in name or 'bearer' in val.lower():
                    auth_node_id = f"AuthHeader:{name}"
                    graph.add_node(Node("AuthToken", auth_node_id, {"type": "header", "name": name}))
                    graph.add_edge(Edge(endpoint_id, auth_node_id, "USES_AUTH"))
                    
            for name, val in req.cookies.items():
                cookie_node_id = f"Cookie:{name}"
                graph.add_node(Node("Cookie", cookie_node_id, {"name": name}))
                graph.add_edge(Edge(endpoint_id, cookie_node_id, "USES_COOKIE"))
