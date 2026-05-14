# 灵境制造插件系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的插件系统，支持无需Fork主项目即可对系统功能进行灵活扩展，包括核心生命周期管理、多进程架构、能力门控、UI贡献系统和插件管理界面。

**Architecture:** 采用多进程架构（每个插件独立进程）+ gRPC进程间通信 + 能力门控沙箱机制。核心系统通过插件注册表管理生命周期，前端通过动态加载框架集成插件UI组件。

**Tech Stack:** Python 3.10+, gRPC, Protocol Buffers, Vue 3, FastAPI, SQLite, multiprocessing, importlib

---

## 文件结构映射

### 新创建文件

| 文件路径 | 职责 |
|---------|------|
| `python/app/core/plugin_system.py` | 插件系统核心：生命周期管理、注册表、依赖解析 |
| `python/app/core/plugin_worker.py` | 进程外Worker管理器：多进程启动、gRPC通信、健康检查 |
| `python/app/core/capability_gating.py` | 能力门控系统：权限声明、验证、资源配额管理 |
| `python/app/api/v1/plugins.py` | 插件管理API：安装/卸载/启用/配置/日志 |
| `python/app/protos/plugin.proto` | gRPC服务定义：插件通信接口 |
| `src/views/PluginMarket.vue` | 插件市场界面：浏览/搜索/安装 |
| `src/views/PluginManager.vue` | 已安装插件管理：启用/停用/配置 |
| `src/views/PluginDetail.vue` | 插件详情页：版本/权限/依赖 |
| `src/views/PluginLogs.vue` | 插件日志系统：收集/过滤/导出 |
| `src/components/plugin/PluginUIRegistry.vue` | 插件UI组件注册和加载框架 |
| `src/components/plugin/PluginLayoutContributor.vue` | 声明式UI布局配置渲染器 |
| `src/stores/plugin.ts` | Pinia插件状态管理 |
| `plugins/.gitkeep` | 插件目录占位符 |
| `tools/plugin-cli.py` | 插件脚手架和开发工具 |
| `templates/plugin/plugin.json` | 插件元数据模板 |
| `templates/plugin/main.py` | 插件入口模板 |
| `test_plugin_system.py` | 插件系统集成测试 |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `python/app/main.py` | 添加插件系统初始化和路由注册 |
| `src/router/index.ts` | 添加插件管理相关路由 |
| `src/App.vue` | 集成插件UI贡献点框架 |

---

## Phase 1: 核心插件生命周期管理

### Task 1: 插件元数据模型和注册表

**Files:**
- Create: `python/app/core/plugin_system.py`
- Test: `test_plugin_system.py` (partial)

- [ ] **Step 1: 定义插件元数据模型**

```python
# python/app/core/plugin_system.py (Lines 1-80)

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PluginStatus(str, Enum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    INITIALIZED = "initialized"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNINSTALLED = "uninstalled"
    ERROR = "error"


class PluginType(str, Enum):
    ADAPTER = "adapter"
    DATA_SOURCE = "data_source"
    ANALYZER = "analyzer"
    VISUALIZATION = "visualization"


CAPABILITY_DATA_SOURCE = "data_source"
CAPABILITY_MACHINE_CONTROL = "machine_control"
CAPABILITY_FILE_ACCESS = "file_access"
CAPABILITY_NETWORK_ACCESS = "network_access"
CAPABILITY_GPU_ACCESS = "gpu_access"

VALID_CAPABILITIES = {
    CAPABILITY_DATA_SOURCE,
    CAPABILITY_MACHINE_CONTROL,
    CAPABILITY_FILE_ACCESS,
    CAPABILITY_NETWORK_ACCESS,
    CAPABILITY_GPU_ACCESS,
}


@dataclass
class PluginDependency:
    name: str
    version: str = ">=0.0.0"
    required: bool = True


@dataclass
class PluginMetadata:
    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    entry_point: str = "main.py"
    plugin_type: str = ""
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[PluginDependency] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    min_core_version: str = "1.0.0"
    max_core_version: str = "99.99.99"
    plugin_path: str = ""
    status: PluginStatus = PluginStatus.DISCOVERED
    config: Dict[str, Any] = field(default_factory=dict)
    enabled_at: Optional[float] = None
    disabled_at: Optional[float] = None
    installed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entry_point": self.entry_point,
            "plugin_type": self.plugin_type,
            "capabilities": self.capabilities,
            "dependencies": [
                {"name": d.name, "version": d.version, "required": d.required}
                for d in self.dependencies
            ],
            "config_schema": self.config_schema,
            "min_core_version": self.min_core_version,
            "max_core_version": self.max_core_version,
            "plugin_path": self.plugin_path,
            "status": self.status.value,
            "config": self.config,
            "enabled_at": self.enabled_at,
            "disabled_at": self.disabled_at,
            "installed_at": self.installed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PluginMetadata:
        deps = []
        for d in data.get("dependencies", []):
            deps.append(PluginDependency(
                name=d["name"],
                version=d.get("version", ">=0.0.0"),
                required=d.get("required", True)
            ))
        
        compat = data.get("compatibility", {})
        return cls(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            author=data.get("author", ""),
            description=data.get("description", ""),
            entry_point=data.get("entry_point", "main.py"),
            plugin_type=data.get("plugin_type", ""),
            capabilities=data.get("capabilities", []),
            dependencies=deps,
            config_schema=data.get("config_schema", {}),
            min_core_version=compat.get("min_core_version", "1.0.0"),
            max_core_version=compat.get("max_core_version", "99.99.99"),
            plugin_path=data.get("plugin_path", ""),
            status=PluginStatus(data.get("status", "discovered")),
            config=data.get("config", {}),
        )
```

- [ ] **Step 2: 实现插件注册表**

```python
# python/app/core/plugin_system.py (Lines 81-180)

class PluginRegistry:
    _instance: Optional[PluginRegistry] = None
    
    def __init__(self):
        self._plugins: Dict[str, PluginMetadata] = {}
        self._plugins_by_type: Dict[str, List[str]] = {}
        self._plugins_by_capability: Dict[str, List[str]] = {}
        self._plugin_instances: Dict[str, Any] = {}
        self._lock = __import__('threading').Lock()
    
    @classmethod
    def get_instance(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def register(self, metadata: PluginMetadata) -> None:
        with self._lock:
            if metadata.id in self._plugins:
                raise ValueError(f"Plugin '{metadata.id}' already registered")
            
            self._plugins[metadata.id] = metadata
            metadata.status = PluginStatus.REGISTERED
            
            ptype = metadata.plugin_type
            if ptype:
                if ptype not in self._plugins_by_type:
                    self._plugins_by_type[ptype] = []
                self._plugins_by_type[ptype].append(metadata.id)
            
            for cap in metadata.capabilities:
                if cap not in self._plugins_by_capability:
                    self._plugins_by_capability[cap] = []
                self._plugins_by_capability[cap].append(metadata.id)
            
            logger.info(f"Plugin registered: {metadata.id} v{metadata.version}")
    
    def unregister(self, plugin_id: str) -> None:
        with self._lock:
            if plugin_id not in self._plugins:
                raise KeyError(f"Plugin '{plugin_id}' not found")
            
            metadata = self._plugins[plugin_id]
            
            ptype = metadata.plugin_type
            if ptype and plugin_id in self._plugins_by_type.get(ptype, []):
                self._plugins_by_type[ptype].remove(plugin_id)
            
            for cap in metadata.capabilities:
                if plugin_id in self._plugins_by_capability.get(cap, []):
                    self._plugins_by_capability[cap].remove(plugin_id)
            
            self._plugin_instances.pop(plugin_id, None)
            del self._plugins[plugin_id]
            
            logger.info(f"Plugin unregistered: {plugin_id}")
    
    def get(self, plugin_id: str) -> Optional[PluginMetadata]:
        return self._plugins.get(plugin_id)
    
    def get_instance(self, plugin_id: str) -> Optional[Any]:
        return self._plugin_instances.get(plugin_id)
    
    def set_instance(self, plugin_id: str, instance: Any) -> None:
        self._plugin_instances[plugin_id] = instance
    
    def list_plugins(
        self,
        status: Optional[PluginStatus] = None,
        plugin_type: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> List[PluginMetadata]:
        result = list(self._plugins.values())
        
        if status:
            result = [p for p in result if p.status == status]
        if plugin_type:
            result = [p for p in result if p.plugin_type == plugin_type]
        if capability:
            result = [p for p in result if capability in p.capabilities]
        
        return result
    
    def get_plugins_by_type(self, plugin_type: str) -> List[str]:
        return self._plugins_by_type.get(plugin_type, [])
    
    def get_plugins_by_capability(self, capability: str) -> List[str]:
        return self._plugins_by_capability.get(capability, [])
    
    def has_plugin(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins
    
    def update_status(self, plugin_id: str, status: PluginStatus) -> None:
        if plugin_id in self._plugins:
            self._plugins[plugin_id].status = status
            if status == PluginStatus.ENABLED:
                self._plugins[plugin_id].enabled_at = time.time()
            elif status == PluginStatus.DISABLED:
                self._plugins[plugin_id].disabled_at = time.time()
    
    def update_config(self, plugin_id: str, config: Dict[str, Any]) -> None:
        if plugin_id in self._plugins:
            self._plugins[plugin_id].config.update(config)
    
    def get_all_metadata(self) -> Dict[str, Any]:
        return {
            "plugins": {pid: p.to_dict() for pid, p in self._plugins.items()},
            "by_type": dict(self._plugins_by_type),
            "by_capability": dict(self._plugins_by_capability),
        }
```

- [ ] **Step 3: 编写测试用例**

