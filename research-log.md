# Research Log

Append-only timeline. Formal confirmatory experiments begin only after their protocol commit.

| # | Date | Type | Summary |
|---|---|---|---|
| 1 | 2026-07-17 | bootstrap | Scoped the question as evidence-graded signature-backed recovery, with an explicit claim ceiling below ground-truth CoT. Selected failure analysis, decomposition, and stakeholder auditability as the main ideation lenses. |
| 2 | 2026-07-17 | exploratory | Verified 11/11 pre-change mocked tests, reproduced the checked-in red audit (0/14 strong; 10 near-duplicate and 4 summary-visible), and initialized `open-reasoning` for real cases. These observations predate preregistration and are exploratory. |
| 3 | 2026-07-17 | exploratory | Live Sonnet 5 trials exposed a deprecated-temperature replay failure and long-request transport failures. Added and tested a provider fallback. A fresh `open-reasoning` palindrome run then answered 62 correctly and reached strong recovery: 2,508 recovery output tokens, 2,469 billed harvest output tokens, 5,916 recovery characters versus 2,010 summary characters, sequence similarity 0.2222, no leakage/refusal, both markers in order. This is one exploratory row, not a rate estimate. |
| 4 | 2026-07-17 | bootstrap | Surveyed provider documentation and primary work on CoT faithfulness, monitorability, lexical/semantic similarity, and LLM-judge bias. Defined metric v0.1 as a hard-gated evidence vector with token-length alignment and falsification controls. |
| 5 | 2026-07-17 | inner-loop | H1a confirmatory run: all 9 frozen checks passed. Current `strong_recovery` accepted 4/7 synthetic negatives; the new diagnostic conjunction accepted the complete trace and 0/7 negatives. Capped token coverage rewarded padded summary overflow, while log-symmetric alignment and n-gram containment exposed it. Full 14-test suite passed; production gate unchanged. |
| 6 | 2026-07-17 | report | Generated `to_human/progress-001.html` with the H1a false-positive comparison, failure mechanisms, control table, exploratory live feasibility row, and H1b direction. |
