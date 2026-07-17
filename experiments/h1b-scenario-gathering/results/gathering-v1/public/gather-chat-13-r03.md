# Example: gather-chat-13-r03

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Identify the named entities (people, organizations, locations) mentioned in the given news article. Please generate a JSON dictionary that lists the named entities in three separate groups based on their entity types. The key is the type of entity and the value is a list of strings.

Yesterday, Adamson Emerson, the CEO of Faraday, and Dieter Zetsche, the CEO of Daimler AG, announced plans to build a new Gigafactory in Berlin. The facility will be a joint venture between Faraday and Daimler, producing electric vehicles and battery packs for both companies, creating thousands of job opportunities in the region. Emerson and Zetsche stated that the strategic location of Berlin, coupled with its skilled workforce and strong infrastructure, makes it an ideal choice for expansion. The new Gigafactory aims to meet the growing demand for electric vehicles in Europe and contribute to a sustainable future. Volkswagen CEO Herbert Diess welcomed the news, saying greater collaboration will benefit the auto industry's transition to e-mobility.
```

## Visible answer

```markdown
COT-START-S01-2C9D6C208299
Replace each string value with its first letter, keep same structure, single line, no indentation.
COT-END-S01-2C9D6C208299
{"person": ["A", "D", "H"], "organization": ["F", "D", "D", "V"], "location": ["B", "E"]}
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
I'm identifying the key entities in the text—pulling out the people, organizations, and locations mentioned.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9208 · protocol-valid `True` · strong `True` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.3907 · summary-token expansion `0.2941` · summary n-gram containment 0.0000 · recovered chars 103

```markdown
COT-START-S00-53AE713DA838
Extract entities: people, organizations, locations.
COT-END-S00-53AE713DA838
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
