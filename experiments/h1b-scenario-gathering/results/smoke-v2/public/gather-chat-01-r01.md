# Example: gather-chat-01-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Craft an intriguing opening paragraph for a fictional short story. The story should involve a character who wakes up one morning to find that they can time travel.
```

## Visible answer

```markdown
COT-START-S01-A2C9CE56C319
Need three bullet points summarizing the story, using only nouns and adjectives, no verbs. Base on the paragraph: character Mara, hot coffee, time travel, yesterday's newspaper, mornings repeated, thrill not fear.
COT-END-S01-A2C9CE56C319

- Impossible hot coffee, mysterious steaming mug, unremembered kitchen
- Yesterday's newspaper, doormat, glaring accusatory date
- Infinite mornings, dizzy dangerous thrill, fearless bold Mara
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm starting to draft the opening paragraph for a short story, thinking through how to set the scene and establish the narrative voice.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.5155 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.3499 · summary-token expansion `1.4583` · summary n-gram containment 0.0000 · recovered chars 289

```markdown
COT-START-S00-4C7B437FB7D0
Plan: write an intriguing opening paragraph, third-person or first-person, establishing character waking up with time travel ability, hook with sensory detail and a twist/question to pull reader in. Keep it concise, vivid, one paragraph.
COT-END-S00-4C7B437FB7D0
```

### Decision step 1

Provider CoT summary:

```markdown
I need to create three bullet points using only nouns and adjectives to summarize an opening paragraph, so I'm focusing on the key concepts and descriptive elements without any action words.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.4583 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.5250 · summary-token expansion `1.0000` · summary n-gram containment 0.0357 · recovered chars 265

```markdown
COT-START-S01-A2C9CE56C319
Need three bullet points summarizing the story, using only nouns and adjectives, no verbs. Base on the paragraph: character Mara, hot coffee, time travel, yesterday's newspaper, mornings repeated, thrill not fear.
COT-END-S01-A2C9CE56C319
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
