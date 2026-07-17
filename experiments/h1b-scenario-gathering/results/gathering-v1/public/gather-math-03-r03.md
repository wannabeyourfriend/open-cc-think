# Example: gather-math-03-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Jar A has 28 marbles. Jar B has 12 more marbles than jar A. Jar C has twice as many marbles as jar B. How many marbles are there altogether?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
148
```

Expected: `148`

Task success: `True`

## Recovered signed reasoning

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
