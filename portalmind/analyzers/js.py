from portalmind.models.timeline import Timeline
from portalmind.models.graph import KnowledgeGraph, Node

class JSAnalyzer:
    def analyze(self, timeline: Timeline, graph: KnowledgeGraph):
        for e in timeline.get_events_by_type("JSInvocation"):
            node_id = f"JS:{e.properties.get('function', 'anonymous')}"
            graph.add_node(Node("JSFunction", node_id, e.properties, created_by="JSAnalyzer", artifact=e.artifact))
