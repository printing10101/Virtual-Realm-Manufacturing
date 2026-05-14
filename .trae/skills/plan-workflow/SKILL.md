---
name: "plan-workflow"
description: "Write and execute implementation plans. Invoke when you have specs/requirements for multi-step tasks (writing phase) or when ready to execute a written plan with review checkpoints (execution phase)."
---

# Plan Workflow

Complete planning and execution skill combining plan writing and plan execution workflows. Provides end-to-end support from requirements to implementation.

## Phase 1: Writing Plans

### When to Use
- Have spec or requirements for multi-step task
- Before touching code
- Need to decompose complex work into bite-sized tasks

### Plan Structure

**Header (REQUIRED):**
```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use plan-workflow execution phase to implement this plan task-by-task.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

### Task Structure

Each task should be 2-5 minutes of work:

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**
```

### File Structure Guidelines
- Design units with clear responsibility boundaries
- Prefer smaller, focused files over large ones
- Files that change together should live together
- Split by responsibility, not by technical layer
- Follow existing codebase patterns

### No Placeholders
NEVER write:
- "TBD", "TODO", "implement later"
- "Add appropriate error handling"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code)

### Self-Review Checklist
1. **Spec coverage**: Each requirement has a task
2. **Placeholder scan**: No TBD/TODO patterns
3. **Type consistency**: Signatures match across tasks

## Phase 2: Executing Plans

### When to Use
- Have written implementation plan
- Ready to execute in separate session
- Need review checkpoints

### Execution Process

**Step 1: Load and Review**
1. Read plan file
2. Review critically
3. Raise concerns before starting
4. Create TodoWrite and proceed

**Step 2: Execute Tasks**
For each task:
1. Mark as in_progress
2. Follow each step exactly
3. Run verifications as specified
4. Mark as completed

**Step 3: Complete Development**
After all tasks complete and verified:
- Run final tests
- Commit all changes
- Announce completion

### When to Stop and Ask
**STOP immediately when:**
- Hit a blocker (missing dependency, test fails)
- Plan has critical gaps
- Don't understand instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

### When to Revisit Earlier Steps
**Return to Review when:**
- Partner updates the plan
- Fundamental approach needs rethinking

**Don't force through blockers** - stop and ask.

## Execution Options

After writing plan, offer two execution paths:

**1. Direct Execution (this skill)** - Execute tasks in current session with checkpoints

**2. Subagent-Driven** - Dispatch fresh subagent per task, review between tasks

## Remember
- Exact file paths always
- Complete code in every step
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits
- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Stop when blocked, don't guess
- Never start implementation on main/master without explicit consent

## Integration

**Workflow phases:**
1. **Writing Plans** - Create implementation plan
2. **Executing Plans** - Follow plan task-by-task
3. **Review Checkpoints** - Verify progress between tasks
