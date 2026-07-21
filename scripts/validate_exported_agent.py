from __future__ import annotations
import json, os
from pathlib import Path
import yaml

REQUIRED = ("prompt.json", "prompt.md", "prompt.yaml", "manifest.yaml")

def main() -> None:
    name = os.environ["PROMPT_NAME"].strip()
    if not name.startswith("agents/"):
        raise SystemExit("Validation is restricted to agents/... paths.")
    root = Path("prompts") / name
    versions = sorted(
        [p for p in root.glob("version-*") if p.is_dir() and p.name[8:].isdigit()],
        key=lambda p: int(p.name[8:])
    )
    if not versions:
        raise SystemExit(f"No exported versions below {root}")
    directory = versions[-1]
    for filename in REQUIRED:
        path = directory / filename
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            raise SystemExit(f"Missing or empty artefact: {path}")
    raw = json.loads((directory / "prompt.json").read_text(encoding="utf-8"))
    deployable = yaml.safe_load((directory / "prompt.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((directory / "manifest.yaml").read_text(encoding="utf-8"))
    assert raw["name"] == name
    assert deployable["source"]["promptName"] == name
    assert manifest["prompt"]["langfuseName"] == name
    print(f"Validated four artefacts in {directory}")

if __name__ == "__main__":
    main()