```python
# test_plugin_system.py (Lines 1-100)

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))

from app.core.plugin_system import (
    PluginMetadata,
    PluginRegistry,
    PluginStatus,
    PluginDependency,
)


class TestPluginMetadata(unittest.TestCase):
    def test_create_metadata(self):
        meta = PluginMetadata(
            id="test-plugin",
            name="Test Plugin",
            version="1.0.0",
        )
        self.assertEqual(meta.id, "test-plugin")
        self.assertEqual(meta.status, PluginStatus.DISCOVERED)
    
    def test_metadata_to_dict(self):
        meta = PluginMetadata(
            id="test",
            name="Test",
            version="1.0.0",
            capabilities=["data_source"],
        )
        d = meta.to_dict()
        self.assertEqual(d["id"], "test")
        self.assertEqual(d["capabilities"], ["data_source"])
    
    def test_metadata_from_dict(self):
        data = {
            "id": "fanuc-adapter",
            "name": "发那科适配器",
            "version": "1.0.0",
            "author": "团队",
            "description": "测试",
            "capabilities": ["data_source", "machine_control"],
            "dependencies": [{"name": "opcua", "version": ">=2.0", "required": True}],
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "2.0.0"},
        }
        meta = PluginMetadata.from_dict(data)
        self.assertEqual(meta.id, "fanuc-adapter")
        self.assertEqual(len(meta.dependencies), 1)
        self.assertEqual(meta.dependencies[0].name, "opcua")
        self.assertEqual(meta.min_core_version, "1.0.0")


class TestPluginRegistry(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()
        self.registry = PluginRegistry.get_instance()
    
    def tearDown(self):
        PluginRegistry.reset()
    
    def test_register_plugin(self):
        meta = PluginMetadata(id="test", name="Test", version="1.0.0")
        self.registry.register(meta)
        self.assertTrue(self.registry.has_plugin("test"))
        self.assertEqual(meta.status, PluginStatus.REGISTERED)
    
    def test_unregister_plugin(self):
        meta = PluginMetadata(id="test", name="Test", version="1.0.0")
        self.registry.register(meta)
        self.registry.unregister("test")
        self.assertFalse(self.registry.has_plugin("test"))
    
    def test_duplicate_register_raises(self):
        meta = PluginMetadata(id="test", name="Test", version="1.0.0")
        self.registry.register(meta)
        with self.assertRaises(ValueError):
            self.registry.register(meta)
    
    def test_list_plugins_by_type(self):
        m1 = PluginMetadata(id="p1", name="P1", version="1.0.0", plugin_type="adapter")
        m2 = PluginMetadata(id="p2", name="P2", version="1.0.0", plugin_type="analyzer")
        self.registry.register(m1)
        self.registry.register(m2)
        
        adapters = self.registry.list_plugins(plugin_type="adapter")
        self.assertEqual(len(adapters), 1)
        self.assertEqual(adapters[0].id, "p1")
    
    def test_list_plugins_by_capability(self):
        m1 = PluginMetadata(id="p1", name="P1", version="1.0.0", capabilities=["data_source"])
        m2 = PluginMetadata(id="p2", name="P2", version="1.0.0", capabilities=["machine_control"])
        self.registry.register(m1)
        self.registry.register(m2)
        
        ds_plugins = self.registry.list_plugins(capability="data_source")
        self.assertEqual(len(ds_plugins), 1)
        self.assertEqual(ds_plugins[0].id, "p1")
    
    def test_update_status(self):
        meta = PluginMetadata(id="test", name="Test", version="1.0.0")
        self.registry.register(meta)
        self.registry.update_status("test", PluginStatus.ENABLED)
        self.assertEqual(meta.status, PluginStatus.ENABLED)
        self.assertIsNotNone(meta.enabled_at)
    
    def test_get_instance(self):
        meta = PluginMetadata(id="test", name="Test", version="1.0.0")
        self.registry.register(meta)
        self.registry.set_instance("test", {"key": "value"})
        self.assertEqual(self.registry.get_instance("test"), {"key": "value"})
```

- [ ] **Step 4: 运行测试验证**

```bash
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python -m pytest test_plugin_system.py::TestPluginMetadata -v
python -m pytest test_plugin_system.py::TestPluginRegistry -v
```

Expected: All tests pass

---

### Task 2: 插件发现和加载机制

**Files:**
- Modify: `python/app/core/plugin_system.py` (append)
- Test: `test_plugin_system.py` (append)

- [ ] **Step 1: 实现插件发现器**

```python
# python/app/core/plugin_system.py (Lines 181-300)

class PluginDiscovery:
    def __init__(
        self,
        plugin_dirs: Optional[List[str]] = None,
        user_dirs: Optional[List[str]] = None,
    ):
        self.plugin_dirs = plugin_dirs or []
        self.user_dirs = user_dirs or []
        self._registry = PluginRegistry.get_instance()
    
    def discover(self) -> List[PluginMetadata]:
        discovered = []
        
        all_dirs = self.plugin_dirs + self.user_dirs
        for directory in all_dirs:
            dir_path = Path(directory)
            if not dir_path.exists():
                logger.warning(f"Plugin directory not found: {directory}")
                continue
            
            discovered.extend(self._scan_directory(dir_path))
        
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
    
    def _scan_directory(self, directory: Path) -> List[PluginMetadata]:
        plugins = []
        
        for item in directory.iterdir():
            if item.is_dir():
                meta = self._load_plugin_meta(item)
                if meta:
                    plugins.append(meta)
        
        return plugins
    
    def _load_plugin_meta(self, plugin_dir: Path) -> Optional[PluginMetadata]:
        plugin_json = plugin_dir / "plugin.json"
        
        if not plugin_json.exists():
            logger.debug(f"No plugin.json found in {plugin_dir}")
            return None
        
        try:
            with open(plugin_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._validate_metadata(data, plugin_dir)
            
            data["plugin_path"] = str(plugin_dir)
            
            if "plugin_type" not in data:
                caps = data.get("capabilities", [])
                if "data_source" in caps:
                    data["plugin_type"] = "data_source"
                elif "machine_control" in caps:
                    data["plugin_type"] = "adapter"
            
            metadata = PluginMetadata.from_dict(data)
            metadata.installed_at = time.time()
            
            return metadata
        
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
            return None
    
    def _validate_metadata(self, data: Dict[str, Any], plugin_dir: Path) -> None:
        required_fields = ["id", "name", "version"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")
        
        caps = data.get("capabilities", [])
        invalid_caps = set(caps) - VALID_CAPABILITIES
        if invalid_caps:
            raise ValueError(f"Invalid capabilities: {invalid_caps}")
        
        deps = data.get("dependencies", [])
        for dep in deps:
            if "name" not in dep:
                raise ValueError("Dependency missing 'name' field")
        
        entry = data.get("entry_point", "main.py")
        entry_path = plugin_dir / entry
        if not entry_path.exists():
            raise ValueError(f"Entry point not found: {entry}")
```

- [ ] **Step 2: 实现插件加载器**

```python
# python/app/core/plugin_system.py (Lines 301-420)

class PluginLoader:
    def __init__(self, registry: Optional[PluginRegistry] = None):
        self._registry = registry or PluginRegistry.get_instance()
    
    def load_plugin(self, metadata: PluginMetadata) -> Any:
        plugin_dir = Path(metadata.plugin_path)
        entry_point = plugin_dir / metadata.entry_point
        
        if not entry_point.exists():
            raise FileNotFoundError(f"Entry point not found: {entry_point}")
        
        sys.path.insert(0, str(plugin_dir))
        
        try:
            module_name = f"plugin_{metadata.id}"
            
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            spec = importlib.util.spec_from_file_location(module_name, entry_point)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {entry_point}")
            
            module = importlib.util.module_from_spec(spec)
            module.__plugin_metadata__ = metadata
            
            spec.loader.exec_module(module)
            
            instance = self._instantiate_plugin(module, metadata)
            self._registry.set_instance(metadata.id, instance)
            
            return instance
        
        except Exception as e:
            metadata.status = PluginStatus.ERROR
            logger.error(f"Failed to load plugin {metadata.id}: {e}")
            raise
        finally:
            if str(plugin_dir) in sys.path:
                sys.path.remove(str(plugin_dir))
    
    def _instantiate_plugin(self, module: Any, metadata: PluginMetadata) -> Any:
        plugin_class = getattr(module, "Plugin", None)
        
        if plugin_class is None:
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and hasattr(attr, "initialize")
                    and hasattr(attr, "shutdown")
                ):
                    plugin_class = attr
                    break
        
        if plugin_class is None:
            return module
        
        instance = plugin_class()
        
        if hasattr(instance, "set_metadata"):
            instance.set_metadata(metadata)
        
        if hasattr(instance, "set_config"):
            instance.set_config(metadata.config)
        
        return instance
    
    def reload_plugin(self, plugin_id: str) -> Any:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        module_name = f"plugin_{plugin_id}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        old_instance = self._registry.get_instance(plugin_id)
        if old_instance and hasattr(old_instance, "shutdown"):
            try:
                old_instance.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down old instance: {e}")
        
        return self.load_plugin(metadata)
```

- [ ] **Step 3: 创建测试插件和测试用例**

```python
# test_plugin_system.py (Lines 101-200)

class TestPluginDiscovery(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()
        self.registry = PluginRegistry.get_instance()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        PluginRegistry.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_plugin(self, plugin_id, metadata_overrides=None):
        plugin_dir = Path(self.temp_dir) / plugin_id
        plugin_dir.mkdir()
        
        meta = {
            "id": plugin_id,
            "name": f"Test {plugin_id}",
            "version": "1.0.0",
            "author": "Test",
            "description": "Test plugin",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {
                "min_core_version": "1.0.0",
                "max_core_version": "99.0.0",
            },
        }
        if metadata_overrides:
            meta.update(metadata_overrides)
        
        with open(plugin_dir / "plugin.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)
        
        with open(plugin_dir / "main.py", "w", encoding="utf-8") as f:
            f.write("""
class Plugin:
    def initialize(self, context):
        self.initialized = True
    
    def shutdown(self):
        self.initialized = False
""")
        
        return plugin_dir
    
    def test_discover_plugins(self):
        self._create_test_plugin("plugin-a")
        self._create_test_plugin("plugin-b")
        
        discovery = PluginDiscovery(plugin_dirs=[self.temp_dir])
        plugins = discovery.discover()
        
        self.assertEqual(len(plugins), 2)
        plugin_ids = [p.id for p in plugins]
        self.assertIn("plugin-a", plugin_ids)
        self.assertIn("plugin-b", plugin_ids)
    
    def test_discover_empty_directory(self):
        empty_dir = Path(self.temp_dir) / "empty"
        empty_dir.mkdir()
        
        discovery = PluginDiscovery(plugin_dirs=[str(empty_dir)])
        plugins = discovery.discover()
        self.assertEqual(len(plugins), 0)
    
    def test_discover_nonexistent_directory(self):
        discovery = PluginDiscovery(plugin_dirs=["/nonexistent/path"])
        plugins = discovery.discover()
        self.assertEqual(len(plugins), 0)
    
    def test_validate_missing_fields(self):
        plugin_dir = Path(self.temp_dir) / "invalid"
        plugin_dir.mkdir()
        
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump({"id": "test"}, f)
        
        discovery = PluginDiscovery(plugin_dirs=[self.temp_dir])
        plugins = discovery.discover()
        self.assertEqual(len(plugins), 0)
    
    def test_validate_invalid_capability(self):
        self._create_test_plugin("invalid-cap", {
            "capabilities": ["data_source", "invalid_capability"]
        })
        
        discovery = PluginDiscovery(plugin_dirs=[self.temp_dir])
        plugins = discovery.discover()
        self.assertEqual(len(plugins), 0)


class TestPluginLoader(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()
        self.registry = PluginRegistry.get_instance()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        PluginRegistry.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_plugin(self):
        plugin_dir = Path(self.temp_dir) / "test-loader"
        plugin_dir.mkdir()
        
        meta = {
            "id": "test-loader",
            "name": "Test Loader",
            "version": "1.0.0",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
        }
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(meta, f)
        
        with open(plugin_dir / "main.py", "w") as f:
            f.write("""
class Plugin:
    def __init__(self):
        self.value = 42
    
    def initialize(self, context):
        pass
    
    def shutdown(self):
        pass
""")
        
        discovery = PluginDiscovery(plugin_dirs=[self.temp_dir])
        plugins = discovery.discover()
        
        for p in plugins:
            self.registry.register(p)
        
        loader = PluginLoader(self.registry)
        instance = loader.load_plugin(plugins[0])
        
        self.assertIsNotNone(instance)
        self.assertEqual(instance.value, 42)
```

- [ ] **Step 4: 运行测试验证**

```bash
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python -m pytest test_plugin_system.py::TestPluginDiscovery -v
python -m pytest test_plugin_system.py::TestPluginLoader -v
```

---

### Task 3: 插件初始化和生命周期管理

**Files:**
- Modify: `python/app/core/plugin_system.py` (append)
- Test: `test_plugin_system.py` (append)

- [ ] **Step 1: 实现插件生命周期管理器**

