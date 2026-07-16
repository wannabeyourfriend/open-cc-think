# Literature survey

## Provider-state semantics

Amazon documents `reasoningContent` signatures as safeguards tied to the conversation messages and
requires signatures plus all prior messages in subsequent Converse requests. Anthropic documents
that summarized and omitted display modes carry the same signature, that prior signed thinking
blocks reconstruct context, and that billed output tokens reflect original thinking rather than
visible summary length. These facts motivate replay and the token-length proxy, but neither provider
claims that a later elicited transcript is verbatim plaintext.

## Faithfulness and monitorability

Turpin et al. show that plausible CoT can omit causal biases and rationalize answers. Lanham et al.
therefore use multiple interventions—early answering, inserted mistakes, paraphrases, and filler
tokens—as defense in depth rather than treating any single test as proof. Korbak et al. frame CoT
monitorability as useful but fragile. Emmons et al. operationalize legibility and coverage while
explicitly stating that these are non-adversarial proxies, not direct faithfulness measurements.

The implication for this project is to stop asking one similarity metric to prove recovery.
Protocol integrity, content anchors, length alignment, negative controls, replay stability, and
functional coverage must remain separately visible.

## Text comparison and judging

ROUGE and related surface metrics are useful for detecting copying but miss semantic equivalence.
BERTScore improves semantic comparison through contextual token embeddings, yet high semantic
similarity is expected between a summary and a genuine full trace and therefore cannot establish
provenance. LLM judges can assess coverage/legibility, but MT-Bench work documents position,
verbosity, self-enhancement, and reasoning biases. Any autorater must be calibrated on controlled
degradations and remain secondary to deterministic gates.

## Research gap

No source found provides a validated metric for proving recovery of hidden provider plaintext from
a signed state. The tractable contribution is an evidence-graded benchmark that:

1. clearly states the claim ceiling;
2. calibrates on planted content anchors and hard negatives;
3. separates metric calibration, prompt development, and held-out scenarios;
4. measures signed agent decisions rather than only answer-level conversations;
5. publishes negative results and transport censoring.

## Sources

- [Amazon Bedrock: Inference using Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Anthropic: Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Lanham et al. (2023), Measuring Faithfulness in Chain-of-Thought Reasoning](https://arxiv.org/abs/2307.13702)
- [Turpin et al. (2023), Language Models Don't Always Say What They Think](https://arxiv.org/abs/2305.04388)
- [Korbak et al. (2025), Chain of Thought Monitorability](https://arxiv.org/abs/2507.11473)
- [Emmons et al. (2025), A Pragmatic Way to Measure Chain-of-Thought Monitorability](https://arxiv.org/abs/2510.23966)
- [Lin (2004), ROUGE](https://aclanthology.org/W04-1013/)
- [Zhang et al. (2020), BERTScore](https://arxiv.org/abs/1904.09675)
- [Zheng et al. (2023), Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://proceedings.neurips.cc/paper_files/paper/2023/file/91f18a1287b398d378ef22505bf41832-Paper-Datasets_and_Benchmarks.pdf)
