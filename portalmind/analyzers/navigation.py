from portalmind.models.timeline import Timeline
from portalmind.models.graph import KnowledgeGraph, Node

class NavigationAnalyzer:
    def analyze(self, timeline: Timeline, graph: KnowledgeGraph):
        for e in timeline.get_events_by_type("Navigation"):
            node_id = f"Nav:{e.properties.get('url', 'unknown')}"
            graph.add_node(Node("NavigationState", node_id, e.properties, created_by="NavigationAnalyzer", artifact=e.artifact))
