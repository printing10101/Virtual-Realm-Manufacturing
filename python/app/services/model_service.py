import os
from pathlib import Path
from typing import Optional, Dict, Any
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType


class ModelService:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self._supported_formats = ["stl", "obj", "step", "iges", "3mf"]

    async def parse_model(self, task_id: str, file_path: str) -> Dict[str, Any]:
        with self.logger.log_step(
            task_id, "model_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "parse_model", "file_path": file_path}
        ) as log_entry:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {file_path}")

            file_format = path.suffix.lstrip(".").lower()
            if file_format not in self._supported_formats:
                raise ValueError(f"Unsupported format: {file_format}")

            file_size = path.stat().st_size

            result = {
                "file_path": str(path),
                "format": file_format,
                "size_bytes": file_size
            }
            log_entry.output = result
            return result

    async def convert_format(self, task_id: str, input_path: str, output_format: str) -> str:
        with self.logger.log_step(
            task_id, "model_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "convert_format", "input_path": input_path, "output_format": output_format}
        ) as log_entry:
            if output_format not in self._supported_formats:
                raise ValueError(f"Unsupported output format: {output_format}")

            input_path_obj = Path(input_path)
            output_path = input_path_obj.with_suffix(f".{output_format}")

            with open(input_path_obj, "rb") as f:
                content = f.read()

            with open(output_path, "wb") as f:
                f.write(content)

            result = {
                "output_path": str(output_path),
                "format": output_format
            }
            log_entry.output = result
            return str(output_path)

    async def get_model_info(self, task_id: str, file_path: str) -> Dict[str, Any]:
        with self.logger.log_step(
            task_id, "model_service", StepType.CONSTRAINT_PARSE,
            input_data={"action": "get_model_info", "file_path": file_path}
        ) as log_entry:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Model file not found: {file_path}")

            stat = path.stat()
            result = {
                "path": str(path),
                "size_bytes": stat.st_size,
                "format": path.suffix.lstrip(".").lower(),
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime
            }
            log_entry.output = result
            return result

    async def validate_model(self, task_id: str, file_path: str) -> Dict[str, Any]:
        with self.logger.log_step(
            task_id, "model_service", StepType.VALIDATION,
            input_data={"action": "validate_model", "file_path": file_path}
        ) as log_entry:
            path = Path(file_path)
            if not path.exists():
                return {"valid": False, "error": "File not found"}

            file_format = path.suffix.lstrip(".").lower()
            if file_format not in self._supported_formats:
                return {"valid": False, "error": f"Unsupported format: {file_format}"}

            result = {
                "valid": True,
                "format": file_format,
                "file_path": str(path)
            }
            log_entry.output = result
            return result


model_service = ModelService
