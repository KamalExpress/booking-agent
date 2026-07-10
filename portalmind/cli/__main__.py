import argparse
from portalmind.ingest.har import ingest_har
from portalmind.ingest.trace import ingest_trace
from portalmind.models.graph import KnowledgeGraph
from portalmind.models.timeline import Timeline, TimelineEvent
from portalmind.models.artifact import HARArtifact, TraceArtifact

from portalmind.analyzers.endpoint import EndpointAnalyzer
from portalmind.analyzers.auth import AuthAnalyzer
from portalmind.analyzers.schema import SchemaAnalyzer
from portalmind.analyzers.dom import DOMAnalyzer
from portalmind.analyzers.js import JSAnalyzer
from portalmind.analyzers.navigation import NavigationAnalyzer
from portalmind.analyzers.correlation import CorrelationEngine

from portalmind.reasoners.dataflow import DataFlowReasoner
from portalmind.reasoners.workflow import WorkflowReasoner
from portalmind.planners.automation import AutomationPlanner
from portalmind.storage.filesystem import FileSystemStorage

def main():
    parser = argparse.ArgumentParser(description="PortalMind Intelligence Platform")
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("type", choices=["har", "dom", "trace"])
    ingest_parser.add_argument("file")
    
    args = parser.parse_args()

    if args.command == "ingest":
        timeline = Timeline()
        entries = []
        
        if args.type == "har":
            artifact = HARArtifact(args.file)
            entries = ingest_har(args.file)
            for i, e in enumerate(entries):
                timeline.add_event(TimelineEvent(timestamp=float(i), type="NetworkRequest", artifact=args.file, properties={"method": e.request.method, "url": e.request.url}))
                
        elif args.type == "trace":
            artifact = TraceArtifact(args.file)
            trace_events = ingest_trace(artifact)
            for e in trace_events:
                timeline.add_event(e)
        
        graph = KnowledgeGraph()
        
        if args.type == "trace":
            DOMAnalyzer().analyze(timeline, graph)
            JSAnalyzer().analyze(timeline, graph)
            NavigationAnalyzer().analyze(timeline, graph)
            CorrelationEngine().correlate(timeline, graph)
            
        if args.type == "har":
            EndpointAnalyzer().analyze(entries, graph)
            AuthAnalyzer().analyze(entries, graph)
            SchemaAnalyzer().analyze(entries, graph)
        
        DataFlowReasoner().reason(graph, artifact_name=args.file)
        WorkflowReasoner().reason(graph, artifact_name=args.file)
        
        plan = AutomationPlanner().plan(graph)
        
        storage = FileSystemStorage(".")
        storage.export(graph)
        
        print(f"Ingested {len(timeline.events)} timeline events. Knowledge Graph populated and exported.")
        print(f"Automation Status: {plan['status']} (States: {plan['states_found']}, Variables: {plan['variables_found']})")

if __name__ == "__main__":
    main()
