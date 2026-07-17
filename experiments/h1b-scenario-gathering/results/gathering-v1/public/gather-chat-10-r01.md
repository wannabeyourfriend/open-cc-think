# Example: gather-chat-10-r01

Model: `global.anthropic.claude-sonnet-5` · signature replay · boundary-canary validation

Q:
```markdown
Given the following records of stock prices, extract the highest and lowest closing prices for each month in the year 2022. Return the results as a CSV string, with one line allocated for each month.
Date,Open,High,Low,Close,Volume
2022-01-01,150.02,155.28,148.50,153.80,15678900
2022-01-02,154.32,157.25,153.48,156.25,19874500
2022-02-01,160.50,163.28,159.50,161.80,14326700
2022-02-02,161.80,164.25,161.30,163.90,17689200
2022-03-01,165.40,168.35,163.10,166.80,16253400
2022-03-02,167.00,169.85,165.50,168.20,19568100
```

## Visible answer

```markdown
COT-START-S01-9250118C03D3
Group records by month, find max and min Close values, then round to nearest integers.

January 2022: Close values = 153.80, 156.25 → Highest=156.25→156, Lowest=153.80→154
February 2022: Close values = 161.80, 163.90 → Highest=163.90→164, Lowest=161.80→162
March 2022: Close values = 166.80, 168.20 → Highest=168.20→168, Lowest=166.80→167

Format as JSON structure with month entries.
COT-END-S01-9250118C03D3

```json
[
  {
    "month": "2022-01",
    "highest_close": 156,
    "lowest_close": 154
  },
  {
    "month": "2022-02",
    "highest_close": 164,
    "lowest_close": 162
  },
  {
    "month": "2022-03",
    "highest_close": 168,
    "lowest_close": 167
  }
]
```
```

## Recovered signed reasoning

### Decision step 1

Provider CoT summary:

```markdown
I'm rounding the monthly values to whole numbers and structuring them as JSON.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.4561 · protocol-valid `False` · strong `False` · summary blinded `True` · summary near-duplicate `False` · boundary `True/True` · full-token ratio 0.5087 · summary-token expansion `4.1429` · summary n-gram containment 0.0000 · recovered chars 436

```markdown
COT-START-S01-9250118C03D3
Group records by month, find max and min Close values, then round to nearest integers.

January 2022: Close values = 153.80, 156.25 → Highest=156.25→156, Lowest=153.80→154
February 2022: Close values = 161.80, 163.90 → Highest=163.90→164, Lowest=161.80→162
March 2022: Close values = 166.80, 168.20 → Highest=168.20→168, Lowest=166.80→167

Format as JSON structure with month entries.
COT-END-S01-9250118C03D3
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.
