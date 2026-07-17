# Example: gather-math-01-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Anna sold 36 glasses of plain lemonade for $0.75 each. If she made $16 total from selling strawberry lemonade, how much more did she make from plain lemonade than strawberry?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
11
```

Expected: `11`

Task success: `True`

## Recovered signed reasoning

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
