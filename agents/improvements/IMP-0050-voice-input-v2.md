---
id: IMP-0050
title: Voice input v2 — whole-utterance capture + vocab-aware LLM polish, single paste
status: implemented
source: user-2026-07-14
affects: [meta]
risk: low
created: 2026-07-14
updated: 2026-07-14
commit: 64d506c
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

User (2026-07-14): "I'm not able to interact with AI via voice… the dictation is not very good.
This needs to be solved soon." The existing `voice/voice.py` (Azure Speech, toggle hotkey)
pasted **every recognized sentence immediately**: fragments landed mid-thought in the chat box,
the streaming recognizer never saw full-utterance context (worst case for technical vocabulary),
and there was no correction layer — raw ASR of "cosmos d b / all state / f d p o" went straight
into prompts.

## Proposal

v2 restructures to the pattern the best dictation tools use (capture whole → polish → paste once):

1. **Buffer, don't stream-paste:** toggle on → segments accumulate (printed live in the voice
   terminal only); toggle off → one paste. `Ctrl+Shift+X` cancels without pasting.
2. **LLM polish pass:** the joined transcript runs through Foundry `gpt-5.4`
   (`DefaultAzureCredential`, no keys — same Entra path as the eval harness) with
   `vocab-prompt.txt` embedded in the prompt: fixes technical terms, punctuation, strips filler
   words; hard instruction to never add/omit/answer. Fail-open: any polish error pastes the raw
   transcript instead — dictation is never lost. `VOICE_POLISH=0` disables.
3. **Vocab feeds two layers now:** Azure Speech PhraseList (streaming bias) + the polish prompt
   (correction) — adding a customer name once improves both.

## Acceptance criteria

- [x] Headless polish self-test passes (`python voice.py --selftest-polish`): verified
      2026-07-14 — "q b agent… all state… cosmos d b… f d p o" → "QB agent… Woodgrove…
      Cosmos DB… FDPO", fillers stripped, meaning intact
- [ ] Live dictation session: one toggle cycle produces one polished paste into Copilot chat
- [ ] Wrong-term rate on a real dictated brief noticeably below v1 (user judgment)
- [ ] Fail-open verified: with network/auth broken, raw transcript still pastes

## Validation plan

User runs `start-voice.ps1` (admin terminal) and dictates a real prompt; iterate
`vocab-prompt.txt` with customer/agent names. If polish latency annoys (>3s), consider a
smaller/faster deployment via `VOICE_POLISH_DEPLOYMENT`.

## Eval Plan

- **Type:** manual (interaction tooling; polish path covered by the self-test)
- **Known limits:** capture quality still bounded by Azure Speech streaming ASR; if accuracy
  ceilings persist after vocab tuning, next step is batch re-transcription of the buffered audio
  with a transcribe-class model (audio capture refactor) or a commercial layer (Wispr Flow).

## Notes

- Source: direct user pain 2026-07-14. Builds on the user's existing `voice/` v1 rather than a
  new tool; deps (`openai`, `azure-identity`) already installed and proven by the eval harness.
- Alternatives noted for the record: VS Code Speech extension (integrated but on-device ASR,
  mediocre for jargon); Wispr Flow for Windows (commercial, excellent, system-wide) — the buy
  option if v2 still disappoints.
