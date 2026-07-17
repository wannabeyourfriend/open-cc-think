# Example: gather-math-03-r01

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

### Decision step 0

Provider CoT summary:

```markdown
I'm looking at the values here: A is 28, B is 40, C is 80, which add up to 148 total.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9300 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 3.9000 · summary-token expansion `0.3636` · summary n-gram containment 0.0000 · recovered chars 79

```markdown
COT-START-S00-27F6581C58CF
A=28, B=40, C=80, total=148
COT-END-S00-27F6581C58CF
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
