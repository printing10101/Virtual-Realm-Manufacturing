import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.workflow_logger import AIWorkflowLogger, StepType


class TestLogSanitizationIntegration:
    @pytest.fixture
    def temp_log_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_workflow_logger_sanitizes_process_params(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        with logger.log_step(
            task_id="task_001",
            agent_name="process_agent",
            step_type=StepType.SOLVER_RUN,
            input_data={"cutting_speed": 1200, "feed_rate": 0.25},
            output_data={"result": "success"}
        ) as entry:
            entry.output = {"status": "completed"}

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert log_entry["input"]["cutting_speed"] == "[工艺参数已脱敏]"
        assert log_entry["input"]["feed_rate"] == "[工艺参数已脱敏]"

    def test_workflow_logger_sanitizes_api_keys(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        with logger.log_step(
            task_id="task_002",
            agent_name="llm_agent",
            step_type=StepType.LLM_CALL,
            input_data={"api_key": "sk_abcdef1234567890abcdef1234567890"},
            output_data={"response": "success"}
        ):
            pass

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert "sk_abcdef1234567890abcdef1234567890" not in str(log_entry)
        assert "[已脱敏]" in str(log_entry["input"]["api_key"])

    def test_workflow_logger_sanitizes_file_content(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        with logger.log_step(
            task_id="task_003",
            agent_name="cad_agent",
            step_type=StepType.WORKFLOW_START,
            input_data={"file_content": "G01 X100 Y200 Z300"},
            output_data=None
        ) as entry:
            entry.output = {"status": "processed"}

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert "G01 X100 Y200 Z300" not in str(log_entry)
        assert "[文件内容已脱敏" in str(log_entry["input"]["file_content"])

    def test_workflow_logger_sanitizes_user_input(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        long_description = "A" * 100
        with logger.log_step(
            task_id="task_004",
            agent_name="planning_agent",
            step_type=StepType.TASK_PROGRESS,
            input_data={"description": long_description},
            output_data={"progress": 50}
        ):
            pass

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert log_entry["input"]["description"] == "A" * 50 + "..."

    def test_workflow_logger_preserves_normal_data(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        with logger.log_step(
            task_id="task_005",
            agent_name="validator",
            step_type=StepType.VALIDATION,
            input_data={"status": "checking", "count": 42},
            output_data={"result": "valid"}
        ):
            pass

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert log_entry["input"]["status"] == "checking"
        assert log_entry["input"]["count"] == 42
        assert log_entry["output"]["result"] == "valid"

    def test_workflow_logger_can_disable_sanitization(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir, enable_sanitization=False)

        with logger.log_step(
            task_id="task_006",
            agent_name="debug_agent",
            step_type=StepType.LLM_CALL,
            input_data={"api_key": "sk_secret1234567890abcdef1234567890"},
            output_data={"data": "normal output"}
        ):
            pass

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert "sk_secret1234567890abcdef1234567890" in str(log_entry["input"]["api_key"])

    def test_workflow_logger_token_usage_sanitized(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        logger.log_token_usage(
            task_id="task_007",
            agent_name="llm_agent",
            step_type=StepType.LLM_CALL,
            token_usage={"prompt": 100, "completion": 50},
            model_name="qwen2.5:7b"
        )

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert log_entry["task_id"] == "task_007"
        assert log_entry["token_usage"]["prompt"] == 100

    def test_workflow_logger_handles_exception(self, temp_log_dir):
        logger = AIWorkflowLogger(log_dir=temp_log_dir)

        with pytest.raises(ValueError), logger.log_step(
            task_id="task_008",
            agent_name="error_agent",
            step_type=StepType.VALIDATION,
            input_data={"description": "A" * 100}
        ):
            raise ValueError("Test error")

        log_file = logger._get_log_file()
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            log_entry = json.loads(lines[-1])

        assert "error" in log_entry["output"]
        assert "A" * 100 not in str(log_entry["input"])
        assert "A" * 50 + "..." in str(log_entry["input"]["description"])