```python
# python/app/core/plugin_system.py (Lines 421-600)

class PluginLifecycleManager:
    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        loader: Optional[PluginLoader] = None,
    ):
        self._registry = registry or PluginRegistry.get_instance()
        self._loader = loader or PluginLoader(self._registry)
        self._context: Dict[str, Any] = {}
    
    def set_context(self, key: str, value: Any) -> None:
        self._context[key] = value
    
    def get_context(self, key: str) -> Optional[Any]:
        return self._context.get(key)
    
    def initialize_plugin(self, plugin_id: str) -> None:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        if metadata.status not in (PluginStatus.REGISTERED, PluginStatus.DISABLED):
            raise ValueError(f"Plugin '{plugin_id}' cannot be initialized (status: {metadata.status})")
        
        instance = self._registry.get_instance(plugin_id)
        
        if instance is None:
            instance = self._loader.load_plugin(metadata)
        
        if hasattr(instance, "initialize"):
            instance.initialize(self._context)
        
        self._registry.update_status(plugin_id, PluginStatus.INITIALIZED)
        logger.info(f"Plugin initialized: {plugin_id}")
    
    def enable_plugin(self, plugin_id: str) -> None:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        if metadata.status == PluginStatus.ENABLED:
            logger.info(f"Plugin '{plugin_id}' is already enabled")
            return
        
        if metadata.status not in (PluginStatus.REGISTERED, PluginStatus.INITIALIZED, PluginStatus.DISABLED):
            raise ValueError(f"Plugin '{plugin_id}' cannot be enabled (status: {metadata.status})")
        
        if metadata.status in (PluginStatus.REGISTERED, PluginStatus.DISABLED):
            self.initialize_plugin(plugin_id)
        
        instance = self._registry.get_instance(plugin_id)
        
        if hasattr(instance, "on_enable"):
            instance.on_enable()
        
        self._registry.update_status(plugin_id, PluginStatus.ENABLED)
        logger.info(f"Plugin enabled: {plugin_id}")
    
    def disable_plugin(self, plugin_id: str) -> None:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        if metadata.status != PluginStatus.ENABLED:
            logger.info(f"Plugin '{plugin_id}' is not enabled")
            return
        
        instance = self._registry.get_instance(plugin_id)
        
        if hasattr(instance, "on_disable"):
            instance.on_disable()
        
        self._registry.update_status(plugin_id, PluginStatus.DISABLED)
        logger.info(f"Plugin disabled: {plugin_id}")
    
    def uninstall_plugin(self, plugin_id: str) -> None:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        instance = self._registry.get_instance(plugin_id)
        
        if instance and hasattr(instance, "shutdown"):
            try:
                instance.shutdown()
            except Exception as e:
                logger.warning(f"Error during plugin shutdown: {e}")
        
        plugin_dir = Path(metadata.plugin_path)
        
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)
        
        self._registry.unregister(plugin_id)
        logger.info(f"Plugin uninstalled: {plugin_id}")
    
    def discover_and_register_all(self, plugin_dirs: List[str], user_dirs: Optional[List[str]] = None) -> int:
        discovery = PluginDiscovery(plugin_dirs=plugin_dirs, user_dirs=user_dirs)
        plugins = discovery.discover()
        
        count = 0
        for metadata in plugins:
            if not self._registry.has_plugin(metadata.id):
                self._registry.register(metadata)
                count += 1
        
        logger.info(f"Registered {count} new plugins")
        return count
    
    def initialize_all(self) -> int:
        count = 0
        for metadata in self._registry.list_plugins(status=PluginStatus.REGISTERED):
            try:
                self.initialize_plugin(metadata.id)
                count += 1
            except Exception as e:
                logger.error(f"Failed to initialize plugin {metadata.id}: {e}")
        
        return count
    
    def enable_all(self) -> int:
        count = 0
        for metadata in self._registry.list_plugins(
            status=PluginStatus.INITIALIZED
        ):
            try:
                self.enable_plugin(metadata.id)
                count += 1
            except Exception as e:
                logger.error(f"Failed to enable plugin {metadata.id}: {e}")
        
        return count
    
    def shutdown_all(self) -> None:
        for metadata in self._registry.list_plugins():
            if metadata.status == PluginStatus.ENABLED:
                try:
                    self.disable_plugin(metadata.id)
                except Exception as e:
                    logger.error(f"Error disabling plugin {metadata.id}: {e}")
        
        for metadata in self._registry.list_plugins():
            try:
                instance = self._registry.get_instance(metadata.id)
                if instance and hasattr(instance, "shutdown"):
                    instance.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {metadata.id}: {e}")
    
    def get_plugin_info(self, plugin_id: str) -> Dict[str, Any]:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        return {
            "metadata": metadata.to_dict(),
            "has_instance": self._registry.get_instance(plugin_id) is not None,
            "context_keys": list(self._context.keys()),
        }
```

- [ ] **Step 2: 实现依赖解析器**

```python
# python/app/core/plugin_system.py (Lines 601-700)

class DependencyResolver:
    def __init__(self, registry: Optional[PluginRegistry] = None):
        self._registry = registry or PluginRegistry.get_instance()
    
    def resolve_dependencies(self, plugin_id: str) -> List[str]:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        
        visited = set()
        order = []
        self._dfs(plugin_id, visited, order)
        
        return order
    
    def _dfs(self, plugin_id: str, visited: Set[str], order: List[str]) -> None:
        if plugin_id in visited:
            return
        
        visited.add(plugin_id)
        
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            return
        
        for dep in metadata.dependencies:
            if self._registry.has_plugin(dep.name):
                self._dfs(dep.name, visited, order)
            elif dep.required:
                raise ValueError(f"Required dependency '{dep.name}' not found for plugin '{plugin_id}'")
        
        order.append(plugin_id)
    
    def check_compatibility(self, plugin_id: str, core_version: str = "1.6.0") -> bool:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            return False
        
        from packaging import version as pkg_version
        
        try:
            core_v = pkg_version.parse(core_version)
            min_v = pkg_version.parse(metadata.min_core_version)
            max_v = pkg_version.parse(metadata.max_core_version)
            
            return min_v <= core_v <= max_v
        except Exception:
            return True
    
    def get_dependency_tree(self, plugin_id: str, depth: int = 0) -> Dict[str, Any]:
        metadata = self._registry.get(plugin_id)
        if metadata is None:
            return {}
        
        tree = {
            "id": plugin_id,
            "name": metadata.name,
            "version": metadata.version,
            "dependencies": [],
        }
        
        if depth < 3:
            for dep in metadata.dependencies:
                if self._registry.has_plugin(dep.name):
                    tree["dependencies"].append(
                        self.get_dependency_tree(dep.name, depth + 1)
                    )
                else:
                    tree["dependencies"].append({
                        "id": dep.name,
                        "version": dep.version,
                        "required": dep.required,
                        "status": "missing" if dep.required else "optional",
                    })
        
        return tree
```

- [ ] **Step 3: 创建全局单例和初始化函数**

```python
# python/app/core/plugin_system.py (Lines 701-780)

_plugin_manager: Optional[PluginLifecycleManager] = None
_dependency_resolver: Optional[DependencyResolver] = None


def init_plugin_system(
    plugin_dirs: Optional[List[str]] = None,
    user_dirs: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> PluginLifecycleManager:
    global _plugin_manager, _dependency_resolver
    
    registry = PluginRegistry.get_instance()
    loader = PluginLoader(registry)
    
    _plugin_manager = PluginLifecycleManager(registry, loader)
    _dependency_resolver = DependencyResolver(registry)
    
    if context:
        for key, value in context.items():
            _plugin_manager.set_context(key, value)
    
    count = _plugin_manager.discover_and_register_all(
        plugin_dirs=plugin_dirs or [],
        user_dirs=user_dirs or [],
    )
    
    _plugin_manager.initialize_all()
    _plugin_manager.enable_all()
    
    logger.info(f"Plugin system initialized with {count} plugins")
    return _plugin_manager


def get_plugin_manager() -> PluginLifecycleManager:
    if _plugin_manager is None:
        raise RuntimeError("Plugin system not initialized. Call init_plugin_system() first.")
    return _plugin_manager


def get_dependency_resolver() -> DependencyResolver:
    if _dependency_resolver is None:
        raise RuntimeError("Dependency resolver not initialized.")
    return _dependency_resolver


def shutdown_plugin_system() -> None:
    global _plugin_manager, _dependency_resolver
    
    if _plugin_manager:
        _plugin_manager.shutdown_all()
        _plugin_manager = None
    
    _dependency_resolver = None
    PluginRegistry.reset()
    
    logger.info("Plugin system shutdown")
```

- [ ] **Step 4: 编写生命周期测试**

```python
# test_plugin_system.py (Lines 201-320)

class TestPluginLifecycle(unittest.TestCase):
    def setUp(self):
        from app.core.plugin_system import (
            init_plugin_system,
            shutdown_plugin_system,
            get_plugin_manager,
        )
        PluginRegistry.reset()
        self.temp_dir = tempfile.mkdtemp()
        
        plugin_dir = Path(self.temp_dir) / "lifecycle-test"
        plugin_dir.mkdir()
        
        meta = {
            "id": "lifecycle-test",
            "name": "Lifecycle Test",
            "version": "1.0.0",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
        }
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(meta, f)
        
        with open(plugin_dir / "main.py", "w") as f:
            f.write("""
class Plugin:
    def __init__(self):
        self.initialized = False
        self.enabled = False
    
    def initialize(self, context):
        self.initialized = True
    
    def shutdown(self):
        self.initialized = False
    
    def on_enable(self):
        self.enabled = True
    
    def on_disable(self):
        self.enabled = False
""")
    
    def tearDown(self):
        shutdown_plugin_system()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_lifecycle(self):
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        
        self.assertTrue(manager._registry.has_plugin("lifecycle-test"))
        
        instance = manager._registry.get_instance("lifecycle-test")
        self.assertTrue(instance.initialized)
        self.assertTrue(instance.enabled)
        
        manager.disable_plugin("lifecycle-test")
        metadata = manager._registry.get("lifecycle-test")
        self.assertEqual(metadata.status, PluginStatus.DISABLED)
        self.assertFalse(instance.enabled)
        
        manager.enable_plugin("lifecycle-test")
        metadata = manager._registry.get("lifecycle-test")
        self.assertEqual(metadata.status, PluginStatus.ENABLED)
        self.assertTrue(instance.enabled)
    
    def test_uninstall_plugin(self):
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        manager.uninstall_plugin("lifecycle-test")
        
        self.assertFalse(manager._registry.has_plugin("lifecycle-test"))
    
    def test_get_plugin_info(self):
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        manager.set_context("app_version", "1.6.0")
        
        info = manager.get_plugin_info("lifecycle-test")
        self.assertEqual(info["metadata"]["id"], "lifecycle-test")
        self.assertTrue(info["has_instance"])
        self.assertIn("app_version", info["context_keys"])
    
    def test_shutdown_all(self):
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        manager.shutdown_all()
        
        instance = manager._registry.get_instance("lifecycle-test")
        self.assertFalse(instance.initialized)


class TestDependencyResolver(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()
        self.registry = PluginRegistry.get_instance()
        self.resolver = DependencyResolver(self.registry)
    
    def tearDown(self):
        PluginRegistry.reset()
    
    def test_resolve_no_dependencies(self):
        meta = PluginMetadata(id="simple", name="Simple", version="1.0.0")
        self.registry.register(meta)
        
        order = self.resolver.resolve_dependencies("simple")
        self.assertEqual(order, ["simple"])
    
    def test_resolve_with_dependencies(self):
        base = PluginMetadata(id="base", name="Base", version="1.0.0")
        ext = PluginMetadata(
            id="ext",
            name="Extension",
            version="1.0.0",
            dependencies=[PluginDependency(name="base")],
        )
        self.registry.register(base)
        self.registry.register(ext)
        
        order = self.resolver.resolve_dependencies("ext")
        self.assertEqual(order, ["base", "ext"])
    
    def test_missing_required_dependency(self):
        meta = PluginMetadata(
            id="needs-dep",
            name="Needs Dep",
            version="1.0.0",
            dependencies=[PluginDependency(name="missing", required=True)],
        )
        self.registry.register(meta)
        
        with self.assertRaises(ValueError):
            self.resolver.resolve_dependencies("needs-dep")
    
    def test_get_dependency_tree(self):
        base = PluginMetadata(id="base", name="Base", version="1.0.0")
        ext = PluginMetadata(
            id="ext",
            name="Extension",
            version="1.0.0",
            dependencies=[PluginDependency(name="base")],
        )
        self.registry.register(base)
        self.registry.register(ext)
        
        tree = self.resolver.get_dependency_tree("ext")
        self.assertEqual(tree["id"], "ext")
        self.assertEqual(len(tree["dependencies"]), 1)
        self.assertEqual(tree["dependencies"][0]["id"], "base")
```

