# Example: gather-math-14-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
The grocery store sells chips for $2 per packet and corn chips for $1.5 per packet. John would like to buy 15 packets of chips, and with the rest of the money he has left, buy as many packets of corn chips as he can. How many packets of corn chips could John buy if he has $45 for his entire purchase?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
10
```

Expected: `10`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm working through a calculation: multiplying 15 by 2 to get 30, then subtracting that from 45 to get 15, and finally dividing by 1.5 to arrive at 10.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0870 · summary-token expansion `0.2667` · summary n-gram containment 0.0000 · recovered chars 80

```markdown
COT-START-S00-9AC5A7D0D8B9
15*2=30, 45-30=15, 15/1.5=10
COT-END-S00-9AC5A7D0D8B9
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
