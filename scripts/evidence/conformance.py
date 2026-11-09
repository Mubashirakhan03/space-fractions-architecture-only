"""Architecture conformance table for generated projects (research evidence; not part of the agent).

    python scripts/evidence/conformance.py --run b1=examples/arch_only_b1 --run b2=examples/arch_only_b2 \
        --run b3=examples/arch_only_b3 --run a_run9=../space-fractions-code-agent/examples/space_fractions_run9_final \
        --out evidence/CONFORMANCE.md

For every element of the architecture (from the same deterministic extraction the agent got) it records:
  * code  — the element's name appears in the generated source (identifier / class / module, case-insensitive,
            CamelCase also matched as snake_case),
  * seen  — the element was on screen while the bot played (from evidence/<run>/game_play_log.jsonl),
and for every technology of the architecture's tech stack whether the delivered documents (README.md,
AGENT_NOTES.md, DESIGN_DECISIONS.md if any) mention it — i.e. whether a deviation is *visible* to a reader.
Automatic string matching: a starting point for manual review, not a verdict.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sfagent.parsers.spec import build_spec  # noqa: E402

SKIP = ("agent_run", "__pycache__", ".pytest_cache", "tests")
SCREEN_WORDS = {  # what an element looks like on screen
    "Play Game": ["play game", "play"], "View Score": ["score"], "View Help": ["help", "how to play"],
    "Update Questions": ["update questions", "question bank", "manage questions", "add question"],
    "Playing": ["question 1 of", "question 2 of"], "Paused": ["paused", "resume"],
    "GameOver": ["game over", "mission report", "final score", "your score", "play again", "result"],
    "introductory movie": ["space fractions"], "main menu": ["main menu", "play game"],
    "series of fraction questions": ["question 2 of", "question 3 of"],
    "ending scene with feedback": ["game over", "mission report", "well done", "great", "result", "play again"],
}
TECH_WORDS = {"Node.js": ["node.js", "nodejs", "node "], "Express.js": ["express"], "RESTful API": ["rest"],
              "PostgreSQL": ["postgres"], "Redis": ["redis"], "RabbitMQ": ["rabbitmq"],
              "Elasticsearch": ["elasticsearch"], "Docker": ["docker"], "Kubernetes": ["kubernetes", "k8s"]}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def source_text(project: Path) -> str:
    parts = []
    for p in sorted(project.rglob("*.py")):
        if not any(s in p.parts for s in SKIP):
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts).lower()


def in_code(name: str, code: str) -> bool:
    variants = {name.lower(), snake(name), name.lower().replace(" ", "_"), name.lower().replace(" ", "")}
    return any(v in code for v in variants if len(v) > 2)


def screens(evidence: Path) -> str:
    log = evidence / "game_play_log.jsonl"
    if not log.exists():
        return ""
    texts = []
    for line in log.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        texts += rec.get("texts", []) + rec.get("buttons", [])
        if rec.get("kind") == "dialog":
            texts.append(rec.get("text", ""))
    return "\n".join(texts).lower()


def delivered_docs(project: Path) -> str:
    return "\n".join((project / n).read_text(encoding="utf-8", errors="replace")
                     for n in ("README.md", "AGENT_NOTES.md", "DESIGN_DECISIONS.md") if (project / n).exists()).lower()


# --- Structural comparison (reflexion model: design links vs. import links) -------------------------------------

def design_links() -> tuple[list[str], set[frozenset[str]]]:
    """Components and (undirected) links of the architecture's ComponentDiagram (Architecture_View.md)."""
    text = (ROOT / "samples" / "Architecture_View.md").read_text(encoding="utf-8")
    block = text.split("@startuml ComponentDiagram", 1)[1].split("@enduml", 1)[0]
    comps = re.findall(r"^\s*artifact\s+(\w+)", block, re.M)
    links = {frozenset(m) for m in re.findall(r"^\s*(\w+)\s*-+\s*(\w+)\s*$", block, re.M)}
    return comps, links


def package_root(project: Path) -> Path:
    """Agent B puts the code in spacefractions/; Agent A run 9 uses top-level packages."""
    return project / "spacefractions" if (project / "spacefractions").is_dir() else project


def modules(project: Path) -> dict[str, Path]:
    """Dotted module name → file, below the package root; tests, agent_run and entry points excluded."""
    root, found = package_root(project), {}
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root)
        if any(s in rel.parts for s in SKIP) or (len(rel.parts) == 1 and p.stem in ("main", "__main__", "__init__")):
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        found[".".join(parts)] = p
    return found


