# Example: gather-math-13-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Tom plays 9 rounds of golf.  He takes an average of 4 strokes per hole.  The par value per hole is 3.  How many strokes over par was he?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
9
```

Expected: `9`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
So with 9 holes at 4 strokes each, that's 36 total strokes, which puts me 9 over par since par for 9 holes would be 27.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0759 · summary-token expansion `0.5556` · summary n-gram containment 0.0000 · recovered chars 123

```markdown
COT-START-S00-9244397AD17A
9 holes, 4 strokes each = 36 strokes. Par = 9*3=27. Over par = 36-27=9.
COT-END-S00-9244397AD17A
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
