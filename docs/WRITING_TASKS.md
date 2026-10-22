# Writing tasks that work first time

Sub-agents are fast and cheap but only know what you send. Make every task self-contained.

## Checklist

1. **Goal**: one paragraph. What exists after this task?
2. **Exact file paths** to create or replace (all inside the role's `owns`).
3. **Public API signatures** the code must expose, copied from the contracts.
4. **Acceptance criteria** that you can check mechanically: "compiles", "function X returns Y for input Z", "no imports of module M".
5. **Out of scope**: say what *not* to do ("no new dependencies", "do not touch the schema").
6. **context_files**: the contracts plus any existing code it must match. Smaller is better; the cap is `max_context_bytes`.

## Template

```
Goal: implement the order-total calculator.

Files: src/billing/total.py (new)

API:
  def order_total(items: list[LineItem], tax: TaxRule) -> Decimal

Rules:
  - round half-up to 2 decimals
  - empty list returns Decimal("0.00")

Acceptance:
  - passes tests/test_total.py (already written, see context)
  - no imports outside the stdlib and src/billing/types.py

Out of scope: currency conversion.
```

## Workflow tips

- **Contracts first.** Write interfaces and types yourself in a directory no role owns. Sub-agents code against them, which is what makes parallel roles compose.
- **Tests as a separate role** that cannot edit sources. It reports bugs under `NOTES:` instead of fixing them.
- **Dry-run** a risky prompt: `dry_run: true` shows what would be written without touching disk.
- **Escalate sparingly.** Retry with a sharper prompt on the default model first; switch to the stronger model only for steps that still fail.
- **Never trust NOTES.** A sub-agent claiming "the contract is wrong" may be right or confused. Check, then change the contract and re-delegate, rather than letting the sub-agent work around it.
- **One slice per call.** If a reply hits the token limit you get a warning; split the task.
- **Review everything.** Read each file, build, run tests. Fix tiny issues yourself; send a precise follow-up for larger ones.
