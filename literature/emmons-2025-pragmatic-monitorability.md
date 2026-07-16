# A Pragmatic Way to Measure Chain-of-Thought Monitorability

- Authors: Scott Emmons, Roland S. Zimmermann, David K. Elson, Rohin Shah
- Year: 2025
- URL: https://arxiv.org/abs/2510.23966

## Findings

The paper defines legibility and coverage and implements them with an LLM autorater calibrated on
synthetic degradations. It treats these as inexpensive default-monitorability proxies, not
substitutes for adversarial stress tests or direct faithfulness.

## Relevance

Coverage and legibility can be secondary recovery metrics after synthetic deletion, reordering,
contradiction, and verbosity calibration. Judge variance and same-family bias must be reported.
