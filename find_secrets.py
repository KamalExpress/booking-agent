import os
import re

patterns = [
    re.compile(r'(?i)(password|secret|api_key|apikey|token|private_key).*?(:|=)'),
]
exclude_dirs = {'venv', '.pytest_cache', '.git', '__pycache__', 'logs'}
exclude_files = {'accounts.json', 'private_key.pem', 'settings.json'} # already known or to ignore

def search_secrets():
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if not (file.endswith('.py') or file.endswith('.json') or '.env' in file or file.endswith('.txt')):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if any(p.search(line) for p in patterns):
                            print(f"{path}:{i+1}:{line.strip()}")
            except Exception as e:
                pass

if __name__ == '__main__':
    search_secrets()
