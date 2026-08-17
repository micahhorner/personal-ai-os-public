---
id: doc-method-kit-dials
type: system-doc
file_class: canonical
authority: canonical
canonical_for: method-kit-dial-registry
version: 0.1.0
status: active
created: 2026-07-11
updated: 2026-07-11
summary: "The personalization registry: 11 dials that make a doctrine pack personal. Each dial names what it controls, its settings, its default, and the interview sections that set it."
---

# The Dials — what makes a pack personal

Everything in [CORE.md](CORE.md) is universal. Everything here varies by person and is set by the [interview](INTERVIEW.md). Each dial has a **conservative default** — used when an answer is missing or contradictory — because the safe failure mode is too much care, not too little. The generator writes the chosen setting into the person's pack at the `⟨Dn⟩` markers.

| # | Dial | Controls | Settings (default **bold**) | Set by interview § |
|---|---|---|---|---|
| D1 | **Task/project threshold** | When work must get a plan and gates | by time (30m/2h/half-day), by tier (**anything above Medium**), by dependency count | §2, §4 |
| D2 | **Approval boundary** | What the AI may do without asking | conservative (**High+ asks**), balanced (Critical asks, High reports-after), delegated (named zones pre-approved) | §3 |
| D3 | **Deletion authority** | Who can destroy what | **owner-only, per instance**; owner-only, per category; AI may archive / never delete | §3 |
| D4 | **Approval scope** | How far one "yes" travels | **one approval = one instance**; approval covers the category for this project; standing approvals list | §3 |
| D5 | **Journaling depth** | What gets a written change record | everything medium+, **medium+ with weekly digest**, high/critical only | §4 |
| D6 | **Metadata richness** | Frontmatter on artifacts | full (id/dates/summary/class on everything), **standard** (dates+summary on substantive files), minimal (dates only) | §4, §5 |
| D7 | **Backup stack depth** | Layers of recoverability | full (checkpoint+snapshot+remote+archive+parallel-run), **standard** (checkpoint+remote), minimal (remote only) — floor: an off-machine copy MUST exist | §5 |
| D8 | **Portability strictness** | Tolerance for proprietary tools | strict (plain text only), **pragmatic** (proprietary allowed with named export path), relaxed (convenience wins, exit unplanned) | §5 |
| D9 | **Handoff depth** | Session-end ritual | full six-part handoff always, **handoff on multi-session projects only**, lightweight status note | §6 |
| D10 | **AI autonomy posture** | Report-first vs. fix-first | **report-first on everything consequential**, fix-and-report for named low-risk zones, fix-first except Critical | §3, §7 |
| D11 | **Report style** | How the AI communicates | terse bullets, **led-by-outcome prose with evidence**, full detail always; plus: recommendations mandatory vs. options acceptable | §7 |

## Rules for the generator

1. **Every dial gets set.** Missing or contradictory answers → the bold default, and the gap is listed in the pack's readback for the person to correct.
2. **Behavior beats claims.** If the behavioral probes (interview §2/§5) contradict a stated preference — e.g., "I'm meticulous" but no backup exists — set the dial from the *stated aspiration*, but record the observed gap in their pack's honest-position note. People are allowed to want to be better than they are; the pack should help them get there, not flatter them.
3. **Dials never weaken the Core.** No setting removes the spine, the evidence rule, the checkpoint-before-risk rule, or the off-machine-backup floor. A person who wants those removed doesn't want a doctrine pack.
4. **Additions welcome.** If the interview surfaces a genuinely personal rule that fits no dial (domain conventions, a hard privacy line, a tool mandate), it goes into their pack's own principles section, labeled as theirs — the registry stays these 11.
