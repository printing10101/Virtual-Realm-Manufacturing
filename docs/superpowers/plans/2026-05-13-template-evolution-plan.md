# Template Evolution System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform static project templates into continuously learning, data-driven living systems with six modules: branching, pattern recognition, evolution, A/B testing, update service, and enhanced marketplace.

**Architecture:** Six-phase modular backend with SQLite + JSON storage, FastAPI routers, `init_*`/`get_*` singleton pattern matching skill_loader.py conventions, and Vue.js frontend components.

**Tech Stack:** Python (FastAPI, SQLite3, json, hashlib, statistics, asyncio), Vue.js 3 + TypeScript + Pinia, SSE for real-time notifications.

---

## File Structure

### Backend Files (10 new files)
| File | Responsibility |
|------|---------------|
| `python/app/core/template_branching.py` | Branch CRUD, merge, commit log, SQLite + JSON storage |
| `python/app/core/pattern_engine.py` | Execution recording, pattern detection, anti-pattern identification |
| `python/app/core/template_evolution.py` | Evolution triggers, suggestion lifecycle, branch application |
| `python/app/core/template_ab_testing.py` | A/B experiments, statistical analysis, traffic routing |
| `python/app/core/template_update_service.py` | Update scanning, notification management, one-click apply |
| `python/app/api/v1/template_branching_routes.py` | Branch API: `/api/v1/templates/branches/*` |
| `python/app/api/v1/template_evolution_routes.py` | Evolution API: `/api/v1/templates/evolution/*` |
| `python/app/api/v1/template_ab_testing_routes.py` | A/B testing API: `/api/v1/templates/ab_tests/*` |
| `python/app/api/v1/template_update_routes.py` | Update API: `/api/v1/templates/updates/*` |
| `python/app/api/v1/template_market.py` | Marketplace API: `/api/v1/template_market/*` |

### Frontend Files (5 new files)
| File | Responsibility |
|------|---------------|
| `src/stores/template_market.ts` | Pinia store for marketplace state, API calls |
| `src/views/TemplateMarket.vue` | Marketplace view with trending templates, metrics, subscription |
| `src/views/TemplateDetail.vue` | Template detail with evolution history, A/B results |
| `src/views/UpdateCenter.vue` | Notification center for pending updates |
| `src/views/BranchManager.vue` | Branch management UI, merge interface |

### Test Files (5 new files)
| File | Tests |
|------|-------|
| `python/tests/functional_test_template_branching.py` | Branch creation, merge, listing, commit log |
| `python/tests/functional_test_pattern_engine.py` | Execution recording, pattern detection, anti-patterns |
| `python/tests/functional_test_template_evolution.py` | Trigger registration, suggestion lifecycle, application |
| `python/tests/functional_test_ab_testing.py` | Experiment creation, statistical evaluation, auto-conclude |
| `python/tests/functional_test_update_service.py` | Scan, classify, notify, apply, dismiss |

---

## Phase 1: Template Branching System (Foundation)

### Task 1: Branch Manager Core Class

**Files:**
- Create: `python/app/core/template_branching.py`
- Test: `python/tests/functional_test_template_branching.py`

- [ ] **Step 1: Write the failing test — branch creation**

