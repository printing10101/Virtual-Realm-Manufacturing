# Template Evolution System Design

**Date**: 2026-05-13
**Project**: 灵境制造 (Lingjing Manufacturing)
**Status**: Implemented

---

## Overview

Transform static project templates into continuously learning, data-driven living systems. The system comprises six core modules that work together to detect patterns, evolve templates, validate changes via A/B testing, manage branches, push updates proactively, and expose capabilities through an enhanced marketplace.

## Architecture Principles

1. **Data-driven**: Every evolution decision is backed by execution data. No subjective changes.
2. **User sovereignty**: System recommends, user decides. All auto-merges have thresholds.
3. **Full audit trail**: Every state is versioned, timestamped, and reversible.
4. **Follow existing patterns**: Uses SQLite + JSON storage, FastAPI routers, `init_*()`/`get_*()` initialization, Pydantic models — matching `skill_loader.py`, `budget.py`, `approval_workflow.py` conventions.

## System Decomposition

### Phase 1: Foundation (Template Branching System)
**File**: `python/app/core/template_branching.py`

#### Data Model
```python
@dataclass
class TemplateBranch:
    branch_id: str           # unique ID (uuid)
    name: str                # e.g., "main", "auto-001", "car-industry"
    base_branch: str         # parent branch ID
    template_data: dict      # the actual template content
    metadata: dict           # {type: "main|industry|material|project|experiment"}
    created_at: float
    updated_at: float
    commit_log: List[CommitEntry]
```

#### Branch Types
| Type | Prefix | Purpose |
|------|--------|---------|
| main | `main` | Verified best-practice baseline |
| industry | `industry-{name}` | Car, aerospace, mold, etc. |
| material | `material-{name}` | 45-steel, aluminum, titanium, etc. |
| project | `project-{id}` | Per-project customization |
| experiment | `exp-{id}` | A/B test candidate |

#### Core Functions
- `create_branch(name, base, data, metadata)` → new branch
- `merge_branch(source, target, strategy)` → merge with conflict resolution
- `get_branch(branch_id)` → retrieve branch
- `list_branches(type_filter=None)` → list with optional filter
- `get_commit_log(branch_id)` → full history

#### Storage
- SQLite table: `template_branches(branch_id, name, base_branch, type, created_at, updated_at)`
- JSON files: `data/templates/branches/{branch_id}.json` (template content + commit log)

### Phase 2: Pattern Recognition Engine
**File**: `python/app/core/pattern_engine.py`

#### Data Model
```python
@dataclass
class Pattern:
    pattern_id: str
    pattern_type: str          # "workflow" | "anti_pattern" | "combination"
    description: str
    elements: dict             # e.g., {"model": "cfc", "skill": "vibration", "interval": "0.1s"}
    conditions: dict           # e.g., {"material": "aluminum", "operation": "finishing"}
    metrics: dict              # e.g., {"accuracy_improvement": 0.15, "confidence": 0.92}
    sample_size: int           # number of executions observed
    suggestion: str | None     # auto-generated recommendation
    created_at: float
```

#### Pattern Detection Logic
- **Workflow extraction**: After each task completion, analyze execution path (skills used, model config, time, retries, errors)
- **Quality scoring**: Weighted composite of `execution_time`, `success_rate`, `resource_cost`
- **Anti-pattern detection**: Flag patterns with `retry_count > 2`, `error_rate > 0.3`, `resource_waste > 20%`
- **Combination discovery**: Cross-reference task outcomes with element combinations using frequency analysis + chi-squared test

#### Core Functions
- `record_execution(task_id, execution_path, result)` → store execution data
- `analyze_patterns(min_samples=10)` → discover new patterns from accumulated data
- `get_patterns(pattern_type=None, conditions=None)` → query discovered patterns
- `generate_suggestions(pattern_id)` → create update suggestion from pattern
- `get_anti_patterns()` → list all detected anti-patterns

