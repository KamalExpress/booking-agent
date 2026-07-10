from portalmind.models.timeline import Timeline
from portalmind.models.graph import KnowledgeGraph, Node

class DOMAnalyzer:
    def analyze(self, timeline: Timeline, graph: KnowledgeGraph):
        for e in timeline.get_events_by_type("DOMEvent"):
            node_id = f"DOM:{e.properties.get('selector', 'unknown')}"
            graph.add_node(Node("DOMElement", node_id, e.properties, created_by="DOMAnalyzer", artifact=e.artifact))
