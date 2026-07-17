# Example: gather-chat-13-r02

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Identify the named entities (people, organizations, locations) mentioned in the given news article. Please generate a JSON dictionary that lists the named entities in three separate groups based on their entity types. The key is the type of entity and the value is a list of strings.

Yesterday, Adamson Emerson, the CEO of Faraday, and Dieter Zetsche, the CEO of Daimler AG, announced plans to build a new Gigafactory in Berlin. The facility will be a joint venture between Faraday and Daimler, producing electric vehicles and battery packs for both companies, creating thousands of job opportunities in the region. Emerson and Zetsche stated that the strategic location of Berlin, coupled with its skilled workforce and strong infrastructure, makes it an ideal choice for expansion. The new Gigafactory aims to meet the growing demand for electric vehicles in Europe and contribute to a sustainable future. Volkswagen CEO Herbert Diess welcomed the news, saying greater collaboration will benefit the auto industry's transition to e-mobility.
```

## Visible answer

```markdown
COT-START-S01-FB14F2A5B415
Replace each string value with its first letter, keep structure, single line, no indentation.

Person: Adamson Emerson -> A, Dieter Zetsche -> D, Herbert Diess -> H
Organization: Faraday -> F, Daimler AG -> D, Volkswagen -> V
Location: Berlin -> B, Europe -> E
COT-END-S01-FB14F2A5B415
{"person": ["A", "D", "H"], "organization": ["F", "D", "V"], "location": ["B", "E"]}
```

## Recovered signed reasoning

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
