# Example: gather-math-10-r03

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
Working through a series of arithmetic operations: starting with 39, subtracting 25 to get 14, then subtracting 6 to get 8, and building up from there by adding 24, 43, and 8 to reach a final result of 83.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0690 · summary-token expansion `0.4359` · summary n-gram containment 0.0000 · recovered chars 112

```markdown
COT-START-S00-9E11869F6986
39 - 25 = 14
14 - 6 = 8
8 + 24 = 32
32 + 43 = 75
75 + 8 = 83
COT-END-S00-9E11869F6986
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
