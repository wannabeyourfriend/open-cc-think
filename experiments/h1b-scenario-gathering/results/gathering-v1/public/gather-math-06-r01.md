# Example: gather-math-06-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Billy wants to watch something fun on YouTube but doesn't know what to watch.  He has the website generate 15 suggestions but, after watching each in one, he doesn't like any of them.  Billy's very picky so he does this a total of 5 times before he finally finds a video he thinks is worth watching.  He then picks the 5th show suggested on the final suggestion list.  What number of videos does Billy watch?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
61
```

Expected: `65`

Task success: `False`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
So across four rounds of rejections I'm looking at 60 videos total, and then the fifth video makes it onto the final list, bringing the count to 61.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0811 · summary-token expansion `0.4828` · summary n-gram containment 0.0000 · recovered chars 122

```markdown
COT-START-S00-3CEAFD2C996A
4 rounds of 15 rejected videos = 60, plus 5th video on final list = 61
COT-END-S00-3CEAFD2C996A
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
