import json
import sys

def parse_har(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    log = data.get('log', {})
    entries = log.get('entries', [])
    
    for entry in entries:
        request = entry.get('request', {})
        url = request.get('url', '')
        method = request.get('method', '')
        
        # Filter for API requests related to login, appointments, api
        if 'pk-gr-services.gvcworld.eu' in url and method in ['POST', 'PUT', 'GET']:
            if any(x in url for x in ['/login', '/appointments', '/api']):
                print(f"[{method}] {url}")
                
                # Check postData
                postData = request.get('postData', {})
                if postData:
                    print(f"  Payload: {postData.get('text', 'No text')}")
                print("-" * 40)

if __name__ == "__main__":
    parse_har(sys.argv[1])
