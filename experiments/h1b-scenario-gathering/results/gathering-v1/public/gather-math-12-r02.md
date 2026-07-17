# Example: gather-math-12-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Tom decided to go on a trip. During this trip, he needs to cross a lake, which in one direction takes 4 hours. During this time, Tom needs an assistant to help him with the crossing. Hiring an assistant costs $10 per hour. How much would Tom have to pay for help with crossing the lake back and forth?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
COT-START-S00-7BCB507FC9D8
Crossing takes 4 hours one way, back and forth = 8 hours total.
Cost = 8 hours × $10/hour = $80
COT-END-S00-7BCB507FC9D8
80
```

Expected: `80`

Task success: `True`

## Recovered signed reasoning

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