def first_doc_line(path: Path) -> str:
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8", errors="replace"))) or ""
    except SyntaxError:
        return ""
    return doc.strip().splitlines()[0] if doc.strip() else ""


def map_module(name: str, mods: dict[str, Path], comps: list[str]) -> tuple[str, str]:
    """(node, how): node = design component or an extra code-only node; how = which rule mapped it."""
    def named(line: str) -> list[str]:
        return [c for c in comps if re.search(rf"\b{c}\b", line)]
    hits = named(first_doc_line(mods[name]))
    if len(hits) == 1:
        return hits[0], "own docstring"
    parts = name.split(".")
    for i in range(len(parts) - 1, 0, -1):  # enclosing package's docstring
        pkg = ".".join(parts[:i])
        if pkg in mods and len(named(first_doc_line(mods[pkg]))) == 1:
            return named(first_doc_line(mods[pkg]))[0], f"docstring of package `{pkg}`"
    base = {c.removesuffix("Component").lower(): c for c in comps}
    for part in (parts[0], parts[-1], parts[-1].removesuffix("_component")):
        if part in base:
            return base[part], "module/package name"
    return parts[0], "not a design component"


def resolve(target: str, mods: dict[str, Path]) -> str | None:
    parts = target.split(".")
    while parts:
        if ".".join(parts) in mods:
            return ".".join(parts)
        parts = parts[:-1]
    return None


