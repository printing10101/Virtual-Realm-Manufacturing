"""
Model Registry Service

Provides a thread-safe singleton service that unifies access to:
- LNNModelRegistry (model registration & metadata)
- ModelCache (predictor caching)
- training_tasks (training task state)

This eliminates the dual-instance problem where lnn.py and agent_gateway.py
each created their own LNNModelRegistry, causing data inconsistency.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from app.ai.lnn.inference.registry import LNNModelRegistry, ModelRegistry
from app.ai.lnn.inference.model_cache import get_model_cache, ModelCache


class ModelRegistryService:
    """
    Thread-safe singleton service for unified model registry access.

    All modules must access model registry, model cache, and training tasks
    through this service instance — never by directly instantiating LNNModelRegistry
    or ModelCache.
    """

    _instance: Optional[ModelRegistryService] = None
    _lock = threading.Lock()

    def __init__(self):
        self._model_registry: LNNModelRegistry = LNNModelRegistry()
        self._pytorch_registry: ModelRegistry = ModelRegistry()
        self._model_cache: ModelCache = get_model_cache()
        self._training_tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ModelRegistryService":
        """
        Get the singleton instance using double-checked locking.

        Returns:
            The unique ModelRegistryService instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing purposes)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance = None

    # ── Model Registry Delegation ──────────────────────────────────────

    @property
    def model_registry(self) -> LNNModelRegistry:
        """Get the shared LNNModelRegistry instance."""
        return self._model_registry

    @property
    def pytorch_registry(self) -> ModelRegistry:
        """Get the shared ModelRegistry (PyTorch) instance."""
        return self._pytorch_registry

    def register_model(self, model_info) -> bool:
        """Register a new model."""
        return self._model_registry.register_model(model_info)

    def register_quantized_model(self, *args, **kwargs) -> bool:
        """Register a quantized model."""
        return self._model_registry.register_quantized_model(*args, **kwargs)

    def get_model_entry(self, model_name: str):
        """Get a model entry by name. Returns None if not found (no exception)."""
        return self._model_registry.registry.get(model_name)

    def list_models(self, return_objects: bool = False):
        """List all registered models."""
        return self._model_registry.list_models(return_objects=return_objects)

    def validate_model(self, model_name: str) -> Dict[str, Any]:
        """Validate a model."""
        return self._model_registry.validate_model(model_name)

    # ── Model Cache Delegation ─────────────────────────────────────────

    @property
    def model_cache(self) -> ModelCache:
        """Get the shared ModelCache instance."""
        return self._model_cache

    def get_cached_predictor(self, model_name: str):
        """Get a cached predictor by model name."""
        return self._model_cache.get(model_name)

    def cache_predictor(self, model_name: str, predictor, memory_size_bytes: int = 0) -> None:
        """Cache a predictor instance."""
        self._model_cache.put(model_name, predictor, memory_size_bytes)

    def clear_cache(self):
        """Clear all cached predictors."""
        return self._model_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._model_cache.get_stats()

    # ── Training Task Management ───────────────────────────────────────

    def get_training_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get the shared training tasks dictionary."""
        return self._training_tasks

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific training task by ID."""
        return self._training_tasks.get(task_id)

    def create_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """Create a new training task entry."""
        with self._tasks_lock:
            self._training_tasks[task_id] = task_data

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing training task. Returns False if task not found."""
        with self._tasks_lock:
            if task_id in self._training_tasks:
                self._training_tasks[task_id].update(updates)
                return True
            return False

    def remove_task(self, task_id: str) -> bool:
        """Remove a training task. Returns False if not found."""
        with self._tasks_lock:
            if task_id in self._training_tasks:
                del self._training_tasks[task_id]
                return True
            return False


# Module-level singleton accessor — ensures global single point of access
def get_model_registry_service() -> ModelRegistryService:
    """
    Get the global ModelRegistryService singleton.

    This is the preferred way to access model registry functionality
    from any module. Do NOT directly instantiate LNNModelRegistry.
    """
    return ModelRegistryService.get_instance()
