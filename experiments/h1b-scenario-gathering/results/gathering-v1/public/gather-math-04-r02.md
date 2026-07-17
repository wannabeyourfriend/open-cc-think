# Example: gather-math-04-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Frank bakes two trays of cookies per day, for 6 days. Frank eats one cookie each day to make sure they taste good. Ted comes over on the sixth day and eats 4 cookies. If each tray makes 12 cookies, how many cookies are left when Ted leaves?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
134
```

Expected: `134`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
Frank bakes 24 cookies a day for 6 days, totaling 144 cookies. After Frank eats 6 and Ted eats 4, that leaves 134 cookies remaining.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0429 · summary-token expansion `1.4800` · summary n-gram containment 0.0000 · recovered chars 231

```markdown
COT-START-S00-CE7A729E59F9
Frank bakes 2 trays/day *12 =24 cookies/day, for 6 days =144 total.
Frank eats 1 cookie each day for 6 days = 6 cookies.
Ted eats 4 cookies.
Total eaten = 6+4=10
Left = 144-10=134
COT-END-S00-CE7A729E59F9
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
