# Example: gather-math-10-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
A man used to have 39 cows but last year 25 of them died and he sold 6 of them. This year the number of the cows increased by 24 and the man bought 43 more. His friend gave him 8 cows as a gift. How many cows does the man have now?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
83
```

Expected: `83`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm tracking the inventory changes: starting with 39 items, then accounting for deaths, sales, increases, purchases, and gifts to arrive at a final count of 83.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.5493 · summary-token expansion `0.7778` · summary n-gram containment 0.0000 · recovered chars 151

```markdown
COT-START-S00-4C20D622222C
Start: 39
Died: -25 = 14
Sold: -6 = 8
Increased by 24: +24 = 32
Bought 43: +43 = 75
Gift 8: +8 = 83
COT-END-S00-4C20D622222C
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
