# Research basis for signed full-CoT trajectory collection

This note fixes the terminology, calibration sources, and experimental controls used by the
Signature-CoT pipeline. The production target is Terminal-Bench 2.0 on Harbor, but prompt selection
must happen on separate data so the benchmark is not used as an optimization set.

## What is being measured

The project stores three different model outputs and never treats them as interchangeable:

1. **Provider CoT summary**: the readable text returned by Claude Sonnet 4.6 with
   `thinking.display="summarized"`.
2. **Visible answer/action**: assistant text and structured tool calls used by the environment.
3. **Signed full-span recovery**: text elicited by replaying the exact signed decision state and
   requiring both hidden boundary canaries.

AWS documents that a Converse `reasoningContent.reasoningText.signature` must be returned with the
unchanged prior messages for reasoning continuity. Anthropic documents that Sonnet 4.6 returns a
summary rather than the full internal thinking, while `display="omitted"` and
`display="summarized"` carry the same signature. This is the technical opening investigated here:

- [Amazon Bedrock Converse reasoning content](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Amazon Bedrock adaptive thinking](https://docs.aws.amazon.com/bedrock/latest/userguide/claude-messages-adaptive-thinking.html)
- [Claude extended-thinking display and summaries](https://platform.claude.com/docs/en/docs/build-with-claude/extended-thinking)

A boundary-complete recovery is **not** cryptographic proof of provider-verbatim plaintext. The
model may still omit, paraphrase, or fabricate text inside the recovered span. Artifacts therefore
label the field `signed_full_cot_recovery`, not `ground_truth_cot`.

## Relevant literature

### CoT usefulness and faithfulness

- Wei et al., [Chain-of-Thought Prompting Elicits Reasoning in Large Language
  Models](https://arxiv.org/abs/2201.11903), established CoT prompting across arithmetic,
  commonsense, and symbolic tasks.
- Yao et al., [ReAct](https://arxiv.org/abs/2210.03629), interleaves reasoning and actions and is the
  closest conceptual baseline for decision-level terminal traces.
- Turpin et al., [Language Models Don't Always Say What They
  Think](https://arxiv.org/abs/2305.04388), shows that plausible explanations can omit causal
  influences.
- Lanham et al., [Measuring Faithfulness in Chain-of-Thought
  Reasoning](https://arxiv.org/abs/2307.13702), evaluates interventions on CoT and finds substantial
  task- and model-dependent variation.
- Korbak et al., [Chain of Thought Monitorability: A New and Fragile Opportunity for AI
  Safety](https://arxiv.org/abs/2507.11473), motivates preserving monitorable reasoning while
  warning that it is an imperfect signal.
- OpenAI's [monitorability evaluation](https://openai.com/index/evaluating-chain-of-thought-monitorability/)
  separates CoT-only, action-only, and combined observations. The present trace schema preserves
  the same separation.

### Prompt optimization

- Zhou et al., [Automatic Prompt Engineer](https://arxiv.org/abs/2211.01910), treats instructions as
  programs and selects them on an evaluation set.
- Yang et al., [OPRO](https://arxiv.org/abs/2309.03409), uses an LLM to propose prompts based on
  scored prompt history.
- Fernando et al., [PromptBreeder](https://arxiv.org/abs/2309.16797), evolves task prompts and
  mutation prompts.

For the first controlled sweep, this project uses a smaller and more auditable method: a frozen
candidate pool, paired evaluation on the same signatures, scenario-macro scoring, successive
halving, and a final held-out calibration slice. Generative prompt mutation can be added only after
this baseline is stable.

### Existing reasoning and agent-trace data

- [OpenThoughts](https://arxiv.org/abs/2506.04178) studies open reasoning-data recipes across math,
  code, and science.
- [OpenCodeReasoning](https://arxiv.org/abs/2504.01943) studies code-reasoning distillation and data
  filtering.
- [SWE-Gym](https://arxiv.org/abs/2412.21139) releases executable software-engineering tasks and
  agent trajectories.
- [R2E-Gym](https://arxiv.org/abs/2504.07164) builds procedural repository-level environments and
  trajectories.
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) evaluates real terminal
  agents; new Terminal-Bench 2.0 runs use [Harbor](https://www.harborframework.com/docs/tutorials/running-terminal-bench).
- Harbor's [ATIF v1.7 RFC](https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md)
  is the output contract. One original LLM inference maps to one ATIF agent step.

These datasets generally contain model-produced rationales or visible ReAct thoughts. They do not
provide the combination targeted here: provider summary, signed-state full-span recovery, exact
tool protocol, and the visible answer in one validated ATIF record.

## Frozen calibration sources

The checked-in manifest contains 12 instances per scenario (36 total):

| Scenario | Source | Why it is used |
| --- | --- | --- |
| Coding | [OpenAI HumanEval](https://github.com/openai/human-eval) | Compact, deterministic code prompts; separate from Terminal-Bench |
| Math | [OpenAI GSM8K train split](https://github.com/openai/grade-school-math) | Multi-step arithmetic with parseable final answers |
| Chat | [LMSYS MT-Bench](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge) | Multi-turn open-ended chat across non-code/non-math categories |

Instances are selected deterministically from official source files using a fixed seed and SHA-256
ordering. GSM8K uses the training split; MT-Bench math, coding, and reasoning categories are
excluded from the chat stratum. Source byte hashes are stored in the manifest.

## Optimization protocol

1. Harvest every fixed instance once with Sonnet 4.6, adaptive thinking, high effort, and
   `display="summarized"`.
2. Preserve the exact prefix, assistant content, signature, visible answer/action, and tool-result
   bridge for every decision.
3. Evaluate all prompt candidates on the same first two instances per scenario.
4. Keep the top half; evaluate survivors on the next two instances per scenario.
5. Keep the top half; evaluate finalists on the next four instances per scenario.
6. Freeze the winner and report it on the remaining four instances per scenario.
7. Rank by scenario-macro valid rate, both-canary success, quality, coverage proxy, refusal rate,
   leakage, and variability. Do not optimize answer correctness with the extraction prompt.
8. Reject a production trajectory when any original decision lacks a signature or any recovered
   decision lacks ordered start/end canaries.

Original-agent metrics and extraction/replay metrics are reported separately. Extraction calls are
never inserted as agent actions in the ATIF trajectory.

