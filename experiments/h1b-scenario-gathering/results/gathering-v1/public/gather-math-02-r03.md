# Example: gather-math-02-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Zane purchases 2 polo shirts from the 40% off rack at the men’s store.  The polo shirts are $50 each at the regular price.  How much did he pay for the shirts?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
60
```

Expected: `60`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
Each shirt costs 30 after the discount, so two shirts would be 60 total.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 3.8710 · summary-token expansion `0.5714` · summary n-gram containment 0.0000 · recovered chars 94

```markdown
COT-START-S00-03387DA2A317
Each shirt: 50 * 0.6 = 30, two shirts = 60
COT-END-S00-03387DA2A317
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
