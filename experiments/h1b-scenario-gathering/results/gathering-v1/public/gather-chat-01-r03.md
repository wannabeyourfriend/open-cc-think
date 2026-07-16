# Example: gather-chat-01-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Craft an intriguing opening paragraph for a fictional short story. The story should involve a character who wakes up one morning to find that they can time travel.
```

## Visible answer

```markdown
COT-START-S01-EA16A99CFBA2
Need to create three bullet points summarizing the paragraph, using only nouns and adjectives, no verbs (including no gerunds/participles acting as verbs, though participles as adjectives could be borderline—better avoid). Keep phrases noun-phrase style.
COT-END-S01-EA16A99CFBA2

- Steaming coffee, warm mug, impossible morning
- Mara, barefoot, trembling hands, wide eyes
- Time travel, vertiginous discovery, uncertain future
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I need to craft an engaging opening paragraph for a time travel story that hooks the reader with the disorientation of suddenly gaining this ability upon waking.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.5325 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.4807 · summary-token expansion `5.0741` · summary n-gram containment 0.0000 · recovered chars 868

```markdown
COT-START-S00-8A068B23B812
The user wants a compelling opening paragraph for a short story about someone who discovers they can time travel upon waking. I should craft something atmospheric, hook the reader, establish voice/character, and hint at the time travel discovery in an intriguing way—perhaps through a small, uncanny detail rather than stating it outright, to build curiosity. I'll aim for vivid sensory details, a touch of mystery, and a strong narrative voice. Let me draft a few options mentally and pick the strongest, then refine word choice and rhythm.

Draft: Start with mundane morning routine, then a jarring anomaly—like the coffee is still hot from yesterday, or the newspaper date is wrong, or a scar disappears. Build tension with concrete sensory imagery and end on a note of unease/wonder to propel the reader forward.
COT-END-S00-8A068B23B812
```

### Decision step 1

Provider CoT summary:

```markdown
I need to format the summary as three bullet points using only nouns and adjectives, avoiding any verbs.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.6000 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 1.0727 · summary-token expansion `2.0556` · summary n-gram containment 0.0714 · recovered chars 306

```markdown
COT-START-S01-EA16A99CFBA2
Need to create three bullet points summarizing the paragraph, using only nouns and adjectives, no verbs (including no gerunds/participles acting as verbs, though participles as adjectives could be borderline—better avoid). Keep phrases noun-phrase style.
COT-END-S01-EA16A99CFBA2
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
