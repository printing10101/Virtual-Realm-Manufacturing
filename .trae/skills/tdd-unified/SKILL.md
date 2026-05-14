---
name: "tdd-unified"
description: "Test-Driven Development with Red-Green-Refactor cycle. Invoke when implementing features, fixing bugs, writing tests, or before writing implementation code."
---

# TDD Unified

Test-Driven Development (TDD) skill combining best practices from multiple TDD approaches. Write the test first, watch it fail, write minimal code to pass, refactor.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

## When to Use

**Always:**
- New features
- Bug fixes (write test reproducing bug first)
- Refactoring
- Behavior changes
- Complex algorithms
- API design

**Exceptions (ask user):**
- Throwaway prototypes
- Generated code
- Configuration files
- Exploratory programming
- Simple CRUD (weigh tradeoffs)

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

**No exceptions:**
- Don't keep as "reference"
- Don't "adapt" it while writing tests
- Delete means delete
- Implement fresh from tests

## Core Cycle: Red-Green-Refactor

### 1. RED - Write Failing Test

**Goal:** Write one test describing expected behavior that should fail.

**Principles:**
- Test first, implementation after
- Test must clearly express expected behavior
- Write only minimal code to make test compile
- Test should be concise, readable, descriptive

**Requirements:**
- One behavior per test
- Clear name describing behavior
- Real code (no mocks unless unavoidable)
- AAA pattern: Arrange-Act-Assert

**Example:**
```python
def test_addition_of_two_numbers():
    # Arrange
    calc = Calculator()
    
    # Act
    result = calc.add(2, 3)
    
    # Assert
    assert result == 5
```

### 2. Verify RED - Watch It Fail

**MANDATORY. Never skip.**

```bash
pytest tests/path/test.py -v
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes?** You're testing existing behavior. Fix test.
**Test errors?** Fix error, re-run until it fails correctly.

### 3. GREEN - Minimal Code

**Goal:** Write simplest code to pass the test.

**Principles:**
- Any code that makes test pass is valid
- Don't over-engineer or add extra features
- Focus on passing current test only
- Keep code concise

**Example:**
```python
def add(self, a, b):
    return a + b  # Real implementation
```

Don't add features, refactor other code, or "improve" beyond the test.

### 4. Verify GREEN - Watch It Pass

**MANDATORY.**

```bash
pytest tests/path/test.py -v
```

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.
**Other tests fail?** Fix now.

### 5. REFACTOR - Clean Up

**Goal:** Improve code design, eliminate duplication, keep functionality.

**Principles:**
- Improve internal structure, don't change external behavior
- Eliminate duplicate code
- Improve readability and maintainability
- Keep all tests passing

**Example:**
```python
def add(self, a, b):
    return a + b  # Clean, real implementation
```

### Repeat

Next failing test for next feature. Small steps, rapid feedback.

## TDD Golden Rules

1. **Small steps**: One small change at a time
2. **Test first**: Always let tests guide development
3. **Rapid feedback**: Tests must run fast
4. **Continuous refactoring**: Keep code clean
5. **Avoid over-engineering**: Only implement what's needed now

## Good Tests (F.I.R.S.T.)

- **Fast**: Tests execute quickly
- **Independent**: Tests don't depend on each other
- **Repeatable**: Results are consistent
- **Self-Validating**: Tests auto-determine pass/fail
- **Timely**: Written before implementation

## Anti-Patterns - Red Flags

**STOP and start over when:**
- Code before test
- Test after implementation
- Test passes immediately
- Can't explain why test failed
- Tests added "later"
- Rationalizing "just this once"
- "I already manually tested it"
- "Tests after achieve same purpose"
- "Keep as reference" or "adapt existing code"

**All of these mean: Delete code. Start over with TDD.**

## Common Rationalizations vs Reality

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is technical debt. |
| "TDD is dogmatic" | TDD IS pragmatic: catches bugs early, prevents regressions. |
| "Tests after achieve same goals" | Tests-after = "what does this do?" Tests-first = "what should this do?" |

## Bug Fix Workflow

Bug found? Write failing test reproducing it. Follow TDD cycle. Test proves fix and prevents regression.

**Never fix bugs without a test.**

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered

**Can't check all boxes? You skipped TDD. Start over.**

## When Stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write wished-for API. Write assertion first. Ask user. |
| Test too complicated | Design too complicated. Simplify interface. |
| Must mock everything | Code too coupled. Use dependency injection. |
| Test setup huge | Extract helpers. Still complex? Simplify design. |
