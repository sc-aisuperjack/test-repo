from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any
import yaml
from langfuse import get_client

VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}")
SAFE_SEGMENT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Missing configuration: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise SystemExit(f"Configuration must be a mapping: {path}")
    return value

def validate_prompt_name(prompt_name: str, allowed_root: str) -> list[str]:
    if not prompt_name or prompt_name.startswith("/") or ".." in prompt_name:
        raise SystemExit(f"Unsafe prompt name: {prompt_name!r}")
    if prompt_name != prompt_name.lower():
        raise SystemExit(f"Prompt names must be lowercase: {prompt_name}")
    segments = prompt_name.split("/")
    if len(segments) < 2 or segments[0] != allowed_root:
        raise SystemExit(f"Only prompts below '{allowed_root}/' may be exported: {prompt_name}")
    invalid = [s for s in segments if not SAFE_SEGMENT_PATTERN.fullmatch(s)]
    if invalid:
        raise SystemExit("Invalid path segment(s): " + ", ".join(invalid))
    return segments

def normalise(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")

def render_content(value: Any) -> str:
    if isinstance(value, str):
        return normalise(value).strip()
    if isinstance(value, list):
        return "\n\n".join(filter(None, (render_content(v) for v in value))).strip()
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return normalise(value["text"]).strip()
        if "content" in value:
            return render_content(value["content"])
        return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
    return str(value).strip()

def render_markdown(value: Any) -> str:
    if isinstance(value, str):
        return normalise(value).rstrip() + "\n"
    if isinstance(value, list):
        sections = []
        for i, message in enumerate(value, 1):
            if not isinstance(message, dict):
                raise SystemExit(f"Chat message {i} is not an object.")
            role = str(message.get("role", "message")).replace("_", " ").title()
            body = render_content(message.get("content", ""))
            if body:
                sections.append(f"## {role}\n\n{body}")
        if not sections:
            raise SystemExit("Chat prompt contains no renderable content.")
        return "\n\n".join(sections).rstrip() + "\n"
    return render_content(value).rstrip() + "\n"

def load_variable_map(path: Path) -> dict[str, str]:
    mappings = load_yaml(path).get("variables", {})
    if not isinstance(mappings, dict):
        raise SystemExit(f"'variables' must be a mapping in {path}")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in mappings.items()):
        raise SystemExit(f"Variable mappings must contain text values: {path}")
    return mappings

def convert_variables(text: str, mappings: dict[str, str]) -> tuple[str, list[str]]:
    used, unknown = [], []
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        used.append(name)
        if name not in mappings:
            unknown.append(name)
            return match.group(0)
        return "{{" + mappings[name] + "}}"
    converted = VARIABLE_PATTERN.sub(replace, text)
    if unknown:
        names = ", ".join(f"{{{{{n}}}}}" for n in sorted(set(unknown)))
        raise SystemExit(f"Unknown Langfuse variable(s): {names}. Add mappings to config/connect-variable-map.yaml.")
    return converted, sorted(set(used))

def main() -> None:
    policy = load_yaml(Path("config/prompt-export-policy.yaml"))
    export_policy = policy.get("export", {})
    allowed_root = str(export_policy.get("allowedRoot", "agents"))
    output_root = Path(str(export_policy.get("outputRoot", "prompts")))
    prompt_name = os.environ["PROMPT_NAME"].strip()
    label = os.environ.get("PROMPT_LABEL", "production").strip()
    segments = validate_prompt_name(prompt_name, allowed_root)

    prompt = get_client().get_prompt(prompt_name, label=label)
    version = getattr(prompt, "version", None)
    version_text = str(version)
    if not re.fullmatch(r"\d+", version_text):
        raise SystemExit(f"Unexpected Langfuse version: {version!r}")

    labels = list(getattr(prompt, "labels", []) or [])
    if label not in labels:
        raise SystemExit(f"Fetched version lacks required '{label}' label.")

    prompt_content = getattr(prompt, "prompt", None)
    if prompt_content in (None, "", []):
        raise SystemExit("The complete agent prompt is empty.")

    prompt_config = getattr(prompt, "config", {}) or {}
    if not isinstance(prompt_config, dict):
        raise SystemExit("Langfuse prompt config must be a JSON object.")

    markdown = render_markdown(prompt_content)
    connect_text, variables = convert_variables(
        markdown, load_variable_map(Path("config/connect-variable-map.yaml"))
    )

    version_dir = output_root.joinpath(*segments) / f"version-{version_text}"
    if version_dir.exists() and any(version_dir.iterdir()):
        raise SystemExit(f"Immutable version already exists: {version_dir}")
    version_dir.mkdir(parents=True, exist_ok=False)

    raw = {
        "name": prompt_name, "version": version, "labels": labels,
        "type": getattr(prompt, "type", None), "config": prompt_config,
        "prompt": prompt_content,
    }
    identity = {
        "supplierVendor": prompt_config.get("supplierVendor", segments[1] if len(segments) > 1 else None),
        "domain": prompt_config.get("domain", segments[2] if len(segments) > 2 else None),
        "channel": prompt_config.get("channel", segments[3] if len(segments) > 3 else None),
        "component": prompt_config.get("component", segments[-1]),
    }
    runtime = {
        "platform": prompt_config.get("platform", "amazon-connect"),
        "model": prompt_config.get("model", "not-specified"),
        "connectPromptType": prompt_config.get("connectPromptType", "not-specified"),
    }
    deployable = {
        "schemaVersion": 1,
        "source": {"system": "langfuse", "promptName": prompt_name, "promptVersion": version, "label": label},
        "identity": identity, "runtime": runtime,
        "template": {"format": "markdown", "text": connect_text},
        "variables": {"converted": variables},
    }
    manifest = {
        "schemaVersion": 1,
        "prompt": {"langfuseName": prompt_name, "langfuseVersion": version, "langfuseLabel": label},
        "identity": identity, "runtime": runtime,
        "artefacts": {"source": "prompt.json", "review": "prompt.md", "deployable": "prompt.yaml"},
        "release": {"status": "production-synchronised", "semanticVersion": None},
    }

    (version_dir / "prompt.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (version_dir / "prompt.md").write_text(markdown, encoding="utf-8")
    (version_dir / "prompt.yaml").write_text(yaml.safe_dump(deployable, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    (version_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    print(f"Exported {prompt_name} version {version_text} to {version_dir}")

if __name__ == "__main__":
    main()
