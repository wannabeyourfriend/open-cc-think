# Example: gather-math-11-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
At the height of cranberry season, there are 60000 cranberries in a bog. 40% are harvested by humans and another 20000 are eaten by elk. How many cranberries are left?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
16000
```

Expected: `16000`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm working through the math: 40% of 60,000 is 24,000 harvested, leaving 36,000, then subtracting another 20,000 gives 16,000 remaining.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0521 · summary-token expansion `0.5000` · summary n-gram containment 0.0000 · recovered chars 135

```markdown
COT-START-S00-AFF5AF2B8D5E
60000 * 0.4 = 24000 harvested
60000 - 24000 = 36000 remaining
36000 - 20000 = 16000
COT-END-S00-AFF5AF2B8D5E
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
