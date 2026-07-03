"""Task router subpackage for the LNN hybrid inference engine.

Status: Experimental / Stub implementation.

The router module provides hybrid (rule + ML) decision logic for selecting
the optimal inference engine per task. The full algorithm described in
``ARCHITECTURE.md`` §3.3 is not yet implemented; this stub returns a
deterministic fallback decision so that downstream consumers (e.g. the
research agents in ``research/agents_research/agents.py``) can import the
public API without silent failures.

See ARCHITECTURE.md for the target design contract.
"""

from app.ai.lnn.router.task_router import TaskRouter

__all__ = ["TaskRouter"]
