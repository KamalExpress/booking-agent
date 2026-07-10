from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class TimelineEvent:
    timestamp: float
    type: str
    artifact: str
    properties: Dict[str, Any] = field(default_factory=dict)
    frame_id: Optional[str] = None
    execution_context: Optional[str] = None
    call_stack: Optional[List[str]] = None

class Timeline:
    def __init__(self):
        self.events: List[TimelineEvent] = []

    def add_event(self, event: TimelineEvent):
        self.events.append(event)
        self.events.sort(key=lambda x: x.timestamp)
        
    def get_events_by_type(self, event_type: str) -> List[TimelineEvent]:
        return [e for e in self.events if e.type == event_type]
