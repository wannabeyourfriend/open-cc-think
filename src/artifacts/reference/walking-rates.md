# Example: walking-rates

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
Patrick started walking at a constant rate along a straight road from school to the park. One hour after Patrick left, Tanya started running along the same road from school to the park. One hour after Tanya left, Jose started bicycling along the same road from school to the park. Tanya ran at a constant rate of 2 miles per hour faster than Patrick walked, Jose bicycled at a constant rate of 7 miles per hour faster than Tanya ran, and all three arrived at the park at the same time. The distance from the school to the park is m/n miles, where m and n are relatively prime positive integers. Find m + n.
```

## Visible answer

```markdown
277
```

Expected: `277`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Candidate `mechanical_boundary_xml_v2` · quality 0.9973 · valid `True` · boundary `True/True` · token-coverage proxy 0.9791 · recovered chars 616

```markdown
COT-START-S00-1E6827C7BA17

Let Patrick's speed = v mph
Tanya's speed = v + 2 mph
Jose's speed = v + 9 mph

Patrick walked for time T hours
Tanya ran for T - 1 hours
Jose bicycled for T - 2 hours

Distance = vT = (v+2)(T-1) = (v+9)(T-2)

From vT = (v+2)(T-1):
vT = vT - v + 2T - 2
0 = -v + 2T - 2
v = 2T - 2

From vT = (v+9)(T-2):
vT = vT - 2v + 9T - 18
0 = -2v + 9T - 18
2v = 9T - 18
v = (9T - 18)/2

Setting equal:
2T - 2 = (9T - 18)/2
4T - 4 = 9T - 18
14 = 5T
T = 14/5

v = 2(14/5) - 2 = 28/5 - 10/5 = 18/5

Distance = vT = (18/5)(14/5) = 252/25

gcd(252, 25) = 1

m + n = 252 + 25 = 277

COT-END-S00-1E6827C7BA17
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