#### Storage
- SQLite table: `pattern_executions(task_id, branch_id, elements, conditions, metrics, created_at)`
- SQLite table: `patterns(pattern_id, type, description, elements, conditions, metrics, sample_size, suggestion, created_at)`

### Phase 3: Template Evolution Core
**File**: `python/app/core/template_evolution.py`

#### Data Model
```python
@dataclass
class EvolutionTrigger:
    trigger_type: str          # "skill" | "model_config" | "approval_strategy" | "heartbeat_routine" | "budget_strategy"
    condition: Callable        # data-driven condition function
    action: Callable           # what to do when triggered
    cooldown_hours: int        # prevent over-triggering

@dataclass
class EvolutionSuggestion:
    suggestion_id: str
    trigger_type: str
    description: str
    data_evidence: dict        # {metric: value, threshold: value, actual: value}
    proposed_change: dict      # the actual template diff
    confidence: float          # 0.0 - 1.0
    created_at: float
    status: str                # "pending" | "accepted" | "rejected" | "applied"
```

#### Trigger Rules
| Trigger Type | Condition | Action |
|-------------|-----------|--------|
| skill | Same error type >= 3 times | Create suggestion to add/update skill doc |
| model_config | A/B test shows better result | Update default hyperparams |
| approval_strategy | False positive rate > 20% | Adjust risk threshold |
| heartbeat_routine | GPU utilization < 30% for 7 days | Optimize scheduling frequency |
| budget_strategy | Consecutive overspend or waste > 20% | Generate quota adjustment suggestion |

#### Core Functions
- `register_trigger(trigger_type, condition, action, cooldown_hours)` → register evolution trigger
- `evaluate_triggers()` → check all triggers against current data
- `create_suggestion(trigger_type, evidence, proposed_change)` → create evolution suggestion
- `apply_suggestion(suggestion_id, branch_id)` → apply suggestion to branch
- `list_suggestions(status_filter=None)` → list pending/accepted/rejected suggestions
- `get_evolution_history(branch_id)` → full evolution timeline

#### Integration
- Uses `pattern_engine` for pattern data
- Uses `template_branching` for branch management
- Emits SSE events for real-time notifications
- Logs to audit trail

### Phase 4: A/B Testing Framework
**File**: `python/app/core/template_ab_testing.py`

#### Data Model
```python
@dataclass
class ABExperiment:
    experiment_id: str
    name: str
    control_branch: str        # main branch
    candidate_branch: str      # experiment branch
    traffic_split: float       # default 0.10 (10%)
    metrics: dict              # {metric_name: {control: value, candidate: value}}
    status: str                # "running" | "concluded" | "rolled_back" | "merged"
    created_at: float
    concluded_at: float | None
    result: str | None         # "winner_candidate" | "winner_control" | "inconclusive"
```

#### Success Criteria
- **Auto-merge**: candidate improves key metrics > 5% AND statistical confidence > 95%
- **Auto-rollback**: candidate worsens metrics < 0% OR error rate increases

#### Statistical Engine
- Uses Welch's t-test for continuous metrics (execution time, resource cost)
- Uses chi-squared test for categorical metrics (success rate)
- Minimum sample size: 30 executions per branch

#### Core Functions
- `create_experiment(name, control_branch, candidate_branch, traffic_split=0.10)` → new experiment
- `record_execution(experiment_id, branch, metrics)` → record execution data
- `evaluate(experiment_id)` → run statistical analysis
- `auto_conclude(experiment_id)` → merge or rollback based on criteria
- `get_active_experiments()` → list running experiments
- `get_experiment_results(experiment_id)` → full results

#### Traffic Routing
- Uses consistent hashing on `project_id` to ensure same project always gets same branch
- Stored in SQLite: `ab_traffic(project_id, experiment_id, assigned_branch)`

### Phase 5: Template Update Service
**File**: `python/app/core/template_update_service.py`

#### Data Model
```python
@dataclass
class UpdateNotification:
    notification_id: str
    project_id: str
    suggestion_id: str         # link to evolution_suggestion
    priority: str              # "optional" | "recommended" | "critical"
    title: str
    description: str
    change_preview: dict       # diff preview
    expected_impact: dict      # {metric: expected_change}
    created_at: float
    status: str                # "pending" | "accepted" | "dismissed" | "applied"
```

