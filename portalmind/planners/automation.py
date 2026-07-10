from portalmind.models.graph import KnowledgeGraph

class AutomationPlanner:
    def plan(self, graph: KnowledgeGraph):
        states = graph.get_nodes_by_type("State")
        variables = graph.get_nodes_by_type("Variable")
        
        return {
            "status": "ready" if len(states) > 1 and len(variables) > 0 else "needs_more_artifacts",
            "states_found": len(states),
            "variables_found": len(variables)
        }
