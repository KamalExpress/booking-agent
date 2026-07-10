from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

@dataclass
class NormalizedRequest:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    post_data: Optional[str] = None
    post_mime_type: Optional[str] = None

@dataclass
class NormalizedResponse:
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    content_text: Optional[str] = None
    time_ms: float = 0.0

@dataclass
class NormalizedEntry:
    request: NormalizedRequest
    response: NormalizedResponse
    started_date_time: str = ""
