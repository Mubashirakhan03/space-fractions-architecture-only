"""Print the DeepSeek account balance (GET /user/balance — uses no tokens). The key comes from .env, never printed."""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sfagent.config import AppConfig  # noqa: E402

key = AppConfig().resolved_api_key()
req = urllib.request.Request("https://api.deepseek.com/user/balance",
                             headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.load(r)
for b in data.get("balance_infos", []):
    print(f"balance {b['currency']} {b['total_balance']} (available: {data.get('is_available')})")
