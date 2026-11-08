"""Headless agent run (same Agent as the GUI), printing every event as one line.

    python scripts/run_agent_cli.py --out examples/space_fractions_generated \
        [--doc samples/Architecture_Documentation.md] [--view samples/Architecture_View.md] \
        [--profile profiles/space_fractions.md] [--mock] [--max-cost 1.0] [--max-requests 40] [--resume]

The DeepSeek key is read from DEEPSEEK_API_KEY / .env and never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sfagent.agent.loop import Agent  # noqa: E402
from sfagent.config import AppConfig  # noqa: E402
from sfagent.gui.controller import build_provider  # noqa: E402
from sfagent.parsers.spec import build_spec  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--doc", default=str(ROOT / "samples" / "Architecture_Documentation.md"))
    ap.add_argument("--view", default=str(ROOT / "samples" / "Architecture_View.md"))
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--max-cost", type=float, default=1.0)
    ap.add_argument("--max-requests", type=int, default=40)
    ap.add_argument("--fix-rounds", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=AppConfig.max_total_tokens)
    ap.add_argument("--max-steps", type=int, default=AppConfig.max_steps)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--record-deviations", action="store_true",
                    help="experiment switch: tell the model to record every deviation from the architecture")
    a = ap.parse_args()

    cfg = AppConfig(provider="mock" if a.mock else "deepseek", max_cost_usd=a.max_cost, max_requests=a.max_requests,
                    fix_rounds=a.fix_rounds, max_total_tokens=a.max_tokens, max_steps=a.max_steps,
                    doc_path=a.doc, view_path=a.view, output_dir=a.out, record_deviations=a.record_deviations)
    provider = build_provider(cfg)
    spec = build_spec(Path(a.doc), Path(a.view))
    started = time.time()

    def on_event(kind: str, d: dict) -> None:
        t = f"[{time.time() - started:6.1f}s]"
        if kind == "usage":
            line = f"usage requests={d['requests']} cost=${d['cost_usd']:.4f} tokens={d['usage']}"
        elif kind == "tool_call":
            line = f"→ {d['summary']}"
        elif kind == "tool_result":
            line = f"   {'ok ' if d['ok'] else 'ERR'} {d['preview'].splitlines()[0][:200] if d['preview'] else ''}"
        elif kind == "todos":
            line = "todos " + " | ".join(f"{t['status'][:4]}:{t['content'][:50]}" for t in d["todos"])
        elif kind == "verify":
            line = f"VERIFY {'PASSED' if d['ok'] else 'FAILED'}\n{d['report'][-2500:]}"
        elif kind == "done":
            line = "DONE " + json.dumps(d["result"], default=str)
        else:
            line = f"{kind}: {d.get('text') or d.get('phase') or ''}"
        print(t, line, flush=True)

    print(f"provider={provider.name} model={provider.model} variant=architecture-only "
          f"record_deviations={'ON' if a.record_deviations else 'OFF'} out={a.out}", flush=True)
    result = Agent(provider, cfg, a.out, spec, on_event=on_event).run(resume=a.resume)
    return 0 if result.status == "completed" and result.verify_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
