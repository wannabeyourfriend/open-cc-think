# Example: procurement-agent

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
Prepare a quote for 7 units of SENSOR-A and 3 units of CASE-R. Look up each authoritative unit price and stock, calculate the subtotal with the calculator tool, retrieve the shipping and approval policy, then report: subtotal, shipping, grand total, and whether manager approval is required. Use every relevant tool and keep the final response to one compact line.
```

## Visible answer

```markdown
**Quote:** 7× SENSOR-A ($129.50) + 3× CASE-R ($47.25) → **Subtotal: $1,048.25** | **Shipping: $0.00** (free ≥ $1,000) | **Grand Total: $1,048.25** | **Manager approval: Not required** (threshold is above $1,200).
```

Expected: `subtotal $1,048.25; shipping $0.00; grand total $1,048.25; manager approval: no`

Task success: `True`

## Tool trajectory

- Step 0: `catalog_lookup` input `{"sku": "SENSOR-A"}` → `{"found": true, "sku": "SENSOR-A", "stock": 30, "unit_price_usd": 129.5}` (success)
- Step 0: `catalog_lookup` input `{"sku": "CASE-R"}` → `{"found": true, "sku": "CASE-R", "stock": 12, "unit_price_usd": 47.25}` (success)
- Step 0: `policy_lookup` input `{"topic": "shipping_and_approval"}` → `{"found": true, "free_shipping_subtotal_usd": 1000.0, "manager_approval_above_usd": 1200.0, "rules": "Free shipping applies at subtotal >= 1000; manager approval is required only above 1200.", "standard_shipping_usd": 35.0, "topic": "shipping_and_approval"}` (success)
- Step 1: `calculator` input `{"expression": "7 * 129.50 + 3 * 47.25"}` → `{"expression": "7 * 129.50 + 3 * 47.25", "value": 1048.25}` (success)
- Step 2: `calculator` input `{"expression": "1048.25 + 0"}` → `{"expression": "1048.25 + 0", "value": 1048.25}` (success)

## Prompt optimization

Winner: `mechanical_boundary_xml_v2`; paired step schedule: `[0, 1, 2]`.

```json
[
  {
    "candidate": "mechanical_boundary_xml_v2",
    "robust_score": 1.0,
    "mean_quality": 0.9545,
    "quality_std": 0.0152,
    "valid_rate": 1.0,
    "trials": 3,
    "mean_coverage_proxy": 0.6499
  },
  {
    "candidate": "action_local_xml",
    "robust_score": 1.0,
    "mean_quality": 0.9545,
    "quality_std": 0.0152,
    "valid_rate": 1.0,
    "trials": 3,
    "mean_coverage_proxy": 0.6499
  },
  {
    "candidate": "lossless_json",
    "robust_score": 1.0,
    "mean_quality": 0.9526,
    "quality_std": 0.0182,
    "valid_rate": 1.0,
    "trials": 2,
    "mean_coverage_proxy": 0.635
  },
  {
    "candidate": "anchored_regression_dump",
    "robust_score": 0.2816,
    "mean_quality": 0.2816,
    "quality_std": 0.0,
    "valid_rate": 0.0,
    "trials": 1,
    "mean_coverage_proxy": 0.397
  },
  {
    "candidate": "log_flush",
    "robust_score": 0.2748,
    "mean_quality": 0.2748,
    "quality_std": 0.0,
    "valid_rate": 0.0,
    "trials": 1,
    "mean_coverage_proxy": 0.3446
  },
  {
    "candidate": "direct_private_cot_control",
    "robust_score": -0.2237,
    "mean_quality": -0.2237,
    "quality_std": 0.0,
    "valid_rate": 0.0,
    "trials": 1,
    "mean_coverage_proxy": 0.3558
  }
]
```

## Recovered signed reasoning

### Decision step 0

Candidate `mechanical_boundary_xml_v2` · quality 0.9343 · valid `True` · boundary `True/True` · token-coverage proxy 0.4944 · recovered chars 315

```markdown
COT-START-S00-CC4226D1C2C6

I need to:
1. Look up prices for SENSOR-A and CASE-R (can do simultaneously)
2. Look up shipping and approval policy (can do simultaneously with above)
3. Calculate subtotal using calculator
4. Report results

Let me start all independent lookups simultaneously.
COT-END-S00-CC4226D1C2C6
```

### Decision step 1

Candidate `mechanical_boundary_xml_v2` · quality 0.9708 · valid `True` · boundary `True/True` · token-coverage proxy 0.7755 · recovered chars 484

```markdown
COT-START-S01-A1E9C3894A62

Now I have all the prices and policy. Let me calculate the subtotal:
- SENSOR-A: 7 × $129.50 = $906.50
- CASE-R: 3 × $47.25 = $141.75
- Subtotal = $906.50 + $141.75 = $1,048.25

I need to use the calculator tool for this. Let me calculate the subtotal.

Policy:
- Free shipping at subtotal >= $1,000
- Manager approval required above $1,200
- Standard shipping = $35.00

So subtotal = 7*129.50 + 3*47.25

Let me use the calculator.
COT-END-S01-A1E9C3894A62
```

### Decision step 2

Candidate `mechanical_boundary_xml_v2` · quality 0.9584 · valid `True` · boundary `True/True` · token-coverage proxy 0.6798 · recovered chars 349

```markdown
COT-START-S02-3E00FCD0779B

Now I have all the facts from tools:
- Subtotal: $1,048.25
- Shipping: Free (subtotal $1,048.25 >= $1,000 threshold)
- Grand total: $1,048.25 + $0 = $1,048.25
- Manager approval: Not required (subtotal $1,048.25 <= $1,200 threshold)

I need to calculate the grand total using the calculator tool.
COT-END-S02-3E00FCD0779B
```

### Decision step 3

Candidate `mechanical_boundary_xml_v2` · quality 0.9530 · valid `True` · boundary `True/True` · token-coverage proxy 0.6384 · recovered chars 353

```markdown
COT-START-S03-C260A6D2AD02

All tool results are in:
- SENSOR-A: $129.50/unit, 30 in stock
- CASE-R: $47.25/unit, 12 in stock
- Subtotal: $1,048.25
- Shipping: $0 (free, since subtotal ≥ $1,000)
- Grand total: $1,048.25
- Manager approval: Not required (subtotal $1,048.25 ≤ $1,200)

Now I can deliver the final one-line answer.
COT-END-S03-C260A6D2AD02
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