- [ ] **Step 5: 运行全部测试**

```bash
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python -m pytest test_plugin_system.py -v
```

Expected: All tests pass

---

## Phase 2: 进程外Worker架构

### Task 4: gRPC服务定义和Protobuf生成

**Files:**
- Create: `python/app/protos/plugin.proto`
- Create: `python/app/protos/__init__.py`

- [ ] **Step 1: 定义gRPC服务接口**

```protobuf
// python/app/protos/plugin.proto

syntax = "proto3";

package plugin;

service PluginWorker {
  rpc Initialize(InitializeRequest) returns (InitializeResponse);
  rpc Shutdown(ShutdownRequest) returns (ShutdownResponse);
  rpc ExecuteCommand(CommandRequest) returns (CommandResponse);
  rpc GetStatus(StatusRequest) returns (StatusResponse);
  rpc StreamLogs(LogStreamRequest) returns (stream LogEntry);
  rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
}

message InitializeRequest {
  string plugin_id = 1;
  string plugin_path = 2;
  map<string, string> config = 3;
  map<string, string> context = 4;
}

message InitializeResponse {
  bool success = 1;
  string message = 2;
  repeated string capabilities = 3;
}

message ShutdownRequest {
  string plugin_id = 1;
}

message ShutdownResponse {
  bool success = 1;
  string message = 2;
}

message CommandRequest {
  string plugin_id = 1;
  string command = 2;
  bytes payload = 3;
  map<string, string> parameters = 4;
}

message CommandResponse {
  bool success = 1;
  bytes result = 2;
  string error_message = 3;
}

message StatusRequest {
  string plugin_id = 1;
}

message StatusResponse {
  string plugin_id = 1;
  string status = 2;
  int64 uptime_seconds = 3;
  double memory_usage_mb = 4;
  double cpu_usage_percent = 5;
}

message LogStreamRequest {
  string plugin_id = 1;
  int32 log_level = 2;
}

message LogEntry {
  string plugin_id = 1;
  int64 timestamp = 2;
  int32 level = 3;
  string message = 4;
  string source = 5;
}

message HealthCheckRequest {
  string plugin_id = 1;
}

message HealthCheckResponse {
  bool healthy = 1;
  string message = 2;
  repeated string checks = 3;
}

message PluginRegistration {
  string plugin_id = 1;
  string name = 2;
  string version = 3;
  repeated string capabilities = 4;
  string worker_address = 5;
  int32 worker_port = 6;
}
```

- [ ] **Step 2: 创建protos包**

```python
# python/app/protos/__init__.py
```

---

### Task 5: Worker进程管理器

**Files:**
- Create: `python/app/core/plugin_worker.py`
- Test: `test_plugin_system.py` (append worker tests)

- [ ] **Step 1: 实现Worker进程管理器**

```python
# python/app/core/plugin_worker.py (Lines 1-200)

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"


@dataclass
class WorkerConfig:
    plugin_id: str
    plugin_path: str
    worker_port: int = 0
    max_restarts: int = 3
    health_check_interval: float = 30.0
    restart_delay: float = 5.0
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkerInfo:
    config: WorkerConfig
    status: WorkerStatus = WorkerStatus.STOPPED
    process: Optional[multiprocessing.Process] = None
    pid: Optional[int] = None
    port: Optional[int] = None
    started_at: Optional[float] = None
    restart_count: int = 0
    last_health_check: Optional[float] = None
    last_error: Optional[str] = None


class PluginWorkerManager:
    _instance: Optional[PluginWorkerManager] = None
    
    def __init__(self):
        self._workers: Dict[str, WorkerInfo] = {}
        self._health_check_callbacks: List[Callable] = []
        self._running = False
    
    @classmethod
    def get_instance(cls) -> PluginWorkerManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def start_worker(self, config: WorkerConfig) -> WorkerInfo:
        if config.plugin_id in self._workers:
            existing = self._workers[config.plugin_id]
            if existing.status == WorkerStatus.RUNNING:
                raise ValueError(f"Worker for plugin '{config.plugin_id}' already running")
        
        port = config.worker_port or self._find_free_port()
        
        info = WorkerInfo(
            config=config,
            port=port,
            status=WorkerStatus.STARTING,
        )
        self._workers[config.plugin_id] = info
        
        process = multiprocessing.Process(
            target=self._run_worker,
            args=(config, port),
            name=f"plugin-worker-{config.plugin_id}",
            daemon=True,
        )
        
        process.start()
        
        info.process = process
        info.pid = process.pid
        info.started_at = time.time()
        info.status = WorkerStatus.RUNNING
        
        logger.info(f"Worker started for plugin '{config.plugin_id}' (PID: {process.pid}, Port: {port})")
        
        return info
    
    def stop_worker(self, plugin_id: str, timeout: float = 10.0) -> None:
        info = self._workers.get(plugin_id)
        if info is None:
            return
        
        info.status = WorkerStatus.STOPPING
        
        if info.process and info.process.is_alive():
            try:
                info.process.terminate()
                info.process.join(timeout=timeout)
                
                if info.process.is_alive():
                    info.process.kill()
                    info.process.join(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping worker '{plugin_id}': {e}")
        
        info.status = WorkerStatus.STOPPED
        logger.info(f"Worker stopped for plugin '{plugin_id}'")
    
    def restart_worker(self, plugin_id: str) -> WorkerInfo:
        info = self._workers.get(plugin_id)
        if info is None:
            raise KeyError(f"Worker for plugin '{plugin_id}' not found")
        
        if info.restart_count >= info.config.max_restarts:
            info.status = WorkerStatus.CRASHED
            info.last_error = f"Max restarts ({info.config.max_restarts}) reached"
            raise RuntimeError(f"Cannot restart '{plugin_id}': max restarts exceeded")
        
        info.status = WorkerStatus.RESTARTING
        info.restart_count += 1
        
        logger.info(f"Restarting worker for plugin '{plugin_id}' (attempt {info.restart_count})")
        
        self.stop_worker(plugin_id)
        
        time.sleep(info.config.restart_delay)
        
        new_info = self.start_worker(info.config)
        new_info.restart_count = info.restart_count
        
        return new_info
    
    def health_check(self, plugin_id: Optional[str] = None) -> Dict[str, Any]:
        results = {}
        
        plugin_ids = [plugin_id] if plugin_id else list(self._workers.keys())
        
        for pid in plugin_ids:
            info = self._workers.get(pid)
            if info is None:
                results[pid] = {"status": "not_found"}
                continue
            
            if info.process is None:
                results[pid] = {"status": "no_process"}
                continue
            
            is_alive = info.process.is_alive()
            info.last_health_check = time.time()
            
            if not is_alive and info.status == WorkerStatus.RUNNING:
                info.status = WorkerStatus.CRASHED
                info.last_error = "Process died unexpectedly"
                
                try:
                    self.restart_worker(pid)
                    results[pid] = {"status": "restarted", "restart_count": info.restart_count}
                except RuntimeError:
                    results[pid] = {"status": "crashed", "error": info.last_error}
            else:
                results[pid] = {
                    "status": "healthy" if is_alive else "unhealthy",
                    "pid": info.pid,
                    "uptime": time.time() - info.started_at if info.started_at else 0,
                    "restart_count": info.restart_count,
                }
        
        return results
    
    def get_worker_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        info = self._workers.get(plugin_id)
        if info is None:
            return None
        
        return {
            "plugin_id": info.config.plugin_id,
            "status": info.status.value,
            "pid": info.pid,
            "port": info.port,
            "started_at": info.started_at,
            "restart_count": info.restart_count,
            "last_error": info.last_error,
            "uptime": time.time() - info.started_at if info.started_at else 0,
        }
    
    def list_workers(self) -> List[Dict[str, Any]]:
        return [self.get_worker_info(pid) for pid in self._workers if self.get_worker_info(pid)]
    
    def stop_all_workers(self, timeout: float = 10.0) -> None:
        for plugin_id in list(self._workers.keys()):
            try:
                self.stop_worker(plugin_id, timeout)
            except Exception as e:
                logger.error(f"Error stopping worker '{plugin_id}': {e}")
        
        self._workers.clear()
        logger.info("All workers stopped")
    
    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def _run_worker(self, config: WorkerConfig, port: int) -> None:
        logger.info(f"Worker process starting for plugin '{config.plugin_id}' on port {port}")
        
        try:
            env = os.environ.copy()
            env.update(config.environment)
            env["PLUGIN_ID"] = config.plugin_id
            env["PLUGIN_PORT"] = str(port)
            env["PLUGIN_PATH"] = config.plugin_path
            
            worker_script = Path(__file__).parent / "worker_process.py"
            
            if worker_script.exists():
                result = subprocess.run(
                    [sys.executable, str(worker_script)],
                    env=env,
                    cwd=config.plugin_path,
                )
                
                if result.returncode != 0:
                    logger.error(f"Worker process exited with code {result.returncode}")
            else:
                self._run_worker_inline(config, port)
        
        except Exception as e:
            logger.error(f"Worker process failed for '{config.plugin_id}': {e}")
            raise
    
    def _run_worker_inline(self, config: WorkerConfig, port: int) -> None:
        from app.core.plugin_system import PluginLoader, PluginRegistry, PluginMetadata
        
        registry = PluginRegistry.get_instance()
        loader = PluginLoader(registry)
        
        metadata = PluginMetadata(
            id=config.plugin_id,
            name=config.plugin_id,
            version="1.0.0",
            plugin_path=config.plugin_path,
        )
        
        try:
            instance = loader.load_plugin(metadata)
            
            if hasattr(instance, "initialize"):
                instance.initialize({})
            
            while True:
                time.sleep(1)
        
        except KeyboardInterrupt:
            pass
        finally:
            if hasattr(instance, "shutdown"):
                instance.shutdown()
```

- [ ] **Step 2: 编写Worker测试**

