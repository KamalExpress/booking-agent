from portalmind.models.graph import KnowledgeGraph, Node, Edge
from portalmind.models.network import NormalizedEntry
from urllib.parse import urlparse

class EndpointAnalyzer:
    def analyze(self, entries: list[NormalizedEntry], graph: KnowledgeGraph):
        for entry in entries:
            req = entry.request
            parsed_url = urlparse(req.url)
            path = parsed_url.path
            
            # Simple heuristic to ignore static assets
            if not path or path.startswith('chrome-extension') or 'fonts' in req.url or req.url.endswith(('.js', '.css', '.png', '.jpg', '.svg', '.woff2')):
                continue
                
            endpoint_id = f"{req.method} {path}"
            
            node = Node("Endpoint", endpoint_id, properties={
                "method": req.method,
                "url": req.url,
                "path": path
            })
            graph.add_node(node)
