# Example: gather-chat-02-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Edit the following paragraph to correct any grammatical errors:
She didn't remembre where is her purse, so I thinks its in the car but he's say it's on kitchen table but he are not sure, and then they asked me to looking for it, she's say, "Can you?", and I responds with, "Maybe, but ain't no sure," and he not heard me, and, "What?", he asks, "Did you found it?".
```

## Visible answer

```markdown
COT-START-S01-F669DBD04D04
COT-END-S01-F669DBD04D04

They didn't remember where their purse was, so I thought it was in the car, but the other person said it was on the kitchen table, though they weren't sure. Then they asked me to look for it. They said, "Can you?" and I responded, "Maybe, but I'm not sure." The other person didn't hear me, so they asked, "What? Did you find it?"
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm working through a paragraph with multiple grammar issues—fixing verb tenses, subject-verb agreement, pronoun consistency, and awkward phrasing to make it flow naturally and be grammatically correct.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.4212 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.1633 · summary-token expansion `0.0000` · summary n-gram containment 0.0000 · recovered chars 51

```markdown
COT-START-S00-952AE09CBEF0
COT-END-S00-952AE09CBEF0
```

### Decision step 1

Provider CoT summary:

```markdown
I need to replace gendered pronouns with gender-neutral alternatives, but since there are multiple people involved, I have to be careful about ambiguity when using "they" for everyone. I could use names or labels like "Person A" and "Person B" to keep things clear and distinct.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.4100 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.0768 · summary-token expansion `0.0000` · summary n-gram containment 0.0000 · recovered chars 51

```markdown
COT-START-S01-F669DBD04D04
COT-END-S01-F669DBD04D04
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
