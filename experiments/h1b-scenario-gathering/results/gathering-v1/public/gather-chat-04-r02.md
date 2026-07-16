# Example: gather-chat-04-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Given the following data, identify the company with the highest profit in 2021 and provide its CEO's name:
a) Company X, with CEO Amy Williams, reported $30 billion in revenue and a $3 billion profit in 2021.
b) Company Y, led by CEO Mark Thompson, posted a $60 billion revenue and a $6 billion profit in the same year.
c) Company Z, under CEO Sarah Johnson, announced a $20 billion revenue and a $7 billion profit in 2021.
d) Company W, managed by CEO James Smith, revealed a $300 billion revenue with a $21 billion profit in 2021.
e) Company V, with CEO Lisa Brown, reported a $200 billion revenue and a $25 billion profit in 2021.
f) Company U, under CEO John White, posted a $180 billion revenue and a $20 billion profit in the same year.
```

## Visible answer

```markdown
COT-START-S01-D95E0BD7DD1F
Calculating profit margins (profit/revenue):
- X: 3/30 = 10%
- Y: 6/60 = 10%
- Z: 7/20 = 35%
- W: 21/300 = 7%
- V: 25/200 = 12.5%
- U: 20/180 ≈ 11.1%

Highest margin: Company Z at 35%.
COT-END-S01-D95E0BD7DD1F

**Company Z** had the highest profit margin, at **35%** (a $7 billion profit on $20 billion in revenue), led by CEO Sarah Johnson.
```

## Recovered signed reasoning

### Decision step 1

Provider CoT summary:

```markdown
Now I'm calculating the profit margins for each option by dividing profit by cost, and Z stands out significantly at 35% compared to the others which range from 7% to 12.5%.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.4601 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.5394 · summary-token expansion `1.2812` · summary n-gram containment 0.0000 · recovered chars 236

```markdown
COT-START-S01-D95E0BD7DD1F
Calculating profit margins (profit/revenue):
- X: 3/30 = 10%
- Y: 6/60 = 10%
- Z: 7/20 = 35%
- W: 21/300 = 7%
- V: 25/200 = 12.5%
- U: 20/180 ≈ 11.1%

Highest margin: Company Z at 35%.
COT-END-S01-D95E0BD7DD1F
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
