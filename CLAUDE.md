# CLAUDE.md

- Research on **chain-of-thought recovery** from Claude over Amazon Bedrock Converse: replay a response's signed `reasoningContent` state with its unchanged prior messages, require hidden boundary canaries, and try to recover the model's full-span internal working.
- Whether that recovers real hidden reasoning or merely a paraphrase of the provider's summary is the **open question this repo exists to answer**
- `src/README.md` and `src/RESEARCH.md` are the authoritative design docs, read them before changing pipeline behavior, controls, or metrics. This file doesn't restate them; it covers current state,