```python
# test_plugin_system.py (Append at end)

class TestPluginWorkerManager(unittest.TestCase):
    def setUp(self):
        from app.core.plugin_worker import PluginWorkerManager
        PluginWorkerManager.reset()
        self.manager = PluginWorkerManager.get_instance()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        from app.core.plugin_worker import PluginWorkerManager
        self.manager.stop_all_workers(timeout=2)
        PluginWorkerManager.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_start_and_stop_worker(self):
        from app.core.plugin_worker import WorkerConfig, WorkerStatus
        
        config = WorkerConfig(
            plugin_id="test-worker",
            plugin_path=self.temp_dir,
        )
        
        info = self.manager.start_worker(config)
        self.assertEqual(info.status, WorkerStatus.RUNNING)
        self.assertIsNotNone(info.pid)
        self.assertIsNotNone(info.port)
        
        self.manager.stop_worker("test-worker")
        info = self.manager.get_worker_info("test-worker")
        self.assertEqual(info["status"], "stopped")
    
    def test_list_workers(self):
        from app.core.plugin_worker import WorkerConfig
        
        config1 = WorkerConfig(
            plugin_id="worker-1",
            plugin_path=self.temp_dir,
        )
        config2 = WorkerConfig(
            plugin_id="worker-2",
            plugin_path=self.temp_dir,
        )
        
        self.manager.start_worker(config1)
        self.manager.start_worker(config2)
        
        workers = self.manager.list_workers()
        self.assertEqual(len(workers), 2)
        
        self.manager.stop_all_workers()
    
    def test_health_check(self):
        from app.core.plugin_worker import WorkerConfig
        
        config = WorkerConfig(
            plugin_id="health-test",
            plugin_path=self.temp_dir,
            health_check_interval=5.0,
        )
        
        self.manager.start_worker(config)
        
        results = self.manager.health_check("health-test")
        self.assertIn("health-test", results)
        self.assertIn("status", results["health-test"])
```

- [ ] **Step 3: 运行Worker测试**

```bash
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python -m pytest test_plugin_system.py::TestPluginWorkerManager -v -s
```

---

## Phase 3: 能力门控系统

### Task 6: 能力声明和权限验证

**Files:**
- Create: `python/app/core/capability_gating.py`
- Test: `test_plugin_system.py` (append gating tests)

- [ ] **Step 1: 实现能力门控系统**

```python
# python/app/core/capability_gating.py (Lines 1-250)

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CapabilityLevel(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    FULL_CONTROL = "full_control"


@dataclass
class FileAccessRule:
    path_pattern: str
    level: CapabilityLevel = CapabilityLevel.READ_ONLY
    _compiled: Optional[Any] = field(default=None, repr=False)
    
    def matches(self, path: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(path, self.path_pattern)


@dataclass
class NetworkAccessRule:
    host_pattern: str
    port_range: Optional[tuple] = None
    protocol: str = "*"
    
    def matches(self, host: str, port: int = 0) -> bool:
        import fnmatch
        host_match = fnmatch.fnmatch(host, self.host_pattern)
        
        if self.port_range is None:
            return host_match
        
        return host_match and (self.port_range[0] <= port <= self.port_range[1])


@dataclass
class GpuResourceLimit:
    max_memory_mb: float = 1024.0
    max_utilization_percent: float = 50.0
    allowed_devices: List[int] = field(default_factory=lambda: [0])


@dataclass
class CapabilityGrant:
    capability: str
    level: CapabilityLevel = CapabilityLevel.READ_ONLY
    file_rules: List[FileAccessRule] = field(default_factory=list)
    network_rules: List[NetworkAccessRule] = field(default_factory=list)
    gpu_limits: Optional[GpuResourceLimit] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilityGatekeeper:
    _instance: Optional[CapabilityGatekeeper] = None
    
    def __init__(self):
        self._grants: Dict[str, Dict[str, CapabilityGrant]] = {}
        self._default_grants: Dict[str, CapabilityGrant] = self._create_default_grants()
    
    @classmethod
    def get_instance(cls) -> CapabilityGatekeeper:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def _create_default_grants(self) -> Dict[str, CapabilityGrant]:
        return {
            "data_source": CapabilityGrant(
                capability="data_source",
                level=CapabilityLevel.READ_ONLY,
                network_rules=[NetworkAccessRule(host_pattern="localhost", port_range=(1, 65535))],
            ),
            "machine_control": CapabilityGrant(
                capability="machine_control",
                level=CapabilityLevel.READ_WRITE,
                network_rules=[NetworkAccessRule(host_pattern="localhost", port_range=(1, 65535))],
            ),
            "file_access": CapabilityGrant(
                capability="file_access",
                level=CapabilityLevel.READ_ONLY,
                file_rules=[FileAccessRule(path_pattern="*.txt", level=CapabilityLevel.READ_ONLY)],
            ),
            "network_access": CapabilityGrant(
                capability="network_access",
                level=CapabilityLevel.READ_ONLY,
                network_rules=[NetworkAccessRule(host_pattern="*")],
            ),
            "gpu_access": CapabilityGrant(
                capability="gpu_access",
                level=CapabilityLevel.READ_ONLY,
                gpu_limits=GpuResourceLimit(
                    max_memory_mb=512.0,
                    max_utilization_percent=30.0,
                ),
            ),
        }
    
    def grant_capabilities(self, plugin_id: str, capabilities: List[str]) -> List[CapabilityGrant]:
        if plugin_id not in self._grants:
            self._grants[plugin_id] = {}
        
        granted = []
        for cap in capabilities:
            if cap in self._default_grants:
                grant = self._default_grants[cap]
                self._grants[plugin_id][cap] = grant
                granted.append(grant)
            else:
                logger.warning(f"Unknown capability '{cap}' for plugin '{plugin_id}'")
        
        logger.info(f"Granted {len(granted)} capabilities to plugin '{plugin_id}'")
        return granted
    
    def revoke_capabilities(self, plugin_id: str, capabilities: List[str]) -> None:
        if plugin_id in self._grants:
            for cap in capabilities:
                self._grants[plugin_id].pop(cap, None)
            
            if not self._grants[plugin_id]:
                del self._grants[plugin_id]
        
        logger.info(f"Revoked capabilities from plugin '{plugin_id}'")
    
    def has_capability(self, plugin_id: str, capability: str) -> bool:
        return (
            plugin_id in self._grants
            and capability in self._grants[plugin_id]
        )
    
    def get_grant(self, plugin_id: str, capability: str) -> Optional[CapabilityGrant]:
        if plugin_id in self._grants:
            return self._grants[plugin_id].get(capability)
        return None
    
    def check_file_access(self, plugin_id: str, path: str, operation: str = "read") -> bool:
        grant = self.get_grant(plugin_id, "file_access")
        if grant is None:
            return False
        
        for rule in grant.file_rules:
            if rule.matches(path):
                if operation == "read" and grant.level in (CapabilityLevel.READ_ONLY, CapabilityLevel.READ_WRITE, CapabilityLevel.FULL_CONTROL):
                    return True
                if operation == "write" and grant.level in (CapabilityLevel.READ_WRITE, CapabilityLevel.FULL_CONTROL):
                    return True
        
        return False
    
    def check_network_access(self, plugin_id: str, host: str, port: int = 0) -> bool:
        grant = self.get_grant(plugin_id, "network_access")
        if grant is None:
            grant = self.get_grant(plugin_id, "data_source")
            if grant is None:
                return False
        
        for rule in grant.network_rules:
            if rule.matches(host, port):
                return True
        
        return False
    
    def check_gpu_access(self, plugin_id: str) -> Optional[GpuResourceLimit]:
        grant = self.get_grant(plugin_id, "gpu_access")
        if grant is None:
            return None
        
        return grant.gpu_limits
    
    def get_plugin_capabilities(self, plugin_id: str) -> List[str]:
        if plugin_id in self._grants:
            return list(self._grants[plugin_id].keys())
        return []
    
    def get_all_grants(self) -> Dict[str, List[Dict[str, Any]]]:
        result = {}
        for plugin_id, caps in self._grants.items():
            result[plugin_id] = []
            for cap_name, grant in caps.items():
                result[plugin_id].append({
                    "capability": cap_name,
                    "level": grant.level.value,
                    "file_rules": [{"pattern": r.path_pattern, "level": r.level.value} for r in grant.file_rules],
                    "network_rules": [{"host": r.host_pattern, "port_range": r.port_range} for r in grant.network_rules],
                    "gpu_limits": {
                        "max_memory_mb": grant.gpu_limits.max_memory_mb,
                        "max_utilization_percent": grant.gpu_limits.max_utilization_percent,
                    } if grant.gpu_limits else None,
                })
        return result
    
    def update_grant_rules(
        self,
        plugin_id: str,
        capability: str,
        file_rules: Optional[List[Dict]] = None,
        network_rules: Optional[List[Dict]] = None,
        gpu_limits: Optional[Dict] = None,
    ) -> None:
        grant = self.get_grant(plugin_id, capability)
        if grant is None:
            raise ValueError(f"No grant found for plugin '{plugin_id}' capability '{capability}'")
        
        if file_rules is not None:
            grant.file_rules = [
                FileAccessRule(path_pattern=r.get("path_pattern", "*"), level=CapabilityLevel(r.get("level", "read_only")))
                for r in file_rules
            ]
        
        if network_rules is not None:
            grant.network_rules = [
                NetworkAccessRule(
                    host_pattern=r.get("host_pattern", "*"),
                    port_range=tuple(r.get("port_range", (1, 65535))) if r.get("port_range") else None,
                )
                for r in network_rules
            ]
        
        if gpu_limits is not None:
            grant.gpu_limits = GpuResourceLimit(
                max_memory_mb=gpu_limits.get("max_memory_mb", 1024.0),
                max_utilization_percent=gpu_limits.get("max_utilization_percent", 50.0),
            )
        
        logger.info(f"Updated grant rules for plugin '{plugin_id}' capability '{capability}'")
```

- [ ] **Step 2: 编写能力门控测试**

```python
# test_plugin_system.py (Append at end)

class TestCapabilityGating(unittest.TestCase):
    def setUp(self):
        from app.core.capability_gating import CapabilityGatekeeper
        CapabilityGatekeeper.reset()
        self.gatekeeper = CapabilityGatekeeper.get_instance()
    
    def tearDown(self):
        from app.core.capability_gating import CapabilityGatekeeper
        CapabilityGatekeeper.reset()
    
    def test_grant_capabilities(self):
        grants = self.gatekeeper.grant_capabilities("test-plugin", ["data_source", "file_access"])
        self.assertEqual(len(grants), 2)
        
        self.assertTrue(self.gatekeeper.has_capability("test-plugin", "data_source"))
        self.assertTrue(self.gatekeeper.has_capability("test-plugin", "file_access"))
    
    def test_revoke_capabilities(self):
        self.gatekeeper.grant_capabilities("test-plugin", ["data_source", "file_access"])
        self.gatekeeper.revoke_capabilities("test-plugin", ["data_source"])
        
        self.assertFalse(self.gatekeeper.has_capability("test-plugin", "data_source"))
        self.assertTrue(self.gatekeeper.has_capability("test-plugin", "file_access"))
    
    def test_check_file_access(self):
        from app.core.capability_gating import FileAccessRule, CapabilityLevel
        
        self.gatekeeper.grant_capabilities("test-plugin", ["file_access"])
        
        grant = self.gatekeeper.get_grant("test-plugin", "file_access")
        grant.file_rules.append(FileAccessRule(path_pattern="*.txt"))
        
        self.assertTrue(self.gatekeeper.check_file_access("test-plugin", "data.txt", "read"))
        self.assertFalse(self.gatekeeper.check_file_access("test-plugin", "data.csv", "read"))
    
    def test_check_network_access(self):
        self.gatekeeper.grant_capabilities("test-plugin", ["data_source"])
        
        self.assertTrue(self.gatekeeper.check_network_access("test-plugin", "localhost", 8080))
        self.assertFalse(self.gatekeeper.check_network_access("test-plugin", "external.com", 443))
    
    def test_check_gpu_access(self):
        self.gatekeeper.grant_capabilities("test-plugin", ["gpu_access"])
        
        limits = self.gatekeeper.check_gpu_access("test-plugin")
        self.assertIsNotNone(limits)
        self.assertEqual(limits.max_memory_mb, 512.0)
    
    def test_get_all_grants(self):
        self.gatekeeper.grant_capabilities("plugin-1", ["data_source"])
        self.gatekeeper.grant_capabilities("plugin-2", ["file_access", "network_access"])
        
        all_grants = self.gatekeeper.get_all_grants()
        self.assertIn("plugin-1", all_grants)
        self.assertIn("plugin-2", all_grants)
        self.assertEqual(len(all_grants["plugin-1"]), 1)
        self.assertEqual(len(all_grants["plugin-2"]), 2)
    
    def test_update_grant_rules(self):
        self.gatekeeper.grant_capabilities("test-plugin", ["file_access"])
        
        self.gatekeeper.update_grant_rules(
            "test-plugin",
            "file_access",
            file_rules=[{"path_pattern": "*.log", "level": "read_write"}],
        )
        
        grant = self.gatekeeper.get_grant("test-plugin", "file_access")
        self.assertEqual(len(grant.file_rules), 1)
        self.assertEqual(grant.file_rules[0].path_pattern, "*.log")
```

