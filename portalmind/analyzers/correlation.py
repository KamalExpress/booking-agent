from portalmind.models.timeline import Timeline
from portalmind.models.graph import KnowledgeGraph, Edge

class CorrelationEngine:
    def correlate(self, timeline: Timeline, graph: KnowledgeGraph):
        js_events = timeline.get_events_by_type("JSInvocation")
        net_events = timeline.get_events_by_type("NetworkRequest")
        dom_events = timeline.get_events_by_type("DOMEvent")
        
        for js in js_events:
            js_node_id = f"JS:{js.properties.get('function', 'anonymous')}"
            for net in net_events:
                if js.timestamp <= net.timestamp <= js.timestamp + 5.0:
                    net_node_id = f"Endpoint:{net.properties.get('method')} {net.properties.get('url')}"
                    graph.add_edge(Edge(js_node_id, net_node_id, "TRIGGERS_REQUEST", created_by="CorrelationEngine", artifact=js.artifact))

        for dom in dom_events:
            dom_node_id = f"DOM:{dom.properties.get('selector', 'unknown')}"
            for js in js_events:
                js_node_id = f"JS:{js.properties.get('function', 'anonymous')}"
                if dom.timestamp <= js.timestamp <= dom.timestamp + 5.0:
                    graph.add_edge(Edge(dom_node_id, js_node_id, "TRIGGERS_JS", created_by="CorrelationEngine", artifact=dom.artifact))
