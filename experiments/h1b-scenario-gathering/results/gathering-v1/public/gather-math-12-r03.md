# Example: gather-math-12-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Tom decided to go on a trip. During this trip, he needs to cross a lake, which in one direction takes 4 hours. During this time, Tom needs an assistant to help him with the crossing. Hiring an assistant costs $10 per hour. How much would Tom have to pay for help with crossing the lake back and forth?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
80
```

Expected: `80`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
So a 4-hour trip each way comes to 8 hours total, which at $10 per hour works out to $80.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0857 · summary-token expansion `0.7000` · summary n-gram containment 0.0000 · recovered chars 120

```markdown
COT-START-S00-2A1448A49654
4 hours one way, back and forth = 8 hours total. $10/hour × 8 = $80.
COT-END-S00-2A1448A49654
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
