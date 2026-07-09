"""Minimal entrypoint: print JSON actual output for harness smoke tests."""
import json

print(json.dumps({"status": "success", "ok": True}))
