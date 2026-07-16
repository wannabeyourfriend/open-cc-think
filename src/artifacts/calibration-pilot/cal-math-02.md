# Example: cal-math-02

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
John assembles computers and sells prebuilt computers as a business. The parts for the computer cost $800.  He sells the computers for 1.4 times the value of the components.  He manages to build 60 computers a month.  He has to pay $5000 a month in rent and another $3000 in non-rent extra expenses a month.  How much profit does he make a month?
```

## Visible answer

```markdown
$11200
```

Expected: `11200`

Task success: `True`

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
COT-START-S00-646BDB3E23D9

Parts cost: $800 per computer
Selling price: $800 × 1.4 = $1120 per computer
Computers per month: 60

Revenue: 60 × $1120 = $67,200
Cost of parts: 60 × $800 = $48,000
Rent: $5,000
Other expenses: $3,000

Total expenses: $48,000 + $5,000 + $3,000 = $56,000

Profit: $67,200 - $56,000 = $11,200

COT-END-S00-646BDB3E23D9
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9930 · valid `True` · boundary `True/True` · token-coverage proxy 0.9465 · recovered chars 346

```markdown
COT-START-S00-646BDB3E23D9

Parts cost: $800 per computer
Selling price: $800 × 1.4 = $1120 per computer
Computers per month: 60

Revenue: 60 × $1120 = $67,200
Cost of parts: 60 × $800 = $48,000
Rent: $5,000
Other expenses: $3,000

Total expenses: $48,000 + $5,000 + $3,000 = $56,000

Profit: $67,200 - $56,000 = $11,200

COT-END-S00-646BDB3E23D9
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