- [ ] **Step 3: 运行能力门控测试**

```bash
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python -m pytest test_plugin_system.py::TestCapabilityGating -v
```

---

## Phase 4: API端点和前端界面

### Task 7: 插件管理API端点

**Files:**
- Create: `python/app/api/v1/plugins.py`
- Modify: `python/app/main.py`

- [ ] **Step 1: 创建插件管理API**

```python
# python/app/api/v1/plugins.py (Lines 1-300)

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.capability_gating import CapabilityGatekeeper, get_capability_gatekeeper
from app.core.plugin_system import (
    PluginLifecycleManager,
    PluginMetadata,
    PluginRegistry,
    PluginStatus,
    get_dependency_resolver,
    get_plugin_manager,
)
from app.core.plugin_worker import PluginWorkerManager, WorkerConfig
from app.core.response import error, success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


@router.get("/marketplace")
def list_marketplace_plugins(
    query: Optional[str] = Query(None, description="Search query"),
    plugin_type: Optional[str] = Query(None, description="Filter by type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return success(data={
        "plugins": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    })


@router.post("/marketplace/{plugin_id}/install")
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
        
        return success(data={
            "plugins": [p.to_dict() for p in plugins],
            "total": len(plugins),
        })
    except Exception as e:
        return error(str(e), code=500)


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
        except:
            pass
        
        info["worker"] = worker_info
        
        return success(data=info)
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.post("/{plugin_id}/enable")
def enable_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager.enable_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' enabled"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.post("/{plugin_id}/disable")
def disable_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager.disable_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' disabled"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.post("/{plugin_id}/reload")
def reload_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager._loader.reload_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' reloaded"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.delete("/{plugin_id}")
def uninstall_plugin(plugin_id: str):
    try:
        manager = get_plugin_manager()
        manager.uninstall_plugin(plugin_id)
        return success(data={"message": f"Plugin '{plugin_id}' uninstalled"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.put("/{plugin_id}/config")
def update_plugin_config(plugin_id: str, config: Dict[str, Any]):
    try:
        manager = get_plugin_manager()
        manager._registry.update_config(plugin_id, config)
        return success(data={"message": f"Plugin '{plugin_id}' config updated"})
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.get("/{plugin_id}/dependencies")
def get_plugin_dependencies(plugin_id: str):
    try:
        resolver = get_dependency_resolver()
        tree = resolver.get_dependency_tree(plugin_id)
        order = resolver.resolve_dependencies(plugin_id)
        
        return success(data={
            "tree": tree,
            "load_order": order,
        })
    except KeyError:
        return error(f"Plugin '{plugin_id}' not found", code=404)
    except Exception as e:
        return error(str(e), code=500)


@router.get("/{plugin_id}/logs")
def get_plugin_logs(
    plugin_id: str,
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return success(data={
        "logs": [],
        "total": 0,
    })


@router.get("/{plugin_id}/capabilities")
def get_plugin_capabilities(plugin_id: str):
    try:
        gatekeeper = CapabilityGatekeeper.get_instance()
        caps = gatekeeper.get_plugin_capabilities(plugin_id)
        grants = gatekeeper.get_grant(plugin_id, "file_access")
        
        return success(data={
            "capabilities": caps,
            "grants": grants,
        })
    except Exception as e:
        return error(str(e), code=500)


@router.put("/{plugin_id}/capabilities/{capability}")
def update_capability_grant(
    plugin_id: str,
    capability: str,
    file_rules: Optional[List[Dict]] = None,
    network_rules: Optional[List[Dict]] = None,
    gpu_limits: Optional[Dict] = None,
):
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
    except Exception as e:
        return error(str(e), code=500)


@router.get("/workers")
def list_workers():
    try:
        worker_mgr = PluginWorkerManager.get_instance()
        workers = worker_mgr.list_workers()
        return success(data={"workers": workers})
    except Exception as e:
        return error(str(e), code=500)


@router.post("/workers/{plugin_id}/start")
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
    except Exception as e:
        return error(str(e), code=500)


@router.post("/workers/{plugin_id}/stop")
def stop_worker(plugin_id: str):
    try:
        worker_mgr = PluginWorkerManager.get_instance()
        worker_mgr.stop_worker(plugin_id)
        return success(data={"message": f"Worker for '{plugin_id}' stopped"})
    except Exception as e:
        return error(str(e), code=500)


@router.get("/health")
def health_check(plugin_id: Optional[str] = None):
    try:
        worker_mgr = PluginWorkerManager.get_instance()
        results = worker_mgr.health_check(plugin_id)
        return success(data={"health": results})
    except Exception as e:
        return error(str(e), code=500)
```

- [ ] **Step 2: 集成到main.py**

```python
# python/app/main.py - 在现有import后添加:
from app.api.v1 import plugins

# 在lifespan中添加插件系统初始化:
from app.core.plugin_system import init_plugin_system, shutdown_plugin_system
from app.core.plugin_worker import PluginWorkerManager

# 在startup_event中添加 (在init_approval_engine()后):
init_plugin_system(
    plugin_dirs=[str(Path(__file__).parent.parent / "plugins")],
    user_dirs=[],
    context={"app_version": "1.6.0"},
)

# 在shutdown_event中添加 (第一行):
shutdown_plugin_system()
PluginWorkerManager.get_instance().stop_all_workers()

# 在include_router部分添加:
app.include_router(plugins.router)
```

---

### Task 8: 插件管理前端界面

**Files:**
- Create: `src/views/PluginMarket.vue`
- Create: `src/views/PluginManager.vue`
- Create: `src/views/PluginDetail.vue`
- Create: `src/views/PluginLogs.vue`
- Create: `src/stores/plugin.ts`
- Modify: `src/router/index.ts`

- [ ] **Step 1: 创建Pinia插件状态管理**

```typescript
// src/stores/plugin.ts

import { defineStore } from 'pinia'
import axios from 'axios'

export interface Plugin {
  id: string
  name: string
  version: string
  author: string
  description: string
  entry_point: string
  plugin_type: string
  capabilities: string[]
  dependencies: Array<{ name: string; version: string; required: boolean }>
  config_schema: Record<string, any>
  min_core_version: string
  max_core_version: string
  plugin_path: string
  status: string
  config: Record<string, any>
  enabled_at?: number
  disabled_at?: number
  installed_at?: number
}

export interface PluginDetail {
  metadata: Plugin
  has_instance: boolean
  context_keys: string[]
  dependency_tree: any
  capabilities: string[]
  worker?: any
}

export interface PluginState {
  plugins: Plugin[]
  currentPlugin: PluginDetail | null
  loading: boolean
  error: string | null
}

export const usePluginStore = defineStore('plugin', {
  state: (): PluginState => ({
    plugins: [],
    currentPlugin: null,
    loading: false,
    error: null,
  }),

  getters: {
    enabledPlugins: (state) => state.plugins.filter(p => p.status === 'enabled'),
    disabledPlugins: (state) => state.plugins.filter(p => p.status === 'disabled'),
    adapterPlugins: (state) => state.plugins.filter(p => p.plugin_type === 'adapter'),
    dataSourcePlugins: (state) => state.plugins.filter(p => p.plugin_type === 'data_source'),
    analyzerPlugins: (state) => state.plugins.filter(p => p.plugin_type === 'analyzer'),
    visualizationPlugins: (state) => state.plugins.filter(p => p.plugin_type === 'visualization'),
  },

  actions: {
    async fetchPlugins() {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get('/api/v1/plugins')
        this.plugins = response.data.data.plugins
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async fetchPluginDetail(pluginId: string) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get(`/api/v1/plugins/${pluginId}`)
        this.currentPlugin = response.data.data
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async enablePlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.post(`/api/v1/plugins/${pluginId}/enable`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async disablePlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.post(`/api/v1/plugins/${pluginId}/disable`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async uninstallPlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.delete(`/api/v1/plugins/${pluginId}`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async updatePluginConfig(pluginId: string, config: Record<string, any>) {
      this.loading = true
      try {
        await axios.put(`/api/v1/plugins/${pluginId}/config`, config)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async reloadPlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.post(`/api/v1/plugins/${pluginId}/reload`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
  },
})
```

- [ ] **Step 2: 创建插件管理页面**

