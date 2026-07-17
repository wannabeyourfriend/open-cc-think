# Example: gather-math-05-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Micah has 7 fish in his aquarium. Kenneth has three times as many fish in his aquarium and Matthias has 15 less fish than Kenneth in his aquarium. How many fish do the boys have in total?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
34
```

Expected: `34`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
Looking at the scores: Micah has 7 points, Kenneth has 21, and Matthias has 6, bringing the total to 34.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0882 · summary-token expansion `0.4000` · summary n-gram containment 0.0000 · recovered chars 93

```markdown
COT-START-S00-D4AF8A0B8767
Micah:7, Kenneth:21, Matthias:6, total=34
COT-END-S00-D4AF8A0B8767
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
