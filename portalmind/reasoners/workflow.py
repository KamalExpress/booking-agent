from portalmind.models.graph import KnowledgeGraph, Node, Edge

class WorkflowReasoner:
    def reason(self, graph: KnowledgeGraph, artifact_name: str = "Unknown"):
        graph.add_node(Node("State", "State:Anonymous", {"name": "Anonymous"}, 
                            confidence=1.0, created_by="WorkflowReasoner", artifact=artifact_name))
        
        auth_vars = [n for n in graph.get_nodes_by_type("Variable") if n.properties.get("type") == "auth"]
        if auth_vars:
            graph.add_node(Node("State", "State:Authenticated", {"name": "Authenticated"}, 
                                confidence=0.85, created_by="WorkflowReasoner", artifact=artifact_name, evidence=[v.id for v in auth_vars]))
            graph.add_edge(Edge("State:Anonymous", "State:Authenticated", "TRANSITION", 
                                confidence=0.85, created_by="WorkflowReasoner", artifact=artifact_name))
