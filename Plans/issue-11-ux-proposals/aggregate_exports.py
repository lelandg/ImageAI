#!/usr/bin/env python3
"""Aggregate weighted UX-proposal exports for issue #11.

Reads one or more ``imageai-ux11-export/v1`` JSON files produced by the
interactive proposal pages in this directory and prints a ranked Markdown
table. Ranking: best (max) weight desc, then total weight desc, then number
of exports containing the option, then option ID.

Usage (from the repo root):
    python3 Plans/issue-11-ux-proposals/aggregate_exports.py Plans/issue-11-ux-proposals/exports/*.json

The same logic runs client-side in tab-recommendations-2026-07-29.html
(section 07). A weight of 10 in any export marks a top choice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA = "imageai-ux11-export/v1"


def load_exports(paths: list[str]) -> tuple[list[dict], list[str]]:
    exports, problems = [], []
    for p in paths:
        path = Path(p)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path}: {exc}")
            continue
        items = data if isinstance(data, list) else [data]
        for i, obj in enumerate(items):
            if isinstance(obj, dict) and obj.get("schema") == SCHEMA and isinstance(obj.get("selections"), list):
                exports.append(obj)
            else:
                problems.append(f"{path}[{i}]: not an {SCHEMA} object")
    return exports, problems


def aggregate(exports: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for ex in exports:
        try:
            weight = max(1, min(10, int(ex.get("weight", 1))))
        except (TypeError, ValueError):
            weight = 1
        for sel in ex["selections"]:
            oid = (sel or {}).get("id")
            if not oid:
                continue
            row = by_id.setdefault(
                oid, {"id": oid, "title": sel.get("title", ""), "best": 0, "total": 0, "hits": 0, "pages": set()}
            )
            row["best"] = max(row["best"], weight)
            row["total"] += weight
            row["hits"] += 1
            row["title"] = row["title"] or sel.get("title", "")
            row["pages"].add(ex.get("page", "?"))
    return sorted(by_id.values(), key=lambda r: (-r["best"], -r["total"], -r["hits"], r["id"]))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    exports, problems = load_exports(argv[1:])
    if not exports:
        print("No valid exports found.", file=sys.stderr)
        for p in problems:
            print(f"  skipped: {p}", file=sys.stderr)
        return 1
    rows = aggregate(exports)
    print(f"# ImageAI UX11 — aggregated ranking ({len(exports)} exports, {len(rows)} options)\n")
    print("| # | Option | Title | Best | Total | Exports | Pages |")
    print("|---|--------|-------|------|-------|---------|-------|")
    for i, r in enumerate(rows, 1):
        pages = ", ".join(sorted(r["pages"]))
        print(f"| {i} | `{r['id']}` | {r['title']} | {r['best']} | {r['total']} | {r['hits']} | {pages} |")
    if problems:
        print(f"\n> Skipped {len(problems)} invalid item(s):", file=sys.stderr)
        for p in problems:
            print(f">   {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
