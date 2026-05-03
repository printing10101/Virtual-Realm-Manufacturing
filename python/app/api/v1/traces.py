from fastapi import APIRouter, HTTPException
from dataclasses import asdict
from typing import List, Dict, Any

from app.core.response import success, error, ErrorCode
from app.core.container import container

router = APIRouter(prefix="/api/v1/traces", tags=["Process Trace"])


@router.get("/{task_id}")
async def get_task_traces(task_id: str):
    process_service = container.get_service("process_service")
    
    task_manager = container.get_service("task_manager")
    task = task_manager.get_task(task_id)
    if not task:
        return error(code=ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")
    
    traces = process_service.trace.get_task_traces(task_id)
    
    trace_list = []
    for node in traces:
        node_data = asdict(node)
        node_data["children"] = process_service.trace.dag_children.get(node.node_id, [])
        trace_list.append(node_data)
    
    return success(data={
        "task_id": task_id,
        "traces": trace_list,
        "total_nodes": len(trace_list)
    })


@router.get("/{task_id}/chain")
async def get_evolution_chain(task_id: str, node_id: str = None):
    process_service = container.get_service("process_service")
    
    traces = process_service.trace.get_task_traces(task_id)
    if not traces:
        return error(code=ErrorCode.NOT_FOUND, message=f"No traces found for task {task_id}")
    
    if node_id:
        target_node = process_service.trace.get_node(node_id)
        if not target_node:
            return error(code=ErrorCode.NOT_FOUND, message=f"Node {node_id} not found")
    else:
        target_node = process_service.trace.get_sota_node()
        if not target_node:
            target_node = traces[-1]
    
    chain = process_service.trace.get_evolution_chain(target_node.node_id)
    
    chain_data = []
    for node in chain:
        node_data = asdict(node)
        node_data["children"] = process_service.trace.dag_children.get(node.node_id, [])
        chain_data.append(node_data)
    
    return success(data={
        "task_id": task_id,
        "chain": chain_data,
        "chain_length": len(chain_data)
    })


@router.get("/{task_id}/mermaid")
async def get_mermaid_dag(task_id: str):
    process_service = container.get_service("process_service")
    
    traces = process_service.trace.get_task_traces(task_id)
    if not traces:
        return error(code=ErrorCode.NOT_FOUND, message=f"No traces found for task {task_id}")
    
    mermaid_output = process_service.trace.to_mermaid()
    
    return success(data={
        "task_id": task_id,
        "mermaid": mermaid_output
    })


@router.get("/{task_id}/sota")
async def get_sota_metrics(task_id: str):
    process_service = container.get_service("process_service")
    
    sota_node = process_service.trace.get_sota_node()
    sota_metrics = process_service.trace.sota_metrics
    
    return success(data={
        "task_id": task_id,
        "sota_node": asdict(sota_node) if sota_node else None,
        "sota_metrics": sota_metrics
    })


@router.get("/{task_id}/branches")
async def get_branches(task_id: str, node_id: str = None):
    process_service = container.get_service("process_service")
    
    traces = process_service.trace.get_task_traces(task_id)
    if not traces:
        return error(code=ErrorCode.NOT_FOUND, message=f"No traces found for task {task_id}")
    
    if node_id:
        target_node = process_service.trace.get_node(node_id)
        if not target_node:
            return error(code=ErrorCode.NOT_FOUND, message=f"Node {node_id} not found")
    else:
        root_nodes = [n for n in traces if not n.parent_ids]
        if not root_nodes:
            return error(code=ErrorCode.NOT_FOUND, message=f"No root nodes found for task {task_id}")
        target_node = root_nodes[0]
    
    branches = process_service.trace.get_branches(target_node.node_id)
    
    branches_data = []
    for branch in branches:
        branch_data = [asdict(node) for node in branch]
        branches_data.append(branch_data)
    
    return success(data={
        "task_id": task_id,
        "root_node_id": target_node.node_id,
        "branches": branches_data,
        "branch_count": len(branches_data)
    })
