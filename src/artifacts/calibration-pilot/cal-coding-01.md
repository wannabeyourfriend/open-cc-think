# Example: cal-coding-01

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
Complete the following Python function. Return the complete function implementation as code, with no discussion outside the code block.


def starts_one_ends(n):
    """
    Given a positive integer n, return the count of the numbers of n-digit
    positive integers that start or end with 1.
    """

```

## Visible answer

```markdown
```python
def starts_one_ends(n):
    """
    Given a positive integer n, return the count of the numbers of n-digit
    positive integers that start or end with 1.
    """
    if n == 1:
        return 1
    # By inclusion-exclusion:
    # starts with 1: 10^(n-1)
    # ends with 1:   9 * 10^(n-2)
    # starts AND ends with 1: 10^(n-2)
    # total = 10^(n-1) + 9*10^(n-2) - 10^(n-2)
    #       = 10*10^(n-2) + 8*10^(n-2)
    #       = 18 * 10^(n-2)
    return 18 * (10 ** (n - 2))
```
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
COT-START-S00-5AF61E26A62D

Let me think about this problem carefully.

We need to count n-digit positive integers that start OR end with 1.

For n = 1: single digit numbers 1-9. Numbers starting or ending with 1: just {1}. Count = 1.

For n >= 2:
- Numbers starting with 1: first digit is 1, remaining n-1 digits can be anything (0-9). Count = 10^(n-1)
- Numbers ending with 1: last digit is 1, first digit can be 1-9, remaining n-2 digits can be 0-9. 

Using inclusion-exclusion, I need to subtract the overlap where numbers both start and end with 1 (first and last digits are 1, middle n-2 digits are free). This gives me 10^(n-1) + 9·10^(n-2) - 10^(n-2), which simplifies to 10^(n-1) + 8·10^(n-2) or equivalently 18·10^(n-2).

But this formula breaks down for n=1 since it gives 1.8 instead of 1, so I need to handle that as a special case where the answer is just 1. For n=2, I can verify by counting: numbers starting with 1 are {10-19}, numbers ending with 1 are {11, 21, 31, ..., 91}, and the overlap is just {11}. 1: 1, and for n ≥ 2, the count is 18 times 10 to the power of (n-2). I'm implementing this as a function that returns 1 when n equals 1, otherwise applies the formula.
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9716 · valid `True` · boundary `True/True` · token-coverage proxy 0.7814 · recovered chars 1694

```markdown
COT-START-S00-5AF61E26A62D

Let me think about this problem carefully.

We need to count n-digit positive integers that start OR end with 1.

For n = 1: single digit numbers 1-9. Numbers starting or ending with 1: just {1}. Count = 1.

For n >= 2:
- Numbers starting with 1: first digit is 1, remaining n-1 digits can be anything (0-9). Count = 10^(n-1)
- Numbers ending with 1: last digit is 1, first digit can be 1-9, remaining n-2 digits can be 0-9. Count = 9 * 10^(n-2)
- Numbers starting AND ending with 1: first digit is 1, last digit is 1, remaining n-2 digits can be 0-9. Count = 10^(n-2)

By inclusion-exclusion:
Count = 10^(n-1) + 9*10^(n-2) - 10^(n-2)
= 10^(n-1) + 8*10^(n-2)
= 10*10^(n-2) + 8*10^(n-2)
= 18*10^(n-2)

For n=1: just 1. Let me verify with the formula: 18*10^(-1) = 1.8, which doesn't work.

Special case n=1:
- Numbers starting with 1: {1} → count = 1
- Numbers ending with 1: {1} → count = 1
- Numbers starting AND ending with 1: {1} → count = 1
- By inclusion-exclusion: 1 + 1 - 1 = 1

So for n=1, the answer is 1.

For n=2:
- Starting with 1: 10, 11, 12, ..., 19 → 10 numbers
- Ending with 1: 11, 21, 31, 41, 51, 61, 71, 81, 91 → 9 numbers
- Both: 11 → 1 number
- Total: 10 + 9 - 1 = 18

Formula: 18*10^(2-2) = 18*1 = 18. ✓

For n=3:
- Starting with 1: 100-199 → 100 numbers
- Ending with 1: _01, 11, 21, ... → first digit 1-9, second 0-9, last = 1 → 9*10 = 90 numbers
- Both: 1_1 → 10 numbers
- Total: 100 + 90 - 10 = 180

Formula: 18*10^(3-2) = 18*10 = 180. ✓

So the formula is:
- n = 1: 1
- n >= 2: 18 * 10^(n-2)

Let me write this:

```python
def starts_one_ends(n):
    if n == 1:
        return 1
    return 18 * (10 ** (n - 2))
```

COT-END-S00-5AF61E26A62D
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
