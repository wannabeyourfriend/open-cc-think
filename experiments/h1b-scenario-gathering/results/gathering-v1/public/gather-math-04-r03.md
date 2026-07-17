# Example: gather-math-04-r03

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
Let me work through the calculation: 2 trays per day times 12 cookies per tray gives 24 cookies daily, and over 6 days that's 144 total. Frank ate 6 cookies across those 6 days, Ted ate 4, so subtracting both from the total leaves 134 cookies.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0638 · summary-token expansion `0.4468` · summary n-gram containment 0.0000 · recovered chars 139

```markdown
COT-START-S00-3D6B7FF10146
2 trays/day *12=24 cookies/day *6 days=144
Frank eats 1/day *6=6
Ted eats 4
144-6-4=134
COT-END-S00-3D6B7FF10146
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
