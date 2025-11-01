import json
from pathlib import Path

CALLS_PATH = Path("tests/webhook_calls.json")

if CALLS_PATH.exists():
    print(json.loads(CALLS_PATH.read_text(encoding="utf-8")))
else:
    print("No webhook calls captured.")
