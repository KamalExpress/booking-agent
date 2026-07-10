import os
import json
import pytest
from portalmind.ingest.har import ingest_har
from portalmind.models.graph import KnowledgeGraph
from portalmind.analyzers.endpoint import EndpointAnalyzer
from portalmind.analyzers.auth import AuthAnalyzer
from portalmind.analyzers.schema import SchemaAnalyzer
from portalmind.reasoners.dataflow import DataFlowReasoner
from portalmind.reasoners.workflow import WorkflowReasoner
from portalmind.storage.filesystem import FileSystemStorage

def test_pipeline():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic.har")
    entries = ingest_har(fixture_path)
    assert len(entries) == 2
    
    graph = KnowledgeGraph()
    EndpointAnalyzer().analyze(entries, graph)
    AuthAnalyzer().analyze(entries, graph)
    SchemaAnalyzer().analyze(entries, graph)
    
    DataFlowReasoner().reason(graph, artifact_name="synthetic.har")
    WorkflowReasoner().reason(graph, artifact_name="synthetic.har")
    
    endpoints = graph.get_nodes_by_type("Endpoint")
    assert len(endpoints) == 2
    
    cookies = graph.get_nodes_by_type("Cookie")
    assert len(cookies) == 1
    assert cookies[0].properties["name"] == "session_id"
    
    auth_headers = graph.get_nodes_by_type("AuthToken")
    assert len(auth_headers) == 1
    assert auth_headers[0].properties["name"] == "authorization"
    
    variables = graph.get_nodes_by_type("Variable")
    assert len(variables) > 0
    assert variables[0].artifact == "synthetic.har"
    assert variables[0].confidence >= 0.9
    
    states = graph.get_nodes_by_type("State")
    assert len(states) >= 1
    
    schemas = graph.get_nodes_by_type("Schema")
    assert len(schemas) == 1
    
    storage = FileSystemStorage(os.path.join(os.path.dirname(__file__), "output"))
    storage.export(graph)
    
    # Check outputs
    assert os.path.exists(os.path.join(storage.output_dir, "knowledge", "raw", "network.json"))

def test_trace_pipeline():
    from portalmind.ingest.trace import ingest_trace
    from portalmind.models.artifact import TraceArtifact
    from portalmind.models.timeline import Timeline
    from portalmind.analyzers.correlation import CorrelationEngine
    from portalmind.analyzers.dom import DOMAnalyzer
    from portalmind.analyzers.js import JSAnalyzer
    from portalmind.analyzers.navigation import NavigationAnalyzer
    
    artifact = TraceArtifact("synthetic.trace.zip")
    trace_events = ingest_trace(artifact)
    
    timeline = Timeline()
    for e in trace_events:
        timeline.add_event(e)
        
    assert len(timeline.events) == 4
    
    graph = KnowledgeGraph()
    DOMAnalyzer().analyze(timeline, graph)
    JSAnalyzer().analyze(timeline, graph)
    NavigationAnalyzer().analyze(timeline, graph)
    CorrelationEngine().correlate(timeline, graph)
    
    assert len(graph.edges) > 0
    triggers = [e for e in graph.edges if e.relationship in ("TRIGGERS_REQUEST", "TRIGGERS_JS")]
    assert len(triggers) > 0
