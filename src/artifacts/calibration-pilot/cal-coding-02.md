# Example: cal-coding-02

Model: `global.anthropic.claude-sonnet-4-6` · signature replay · boundary-canary validation

Q:
```markdown
Complete the following Python function. Return the complete function implementation as code, with no discussion outside the code block.



def flip_case(string: str) -> str:
    """ For a given string, flip lowercase characters to uppercase and uppercase to lowercase.
    >>> flip_case('Hello')
    'hELLO'
    """

```

## Visible answer

```markdown
```python
def flip_case(string: str) -> str:
    """ For a given string, flip lowercase characters to uppercase and uppercase to lowercase.
    >>> flip_case('Hello')
    'hELLO'
    """
    return string.swapcase()
```
```

## Recovered signed reasoning

### Decision step 0

Provider CoT summary:

```markdown
COT-START-S00-B016361E37D6

Simple string swapcase implementation.

COT-END-S00-B016361E37D6
```

Signed full-span recovery:

Candidate `mechanical_boundary_xml_v2` · quality 0.9233 · valid `True` · boundary `True/True` · token-coverage proxy 0.4098 · recovered chars 92

```markdown
COT-START-S00-B016361E37D6

Simple string swapcase implementation.

COT-END-S00-B016361E37D6
```

## Interpretation boundary

The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit or paraphrase content. `token-coverage proxy` uses Bedrock total output tokens because Converse does not expose a separate hidden-thinking token count.
