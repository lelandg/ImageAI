"""Rebuild the credited sample through public CLI calls, without provider requests."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Output project library; default: a new temporary directory")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    entry = here.parents[1] / "main.py"
    root = args.root.resolve() if args.root else Path(tempfile.mkdtemp(prefix="imageai-lumen-"))

    def run(operation, data, project=None):
        command = [sys.executable, str(entry), "--sprite", operation, "--sprite-root", str(root),
                   "--sprite-data", "-", "--json"]
        if project:
            command.extend(["--sprite-project", project])
        result = subprocess.run(command, input=json.dumps(data), text=True, encoding="utf-8",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            sys.stderr.write(result.stderr)
            raise RuntimeError(result.stdout)
        return json.loads(result.stdout)

    created = run("new", {"name": "Lumen sample", "source": str(here / "lumen-source.png"),
        "settings": {"generation": {"aspect_ratio": "1:1"},
                     "background": {"mode": "solid", "color": "#14253D"},
                     "stabilize": {"pad_px": 8},
                     "profiles": [{"name": "hd", "cell_size": [320, 320]},
                                  {"name": "pixel", "cell_size": [96, 96], "palette_size": 64}]}})
    project = created["project"]
    run("action-edit", {"operation": "add", "values": {"name": "aha_constellation",
        "prompt": "The patient compiler discovers a constellation.", "fps": 8, "target_frames": 6}}, project)
    run("import-sheet", {"actions": ["aha_constellation"], "path": str(here / "lumen-aha-sheet.png"),
                          "columns": 6, "rows": 1}, project)
    run("process", {}, project)
    run("frame-edit", {"action": "aha_constellation", "operation": "update", "indices": list(range(6)),
                        "values": {"duration_ms": 160}}, project)
    run("frame-edit", {"action": "aha_constellation", "operation": "delete", "indices": [0]}, project)
    result = run("export", {"profiles": ["hd", "pixel"], "formats": ["gif", "grid", "aseprite_json"],
                            "engine_preset": "web_preview"}, project)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
