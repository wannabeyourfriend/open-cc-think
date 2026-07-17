# Example: gather-math-09-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Sienna gave Bailey half of her suckers. Jen ate half and gave the rest to Molly. Molly ate 2 and gave the rest to Harmony. Harmony kept 3 and passed the remainder to Taylor. Taylor ate one and gave the last 5 to Callie. How many suckers did Jen eat?

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
I'm working through the sequence of events backwards. Jen started with 22 cookies, ate half (11), and gave the remaining 11 to Molly. Molly then had 11 plus the 9 she'd received earlier, making 20 total before eating 2. Harmony kept 3 from her original 9 and passed 6 to Molly. Taylor ate 1 from her original 6 and gave 5 to Harmony.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.2688 · summary-token expansion `1.0154` · summary n-gram containment 0.0000 · recovered chars 365

```markdown
COT-START-S00-E54F29E45DD4
Taylor: ate 1, gave 5, so had 6 before eating.
Harmony: kept 3, passed 6, so had 9 before keeping.
Molly: ate 2, gave 9, had 11 before eating.
Jen: ate half, gave rest (11) to Molly, so had 22, ate 11.

Wait, "gave the rest to Molly" - rest after eating half is 11, so half=11, total=22, ate half=11.

Jen ate 11.
COT-END-S00-E54F29E45DD4
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
