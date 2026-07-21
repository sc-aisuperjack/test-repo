# Langfuse setup for the agents-only production export

## Existing lowercase hierarchy

Keep:

- `shared/...`
- `domains/...`
- `channels/...`
- `supplier-vendors/...`
- `agents/...`

The first four roots contain micro prompts. `supplier-vendors/british-gas/...`
contains the 15 scaffold sections and British Gas-specific reusable content.
Only fully assembled prompts under `agents/...` are exportable.

## Recommended complete-agent names

- `agents/british-gas/payg/voice/assistant`
- `agents/british-gas/payg/voice/orchestration`
- `agents/british-gas/payments/chat/assistant`

## Agent config example

```json
{
  "supplierVendor": "british-gas",
  "domain": "payg",
  "channel": "voice",
  "component": "assistant",
  "platform": "amazon-connect",
  "model": "amazon_nova_2_sonic",
  "connectPromptType": "SELF_SERVICE_PRE_PROCESSING"
}
```

## GitHub dispatch

Event type:

`langfuse-production-prompt-update`

Required payload shape:

```json
{
  "event_type": "langfuse-production-prompt-update",
  "client_payload": {
    "prompt": {
      "name": "agents/british-gas/payg/voice/assistant"
    }
  }
}
```
