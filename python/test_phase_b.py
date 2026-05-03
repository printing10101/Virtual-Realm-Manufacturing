import os
import json
import glob
import asyncio
from pathlib import Path
from app.core.container import container
from app.core.workflow_logger import workflow_logger, StepType


async def test_workflow_logger():
    print("Testing AIWorkflowLogger...")
    
    task_id = "test-task-001"
    
    with workflow_logger.log_step(
        task_id=task_id,
        agent_name="test_agent",
        step_type=StepType.LLM_CALL,
        input_data={"prompt": "test prompt", "sensitive_key": "should_be_redacted"},
        model_name="test-model"
    ) as log_entry:
        await asyncio.sleep(0.1)
        log_entry.output = {"response": "test response"}
        log_entry.token_usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    
    log_file = workflow_logger._get_log_file()
    assert log_file.exists(), "Log file should exist"
    print(f"[OK] Log file created: {log_file}")
    
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) > 0, "Log file should have entries"
        
        last_entry = json.loads(lines[-1])
        assert last_entry["task_id"] == task_id
        assert last_entry["agent_name"] == "test_agent"
        assert last_entry["step_type"] == StepType.LLM_CALL.value
        assert "duration_ms" in last_entry
        assert last_entry["duration_ms"] > 0
        print(f"[OK] Log entry format correct, duration: {last_entry['duration_ms']:.2f}ms")
        
        if "input" in last_entry:
            assert "sensitive_key" not in last_entry["input"] or last_entry["input"].get("sensitive_key") == "[REDACTED]"
            print("[OK] Sensitive data filtered correctly")
    
    print("[OK] AIWorkflowLogger tests passed!\n")


async def test_container():
    print("Testing ServiceContainer...")
    
    container.initialize()
    
    task_manager = container.get_service("task_manager")
    assert task_manager is not None, "TaskManager should be available"
    print("[OK] TaskManager retrieved from container")
    
    workflow_logger_service = container.get_service("workflow_logger")
    assert workflow_logger_service is not None, "WorkflowLogger should be available"
    print("[OK] WorkflowLogger retrieved from container")
    
    ai_service = container.get_service("ai_service")
    assert ai_service is not None, "AIService should be available"
    assert ai_service.task_manager == task_manager, "AIService should share TaskManager instance"
    print("[OK] AIService retrieved with correct dependencies")
    
    process_service = container.get_service("process_service")
    assert process_service is not None, "ProcessService should be available"
    assert process_service.task_manager == task_manager, "ProcessService should share TaskManager instance"
    print("[OK] ProcessService retrieved with correct dependencies")
    
    report_service = container.get_service("report_service")
    assert report_service is not None, "ReportService should be available"
    print("[OK] ReportService retrieved")
    
    validation_service = container.get_service("validation_service")
    assert validation_service is not None, "ValidationService should be available"
    print("[OK] ValidationService retrieved")
    
    knowledge_service = container.get_service("knowledge_service")
    assert knowledge_service is not None, "KnowledgeService should be available"
    print("[OK] KnowledgeService retrieved")
    
    model_service = container.get_service("model_service")
    assert model_service is not None, "ModelService should be available"
    print("[OK] ModelService retrieved")
    
    process_service_2 = container.get_service("process_service")
    assert process_service is process_service_2, "ProcessService should be singleton"
    print("[OK] Service instances are singletons")
    
    print("[OK] ServiceContainer tests passed!\n")


async def test_log_cleanup():
    print("Testing log cleanup...")
    
    log_dir = Path("logs/workflows")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    old_file = log_dir / "workflow_2020-01-01.jsonl"
    with open(old_file, "w", encoding="utf-8") as f:
        f.write('{"test": "old_log"}\n')
    
    new_logger = workflow_logger.__class__(log_dir=str(log_dir), retention_days=30)
    new_logger._cleanup_old_logs()
    
    assert not old_file.exists(), "Old log file should be deleted"
    print("[OK] Old log files cleaned up correctly")
    
    print("[OK] Log cleanup tests passed!\n")


async def test_jsonl_format():
    print("Testing JSONL format compliance...")
    
    log_file = workflow_logger._get_log_file()
    
    with open(log_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    assert isinstance(entry, dict), f"Line {i} should be a JSON object"
                except json.JSONDecodeError as e:
                    raise AssertionError(f"Line {i} is not valid JSON: {e}")
    
    print("[OK] All log entries are valid JSON (JSONL format)")
    print("[OK] JSONL format tests passed!\n")


async def main():
    print("=" * 50)
    print("Phase B Test Suite")
    print("=" * 50)
    
    try:
        await test_workflow_logger()
        await test_container()
        await test_log_cleanup()
        await test_jsonl_format()
        
        print("=" * 50)
        print("ALL PHASE B TESTS PASSED!")
        print("=" * 50)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
