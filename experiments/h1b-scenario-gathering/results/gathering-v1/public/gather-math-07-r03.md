# Example: gather-math-07-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Beth went shopping. She bought 15 more cans of peas than twice the number of cans of corn that she bought. If she bought 35 cans of peas, how many cans of corn did she buy?

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
I'm solving for c by isolating it: starting with 35 equals 2c plus 15, I subtract 15 from both sides to get 2c equals 20, then divide by 2 to find c equals 10.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9300 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.1154 · summary-token expansion `0.2000` · summary n-gram containment 0.0000 · recovered chars 79

```markdown
COT-START-S00-151120215574
35 = 2c + 15
2c = 20
c = 10
COT-END-S00-151120215574
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
