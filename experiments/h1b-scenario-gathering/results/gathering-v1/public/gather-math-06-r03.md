# Example: gather-math-06-r03

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
So across the first four rounds he watches 15 videos each time and dislikes all of them, totaling 60 videos. Then in the fifth round he picks the fifth video and watches videos 1 through 5, adding 5 more, which brings the total to 65.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.6119 · summary-token expansion `0.5333` · summary n-gram containment 0.0000 · recovered chars 180

```markdown
COT-START-S00-45277AFE9DBA
First 4 rounds: 15 videos each watched (all disliked) = 4*15=60
5th round: he picks 5th video, watches videos 1-5 = 5
Total = 65
COT-END-S00-45277AFE9DBA
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