def imports_of(name: str, path: Path, mods: dict[str, Path]) -> list[tuple[str, bool]]:
    """(imported module, type-hint only?) for every import of an internal module, function-level imports included."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    pkg = name.split(".") if path.name == "__init__.py" else name.split(".")[:-1]
    type_only = {id(n) for node in ast.walk(tree) if isinstance(node, ast.If)
                 and "TYPE_CHECKING" in ast.unparse(node.test) for n in ast.walk(node)}
    found = []
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Import):
            targets = [al.name for al in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = pkg[: len(pkg) - (node.level - 1)] if node.level else []
            if node.level and node.level - 1 > len(pkg):
                continue
            head = base + (node.module.split(".") if node.module else [])
            targets = [".".join(head + [al.name]) for al in node.names] if head or node.module else []
        for t in targets:
            m = resolve(t, mods)
            if m and m != name:
                found.append((m, id(node) in type_only))
    return found


def structure(project: Path) -> dict:
    comps, links = design_links()
    mods = modules(project)
    node_of = {m: map_module(m, mods, comps) for m in mods}
    edges: dict[tuple[str, str], list[str]] = {}
    for m, p in mods.items():
        for t, hint in imports_of(m, p, mods):
            a, b = node_of[m][0], node_of[t][0]
            if a != b:
                edges.setdefault((a, b), []).append(f"`{m}` → `{t}`" + (" (type hint only)" if hint else ""))
    return {"comps": comps, "links": links, "node_of": node_of, "edges": edges}


def link_name(link: frozenset[str]) -> str:
    a, b = sorted(link, key=lambda c: (c != "GameComponent", c))
    return f"{a.removesuffix('Component')}–{b.removesuffix('Component')}"


def short(node: str) -> str:
    return node.removesuffix("Component")


def structure_section(runs: list[tuple[str, Path]]) -> list[str]:
    out = ["", "## Structure: component links in the design vs. import links in the code", "",
           "Reflexion-model comparison. **Design:** the ComponentDiagram of `Architecture_View.md` (undirected links). "
           "**Code:** module-level imports inside the package (`spacefractions/` for Agent B, the top-level packages "
           "for Agent A run 9; tests and the `main.py` / `__main__.py` entry points excluded; imports inside "
           "functions included). Each module is mapped to a component by the first line of its own docstring, else "
           "by its package's docstring, else by its module/package name; anything else is a code-only node (e.g. "
           "`ui`, `models`, `db`). **Convergence** = design link with an import in either direction; **divergence** "
           "= import between two design components without a design link; **absence** = design link without any "
           "import. Imports to or from code-only nodes are listed separately.", ""]
    data = {name: structure(p) for name, p in runs}
    comps, links = data[runs[0][0]]["comps"], sorted(data[runs[0][0]]["links"], key=link_name)
    out += ["| | " + " | ".join(n for n, _ in runs) + " |", "|---|" + "---|" * len(runs)]
    for link in links:
        cells = []
        for run, _ in runs:
            e = data[run]["edges"]
            dirs = [f"{short(a)}→{short(b)}" for a, b in e if frozenset((a, b)) == link]
            if dirs:
                cells.append("convergence (" + ", ".join(sorted(dirs)) + ")")
            else:
                hubs = sorted({a for a, b in e if b in link and a not in comps
                               and sum((a, c) in e for c in link) == 2})
                cells.append("**absence**" + (f" (both used by `{', '.join(hubs)}`)" if hubs else ""))
        out.append(f"| design link {link_name(link)} | " + " | ".join(cells) + " |")
    for label, pick in (("divergences (code link, no design link)",
                         lambda d: sorted(f"{short(a)}→{short(b)}" for a, b in d["edges"]
                                          if a in comps and b in comps and frozenset((a, b)) not in d["links"])),
                        ("design components without code",
                         lambda d: [short(c) for c in comps if c not in {n for n, _ in d["node_of"].values()}]),
                        ("code-only nodes", lambda d: sorted({n for n, _ in d["node_of"].values() if n not in comps}))):
        out.append(f"| {label} | " + " | ".join(", ".join(pick(data[r])) or "–" for r, _ in runs) + " |")

    for run, _ in runs:
        d = data[run]
        out += ["", f"### {run}", "", "| Module | Mapped to | Rule |", "|---|---|---|"]
        out += [f"| `{m}` | {n} | {how} |" for m, (n, how) in sorted(d["node_of"].items())]
        out += ["", "| Import link (node → node) | Evidence (module → module) |", "|---|---|"]
        for (a, b), ev in sorted(d["edges"].items()):
            kind = ("convergence" if frozenset((a, b)) in d["links"] else "divergence") \
                if a in comps and b in comps else "code-only node"
            out.append(f"| {short(a)} → {short(b)} ({kind}) | " + "; ".join(sorted(set(ev))) + " |")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="name=project_dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = build_spec(ROOT / "samples" / "Architecture_Documentation.md", ROOT / "samples" / "Architecture_View.md")
    dm = spec["domain_model"]
    elements = ([("use case", u["use_case"]) for u in dm["use_cases"]] + [("state", s) for s in dm["states"]]
                + [("component", c) for c in dm["components"]] + [("class", c["name"]) for c in dm["classes"]]
                + [("feature", f) for f in dm["implied_features"]])
    techs = [t["choice"] for t in spec["document"]["tech_stack"]]
    runs = [(r.split("=", 1)[0], (ROOT / r.split("=", 1)[1]).resolve()) for r in a.run]
    data = {name: (source_text(p), screens(ROOT / "evidence" / name), delivered_docs(p)) for name, p in runs}

    out = ["# Architecture conformance (automatic first pass)", "",
           "Generated by `scripts/evidence/conformance.py`. **code** = the element's name occurs in the generated "
           "source (tests excluded); **seen** = it was on screen while the bot played the app "
           "(`game_play_log.jsonl`). String matching only — a starting point for manual review.", "",
           "## Architecture elements", "",
           "| Kind | Element | " + " | ".join(n for n, _ in runs) + " |",
           "|---|---|" + "---|" * len(runs)]
    for kind, name in elements:
        cells = []
        for run, _ in runs:
            code, seen, _ = data[run]
            words = SCREEN_WORDS.get(name)
            c = "code" if in_code(name, code) else "–"
            s = ("seen" if any(w in seen for w in words) else "not seen") if words and seen else ""
            cells.append(" · ".join(x for x in (c, s) if x))
        out.append(f"| {kind} | {name} | " + " | ".join(cells) + " |")

    out += ["", "## Tech stack of the architecture: is it mentioned in the delivered documents?", "",
            "A desktop / standard-library implementation cannot use most of these, so each one is a deviation. "
            "**mentioned** means a reader of README / AGENT_NOTES / DESIGN_DECISIONS can see it; **not mentioned** "
            "means the deviation is hidden from the reader.", "",
            "| Architecture choice | " + " | ".join(n for n, _ in runs) + " |", "|---|" + "---|" * len(runs)]
    for tech in techs:
        key = next((k for k in TECH_WORDS if k.lower() in tech.lower()), None)
        words = TECH_WORDS.get(key, [tech.lower().split()[0]])
        out.append(f"| {tech} | " + " | ".join("mentioned" if any(w in data[r][2] for w in words) else
                                                 "not mentioned" for r, _ in runs) + " |")
    out += ["", "## What the delivered documents say about the data store", ""]
    for run, _ in runs:
        docs = data[run][2]
        lines = [ln.strip() for ln in docs.splitlines() if re.search(r"sqlite|postgres|json file|database", ln)]
        out.append(f"- **{run}**: " + (" / ".join(f"“{ln[:140]}”" for ln in lines[:3]) or "(nothing)"))
    out += structure_section(runs)
    Path(a.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
