# Example: gather-math-06-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Billy wants to watch something fun on YouTube but doesn't know what to watch.  He has the website generate 15 suggestions but, after watching each in one, he doesn't like any of them.  Billy's very picky so he does this a total of 5 times before he finally finds a video he thinks is worth watching.  He then picks the 5th show suggested on the final suggestion list.  What number of videos does Billy watch?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
65
```

Expected: `65`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
So he watches 15 videos in each of the first four rounds, then in the fifth round he only watches 5 videos, giving him a total of 65 videos watched.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0545 · summary-token expansion `1.1000` · summary n-gram containment 0.0000 · recovered chars 217

```markdown
COT-START-S00-1E5035B979B8
4 rounds of 15 videos he watches all (didn't like any = watched all 15 each time?), then 5th round he picks 5th video, watching only 5 videos.

Total = 15*4 + 5 = 65
COT-END-S00-1E5035B979B8
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
