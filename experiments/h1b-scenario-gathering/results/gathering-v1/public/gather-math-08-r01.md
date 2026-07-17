# Example: gather-math-08-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Tabitha and her friends were excited to go to the Christmas parade because they knew candy would be thrown to the crowd from the floats.  Tabitha caught 22 pieces of candy.  Stan caught 13 pieces.  Julie caught half the amount of candy as Tabitha caught and Carlos caught twice as much candy as Stan.  How many pieces in total did the friends catch?

Return only the final numeric answer in the visible response.
```

## Visible answer

```markdown
72
```

Expected: `72`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm adding up the ages: Tabitha is 22, Stan is 13, Julie is 11, and Carlos is 26, which gives me a total of 72.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 1.0000 · protocol-valid `True` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 2.0233 · summary-token expansion `0.5385` · summary n-gram containment 0.0000 · recovered chars 113

```markdown
COT-START-S00-EE7336E2A96A
Tabitha=22, Stan=13, Julie=11, Carlos=26
Total=22+13+11+26=72
COT-END-S00-EE7336E2A96A
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
