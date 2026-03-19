# MiroFish Proof Deep-Dive

Date: 2026-03-18

## Why previous numbers were not enough
A confidence number (e.g., 61%) alone does **not** prove live provider execution.
It can come from:
- a real upstream response, or
- fallback/stub logic.

So we added explicit runtime proof telemetry.

## New proof path implemented

### API endpoint
- `POST /mirofish/diagnostics`

Returns:
- `verdict`: `LIVE | FALLBACK | ERROR | NOT_CONFIGURED`
- `provider_mode`
- `live_error` (if fallback/error)
- `checks[]` table with endpoint-level diagnostics
  - `health`
  - `simulation_history`
  - `predict_endpoint`
  - `chat_bridge`
- `sample_predict`

### UI panel
Swarm page now includes:
- **MiroFish Proof** card (provider mode + verdict)
- **MiroFish Diagnostics (Deep Proof)** card with check table and detailed error text

## Current factual result in your environment
From diagnostics:
- `health`: OK
- `simulation_history`: OK
- `predict_endpoint`: FAIL (`404 /predict` missing)
- `chat_bridge`: FAIL (`500`, upstream `429 insufficient_quota`)

Verdict:
- `FALLBACK`
- Provider mode: `fallback_stub`

This is now explicit in UI and API. No hidden assumptions.

## Action items to reach LIVE verdict
1. Ensure MiroFish exposes a compatible `/predict` endpoint, **or**
2. Ensure `/api/report/chat` succeeds (quota/billing and model access fixed), and
3. Keep valid simulation history available.

Once either direct predict or chat bridge succeeds, verdict flips to `LIVE` automatically.