#### Priority Classification
| Priority | Criteria | UX Treatment |
|----------|----------|--------------|
| optional | Minor optimization (< 3% improvement) | Shown in notification panel, no push |
| recommended | Clear benefit (3-10% improvement) | Highlighted card, gentle nudge |
| critical | Stability/security fix, or > 10% improvement | Prominent banner, immediate action suggested |

#### Core Functions
- `scan_for_updates(project_id)` → find applicable suggestions for project
- `classify_priority(suggestion)` → determine priority level
- `create_notification(project_id, suggestion, priority)` → create update notification
- `apply_update(notification_id)` → one-click apply
- `preview_update(notification_id)` → show full diff + expected impact
- `dismiss_notification(notification_id)` → user dismisses
- `get_notifications(project_id, status_filter=None)` → list notifications

### Phase 6: Enhanced Marketplace (Frontend + Backend)
**Files**: 
- Backend: `python/app/api/v1/template_market.py`
- Frontend: `src/views/TemplateMarket.vue`, `src/stores/template_market.ts`

#### New Backend Endpoints
```
GET    /api/v1/template_market/trending          # Popularity ranking
GET    /api/v1/template_market/templates/{id}/metrics  # Effectiveness stats
POST   /api/v1/template_market/publish           # Publish validated template
GET    /api/v1/template_market/subscriptions     # User subscriptions
POST   /api/v1/template_market/subscriptions     # Subscribe to category
POST   /api/v1/template_market/export/{id}       # Export with evolution history
POST   /api/v1/template_market/import            # Import with auto-adaptation
GET    /api/v1/template_market/sync/{id}         # Incremental sync diff
```

#### New Frontend Views
- **TemplateMarket.vue**: Main marketplace with trending, metrics, subscribe
- **TemplateDetail.vue**: Detailed view with evolution history, A/B test results
- **UpdateCenter.vue**: Pending update notifications, one-click apply
- **BranchManager.vue**: Branch list, merge UI, experiment status

## Data Flow Architecture

```
Task Execution → Pattern Engine (record)
                    ↓ (analyze)
              Evolution Core (evaluate triggers)
                    ↓ (create suggestion)
              A/B Testing (create experiment)
                    ↓ (record + evaluate)
              ┌─→ merged ─→ Update Service (notify projects)
              └─→ rolled_back → Evolution Core (learn, don't repeat)

User ← SSE Events ← Update Service ← Evolution Core
```

## API Routes Summary

All routes follow existing `python/app/api/v1/` convention:

| Router | File | Routes |
|--------|------|--------|
| `template_evolution` | `template_evolution_routes.py` | `/api/v1/templates/evolution/*` |
| `template_branching` | `template_branching_routes.py` | `/api/v1/templates/branches/*` |
| `template_ab_testing` | `template_ab_testing_routes.py` | `/api/v1/templates/ab_tests/*` |
| `template_update` | `template_update_routes.py` | `/api/v1/templates/updates/*` |
| `template_market` | `template_market.py` | `/api/v1/template_market/*` |

## Initialization Pattern

Follow existing convention from `main.py`:

```python
# In main.py startup_event():
from app.core.template_branching import init_template_branching, get_branch_manager
from app.core.pattern_engine import init_pattern_engine, get_pattern_engine
from app.core.template_evolution import init_template_evolution, get_evolution_engine
from app.core.template_ab_testing import init_ab_testing, get_ab_testing
from app.core.template_update_service import init_update_service, get_update_service

init_template_branching()
init_pattern_engine()
init_template_evolution()
init_ab_testing()
init_update_service()
```

## File Index

