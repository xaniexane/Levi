---
skill_id: web_sec_input_validation
name: Input Validation
description: Validate every input at the trust boundary: allowlists, types, lengths, and rejecting the unexpected.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web]
version: 1.0.0
---
# Input Validation
## Purpose
Treat all client input as untrusted and reject what does not fit before it touches business logic.
## Key ideas
- Validate on the server; client-side checks are UX, not security, and attackers bypass them freely.
- Prefer allowlists (known-good patterns) over denylists (known-bad signatures attackers mutate around).
- Check type, length, range, and format together; each dimension catches a different class of abuse.
- Reject or sanitize unexpected fields rather than silently ignoring them; silent acceptance hides attacks.
- Centralize validation in one layer so every endpoint gets the same rigor without copy-paste drift.

## In practice
Define the contract for each input once: what type, what range, what length, what pattern, and validate at the boundary before any business logic runs. Use well-tested validation libraries rather than hand-rolled regexes for emails, URLs, and other structured formats; the edge cases are where hand-rolled checks fail. When input is invalid, return a clear 400 naming the problem field; vague errors frustrate legitimate users while telling attackers nothing useful either way. Log validation failures at warn level with the field name (not the value, which may be an attack payload you do not want stored) to spot probing patterns early.

```python
from pydantic import BaseModel, Field, field_validator

class OrderIn(BaseModel):
    item: str = Field(min_length=1, max_length=80)
    qty: int = Field(ge=1, le=99)
    ship: str = Field(pattern="^(standard|express)$")

    @field_validator("item")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        if any(ord(c) < 32 for c in v):
            raise ValueError("control characters not allowed")
        return v.strip()
```

## Common mistakes
- Validating only in the browser and trusting whatever arrives at the server.
- Writing denylists of bad strings that attackers evade with trivial mutations.
- Logging raw rejected input, storing attack payloads in the log system.

## Checklist
- Is every input validated server-side against an explicit contract?
- Are allowlists preferred over denylists for formats and values?
- Do validation failures log the field, not the payload?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
