import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from app.core.process_trace import ProcessTrace, TraceNode
from app.core.task_manager import TaskManager, TaskType
from app.core.workflow_logger import AIWorkflowLogger
from app.services.process_service import ProcessService


class MockConfig:
    pass


async def test_process_service_with_trace():
    task_manager = TaskManager()
    workflow_logger = AIWorkflowLogger(log_dir="test_logs/workflows")
    config = MockConfig()
    
    process_service = ProcessService(task_manager, workflow_logger, config)
    
    print("=== 测试1：创建初始工艺参数生成 ===")
    result1 = await process_service.generate_process_params_with_task(
        material="45钢",
        part_type="轴类"
    )
    print(f"结果: {result1.get('trace_node_id', 'N/A')}")
    task_id1 = result1.get('trace_node_id', '').split('-')[0] if result1.get('trace_node_id') else None
    
    print(f"\nTrace节点数量: {len(process_service.trace.nodes)}")
    for node_id, node in process_service.trace.nodes.items():
        print(f"  - {node_id[:8]}: {node.hypothesis[:30]}...")
    
    print("\n=== 测试2：创建修正分支 ===")
    if process_service.trace.nodes:
        first_node_id = list(process_service.trace.nodes.keys())[0]
        print(f"基于节点 {first_node_id[:8]} 创建修正分支")
        
        result2 = await process_service.retry_with_correction(
            original_task_id="",
            failed_node_id=first_node_id,
            correction_reason="切削速度过高导致刀具寿命不足",
            material="45钢",
            part_type="轴类"
        )
        print(f"修正结果: {result2.get('trace_node_id', 'N/A')}")
    
    print(f"\nTrace节点数量: {len(process_service.trace.nodes)}")
    for node_id, node in process_service.trace.nodes.items():
        print(f"  - {node_id[:8]}: 假设={node.hypothesis[:30]}..., SOTA={node.is_sota}")
    
    print("\n=== 测试3：获取演化链 ===")
    if process_service.trace.nodes:
        last_node_id = list(process_service.trace.nodes.keys())[-1]
        chain = process_service.trace.get_evolution_chain(last_node_id)
        print(f"演化链长度: {len(chain)}")
        for i, node in enumerate(chain):
            print(f"  {i+1}. {node.node_id[:8]}: {node.hypothesis[:40]}...")
    
    print("\n=== 测试4：获取分支 ===")
    if process_service.trace.nodes:
        first_node_id = list(process_service.trace.nodes.keys())[0]
        branches = process_service.trace.get_branches(first_node_id)
        print(f"分支数量: {len(branches)}")
        for i, branch in enumerate(branches):
            print(f"  分支{i+1}: {len(branch)}个节点")
    
    print("\n=== 测试5：获取SOTA ===")
    sota_node = process_service.trace.get_sota_node()
    if sota_node:
        print(f"SOTA节点: {sota_node.node_id[:8]}")
        print(f"指标: {sota_node.metrics}")
    else:
        print("无SOTA节点")
    
    print("\n=== 测试6：Mermaid输出 ===")
    mermaid = process_service.trace.to_mermaid()
    print(mermaid)
    
    print("\n=== 测试7：JSON序列化 ===")
    export_path = process_service.trace.export_json("test_traces/api_test.json")
    print(f"导出路径: {export_path}")
    
    new_trace = ProcessTrace(storage_dir="test_traces")
    new_trace.import_json("test_traces/api_test.json")
    print(f"导入后节点数: {len(new_trace.nodes)}")
    
    print("\n所有测试完成!")


if __name__ == "__main__":
    asyncio.run(test_process_service_with_trace())