### New Files (Backend)
1. `python/app/core/template_branching.py` — Branch management
2. `python/app/core/pattern_engine.py` — Pattern recognition
3. `python/app/core/template_evolution.py` — Evolution core + triggers
4. `python/app/core/template_ab_testing.py` — A/B testing framework
5. `python/app/core/template_update_service.py` — Update push service
6. `python/app/api/v1/template_evolution_routes.py` — Evolution API routes
7. `python/app/api/v1/template_branching_routes.py` — Branching API routes
8. `python/app/api/v1/template_ab_testing_routes.py` — A/B testing API routes
9. `python/app/api/v1/template_update_routes.py` — Update API routes
10. `python/app/api/v1/template_market.py` — Marketplace API routes

### New Files (Frontend)
1. `src/views/TemplateMarket.vue` — Marketplace main view
2. `src/views/TemplateDetail.vue` — Template detail with evolution history
3. `src/views/UpdateCenter.vue` — Update notification center
4. `src/views/BranchManager.vue` — Branch management UI
5. `src/stores/template_market.ts` — Marketplace Pinia store

### New Directories
1. `data/templates/branches/` — Branch JSON storage
2. `data/templates/evolution_log/` — Evolution history logs
3. `data/templates/experiments/` — A/B experiment data

## Testing Strategy

- Unit tests: `python/tests/functional_test_template_branching.py`
- Unit tests: `python/tests/functional_test_pattern_engine.py`
- Unit tests: `python/tests/functional_test_template_evolution.py`
- Unit tests: `python/tests/functional_test_ab_testing.py`
- Unit tests: `python/tests/functional_test_update_service.py`
- E2E tests: `e2e/template-evolution.spec.ts`

## Dependencies

No new external Python dependencies required. Uses existing:
- `sqlite3` — data storage
- `json` — branch/evolution file storage
- `hashlib` — content hashing
- `statistics` — statistical analysis
- `datetime` — timestamps
- `asyncio` — async operations

Optional: `scipy` for advanced statistical tests (chi-squared, t-test) — add to `requirements.txt` only if needed.

## Migration Plan

1. Create all core modules (no API/frontend yet) — system works silently
2. Add API routes — expose functionality to frontend
3. Add frontend views — user-facing features
4. Integrate with existing `main.py` startup — activate in production
5. Seed initial `main` branch from current template state
6. Run pattern engine analysis on historical execution data (if available)

---

## Implementation Summary

### Completed (2026-05-13)

All 6 phases have been implemented and tested:

| Phase | Module | Tests | Status |
|-------|--------|-------|--------|
| 1 | Template Branching | 9/9 passed | ✅ |
| 2 | Pattern Engine | 8/8 passed | ✅ |
| 3 | Template Evolution | 12/12 passed | ✅ |
| 4 | A/B Testing | 10/10 passed | ✅ |
| 5 | Update Service | 14/14 passed | ✅ |
| 6 | Marketplace + Frontend | API + 4 views | ✅ |
| **Total** | **10 backend files + 4 frontend views + 5 test files + routes** | **53/53** | **✅** |

### Files Created
- **Backend core**: `template_branching.py`, `pattern_engine.py`, `template_evolution.py`, `template_ab_testing.py`, `template_update_service.py`
- **Backend API**: `template_branching_routes.py`, `pattern_engine_routes.py`, `template_evolution_routes.py`, `template_ab_testing_routes.py`, `template_update_routes.py`, `template_market.py`
- **Frontend**: `TemplateMarket.vue`, `TemplateDetail.vue`, `UpdateCenter.vue`, `BranchManager.vue`
- **Tests**: `functional_test_template_branching.py`, `functional_test_pattern_engine.py`, `functional_test_template_evolution.py`, `functional_test_ab_testing.py`, `functional_test_update_service.py`
- **Modified**: `main.py` (imports, init, routers), `router/index.ts` (4 new routes)

### Bugs Fixed During Implementation
1. Evolution trigger conditions compared dict wrappers vs raw values — added flattening layer in `evaluate_triggers()`
2. SQLite cannot store dict values — added JSON serialization for non-scalar metrics
3. A/B statistical test confidence calculation needed more robust Welch's t-test approximation
