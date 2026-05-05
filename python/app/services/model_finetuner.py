import glob
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import config
from app.core.workflow_logger import AIWorkflowLogger, StepType


class DataSanitizer:
    SENSITIVE_KEYS = [
        "customer_name", "project_id", "project_name", "client",
        "price", "cost", "budget", "contract_number",
        "file_path", "file_content", "binary_data",
        "password", "secret", "token", "api_key"
    ]

    PATTERN_KEYWORDS = [
        "客户", "项目", "价格", "成本", "合同", "订单",
        "customer", "project", "price", "cost", "contract"
    ]

    SENSITIVE_PATTERNS = [
        (r'(?:客户|客户名称|customer|client)[:：\s]*([^\s,，;；]+)', '客户信息'),
        (r'(?:价格|price|cost|成本|预算|budget)[:：\s]*(\d+\.?\d*)', '价格信息'),
        (r'(?:合同|合同号|contract|订单|订单号)[:：\s]*([A-Za-z0-9\-]+)', '合同订单'),
        (r'(?:项目|project)[:：\s]*([^\s,，;；]{3,})', '项目名称'),
        (r'\b(?:tel|phone|mobile|电话|手机)[:：\s]*([1][3-9]\d{9})', '电话号码'),
        (r'\b(?:email|邮箱|mail)[:：\s]*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', '邮箱地址'),
    ]

    @classmethod
    def sanitize(cls, data: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}
        for key, value in data.items():
            if cls._is_sensitive_key(key):
                continue
            if isinstance(value, dict):
                sanitized[key] = cls.sanitize(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    cls.sanitize(item) if isinstance(item, dict) else cls._sanitize_string(item) if isinstance(item, str) else item
                    for item in value
                ]
            elif isinstance(value, str):
                sanitized[key] = cls._sanitize_string(value)
            else:
                sanitized[key] = value
        return sanitized

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        key_lower = key.lower()
        return key_lower in cls.SENSITIVE_KEYS or any(
            kw in key_lower for kw in cls.PATTERN_KEYWORDS
        )

    @classmethod
    def _sanitize_string(cls, text: str) -> str:
        sanitized_text = text
        found_sensitive = False

        for pattern, _sensitive_type in cls.SENSITIVE_PATTERNS:
            match = re.search(pattern, sanitized_text)
            if match:
                found_sensitive = True
                if match.groups():
                    sensitive_value = match.group(1)
                    if len(sensitive_value) > 6:
                        replacement = sensitive_value[:2] + '*' * (len(sensitive_value) - 4) + sensitive_value[-2:]
                    else:
                        replacement = '*' * len(sensitive_value)
                    sanitized_text = sanitized_text.replace(sensitive_value, replacement)

        if found_sensitive:
            return sanitized_text

        for kw in cls.PATTERN_KEYWORDS:
            if kw in text.lower() and len(text) < 20:
                return "[REDACTED]"

        return text


