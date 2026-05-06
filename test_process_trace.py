import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from app.core.process_trace import ProcessTrace, TraceNode


def test_basic_trace():
    trace = ProcessTrace(storage_dir="test_traces")
    
    root_node = TraceNode(
        node_id="node-001",
        task_id="task-001",
        hypothesis="使用硬质合金刀具，v_c=120，预期切削力<800N",
        reason="基于材料特性选择初始参数",
        result={"cutting_speed": 120.0, "feed_rate": 0.2, "depth_of_cut": 2.0},
        validation_result={"passed": True, "cutting_force": 750.0},
        metrics={"cutting_force": 750.0, "surface_roughness": 1.6, "tool_life": 120.0},
        is_sota=False
    )
    
    trace.add_node(root_node, [])
    print("根节点已创建")
    
    branch_node_1 = TraceNode(
        node_id="node-002",
        task_id="task-001",
        parent_ids=["node-001"],
        hypothesis="优化切削速度到150，预期提高效率",
        reason="基于根节点结果尝试提高切削速度",
        result={"cutting_speed": 150.0, "feed_rate": 0.25, "depth_of_cut": 2.0},
        validation_result={"passed": True, "cutting_force": 780.0},
        metrics={"cutting_force": 780.0, "surface_roughness": 1.8, "tool_life": 100.0},
        is_sota=False
    )
    
    trace.add_node(branch_node_1, ["node-001"])
    print("分支节点1已创建")
    
    branch_node_2 = TraceNode(
        node_id="node-003",
        task_id="task-001",
        parent_ids=["node-001"],
        hypothesis="优化进给量到0.15，预期降低表面粗糙度",
        reason="基于根节点结果尝试降低进给量",
        result={"cutting_speed": 120.0, "feed_rate": 0.15, "depth_of_cut": 2.0},
        validation_result={"passed": True, "cutting_force": 700.0},
        metrics={"cutting_force": 700.0, "surface_roughness": 1.2, "tool_life": 140.0},
        is_sota=False
    )
    
    trace.add_node(branch_node_2, ["node-001"])
    print("分支节点2已创建")
    
    chain = trace.get_evolution_chain("node-002")
    print(f"演化链长度: {len(chain)}")
    assert len(chain) == 2, f"期望演化链长度为2，实际为{len(chain)}"
    
    branches = trace.get_branches("node-001")
    print(f"分支数量: {len(branches)}")
    assert len(branches) == 2, f"期望分支数量为2，实际为{len(branches)}"
    
    sota_node = trace.get_sota_node()
    print(f"SOTA节点: {sota_node.node_id if sota_node else 'None'}")
    
    mermaid_output = trace.to_mermaid()
    print("Mermaid输出:")
    print(mermaid_output)
    
    export_path = trace.export_json("test_traces/test_export.json")
    print(f"导出路径: {export_path}")
    
    new_trace = ProcessTrace(storage_dir="test_traces")
    new_trace.import_json("test_traces/test_export.json")
    print(f"导入后节点数: {len(new_trace.nodes)}")
    assert len(new_trace.nodes) == 3, f"期望导入3个节点，实际为{len(new_trace.nodes)}"
    
    print("所有测试通过!")


if __name__ == "__main__":
    test_basic_trace()
