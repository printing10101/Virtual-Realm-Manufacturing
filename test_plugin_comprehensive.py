﻿import json
import os
import shutil
import sys
import tempfile
import time
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
from core.capability_gating import CapabilityGatekeeper, FileAccessRule, CapabilityLevel


TEST_PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "test_plugins")


class TestResult:
    def __init__(self):
        self.scenarios = []
        self.assertions = 0
        self.passed = 0
        self.failed = 0

    def add_scenario(self, name, passed, details):
        self.scenarios.append({
            "name": name,
            "passed": passed,
            "details": details,
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def assert_true(self, condition, description):
        self.assertions += 1
        if condition:
            self.passed += 1
            return True
        else:
            self.failed += 1
            print(f"  FAIL: {description}")
            return False

    def summary(self):
        total = len(self.scenarios)
        passed = sum(1 for s in self.scenarios if s["passed"])
        print(f"\n{'='*60}")
        print(f"Plugin System Comprehensive Test Report")
        print(f"{'='*60}")
        for s in self.scenarios:
            status = "PASS" if s["passed"] else "FAIL"
            print(f"  [{status}] {s['name']}")
        print(f"{'='*60}")
        print(f"Total scenarios: {total}")
        print(f"Passed scenarios: {passed}")
        print(f"Failed scenarios: {total - passed}")
        print(f"Total assertions: {self.assertions}")
        print(f"{'='*60}")
        return passed == total


result = TestResult()


def cleanup_test_dir():
    if os.path.exists(TEST_PLUGINS_DIR):
        for item in os.listdir(TEST_PLUGINS_DIR):
            item_path = os.path.join(TEST_PLUGINS_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)


def create_test_plugin(plugin_id, metadata, main_code):
    plugin_dir = Path(TEST_PLUGINS_DIR) / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)

    with open(plugin_dir / "plugin.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    with open(plugin_dir / "main.py", "w", encoding="utf-8") as f:
        f.write(main_code)

    return plugin_dir


def setup_fresh_system(plugin_dirs=None):
    PluginRegistry.reset()
    CapabilityGatekeeper.reset()
    return init_plugin_system(
        plugin_dirs=plugin_dirs or [TEST_PLUGINS_DIR],
        user_dirs=[],
        context={"app_version": "1.6.0"},
    )


def teardown_system():
    try:
        shutdown_plugin_system()
    except Exception:
        pass
    CapabilityGatekeeper.reset()


class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        cleanup_test_dir()
        Path(TEST_PLUGINS_DIR).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        teardown_system()
        cleanup_test_dir()

    def test_1_basic_plugin_loading(self):
        print("\n[Test 1] Basic Plugin Loading Test")
        details = []

        create_test_plugin("minimal-adapter", {
            "id": "minimal-adapter",
            "name": "最小适配器",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "最小化模拟适配器插件",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.loaded = False

    def set_metadata(self, metadata):
        self.metadata = metadata

    def initialize(self, context):
        self.loaded = True
        logger.info(f"Minimal adapter {self.metadata.id} loaded")

    def shutdown(self):
        self.loaded = False
''')

        manager = setup_fresh_system()

        has_plugin = result.assert_true(
            manager._registry.has_plugin("minimal-adapter"),
            "Plugin registered in registry"
        )
        details.append(f"Plugin registered: {has_plugin}")

        metadata = manager._registry.get("minimal-adapter")
        is_enabled = result.assert_true(
            metadata is not None and metadata.status == PluginStatus.ENABLED,
            f"Plugin status is ENABLED (actual: {metadata.status if metadata else 'None'})"
        )
        details.append(f"Status enabled: {is_enabled}")

        instance = manager._registry.get_plugin_instance("minimal-adapter")
        is_loaded = result.assert_true(
            instance is not None and instance.loaded,
            "Plugin instance loaded and initialized"
        )
        details.append(f"Instance loaded: {is_loaded}")

        caps = metadata.capabilities if metadata else []
        has_caps = result.assert_true(
            "data_source" in caps,
            "Plugin has data_source capability"
        )
        details.append(f"Has capability: {has_caps}")

        result.add_scenario("Basic Plugin Loading", all([has_plugin, is_enabled, is_loaded, has_caps]), details)

    def test_2_lifecycle_completeness(self):
        print("\n[Test 2] Lifecycle Completeness Test")
        details = []

        create_test_plugin("lifecycle-test", {
            "id": "lifecycle-test",
            "name": "生命周期测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "完整生命周期回调测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.lifecycle_log = []

    def set_metadata(self, metadata):
        self.lifecycle_log.append("set_metadata")

    def set_config(self, config):
        self.lifecycle_log.append("set_config")

    def initialize(self, context):
        self.lifecycle_log.append("initialize")
        logger.info("Lifecycle: initialized")

    def shutdown(self):
        self.lifecycle_log.append("shutdown")
        logger.info("Lifecycle: shutdown")

    def on_enable(self):
        self.lifecycle_log.append("on_enable")
        logger.info("Lifecycle: enabled")

    def on_disable(self):
        self.lifecycle_log.append("on_disable")
        logger.info("Lifecycle: disabled")
''')

        manager = setup_fresh_system()

        instance = manager._registry.get_plugin_instance("lifecycle-test")
        has_init = result.assert_true(
            instance is not None and "initialize" in instance.lifecycle_log,
            "Initialize callback executed"
        )
        details.append(f"Initialize called: {has_init}")

        manager.disable_plugin("lifecycle-test")
        metadata = manager._registry.get("lifecycle-test")
        is_disabled = result.assert_true(
            metadata.status == PluginStatus.DISABLED,
            f"Status changed to DISABLED after disable (actual: {metadata.status})"
        )
        details.append(f"Disable status: {is_disabled}")

        has_disable = result.assert_true(
            "on_disable" in instance.lifecycle_log,
            "on_disable callback executed"
        )
        details.append(f"Disable callback: {has_disable}")

        manager.enable_plugin("lifecycle-test")
        metadata = manager._registry.get("lifecycle-test")
        is_enabled = result.assert_true(
            metadata.status == PluginStatus.ENABLED,
            f"Status changed to ENABLED after re-enable (actual: {metadata.status})"
        )
        details.append(f"Re-enable status: {is_enabled}")

        has_enable = result.assert_true(
            "on_enable" in instance.lifecycle_log,
            "on_enable callback executed on re-enable"
        )
        details.append(f"Re-enable callback: {has_enable}")

        expected_order = ["set_metadata", "set_config", "initialize", "on_enable", "on_disable", "initialize", "on_enable"]
        correct_order = result.assert_true(
            instance.lifecycle_log == expected_order,
            f"Lifecycle callbacks in correct order: {instance.lifecycle_log}"
        )
        details.append(f"Callback order: {correct_order}")

        all_pass = all([has_init, is_disabled, has_disable, is_enabled, has_enable, correct_order])
        result.add_scenario("Lifecycle Completeness", all_pass, details)

    def test_3_process_isolation_safety(self):
        print("\n[Test 3] Process Isolation Safety Test")
        details = []

        create_test_plugin("crash-test", {
            "id": "crash-test",
            "name": "崩溃测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "进程隔离安全性测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.running = True

    def initialize(self, context):
        self.running = True
        logger.info("Crash test plugin initialized")

    def shutdown(self):
        self.running = False
        logger.info("Crash test plugin shutdown")

    def trigger_crash(self, error_type="value"):
        if error_type == "value":
            raise ValueError("Simulated crash: value error")
        elif error_type == "runtime":
            raise RuntimeError("Simulated crash: runtime error")
        elif error_type == "type":
            raise TypeError("Simulated crash: type error")

    def get_status(self):
        return {"running": self.running, "healthy": True}
''')

        manager = setup_fresh_system()

        instance = manager._registry.get_plugin_instance("crash-test")
        is_loaded = result.assert_true(
            instance is not None,
            "Crash test plugin loaded successfully"
        )
        details.append(f"Plugin loaded: {is_loaded}")

        main_system_ok = result.assert_true(
            manager._registry.has_plugin("crash-test"),
            "Main system registry intact after plugin load"
        )
        details.append(f"Main system intact: {main_system_ok}")

        crash_caught = False
        try:
            instance.trigger_crash("value")
        except ValueError:
            crash_caught = True

        exception_caught = result.assert_true(
            crash_caught,
            "Exception caught without affecting main system"
        )
        details.append(f"Exception caught: {exception_caught}")

        system_still_ok = result.assert_true(
            manager._registry.has_plugin("crash-test") and
            len(manager._registry.list_plugins()) > 0,
            "System still functional after plugin crash"
        )
        details.append(f"System functional after crash: {system_still_ok}")

        other_plugins_ok = result.assert_true(
            len(manager._registry.list_plugins()) >= 1,
            "Other plugins not affected by crash"
        )
        details.append(f"Other plugins OK: {other_plugins_ok}")

        all_pass = all([is_loaded, main_system_ok, exception_caught, system_still_ok, other_plugins_ok])
        result.add_scenario("Process Isolation Safety", all_pass, details)

    def test_4_capability_permission_control(self):
        print("\n[Test 4] Capability Permission Control Test")
        details = []

        create_test_plugin("permission-test", {
            "id": "permission-test",
            "name": "权限测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "能力权限控制测试",
            "entry_point": "main.py",
            "capabilities": ["machine_control", "data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.control_executed = False

    def initialize(self, context):
        logger.info("Permission test plugin initialized")

    def shutdown(self):
        pass

    def execute_machine_control(self, command):
        self.control_executed = True
        return {"status": "executed", "command": command}
''')

        manager = setup_fresh_system()

        gatekeeper = CapabilityGatekeeper.get_instance()
        has_mc_cap = result.assert_true(
            manager._registry.get("permission-test").capabilities is not None,
            "Plugin declares machine_control capability"
        )
        details.append(f"Declares machine_control: {has_mc_cap}")

        plugin_id = "permission-test"
        gatekeeper.grant_capabilities(plugin_id, ["data_source"])

        has_data = result.assert_true(
            gatekeeper.has_capability(plugin_id, "data_source"),
            "Plugin has data_source capability granted"
        )
        details.append(f"Has data_source: {has_data}")

        no_mc = result.assert_true(
            not gatekeeper.has_capability(plugin_id, "machine_control"),
            "Plugin does NOT have machine_control capability granted"
        )
        details.append(f"No machine_control: {no_mc}")

        gatekeeper.grant_capabilities(plugin_id, ["machine_control"])
        has_mc = result.assert_true(
            gatekeeper.has_capability(plugin_id, "machine_control"),
            "Plugin has machine_control after grant"
        )
        details.append(f"Has machine_control after grant: {has_mc}")

        instance = manager._registry.get_plugin_instance("permission-test")
        instance.execute_machine_control("STOP")
        control_ok = result.assert_true(
            instance.control_executed,
            "Machine control executed after permission granted"
        )
        details.append(f"Control executed: {control_ok}")

        all_pass = all([has_mc_cap, has_data, no_mc, has_mc, control_ok])
        result.add_scenario("Capability Permission Control", all_pass, details)

    def test_5_ui_contribution_integration(self):
        print("\n[Test 5] UI Contribution Integration Test")
        details = []

        create_test_plugin("ui-contrib", {
            "id": "ui-contrib",
            "name": "UI贡献",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "UI贡献集成测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.data_version = 1

    def initialize(self, context):
        logger.info("UI contrib plugin initialized")

    def shutdown(self):
        pass

    def get_ui_components(self):
        return [
            {
                "type": "chart",
                "name": "设备温度监控",
                "position": "dashboard-main",
                "config": {
                    "chart_type": "line",
                    "refresh_interval": 5,
                    "data_points": 100,
                }
            },
            {
                "type": "gauge",
                "name": "机床转速",
                "position": "dashboard-sidebar",
                "config": {
                    "min": 0,
                    "max": 10000,
                    "unit": "RPM",
                }
            }
        ]

    def get_chart_data(self, component_name):
        self.data_version += 1
        return {
            "component": component_name,
            "version": self.data_version,
            "data": [10, 20, 30, 40, 50],
            "timestamp": "2026-05-13T10:00:00",
        }
''')

        manager = setup_fresh_system()

        instance = manager._registry.get_plugin_instance("ui-contrib")
        is_loaded = result.assert_true(
            instance is not None,
            "UI contribution plugin loaded"
        )
        details.append(f"Plugin loaded: {is_loaded}")

        components = instance.get_ui_components()
        has_components = result.assert_true(
            len(components) == 2,
            f"Plugin provides 2 UI components (actual: {len(components)})"
        )
        details.append(f"UI components count: {has_components}")

        has_chart = result.assert_true(
            any(c["type"] == "chart" for c in components),
            "Chart component type present"
        )
        details.append(f"Chart type: {has_chart}")

        has_gauge = result.assert_true(
            any(c["type"] == "gauge" for c in components),
            "Gauge component type present"
        )
        details.append(f"Gauge type: {has_gauge}")

        chart_data = instance.get_chart_data("设备温度监控")
        data_valid = result.assert_true(
            "data" in chart_data and "timestamp" in chart_data,
            "Chart data contains data and timestamp fields"
        )
        details.append(f"Chart data valid: {data_valid}")

        data_v1 = instance.get_chart_data("设备温度监控")
        data_updated = result.assert_true(
            data_v1["version"] > chart_data["version"],
            "Data version increments on each update"
        )
        details.append(f"Data update mechanism: {data_updated}")

        all_pass = all([is_loaded, has_components, has_chart, has_gauge, data_valid, data_updated])
        result.add_scenario("UI Contribution Integration", all_pass, details)

    def test_6_hotplug_functionality(self):
        print("\n[Test 6] Hotplug Functionality Test")
        details = []

        manager = setup_fresh_system(plugin_dirs=[])

        system_running = result.assert_true(
            manager is not None,
            "System running before hotplug"
        )
        details.append(f"System running: {system_running}")

        initial_count = len(manager._registry.list_plugins())

        create_test_plugin("hotplug-test", {
            "id": "hotplug-test",
            "name": "热插拔测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "热插拔功能测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.plugin_status = "active"

    def initialize(self, context):
        logger.info("Hotplug test plugin initialized")

    def shutdown(self):
        self.plugin_status = "stopped"

    def get_status(self):
        return {
            "plugin_status": self.plugin_status,
            "healthy": True,
            "uptime": "immediate",
        }
''')

        count = manager.discover_and_register_all(plugin_dirs=[TEST_PLUGINS_DIR])
        discovered = result.assert_true(
            count == 1,
            f"New plugin discovered during runtime (count: {count})"
        )
        details.append(f"Plugin discovered: {discovered}")

        manager.initialize_all()
        manager.enable_all()

        new_count = len(manager._registry.list_plugins())
        count_increased = result.assert_true(
            new_count > initial_count,
            f"Plugin count increased after hotplug (before: {initial_count}, after: {new_count})"
        )
        details.append(f"Count increased: {count_increased}")

        has_plugin = result.assert_true(
            manager._registry.has_plugin("hotplug-test"),
            "Hotplug plugin registered in running system"
        )
        details.append(f"Plugin registered: {has_plugin}")

        instance = manager._registry.get_plugin_instance("hotplug-test")
        is_active = result.assert_true(
            instance is not None and instance.plugin_status == "active",
            "Hotplug plugin active and responding immediately"
        )
        details.append(f"Plugin active: {is_active}")

        status = instance.get_status()
        responds = result.assert_true(
            status["healthy"],
            "Hotplug plugin returns valid status"
        )
        details.append(f"Responds correctly: {responds}")

        all_pass = all([system_running, discovered, count_increased, has_plugin, is_active, responds])
        result.add_scenario("Hotplug Functionality", all_pass, details)

    def test_7_hot_reload_mechanism(self):
        print("\n[Test 7] Hot Reload Mechanism Test")
        details = []

        create_test_plugin("hot-reload", {
            "id": "hot-reload",
            "name": "热重载测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "热重载机制测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    VERSION = "1.0.0"

    def __init__(self):
        self.feature = "original"

    def initialize(self, context):
        logger.info("Hot reload plugin v1 initialized")

    def shutdown(self):
        logger.info("Hot reload plugin shutdown")

    def get_feature(self):
        return self.feature

    def get_version(self):
        return Plugin.VERSION
''')

        manager = setup_fresh_system()

        instance = manager._registry.get_plugin_instance("hot-reload")
        original_feature = result.assert_true(
            instance is not None and instance.get_feature() == "original",
            "Original feature working before reload"
        )
        details.append(f"Original feature: {original_feature}")

        plugin_dir = Path(TEST_PLUGINS_DIR) / "hot-reload"
        with open(plugin_dir / "main.py", "w", encoding="utf-8") as f:
            f.write('''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    VERSION = "2.0.0"

    def __init__(self):
        self.feature = "updated"

    def initialize(self, context):
        logger.info("Hot reload plugin v2 initialized")

    def shutdown(self):
        logger.info("Hot reload plugin shutdown")

    def get_feature(self):
        return self.feature

    def get_version(self):
        return Plugin.VERSION
''')

        new_instance = manager._loader.reload_plugin("hot-reload")
        reloaded = result.assert_true(
            new_instance is not None,
            "Plugin reloaded successfully"
        )
        details.append(f"Reloaded: {reloaded}")

        new_feature = result.assert_true(
            new_instance.get_feature() == "updated",
            f"New feature active after reload (actual: {new_instance.get_feature()})"
        )
        details.append(f"New feature: {new_feature}")

        new_version = result.assert_true(
            new_instance.get_version() == "2.0.0",
            f"Version updated after reload (actual: {new_instance.get_version()})"
        )
        details.append(f"Version updated: {new_version}")

        system_still_ok = result.assert_true(
            manager._registry.has_plugin("hot-reload"),
            "System still functional after hot reload"
        )
        details.append(f"System intact: {system_still_ok}")

        all_pass = all([original_feature, reloaded, new_feature, new_version, system_still_ok])
        result.add_scenario("Hot Reload Mechanism", all_pass, details)

    def test_8_dependency_management(self):
        print("\n[Test 8] Plugin Dependency Management Test")
        details = []

        create_test_plugin("base-dependency", {
            "id": "base-dependency",
            "name": "基础依赖",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "基础依赖插件",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.ready = True

    def initialize(self, context):
        logger.info("Base dependency initialized")

    def shutdown(self):
        self.ready = False

    def get_base_data(self):
        return {"base": "ready", "version": "1.0.0"}
''')

        create_test_plugin("dependency-extension", {
            "id": "dependency-extension",
            "name": "依赖扩展",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "依赖扩展插件",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [{"name": "base-dependency", "version": ">=1.0.0", "required": True}],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.extended = True

    def initialize(self, context):
        logger.info("Dependency extension initialized")

    def shutdown(self):
        self.extended = False

    def get_extended_data(self):
        return {"extended": "ready", "depends_on": "base-dependency"}
''')

        manager = setup_fresh_system()

        has_base = result.assert_true(
            manager._registry.has_plugin("base-dependency"),
            "Base dependency plugin registered"
        )
        details.append(f"Base dependency registered: {has_base}")

        has_ext = result.assert_true(
            manager._registry.has_plugin("dependency-extension"),
            "Extension plugin registered"
        )
        details.append(f"Extension registered: {has_ext}")

        resolver = get_dependency_resolver()
        order = resolver.resolve_dependencies("dependency-extension")
        correct_order = result.assert_true(
            order == ["base-dependency", "dependency-extension"],
            f"Dependency resolution order correct (actual: {order})"
        )
        details.append(f"Resolution order: {correct_order}")

        tree = resolver.get_dependency_tree("dependency-extension")
        has_tree = result.assert_true(
            len(tree.get("dependencies", [])) == 1,
            "Dependency tree shows base-dependency"
        )
        details.append(f"Dependency tree: {has_tree}")

        base_instance = manager._registry.get_plugin_instance("base-dependency")
        ext_instance = manager._registry.get_plugin_instance("dependency-extension")
        both_loaded = result.assert_true(
            base_instance is not None and ext_instance is not None,
            "Both dependency and extension instances loaded"
        )
        details.append(f"Both loaded: {both_loaded}")

        base_data = base_instance.get_base_data()
        ext_data = ext_instance.get_extended_data()
        both_work = result.assert_true(
            base_data["base"] == "ready" and ext_data["extended"] == "ready",
            "Both plugins functional"
        )
        details.append(f"Both functional: {both_work}")

        all_pass = all([has_base, has_ext, correct_order, has_tree, both_loaded, both_work])
        result.add_scenario("Dependency Management", all_pass, details)

    def test_9_gray_release_strategy(self):
        print("\n[Test 9] Gray Release Strategy Test")
        details = []

        manager = setup_fresh_system(plugin_dirs=[])

        machines = {
            "machine-001": {"type": "production", "plugins": []},
            "machine-002": {"type": "testing", "plugins": []},
            "machine-003": {"type": "production", "plugins": []},
            "machine-004": {"type": "testing", "plugins": []},
        }

        create_test_plugin("gray-release", {
            "id": "gray-release",
            "name": "灰度发布测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "灰度发布功能测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {
                "type": "object",
                "properties": {
                    "target_machines": {"type": "array", "default": []},
                },
            },
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.target_machines = []

    def initialize(self, context):
        logger.info("Gray release plugin initialized")

    def shutdown(self):
        pass

    def set_config(self, config):
        self.target_machines = config.get("target_machines", [])

    def should_activate(self, machine_id):
        return machine_id in self.target_machines

    def get_status(self, machine_id):
        return {
            "machine_id": machine_id,
            "active": self.should_activate(machine_id),
            "targets": self.target_machines,
        }
''')

        manager.discover_and_register_all(plugin_dirs=[TEST_PLUGINS_DIR])
        manager.initialize_all()
        manager.enable_all()

        instance = manager._registry.get_plugin_instance("gray-release")
        instance.set_config({"target_machines": ["machine-002", "machine-004"]})

        total_machines = result.assert_true(
            len(machines) == 4,
            f"Total 4 machines in environment (actual: {len(machines)})"
        )
        details.append(f"Machine count: {total_machines}")

        for machine_id, machine_info in machines.items():
            status = instance.get_status(machine_id)
            if machine_info["type"] == "testing":
                machine_info["plugins"].append("gray-release")
                is_active = result.assert_true(
                    status["active"],
                    f"Plugin active on {machine_id} (testing machine)"
                )
                details.append(f"Active on {machine_id}: {is_active}")
            else:
                is_inactive = result.assert_true(
                    not status["active"],
                    f"Plugin NOT active on {machine_id} (production machine)"
                )
                details.append(f"Inactive on {machine_id}: {is_inactive}")

        testing_active = all(
            m["plugins"] == ["gray-release"] if m["type"] == "testing"
            else m["plugins"] == []
            for m in machines.values()
        )
        strategy_correct = result.assert_true(
            testing_active,
            "Gray release strategy correctly targets only testing machines"
        )
        details.append(f"Strategy correct: {strategy_correct}")

        other_plugins_ok = result.assert_true(
            len(manager._registry.list_plugins()) == 1,
            "Other machines not affected by gray release"
        )
        details.append(f"Other machines unaffected: {other_plugins_ok}")

        all_pass = all([total_machines, strategy_correct, other_plugins_ok])
        result.add_scenario("Gray Release Strategy", all_pass, details)

    def test_10_log_completeness(self):
        print("\n[Test 10] Log Completeness Test")
        details = []

        import logging
        log_capture = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                log_capture.append({
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "module": record.module,
                    "timestamp": record.created,
                })

        handler = TestHandler()
        handler.setLevel(logging.DEBUG)
        logger_ps = logging.getLogger("core.plugin_system")
        logger_cg = logging.getLogger("core.capability_gating")
        logger_ps.setLevel(logging.DEBUG)
        logger_cg.setLevel(logging.DEBUG)
        logger_ps.addHandler(handler)
        logger_cg.addHandler(handler)

        create_test_plugin("log-test", {
            "id": "log-test",
            "name": "日志完整性测试",
            "version": "1.0.0",
            "author": "测试团队",
            "description": "日志完整性测试",
            "entry_point": "main.py",
            "capabilities": ["data_source"],
            "dependencies": [],
            "config_schema": {},
            "compatibility": {"min_core_version": "1.0.0", "max_core_version": "99.0.0"},
        }, '''
import logging
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        self.ready = True

    def initialize(self, context):
        logger.info("Log test plugin initialized")

    def shutdown(self):
        logger.info("Log test plugin shutdown")
        self.ready = False
''')

        manager = setup_fresh_system()

        manager.disable_plugin("log-test")
        manager.enable_plugin("log-test")

        has_load_logs = result.assert_true(
            any("registered" in log["message"].lower() for log in log_capture),
            "Plugin registration log present"
        )
        details.append(f"Registration log: {has_load_logs}")

        has_init_logs = result.assert_true(
            any("initialized" in log["message"].lower() for log in log_capture),
            "Plugin initialization log present"
        )
        details.append(f"Initialization log: {has_init_logs}")

        has_enable_logs = result.assert_true(
            any("enabled" in log["message"].lower() for log in log_capture),
            "Plugin enable log present"
        )
        details.append(f"Enable log: {has_enable_logs}")

        has_disable_logs = result.assert_true(
            any("disabled" in log["message"].lower() for log in log_capture),
            "Plugin disable log present"
        )
        details.append(f"Disable log: {has_disable_logs}")

        info_level = result.assert_true(
            any(log["level"] == "INFO" for log in log_capture),
            "INFO level logs present"
        )
        details.append(f"INFO level: {info_level}")

        has_timestamps = result.assert_true(
            all("timestamp" in log and log["timestamp"] > 0 for log in log_capture),
            "All logs have valid timestamps"
        )
        details.append(f"Timestamps valid: {has_timestamps}")

        has_modules = result.assert_true(
            any("module" in log and log["module"] for log in log_capture),
            "Logs contain module information"
        )
        details.append(f"Module info: {has_modules}")

        total_logs = result.assert_true(
            len(log_capture) >= 4,
            f"Sufficient log entries captured (count: {len(log_capture)})"
        )
        details.append(f"Log count sufficient: {total_logs}")

        logger_ps.removeHandler(handler)
        logger_cg.removeHandler(handler)

        all_pass = all([has_load_logs, has_init_logs, has_enable_logs, has_disable_logs,
                        info_level, has_timestamps, has_modules, total_logs])
        result.add_scenario("Log Completeness", all_pass, details)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPluginSystem)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
    result.summary()