class FineTuneManager:
    def __init__(self, workflow_logger: AIWorkflowLogger | None = None):
        self.logger = workflow_logger
        self.sanitizer = DataSanitizer()
        self.output_dir = Path(config.finetune.finetune_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_path = self.output_dir / "training_data.jsonl"
        self.status_path = self.output_dir / "finetune_status.json"
        self.model_dir = self.output_dir / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def collect_training_data(self) -> list[dict[str, Any]]:
        log_dir = Path(self.logger.log_dir) if self.logger else Path("logs/workflows")
        log_files = sorted(glob.glob(str(log_dir / "workflow_*.jsonl")))

        training_data = []
        for log_file in log_files:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if self._is_cloud_quality_entry(entry):
                            training_data.append(entry)
                    except json.JSONDecodeError:
                        continue

        return training_data

    def sanitize_for_local(self, raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized_data = []
        for entry in raw_data:
            sanitized = self.sanitizer.sanitize(entry)
            training_sample = self._extract_training_sample(sanitized)
            if training_sample and self._is_valid_sample(training_sample):
                sanitized_data.append(training_sample)
        return sanitized_data

    def build_dataset(self, sanitized_data: list[dict[str, Any]]) -> str:
        dataset = []
        for sample in sanitized_data:
            instruction = sample.get("instruction", "")
            input_text = sample.get("input", "")
            output_text = sample.get("output", "")

            if not instruction or not output_text:
                continue

            dataset.append({
                "instruction": instruction,
                "input": input_text,
                "output": output_text,
                "source": sample.get("source", "cloud_refined"),
                "timestamp": sample.get("timestamp", datetime.now().isoformat())
            })

        dataset_path = str(self.dataset_path)
        with open(dataset_path, "w", encoding="utf-8") as f:
            for entry in dataset:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return dataset_path

    def trigger_finetune(self, force: bool = False) -> dict[str, Any]:
        if not force and not self._should_trigger_finetune():
            return {
                "status": "skipped",
                "reason": "Trigger conditions not met",
                "current_samples": self._get_current_sample_count(),
                "min_samples": config.finetune.finetune_min_samples,
                "last_finetune": self._get_last_finetune_date()
            }

        raw_data = self.collect_training_data()
        sanitized_data = self.sanitize_for_local(raw_data)
        dataset_path = self.build_dataset(sanitized_data)

        if len(sanitized_data) < config.finetune.finetune_min_samples and not force:
            return {
                "status": "insufficient_data",
                "current_samples": len(sanitized_data),
                "min_samples": config.finetune.finetune_min_samples
            }

        self._update_status("running", {
            "started_at": datetime.now().isoformat(),
            "dataset_size": len(sanitized_data),
            "dataset_path": dataset_path
        })

        try:
            result = self._execute_lora_finetune(dataset_path, sanitized_data)
            self._update_status("completed", {
                "completed_at": datetime.now().isoformat(),
                "result": result
            })
            self._update_last_finetune_date()
            return {"status": "completed", "result": result}
        except Exception as e:
            self._update_status("failed", {
                "failed_at": datetime.now().isoformat(),
                "error": str(e)
            })
            return {"status": "failed", "error": str(e)}

    def rollback_model(self) -> dict[str, Any]:
        status = self._get_status()
        if status.get("status") != "completed":
            return {"status": "nothing_to_rollback", "message": "No completed finetune found"}

        current_model = status.get("model_path")
        if not current_model or not Path(current_model).exists():
            return {"status": "rollback_failed", "message": "Current model not found"}

        backup_model = current_model + ".backup"
        if Path(backup_model).exists():
            try:
                shutil.copy2(backup_model, current_model)
                self._update_status("rolled_back", {
                    "rolled_back_at": datetime.now().isoformat(),
                    "previous_model": current_model,
                    "restored_from": backup_model
                })
                return {"status": "rollback_completed", "restored_from": backup_model}
            except Exception as e:
                return {"status": "rollback_failed", "error": str(e)}
        else:
            return {"status": "rollback_failed", "message": "Backup model not found"}

    def get_finetune_status(self) -> dict[str, Any]:
        return self._get_status()

    def _is_cloud_quality_entry(self, entry: dict[str, Any]) -> bool:
        if entry.get("step_type") != StepType.LLM_CALL.value:
            return False
        output = entry.get("output", {})
        response_length = output.get("response_length", 0)
        if response_length < 50:
            return False
        error = output.get("error")
        return not error

    def _extract_training_sample(self, sanitized_entry: dict[str, Any]) -> dict[str, Any] | None:
        input_data = sanitized_entry.get("input", {})
        output_data = sanitized_entry.get("output", {})

        if not input_data or not output_data:
            return None

        instruction = input_data.get("prompt_type", "") or input_data.get("agent_name", "")
        if not instruction:
            instruction = f"工艺生成任务 - {sanitized_entry.get('agent_name', '')}"

        input_text = json.dumps({
            "material": input_data.get("material", ""),
            "tool": input_data.get("tool", ""),
            "requirements": input_data.get("requirements", ""),
            "constraints": input_data.get("constraints", [])
        }, ensure_ascii=False)

        output_text = output_data.get("content", "") or json.dumps(output_data, ensure_ascii=False)

        return {
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
            "source": "cloud_refined",
            "agent_name": sanitized_entry.get("agent_name", ""),
            "timestamp": sanitized_entry.get("timestamp", datetime.now().isoformat())
        }

    def _is_valid_sample(self, sample: dict[str, Any]) -> bool:
        if not sample.get("instruction") or not sample.get("output"):
            return False
        return not len(sample["output"]) < 20

    def _should_trigger_finetune(self) -> bool:
        current_samples = self._get_current_sample_count()
        if current_samples < config.finetune.finetune_min_samples:
            return False

        last_finetune = self._get_last_finetune_date()
        if last_finetune:
            last_date = datetime.fromisoformat(last_finetune)
            if datetime.now() - last_date < timedelta(days=config.finetune.finetune_interval_days):
                return False

        return True

    def _get_current_sample_count(self) -> int:
        if not self.dataset_path.exists():
            return 0
        with open(self.dataset_path, encoding="utf-8") as f:
            return sum(1 for _ in f)

    def _get_last_finetune_date(self) -> str | None:
        status = self._get_status()
        return status.get("last_finetune_date")

    def _update_last_finetune_date(self):
        status = self._get_status()
        status["last_finetune_date"] = datetime.now().isoformat()
        with open(self.status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)

    def _get_status(self) -> dict[str, Any]:
        if self.status_path.exists():
            with open(self.status_path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "status": "idle",
            "last_finetune_date": None,
            "model_path": None,
            "history": []
        }

    def _update_status(self, status: str, details: dict[str, Any]):
        current = self._get_status()
        current["status"] = status
        current.update(details)
        current["history"].append({
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details
        })
        if len(current["history"]) > 50:
            current["history"] = current["history"][-50:]
        with open(self.status_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

    def _execute_lora_finetune(self, dataset_path: str, data: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "method": "lora_simulation",
            "dataset_path": dataset_path,
            "samples_used": len(data),
            "base_model": config.model_router.local_model,
            "message": "LoRA 微调已模拟完成。实际部署需要：1) 安装 unsloth 或 llama.cpp 2) 配置 GPU 环境 3) 执行真实微调流程",
            "note": "当前为框架实现，生产环境可集成 unsloth 的 LoRA 训练脚本"
        }
