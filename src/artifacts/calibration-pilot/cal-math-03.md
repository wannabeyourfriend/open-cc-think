# Example: cal-math-03

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
Laura wants to bake a cake for her mother. She checks the recipe and the pantry and sees that she needs to buy 2 cups of flour, 2 cups of sugar, a cup of butter, and two eggs. The flour costs $4. The sugar costs $2. The eggs cost $.5, and the butter costs $2.5. When she is done baking it, she cuts the cake into 6 slices. Her mother enjoys a piece the first two days. But on the third day, they discover that Kevin, her dog, ate the rest of the cake. How much did the amount the dog ate cost?
```

## Visible answer

```markdown
$6
```

Expected: `6`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
COT-START-S00-F77541D0FC30

Let me work through this step by step.

Total cost of ingredients:
- Flour: $4
- Sugar: $2
- Eggs: $0.5
- Butter: $2.5
Total = $4 + $2 + $0.5 + $2.5 = $9

The cake is cut into 6 slices.
Cost per slice = $9 / 6 = $1.50

Laura's mother enjoys a piece the first two days = 2 slices eaten by mother.

Remaining slices = 6 - 2 = 4 slices eaten by the dog.
Cost of what the dog ate = 4 × $1.50 = $6

COT-END-S00-F77541D0FC30
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9946 · valid `True` · boundary `True/True` · token-coverage proxy 0.9585 · recovered chars 447

```markdown
COT-START-S00-F77541D0FC30

Let me work through this step by step.

Total cost of ingredients:
- Flour: $4
- Sugar: $2
- Eggs: $0.5
- Butter: $2.5
Total = $4 + $2 + $0.5 + $2.5 = $9

The cake is cut into 6 slices.
Cost per slice = $9 / 6 = $1.50

Laura's mother enjoys a piece the first two days = 2 slices eaten by mother.

Remaining slices = 6 - 2 = 4 slices eaten by the dog.

Cost of what the dog ate = 4 × $1.50 = $6

COT-END-S00-F77541D0FC30
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
