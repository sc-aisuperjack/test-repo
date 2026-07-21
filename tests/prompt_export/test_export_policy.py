from pathlib import Path
import importlib.util
import pytest

path = Path(__file__).parents[2] / "scripts" / "export_langfuse_agent.py"
spec = importlib.util.spec_from_file_location("export_langfuse_agent", path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

@pytest.mark.parametrize("name", [
    "agents/british-gas/payg/voice/assistant",
    "agents/british-gas/payg/voice/orchestration",
    "agents/eon/billing/chat/assistant",
])
def test_agent_paths_allowed(name):
    assert module.validate_prompt_name(name, "agents")[0] == "agents"

@pytest.mark.parametrize("name", [
    "shared/guardrails/pii",
    "domains/payg/model-instructions/top-up",
    "channels/voice/response-schema/concision",
    "supplier-vendors/british-gas/persona/brand-tone",
])
def test_micro_prompt_roots_blocked(name):
    with pytest.raises(SystemExit):
        module.validate_prompt_name(name, "agents")

@pytest.mark.parametrize("name", [
    "Agents/british-gas/payg/voice/assistant",
    "agents/British-Gas/payg/voice/assistant",
    "../agents/british-gas/payg/voice/assistant",
    "/agents/british-gas/payg/voice/assistant",
])
def test_unsafe_names_blocked(name):
    with pytest.raises(SystemExit):
        module.validate_prompt_name(name, "agents")

def test_variable_conversion():
    converted, used = module.convert_variables(
        "Locale {{locale}} account {{account_number}}",
        {"locale": "$.locale", "account_number": "$.Custom.accountNumber"},
    )
    assert converted == "Locale {{$.locale}} account {{$.Custom.accountNumber}}"
    assert used == ["account_number", "locale"]

def test_unknown_variable_fails():
    with pytest.raises(SystemExit):
        module.convert_variables("{{unknown}}", {})
