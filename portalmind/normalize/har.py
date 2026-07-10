from portalmind.models.network import NormalizedRequest, NormalizedResponse, NormalizedEntry

def normalize_har_entry(entry: dict) -> NormalizedEntry:
    req = entry.get('request', {})
    res = entry.get('response', {})
    
    headers = {h['name'].lower(): h['value'] for h in req.get('headers', [])}
    cookies = {c['name']: c['value'] for c in req.get('cookies', [])}
    
    post_data = req.get('postData', {})
    
    n_req = NormalizedRequest(
        method=req.get('method', ''),
        url=req.get('url', ''),
        headers=headers,
        cookies=cookies,
        post_data=post_data.get('text'),
        post_mime_type=post_data.get('mimeType')
    )
    
    res_headers = {h['name'].lower(): h['value'] for h in res.get('headers', [])}
    content = res.get('content', {})
    
    n_res = NormalizedResponse(
        status=res.get('status', 0),
        headers=res_headers,
        content_type=content.get('mimeType', ''),
        content_text=content.get('text'),
        time_ms=entry.get('time', 0.0)
    )
    
    return NormalizedEntry(
        request=n_req,
        response=n_res,
        started_date_time=entry.get('startedDateTime', '')
    )

def normalize_har(har_data: dict) -> list[NormalizedEntry]:
    entries = har_data.get('log', {}).get('entries', [])
    return [normalize_har_entry(e) for e in entries]
