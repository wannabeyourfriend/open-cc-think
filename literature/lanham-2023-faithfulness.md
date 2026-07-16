# Measuring Faithfulness in Chain-of-Thought Reasoning

- Authors: Tamera Lanham et al.
- Year: 2023
- URL: https://arxiv.org/abs/2307.13702

## Findings

The paper tests CoT faithfulness through early answering, inserted mistakes, paraphrasing, and filler
tokens. Effects vary substantially by task and model size. The authors explicitly present the tests
as defense in depth: each rules out a class of failure rather than proving faithfulness.

## Relevance

Recovery evaluation should likewise use multiple independent falsification tests. Functional
interventions can assess whether a trace contains useful reasoning, but they do not prove that the
trace is the provider's verbatim original.
