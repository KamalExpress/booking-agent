from portalmind.models.timeline import TimelineEvent
from portalmind.models.artifact import TraceArtifact

def ingest_trace(artifact: TraceArtifact) -> list[TimelineEvent]:
    events = []
    
    # Placeholder for actual Playwright trace parsing logic
    # In reality, this extracts network requests, clicks, and navigation
    events.append(TimelineEvent(
        timestamp=100.0,
        type="NetworkRequest",
        artifact=artifact.path,
        properties={"method": "GET", "url": "https://api.example.com"}
    ))
    events.append(TimelineEvent(
        timestamp=101.0,
        type="DOMEvent",
        artifact=artifact.path,
        properties={"action": "click", "selector": "#login-btn"}
    ))
    events.append(TimelineEvent(
        timestamp=102.0,
        type="JSInvocation",
        artifact=artifact.path,
        properties={"function": "submitForm"}
    ))
    events.append(TimelineEvent(
        timestamp=103.0,
        type="Navigation",
        artifact=artifact.path,
        properties={"url": "https://api.example.com/dashboard"}
    ))
    
    return events
