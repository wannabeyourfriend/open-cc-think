# Provider documentation: signed reasoning state

- Organizations: Amazon Web Services; Anthropic
- Updated/accessed: 2026-07-17
- URLs:
  - https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
  - https://platform.claude.com/docs/en/build-with-claude/extended-thinking
  - https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5

## Relevant findings

- Bedrock requires a reasoning signature and unchanged prior messages for continuation.
- Anthropic says summarized and omitted displays use the same signature.
- On Sonnet 5, thinking display defaults to omitted unless summarized is requested.
- Billed output tokens correspond to original thinking tokens plus visible output, not merely the
  visible summary. Visible-summary token length therefore cannot be inferred from usage alone.
- Sonnet 5 rejects non-default sampling parameters, including explicit temperature.

## Implications

Signature acceptance is a state-continuity control, not plaintext ground truth. Billed output tokens
support a full-span length proxy. Local summary blanking is defensible because the signed block
structure and signature remain intact, but provider-side omitted display should still be tested as a
population-level ablation.
