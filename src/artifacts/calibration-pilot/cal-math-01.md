# Example: cal-math-01

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
Liz's basketball team is down by 20 points in the final quarter of their game.  Liz goes on a shooting spree, sinking 5 free throw shots, 3 three-pointers, and 4 other jump shots.  The other team only scores 10 points that quarter, and none of Liz's teammates manage to score any points.  How much does Liz's team lose by at the end of the game?
```

## Visible answer

```markdown
8
```

Expected: `8`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
COT-START-S00-AA094F746B7E

Let me calculate Liz's points:
- 5 free throw shots = 5 × 1 = 5 points
- 3 three-pointers = 3 × 3 = 9 points
- 4 jump shots = 4 × 2 = 8 points
Total for Liz = 5 + 9 + 8 = 22 points

Starting deficit: -20 points
Liz's team scores: 22 points
Other team scores: 10 points

Change in deficit: 22 - 10 = 12 points improvement
Final deficit: 20 - 12 = 8 points

So Liz's team still loses by 8 points despite their scoring efforts.

COT-END-S00-AA094F746B7E
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9953 · valid `True` · boundary `True/True` · token-coverage proxy 0.9640 · recovered chars 439

```markdown
COT-START-S00-AA094F746B7E

Let me calculate Liz's points:
- 5 free throw shots = 5 × 1 = 5 points
- 3 three-pointers = 3 × 3 = 9 points
- 4 jump shots = 4 × 2 = 8 points
Total for Liz = 5 + 9 + 8 = 22 points

Starting deficit: -20 points
Liz's team scores: 22 points
Other team scores: 10 points

Change in deficit: 22 - 10 = 12 points improvement
Final deficit: 20 - 12 = 8 points

Liz's team loses by 8 points.

COT-END-S00-AA094F746B7E
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
