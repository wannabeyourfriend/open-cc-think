# Example: gather-math-09-r03

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
Working backwards through the distribution: Jen started with 22 candies, ate half (11), and gave the rest to Molly. Molly received those 11, ate 2 of her own, and passed everything to Harmony. Harmony kept 3 and passed the remaining 9 to Taylor, who ate 1 and gave 5 to Callie.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.2746 · summary-token expansion `1.1961` · summary n-gram containment 0.0213 · recovered chars 330

```markdown
COT-START-S00-955BD679D43F
Taylor gave 5 to Callie after eating 1, so Taylor had 6.
Harmony kept 3 and passed remainder to Taylor, so Harmony had 3+6=9.
Molly ate 2 and gave rest to Harmony, so Molly had 2+9=11.
Jen ate half and gave rest to Molly - the rest equals 11, so Jen had 22 total, ate half = 11.
COT-END-S00-955BD679D43F
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
