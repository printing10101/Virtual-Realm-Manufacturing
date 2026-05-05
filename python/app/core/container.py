from typing import Any

from app.config import config
from app.core.task_manager import task_manager
from app.core.workflow_logger import workflow_logger


class ServiceContainer:
    def __init__(self):
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Any] = {}
        self._initialized = False

    def register_singleton(self, name: str, instance: Any):
        self._services[name] = instance

    def register_factory(self, name: str, factory_func: Any):
        self._factories[name] = factory_func

    def get_service(self, name: str) -> Any | None:
        if name in self._services:
            return self._services[name]
        if name in self._factories:
            instance = self._factories[name]()
            self._services[name] = instance
            return instance
        return None

    def initialize(self):
        if self._initialized:
            return

        self.register_singleton("task_manager", task_manager)
        self.register_singleton("workflow_logger", workflow_logger)
        self.register_singleton("config", config)

        self.register_factory("ai_service", self._create_ai_service)
        self.register_factory("process_service", self._create_process_service)
        self.register_factory("report_service", self._create_report_service)
        self.register_factory("validation_service", self._create_validation_service)
        self.register_factory("knowledge_service", self._create_knowledge_service)
        self.register_factory("model_service", self._create_model_service)
        self.register_factory("dataset_manager", self._create_dataset_manager)
        self.register_factory("validation_engine", self._create_validation_engine)
        self.register_factory("model_router", self._create_model_router)
        self.register_factory("finetuner", self._create_finetuner)
        self.register_factory("settings_service", self._create_settings_service)
        self.register_factory("project_service", self._create_project_service)

        self._initialized = True

    def _create_ai_service(self):
        from app.services.ai_service import AIService
        return AIService(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_process_service(self):
        from app.services.process_service import ProcessService
        return ProcessService(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_report_service(self):
        from app.services.report_service import ReportGenerationService
        return ReportGenerationService(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_validation_service(self):
        from app.services.validation_service import SimulationValidationService
        return SimulationValidationService(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_knowledge_service(self):
        from app.services.knowledge_service import KnowledgeService
        return KnowledgeService(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_model_service(self):
        from app.services.model_service import ModelService
        return ModelService(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_dataset_manager(self):
        from app.services.dataset_manager import DatasetManager
        return DatasetManager()

    def _create_validation_engine(self):
        from app.services.validation_engine import ValidationEngine
        return ValidationEngine(
            task_manager=self.get_service("task_manager"),
            workflow_logger=self.get_service("workflow_logger"),
            config=self.get_service("config")
        )

    def _create_model_router(self):
        from app.services.model_router import ModelRouter
        return ModelRouter(
            workflow_logger=self.get_service("workflow_logger")
        )

    def _create_finetuner(self):
        from app.services.model_finetuner import FineTuneManager
        return FineTuneManager(
            workflow_logger=self.get_service("workflow_logger")
        )

    def _create_settings_service(self):
        from app.services.settings_repository import SettingsService
        return SettingsService()

    def _create_project_service(self):
        from app.services.project_repository import ProjectService
        return ProjectService()


container = ServiceContainer()
