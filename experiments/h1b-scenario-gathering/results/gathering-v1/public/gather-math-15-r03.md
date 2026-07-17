# Example: gather-math-15-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Cheryl ate 7 m&m's after lunch. She ate 5 m&m's after dinner, and she gave some to her sister. If Cheryl had 25 m&m's at the beginning, how many did she give to her sister?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
13
```

Expected: `13`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm working through a simple arithmetic calculation: 25 minus 7 equals 18, not 13.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9300 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.1132 · summary-token expansion `0.1333` · summary n-gram containment 0.0000 · recovered chars 61

```markdown
COT-START-S00-1A99F9C1B4BE
25-7-5=13
COT-END-S00-1A99F9C1B4BE
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