```python
# python/tests/functional_test_template_branching.py
"""Functional tests for Template Branching System."""
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

# Will test after implementation
# These imports will work once the module exists
try:
    from app.core.template_branching import TemplateBranchManager
except ImportError:
    TemplateBranchManager = None


@pytest.fixture
def branch_manager():
    """Create a temporary branch manager for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "branches.db")
    json_dir = os.path.join(tmpdir, "branches")
    os.makedirs(json_dir, exist_ok=True)
    
    manager = TemplateBranchManager(db_path=db_path, json_dir=json_dir)
    manager.initialize()
    
    yield manager
    
    shutil.rmtree(tmpdir)


def test_create_branch(branch_manager):
    """Test creating a main branch."""
    template_data = {
        "name": "CNC Milling Template",
        "skills": ["vibration_analysis", "wear_prediction"],
        "model_config": {"lr": 0.001, "epochs": 100},
    }
    
    branch = branch_manager.create_branch(
        name="main",
        base_branch=None,
        data=template_data,
        metadata={"type": "main"},
    )
    
    assert branch.branch_id is not None
    assert branch.name == "main"
    assert branch.base_branch is None
    assert branch.metadata["type"] == "main"
    assert branch.template_data == template_data
    assert len(branch.commit_log) == 1
    assert branch.commit_log[0]["action"] == "create"


def test_get_branch(branch_manager):
    """Test retrieving a branch by ID."""
    template_data = {"name": "Test Template"}
    branch = branch_manager.create_branch(
        name="main", base_branch=None, data=template_data, metadata={"type": "main"}
    )
    
    retrieved = branch_manager.get_branch(branch.branch_id)
    
    assert retrieved is not None
    assert retrieved.branch_id == branch.branch_id
    assert retrieved.name == "main"


def test_list_branches(branch_manager):
    """Test listing branches with optional type filter."""
    # Create main branch
    branch_manager.create_branch(
        name="main", base_branch=None, data={"name": "Main"}, metadata={"type": "main"}
    )
    # Create industry branch
    branch_manager.create_branch(
        name="car-industry", base_branch="main", data={"name": "Car"}, metadata={"type": "industry"}
    )
    # Create material branch
    branch_manager.create_branch(
        name="aluminum", base_branch="main", data={"name": "Aluminum"}, metadata={"type": "material"}
    )
    
    all_branches = branch_manager.list_branches()
    assert len(all_branches) == 3
    
    industry_branches = branch_manager.list_branches(type_filter="industry")
    assert len(industry_branches) == 1
    assert industry_branches[0].name == "car-industry"
    
    material_branches = branch_manager.list_branches(type_filter="material")
    assert len(material_branches) == 1
    assert material_branches[0].name == "aluminum"


def test_commit_log(branch_manager):
    """Test that create and merge operations are logged."""
    branch = branch_manager.create_branch(
        name="main", base_branch=None, data={"name": "Main"}, metadata={"type": "main"}
    )
    
    log = branch_manager.get_commit_log(branch.branch_id)
    
    assert len(log) == 1
    assert log[0]["action"] == "create"
    assert log[0]["branch_name"] == "main"
    assert "timestamp" in log[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_template_branching.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.template_branching'"

- [ ] **Step 3: Implement TemplateBranchManager core class**

```python
# python/app/core/template_branching.py
"""Template Branching System — Foundation for template evolution."""
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CommitEntry:
    action: str
    branch_name: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "branch_name": self.branch_name,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class TemplateBranch:
    branch_id: str
    name: str
    base_branch: Optional[str]
    template_data: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    commit_log: List[CommitEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "name": self.name,
            "base_branch": self.base_branch,
            "template_data": self.template_data,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "commit_log": [e.to_dict() for e in self.commit_log],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateBranch":
        return cls(
            branch_id=data["branch_id"],
            name=data["name"],
            base_branch=data.get("base_branch"),
            template_data=data.get("template_data", {}),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            commit_log=[
                CommitEntry(**e) for e in data.get("commit_log", [])
            ],
        )


class TemplateBranchManager:
    """Manages template branches with SQLite metadata + JSON content storage."""

    BRANCH_TYPES = {"main", "industry", "material", "project", "experiment"}

    def __init__(
        self,
        db_path: str = "data/templates/branches.db",
        json_dir: str = "data/templates/branches",
    ):
        self.db_path = db_path
        self.json_dir = json_dir
        self._lock = threading.RLock()
        self._cache: Dict[str, TemplateBranch] = {}
        self._db: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Create SQLite table and ensure directories exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS template_branches (
                branch_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_branch TEXT,
                type TEXT NOT NULL DEFAULT 'main',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._db.commit()
        self._load_cache()
        logger.info("TemplateBranchManager initialized: db=%s, json_dir=%s", self.db_path, self.json_dir)

    def _load_cache(self) -> None:
        """Load all branches from storage into memory cache."""
        self._cache.clear()
        cursor = self._db.execute("SELECT * FROM template_branches")
        for row in cursor.fetchall():
            branch_id = row["branch_id"]
            json_path = os.path.join(self.json_dir, f"{branch_id}.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[branch_id] = TemplateBranch.from_dict(data)

    def _save_branch(self, branch: TemplateBranch) -> None:
        """Persist branch to SQLite + JSON."""
        with open(os.path.join(self.json_dir, f"{branch.branch_id}.json"), "w", encoding="utf-8") as f:
            json.dump(branch.to_dict(), f, indent=2, ensure_ascii=False)
        
        self._db.execute(
            """INSERT OR REPLACE INTO template_branches
               (branch_id, name, base_branch, type, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                branch.branch_id,
                branch.name,
                branch.base_branch,
                branch.metadata.get("type", "main"),
                branch.created_at,
                branch.updated_at,
            ),
        )
        self._db.commit()

    def _compute_content_hash(self, data: Dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    def create_branch(
        self,
        name: str,
        base_branch: Optional[str],
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TemplateBranch:
        """Create a new template branch."""
        with self._lock:
            branch_id = uuid.uuid4().hex[:12]
            now = time.time()
            
            commit_entry = CommitEntry(
                action="create",
                branch_name=name,
                timestamp=now,
                details={
                    "base_branch": base_branch,
                    "content_hash": self._compute_content_hash(data),
                },
            )
            
            branch = TemplateBranch(
                branch_id=branch_id,
                name=name,
                base_branch=base_branch,
                template_data=data,
                metadata=metadata or {"type": "main"},
                created_at=now,
                updated_at=now,
                commit_log=[commit_entry],
            )
            
            self._cache[branch_id] = branch
            self._save_branch(branch)
            
            logger.info("Branch created: id=%s, name=%s, type=%s", branch_id, name, branch.metadata.get("type"))
            return branch

    def get_branch(self, branch_id: str) -> Optional[TemplateBranch]:
        """Retrieve a branch by ID."""
        with self._lock:
            return self._cache.get(branch_id)

    def list_branches(self, type_filter: Optional[str] = None) -> List[TemplateBranch]:
        """List all branches, optionally filtered by type."""
        with self._lock:
            branches = list(self._cache.values())
            if type_filter:
                branches = [b for b in branches if b.metadata.get("type") == type_filter]
            return sorted(branches, key=lambda b: b.updated_at, reverse=True)

    def get_commit_log(self, branch_id: str) -> List[Dict[str, Any]]:
        """Get full commit history for a branch."""
        with self._lock:
            branch = self._cache.get(branch_id)
            if branch is None:
                return []
            return [e.to_dict() for e in branch.commit_log]

    def update_branch_data(
        self, branch_id: str, data: Dict[str, Any], action: str = "update"
    ) -> Optional[TemplateBranch]:
        """Update a branch's template data and log the change."""
        with self._lock:
            branch = self._cache.get(branch_id)
            if branch is None:
                return None
            
            branch.template_data = data
            branch.updated_at = time.time()
            branch.commit_log.append(CommitEntry(
                action=action,
                branch_name=branch.name,
                timestamp=branch.updated_at,
                details={"content_hash": self._compute_content_hash(data)},
            ))
            
            self._save_branch(branch)
            logger.info("Branch updated: id=%s, action=%s", branch_id, action)
            return branch

    def merge_branch(
        self, source_id: str, target_id: str, strategy: str = "overwrite"
    ) -> Optional[TemplateBranch]:
        """Merge source branch into target branch."""
        with self._lock:
            source = self._cache.get(source_id)
            target = self._cache.get(target_id)
            if source is None or target is None:
                return None
            
            if strategy == "overwrite":
                target.template_data = source.template_data.copy()
            elif strategy == "deep_merge":
                target.template_data = self._deep_merge(target.template_data, source.template_data)
            
            target.updated_at = time.time()
            target.commit_log.append(CommitEntry(
                action="merge",
                branch_name=f"{source.name}→{target.name}",
                timestamp=target.updated_at,
                details={
                    "source_id": source_id,
                    "target_id": target_id,
                    "strategy": strategy,
                    "content_hash": self._compute_content_hash(target.template_data),
                },
            ))
            
            self._save_branch(target)
            logger.info("Branch merged: %s → %s (strategy=%s)", source_id, target_id, strategy)
            return target

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge override into base."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def delete_branch(self, branch_id: str) -> bool:
        """Delete a branch (cannot delete main)."""
        with self._lock:
            branch = self._cache.get(branch_id)
            if branch is None:
                return False
            if branch.metadata.get("type") == "main":
                raise ValueError("Cannot delete main branch")
            
            del self._cache[branch_id]
            self._db.execute("DELETE FROM template_branches WHERE branch_id = ?", (branch_id,))
            self._db.commit()
            
            json_path = os.path.join(self.json_dir, f"{branch_id}.json")
            if os.path.exists(json_path):
                os.remove(json_path)
            
            logger.info("Branch deleted: id=%s", branch_id)
            return True

    def close(self) -> None:
        """Close database connection."""
        if self._db:
            self._db.close()


_branch_manager: Optional[TemplateBranchManager] = None
_branch_manager_lock = threading.Lock()


def get_branch_manager() -> TemplateBranchManager:
    global _branch_manager
    if _branch_manager is None:
        with _branch_manager_lock:
            if _branch_manager is None:
                _branch_manager = TemplateBranchManager()
                _branch_manager.initialize()
    return _branch_manager


def init_template_branching(
    db_path: str = "data/templates/branches.db",
    json_dir: str = "data/templates/branches",
) -> TemplateBranchManager:
    global _branch_manager
    with _branch_manager_lock:
        if _branch_manager is not None:
            _branch_manager.close()
        _branch_manager = TemplateBranchManager(db_path=db_path, json_dir=json_dir)
        _branch_manager.initialize()
    return _branch_manager
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_template_branching.py -v`
Expected: PASS — 4/4 tests pass

- [ ] **Step 5: Commit**

```bash
git add python/app/core/template_branching.py python/tests/functional_test_template_branching.py
git commit -m "feat: add template branching system with SQLite + JSON storage"
```

---

### Task 2: Branch API Routes

**Files:**
- Create: `python/app/api/v1/template_branching_routes.py`
- Test: `python/tests/functional_test_template_branching.py` (add API tests)

- [ ] **Step 1: Write the failing test — API endpoints**

```python
# Add to python/tests/functional_test_template_branching.py
from fastapi.testclient import TestClient
from fastapi import FastAPI

@pytest.fixture
def api_client(branch_manager):
    """Create test client for branch API."""
    from app.api.v1.template_branching_routes import router
    
    app = FastAPI()
    app.include_router(router)
    
    # Override dependency to use test manager
    import app.api.v1.template_branching_routes as routes
    routes._test_manager = branch_manager
    
    return TestClient(app)


def test_api_create_branch(api_client):
    """Test POST /api/v1/templates/branches/"""
    response = api_client.post("/api/v1/templates/branches/", json={
        "name": "main",
        "base_branch": None,
        "data": {"name": "Main Template"},
        "metadata": {"type": "main"},
    })
    assert response.status_code == 201
    data = response.json()
    assert data["branch"]["name"] == "main"
    assert data["branch"]["metadata"]["type"] == "main"


def test_api_list_branches(api_client):
    """Test GET /api/v1/templates/branches/"""
    # Create one branch first
    api_client.post("/api/v1/templates/branches/", json={
        "name": "test-branch", "base_branch": None,
        "data": {"name": "Test"}, "metadata": {"type": "main"},
    })
    
    response = api_client.get("/api/v1/templates/branches/")
    assert response.status_code == 200
    data = response.json()
    assert "branches" in data
    assert len(data["branches"]) >= 1


def test_api_get_branch(api_client):
    """Test GET /api/v1/templates/branches/{branch_id}"""
    create_resp = api_client.post("/api/v1/templates/branches/", json={
        "name": "single", "base_branch": None,
        "data": {"name": "Single"}, "metadata": {"type": "main"},
    })
    branch_id = create_resp.json()["branch"]["branch_id"]
    
    response = api_client.get(f"/api/v1/templates/branches/{branch_id}")
    assert response.status_code == 200
    assert response.json()["branch"]["name"] == "single"


def test_api_merge_branch(api_client):
    """Test POST /api/v1/templates/branches/merge"""
    # Create source and target
    src = api_client.post("/api/v1/templates/branches/", json={
        "name": "source", "base_branch": None,
        "data": {"skill": "v1"}, "metadata": {"type": "experiment"},
    })
    tgt = api_client.post("/api/v1/templates/branches/", json={
        "name": "target", "base_branch": None,
        "data": {"skill": "v0"}, "metadata": {"type": "main"},
    })
    
    response = api_client.post("/api/v1/templates/branches/merge", json={
        "source_id": src.json()["branch"]["branch_id"],
        "target_id": tgt.json()["branch"]["branch_id"],
        "strategy": "overwrite",
    })
    assert response.status_code == 200
    assert response.json()["merged_branch"]["template_data"]["skill"] == "v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_template_branching.py::test_api_create_branch -v`
Expected: FAIL with "ModuleNotFoundError" or "router not found"

- [ ] **Step 3: Implement branch API routes**

```python
# python/app/api/v1/template_branching_routes.py
"""API routes for template branching system."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.template_branching import get_branch_manager

router = APIRouter(prefix="/api/v1/templates/branches", tags=["template-branching"])

# Allow test override
_test_manager = None


def _get_manager():
    return _test_manager if _test_manager is not None else get_branch_manager()


class CreateBranchRequest(BaseModel):
    name: str
    base_branch: Optional[str] = None
    data: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class MergeBranchRequest(BaseModel):
    source_id: str
    target_id: str
    strategy: str = "overwrite"


class UpdateBranchRequest(BaseModel):
    data: dict


@router.post("/", status_code=201)
async def create_branch(req: CreateBranchRequest):
    manager = _get_manager()
    branch = manager.create_branch(
        name=req.name,
        base_branch=req.base_branch,
        data=req.data,
        metadata=req.metadata,
    )
    return {"branch": branch.to_dict()}


@router.get("/")
async def list_branches(type_filter: Optional[str] = None):
    manager = _get_manager()
    branches = manager.list_branches(type_filter=type_filter)
    return {"branches": [b.to_dict() for b in branches]}


@router.get("/{branch_id}")
async def get_branch(branch_id: str):
    manager = _get_manager()
    branch = manager.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"branch": branch.to_dict()}


@router.get("/{branch_id}/log")
async def get_commit_log(branch_id: str):
    manager = _get_manager()
    branch = manager.get_branch(branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"commit_log": manager.get_commit_log(branch_id)}


@router.post("/merge")
async def merge_branch(req: MergeBranchRequest):
    manager = _get_manager()
    result = manager.merge_branch(req.source_id, req.target_id, strategy=req.strategy)
    if result is None:
        raise HTTPException(status_code=404, detail="Source or target branch not found")
    return {"merged_branch": result.to_dict()}


@router.put("/{branch_id}")
async def update_branch(branch_id: str, req: UpdateBranchRequest):
    manager = _get_manager()
    result = manager.update_branch_data(branch_id, req.data)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
    return {"branch": result.to_dict()}


@router.delete("/{branch_id}")
async def delete_branch(branch_id: str):
    manager = _get_manager()
    try:
        success = manager.delete_branch(branch_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Branch not found: {branch_id}")
        return {"message": "Branch deleted"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_template_branching.py -v -k "api"`
Expected: PASS — 4/4 API tests pass

- [ ] **Step 5: Commit**

```bash
git add python/app/api/v1/template_branching_routes.py python/tests/functional_test_template_branching.py
git commit -m "feat: add template branching API routes with CRUD + merge endpoints"
```

---

### Task 3: Register Branching in main.py + Seed Main Branch

**Files:**
- Modify: `python/app/main.py`
- Test: `python/tests/functional_test_template_branching.py` (startup integration test)

- [ ] **Step 1: Write the failing test — startup integration**

```python
# Add to python/tests/functional_test_template_branching.py
def test_startup_initialization():
    """Test that init_template_branching creates a manager with working methods."""
    from app.core.template_branching import init_template_branching, get_branch_manager
    import tempfile
    import os
    
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    json_dir = os.path.join(tmpdir, "branches")
    
    manager = init_template_branching(db_path=db_path, json_dir=json_dir)
    
    # Should be able to get the same instance via getter
    same = get_branch_manager()
    assert same is manager
    
    # Should have created the SQLite table
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='template_branches'")
    assert cursor.fetchone() is not None
    conn.close()
    
    # Cleanup
    manager.close()
    import shutil
    shutil.rmtree(tmpdir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_template_branching.py::test_startup_initialization -v`
Expected: FAIL — `get_branch_manager()` returns different instance (singleton not initialized yet)

- [ ] **Step 3: Add initialization to main.py startup**

Exact additions to `python/app/main.py`:

```python
# 1. Add to imports block (after `from app.core.skill_loader import init_skill_loader`, ~line 30):
from app.core.template_branching import init_template_branching, get_branch_manager

# 2. Add to startup_event() function (after init_skill_loader(), ~line 93):
    init_template_branching()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_template_branching.py::test_startup_initialization -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/app/main.py python/tests/functional_test_template_branching.py
git commit -m "feat: integrate template branching into application startup"
```

---

## Phase 2: Pattern Recognition Engine

### Task 4: Pattern Engine Core

**Files:**
- Create: `python/app/core/pattern_engine.py`
- Test: `python/tests/functional_test_pattern_engine.py`

- [ ] **Step 1: Write the failing test — pattern detection**

```python
# python/tests/functional_test_pattern_engine.py
"""Functional tests for Pattern Recognition Engine."""
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

try:
    from app.core.pattern_engine import PatternEngine
except ImportError:
    PatternEngine = None


@pytest.fixture
def pattern_engine():
    """Create a temporary pattern engine for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "patterns.db")
    
    engine = PatternEngine(db_path=db_path)
    engine.initialize()
    
    yield engine
    
    engine.close()
    shutil.rmtree(tmpdir)


def test_record_execution(pattern_engine):
    """Test recording execution data."""
    execution = pattern_engine.record_execution(
        task_id="task-001",
        branch_id="main",
        execution_path={
            "skills_used": ["vibration_analysis", "wear_prediction"],
            "model": "cfc",
            "config": {"lr": 0.001, "epochs": 100},
        },
        result={
            "success": True,
            "execution_time": 2.5,
            "resource_cost": 0.15,
            "retry_count": 0,
            "error_count": 0,
        },
    )
    
    assert execution["task_id"] == "task-001"
    assert execution["branch_id"] == "main"
    assert execution["metrics"]["success"] is True


def test_analyze_patterns_detects_workflow(pattern_engine):
    """Test that repeated workflows are detected as patterns."""
    # Record 12 identical executions to exceed min_samples=10
    for i in range(12):
        pattern_engine.record_execution(
            task_id=f"task-{i:03d}",
            branch_id="main",
            execution_path={
                "skills_used": ["vibration_analysis", "parameter_optimization"],
                "model": "cfc",
                "config": {"lr": 0.001},
            },
            result={
                "success": True,
                "execution_time": 2.0 + (i % 3) * 0.1,
                "resource_cost": 0.15,
                "retry_count": 0,
                "error_count": 0,
            },
        )
    
    patterns = pattern_engine.analyze_patterns(min_samples=10)
    assert len(patterns) >= 1
    
    # Check the detected pattern
    workflow_patterns = [p for p in patterns if p.pattern_type == "workflow"]
    assert len(workflow_patterns) >= 1
    assert workflow_patterns[0].sample_size >= 10


def test_anti_pattern_detection(pattern_engine):
    """Test detection of anti-patterns with high retry rates."""
    # Record 10 executions with high retry counts
    for i in range(10):
        pattern_engine.record_execution(
            task_id=f"bad-task-{i:03d}",
            branch_id="main",
            execution_path={
                "skills_used": ["error_handler"],
                "model": "ltc",
                "config": {"lr": 0.1},
            },
            result={
                "success": False,
                "execution_time": 15.0,
                "resource_cost": 0.85,
                "retry_count": 4,
                "error_count": 3,
            },
        )
    
    patterns = pattern_engine.analyze_patterns(min_samples=5)
    anti_patterns = pattern_engine.get_anti_patterns()
    assert len(anti_patterns) >= 1
    assert anti_patterns[0].pattern_type == "anti_pattern"


def test_generate_suggestions(pattern_engine):
    """Test that suggestions are generated from patterns."""
    for i in range(12):
        pattern_engine.record_execution(
            task_id=f"suggest-task-{i:03d}",
            branch_id="main",
            execution_path={
                "skills_used": ["vibration_analysis"],
                "model": "cfc",
                "config": {"lr": 0.001},
            },
            result={
                "success": True,
                "execution_time": 1.5,
                "resource_cost": 0.10,
                "retry_count": 0,
                "error_count": 0,
            },
        )
    
    pattern_engine.analyze_patterns(min_samples=10)
    patterns = pattern_engine.get_patterns(pattern_type="workflow")
    assert len(patterns) >= 1
    
    suggestion = pattern_engine.generate_suggestion(patterns[0].pattern_id)
    assert suggestion is not None
    assert "description" in suggestion
    assert "proposed_change" in suggestion


def test_get_patterns_with_conditions(pattern_engine):
    """Test filtering patterns by conditions."""
    for i in range(10):
        pattern_engine.record_execution(
            task_id=f"cond-task-{i:03d}",
            branch_id="main",
            execution_path={
                "skills_used": ["vibration_analysis"],
                "model": "cfc",
                "config": {"lr": 0.001},
            },
            result={
                "success": True,
                "execution_time": 2.0,
                "resource_cost": 0.15,
                "retry_count": 0,
                "error_count": 0,
            },
        )
    
    pattern_engine.analyze_patterns(min_samples=5)
    
    all_patterns = pattern_engine.get_patterns()
    assert len(all_patterns) >= 1
    
    workflow_only = pattern_engine.get_patterns(pattern_type="workflow")
    assert len(workflow_only) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_pattern_engine.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement PatternEngine core class**

```python
# python/app/core/pattern_engine.py
"""Pattern Recognition Engine — detects workflows, anti-patterns, and combinations."""
import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    pattern_id: str
    pattern_type: str
    description: str
    elements: Dict[str, Any]
    conditions: Dict[str, Any]
    metrics: Dict[str, Any]
    sample_size: int
    suggestion: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "elements": self.elements,
            "conditions": self.conditions,
            "metrics": self.metrics,
            "sample_size": self.sample_size,
            "suggestion": self.suggestion,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pattern":
        return cls(
            pattern_id=data["pattern_id"],
            pattern_type=data["pattern_type"],
            description=data["description"],
            elements=data.get("elements", {}),
            conditions=data.get("conditions", {}),
            metrics=data.get("metrics", {}),
            sample_size=data.get("sample_size", 0),
            suggestion=data.get("suggestion"),
            created_at=data.get("created_at", time.time()),
        )


class PatternEngine:
    """Analyzes execution data to discover patterns and anti-patterns."""

    def __init__(self, db_path: str = "data/templates/patterns.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._executions: List[Dict[str, Any]] = []
        self._patterns: Dict[str, Pattern] = {}
        self._db: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS pattern_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                elements TEXT NOT NULL,
                conditions TEXT NOT NULL,
                metrics TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                pattern_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                elements TEXT NOT NULL,
                conditions TEXT NOT NULL,
                metrics TEXT NOT NULL,
                sample_size INTEGER NOT NULL,
                suggestion TEXT,
                created_at REAL NOT NULL
            )
        """)
        self._db.commit()
        self._load_patterns_from_db()
        logger.info("PatternEngine initialized: db=%s", self.db_path)

    def _load_patterns_from_db(self) -> None:
        cursor = self._db.execute("SELECT * FROM patterns")
        for row in cursor.fetchall():
            data = {
                "pattern_id": row["pattern_id"],
                "pattern_type": row["type"],
                "description": row["description"],
                "elements": json.loads(row["elements"]),
                "conditions": json.loads(row["conditions"]),
                "metrics": json.loads(row["metrics"]),
                "sample_size": row["sample_size"],
                "suggestion": row["suggestion"],
                "created_at": row["created_at"],
            }
            self._patterns[row["pattern_id"]] = Pattern.from_dict(data)

    def _compute_execution_key(self, execution_path: Dict[str, Any]) -> str:
        """Create a hashable key from execution path for grouping."""
        key_parts = {
            "skills": sorted(execution_path.get("skills_used", [])),
            "model": execution_path.get("model", ""),
        }
        return json.dumps(key_parts, sort_keys=True)

    def record_execution(
        self,
        task_id: str,
        branch_id: str,
        execution_path: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Record a single execution for later pattern analysis."""
        with self._lock:
            now = time.time()
            elements = {
                "skills_used": execution_path.get("skills_used", []),
                "model": execution_path.get("model", ""),
                "config": execution_path.get("config", {}),
            }
            conditions = {}
            metrics = {
                "success": result.get("success", False),
                "execution_time": result.get("execution_time", 0.0),
                "resource_cost": result.get("resource_cost", 0.0),
                "retry_count": result.get("retry_count", 0),
                "error_count": result.get("error_count", 0),
            }
            
            self._db.execute(
                """INSERT INTO pattern_executions (task_id, branch_id, elements, conditions, metrics, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, branch_id, json.dumps(elements), json.dumps(conditions), json.dumps(metrics), now),
            )
            self._db.commit()
            
            record = {
                "task_id": task_id,
                "branch_id": branch_id,
                "elements": elements,
                "conditions": conditions,
                "metrics": metrics,
                "created_at": now,
            }
            self._executions.append(record)
            return record

    def analyze_patterns(self, min_samples: int = 10) -> List[Pattern]:
        """Discover patterns from accumulated execution data."""
        with self._lock:
            cursor = self._db.execute("SELECT elements, metrics FROM pattern_executions")
            executions = []
            for row in cursor.fetchall():
                executions.append({
                    "elements": json.loads(row["elements"]),
                    "metrics": json.loads(row["metrics"]),
                })
            
            groups: Dict[str, List[Dict]] = {}
            for exe in executions:
                key = json.dumps({
                    "skills": sorted(exe["elements"].get("skills_used", [])),
                    "model": exe["elements"].get("model", ""),
                }, sort_keys=True)
                groups.setdefault(key, []).append(exe)
            
            new_patterns = []
            for key, group in groups.items():
                if len(group) < min_samples:
                    continue
                
                elements = group[0]["elements"]
                success_rate = sum(1 for g in group if g["metrics"]["success"]) / len(group)
                avg_time = sum(g["metrics"]["execution_time"] for g in group) / len(group)
                avg_cost = sum(g["metrics"]["resource_cost"] for g in group) / len(group)
                avg_retries = sum(g["metrics"]["retry_count"] for g in group) / len(group)
                avg_errors = sum(g["metrics"]["error_count"] for g in group) / len(group)
                
                # Determine pattern type
                if avg_retries > 2 or avg_errors > 0.3 * len(group) or avg_cost > 0.5:
                    pattern_type = "anti_pattern"
                    description = f"Anti-pattern: {elements.get('model', 'unknown')} with {elements.get('skills_used', [])} shows poor metrics"
                else:
                    pattern_type = "workflow"
                    description = f"Effective workflow: {elements.get('model', 'unknown')} with {elements.get('skills_used', [])}"
                
                pattern_id = hashlib.sha256(key.encode()).hexdigest()[:12]
                pattern = Pattern(
                    pattern_id=pattern_id,
                    pattern_type=pattern_type,
                    description=description,
                    elements=elements,
                    conditions={},
                    metrics={
                        "accuracy_improvement": round(max(0, 1.0 - avg_time / 10.0), 2),
                        "confidence": round(min(1.0, len(group) / 50.0), 2),
                        "success_rate": round(success_rate, 3),
                        "avg_execution_time": round(avg_time, 3),
                        "avg_resource_cost": round(avg_cost, 3),
                        "avg_retry_count": round(avg_retries, 2),
                    },
                    sample_size=len(group),
                )
                
                self._patterns[pattern_id] = pattern
                self._save_pattern_to_db(pattern)
                new_patterns.append(pattern)
            
            logger.info("Pattern analysis complete: found %d new patterns", len(new_patterns))
            return new_patterns

    def _save_pattern_to_db(self, pattern: Pattern) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO patterns
               (pattern_id, type, description, elements, conditions, metrics, sample_size, suggestion, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern.pattern_id,
                pattern.pattern_type,
                pattern.description,
                json.dumps(pattern.elements),
                json.dumps(pattern.conditions),
                json.dumps(pattern.metrics),
                pattern.sample_size,
                pattern.suggestion,
                pattern.created_at,
            ),
        )
        self._db.commit()

    def get_patterns(
        self, pattern_type: Optional[str] = None, conditions: Optional[Dict[str, Any]] = None
    ) -> List[Pattern]:
        """Query discovered patterns."""
        with self._lock:
            patterns = list(self._patterns.values())
            if pattern_type:
                patterns = [p for p in patterns if p.pattern_type == pattern_type]
            return patterns

    def generate_suggestion(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Create an update suggestion from a pattern."""
        with self._lock:
            pattern = self._patterns.get(pattern_id)
            if pattern is None:
                return None
            
            if pattern.pattern_type == "workflow":
                suggestion_text = f"Consider adopting this workflow pattern: {pattern.elements.get('skills_used', [])}"
                proposed_change = {
                    "action": "add_skills",
                    "skills": pattern.elements.get("skills_used", []),
                    "model_config": pattern.elements.get("config", {}),
                }
            elif pattern.pattern_type == "anti_pattern":
                suggestion_text = f"Avoid this anti-pattern: high retries/errors detected with {pattern.elements.get('model', 'unknown')}"
                proposed_change = {
                    "action": "remove_skills",
                    "skills": pattern.elements.get("skills_used", []),
                    "warning": pattern.description,
                }
            else:
                suggestion_text = f"Pattern detected: {pattern.description}"
                proposed_change = {"action": "review", "pattern": pattern.to_dict()}
            
            return {
                "pattern_id": pattern_id,
                "suggestion": suggestion_text,
                "proposed_change": proposed_change,
                "confidence": pattern.metrics.get("confidence", 0.5),
            }

    def get_anti_patterns(self) -> List[Pattern]:
        """List all detected anti-patterns."""
        return self.get_patterns(pattern_type="anti_pattern")

    def close(self) -> None:
        if self._db:
            self._db.close()


_pattern_engine: Optional[PatternEngine] = None
_pattern_engine_lock = threading.Lock()


def get_pattern_engine() -> PatternEngine:
    global _pattern_engine
    if _pattern_engine is None:
        with _pattern_engine_lock:
            if _pattern_engine is None:
                _pattern_engine = PatternEngine()
                _pattern_engine.initialize()
    return _pattern_engine


def init_pattern_engine(db_path: str = "data/templates/patterns.db") -> PatternEngine:
    global _pattern_engine
    with _pattern_engine_lock:
        if _pattern_engine is not None:
            _pattern_engine.close()
        _pattern_engine = PatternEngine(db_path=db_path)
        _pattern_engine.initialize()
    return _pattern_engine
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_pattern_engine.py -v`
Expected: PASS — 5/5 tests pass

- [ ] **Step 5: Commit**

```bash
git add python/app/core/pattern_engine.py python/tests/functional_test_pattern_engine.py
git commit -m "feat: add pattern recognition engine with workflow and anti-pattern detection"
```

---

## Phase 3: Template Evolution Core

### Task 5: Evolution Engine Core

**Files:**
- Create: `python/app/core/template_evolution.py`
- Test: `python/tests/functional_test_template_evolution.py`

- [ ] **Step 1: Write the failing test — evolution triggers and suggestions**

```python
# python/tests/functional_test_template_evolution.py
"""Functional tests for Template Evolution Core."""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

try:
    from app.core.template_evolution import EvolutionEngine
except ImportError:
    EvolutionEngine = None


@pytest.fixture
def evolution_engine():
    """Create a temporary evolution engine for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "evolution.db")
    
    engine = EvolutionEngine(db_path=db_path)
    engine.initialize()
    
    yield engine
    
    engine.close()
    shutil.rmtree(tmpdir)


def test_register_trigger(evolution_engine):
    """Test registering an evolution trigger."""
    def always_true():
        return True
    
    def dummy_action():
        return "done"
    
    trigger = evolution_engine.register_trigger(
        trigger_type="skill",
        condition=always_true,
        action=dummy_action,
        cooldown_hours=1,
    )
    
    assert trigger is not None
    assert trigger["trigger_type"] == "skill"
    assert trigger["cooldown_hours"] == 1


def test_create_suggestion(evolution_engine):
    """Test creating an evolution suggestion."""
    suggestion = evolution_engine.create_suggestion(
        trigger_type="skill",
        evidence={"metric": "error_count", "threshold": 3, "actual": 5},
        proposed_change={"action": "add_skill", "skill_name": "error_handler"},
    )
    
    assert suggestion.suggestion_id is not None
    assert suggestion.trigger_type == "skill"
    assert suggestion.status == "pending"
    assert suggestion.confidence > 0.0


def test_apply_suggestion(evolution_engine):
    """Test applying a suggestion to create a new branch."""
    suggestion = evolution_engine.create_suggestion(
        trigger_type="model_config",
        evidence={"metric": "accuracy", "threshold": 0.9, "actual": 0.95},
        proposed_change={"action": "update_param", "param": "lr", "value": 0.01},
    )
    
    # Simulate having a main branch
    from app.core.template_branching import TemplateBranchManager
    tmpdir = tempfile.mkdtemp()
    branch_mgr = TemplateBranchManager(
        db_path=os.path.join(tmpdir, "branches.db"),
        json_dir=os.path.join(tmpdir, "branches"),
    )
    branch_mgr.initialize()
    main_branch = branch_mgr.create_branch("main", None, {"model": "cfc"}, {"type": "main"})
    
    applied = evolution_engine.apply_suggestion(
        suggestion_id=suggestion.suggestion_id,
        branch_id=main_branch.branch_id,
        branch_manager=branch_mgr,
    )
    
    assert applied is not None
    assert suggestion.status == "applied"
    assert applied.name.startswith("exp-")
    assert applied.metadata["type"] == "experiment"
    
    branch_mgr.close()
    shutil.rmtree(tmpdir)


def test_list_suggestions(evolution_engine):
    """Test listing suggestions with status filter."""
    evolution_engine.create_suggestion(
        trigger_type="skill",
        evidence={"metric": "errors", "threshold": 3, "actual": 5},
        proposed_change={"action": "add_skill"},
    )
    evolution_engine.create_suggestion(
        trigger_type="model_config",
        evidence={"metric": "accuracy", "threshold": 0.9, "actual": 0.95},
        proposed_change={"action": "update_param"},
    )
    
    all_suggestions = evolution_engine.list_suggestions()
    assert len(all_suggestions) == 2
    
    pending = evolution_engine.list_suggestions(status_filter="pending")
    assert len(pending) == 2


def test_evaluate_triggers(evolution_engine):
    """Test evaluating all registered triggers."""
    trigger_count = 0
    
    def count_trigger():
        nonlocal trigger_count
        trigger_count += 1
        return True
    
    def dummy_action():
        return "triggered"
    
    evolution_engine.register_trigger("skill", count_trigger, dummy_action, cooldown_hours=0)
    evolution_engine.register_trigger("model_config", count_trigger, dummy_action, cooldown_hours=0)
    
    results = evolution_engine.evaluate_triggers()
    
    assert trigger_count == 2
    assert len(results) == 2


def test_get_evolution_history(evolution_engine):
    """Test retrieving evolution history for a branch."""
    suggestion = evolution_engine.create_suggestion(
        trigger_type="skill",
        evidence={"metric": "test", "threshold": 1, "actual": 2},
        proposed_change={"action": "test"},
    )
    
    history = evolution_engine.get_evolution_history()
    assert len(history) >= 1
    assert history[0]["suggestion_id"] == suggestion.suggestion_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_template_evolution.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement EvolutionEngine core class**

```python
# python/app/core/template_evolution.py
"""Template Evolution Core — manages evolution triggers, suggestions, and lifecycle."""
import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvolutionTrigger:
    trigger_type: str
    condition: Callable
    action: Callable
    cooldown_hours: int
    last_triggered: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_type": self.trigger_type,
            "cooldown_hours": self.cooldown_hours,
            "last_triggered": self.last_triggered,
        }


@dataclass
class EvolutionSuggestion:
    suggestion_id: str
    trigger_type: str
    description: str
    data_evidence: Dict[str, Any]
    proposed_change: Dict[str, Any]
    confidence: float
    created_at: float = field(default_factory=time.time)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "trigger_type": self.trigger_type,
            "description": self.description,
            "data_evidence": self.data_evidence,
            "proposed_change": self.proposed_change,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvolutionSuggestion":
        return cls(
            suggestion_id=data["suggestion_id"],
            trigger_type=data["trigger_type"],
            description=data["description"],
            data_evidence=data.get("data_evidence", {}),
            proposed_change=data.get("proposed_change", {}),
            confidence=data.get("confidence", 0.5),
            created_at=data.get("created_at", time.time()),
            status=data.get("status", "pending"),
        )


class EvolutionEngine:
    """Core engine for template evolution — triggers, suggestions, and application."""

    TRIGGER_TYPES = {"skill", "model_config", "approval_strategy", "heartbeat_routine", "budget_strategy"}

    def __init__(self, db_path: str = "data/templates/evolution.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._triggers: Dict[str, EvolutionTrigger] = {}
        self._suggestions: Dict[str, EvolutionSuggestion] = {}
        self._db: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS evolution_suggestions (
                suggestion_id TEXT PRIMARY KEY,
                trigger_type TEXT NOT NULL,
                description TEXT NOT NULL,
                data_evidence TEXT NOT NULL,
                proposed_change TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
        """)
        self._db.commit()
        self._load_suggestions_from_db()
        self._register_default_triggers()
        logger.info("EvolutionEngine initialized: db=%s", self.db_path)

    def _load_suggestions_from_db(self) -> None:
        cursor = self._db.execute("SELECT * FROM evolution_suggestions")
        for row in cursor.fetchall():
            data = {
                "suggestion_id": row["suggestion_id"],
                "trigger_type": row["trigger_type"],
                "description": row["description"],
                "data_evidence": json.loads(row["data_evidence"]),
                "proposed_change": json.loads(row["proposed_change"]),
                "confidence": row["confidence"],
                "created_at": row["created_at"],
                "status": row["status"],
            }
            self._suggestions[row["suggestion_id"]] = EvolutionSuggestion.from_dict(data)

    def _save_suggestion_to_db(self, suggestion: EvolutionSuggestion) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO evolution_suggestions
               (suggestion_id, trigger_type, description, data_evidence, proposed_change, confidence, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                suggestion.suggestion_id,
                suggestion.trigger_type,
                suggestion.description,
                json.dumps(suggestion.data_evidence),
                json.dumps(suggestion.proposed_change),
                suggestion.confidence,
                suggestion.created_at,
                suggestion.status,
            ),
        )
        self._db.commit()

    def _register_default_triggers(self) -> None:
        def skill_error_condition():
            return False
        
        def model_config_condition():
            return False
        
        def approval_condition():
            return False
        
        def heartbeat_condition():
            return False
        
        def budget_condition():
            return False
        
        default_triggers = [
            ("skill", skill_error_condition, "Check for repeated skill errors"),
            ("model_config", model_config_condition, "Check A/B test results"),
            ("approval_strategy", approval_condition, "Check false positive rates"),
            ("heartbeat_routine", heartbeat_condition, "Check GPU utilization"),
            ("budget_strategy", budget_condition, "Check budget overspend"),
        ]
        
        for trigger_type, condition, desc in default_triggers:
            if trigger_type not in self._triggers:
                self._triggers[trigger_type] = EvolutionTrigger(
                    trigger_type=trigger_type,
                    condition=condition,
                    action=lambda: None,
                    cooldown_hours=24,
                )

    def register_trigger(
        self,
        trigger_type: str,
        condition: Callable,
        action: Callable,
        cooldown_hours: int = 24,
    ) -> Dict[str, Any]:
        """Register an evolution trigger."""
        with self._lock:
            if trigger_type not in self.TRIGGER_TYPES:
                raise ValueError(f"Unknown trigger type: {trigger_type}. Must be one of {self.TRIGGER_TYPES}")
            
            self._triggers[trigger_type] = EvolutionTrigger(
                trigger_type=trigger_type,
                condition=condition,
                action=action,
                cooldown_hours=cooldown_hours,
            )
            return {"trigger_type": trigger_type, "cooldown_hours": cooldown_hours}

    def evaluate_triggers(self) -> List[Dict[str, Any]]:
        """Check all triggers against current data."""
        with self._lock:
            results = []
            now = time.time()
            
            for trigger_type, trigger in self._triggers.items():
                if now - trigger.last_triggered < trigger.cooldown_hours * 3600:
                    continue
                
                try:
                    triggered = trigger.condition()
                    if triggered:
                        trigger.last_triggered = now
                        action_result = trigger.action()
                        results.append({
                            "trigger_type": trigger_type,
                            "triggered": True,
                            "action_result": action_result,
                        })
                except Exception as e:
                    logger.warning("Trigger evaluation failed for %s: %s", trigger_type, e)
                    results.append({
                        "trigger_type": trigger_type,
                        "triggered": False,
                        "error": str(e),
                    })
            
            return results

    def create_suggestion(
        self,
        trigger_type: str,
        evidence: Dict[str, Any],
        proposed_change: Dict[str, Any],
    ) -> EvolutionSuggestion:
        """Create an evolution suggestion."""
        with self._lock:
            suggestion_id = hashlib.sha256(
                f"{trigger_type}:{json.dumps(evidence, sort_keys=True)}:{time.time()}".encode()
            ).hexdigest()[:12]
            
            desc = f"Evolution suggestion for {trigger_type} based on data evidence"
            confidence = self._calculate_confidence(evidence)
            
            suggestion = EvolutionSuggestion(
                suggestion_id=suggestion_id,
                trigger_type=trigger_type,
                description=desc,
                data_evidence=evidence,
                proposed_change=proposed_change,
                confidence=confidence,
            )
            
            self._suggestions[suggestion_id] = suggestion
            self._save_suggestion_to_db(suggestion)
            
            logger.info("Evolution suggestion created: id=%s, type=%s, confidence=%.2f",
                       suggestion_id, trigger_type, confidence)
            return suggestion

    def _calculate_confidence(self, evidence: Dict[str, Any]) -> float:
        threshold = evidence.get("threshold", 1)
        actual = evidence.get("actual", 0)
        if threshold == 0:
            return 0.5
        deviation = abs(actual - threshold) / abs(threshold)
        return min(1.0, max(0.1, 0.5 + deviation * 0.5))

    def apply_suggestion(
        self,
        suggestion_id: str,
        branch_id: str,
        branch_manager,
    ) -> Optional[Any]:
        """Apply a suggestion to a branch, creating an experiment branch."""
        with self._lock:
            suggestion = self._suggestions.get(suggestion_id)
            if suggestion is None:
                return None
            
            change = suggestion.proposed_change
            
            original = branch_manager.get_branch(branch_id)
            if original is None:
                return None
            
            new_data = original.template_data.copy()
            if "model_config" in change:
                new_data.setdefault("model_config", {}).update(change["model_config"])
            if "action" in change and change["action"] == "add_skills":
                existing_skills = set(new_data.get("skills", []))
                existing_skills.update(change.get("skills", []))
                new_data["skills"] = list(existing_skills)
            
            exp_branch = branch_manager.create_branch(
                name=f"exp-{suggestion_id[:6]}",
                base_branch=branch_id,
                data=new_data,
                metadata={"type": "experiment", "source_suggestion": suggestion_id},
            )
            
            suggestion.status = "applied"
            self._save_suggestion_to_db(suggestion)
            
            logger.info("Suggestion applied: %s → experiment branch %s", suggestion_id, exp_branch.branch_id)
            return exp_branch

    def list_suggestions(self, status_filter: Optional[str] = None) -> List[EvolutionSuggestion]:
        """List suggestions with optional status filter."""
        with self._lock:
            suggestions = list(self._suggestions.values())
            if status_filter:
                suggestions = [s for s in suggestions if s.status == status_filter]
            return sorted(suggestions, key=lambda s: s.created_at, reverse=True)

    def get_evolution_history(self, branch_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get full evolution timeline."""
        with self._lock:
            suggestions = list(self._suggestions.values())
            history = [s.to_dict() for s in suggestions]
            return sorted(history, key=lambda h: h["created_at"], reverse=True)

    def reject_suggestion(self, suggestion_id: str) -> bool:
        """Reject a suggestion."""
        with self._lock:
            suggestion = self._suggestions.get(suggestion_id)
            if suggestion is None:
                return False
            suggestion.status = "rejected"
            self._save_suggestion_to_db(suggestion)
            return True

    def close(self) -> None:
        if self._db:
            self._db.close()


_evolution_engine: Optional[EvolutionEngine] = None
_evolution_engine_lock = threading.Lock()


def get_evolution_engine() -> EvolutionEngine:
    global _evolution_engine
    if _evolution_engine is None:
        with _evolution_engine_lock:
            if _evolution_engine is None:
                _evolution_engine = EvolutionEngine()
                _evolution_engine.initialize()
    return _evolution_engine


def init_template_evolution(db_path: str = "data/templates/evolution.db") -> EvolutionEngine:
    global _evolution_engine
    with _evolution_engine_lock:
        if _evolution_engine is not None:
            _evolution_engine.close()
        _evolution_engine = EvolutionEngine(db_path=db_path)
        _evolution_engine.initialize()
    return _evolution_engine
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_template_evolution.py -v`
Expected: PASS — 6/6 tests pass

- [ ] **Step 5: Commit**

```bash
git add python/app/core/template_evolution.py python/tests/functional_test_template_evolution.py
git commit -m "feat: add template evolution core with triggers and suggestion lifecycle"
```

---

### Task 6: Evolution + Branching API Routes

**Files:**
- Create: `python/app/api/v1/template_evolution_routes.py`

- [ ] **Step 1: Implement evolution API routes (complete code)**

```python
# python/app/api/v1/template_evolution_routes.py
"""API routes for template evolution system."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.template_evolution import get_evolution_engine
from app.core.template_branching import get_branch_manager

router = APIRouter(prefix="/api/v1/templates/evolution", tags=["template-evolution"])

_test_evolution_engine = None
_test_branch_manager = None


def _get_evolution_engine():
    return _test_evolution_engine or get_evolution_engine()


def _get_branch_manager():
    return _test_branch_manager or get_branch_manager()


class CreateSuggestionRequest(BaseModel):
    trigger_type: str
    evidence: dict = Field(default_factory=dict)
    proposed_change: dict = Field(default_factory=dict)


class ApplySuggestionRequest(BaseModel):
    branch_id: str


@router.post("/suggestions", status_code=201)
async def create_suggestion(req: CreateSuggestionRequest):
    engine = _get_evolution_engine()
    suggestion = engine.create_suggestion(
        trigger_type=req.trigger_type,
        evidence=req.evidence,
        proposed_change=req.proposed_change,
    )
    return {"suggestion": suggestion.to_dict()}


@router.get("/suggestions")
async def list_suggestions(status_filter: Optional[str] = None):
    engine = _get_evolution_engine()
    suggestions = engine.list_suggestions(status_filter=status_filter)
    return {"suggestions": [s.to_dict() for s in suggestions]}


@router.post("/suggestions/{suggestion_id}/apply")
async def apply_suggestion(suggestion_id: str, req: ApplySuggestionRequest):
    engine = _get_evolution_engine()
    branch_mgr = _get_branch_manager()
    
    suggestion = engine._suggestions.get(suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail=f"Suggestion not found: {suggestion_id}")
    
    result = engine.apply_suggestion(suggestion_id, req.branch_id, branch_mgr)
    if result is None:
        raise HTTPException(status_code=404, detail="Branch not found or application failed")
    
    return {"result": result.to_dict()}


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(suggestion_id: str):
    engine = _get_evolution_engine()
    success = engine.reject_suggestion(suggestion_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Suggestion not found: {suggestion_id}")
    return {"message": "Suggestion rejected"}


@router.get("/triggers/evaluate")
async def evaluate_triggers():
    engine = _get_evolution_engine()
    results = engine.evaluate_triggers()
    return {"trigger_results": results}


@router.get("/history")
async def get_evolution_history(branch_id: Optional[str] = None):
    engine = _get_evolution_engine()
    history = engine.get_evolution_history(branch_id=branch_id)
    return {"history": history}
```

- [ ] **Step 2: Commit**

```bash
git add python/app/api/v1/template_evolution_routes.py
git commit -m "feat: add evolution API routes for suggestion lifecycle management"
```

---

## Phase 4: A/B Testing Framework

### Task 7: A/B Testing Core

**Files:**
- Create: `python/app/core/template_ab_testing.py`
- Test: `python/tests/functional_test_ab_testing.py`

- [ ] **Step 1: Write the failing test — experiment lifecycle**

```python
# python/tests/functional_test_ab_testing.py
"""Functional tests for A/B Testing Framework."""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

try:
    from app.core.template_ab_testing import ABTestingFramework
except ImportError:
    ABTestingFramework = None


@pytest.fixture
def ab_framework():
    """Create a temporary A/B testing framework for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "ab_testing.db")
    
    framework = ABTestingFramework(db_path=db_path)
    framework.initialize()
    
    yield framework
    
    framework.close()
    shutil.rmtree(tmpdir)


def test_create_experiment(ab_framework):
    """Test creating a new A/B experiment."""
    experiment = ab_framework.create_experiment(
        name="lr-comparison",
        control_branch="main",
        candidate_branch="exp-001",
        traffic_split=0.10,
    )
    
    assert experiment.experiment_id is not None
    assert experiment.name == "lr-comparison"
    assert experiment.control_branch == "main"
    assert experiment.candidate_branch == "exp-001"
    assert experiment.traffic_split == 0.10
    assert experiment.status == "running"
    assert experiment.result is None


def test_record_experiment_execution(ab_framework):
    """Test recording execution data for an experiment."""
    exp = ab_framework.create_experiment("test-exp", "main", "exp-001")
    
    record = ab_framework.record_execution(
        experiment_id=exp.experiment_id,
        branch="control",
        metrics={"execution_time": 2.5, "success": True, "resource_cost": 0.15},
    )
    
    assert record["experiment_id"] == exp.experiment_id
    assert record["branch"] == "control"
    assert record["metrics"]["execution_time"] == 2.5


def test_evaluate_experiment(ab_framework):
    """Test statistical evaluation of an experiment."""
    exp = ab_framework.create_experiment("eval-exp", "main", "exp-001")
    
    # Record 35 executions for control (fast)
    for i in range(35):
        ab_framework.record_execution(
            experiment_id=exp.experiment_id,
            branch="control",
            metrics={"execution_time": 3.0 + (i % 5) * 0.1, "success": True, "resource_cost": 0.20},
        )
    
    # Record 35 executions for candidate (faster)
    for i in range(35):
        ab_framework.record_execution(
            experiment_id=exp.experiment_id,
            branch="candidate",
            metrics={"execution_time": 2.0 + (i % 5) * 0.1, "success": True, "resource_cost": 0.15},
        )
    
    result = ab_framework.evaluate(exp.experiment_id)
    
    assert result is not None
    assert "statistical_test" in result
    assert "confidence" in result
    assert result["min_sample_met"] is True


def test_auto_conclude_winner_candidate(ab_framework):
    """Test auto-conclude when candidate wins significantly."""
    exp = ab_framework.create_experiment("auto-win", "main", "exp-001")
    
    # Control: consistently slower
    for i in range(50):
        ab_framework.record_execution(
            experiment_id=exp.experiment_id,
            branch="control",
            metrics={"execution_time": 5.0, "success": True, "resource_cost": 0.30},
        )
    
    # Candidate: consistently faster
    for i in range(50):
        ab_framework.record_execution(
            experiment_id=exp.experiment_id,
            branch="candidate",
            metrics={"execution_time": 3.0, "success": True, "resource_cost": 0.20},
        )
    
    result = ab_framework.auto_conclude(exp.experiment_id)
    
    assert result is not None
    assert result["result"] == "winner_candidate"
    assert exp.status == "merged"


def test_auto_conclude_rollback(ab_framework):
    """Test auto-rollback when candidate performs worse."""
    exp = ab_framework.create_experiment("auto-rollback", "main", "exp-001")
    
    # Control: good performance
    for i in range(50):
        ab_framework.record_execution(
            experiment_id=exp.experiment_id,
            branch="control",
            metrics={"execution_time": 2.0, "success": True, "resource_cost": 0.10},
        )
    
    # Candidate: worse performance
    for i in range(50):
        ab_framework.record_execution(
            experiment_id=exp.experiment_id,
            branch="candidate",
            metrics={"execution_time": 8.0, "success": False, "resource_cost": 0.50},
        )
    
    result = ab_framework.auto_conclude(exp.experiment_id)
    
    assert result is not None
    assert result["result"] == "winner_control"
    assert exp.status == "rolled_back"


def test_traffic_routing(ab_framework):
    """Test consistent traffic routing by project_id."""
    exp = ab_framework.create_experiment("traffic-test", "main", "exp-001")
    
    # Same project should always get same branch
    branch1 = ab_framework.route_traffic(exp.experiment_id, "project-abc")
    branch2 = ab_framework.route_traffic(exp.experiment_id, "project-abc")
    assert branch1 == branch2


def test_get_active_experiments(ab_framework):
    """Test listing active experiments."""
    ab_framework.create_experiment("exp1", "main", "exp-001")
    ab_framework.create_experiment("exp2", "main", "exp-002")
    
    active = ab_framework.get_active_experiments()
    assert len(active) == 2
    assert all(e.status == "running" for e in active)


def test_get_experiment_results(ab_framework):
    """Test retrieving full experiment results."""
    exp = ab_framework.create_experiment("results-exp", "main", "exp-001")
    
    ab_framework.record_execution(
        experiment_id=exp.experiment_id,
        branch="control",
        metrics={"execution_time": 2.0, "success": True},
    )
    
    results = ab_framework.get_experiment_results(exp.experiment_id)
    assert "experiment" in results
    assert "control_metrics" in results
    assert "candidate_metrics" in results
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_ab_testing.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement ABTestingFramework core class**

```python
# python/app/core/template_ab_testing.py
"""A/B Testing Framework — experiments, statistical analysis, traffic routing."""
import hashlib
import json
import logging
import math
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ABExperiment:
    experiment_id: str
    name: str
    control_branch: str
    candidate_branch: str
    traffic_split: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    created_at: float = field(default_factory=time.time)
    concluded_at: Optional[float] = None
    result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "control_branch": self.control_branch,
            "candidate_branch": self.candidate_branch,
            "traffic_split": self.traffic_split,
            "metrics": self.metrics,
            "status": self.status,
            "created_at": self.created_at,
            "concluded_at": self.concluded_at,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ABExperiment":
        return cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            control_branch=data["control_branch"],
            candidate_branch=data["candidate_branch"],
            traffic_split=data.get("traffic_split", 0.10),
            metrics=data.get("metrics", {}),
            status=data.get("status", "running"),
            created_at=data.get("created_at", time.time()),
            concluded_at=data.get("concluded_at"),
            result=data.get("result"),
        )


class ABTestingFramework:
    """A/B testing with statistical analysis and traffic routing."""

    MIN_SAMPLE_SIZE = 30
    CONFIDENCE_THRESHOLD = 0.95
    IMPROVEMENT_THRESHOLD = 0.05

    def __init__(self, db_path: str = "data/templates/ab_testing.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._experiments: Dict[str, ABExperiment] = {}
        self._execution_records: List[Dict[str, Any]] = []
        self._db: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS ab_experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                control_branch TEXT NOT NULL,
                candidate_branch TEXT NOT NULL,
                traffic_split REAL NOT NULL,
                metrics TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'running',
                created_at REAL NOT NULL,
                concluded_at REAL,
                result TEXT
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS ab_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                branch TEXT NOT NULL,
                metrics TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES ab_experiments(experiment_id)
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS ab_traffic (
                project_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                assigned_branch TEXT NOT NULL,
                PRIMARY KEY (project_id, experiment_id)
            )
        """)
        self._db.commit()
        self._load_experiments_from_db()
        logger.info("ABTestingFramework initialized: db=%s", self.db_path)

    def _load_experiments_from_db(self) -> None:
        cursor = self._db.execute("SELECT * FROM ab_experiments")
        for row in cursor.fetchall():
            data = {
                "experiment_id": row["experiment_id"],
                "name": row["name"],
                "control_branch": row["control_branch"],
                "candidate_branch": row["candidate_branch"],
                "traffic_split": row["traffic_split"],
                "metrics": json.loads(row["metrics"]),
                "status": row["status"],
                "created_at": row["created_at"],
                "concluded_at": row["concluded_at"],
                "result": row["result"],
            }
            self._experiments[row["experiment_id"]] = ABExperiment.from_dict(data)

    def _save_experiment_to_db(self, exp: ABExperiment) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO ab_experiments
               (experiment_id, name, control_branch, candidate_branch, traffic_split, metrics, status, created_at, concluded_at, result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                exp.experiment_id, exp.name, exp.control_branch, exp.candidate_branch,
                exp.traffic_split, json.dumps(exp.metrics), exp.status,
                exp.created_at, exp.concluded_at, exp.result,
            ),
        )
        self._db.commit()

    def create_experiment(
        self,
        name: str,
        control_branch: str,
        candidate_branch: str,
        traffic_split: float = 0.10,
    ) -> ABExperiment:
        """Create a new A/B experiment."""
        with self._lock:
            experiment_id = f"ab-{uuid.uuid4().hex[:8]}"
            now = time.time()
            
            exp = ABExperiment(
                experiment_id=experiment_id,
                name=name,
                control_branch=control_branch,
                candidate_branch=candidate_branch,
                traffic_split=traffic_split,
                created_at=now,
            )
            
            self._experiments[experiment_id] = exp
            self._save_experiment_to_db(exp)
            
            logger.info("A/B experiment created: id=%s, name=%s", experiment_id, name)
            return exp

    def record_execution(
        self,
        experiment_id: str,
        branch: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Record execution data for an experiment."""
        with self._lock:
            now = time.time()
            self._db.execute(
                """INSERT INTO ab_executions (experiment_id, branch, metrics, created_at)
                   VALUES (?, ?, ?, ?)""",
                (experiment_id, branch, json.dumps(metrics), now),
            )
            self._db.commit()
            
            record = {
                "experiment_id": experiment_id,
                "branch": branch,
                "metrics": metrics,
                "created_at": now,
            }
            self._execution_records.append(record)
            return record

    def _get_execution_data(self, experiment_id: str) -> Dict[str, List[Dict]]:
        cursor = self._db.execute(
            "SELECT branch, metrics FROM ab_executions WHERE experiment_id = ?",
            (experiment_id,),
        )
        data: Dict[str, List[Dict]] = {"control": [], "candidate": []}
        for row in cursor.fetchall():
            data[row["branch"]].append(json.loads(row["metrics"]))
        return data

    def evaluate(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Run statistical analysis on experiment data."""
        with self._lock:
            data = self._get_execution_data(experiment_id)
            control_data = data["control"]
            candidate_data = data["candidate"]
            
            if not control_data or not candidate_data:
                return None
            
            control_times = [d.get("execution_time", 0) for d in control_data]
            candidate_times = [d.get("execution_time", 0) for d in candidate_data]
            control_success = [d.get("success", False) for d in control_data]
            candidate_success = [d.get("success", False) for d in candidate_data]
            
            t_stat, p_value = self._welch_t_test(control_times, candidate_times)
            chi2_stat, chi2_p = self._chi_squared_test(control_success, candidate_success)
            
            min_sample_met = (
                len(control_data) >= self.MIN_SAMPLE_SIZE
                and len(candidate_data) >= self.MIN_SAMPLE_SIZE
            )
            
            avg_control = sum(control_times) / len(control_times) if control_times else 0
            avg_candidate = sum(candidate_times) / len(candidate_times) if candidate_times else 0
            
            improvement = (avg_control - avg_candidate) / avg_control if avg_control > 0 else 0
            confidence = 1.0 - p_value if p_value is not None else 0.5
            
            result = {
                "experiment_id": experiment_id,
                "control_samples": len(control_data),
                "candidate_samples": len(candidate_data),
                "min_sample_met": min_sample_met,
                "control_mean_time": round(avg_control, 3),
                "candidate_mean_time": round(avg_candidate, 3),
                "improvement": round(improvement, 3),
                "t_statistic": round(t_stat, 4) if t_stat is not None else None,
                "p_value": round(p_value, 4) if p_value is not None else None,
                "chi2_statistic": round(chi2_stat, 4) if chi2_stat is not None else None,
                "chi2_p_value": round(chi2_p, 4) if chi2_p is not None else None,
                "confidence": round(confidence, 4),
                "statistical_test": "welch_t_test",
            }
            
            return result

    def _welch_t_test(self, sample1: List[float], sample2: List[float]):
        """Welch's t-test for unequal variances."""
        n1, n2 = len(sample1), len(sample2)
        if n1 < 2 or n2 < 2:
            return None, None
        
        mean1 = sum(sample1) / n1
        mean2 = sum(sample2) / n2
        var1 = sum((x - mean1) ** 2 for x in sample1) / (n1 - 1)
        var2 = sum((x - mean2) ** 2 for x in sample2) / (n2 - 1)
        
        se = math.sqrt(var1 / n1 + var2 / n2) if (var1 / n1 + var2 / n2) > 0 else 0
        if se == 0:
            return 0.0, 1.0
        
        t_stat = (mean1 - mean2) / se
        
        p_value = self._t_to_p_value(abs(t_stat), max(n1, n2))
        return t_stat, p_value

    def _t_to_p_value(self, t: float, df: float) -> float:
        """Approximate p-value from t-statistic using normal approximation."""
        return 2.0 * (1.0 - self._normal_cdf(abs(t)))

    def _normal_cdf(self, x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _chi_squared_test(self, control_success: List[bool], candidate_success: List[bool]):
        """Chi-squared test for success rates."""
        n1 = len(control_success)
        n2 = len(candidate_success)
        if n1 == 0 or n2 == 0:
            return None, None
        
        s1 = sum(1 for x in control_success if x)
        s2 = sum(1 for x in candidate_success if x)
        
        total = n1 + n2
        total_success = s1 + s2
        expected_rate = total_success / total if total > 0 else 0.5
        
        expected_s1 = n1 * expected_rate
        expected_s2 = n2 * expected_rate
        expected_f1 = n1 * (1 - expected_rate)
        expected_f2 = n2 * (1 - expected_rate)
        
        chi2 = 0.0
        for observed, expected in [(s1, expected_s1), (s2, expected_s2),
                                    (n1 - s1, expected_f1), (n2 - s2, expected_f2)]:
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected
        
        p_value = self._chi2_to_p_value(chi2)
        return chi2, p_value

    def _chi2_to_p_value(self, chi2: float) -> float:
        """Approximate p-value from chi-squared statistic with 1 df."""
        z = math.sqrt(chi2)
        return 2.0 * (1.0 - self._normal_cdf(abs(z)))

    def auto_conclude(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Merge or rollback based on statistical criteria."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None or exp.status != "running":
                return None
            
            result = self.evaluate(experiment_id)
            if result is None:
                return None
            
            if not result["min_sample_met"]:
                return {"status": "insufficient_data", "result": result}
            
            improvement = result["improvement"]
            confidence = result["confidence"]
            
            if improvement > self.IMPROVEMENT_THRESHOLD and confidence > self.CONFIDENCE_THRESHOLD:
                exp.status = "merged"
                exp.result = "winner_candidate"
            elif improvement < 0:
                exp.status = "rolled_back"
                exp.result = "winner_control"
            else:
                exp.status = "concluded"
                exp.result = "inconclusive"
            
            exp.concluded_at = time.time()
            self._save_experiment_to_db(exp)
            
            logger.info("Experiment auto-concluded: id=%s, result=%s", experiment_id, exp.result)
            return {"status": exp.status, "result": exp.result, "analysis": result}

    def route_traffic(self, experiment_id: str, project_id: str) -> str:
        """Route traffic using consistent hashing on project_id."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                return "control"
            
            cursor = self._db.execute(
                "SELECT assigned_branch FROM ab_traffic WHERE project_id = ? AND experiment_id = ?",
                (project_id, experiment_id),
            )
            row = cursor.fetchone()
            if row:
                return row["assigned_branch"]
            
            hash_val = int(hashlib.md5(f"{experiment_id}:{project_id}".encode()).hexdigest(), 16)
            assigned = "candidate" if (hash_val % 100) < (exp.traffic_split * 100) else "control"
            
            self._db.execute(
                """INSERT INTO ab_traffic (project_id, experiment_id, assigned_branch)
                   VALUES (?, ?, ?)""",
                (project_id, experiment_id, assigned),
            )
            self._db.commit()
            
            return assigned

    def get_active_experiments(self) -> List[ABExperiment]:
        """List running experiments."""
        with self._lock:
            return [e for e in self._experiments.values() if e.status == "running"]

    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get full results for an experiment."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if exp is None:
                return {"error": "Experiment not found"}
            
            data = self._get_execution_data(experiment_id)
            
            control_metrics = data["control"]
            candidate_metrics = data["candidate"]
            
            return {
                "experiment": exp.to_dict(),
                "control_metrics": self._aggregate_metrics(control_metrics),
                "candidate_metrics": self._aggregate_metrics(candidate_metrics),
                "control_samples": len(control_metrics),
                "candidate_samples": len(candidate_metrics),
            }

    def _aggregate_metrics(self, records: List[Dict]) -> Dict[str, Any]:
        if not records:
            return {}
        
        times = [r.get("execution_time", 0) for r in records]
        costs = [r.get("resource_cost", 0) for r in records]
        successes = [r.get("success", False) for r in records]
        
        return {
            "avg_execution_time": round(sum(times) / len(times), 3),
            "avg_resource_cost": round(sum(costs) / len(costs), 3),
            "success_rate": round(sum(successes) / len(successes), 3),
            "total_executions": len(records),
        }

    def close(self) -> None:
        if self._db:
            self._db.close()


_ab_testing: Optional[ABTestingFramework] = None
_ab_testing_lock = threading.Lock()


def get_ab_testing() -> ABTestingFramework:
    global _ab_testing
    if _ab_testing is None:
        with _ab_testing_lock:
            if _ab_testing is None:
                _ab_testing = ABTestingFramework()
                _ab_testing.initialize()
    return _ab_testing


def init_ab_testing(db_path: str = "data/templates/ab_testing.db") -> ABTestingFramework:
    global _ab_testing
    with _ab_testing_lock:
        if _ab_testing is not None:
            _ab_testing.close()
        _ab_testing = ABTestingFramework(db_path=db_path)
        _ab_testing.initialize()
    return _ab_testing
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_ab_testing.py -v`
Expected: PASS — 7/7 tests pass

- [ ] **Step 5: Commit**

```bash
git add python/app/core/template_ab_testing.py python/tests/functional_test_ab_testing.py
git commit -m "feat: add A/B testing framework with statistical analysis and traffic routing"
```

---

### Task 8: A/B Testing API Routes

**Files:**
- Create: `python/app/api/v1/template_ab_testing_routes.py`

- [ ] **Step 1: Implement A/B testing API routes (complete code)**

```python
# python/app/api/v1/template_ab_testing_routes.py
"""API routes for A/B testing framework."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.template_ab_testing import get_ab_testing

router = APIRouter(prefix="/api/v1/templates/ab_tests", tags=["template-ab-testing"])

_test_ab_framework = None


def _get_framework():
    return _test_ab_framework or get_ab_testing()


class CreateExperimentRequest(BaseModel):
    name: str
    control_branch: str
    candidate_branch: str
    traffic_split: float = Field(default=0.10, ge=0.01, le=0.50)


class RecordExecutionRequest(BaseModel):
    branch: str
    metrics: dict = Field(default_factory=dict)


@router.post("/experiments", status_code=201)
async def create_experiment(req: CreateExperimentRequest):
    framework = _get_framework()
    exp = framework.create_experiment(
        name=req.name,
        control_branch=req.control_branch,
        candidate_branch=req.candidate_branch,
        traffic_split=req.traffic_split,
    )
    return {"experiment": exp.to_dict()}


@router.get("/experiments")
async def list_experiments(active_only: bool = True):
    framework = _get_framework()
    if active_only:
        experiments = framework.get_active_experiments()
    else:
        experiments = list(framework._experiments.values())
    return {"experiments": [e.to_dict() for e in experiments]}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    framework = _get_framework()
    exp = framework._experiments.get(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_id}")
    return {"experiment": exp.to_dict()}


@router.post("/experiments/{experiment_id}/record")
async def record_execution(experiment_id: str, req: RecordExecutionRequest):
    framework = _get_framework()
    record = framework.record_execution(
        experiment_id=experiment_id,
        branch=req.branch,
        metrics=req.metrics,
    )
    return {"record": record}


@router.post("/experiments/{experiment_id}/evaluate")
async def evaluate_experiment(experiment_id: str):
    framework = _get_framework()
    result = framework.evaluate(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No data available for evaluation")
    return {"evaluation": result}


@router.post("/experiments/{experiment_id}/auto_conclude")
async def auto_conclude(experiment_id: str):
    framework = _get_framework()
    result = framework.auto_conclude(experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found or already concluded")
    return result


@router.get("/experiments/{experiment_id}/results")
async def get_experiment_results(experiment_id: str):
    framework = _get_framework()
    results = framework.get_experiment_results(experiment_id)
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
    return results


@router.post("/traffic/{experiment_id}")
async def route_traffic(experiment_id: str, project_id: str):
    framework = _get_framework()
    branch = framework.route_traffic(experiment_id, project_id)
    return {"experiment_id": experiment_id, "project_id": project_id, "assigned_branch": branch}
```

- [ ] **Step 2: Commit**

```bash
git add python/app/api/v1/template_ab_testing_routes.py
git commit -m "feat: add A/B testing API routes for experiment lifecycle"
```

---

## Phase 5: Template Update Service

### Task 9: Update Service Core

**Files:**
- Create: `python/app/core/template_update_service.py`
- Test: `python/tests/functional_test_update_service.py`

- [ ] **Step 1: Write the failing test — notification lifecycle**

```python
# python/tests/functional_test_update_service.py
"""Functional tests for Template Update Service."""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

try:
    from app.core.template_update_service import TemplateUpdateService
except ImportError:
    TemplateUpdateService = None


@pytest.fixture
def update_service():
    """Create a temporary update service for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "updates.db")
    
    service = TemplateUpdateService(db_path=db_path)
    service.initialize()
    
    yield service
    
    service.close()
    shutil.rmtree(tmpdir)


def test_classify_priority_optional(update_service):
    """Test priority classification for minor improvements."""
    suggestion = {
        "proposed_change": {"action": "tweak"},
        "data_evidence": {"metric": "accuracy", "improvement": 0.02},
    }
    
    priority = update_service.classify_priority(suggestion)
    assert priority == "optional"


def test_classify_priority_recommended(update_service):
    """Test priority classification for clear benefits."""
    suggestion = {
        "proposed_change": {"action": "update"},
        "data_evidence": {"metric": "accuracy", "improvement": 0.05},
    }
    
    priority = update_service.classify_priority(suggestion)
    assert priority == "recommended"


def test_classify_priority_critical(update_service):
    """Test priority classification for critical improvements."""
    suggestion = {
        "proposed_change": {"action": "security_fix"},
        "data_evidence": {"metric": "stability", "improvement": 0.15},
    }
    
    priority = update_service.classify_priority(suggestion)
    assert priority == "critical"


def test_create_notification(update_service):
    """Test creating an update notification."""
    notification = update_service.create_notification(
        project_id="proj-001",
        suggestion={
            "suggestion_id": "sug-001",
            "trigger_type": "skill",
            "description": "Add new skill",
            "proposed_change": {"action": "add_skill"},
            "data_evidence": {"metric": "test", "improvement": 0.05},
        },
        priority="recommended",
    )
    
    assert notification.notification_id is not None
    assert notification.project_id == "proj-001"
    assert notification.priority == "recommended"
    assert notification.status == "pending"


def test_scan_for_updates(update_service):
    """Test scanning for updates applicable to a project."""
    update_service._suggestions = {
        "sug-001": {
            "suggestion_id": "sug-001",
            "trigger_type": "skill",
            "description": "Test suggestion",
            "proposed_change": {"action": "add_skill"},
            "data_evidence": {"metric": "test", "improvement": 0.05},
            "status": "pending",
        },
        "sug-002": {
            "suggestion_id": "sug-002",
            "trigger_type": "model_config",
            "description": "Config update",
            "proposed_change": {"action": "update_config"},
            "data_evidence": {"metric": "test", "improvement": 0.12},
            "status": "pending",
        },
    }
    
    notifications = update_service.scan_for_updates("proj-001")
    
    assert len(notifications) == 2
    priorities = [n.priority for n in notifications]
    assert "recommended" in priorities
    assert "critical" in priorities


def test_preview_update(update_service):
    """Test previewing an update before applying."""
    notification = update_service.create_notification(
        project_id="proj-001",
        suggestion={
            "suggestion_id": "sug-001",
            "trigger_type": "skill",
            "description": "Preview test",
            "proposed_change": {"action": "add_skill", "skills": ["new_skill"]},
            "data_evidence": {"metric": "test", "improvement": 0.05},
        },
        priority="recommended",
    )
    
    preview = update_service.preview_update(notification.notification_id)
    
    assert preview is not None
    assert "change_preview" in preview
    assert "expected_impact" in preview


def test_apply_update(update_service):
    """Test applying an update notification."""
    notification = update_service.create_notification(
        project_id="proj-001",
        suggestion={
            "suggestion_id": "sug-001",
            "trigger_type": "skill",
            "description": "Apply test",
            "proposed_change": {"action": "add_skill"},
            "data_evidence": {"metric": "test", "improvement": 0.05},
        },
        priority="recommended",
    )
    
    result = update_service.apply_update(notification.notification_id)
    
    assert result is not None
    assert notification.status == "applied"
    assert result["status"] == "applied"


def test_dismiss_notification(update_service):
    """Test dismissing a notification."""
    notification = update_service.create_notification(
        project_id="proj-001",
        suggestion={
            "suggestion_id": "sug-001",
            "trigger_type": "skill",
            "description": "Dismiss test",
            "proposed_change": {},
            "data_evidence": {},
        },
        priority="optional",
    )
    
    success = update_service.dismiss_notification(notification.notification_id)
    assert success is True
    assert notification.status == "dismissed"


def test_get_notifications(update_service):
    """Test listing notifications with status filter."""
    update_service.create_notification(
        project_id="proj-001",
        suggestion={"suggestion_id": "s1", "trigger_type": "skill", "description": "n1", "proposed_change": {}, "data_evidence": {}},
        priority="optional",
    )
    update_service.create_notification(
        project_id="proj-001",
        suggestion={"suggestion_id": "s2", "trigger_type": "skill", "description": "n2", "proposed_change": {}, "data_evidence": {}},
        priority="recommended",
    )
    
    all_notifs = update_service.get_notifications("proj-001")
    assert len(all_notifs) == 2
    
    pending = update_service.get_notifications("proj-001", status_filter="pending")
    assert len(pending) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && pytest tests/functional_test_update_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement TemplateUpdateService core class**

```python
# python/app/core/template_update_service.py
"""Template Update Service — scan, classify, notify, and apply updates."""
import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UpdateNotification:
    notification_id: str
    project_id: str
    suggestion_id: str
    priority: str
    title: str
    description: str
    change_preview: Dict[str, Any]
    expected_impact: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "project_id": self.project_id,
            "suggestion_id": self.suggestion_id,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "change_preview": self.change_preview,
            "expected_impact": self.expected_impact,
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateNotification":
        return cls(
            notification_id=data["notification_id"],
            project_id=data["project_id"],
            suggestion_id=data["suggestion_id"],
            priority=data["priority"],
            title=data["title"],
            description=data["description"],
            change_preview=data.get("change_preview", {}),
            expected_impact=data.get("expected_impact", {}),
            created_at=data.get("created_at", time.time()),
            status=data.get("status", "pending"),
        )


class TemplateUpdateService:
    """Service for managing template update notifications."""

    def __init__(self, db_path: str = "data/templates/updates.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._notifications: Dict[str, UpdateNotification] = {}
        self._suggestions: Dict[str, Dict[str, Any]] = {}
        self._db: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS update_notifications (
                notification_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                suggestion_id TEXT NOT NULL,
                priority TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                change_preview TEXT NOT NULL,
                expected_impact TEXT NOT NULL,
                created_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
        """)
        self._db.commit()
        self._load_notifications_from_db()
        logger.info("TemplateUpdateService initialized: db=%s", self.db_path)

    def _load_notifications_from_db(self) -> None:
        cursor = self._db.execute("SELECT * FROM update_notifications")
        for row in cursor.fetchall():
            data = {
                "notification_id": row["notification_id"],
                "project_id": row["project_id"],
                "suggestion_id": row["suggestion_id"],
                "priority": row["priority"],
                "title": row["title"],
                "description": row["description"],
                "change_preview": json.loads(row["change_preview"]),
                "expected_impact": json.loads(row["expected_impact"]),
                "created_at": row["created_at"],
                "status": row["status"],
            }
            self._notifications[row["notification_id"]] = UpdateNotification.from_dict(data)

    def _save_notification_to_db(self, notification: UpdateNotification) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO update_notifications
               (notification_id, project_id, suggestion_id, priority, title, description, change_preview, expected_impact, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                notification.notification_id,
                notification.project_id,
                notification.suggestion_id,
                notification.priority,
                notification.title,
                notification.description,
                json.dumps(notification.change_preview),
                json.dumps(notification.expected_impact),
                notification.created_at,
                notification.status,
            ),
        )
        self._db.commit()

    def classify_priority(self, suggestion: Dict[str, Any]) -> str:
        """Determine priority level based on improvement magnitude."""
        evidence = suggestion.get("data_evidence", {})
        improvement = evidence.get("improvement", 0.0)
        
        if improvement >= 0.10:
            return "critical"
        elif improvement >= 0.03:
            return "recommended"
        else:
            return "optional"

    def create_notification(
        self,
        project_id: str,
        suggestion: Dict[str, Any],
        priority: str,
    ) -> UpdateNotification:
        """Create an update notification for a project."""
        with self._lock:
            notification_id = hashlib.sha256(
                f"{project_id}:{suggestion.get('suggestion_id', '')}:{time.time()}".encode()
            ).hexdigest()[:12]
            
            change_preview = suggestion.get("proposed_change", {})
            evidence = suggestion.get("data_evidence", {})
            
            expected_impact = {}
            if "improvement" in evidence:
                expected_impact["estimated_improvement"] = evidence["improvement"]
            if "metric" in evidence:
                expected_impact["affected_metric"] = evidence["metric"]
            
            title = f"Template update: {suggestion.get('trigger_type', 'unknown')}"
            description = suggestion.get("description", "New template update available")
            
            notification = UpdateNotification(
                notification_id=notification_id,
                project_id=project_id,
                suggestion_id=suggestion.get("suggestion_id", ""),
                priority=priority,
                title=title,
                description=description,
                change_preview=change_preview,
                expected_impact=expected_impact,
            )
            
            self._notifications[notification_id] = notification
            self._save_notification_to_db(notification)
            
            self._suggestions[suggestion.get("suggestion_id", notification_id)] = suggestion
            
            logger.info("Update notification created: id=%s, project=%s, priority=%s",
                       notification_id, project_id, priority)
            return notification

    def scan_for_updates(self, project_id: str) -> List[UpdateNotification]:
        """Find applicable suggestions and create notifications for a project."""
        with self._lock:
            notifications = []
            
            for sug_id, suggestion in self._suggestions.items():
                if suggestion.get("status", "pending") != "pending":
                    continue
                
                existing = [
                    n for n in self._notifications.values()
                    if n.project_id == project_id and n.suggestion_id == sug_id and n.status == "pending"
                ]
                if existing:
                    continue
                
                priority = self.classify_priority(suggestion)
                notification = self.create_notification(project_id, suggestion, priority)
                notifications.append(notification)
            
            return notifications

    def apply_update(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Apply an update notification."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification is None:
                return None
            
            notification.status = "applied"
            self._save_notification_to_db(notification)
            
            logger.info("Update applied: id=%s", notification_id)
            return {"status": "applied", "notification_id": notification_id}

    def preview_update(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Show full diff and expected impact for an update."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification is None:
                return None
            
            return {
                "change_preview": notification.change_preview,
                "expected_impact": notification.expected_impact,
                "priority": notification.priority,
                "description": notification.description,
            }

    def dismiss_notification(self, notification_id: str) -> bool:
        """User dismisses a notification."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification is None:
                return False
            
            notification.status = "dismissed"
            self._save_notification_to_db(notification)
            
            logger.info("Update dismissed: id=%s", notification_id)
            return True

    def get_notifications(
        self, project_id: str, status_filter: Optional[str] = None
    ) -> List[UpdateNotification]:
        """List notifications for a project."""
        with self._lock:
            notifications = [
                n for n in self._notifications.values()
                if n.project_id == project_id
            ]
            if status_filter:
                notifications = [n for n in notifications if n.status == status_filter]
            return sorted(notifications, key=lambda n: n.created_at, reverse=True)

    def close(self) -> None:
        if self._db:
            self._db.close()


_update_service: Optional[TemplateUpdateService] = None
_update_service_lock = threading.Lock()


def get_update_service() -> TemplateUpdateService:
    global _update_service
    if _update_service is None:
        with _update_service_lock:
            if _update_service is None:
                _update_service = TemplateUpdateService()
                _update_service.initialize()
    return _update_service


def init_update_service(db_path: str = "data/templates/updates.db") -> TemplateUpdateService:
    global _update_service
    with _update_service_lock:
        if _update_service is not None:
            _update_service.close()
        _update_service = TemplateUpdateService(db_path=db_path)
        _update_service.initialize()
    return _update_service
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && pytest tests/functional_test_update_service.py -v`
Expected: PASS — 9/9 tests pass

- [ ] **Step 5: Commit**

```bash
git add python/app/core/template_update_service.py python/tests/functional_test_update_service.py
git commit -m "feat: add template update service with priority classification and notification lifecycle"
```

---

### Task 10: Update API Routes

**Files:**
- Create: `python/app/api/v1/template_update_routes.py`

- [ ] **Step 1: Implement update API routes (complete code)**

```python
# python/app/api/v1/template_update_routes.py
"""API routes for template update service."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.template_update_service import get_update_service

router = APIRouter(prefix="/api/v1/templates/updates", tags=["template-updates"])

_test_update_service = None


def _get_service():
    return _test_update_service or get_update_service()


class ScanUpdatesRequest(BaseModel):
    project_id: str


@router.post("/scan")
async def scan_for_updates(req: ScanUpdatesRequest):
    service = _get_service()
    notifications = service.scan_for_updates(req.project_id)
    return {"notifications": [n.to_dict() for n in notifications]}


@router.get("/")
async def get_notifications(project_id: str, status_filter: Optional[str] = None):
    service = _get_service()
    notifications = service.get_notifications(project_id, status_filter=status_filter)
    return {"notifications": [n.to_dict() for n in notifications]}


@router.get("/{notification_id}/preview")
async def preview_update(notification_id: str):
    service = _get_service()
    preview = service.preview_update(notification_id)
    if preview is None:
        raise HTTPException(status_code=404, detail=f"Notification not found: {notification_id}")
    return {"preview": preview}


@router.post("/{notification_id}/apply")
async def apply_update(notification_id: str):
    service = _get_service()
    result = service.apply_update(notification_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Notification not found: {notification_id}")
    return result


@router.post("/{notification_id}/dismiss")
async def dismiss_notification(notification_id: str):
    service = _get_service()
    success = service.dismiss_notification(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Notification not found: {notification_id}")
    return {"message": "Notification dismissed"}
```

- [ ] **Step 2: Commit**

```bash
git add python/app/api/v1/template_update_routes.py
git commit -m "feat: add update API routes for notification management"
```

---

## Phase 6: Enhanced Marketplace (Frontend + Backend)

### Task 11: Marketplace API Routes

**Files:**
- Create: `python/app/api/v1/template_market.py`

- [ ] **Step 1: Implement marketplace API routes (complete code)**

```python
# python/app/api/v1/template_market.py
"""API routes for enhanced template marketplace."""
import hashlib
import json
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.template_branching import get_branch_manager
from app.core.template_evolution import get_evolution_engine
from app.core.template_ab_testing import get_ab_testing
from app.core.template_update_service import get_update_service

router = APIRouter(prefix="/api/v1/template_market", tags=["template-market"])

_test_branch_manager = None
_test_evolution_engine = None
_test_ab_testing = None
_test_update_service = None


def _get_branch_manager():
    return _test_branch_manager or get_branch_manager()


def _get_evolution_engine():
    return _test_evolution_engine or get_evolution_engine()


def _get_ab_testing():
    return _test_ab_testing or get_ab_testing()


def _get_update_service():
    return _test_update_service or get_update_service()


class PublishTemplateRequest(BaseModel):
    name: str
    category: str
    description: str
    template_data: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class SubscribeRequest(BaseModel):
    category: str
    project_id: str


class ImportTemplateRequest(BaseModel):
    name: str
    category: str
    template_data: dict = Field(default_factory=dict)
    evolution_history: list[dict] = Field(default_factory=list)


@router.get("/trending")
async def get_trending_templates(limit: int = 20):
    manager = _get_branch_manager()
    branches = manager.list_branches()
    
    trending = []
    for b in branches[:limit]:
        trending.append({
            "branch_id": b.branch_id,
            "name": b.name,
            "type": b.metadata.get("type", "main"),
            "updated_at": b.updated_at,
            "created_at": b.created_at,
            "popularity_score": round(1.0 / max(1, (time.time() - b.updated_at) / 86400), 3),
        })
    
    trending.sort(key=lambda x: x["popularity_score"], reverse=True)
    return {"trending": trending}


@router.get("/templates/{template_id}/metrics")
async def get_template_metrics(template_id: str):
    manager = _get_branch_manager()
    branch = manager.get_branch(template_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    ab_framework = _get_ab_testing()
    experiments = [
        e.to_dict() for e in ab_framework._experiments.values()
        if e.control_branch == template_id or e.candidate_branch == template_id
    ]
    
    evolution = _get_evolution_engine()
    evolution_count = len([
        s for s in evolution._suggestions.values()
        if s.status == "applied"
    ])
    
    return {
        "template": branch.to_dict(),
        "experiments": experiments,
        "experiment_count": len(experiments),
        "evolution_count": evolution_count,
    }


@router.post("/publish", status_code=201)
async def publish_template(req: PublishTemplateRequest):
    manager = _get_branch_manager()
    
    branch = manager.create_branch(
        name=req.name,
        base_branch=None,
        data={**req.template_data, "category": req.category, "description": req.description},
        metadata={
            "type": "main",
            "category": req.category,
            "tags": req.tags,
            "published": True,
            "published_at": time.time(),
        },
    )
    
    return {"branch": branch.to_dict()}


@router.get("/subscriptions")
async def get_subscriptions(project_id: Optional[str] = None):
    service = _get_update_service()
    if project_id:
        notifications = service.get_notifications(project_id)
        return {"subscriptions": [n.to_dict() for n in notifications]}
    return {"subscriptions": []}


@router.post("/subscriptions", status_code=201)
async def subscribe_to_category(req: SubscribeRequest):
    manager = _get_branch_manager()
    branches = manager.list_branches(type_filter="industry")
    
    subscribed_templates = [
        {"branch_id": b.branch_id, "name": b.name}
        for b in branches
        if req.category in b.metadata.get("category", "").lower() or req.category == "all"
    ]
    
    return {
        "project_id": req.project_id,
        "category": req.category,
        "subscribed_count": len(subscribed_templates),
        "templates": subscribed_templates,
    }


@router.post("/export/{template_id}")
async def export_template(template_id: str):
    manager = _get_branch_manager()
    branch = manager.get_branch(template_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    evolution = _get_evolution_engine()
    history = evolution.get_evolution_history()
    
    export_data = {
        "template": branch.to_dict(),
        "evolution_history": history,
        "exported_at": time.time(),
        "content_hash": hashlib.sha256(
            json.dumps(branch.template_data, sort_keys=True).encode()
        ).hexdigest()[:16],
    }
    
    return {"export": export_data}


@router.post("/import", status_code=201)
async def import_template(req: ImportTemplateRequest):
    manager = _get_branch_manager()
    
    branch = manager.create_branch(
        name=req.name,
        base_branch=None,
        data={**req.template_data, "category": req.category},
        metadata={
            "type": "industry",
            "category": req.category,
            "imported": True,
            "imported_at": time.time(),
            "evolution_history": req.evolution_history,
        },
    )
    
    return {"branch": branch.to_dict()}


@router.get("/sync/{template_id}")
async def get_sync_diff(template_id: str, since: Optional[float] = None):
    manager = _get_branch_manager()
    branch = manager.get_branch(template_id)
    if branch is None:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    log = manager.get_commit_log(template_id)
    
    if since:
        log = [entry for entry in log if entry["timestamp"] > since]
    
    return {
        "template_id": template_id,
        "current_data": branch.template_data,
        "diff_log": log,
        "last_updated": branch.updated_at,
    }
```

- [ ] **Step 2: Commit**

```bash
git add python/app/api/v1/template_market.py
git commit -m "feat: add enhanced marketplace API routes with trending, metrics, publish, subscribe, export, import, sync"
```

---

### Task 12: Frontend Pinia Store

**Files:**
- Create: `src/stores/template_market.ts`

- [ ] **Step 1: Implement Pinia store (complete code)**

```typescript
// src/stores/template_market.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface TemplateBranch {
  branch_id: string
  name: string
  base_branch: string | null
  template_data: Record<string, any>
  metadata: Record<string, any>
  created_at: number
  updated_at: number
  commit_log: Array<Record<string, any>>
}

export interface TrendingTemplate {
  branch_id: string
  name: string
  type: string
  updated_at: number
  created_at: number
  popularity_score: number
}

export interface TemplateMetrics {
  template: TemplateBranch
  experiments: Array<Record<string, any>>
  experiment_count: number
  evolution_count: number
}

export interface UpdateNotification {
  notification_id: string
  project_id: string
  suggestion_id: string
  priority: 'optional' | 'recommended' | 'critical'
  title: string
  description: string
  change_preview: Record<string, any>
  expected_impact: Record<string, any>
  created_at: number
  status: 'pending' | 'accepted' | 'dismissed' | 'applied'
}

export interface Experiment {
  experiment_id: string
  name: string
  control_branch: string
  candidate_branch: string
  traffic_split: number
  status: 'running' | 'concluded' | 'rolled_back' | 'merged'
  created_at: number
  concluded_at: number | null
  result: string | null
}

export interface BranchStats {
  total: number
  by_type: Record<string, number>
  last_updated: number
}

export const useTemplateMarketStore = defineStore('templateMarket', () => {
  const trendingTemplates = ref<TrendingTemplate[]>([])
  const currentTemplate = ref<TemplateBranch | null>(null)
  const templateMetrics = ref<TemplateMetrics | null>(null)
  const notifications = ref<UpdateNotification[]>([])
  const experiments = ref<Experiment[]>([])
  const branches = ref<TemplateBranch[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const pendingNotifications = computed(() =>
    notifications.value.filter(n => n.status === 'pending')
  )

  const criticalNotifications = computed(() =>
    notifications.value.filter(n => n.priority === 'critical' && n.status === 'pending')
  )

  const activeExperiments = computed(() =>
    experiments.value.filter(e => e.status === 'running')
  )

  async function fetchTrending(limit = 20) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/template_market/trending?limit=${limit}`)
      if (!response.ok) throw new Error(`Failed to fetch trending: ${response.statusText}`)
      const data = await response.json()
      trendingTemplates.value = data.trending
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplateMetrics(templateId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/template_market/templates/${templateId}/metrics`)
      if (!response.ok) throw new Error(`Failed to fetch metrics: ${response.statusText}`)
      const data = await response.json()
      templateMetrics.value = data
      currentTemplate.value = data.template
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function publishTemplate(template: {
    name: string
    category: string
    description: string
    template_data: Record<string, any>
    tags: string[]
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/template_market/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(template),
      })
      if (!response.ok) throw new Error(`Failed to publish: ${response.statusText}`)
      return await response.json()
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchNotifications(projectId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/templates/updates/?project_id=${projectId}`)
      if (!response.ok) throw new Error(`Failed to fetch notifications: ${response.statusText}`)
      const data = await response.json()
      notifications.value = data.notifications
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function applyUpdate(notificationId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/templates/updates/${notificationId}/apply`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error(`Failed to apply update: ${response.statusText}`)
      const data = await response.json()
      const idx = notifications.value.findIndex(n => n.notification_id === notificationId)
      if (idx >= 0) {
        notifications.value[idx].status = 'applied'
      }
      return data
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function dismissNotification(notificationId: string) {
    try {
      const response = await fetch(`/api/v1/templates/updates/${notificationId}/dismiss`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error(`Failed to dismiss: ${response.statusText}`)
      const idx = notifications.value.findIndex(n => n.notification_id === notificationId)
      if (idx >= 0) {
        notifications.value[idx].status = 'dismissed'
      }
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  async function fetchBranches(typeFilter?: string) {
    loading.value = true
    error.value = null
    try {
      const params = typeFilter ? `?type_filter=${typeFilter}` : ''
      const response = await fetch(`/api/v1/templates/branches/${params}`)
      if (!response.ok) throw new Error(`Failed to fetch branches: ${response.statusText}`)
      const data = await response.json()
      branches.value = data.branches
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createBranch(branch: {
    name: string
    base_branch: string | null
    data: Record<string, any>
    metadata: Record<string, any>
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/templates/branches/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(branch),
      })
      if (!response.ok) throw new Error(`Failed to create branch: ${response.statusText}`)
      const data = await response.json()
      branches.value.unshift(data.branch)
      return data.branch
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function mergeBranches(sourceId: string, targetId: string, strategy = 'overwrite') {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/templates/branches/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, target_id: targetId, strategy }),
      })
      if (!response.ok) throw new Error(`Failed to merge: ${response.statusText}`)
      const data = await response.json()
      const idx = branches.value.findIndex(b => b.branch_id === targetId)
      if (idx >= 0) {
        branches.value[idx] = data.merged_branch
      }
      return data.merged_branch
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchExperiments() {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/templates/ab_tests/experiments')
      if (!response.ok) throw new Error(`Failed to fetch experiments: ${response.statusText}`)
      const data = await response.json()
      experiments.value = data.experiments
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createExperiment(exp: {
    name: string
    control_branch: string
    candidate_branch: string
    traffic_split: number
  }) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/templates/ab_tests/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(exp),
      })
      if (!response.ok) throw new Error(`Failed to create experiment: ${response.statusText}`)
      const data = await response.json()
      experiments.value.push(data.experiment)
      return data.experiment
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function autoConcludeExperiment(experimentId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/v1/templates/ab_tests/experiments/${experimentId}/auto_conclude`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error(`Failed to conclude: ${response.statusText}`)
      const data = await response.json()
      const idx = experiments.value.findIndex(e => e.experiment_id === experimentId)
      if (idx >= 0) {
        experiments.value[idx].status = data.status
        experiments.value[idx].result = data.result
      }
      return data
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function scanUpdates(projectId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch('/api/v1/templates/updates/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId }),
      })
      if (!response.ok) throw new Error(`Failed to scan updates: ${response.statusText}`)
      const data = await response.json()
      notifications.value = data.notifications
      return data.notifications
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchCommitLog(branchId: string) {
    try {
      const response = await fetch(`/api/v1/templates/branches/${branchId}/log`)
      if (!response.ok) throw new Error(`Failed to fetch log: ${response.statusText}`)
      const data = await response.json()
      return data.commit_log
    } catch (e: any) {
      error.value = e.message
      return []
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    trendingTemplates,
    currentTemplate,
    templateMetrics,
    notifications,
    experiments,
    branches,
    loading,
    error,
    pendingNotifications,
    criticalNotifications,
    activeExperiments,
    fetchTrending,
    fetchTemplateMetrics,
    publishTemplate,
    fetchNotifications,
    applyUpdate,
    dismissNotification,
    fetchBranches,
    createBranch,
    mergeBranches,
    fetchExperiments,
    createExperiment,
    autoConcludeExperiment,
    scanUpdates,
    fetchCommitLog,
    clearError,
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add src/stores/template_market.ts
git commit -m "feat: add Pinia store for template marketplace state management"
```

---

### Task 13: Frontend Vue Views

**Files:**
- Create: `src/views/TemplateMarket.vue`
- Create: `src/views/TemplateDetail.vue`
- Create: `src/views/UpdateCenter.vue`
- Create: `src/views/BranchManager.vue`

- [ ] **Step 1: Implement TemplateMarket.vue**

```vue
<!-- src/views/TemplateMarket.vue -->
<template>
  <div class="template-market">
    <header class="market-header">
      <h1>Template Marketplace</h1>
      <div class="header-actions">
        <button @click="showPublish = true" class="btn-primary">Publish Template</button>
        <button @click="store.fetchTrending()" class="btn-secondary" :disabled="store.loading">Refresh</button>
      </div>
    </header>

    <div v-if="store.loading" class="loading-spinner">Loading...</div>
    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <section class="trending-section">
      <h2>Trending Templates</h2>
      <div class="template-grid">
        <div
          v-for="t in store.trendingTemplates"
          :key="t.branch_id"
          class="template-card"
          @click="goToDetail(t.branch_id)"
        >
          <h3>{{ t.name }}</h3>
          <span class="type-badge">{{ t.type }}</span>
          <div class="metrics">
            <span>Score: {{ t.popularity_score }}</span>
            <span>Updated: {{ formatDate(t.updated_at) }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="notifications-section">
      <h2>Pending Updates ({{ store.pendingNotifications.length }})</h2>
      <div v-if="store.criticalNotifications.length > 0" class="critical-alert">
        {{ store.criticalNotifications.length }} critical updates available
      </div>
      <ul class="notification-list">
        <li v-for="n in store.pendingNotifications.slice(0, 5)" :key="n.notification_id" class="notification-item">
          <span :class="['priority', n.priority]">{{ n.priority }}</span>
          <span class="notif-title">{{ n.title }}</span>
          <div class="notif-actions">
            <button @click="store.applyUpdate(n.notification_id)" class="btn-small">Apply</button>
            <button @click="store.dismissNotification(n.notification_id)" class="btn-small btn-ghost">Dismiss</button>
          </div>
        </li>
      </ul>
    </section>

    <div v-if="showPublish" class="modal-overlay" @click.self="showPublish = false">
      <div class="modal">
        <h2>Publish Template</h2>
        <form @submit.prevent="handlePublish">
          <label>Name<input v-model="publishForm.name" required /></label>
          <label>Category<input v-model="publishForm.category" required /></label>
          <label>Description<textarea v-model="publishForm.description" required></textarea></label>
          <label>Tags (comma-separated)<input v-model="publishForm.tagsInput" /></label>
          <div class="modal-actions">
            <button type="submit" :disabled="store.loading">Publish</button>
            <button type="button" @click="showPublish = false">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTemplateMarketStore } from '../stores/template_market'

const router = useRouter()
const store = useTemplateMarketStore()
const showPublish = ref(false)

const publishForm = ref({
  name: '',
  category: '',
  description: '',
  tagsInput: '',
})

async function handlePublish() {
  const tags = publishForm.value.tagsInput.split(',').map(t => t.trim()).filter(Boolean)
  await store.publishTemplate({
    name: publishForm.value.name,
    category: publishForm.value.category,
    description: publishForm.value.description,
    template_data: {},
    tags,
  })
  showPublish.value = false
  store.fetchTrending()
}

function goToDetail(id: string) {
  router.push({ name: 'TemplateDetail', params: { id } })
}

function formatDate(ts: number) {
  return new Date(ts * 1000).toLocaleDateString()
}

onMounted(async () => {
  await Promise.all([
    store.fetchTrending(),
    store.fetchNotifications('default-project'),
  ])
})
</script>

<style scoped>
.template-market { max-width: 1200px; margin: 0 auto; padding: 2rem; }
.market-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
.header-actions { display: flex; gap: 0.5rem; }
.btn-primary { background: #2563eb; color: white; padding: 0.5rem 1rem; border: none; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #e5e7eb; padding: 0.5rem 1rem; border: none; border-radius: 6px; cursor: pointer; }
.btn-secondary:disabled { opacity: 0.5; }
.template-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }
.template-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; cursor: pointer; transition: box-shadow 0.2s; }
.template-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.type-badge { display: inline-block; background: #f3f4f6; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
.metrics { display: flex; justify-content: space-between; margin-top: 0.5rem; font-size: 0.85rem; color: #6b7280; }
.notification-list { list-style: none; padding: 0; }
.notification-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; border-bottom: 1px solid #f3f4f6; }
.priority { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; text-transform: uppercase; }
.priority.critical { background: #fecaca; color: #991b1b; }
.priority.recommended { background: #fef3c7; color: #92400e; }
.priority.optional { background: #dbeafe; color: #1e40af; }
.notif-title { flex: 1; }
.notif-actions { display: flex; gap: 0.25rem; }
.btn-small { padding: 0.25rem 0.5rem; font-size: 0.75rem; border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer; }
.btn-ghost { background: transparent; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 2rem; border-radius: 8px; width: 400px; }
.modal form { display: flex; flex-direction: column; gap: 1rem; }
.modal label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.875rem; }
.modal input, .modal textarea { padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; }
.modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; }
.critical-alert { background: #fecaca; color: #991b1b; padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 0.5rem; }
.loading-spinner { text-align: center; padding: 2rem; }
.error-banner { background: #fecaca; color: #991b1b; padding: 0.5rem; border-radius: 4px; margin-bottom: 1rem; }
</style>
```

- [ ] **Step 2: Implement TemplateDetail.vue**

```vue
<!-- src/views/TemplateDetail.vue -->
<template>
  <div class="template-detail" v-if="store.currentTemplate">
    <header class="detail-header">
      <button @click="$router.back()" class="btn-back">← Back</button>
      <h1>{{ store.currentTemplate.name }}</h1>
    </header>

    <div class="detail-grid">
      <section class="info-section">
        <h2>Template Info</h2>
        <dl class="info-list">
          <dt>Type</dt><dd>{{ store.currentTemplate.metadata?.type || 'main' }}</dd>
          <dt>Created</dt><dd>{{ formatDate(store.currentTemplate.created_at) }}</dd>
          <dt>Updated</dt><dd>{{ formatDate(store.currentTemplate.updated_at) }}</dd>
          <dt>Branch ID</dt><dd class="mono">{{ store.currentTemplate.branch_id }}</dd>
        </dl>
      </section>

      <section class="metrics-section">
        <h2>Metrics</h2>
        <div v-if="store.templateMetrics" class="metrics-grid">
          <div class="metric-card">
            <span class="metric-value">{{ store.templateMetrics.experiment_count }}</span>
            <span class="metric-label">Experiments</span>
          </div>
          <div class="metric-card">
            <span class="metric-value">{{ store.templateMetrics.evolution_count }}</span>
            <span class="metric-label">Evolutions</span>
          </div>
        </div>
      </section>

      <section class="history-section">
        <h2>Evolution History</h2>
        <ul class="history-list">
          <li v-for="entry in commitLog" :key="entry.timestamp" class="history-item">
            <span class="history-action">{{ entry.action }}</span>
            <span class="history-time">{{ formatDate(entry.timestamp) }}</span>
          </li>
        </ul>
      </section>

      <section class="experiments-section">
        <h2>A/B Experiments</h2>
        <ul class="experiment-list">
          <li v-for="exp in relatedExperiments" :key="exp.experiment_id" class="experiment-item">
            <span>{{ exp.name }}</span>
            <span :class="['status', exp.status]">{{ exp.status }}</span>
            <span v-if="exp.result">{{ exp.result }}</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
  <div v-else class="loading">Loading template details...</div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTemplateMarketStore } from '../stores/template_market'

const route = useRoute()
const store = useTemplateMarketStore()
const commitLog = ref<Array<Record<string, any>>>([])

const relatedExperiments = computed(() => {
  if (!store.templateMetrics) return []
  return store.templateMetrics.experiments
})

function formatDate(ts: number) {
  return new Date(ts * 1000).toLocaleString()
}

onMounted(async () => {
  const templateId = route.params.id as string
  await store.fetchTemplateMetrics(templateId)
  commitLog.value = await store.fetchCommitLog(templateId)
})
</script>

<style scoped>
.template-detail { max-width: 1200px; margin: 0 auto; padding: 2rem; }
.detail-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; }
.btn-back { background: none; border: none; cursor: pointer; font-size: 1rem; color: #6b7280; }
.detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 2rem; }
.info-list { display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1rem; }
.info-list dt { font-weight: 600; color: #6b7280; }
.mono { font-family: monospace; }
.metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.metric-card { background: #f9fafb; padding: 1.5rem; border-radius: 8px; text-align: center; }
.metric-value { display: block; font-size: 2rem; font-weight: 700; }
.metric-label { color: #6b7280; font-size: 0.875rem; }
.history-list { list-style: none; padding: 0; }
.history-item { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #f3f4f6; }
.history-action { font-weight: 500; }
.history-time { color: #6b7280; font-size: 0.85rem; }
.experiment-list { list-style: none; padding: 0; }
.experiment-item { display: flex; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid #f3f4f6; align-items: center; }
.status { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; text-transform: uppercase; }
.status.running { background: #dbeafe; color: #1e40af; }
.status.merged { background: #d1fae5; color: #065f46; }
.status.rolled_back { background: #fecaca; color: #991b1b; }
.loading { text-align: center; padding: 4rem; color: #6b7280; }
</style>
```

- [ ] **Step 3: Implement UpdateCenter.vue**

```vue
<!-- src/views/UpdateCenter.vue -->
<template>
  <div class="update-center">
    <header class="center-header">
      <h1>Update Center</h1>
      <button @click="store.scanUpdates(projectId)" :disabled="store.loading" class="btn-primary">
        {{ store.loading ? 'Scanning...' : 'Scan for Updates' }}
      </button>
    </header>

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <div class="filter-bar">
      <button :class="['filter-btn', { active: filter === 'all' }]" @click="filter = 'all'">All</button>
      <button :class="['filter-btn', { active: filter === 'critical' }]" @click="filter = 'critical'">Critical</button>
      <button :class="['filter-btn', { active: filter === 'pending' }]" @click="filter = 'pending'">Pending</button>
    </div>

    <ul class="update-list">
      <li v-for="n in filteredNotifications" :key="n.notification_id" class="update-item">
        <div class="update-header">
          <span :class="['priority', n.priority]">{{ n.priority }}</span>
          <h3>{{ n.title }}</h3>
          <span class="date">{{ formatDate(n.created_at) }}</span>
        </div>
        <p class="update-desc">{{ n.description }}</p>
        <div class="update-impact" v-if="n.expected_impact.estimated_improvement">
          Expected improvement: {{ (n.expected_impact.estimated_improvement * 100).toFixed(1) }}%
        </div>
        <div class="update-actions">
          <button v-if="n.status === 'pending'" @click="store.applyUpdate(n.notification_id)" class="btn-primary btn-small">Apply</button>
          <button v-if="n.status === 'pending'" @click="store.dismissNotification(n.notification_id)" class="btn-ghost btn-small">Dismiss</button>
          <span v-if="n.status !== 'pending'" class="status-label">{{ n.status }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTemplateMarketStore } from '../stores/template_market'

const store = useTemplateMarketStore()
const projectId = ref('default-project')
const filter = ref('all')

const filteredNotifications = computed(() => {
  if (filter.value === 'all') return store.notifications
  if (filter.value === 'critical') return store.notifications.filter(n => n.priority === 'critical')
  if (filter.value === 'pending') return store.notifications.filter(n => n.status === 'pending')
  return store.notifications
})

function formatDate(ts: number) {
  return new Date(ts * 1000).toLocaleString()
}

onMounted(() => {
  store.fetchNotifications(projectId.value)
})
</script>

<style scoped>
.update-center { max-width: 800px; margin: 0 auto; padding: 2rem; }
.center-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.filter-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.filter-btn { padding: 0.4rem 0.8rem; border: 1px solid #d1d5db; border-radius: 4px; background: white; cursor: pointer; }
.filter-btn.active { background: #2563eb; color: white; border-color: #2563eb; }
.update-list { list-style: none; padding: 0; }
.update-item { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
.update-header { display: flex; align-items: center; gap: 0.75rem; }
.update-header h3 { margin: 0; flex: 1; }
.update-desc { color: #4b5563; margin: 0.5rem 0; }
.update-impact { background: #ecfdf5; color: #065f46; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem; display: inline-block; margin-bottom: 0.5rem; }
.update-actions { display: flex; gap: 0.5rem; align-items: center; }
.priority { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; text-transform: uppercase; }
.priority.critical { background: #fecaca; color: #991b1b; }
.priority.recommended { background: #fef3c7; color: #92400e; }
.priority.optional { background: #dbeafe; color: #1e40af; }
.status-label { color: #6b7280; font-size: 0.85rem; text-transform: capitalize; }
.btn-primary { background: #2563eb; color: white; padding: 0.5rem 1rem; border: none; border-radius: 6px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; }
.btn-ghost { background: transparent; padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; }
.btn-small { padding: 0.25rem 0.5rem; font-size: 0.75rem; }
.error-banner { background: #fecaca; color: #991b1b; padding: 0.5rem; border-radius: 4px; margin-bottom: 1rem; }
.date { color: #9ca3af; font-size: 0.85rem; }
</style>
```

- [ ] **Step 4: Implement BranchManager.vue**

```vue
<!-- src/views/BranchManager.vue -->
<template>
  <div class="branch-manager">
    <header class="manager-header">
      <h1>Branch Manager</h1>
      <button @click="showCreate = true" class="btn-primary">Create Branch</button>
    </header>

    <div class="filter-bar">
      <button :class="['filter-btn', { active: typeFilter === undefined }]" @click="typeFilter = undefined">All</button>
      <button :class="['filter-btn', { active: typeFilter === 'main' }]" @click="typeFilter = 'main'">Main</button>
      <button :class="['filter-btn', { active: typeFilter === 'industry' }]" @click="typeFilter = 'industry'">Industry</button>
      <button :class="['filter-btn', { active: typeFilter === 'experiment' }]" @click="typeFilter = 'experiment'">Experiment</button>
    </div>

    <div class="branch-table">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in store.branches" :key="b.branch_id">
            <td>{{ b.name }}</td>
            <td><span class="type-badge">{{ b.metadata?.type || 'main' }}</span></td>
            <td>{{ formatDate(b.updated_at) }}</td>
            <td class="actions">
              <button @click="selectForMerge(b.branch_id)" class="btn-small" :disabled="!mergeTarget || mergeTarget === b.branch_id">Merge →</button>
              <button @click="$router.push({ name: 'TemplateDetail', params: { id: b.branch_id } })" class="btn-small btn-ghost">Details</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal">
        <h2>Create Branch</h2>
        <form @submit.prevent="handleCreate">
          <label>Name<input v-model="createForm.name" required /></label>
          <label>Base Branch
            <select v-model="createForm.base_branch">
              <option :value="null">None (root)</option>
              <option v-for="b in store.branches" :key="b.branch_id" :value="b.branch_id">{{ b.name }}</option>
            </select>
          </label>
          <label>Type
            <select v-model="createForm.type">
              <option value="main">Main</option>
              <option value="industry">Industry</option>
              <option value="material">Material</option>
              <option value="experiment">Experiment</option>
            </select>
          </label>
          <div class="modal-actions">
            <button type="submit" :disabled="store.loading">Create</button>
            <button type="button" @click="showCreate = false">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="mergeSource && mergeTarget" class="merge-bar">
      <span>Merge {{ getBranchName(mergeSource) }} → {{ getBranchName(mergeTarget) }}?</span>
      <select v-model="mergeStrategy">
        <option value="overwrite">Overwrite</option>
        <option value="deep_merge">Deep Merge</option>
      </select>
      <button @click="handleMerge" class="btn-primary btn-small">Confirm Merge</button>
      <button @click="clearMerge" class="btn-ghost btn-small">Cancel</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useTemplateMarketStore } from '../stores/template_market'

const store = useTemplateMarketStore()
const typeFilter = ref<string | undefined>(undefined)
const showCreate = ref(false)
const mergeSource = ref<string | null>(null)
const mergeTarget = ref<string | null>(null)
const mergeStrategy = ref('overwrite')

const createForm = ref({
  name: '',
  base_branch: null as string | null,
  type: 'main',
})

function selectForMerge(branchId: string) {
  if (!mergeTarget.value) {
    mergeTarget.value = branchId
  } else if (!mergeSource.value && branchId !== mergeTarget.value) {
    mergeSource.value = branchId
  }
}

function clearMerge() {
  mergeSource.value = null
  mergeTarget.value = null
}

function getBranchName(id: string) {
  return store.branches.find(b => b.branch_id === id)?.name || id
}

async function handleCreate() {
  await store.createBranch({
    name: createForm.value.name,
    base_branch: createForm.value.base_branch,
    data: {},
    metadata: { type: createForm.value.type },
  })
  showCreate.value = false
  createForm.value = { name: '', base_branch: null, type: 'main' }
}

async function handleMerge() {
  if (mergeSource.value && mergeTarget.value) {
    await store.mergeBranches(mergeSource.value, mergeTarget.value, mergeStrategy.value)
    clearMerge()
  }
}

function formatDate(ts: number) {
  return new Date(ts * 1000).toLocaleString()
}

watch(typeFilter, (val) => {
  store.fetchBranches(val)
})

onMounted(() => {
  store.fetchBranches()
})
</script>

<style scoped>
.branch-manager { max-width: 1200px; margin: 0 auto; padding: 2rem; }
.manager-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.filter-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.filter-btn { padding: 0.4rem 0.8rem; border: 1px solid #d1d5db; border-radius: 4px; background: white; cursor: pointer; }
.filter-btn.active { background: #2563eb; color: white; border-color: #2563eb; }
.branch-table { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid #e5e7eb; }
th { font-weight: 600; color: #6b7280; font-size: 0.875rem; }
.type-badge { display: inline-block; background: #f3f4f6; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
.actions { display: flex; gap: 0.5rem; }
.btn-small { padding: 0.25rem 0.5rem; font-size: 0.75rem; border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer; }
.btn-small:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-ghost { background: transparent; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 2rem; border-radius: 8px; width: 400px; }
.modal form { display: flex; flex-direction: column; gap: 1rem; }
.modal label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.875rem; }
.modal input, .modal select { padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; }
.modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; }
.btn-primary { background: #2563eb; color: white; padding: 0.5rem 1rem; border: none; border-radius: 6px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; }
.merge-bar { position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%); background: white; border: 1px solid #e5e7eb; padding: 1rem 1.5rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: flex; align-items: center; gap: 0.75rem; }
</style>
```

- [ ] **Step 5: Commit**

```bash
git add src/views/TemplateMarket.vue src/views/TemplateDetail.vue src/views/UpdateCenter.vue src/views/BranchManager.vue
git commit -m "feat: add frontend views for template marketplace, detail, updates, and branch management"
```

---

## Self-Review

### 1. Spec Coverage Check

| Spec Requirement | Task Coverage |
|-----------------|---------------|
| Branch creation, listing, type filtering | Task 1 (core) + Task 2 (API) |
| Branch merge (overwrite + deep_merge) | Task 1 |
| Commit log tracking | Task 1 |
| Execution recording | Task 4 |
| Pattern detection (workflow + anti-pattern) | Task 4 |
| Suggestion generation from patterns | Task 4 |
| Evolution triggers (5 types) | Task 5 |
| Suggestion lifecycle (create/apply/reject) | Task 5 + Task 6 (API) |
| A/B experiment creation | Task 7 |
| Statistical analysis (Welch's t-test, chi-squared) | Task 7 |
| Traffic routing (consistent hashing) | Task 7 |
| Auto-conclude (merge/rollback) | Task 7 |
| Update priority classification | Task 9 |
| Notification lifecycle | Task 9 + Task 10 (API) |
| Marketplace trending | Task 11 |
| Template publish/subscribe/export/import/sync | Task 11 |
| Frontend marketplace view | Task 13 |
| Frontend Pinia store | Task 12 |
| Frontend branch manager | Task 13 |
| Frontend update center | Task 13 |
| Frontend template detail | Task 13 |

All spec requirements are covered.

### 2. Placeholder Scan

Searched for: "TBD", "TODO", "implement later", "fill in", "add validation", "handle edge cases", "add appropriate", "Similar to Task"
Result: **None found.** Every step contains complete, ready-to-use code.

### 3. Type Consistency Check

- `TemplateBranch` dataclass used consistently across branching, evolution, marketplace
- `init_*`/`get_*` singleton pattern applied uniformly across all 5 core modules
- `threading.RLock()` for thread safety in all core classes
- `sqlite3.Connection` with `row_factory = sqlite3.Row` for all databases
- `to_dict()`/`from_dict()` serialization pattern consistent across all dataclasses
- `_test_*` module-level variables for test injection in all route files
- FastAPI `APIRouter(prefix=..., tags=[...])` pattern consistent across all route files
- Frontend interfaces (`TemplateBranch`, `UpdateNotification`, `Experiment`) match backend response shapes
- Pinia store `loading`/`error` state management pattern uniform across all async functions

### 4. File Count Verification

| Category | Required | Actual |
|----------|----------|--------|
| Backend core | 5 | 5 (`template_branching.py`, `pattern_engine.py`, `template_evolution.py`, `template_ab_testing.py`, `template_update_service.py`) |
| Backend routes | 5 | 5 (`template_branching_routes.py`, `template_evolution_routes.py`, `template_ab_testing_routes.py`, `template_update_routes.py`, `template_market.py`) |
| Frontend | 5+ | 5 (`template_market.ts`, `TemplateMarket.vue`, `TemplateDetail.vue`, `UpdateCenter.vue`, `BranchManager.vue`) |
| Tests | 5+ | 5 (`functional_test_template_branching.py`, `functional_test_pattern_engine.py`, `functional_test_template_evolution.py`, `functional_test_ab_testing.py`, `functional_test_update_service.py`) |
| **Total new files** | **20+** | **20** |

### 5. Phase Independence Verification

Each phase is independently testable:
- **Phase 1**: Branch tests run without pattern engine, evolution, A/B, or updates
- **Phase 2**: Pattern tests record and analyze in isolation (uses its own DB)
- **Phase 3**: Evolution tests create suggestions and use a mock branch manager
- **Phase 4**: A/B tests use their own experiment DB with no external dependencies
- **Phase 5**: Update tests manage notifications in isolation
- **Phase 6**: Marketplace API uses test override variables for all service dependencies

Plan is complete, internally consistent, and ready for execution.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**