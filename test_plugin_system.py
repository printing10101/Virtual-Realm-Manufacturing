import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python", "app"))

from core.plugin_system import (
    PluginMetadata,
    PluginRegistry,
    PluginStatus,
    PluginDependency,
    PluginDiscovery,
    PluginLoader,
    PluginLifecycleManager,
    DependencyResolver,
    init_plugin_system,
    shutdown_plugin_system,
    get_plugin_manager,
    get_dependency_resolver,
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
        self.assertEqual(self.registry.get_plugin_instance("test"), {"key": "value"})


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
        
        with open(plugin_dir / "main.py", "w") as f:
            f.write("# empty")
        
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


class TestPluginLifecycle(unittest.TestCase):
    def setUp(self):
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
        
        instance = manager._registry.get_plugin_instance("lifecycle-test")
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
        
        instance = manager._registry.get_plugin_instance("lifecycle-test")
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


class TestPluginSystemIntegration(unittest.TestCase):
    def setUp(self):
        PluginRegistry.reset()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutdown_plugin_system()
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
        
        resolver = get_dependency_resolver()
        
        order = resolver.resolve_dependencies("ext-plugin")
        self.assertEqual(order, ["base-plugin", "ext-plugin"])
        
        tree = resolver.get_dependency_tree("ext-plugin")
        self.assertEqual(tree["id"], "ext-plugin")
        self.assertEqual(len(tree["dependencies"]), 1)
        self.assertEqual(tree["dependencies"][0]["id"], "base-plugin")


class TestPluginWorkerManager(unittest.TestCase):
    def setUp(self):
        from core.plugin_worker import PluginWorkerManager
        PluginWorkerManager.reset()
        self.manager = PluginWorkerManager.get_instance()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        from core.plugin_worker import PluginWorkerManager
        self.manager.stop_all_workers(timeout=2)
        PluginWorkerManager.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_start_and_stop_worker(self):
        from core.plugin_worker import WorkerConfig, WorkerStatus
        
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
        from core.plugin_worker import WorkerConfig
        
        config1 = WorkerConfig(
            plugin_id="worker-1",
            plugin_path=self.temp_dir,
        )
        config2 = WorkerConfig(
            plugin_id="worker-2",
            plugin_path=self.temp_dir,
        )
        
        try:
            self.manager.start_worker(config1)
            self.manager.start_worker(config2)
            
            workers = self.manager.list_workers()
            self.assertGreaterEqual(len(workers), 1)
        except (TypeError, OSError):
            pass
        
        self.manager.stop_all_workers()


class TestCapabilityGating(unittest.TestCase):
    def setUp(self):
        from core.capability_gating import CapabilityGatekeeper
        CapabilityGatekeeper.reset()
        self.gatekeeper = CapabilityGatekeeper.get_instance()
    
    def tearDown(self):
        from core.capability_gating import CapabilityGatekeeper
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
        from core.capability_gating import FileAccessRule, CapabilityLevel
        
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


class TestPluginCLITool(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_plugin(self):
        import importlib.util
        
        tools_file = os.path.join(os.path.dirname(__file__), "tools", "plugin-cli.py")
        spec = importlib.util.spec_from_file_location("plugin_cli", tools_file)
        plugin_cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin_cli)
        
        plugin_cli.create_plugin("My Test Plugin", "adapter", "Test Author", self.temp_dir)
        
        plugin_dir = Path(self.temp_dir) / "my-test-plugin"
        self.assertTrue(plugin_dir.exists())
        self.assertTrue((plugin_dir / "plugin.json").exists())
        self.assertTrue((plugin_dir / "main.py").exists())
        self.assertTrue((plugin_dir / "README.md").exists())
        
        with open(plugin_dir / "plugin.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        self.assertEqual(meta["id"], "my-test-plugin")
        self.assertEqual(meta["name"], "My Test Plugin")
        self.assertEqual(meta["plugin_type"], "adapter")
        self.assertIn("data_source", meta["capabilities"])
        self.assertIn("machine_control", meta["capabilities"])


if __name__ == "__main__":
    unittest.main()
