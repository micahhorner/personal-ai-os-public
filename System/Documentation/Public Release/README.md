---
id: doc-public-release-assets
x_reviewed_against: ["doc-canonical-architecture:2.22.0"]
type: system-doc
file_class: canonical
authority: derived
derived_from: [doc-canonical-architecture]
canonical_for: public-release-asset-manifest
version: 1.0.0
created: 2026-08-14
updated: 2026-08-14
summary: "Manifest separating current v1.64.6 release materials from immutable historical release evidence."
---

# Public release materials

This directory contains reviewed materials for v1.64.6. Product behavior is governed by the root manifest and canonical product documentation, not by sales copy.

## Release-state boundary

- **Current v1.64.6 materials:** the version-neutral files in `Architecture/`, `Buyer Collateral/`, and `Messaging/`. Target-bound machine evidence is distributed separately with the GitHub release assets for tag `v1.64.6`.
- **Historical evidence:** `Evidence/v1.64.1.md`, `Evidence/final-gate-v1.64.1.json`, and `Architecture/ai-os-proof-card-v1641.{svg,png}`. These remain bound only to immutable v1.64.1 at commit `fc39fc55002a3822a201bda3af0bab63d49a03a2`.
- **Not duplicated in-tree:** v1.64.6 machine evidence or a proof card. GitHub release assets are the target-bound evidence distribution surface.

## Product architecture

[`Architecture/`](Architecture/) contains version-neutral current v1.64.6 explainers, concise and full architecture graphics, an accessible Markdown transcript, and the text-free hero. The full architecture plus its text companion is the canonical public high-level explanation; the concise diagram is an orientation aid. The v1.64.1 proof card is retained only as a historical artifact and must not be presented as current v1.64.6 proof.

## Buyer collateral

[`Buyer Collateral/`](Buyer%20Collateral/) contains current landing-page copy, a client-facing leave-behind, the price sheet, and competitive-positioning guidance. These describe the product and consulting offer; they do not override product mechanics, license terms, security boundaries, or release evidence.

## Messaging controls

[`Messaging/`](Messaging/) contains the current v1.64.6 claims ledger, message house, and plain-language explanations. The claims ledger is the factual boundary for outward claims. Prices, service levels, guarantees, and consulting terms remain business commitments rather than product-test results.

## Release evidence

[`Evidence/`](Evidence/) contains a concise public v1.64.1 evidence summary and the machine-readable final gate bound to the immutable v1.64.1 tag and commit. It qualifies product mechanics only; it does not claim independent human testing or formal external runtime certification.

## Explicit exclusions

This set intentionally excludes all workshop material not named in the approved publication allow-list, including:

- PMM Engine assets and claims, which belong to a separate product and qualification line;
- thought-leadership drafts;
- old or superseded graphics and explainers;
- GTM plans, session transcripts, handoffs, external-audit prompts, and other working files;
- private fixtures, raw test traces, credentials, personal-instance data, and temporary filesystem paths.

Presence in a nearby workshop directory never made a file publishable. Only the files inventoried here were selected.

## Included source inventory

The approved allow-list contains 12 logical entries represented here by 16 physical files. The current architecture SVG sources and deterministic PNG derivatives are both included. The earlier planning total of 17 was an arithmetic error; the named content, not that total, governs scope:

- 3 messaging files;
- 4 buyer-collateral files;
- 9 architecture files: one hero PNG, one HTML explainer, two current SVG/PNG pairs, one Markdown accessibility companion, and the historical v1.64.1 proof-card SVG/PNG pair.

The two evidence files and this manifest are release-control records created in the product; they are not additional workshop imports.