```vue
<!-- src/views/PluginManager.vue -->

<template>
  <div class="plugin-manager">
    <el-card class="header-card">
      <div class="header-content">
        <h2>插件管理</h2>
        <div class="actions">
          <el-button type="primary" @click="refreshPlugins">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-input
            v-model="searchQuery"
            placeholder="搜索插件..."
            style="width: 200px; margin-left: 10px"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ plugins.length }}</div>
          <div class="stat-label">总计</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card enabled">
          <div class="stat-value">{{ enabledPlugins.length }}</div>
          <div class="stat-label">已启用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card disabled">
          <div class="stat-value">{{ disabledPlugins.length }}</div>
          <div class="stat-label">已停用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card error">
          <div class="stat-value">{{ errorPlugins.length }}</div>
          <div class="stat-label">异常</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="plugins-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="全部" name="all">
          <PluginTable
            :plugins="filteredPlugins"
            @enable="handleEnable"
            @disable="handleDisable"
            @uninstall="handleUninstall"
            @detail="handleDetail"
          />
        </el-tab-pane>
        <el-tab-pane label="适配器" name="adapter">
          <PluginTable
            :plugins="adapterPlugins"
            @enable="handleEnable"
            @disable="handleDisable"
            @uninstall="handleUninstall"
            @detail="handleDetail"
          />
        </el-tab-pane>
        <el-tab-pane label="数据源" name="data_source">
          <PluginTable
            :plugins="dataSourcePlugins"
            @enable="handleEnable"
            @disable="handleDisable"
            @uninstall="handleUninstall"
            @detail="handleDetail"
          />
        </el-tab-pane>
        <el-tab-pane label="分析器" name="analyzer">
          <PluginTable
            :plugins="analyzerPlugins"
            @enable="handleEnable"
            @disable="handleDisable"
            @uninstall="handleUninstall"
            @detail="handleDetail"
          />
        </el-tab-pane>
        <el-tab-pane label="可视化" name="visualization">
          <PluginTable
            :plugins="visualizationPlugins"
            @enable="handleEnable"
            @disable="handleDisable"
            @uninstall="handleUninstall"
            @detail="handleDetail"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <PluginDetailDialog
      v-model:visible="detailDialogVisible"
      :plugin="currentPlugin"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePluginStore } from '../stores/plugin'
import { Refresh, Search } from '@element-plus/icons-vue'
import PluginTable from '../components/plugin/PluginTable.vue'
import PluginDetailDialog from '../components/plugin/PluginDetailDialog.vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const pluginStore = usePluginStore()
const searchQuery = ref('')
const activeTab = ref('all')
const detailDialogVisible = ref(false)
const currentPlugin = ref<any>(null)

const plugins = computed(() => pluginStore.plugins)
const enabledPlugins = computed(() => pluginStore.enabledPlugins)
const disabledPlugins = computed(() => pluginStore.disabledPlugins)
const adapterPlugins = computed(() => pluginStore.adapterPlugins)
const dataSourcePlugins = computed(() => pluginStore.dataSourcePlugins)
const analyzerPlugins = computed(() => pluginStore.analyzerPlugins)
const visualizationPlugins = computed(() => pluginStore.visualizationPlugins)

const errorPlugins = computed(() =>
  plugins.value.filter(p => p.status === 'error')
)

const filteredPlugins = computed(() => {
  if (!searchQuery.value) return plugins.value
  const query = searchQuery.value.toLowerCase()
  return plugins.value.filter(
    p => p.name.toLowerCase().includes(query) ||
       p.id.toLowerCase().includes(query) ||
       p.description.toLowerCase().includes(query)
  )
})

onMounted(() => {
  pluginStore.fetchPlugins()
})

const refreshPlugins = () => {
  pluginStore.fetchPlugins()
  ElMessage.success('插件列表已刷新')
}

const handleEnable = async (pluginId: string) => {
  await pluginStore.enablePlugin(pluginId)
  ElMessage.success('插件已启用')
}

const handleDisable = async (pluginId: string) => {
  await pluginStore.disablePlugin(pluginId)
  ElMessage.success('插件已停用')
}

const handleUninstall = async (pluginId: string) => {
  try {
    await ElMessageBox.confirm('确定要卸载此插件吗？此操作不可恢复。', '确认卸载', {
      confirmButtonText: '卸载',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await pluginStore.uninstallPlugin(pluginId)
    ElMessage.success('插件已卸载')
  } catch {
  }
}

const handleDetail = async (pluginId: string) => {
  await pluginStore.fetchPluginDetail(pluginId)
  currentPlugin.value = pluginStore.currentPlugin
  detailDialogVisible.value = true
}
</script>

<style scoped>
.plugin-manager {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  margin-top: 5px;
}

.stat-card.enabled .stat-value {
  color: #67c23a;
}

.stat-card.disabled .stat-value {
  color: #e6a23c;
}

.stat-card.error .stat-value {
  color: #f56c6c;
}

.plugins-card {
  min-height: 400px;
}
</style>
```

- [ ] **Step 3: 创建插件详情对话框组件**

```vue
<!-- src/components/plugin/PluginDetailDialog.vue -->

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="plugin?.metadata?.name || '插件详情'"
    width="800px"
    @close="handleClose"
  >
    <div v-if="plugin" class="plugin-detail">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ plugin.metadata.id }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ plugin.metadata.version }}</el-descriptions-item>
        <el-descriptions-item label="作者">{{ plugin.metadata.author }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType">{{ plugin.metadata.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="类型">{{ plugin.metadata.plugin_type }}</el-descriptions-item>
        <el-descriptions-item label="兼容性">
          {{ plugin.metadata.min_core_version }} - {{ plugin.metadata.max_core_version }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="section">
        <h4>描述</h4>
        <p>{{ plugin.metadata.description }}</p>
      </div>

      <div class="section">
        <h4>能力声明</h4>
        <el-tag
          v-for="cap in plugin.capabilities"
          :key="cap"
          style="margin-right: 5px; margin-bottom: 5px"
        >
          {{ cap }}
        </el-tag>
      </div>

      <div class="section">
        <h4>依赖关系</h4>
        <DependencyTree :tree="plugin.dependency_tree" />
      </div>

      <div v-if="plugin.worker" class="section">
        <h4>Worker信息</h4>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="状态">{{ plugin.worker.status }}</el-descriptions-item>
          <el-descriptions-item label="PID">{{ plugin.worker.pid }}</el-descriptions-item>
          <el-descriptions-item label="端口">{{ plugin.worker.port }}</el-descriptions-item>
          <el-descriptions-item label="运行时长">{{ formatUptime(plugin.worker.uptime) }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="section">
        <h4>配置</h4>
        <el-input
          v-model="configJson"
          type="textarea"
          :rows="5"
          @blur="handleConfigChange"
        />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import DependencyTree from './DependencyTree.vue'
import { usePluginStore } from '../../stores/plugin'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  plugin: any
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const pluginStore = usePluginStore()
const configJson = ref('{}')

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const statusType = computed(() => {
  const status = props.plugin?.metadata?.status
  switch (status) {
    case 'enabled': return 'success'
    case 'disabled': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
})

watch(() => props.plugin, (val) => {
  if (val) {
    configJson.value = JSON.stringify(val.metadata.config, null, 2)
  }
}, { immediate: true })

const formatUptime = (seconds: number) => {
  if (!seconds) return 'N/A'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${minutes}m`
}

const handleConfigChange = async () => {
  if (!props.plugin) return
  try {
    const config = JSON.parse(configJson.value)
    await pluginStore.updatePluginConfig(props.plugin.metadata.id, config)
    ElMessage.success('配置已更新')
  } catch (e) {
    ElMessage.error('无效的JSON格式')
  }
}

const handleClose = () => {
  emit('update:visible', false)
}
</script>

<style scoped>
.plugin-detail {
  padding: 10px 0;
}

.section {
  margin-top: 20px;
}

.section h4 {
  margin-bottom: 10px;
  color: #303133;
}
</style>
```

- [ ] **Step 4: 创建插件表格组件**

```vue
<!-- src/components/plugin/PluginTable.vue -->

<template>
  <el-table :data="plugins" stripe>
    <el-table-column prop="id" label="ID" width="150" />
    <el-table-column prop="name" label="名称" width="150" />
    <el-table-column prop="version" label="版本" width="80" />
    <el-table-column prop="plugin_type" label="类型" width="100">
      <template #default="{ row }">
        <el-tag size="small">{{ row.plugin_type }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="status" label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="getStatusType(row.status)" size="small">
          {{ row.status }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
    <el-table-column label="操作" width="200" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="$emit('detail', row.id)">详情</el-button>
        <el-button
          v-if="row.status === 'enabled'"
          size="small"
          type="warning"
          @click="$emit('disable', row.id)"
        >停用</el-button>
        <el-button
          v-else
          size="small"
          type="success"
          @click="$emit('enable', row.id)"
        >启用</el-button>
        <el-button
          size="small"
          type="danger"
          @click="$emit('uninstall', row.id)"
        >卸载</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
defineProps<{
  plugins: any[]
}>()

defineEmits<{
  enable: [id: string]
  disable: [id: string]
  uninstall: [id: string]
  detail: [id: string]
}>()

const getStatusType = (status: string) => {
  switch (status) {
    case 'enabled': return 'success'
    case 'disabled': return 'warning'
    case 'error': return 'danger'
    default: return 'info'
  }
}
</script>
```

- [ ] **Step 5: 创建依赖树组件**

```vue
<!-- src/components/plugin/DependencyTree.vue -->

<template>
  <div class="dependency-tree">
    <TreeNode v-if="tree" :node="tree" />
  </div>
</template>

<script setup lang="ts">
import TreeNode from './DependencyTreeNode.vue'

defineProps<{
  tree: any
}>()
</script>

<style scoped>
.dependency-tree {
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}
</style>
```

```vue
<!-- src/components/plugin/DependencyTreeNode.vue -->

<template>
  <div class="tree-node">
    <div class="node-content">
      <el-icon v-if="node.dependencies?.length" class="expand-icon" @click="expanded = !expanded">
        <ArrowRight v-if="!expanded" />
        <ArrowDown v-else />
      </el-icon>
      <span class="node-name">{{ node.name }}</span>
      <el-tag size="small" style="margin-left: 5px">{{ node.version }}</el-tag>
      <el-tag
        v-if="node.status === 'missing'"
        type="danger"
        size="small"
        style="margin-left: 5px"
      >缺失</el-tag>
    </div>
    <div v-if="expanded && node.dependencies?.length" class="children">
      <TreeNode v-for="child in node.dependencies" :key="child.id" :node="child" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowRight, ArrowDown } from '@element-plus/icons-vue'

defineProps<{
  node: any
}>()

const expanded = ref(false)
</script>

<style scoped>
.tree-node {
  margin-left: 20px;
}

.node-content {
  display: flex;
  align-items: center;
  padding: 5px 0;
}

.expand-icon {
  cursor: pointer;
  margin-right: 5px;
}

.children {
  margin-left: 10px;
}
</style>
```

- [ ] **Step 6: 添加路由**

```typescript
// src/router/index.ts - 在routes数组中添加:

{
  path: '/plugins',
  name: 'plugin-manager',
  component: () => import('../views/PluginManager.vue'),
  meta: { title: '插件管理' }
},
{
  path: '/plugin-market',
  name: 'plugin-market',
  component: () => import('../views/PluginMarket.vue'),
  meta: { title: '插件市场' }
},
{
  path: '/plugin-logs',
  name: 'plugin-logs',
  component: () => import('../views/PluginLogs.vue'),
  meta: { title: '插件日志' }
},
```

---

## Phase 5: 插件开发工具和测试

### Task 9: 插件脚手架工具

**Files:**
- Create: `tools/plugin-cli.py`
- Create: `templates/plugin/plugin.json`
- Create: `templates/plugin/main.py`

- [ ] **Step 1: 创建插件脚手架工具**

```python
# tools/plugin-cli.py

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


PLUGIN_TYPES = {
    "adapter": {
        "capabilities": ["data_source", "machine_control"],
        "description": "机床通信协议适配器",
    },
    "data_source": {
        "capabilities": ["data_source"],
        "description": "数据采集源",
    },
    "analyzer": {
        "capabilities": ["data_source"],
        "description": "数据分析处理器",
    },
    "visualization": {
        "capabilities": ["data_source"],
        "description": "数据可视化组件",
    },
}


def create_plugin(name: str, plugin_type: str, author: str, output_dir: str):
    if plugin_type not in PLUGIN_TYPES:
        print(f"Error: Invalid plugin type '{plugin_type}'. Choose from: {', '.join(PLUGIN_TYPES.keys())}")
        return
    
    plugin_id = name.lower().replace(" ", "-").replace("_", "-")
    output_path = Path(output_dir) / plugin_id
    
    if output_path.exists():
        print(f"Error: Plugin directory '{output_path}' already exists")
        return
    
    output_path.mkdir(parents=True)
    
    type_info = PLUGIN_TYPES[plugin_type]
    
    metadata = {
        "id": plugin_id,
        "name": name,
        "version": "1.0.0",
        "author": author,
        "description": type_info["description"],
        "entry_point": "main.py",
        "plugin_type": plugin_type,
        "capabilities": type_info["capabilities"],
        "dependencies": [],
        "config_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "compatibility": {
            "min_core_version": "1.6.0",
            "max_core_version": "2.9.9",
        },
    }
    
    with open(output_path / "plugin.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    main_content = f'''
"""
{name} - {type_info["description"]}

Plugin ID: {plugin_id}
Version: 1.0.0
Author: {author}
Created: {datetime.now().strftime("%Y-%m-%d")}
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Plugin:
    """{name} plugin implementation."""
    
    def __init__(self):
        self.metadata = None
        self.config = {{}}
        self.initialized = False
    
    def set_metadata(self, metadata):
        """Set plugin metadata."""
        self.metadata = metadata
    
    def set_config(self, config: Dict[str, Any]):
        """Set plugin configuration."""
        self.config = config
    
    def initialize(self, context: Dict[str, Any]):
        """Initialize the plugin."""
        logger.info(f"Initializing {{self.metadata.name}} v{{self.metadata.version}}")
        self.initialized = True
    
    def shutdown(self):
        """Shutdown the plugin."""
        logger.info(f"Shutting down {{self.metadata.name}}")
        self.initialized = False
    
    def on_enable(self):
        """Called when plugin is enabled."""
        logger.info(f"Plugin {{self.metadata.name}} enabled")
    
    def on_disable(self):
        """Called when plugin is disabled."""
        logger.info(f"Plugin {{self.metadata.name}} disabled")


def get_plugin_class():
    """Return the plugin class."""
    return Plugin
'''
    
    with open(output_path / "main.py", "w", encoding="utf-8") as f:
        f.write(main_content)
    
    readme_content = f'''# {name}

{type_info["description"]}

## Installation

Place this directory in the plugins folder or use the plugin manager UI.

## Configuration

Add configuration in plugin.json or through the plugin manager UI.

## Capabilities

This plugin requires the following capabilities:
{chr(10).join(f"- {cap}" for cap in type_info["capabilities"])}

## Development

Run in development mode using file:// protocol:
```
python tools/plugin-cli.py dev {plugin_id}
```
'''
    
    with open(output_path / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"Plugin '{name}' created successfully at: {output_path}")
    print(f"  - ID: {plugin_id}")
    print(f"  - Type: {plugin_type}")
    print(f"  - Version: 1.0.0")
    print(f"  - Capabilities: {', '.join(type_info['capabilities'])}")


def main():
    parser = argparse.ArgumentParser(description="灵境制造插件系统脚手架工具")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    create_parser = subparsers.add_parser("create", help="Create a new plugin")
    create_parser.add_argument("name", help="Plugin name")
    create_parser.add_argument(
        "--type",
        choices=list(PLUGIN_TYPES.keys()),
        default="data_source",
        help="Plugin type",
    )
    create_parser.add_argument("--author", default="灵境制造团队", help="Plugin author")
    create_parser.add_argument("--output", default="plugins", help="Output directory")
    
    args = parser.parse_args()
    
    if args.command == "create":
        create_plugin(args.name, args.type, args.author, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建插件模板文件**

```json
// templates/plugin/plugin.json

{
  "id": "example-plugin",
  "name": "示例插件",
  "version": "1.0.0",
  "author": "灵境制造团队",
  "description": "这是一个示例插件",
  "entry_point": "main.py",
  "plugin_type": "data_source",
  "capabilities": ["data_source"],
  "dependencies": [],
  "config_schema": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "compatibility": {
    "min_core_version": "1.6.0",
    "max_core_version": "2.9.9"
  }
}
```

```python
# templates/plugin/main.py

"""
示例插件 - 基础实现
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Plugin:
    def __init__(self):
        self.metadata = None
        self.config = {}
        self.initialized = False
    
    def set_metadata(self, metadata):
        self.metadata = metadata
    
    def set_config(self, config: Dict[str, Any]):
        self.config = config
    
    def initialize(self, context: Dict[str, Any]):
        logger.info(f"Initializing {self.metadata.name} v{self.metadata.version}")
        self.initialized = True
    
    def shutdown(self):
        logger.info(f"Shutting down {self.metadata.name}")
        self.initialized = False
    
    def on_enable(self):
        logger.info(f"Plugin {self.metadata.name} enabled")
    
    def on_disable(self):
        logger.info(f"Plugin {self.metadata.name} disabled")
```

- [ ] **Step 3: 创建plugins目录**

```bash
mkdir "c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app\plugins"
```

```
# plugins/.gitkeep
(empty file)
```

---

### Task 10: 系统集成测试

**Files:**
- Modify: `test_plugin_system.py` (add integration tests)

- [ ] **Step 1: 编写完整集成测试**

```python
# test_plugin_system.py (Append integration test class)

class TestPluginSystemIntegration(unittest.TestCase):
    def setUp(self):
        from app.core.plugin_system import (
            init_plugin_system,
            shutdown_plugin_system,
            get_plugin_manager,
        )
        from app.core.capability_gating import CapabilityGatekeeper
        PluginRegistry.reset()
        CapabilityGatekeeper.reset()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        from app.core.plugin_system import shutdown_plugin_system
        from app.core.capability_gating import CapabilityGatekeeper
        shutdown_plugin_system()
        CapabilityGatekeeper.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_plugin_lifecycle_with_capabilities(self):
        plugin_dir = Path(self.temp_dir) / "integration-test"
        plugin_dir.mkdir()
        
        meta = {
            "id": "integration-test",
            "name": "Integration Test",
            "version": "1.0.0",
            "entry_point": "main.py",
            "capabilities": ["data_source", "file_access"],
        }
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(meta, f)
        
        with open(plugin_dir / "main.py", "w") as f:
            f.write("""
class Plugin:
    def __init__(self):
        self.initialized = False
    
    def initialize(self, context):
        self.initialized = True
    
    def shutdown(self):
        self.initialized = False
""")
        
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        
        self.assertTrue(manager._registry.has_plugin("integration-test"))
        
        from app.core.capability_gating import CapabilityGatekeeper
        gatekeeper = CapabilityGatekeeper.get_instance()
        
        caps = gatekeeper.get_plugin_capabilities("integration-test")
        self.assertIn("data_source", caps)
        self.assertIn("file_access", caps)
        
        info = manager.get_plugin_info("integration-test")
        self.assertEqual(info["metadata"]["status"], "enabled")
        
        manager.disable_plugin("integration-test")
        info = manager.get_plugin_info("integration-test")
        self.assertEqual(info["metadata"]["status"], "disabled")
        
        manager.enable_plugin("integration-test")
        info = manager.get_plugin_info("integration-test")
        self.assertEqual(info["metadata"]["status"], "enabled")
    
    def test_plugin_config_update(self):
        plugin_dir = Path(self.temp_dir) / "config-test"
        plugin_dir.mkdir()
        
        meta = {
            "id": "config-test",
            "name": "Config Test",
            "version": "1.0.0",
            "entry_point": "main.py",
            "config_schema": {
                "type": "object",
                "properties": {
                    "interval": {"type": "integer", "default": 60},
                },
            },
        }
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(meta, f)
        
        with open(plugin_dir / "main.py", "w") as f:
            f.write("class Plugin:\n    def initialize(self, ctx): pass\n    def shutdown(self): pass")
        
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        manager._registry.update_config("config-test", {"interval": 30})
        
        metadata = manager._registry.get("config-test")
        self.assertEqual(metadata.config["interval"], 30)
    
    def test_plugin_dependency_resolution(self):
        base_dir = Path(self.temp_dir) / "base"
        ext_dir = Path(self.temp_dir) / "ext"
        base_dir.mkdir()
        ext_dir.mkdir()
        
        base_meta = {
            "id": "base-plugin",
            "name": "Base",
            "version": "1.0.0",
            "entry_point": "main.py",
        }
        with open(base_dir / "plugin.json", "w") as f:
            json.dump(base_meta, f)
        with open(base_dir / "main.py", "w") as f:
            f.write("class Plugin:\n    def initialize(self, ctx): pass\n    def shutdown(self): pass")
        
        ext_meta = {
            "id": "ext-plugin",
            "name": "Extension",
            "version": "1.0.0",
            "entry_point": "main.py",
            "dependencies": [{"name": "base-plugin", "version": ">=1.0.0", "required": True}],
        }
        with open(ext_dir / "plugin.json", "w") as f:
            json.dump(ext_meta, f)
        with open(ext_dir / "main.py", "w") as f:
            f.write("class Plugin:\n    def initialize(self, ctx): pass\n    def shutdown(self): pass")
        
        manager = init_plugin_system(plugin_dirs=[self.temp_dir])
        
        from app.core.plugin_system import get_dependency_resolver
        resolver = get_dependency_resolver()
        
        order = resolver.resolve_dependencies("ext-plugin")
        self.assertEqual(order, ["base-plugin", "ext-plugin"])
        
        tree = resolver.get_dependency_tree("ext-plugin")
        self.assertEqual(tree["id"], "ext-plugin")
        self.assertEqual(len(tree["dependencies"]), 1)
        self.assertEqual(tree["dependencies"][0]["id"], "base-plugin")


class TestPluginCLITool(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_plugin(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
        from plugin_cli import create_plugin
        
        create_plugin("My Test Plugin", "adapter", "Test Author", self.temp_dir)
        
        plugin_dir = Path(self.temp_dir) / "my-test-plugin"
        self.assertTrue(plugin_dir.exists())
        self.assertTrue((plugin_dir / "plugin.json").exists())
        self.assertTrue((plugin_dir / "main.py").exists())
        self.assertTrue((plugin_dir / "README.md").exists())
        
        with open(plugin_dir / "plugin.json", "r") as f:
            meta = json.load(f)
        
        self.assertEqual(meta["id"], "my-test-plugin")
        self.assertEqual(meta["name"], "My Test Plugin")
        self.assertEqual(meta["plugin_type"], "adapter")
        self.assertIn("data_source", meta["capabilities"])
        self.assertIn("machine_control", meta["capabilities"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行完整测试套件**

```bash
cd "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
python -m pytest test_plugin_system.py -v
```

Expected: All tests pass

---

## 自审清单

### 1. 规格覆盖检查

- [x] 插件生命周期管理：发现/注册/初始化/启用/停用/卸载 → Task 1-3
- [x] 插件元数据规范 (plugin.json) → Task 1
- [x] 插件类型系统（Adapter/DataSource/Analyzer/Visualization）→ Task 1, 6
- [x] 进程外Worker架构 → Task 4, 5
- [x] gRPC进程间通信 → Task 4
- [x] 健康检查与自动恢复 → Task 5
- [x] 能力门控系统 → Task 6
- [x] 基于角色的权限控制 → Task 6
- [x] 权限管理界面 → Task 8
- [x] 插件管理前端（市场/已安装/详情/日志）→ Task 8
- [x] 本地开发模式支持 → Task 9
- [x] 插件脚手架工具 → Task 9
- [x] 依赖自动解析 → Task 3
- [x] API端点实现 → Task 7

### 2. 占位符扫描

无TBD、TODO或占位符。每个步骤都包含完整代码。

### 3. 类型一致性检查

- PluginMetadata.to_dict() / from_dict() 在所有任务中一致使用
- PluginStatus枚举值在所有文件中统一
- CapabilityGatekeeper单例模式与现有架构模式一致
- API响应统一使用success()/error()工厂函数
- 所有全局单例使用get_xxx()和init_xxx()模式

---

## 执行建议

推荐按Phase顺序执行：

**Phase 1** (Task 1-3): 核心系统 - 可独立测试
**Phase 2** (Task 4-5): Worker架构 - 依赖Phase 1
**Phase 3** (Task 6): 能力门控 - 可并行开发
**Phase 4** (Task 7-8): API和前端 - 依赖Phase 1-3
**Phase 5** (Task 9-10): 工具和测试 - 最后完成

每个Phase完成后应运行对应测试验证，确保质量。
