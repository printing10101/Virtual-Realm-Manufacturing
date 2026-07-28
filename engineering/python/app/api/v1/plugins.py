from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.auth.permissions import require_permission
from app.capability.capability_gating import CapabilityGatekeeper
from app.plugins.plugin_system import (
    PluginStatus,
    get_dependency_resolver,
    get_plugin_manager,
)
from app.plugins.plugin_worker import PluginWorkerManager, WorkerConfig
from app.core.response import ErrorCode, error, success
from app.core.safe_errors import safe_error_message

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/plugins",
    tags=["plugins"],
    dependencies=[Depends(require_permission("plugin:read"))],
)


@router.get("/marketplace")
def list_marketplace_plugins(
    query: Optional[str] = Query(None, description="Search query"),
    plugin_type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1, le=500),
    page_size: int = Query(20, ge=1, le=100),
):
    return success(
        data={
            "plugins": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/marketplace/{plugin_id}/install", dependencies=[Depends(require_permission("plugin:config:update"))])
def install_marketplace_plugin(plugin_id: str):
    return success(data={"message": f"Plugin '{plugin_id}' installation started"})


@router.get("")
def list_installed_plugins(
    status: Optional[str] = Query(None, description="Filter by status"),
    plugin_type: Optional[str] = Query(None, description="Filter by type"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
):
    try:
        manager = get_plugin_manager()
        registry = manager._registry

        status_filter = PluginStatus(status) if status else None
        plugins = registry.list_plugins(
            status=status_filter,
            plugin_type=plugin_type,
            capability=capability,
        )

        return success(
            data={
                "plugins": [p.to_dict() for p in plugins],
                "total": len(plugins),
            }
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.list_installed", fallback="插件列表查询失败，请稍后重试")
        logger.error("[plugins.list_installed] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.get("/{plugin_id}")
def get_plugin_detail(plugin_id: str):
    try:
        manager = get_plugin_manager()
        info = manager.get_plugin_info(plugin_id)

        resolver = get_dependency_resolver()
        info["dependency_tree"] = resolver.get_dependency_tree(plugin_id)

        gatekeeper = CapabilityGatekeeper.get_instance()
        info["capabilities"] = gatekeeper.get_plugin_capabilities(plugin_id)

        worker_info = None
        try:
            worker_mgr = PluginWorkerManager.get_instance()
            worker_info = worker_mgr.get_worker_info(plugin_id)
        except (RuntimeError, AttributeError, KeyError) as e:
            # 工作进程管理器未初始化或插件无 worker 时，仅缺失 worker 信息
            logger.debug(
                f"Plugin worker info unavailable for {plugin_id}: {e}",
                exc_info=True,
            )

        info["worker"] = worker_info

        return success(data=info)
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.get_detail", fallback="插件详情查询失败，请稍后重试")
        logger.error("[plugins.get_detail] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.post("/{plugin_id}/enable", dependencies=[Depends(require_permission("plugin:config:update"))])
def enable_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager.enable_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' enabled"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.enable", fallback="插件启用失败，请稍后重试")
        logger.error("[plugins.enable] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.post("/{plugin_id}/disable", dependencies=[Depends(require_permission("plugin:config:update"))])
def disable_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager.disable_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' disabled"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.disable", fallback="插件禁用失败，请稍后重试")
        logger.error("[plugins.disable] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.post("/{plugin_id}/reload", dependencies=[Depends(require_permission("plugin:config:update"))])
def reload_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager._loader.reload_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' reloaded"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.reload", fallback="插件重载失败，请稍后重试")
        logger.error("[plugins.reload] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.delete("/{plugin_id}", dependencies=[Depends(require_permission("plugin:config:update"))])
def uninstall_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager.uninstall_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' uninstalled"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.uninstall", fallback="插件卸载失败，请稍后重试")
        logger.error("[plugins.uninstall] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.put("/{plugin_id}/config")
def update_plugin_config(
    plugin_id: str,
    config: Dict[str, Any],
    _perm: None = Depends(require_permission("plugin:config:update")),
):
    # 修复 [B22]：原端点无认证 + 弱验证，任意未登录调用方可修改任意插件配置。
    # 通过 Depends(require_permission("plugin:config:update")) 强制认证 + 权限校验，
    # 未登录调用方将得到 401，权限不足将得到 403。
    try:
        manager = get_plugin_manager()
        manager._registry.update_config(plugin_id, config)
        return success(data={"message": f"Plugin '{plugin_id}' config updated"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.update_config", fallback="插件配置更新失败，请稍后重试")
        logger.error("[plugins.update_config] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.get("/{plugin_id}/dependencies")
def get_plugin_dependencies(plugin_id: str):
    try:
        resolver = get_dependency_resolver()
        tree = resolver.get_dependency_tree(plugin_id)
        order = resolver.resolve_dependencies(plugin_id)

        return success(
            data={
                "tree": tree,
                "load_order": order,
            }
        )
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.get_dependencies", fallback="插件依赖查询失败，请稍后重试")
        logger.error("[plugins.get_dependencies] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.get("/{plugin_id}/logs")
def get_plugin_logs(
    plugin_id: str,
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
):
    return success(
        data={
            "logs": [],
            "total": 0,
        }
    )


@router.get("/{plugin_id}/capabilities")
def get_plugin_capabilities(plugin_id: str):
    try:
        gatekeeper = CapabilityGatekeeper.get_instance()
        caps = gatekeeper.get_plugin_capabilities(plugin_id)

        return success(
            data={
                "capabilities": caps,
            }
        )
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.get_capabilities", fallback="插件能力查询失败，请稍后重试")
        logger.error("[plugins.get_capabilities] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.put("/{plugin_id}/capabilities/{capability}")
def update_capability_grant(
    plugin_id: str,
    capability: str,
    file_rules: Optional[List[Dict]] = None,
    network_rules: Optional[List[Dict]] = None,
    gpu_limits: Optional[Dict] = None,
    _perm: None = Depends(require_permission("plugin:capability:manage")),
):
    # 修复 [B21]：原端点无认证，任意未登录调用方可修改插件能力授权规则。
    # 通过 Depends(require_permission("plugin:capability:manage")) 强制认证 + 权限校验，
    # 未登录调用方将得到 401，权限不足将得到 403。
    try:
        gatekeeper = CapabilityGatekeeper.get_instance()
        gatekeeper.update_grant_rules(
            plugin_id,
            capability,
            file_rules=file_rules,
            network_rules=network_rules,
            gpu_limits=gpu_limits,
        )
        return success(data={"message": f"Capability '{capability}' rules updated"})
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.update_capability", fallback="插件能力规则更新失败，请稍后重试")
        logger.error("[plugins.update_capability] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.get("/workers")
def list_workers():
    try:
        worker_mgr = PluginWorkerManager.get_instance()
        workers = worker_mgr.list_workers()
        return success(data={"workers": workers})
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.list_workers", fallback="工作进程列表查询失败，请稍后重试")
        logger.error("[plugins.list_workers] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.post("/workers/{plugin_id}/start", dependencies=[Depends(require_permission("plugin:config:update"))])
def start_worker(plugin_id: str):
    try:
        manager = get_plugin_manager()
        metadata = manager._registry.get(plugin_id)

        worker_mgr = PluginWorkerManager.get_instance()
        config = WorkerConfig(
            plugin_id=plugin_id,
            plugin_path=metadata.plugin_path,
        )
        worker_mgr.start_worker(config)

        return success(data={"message": f"Worker for '{plugin_id}' started"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.start_worker", fallback="工作进程启动失败，请稍后重试")
        logger.error("[plugins.start_worker] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.post("/workers/{plugin_id}/stop", dependencies=[Depends(require_permission("plugin:config:update"))])
def stop_worker(plugin_id: str):
    try:
        worker_mgr = PluginWorkerManager.get_instance()
        worker_mgr.stop_worker(plugin_id)
        return success(data={"message": f"Worker for '{plugin_id}' stopped"})
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.stop_worker", fallback="工作进程停止失败，请稍后重试")
        logger.error("[plugins.stop_worker] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})


@router.get("/health")
def health_check(plugin_id: Optional[str] = None):
    try:
        worker_mgr = PluginWorkerManager.get_instance()
        results = worker_mgr.health_check(plugin_id)
        return success(data={"health": results})
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as e:
        # 兜底捕获：API 端点统一收口所有未预期的异常
        # 插件操作涉及注册表/沙箱/工作进程，异常族多源
        # 使用安全错误消息，避免泄露内部异常详情
        safe = safe_error_message(e, context="plugins.health_check", fallback="健康检查失败，请稍后重试")
        logger.error("[plugins.health_check] error_id=%s: %s", safe["error_id"], e, exc_info=True)
        return error(code=ErrorCode.INTERNAL_ERROR, message=safe["message"], detail={"error_id": safe["error_id"]})
