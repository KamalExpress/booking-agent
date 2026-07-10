from dataclasses import dataclass
from typing import Optional

@dataclass
class Artifact:
    path: str
    type: str

@dataclass
class HARArtifact(Artifact):
    type: str = "HAR"

@dataclass
class TraceArtifact(Artifact):
    type: str = "Trace"

@dataclass
class DOMArtifact(Artifact):
    type: str = "DOM"

@dataclass
class JSArtifact(Artifact):
    type: str = "JS"
