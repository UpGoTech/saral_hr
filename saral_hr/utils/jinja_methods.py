import json

def parse_json(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []
