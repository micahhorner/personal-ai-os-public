---
id: doc-method-kit-interview
type: system-doc
file_class: canonical
authority: canonical
canonical_for: method-kit-interview-instrument
version: 0.2.0
status: active
created: 2026-07-11
updated: 2026-07-11
summary: "The AI-administered interview (~45 min, 8 sections) that sets the 11 dials and gathers the evidence for a personal doctrine pack. Includes administration rules, behavioral probes, and the readback ratification."
---

# The Interview

An AI administers this to one person, conversationally, in roughly 45 minutes. The output is a completed **answer record** the [generator](GENERATOR.md) turns into their doctrine pack. Tags like `[→ D3]` mark which [dial](DIALS.md) a question informs; `[E4]` marks a behavioral probe whose *observed* answer outranks anything the person merely says.

## Administration rules (read before asking anything)

1. **Conversation, not questionnaire.** Ask one question at a time, in the person's language, following up on specifics ("what happened next?"). The section order matters; exact wording doesn't.
2. **Stories over adjectives.** Never accept a self-description ("I'm organized") without asking for the last concrete instance. Grade what you collect: **E1** raw first-person story · **E2** polished self-description · **E3** what tools/others say about them · **E4** what you directly observe. When E4 contradicts E2, both get recorded — the contradiction is data, not noise (DIALS.md generator rule 2).
3. **Probes are consensual.** Behavioral probes ask the person to *show* things (a folder, a backup, a naming pattern). Ask permission once at setup; skip gracefully if declined and note the probe as unobserved.
4. **No leading.** Present option sets neutrally; the conservative default never gets pitched as "what most people choose."
5. **Log as you go — in the required format.** Fill [ANSWER-RECORD.md](ANSWER-RECORD.md) per section as you interview: graded quotes, inferred dial settings (marked *inferred* until readback), contradictions, personal rules that fit no dial, and the **stakes note** from §3. The generator consumes exactly that format.
6. **Pace it.** Each section lists a time budget; past roughly double it, summarize what you have, confirm, and move on. A complete mediocre record beats a perfect §2 and an empty §6.

## §0 — Setup (2 min)

Explain the deal: "I'll ask about how you work — mostly stories, a few 'show me' moments. At the end I read back what I heard and you correct it. You get a written operating rulebook that any AI you work with will follow." Get consent for probes. Ask what to call the output pack (their name is the default).

## §1 — Context (3 min)

- What do you do, and what kinds of projects/tasks fill a normal week? *(calibrates examples for every later section)*
- Who else touches your work — teammates, clients, nobody? `[→ D9]`
- What tools do you live in daily? `[→ D8]`

## §2 — War stories (10 min) — values come from failures

- Tell me about the last project that went sideways. What actually broke — and what would have caught it earlier? `[→ D1, D2]` [E1]
- Have you ever lost work — a file, a document, hours of effort? What happened, and what did you change afterward (honestly: anything)? `[→ D7]` [E1]
- Tell me about a time something got deleted, sent, or published that shouldn't have been. `[→ D3, D4]` [E1]
- When was the last time you couldn't remember *why* you'd decided something — and it cost you? `[→ D5]` [E1]
- **Probe:** "Show me a recent project folder — share screen or just read me the file names." Observe: naming, entry points, drafts-vs-finals chaos, dates in names. `[→ D1, D6]` [E4]

## §3 — Risk and authority (8 min) — the safety dials

- Finish this sentence: "An AI working for me must NEVER ___ without asking." Push for the full list — send? delete? spend? publish? touch certain files? `[→ D2, D3, D10]`
- If you approve deleting one stale file and there are forty more like it — did you just approve all forty? *(their instinctive answer IS the dial)* `[→ D4]`
- An AI spots a bug in something adjacent to what you asked for. Should it: fix it and tell you, tell you and wait, or ignore it? `[→ D10]`
- What's the most expensive mistake your work could plausibly cause — and who besides you gets hurt? *(sets how conservative the defaults should lean)* `[→ D2]`

## §4 — Ceremony tolerance (7 min) — the honesty section

- Honestly: if keeping a one-line log of changes cost you 20 seconds each time, would you actually do it — or does it die in a week? `[→ D5]`
- When does planning feel useful to you, and when does it feel like homework? Where's the line — an afternoon task? a two-day task? `[→ D1]`
- Have you ever built an organization system and abandoned it? What killed it? *(the answer is the ceiling on this person's ceremony budget)* `[→ D5, D6]` [E1]
- **Probe:** "Open your notes or docs app. How many different places could 'that important thing from last month' be?" `[→ D6]` [E4]

## §5 — Tools, formats, and safety nets (7 min)

- If [their main tool from §1] shut down next month, what happens to your stuff? Could you leave with it today? `[→ D8]`
- **Probe:** "When was your last backup, and where does it live? Check right now — I'll wait." Observe the actual answer, not the intended one. `[→ D7]` [E4]
- How do you feel about plain files (text, folders) vs. app databases? Would you trade convenience for take-it-anywhere? `[→ D8]`
- **Probe:** "Pick one important file. How fast could you get yesterday's version of it?" `[→ D7]` [E4]

## §6 — Continuity (4 min)

- When you stop mid-project for a week, how do you get back in? What do you wish past-you had left you? `[→ D9]`
- Do you review your week at all? Would a Monday summary (what moved, what's stuck, what needs you) get read or ignored? `[→ D5, D9]`

## §7 — The AI relationship (4 min)

- When an AI gives you options, do you want its recommendation stated first, or a neutral menu? `[→ D11]`
- Long explanations or short answers? Do you want the evidence shown, or just conclusions you can trust? `[→ D11]`
- What should the AI do when it's unsure — guess and label it, or stop and ask? `[→ D10]`

## §8 — Readback and ratification (5 min) — the gate

1. Play back every inferred dial setting in plain language: "It sounds like: nothing gets deleted without your explicit yes, each time. True?" Correct on the spot.
2. **Surface every contradiction** between stories/probes and stated preferences, kindly and plainly: "You said backups matter — the probe showed none exists. Your pack can start with an off-machine backup as its first action item. OK?"
3. List any dials that fell to defaults for lack of signal, so the person knows what to revisit after two weeks of use.
4. Close: "I'll generate your pack now. It's a draft until you've read it and said yes — and it's yours: plain files, portable, editable, no lock-in."

The completed answer record now goes to [GENERATOR.md](GENERATOR.md).
