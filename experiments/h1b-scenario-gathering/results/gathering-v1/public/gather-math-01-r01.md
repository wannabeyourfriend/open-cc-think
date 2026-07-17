# Example: gather-math-01-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Anna sold 36 glasses of plain lemonade for $0.75 each. If she made $16 total from selling strawberry lemonade, how much more did she make from plain lemonade than strawberry?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
11
```

Expected: `11`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm working through a calculation: 36 times 0.75 gives me 27, then subtracting 16 leaves 11.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9300 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.1017 · summary-token expansion `0.4118` · summary n-gram containment 0.0000 · recovered chars 79

```markdown
COT-START-S00-C07A088D8867
36 * 0.75 = 27
27 - 16 = 11
COT-END-S00-C07A088D8867
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
