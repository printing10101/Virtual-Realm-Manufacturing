import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.core.task_manager import task_manager, TaskType, TaskStatus


async def test_task_manager_basic():
    print("Testing TaskManager basic functionality...")
    
    task_id = task_manager.create_task(TaskType.WORKFLOW_EXECUTION, {"test": True})
    print(f"[OK] Task created: {task_id}")
    
    task = task_manager.get_task(task_id)
    assert task is not None, "Task should exist"
    assert task.status == TaskStatus.PENDING, "Task should be pending"
    print("[OK] Task status is PENDING")
    
    await task_manager.update_progress(task_id, 50.0, "Testing progress")
    task = task_manager.get_task(task_id)
    assert task.progress == 50.0, "Progress should be 50"
    print("[OK] Progress updated to 50%")
    
    await task_manager.complete_task(task_id, {"result": "success"})
    
    # After completion, task is cleaned up and should not be retrievable
    task = task_manager.get_task(task_id)
    assert task is None, "Task should be cleaned up after completion"
    print("[OK] Task completed and cleaned up successfully")
    
    print("\n[OK] All basic tests passed!")


async def test_concurrent_tasks():
    print("\nTesting concurrent task management...")
    
    task_ids = []
    for i in range(3):
        task_id = task_manager.create_task(TaskType.PROCESS_GENERATION, {"iteration": i})
        task_ids.append(task_id)
    
    assert len(task_ids) == 3, "Should have 3 tasks"
    print(f"[OK] Created 3 concurrent tasks")
    
    tasks = task_manager.list_tasks(task_type_filter=TaskType.PROCESS_GENERATION)
    assert len(tasks) == 3, "Should list 3 tasks"
    print("[OK] List tasks works correctly")
    
    for task_id in task_ids:
        await task_manager.complete_task(task_id, {"iteration_result": "done"})
    
    print("[OK] All concurrent tasks completed")
    
    print("\n[OK] All concurrent tests passed!")


async def test_task_cancellation():
    print("\nTesting task cancellation...")
    
    task_id = task_manager.create_task(TaskType.SIMULATION_VALIDATION)
    print(f"[OK] Task created: {task_id}")
    
    await task_manager.cancel_task(task_id)
    task = task_manager.get_task(task_id)
    assert task is None, "Task should be cleaned up after cancellation"
    print("[OK] Task cancelled and cleaned up successfully")
    
    print("\n[OK] All cancellation tests passed!")


async def main():
    print("=" * 50)
    print("TaskManager Test Suite")
    print("=" * 50)
    
    try:
        await test_task_manager_basic()
        await test_concurrent_tasks()
        await test_task_cancellation()
        
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED!")
        print("=" * 50)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
