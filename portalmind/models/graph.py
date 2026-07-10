from typing import Dict, List, Any, Optional

class Node:
    def __init__(self, node_type: str, node_id: str, properties: Dict[str, Any] = None,
                 confidence: float = 1.0, created_by: str = "Unknown", artifact: str = "Unknown", evidence: List[str] = None):
        self.type = node_type
        self.id = node_id
        self.properties = properties or {}
        self.confidence = confidence
        self.created_by = created_by
        self.artifact = artifact
        self.evidence = evidence or []

    def __repr__(self):
        return f"Node({self.type}, {self.id})"

class Edge:
    def __init__(self, source_id: str, target_id: str, relationship: str, properties: Dict[str, Any] = None,
                 confidence: float = 1.0, created_by: str = "Unknown", artifact: str = "Unknown", evidence: List[str] = None):
        self.source = source_id
        self.target = target_id
        self.relationship = relationship
        self.properties = properties or {}
        self.confidence = confidence
        self.created_by = created_by
        self.artifact = artifact
        self.evidence = evidence or []

    def __repr__(self):
        return f"Edge({self.source} -[{self.relationship}]-> {self.target})"

class KnowledgeGraph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []

    def add_node(self, node: Node):
        if node.id not in self.nodes:
            self.nodes[node.id] = node
        else:
            self.nodes[node.id].properties.update(node.properties)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
        
    def get_nodes_by_type(self, node_type: str) -> List[Node]:
        return [n for n in self.nodes.values() if n.type == node_type]
