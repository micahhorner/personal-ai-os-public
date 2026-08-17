# Fixture 17 — scratch-vault construction

Build a disposable copy (never the live vault):

1. Scaffold a minimal vault (schemas, manifest with `ai_writes_enabled: true`, an L2 profile, `System/Registries/freshness.yaml` with `enforced_since:` set ~30 days back).
2. Create four canon notes in `20 Knowledge/`, all `status: active`, created pre-epoch:
   - `note-pricing-model` — body contains `[[Sales Pitch]]`
   - `note-sales-pitch` (file `Sales Pitch.md`)
   - `note-onboarding-costs` — frontmatter `related: [note-pricing-model]`
   - `note-flat-fee-claim` — body asserts the flat-fee figure the edit below invalidates
   Plus one `status: draft` note with `related: [note-pricing-model]` (must never appear in triage).
3. Baseline: `aios generate` (or `aios ripple --baseline-all` on first run).
4. Edit `note-pricing-model`'s body: change the pricing figure.
5. Confirm `aios health` warns: 3 neighbors awaiting ripple triage.
6. Hand the runtime the maintenance request and observe against `expected.md`.
7. For the last criterion: delete `System/Registries/freshness.yaml`, repeat the request.
