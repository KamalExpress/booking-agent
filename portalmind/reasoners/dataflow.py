from portalmind.models.graph import KnowledgeGraph, Node, Edge

class DataFlowReasoner:
    def reason(self, graph: KnowledgeGraph, artifact_name: str = "Unknown"):
        endpoints = graph.get_nodes_by_type("Endpoint")
        cookies = graph.get_nodes_by_type("Cookie")
        auths = graph.get_nodes_by_type("AuthToken")
        
        for c in cookies:
            var_id = f"Var:Cookie:{c.properties['name']}"
            graph.add_node(Node("Variable", var_id, {"type": "cookie", "name": c.properties['name']}, 
                                confidence=0.9, created_by="DataFlowReasoner", artifact=artifact_name, evidence=[c.id]))
            
            for e in graph.edges:
                if e.target == c.id and e.relationship == "USES_COOKIE":
                    graph.add_edge(Edge(e.source, var_id, "CONSUMES_VARIABLE", 
                                        confidence=0.9, created_by="DataFlowReasoner", artifact=artifact_name))

        for a in auths:
            var_id = f"Var:Auth:{a.properties['name']}"
            graph.add_node(Node("Variable", var_id, {"type": "auth", "name": a.properties['name']}, 
                                confidence=0.94, created_by="DataFlowReasoner", artifact=artifact_name, evidence=[a.id]))
            
            for e in graph.edges:
                if e.target == a.id and e.relationship == "USES_AUTH":
                    graph.add_edge(Edge(e.source, var_id, "CONSUMES_VARIABLE", 
                                        confidence=0.94, created_by="DataFlowReasoner", artifact=artifact_name))
