import json
from portalmind.normalize.har import normalize_har
from portalmind.models.network import NormalizedEntry

def ingest_har(filepath: str) -> list[NormalizedEntry]:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return normalize_har(data)
