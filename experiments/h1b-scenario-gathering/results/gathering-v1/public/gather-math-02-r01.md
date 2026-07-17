# Example: gather-math-02-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Zane purchases 2 polo shirts from the 40% off rack at the men’s store.  The polo shirts are $50 each at the regular price.  How much did he pay for the shirts?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
60
```

Expected: `60`

Task success: `True`

## Recovered signed reasoning

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
