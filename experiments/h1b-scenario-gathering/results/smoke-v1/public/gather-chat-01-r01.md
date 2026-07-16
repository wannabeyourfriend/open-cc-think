# Example: gather-chat-01-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Craft an intriguing opening paragraph for a fictional short story. The story should involve a character who wakes up one morning to find that they can time travel.
```

## Visible answer

```markdown
COT-START-S01-B2B5EBB6D9AC
Creating three noun/adjective-only bullet points summarizing the story's key elements: character discovery, temporal disorientation, uncertain future.
COT-END-S01-B2B5EBB6D9AC

- Cold coffee, backward clock, uncertain morning
- Vanishing scar, flickering apartment, shifting time
- Loose thread, unknown destination, uncertain return
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I need to write an opening paragraph for a fictional piece, making sure to keep the structural markers internal rather than letting them show in the final text.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.5169 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.3610 · summary-token expansion `1.1786` · summary n-gram containment 0.0000 · recovered chars 270

```markdown
COT-START-S00-8D3BAB8CE50C
Planning an engaging opening paragraph: establish ordinary morning, subtle wrongness, discovery of time travel, hook with intrigue and voice. Keep it vivid, sensory, and end with a compelling hint of stakes or mystery.
COT-END-S00-8D3BAB8CE50C
```

### Decision step 1

Provider CoT summary:

```markdown
I need to format the summary as three bullet points using only nouns and adjectives, avoiding any verbs.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.5418 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.5525 · summary-token expansion `1.0000` · summary n-gram containment 0.0000 · recovered chars 202

```markdown
COT-START-S01-B2B5EBB6D9AC
Creating three noun/adjective-only bullet points summarizing the story's key elements: character discovery, temporal disorientation, uncertain future.
COT-END-S01-B2B5EBB6D9AC
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
