"""
Runtime Skill Injection System - Paperclip-inspired Design

Implements dynamic skill loading and injection for AI agents with:
- Three-tier hierarchical architecture (Global → Project → Agent)
- YAML-frontmatter Markdown skill files
- Hot-reload via file watcher
- Multi-version coexistence and rollback
- Skill context merging for agent guidance
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import time
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


DEFAULT_SKILLS_BASE = str(Path(os.environ.get(
    "LNN_SKILLS_DIR",
    str(Path(__file__).resolve().parents[3] / ".trae" / "skills")
)))


class SkillLevel(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    AGENT = "agent"


class SkillPriority(int, Enum):
    """技能优先级：数字越小优先级越高"""
    GLOBAL = 100
    PROJECT = 50
    AGENT = 10


PRIORITY_MAP = {
    SkillLevel.GLOBAL: SkillPriority.GLOBAL,
    SkillLevel.PROJECT: SkillPriority.PROJECT,
    SkillLevel.AGENT: SkillPriority.AGENT,
}


@dataclass
class SkillVersion:
    version: str
    content_hash: str
    file_path: str
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillMetadata:
    skill_id: str
    name: str
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    level: SkillLevel = SkillLevel.GLOBAL
    priority: SkillPriority = SkillPriority.GLOBAL
    applicable_tasks: List[str] = field(default_factory=list)
    required_context: List[str] = field(default_factory=list)
    author: str = ""
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[str] = None
    ratings: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "level": self.level.value,
            "priority": self.priority.value,
            "applicable_tasks": self.applicable_tasks,
            "required_context": self.required_context,
            "author": self.author,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "avg_rating": round(sum(self.ratings) / len(self.ratings), 2) if self.ratings else None,
            "rating_count": len(self.ratings),
        }

    def applicable_to(self, task_type: str) -> bool:
        if not self.applicable_tasks:
            return True
        return task_type in self.applicable_tasks or "*" in self.applicable_tasks

    def contexts_satisfied(self, available_context: Set[str]) -> Tuple[bool, List[str]]:
        if not self.required_context:
            return True, []
        missing = [c for c in self.required_context if c not in available_context]
        return len(missing) == 0, missing


@dataclass
class Skill:
    metadata: SkillMetadata
    raw_content: str = ""
    body: str = ""
    code_blocks: List[Tuple[str, str]] = field(default_factory=list)
    versions: Dict[str, SkillVersion] = field(default_factory=dict)
    executor: Optional[Callable] = None
    context: Dict[str, Any] = field(default_factory=dict)
    is_loaded: bool = False
    is_active: bool = True
    loaded_at: float = field(default_factory=time.time)

    @property
    def current_version(self) -> Optional[SkillVersion]:
        if not self.versions:
            return None
        sorted_versions = sorted(
            self.versions.items(),
            key=lambda x: [int(p) for p in x[0].split(".")]
        )
        return sorted_versions[-1][1]

    def execute(self, **kwargs) -> Any:
        if not self.is_loaded or self.executor is None:
            raise RuntimeError(f"Skill '{self.metadata.name}' is not loaded")
        if not self.is_active:
            raise RuntimeError(f"Skill '{self.metadata.name}' is not active")
        merged_kwargs = {**self.context, **kwargs}
        return self.executor(**merged_kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "is_loaded": self.is_loaded,
            "is_active": self.is_active,
            "loaded_at": self.loaded_at,
            "context": self.context,
            "versions": {v: vs.version for v, vs in self.versions.items()},
        }


class MarkdownSkillParser:
    YAML_FRONTMATTER_PATTERN = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n",
        re.DOTALL
    )
    CODE_BLOCK_PATTERN = re.compile(
        r"```(\w+)\s*\n(.*?)\n```",
        re.DOTALL
    )
    HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)

    @classmethod
    def parse(cls, file_path: str) -> Optional[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            logger.warning("Skill file not found: %s", file_path)
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error("Failed to read skill file %s: %s", file_path, e)
            return None

        result: Dict[str, Any] = {
            "metadata": {},
            "code_blocks": [],
            "body": "",
            "raw_content": content,
        }

        fm_match = cls.YAML_FRONTMATTER_PATTERN.match(content)
        if fm_match:
            result["metadata"] = cls._parse_frontmatter(fm_match.group(1))
            body_start = fm_match.end()
        else:
            legacy_meta = cls._parse_legacy_metadata(content)
            if legacy_meta:
                result["metadata"] = legacy_meta
                body_start = cls._find_body_start(content)
            else:
                body_start = 0

        result["body"] = content[body_start:].strip()
        result["code_blocks"] = cls.CODE_BLOCK_PATTERN.findall(content)

        if not result["metadata"].get("skill_id"):
            result["metadata"]["skill_id"] = path.stem
        if not result["metadata"].get("name"):
            result["metadata"]["name"] = result["metadata"]["skill_id"]

        return result

    @classmethod
    def _parse_frontmatter(cls, fm_text: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        for line in fm_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    items = value[1:-1].split(",")
                    metadata[key] = [item.strip().strip("\"'") for item in items if item.strip()]
                elif value.lower() == "true":
                    metadata[key] = True
                elif value.lower() == "false":
                    metadata[key] = False
                elif value == "":
                    metadata[key] = None
                else:
                    try:
                        metadata[key] = int(value)
                    except ValueError:
                        try:
                            metadata[key] = float(value)
                        except ValueError:
                            metadata[key] = value.strip("\"'")
        return metadata

    @classmethod
    def _parse_legacy_metadata(cls, content: str) -> Optional[Dict[str, Any]]:
        table_pattern = re.compile(r"\|\s*字段\s*\|\s*值\s*\|\s*\n\|[-| ]+\|\s*\n((?:\|.*\|\s*\n?)+)")
        match = table_pattern.search(content)
        if not match:
            return None

        metadata: Dict[str, Any] = {}
        field_map = {
            "技能名称": "display_name",
            "英文名称": "name",
            "适用场景": "applicable_tasks_text",
            "前置条件": "prerequisites",
            "API端点": "api_endpoints",
            "依赖模块": "dependencies_text",
        }

        for row in match.group(1).strip().split("\n"):
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if len(cells) >= 2:
                field = field_map.get(cells[0], cells[0])
                metadata[field] = cells[1]

        if "applicable_tasks_text" in metadata:
            text = metadata.pop("applicable_tasks_text")
            metadata["applicable_tasks"] = cls._extract_task_types(text)
        if "dependencies_text" in metadata:
            metadata["dependencies"] = [
                d.strip() for d in metadata.pop("dependencies_text").split("、")
            ]

        return metadata

    @classmethod
    def _extract_task_types(cls, text: str) -> List[str]:
        type_keywords = {
            "预测": "prediction",
            "训练": "training",
            "分析": "analysis",
            "优化": "optimization",
            "分类": "classification",
            "检测": "detection",
            "振动": "vibration_analysis",
            "磨损": "wear_analysis",
            "寿命": "rul_prediction",
        }
        tasks = []
        for cn, en in type_keywords.items():
            if cn in text:
                tasks.append(en)
        return tasks if tasks else ["*"]

    @classmethod
    def _find_body_start(cls, content: str) -> int:
        table_match = re.search(r"\n---\s*\n", content)
        if table_match:
            return table_match.end()
        heading_match = re.search(r"^#+\s", content, re.MULTILINE)
        if heading_match:
            return heading_match.start()
        return 0


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._skill_order: List[str] = []
        self._lock = threading.RLock()

    def register(self, skill: Skill) -> None:
        with self._lock:
            self._skills[skill.metadata.skill_id] = skill
            if skill.metadata.skill_id not in self._skill_order:
                self._skill_order.append(skill.metadata.skill_id)
        logger.info(
            "Skill registered: %s (level=%s, version=%s)",
            skill.metadata.name, skill.metadata.level.value, skill.metadata.version,
        )

    def get(self, skill_id: str) -> Optional[Skill]:
        with self._lock:
            return self._skills.get(skill_id)

    def get_by_level(self, level: SkillLevel) -> List[Skill]:
        with self._lock:
            return [
                s for s in self._skills.values()
                if s.metadata.level == level and s.is_active
            ]

    def get_by_task(self, task_type: str) -> List[Skill]:
        with self._lock:
            return [
                s for s in self._skills.values()
                if s.is_active and s.metadata.applicable_to(task_type)
            ]

    def list_all(self) -> List[Skill]:
        with self._lock:
            return list(self._skills.values())

    def list_all_metadata(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.metadata.to_dict() for s in self._skills.values()]

    def activate(self, skill_id: str) -> None:
        with self._lock:
            skill = self._skills.get(skill_id)
            if skill:
                skill.is_active = True
                logger.info("Skill activated: %s", skill_id)

    def deactivate(self, skill_id: str) -> None:
        with self._lock:
            skill = self._skills.get(skill_id)
            if skill:
                skill.is_active = False
                logger.info("Skill deactivated: %s", skill_id)

    def remove(self, skill_id: str) -> bool:
        with self._lock:
            if skill_id in self._skills:
                del self._skills[skill_id]
                if skill_id in self._skill_order:
                    self._skill_order.remove(skill_id)
                return True
            return False

    def clear_level(self, level: SkillLevel) -> int:
        with self._lock:
            to_remove = [
                sid for sid, s in self._skills.items()
                if s.metadata.level == level
            ]
            for sid in to_remove:
                del self._skills[sid]
                if sid in self._skill_order:
                    self._skill_order.remove(sid)
            return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            skills = list(self._skills.values())
            return {
                "total": len(skills),
                "active": sum(1 for s in skills if s.is_active),
                "by_level": {
                    level.value: sum(1 for s in skills if s.metadata.level == level)
                    for level in SkillLevel
                },
                "loaded": sum(1 for s in skills if s.is_loaded),
            }


class SkillFileWatcher:
    def __init__(self, skills_dir: str, loader: "SkillLoader", poll_interval: float = 2.0):
        self.skills_dir = skills_dir
        self.loader = loader
        self.poll_interval = poll_interval
        self._mtime_cache: Dict[str, float] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("SkillFileWatcher started (poll_interval=%.1fs)", self.poll_interval)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("SkillFileWatcher stopped")

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._scan_changes()
            except Exception as e:
                logger.warning("SkillFileWatcher scan error: %s", e)
            self._stop_event.wait(self.poll_interval)

    def _scan_changes(self) -> None:
        current_files: Dict[str, float] = {}

        for root, dirs, files in os.walk(self.skills_dir):
            for f in files:
                if f.endswith(".md"):
                    fp = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(fp)
                        current_files[fp] = mtime
                    except OSError:
                        pass

        for fp, mtime in current_files.items():
            old_mtime = self._mtime_cache.get(fp)
            if old_mtime is None:
                logger.info("New skill file detected: %s", fp)
                self._handle_file_event(fp, "created")
            elif mtime > old_mtime:
                logger.info("Skill file modified: %s", fp)
                self._handle_file_event(fp, "modified")

        for fp in self._mtime_cache:
            if fp not in current_files:
                logger.info("Skill file removed: %s", fp)
                self._handle_file_event(fp, "deleted")

        self._mtime_cache = current_files

    def _handle_file_event(self, file_path: str, event: str) -> None:
        try:
            if event == "deleted":
                skill_id = Path(file_path).stem
                self.loader.registry.remove(skill_id)
                logger.info("Skill removed via hot-reload: %s", skill_id)
            else:
                level = self._infer_level(file_path)
                skill = self.loader._load_skill_from_file(file_path, level)
                if skill:
                    self.loader.registry.register(skill)
        except Exception as e:
            logger.error("Failed to handle file event %s for %s: %s", event, file_path, e)

    def _infer_level(self, file_path: str) -> SkillLevel:
        rel = os.path.relpath(file_path, self.skills_dir).replace("\\", "/")
        if rel.startswith("global/"):
            return SkillLevel.GLOBAL
        elif rel.startswith("projects/") or rel.startswith("project/"):
            return SkillLevel.PROJECT
        elif rel.startswith("agents/") or rel.startswith("agent/"):
            return SkillLevel.AGENT
        return SkillLevel.GLOBAL


class SkillLoader:
    """技能加载器 - 三级分层架构 + 热更新 + 版本控制"""

    def __init__(self, skills_base_dir: Optional[str] = None):
        if skills_base_dir is None:
            skills_base_dir = DEFAULT_SKILLS_BASE

        self.skills_base = skills_base_dir
        self.registry = SkillRegistry()
        self._context: Dict[str, Any] = {}
        self._watcher: Optional[SkillFileWatcher] = None

        self._ensure_directory_structure()
        self._load_all_skills()
        self._start_watcher()

        logger.info("SkillLoader initialized: skills_base=%s", skills_base_dir)

    def _ensure_directory_structure(self) -> None:
        for subdir in ["global", "projects", "agents"]:
            os.makedirs(os.path.join(self.skills_base, subdir), exist_ok=True)

    def _start_watcher(self) -> None:
        self._watcher = SkillFileWatcher(self.skills_base, self, poll_interval=2.0)
        self._watcher.start()

    def stop_watcher(self) -> None:
        if self._watcher:
            self._watcher.stop()

    def _load_all_skills(self) -> None:
        self.registry.clear_level(SkillLevel.GLOBAL)
        self.registry.clear_level(SkillLevel.PROJECT)
        self.registry.clear_level(SkillLevel.AGENT)

        global_dir = os.path.join(self.skills_base, "global")
        self._load_skills_from_directory(global_dir, SkillLevel.GLOBAL)

        projects_dir = os.path.join(self.skills_base, "projects")
        if os.path.exists(projects_dir):
            for project_id in os.listdir(projects_dir):
                project_dir = os.path.join(projects_dir, project_id)
                if os.path.isdir(project_dir):
                    self._load_skills_from_directory(project_dir, SkillLevel.PROJECT)

        agents_dir = os.path.join(self.skills_base, "agents")
        if os.path.exists(agents_dir):
            for agent_id in os.listdir(agents_dir):
                agent_dir = os.path.join(agents_dir, agent_id)
                if os.path.isdir(agent_dir):
                    self._load_skills_from_directory(agent_dir, SkillLevel.AGENT)

        self._create_builtin_skills()

        logger.info(
            "All skills loaded: total=%d",
            len(self.registry.list_all())
        )

    def _create_builtin_skills(self) -> None:
        builtins = [
            Skill(
                metadata=SkillMetadata(
                    skill_id="error_handling",
                    name="error_handling",
                    display_name="错误处理与恢复",
                    description="标准化错误处理和自动恢复机制，支持重试、降级、熔断策略",
                    level=SkillLevel.GLOBAL,
                    priority=SkillPriority.GLOBAL,
                    applicable_tasks=["*"],
                    required_context=["error", "retry_count"],
                    tags=["error", "recovery", "retry", "circuit_breaker"],
                ),
                raw_content="# 错误处理与恢复\n\n标准化错误处理技能。",
                body="标准化错误处理技能。",
                is_loaded=True,
                is_active=True,
            ),
            Skill(
                metadata=SkillMetadata(
                    skill_id="constraint_checking",
                    name="constraint_checking",
                    display_name="工艺参数约束校验",
                    description="切削参数安全约束校验，确保加工参数在设备安全范围内",
                    level=SkillLevel.GLOBAL,
                    priority=SkillPriority.GLOBAL,
                    applicable_tasks=["prediction", "optimization"],
                    required_context=["material", "tool_type", "parameters"],
                    tags=["constraint", "validation", "safety"],
                    parameters={
                        "max_spindle_speed": 60000,
                        "max_feed_rate": 10000,
                        "max_depth_of_cut": 5.0,
                    },
                ),
                raw_content="# 工艺参数约束校验\n\n确保切削参数在安全范围内。",
                body="确保切削参数在安全范围内。",
                is_loaded=True,
                is_active=True,
            ),
            Skill(
                metadata=SkillMetadata(
                    skill_id="safety_guidelines",
                    name="safety_guidelines",
                    display_name="安全操作指南",
                    description="加工安全操作规程，包括紧急停机、防护装置检查、人员安全要求",
                    level=SkillLevel.GLOBAL,
                    priority=SkillPriority.GLOBAL,
                    applicable_tasks=["*"],
                    required_context=[],
                    tags=["safety", "guidelines", "operation"],
                ),
                raw_content="# 安全操作指南\n\n加工安全操作规程。",
                body="加工安全操作规程。",
                is_loaded=True,
                is_active=True,
            ),
        ]

        for skill in builtins:
            if not self.registry.get(skill.metadata.skill_id):
                self.registry.register(skill)

    def _load_skills_from_directory(self, directory: str, level: SkillLevel) -> List[Skill]:
        skills = []
        if not os.path.exists(directory):
            return skills

        for file_name in sorted(os.listdir(directory)):
            file_path = os.path.join(directory, file_name)
            if file_name.endswith(".md"):
                skill = self._load_skill_from_file(file_path, level)
                if skill:
                    skills.append(skill)
                    self.registry.register(skill)

        return skills

    def _load_skill_from_file(self, file_path: str, level: SkillLevel) -> Optional[Skill]:
        parsed = MarkdownSkillParser.parse(file_path)
        if parsed is None:
            return None

        meta_dict = parsed.get("metadata", {})

        priority = PRIORITY_MAP.get(level, SkillPriority.GLOBAL)

        metadata = SkillMetadata(
            skill_id=meta_dict.get("skill_id", Path(file_path).stem),
            name=meta_dict.get("name", Path(file_path).stem),
            display_name=meta_dict.get("display_name", meta_dict.get("name", "")),
            description=meta_dict.get("description", ""),
            version=meta_dict.get("version", "1.0.0"),
            level=level,
            priority=priority,
            applicable_tasks=meta_dict.get("applicable_tasks", ["*"]),
            required_context=meta_dict.get("required_context", []),
            author=meta_dict.get("author", ""),
            tags=meta_dict.get("tags", []),
            dependencies=meta_dict.get("dependencies", []),
            parameters=meta_dict.get("parameters", {}),
            source_path=file_path,
        )

        content_hash = self._compute_content_hash(parsed.get("raw_content", ""))

        version_obj = SkillVersion(
            version=metadata.version,
            content_hash=content_hash,
            file_path=file_path,
            metadata=deepcopy(meta_dict),
        )

        skill = Skill(
            metadata=metadata,
            raw_content=parsed.get("raw_content", ""),
            body=parsed.get("body", ""),
            code_blocks=parsed.get("code_blocks", []),
            versions={metadata.version: version_obj},
        )

        for lang, code in parsed.get("code_blocks", []):
            if lang == "python":
                try:
                    executor = self._compile_code(code, metadata.skill_id)
                    if executor:
                        skill.executor = executor
                        skill.is_loaded = True
                except Exception as e:
                    logger.warning(
                        "Failed to load code block from %s: %s", file_path, e
                    )

        return skill

    def _compile_code(self, code: str, skill_id: str) -> Optional[Callable]:
        compiled = compile(code, f"<skill:{skill_id}>", "exec")
        namespace: Dict[str, Any] = {}
        exec(compiled, namespace)
        for name in ("execute", "run", "main", "handler"):
            if name in namespace and callable(namespace[name]):
                return namespace[name]
        if "SkillExecutor" in namespace:
            cls = namespace["SkillExecutor"]
            try:
                return cls()
            except Exception:
                for attr_name in dir(cls):
                    if not attr_name.startswith("_") and callable(getattr(cls, attr_name)):
                        return getattr(cls, attr_name)()
        for attr_name, attr_val in namespace.items():
            if not attr_name.startswith("_") and callable(attr_val):
                return attr_val
        return None

    @staticmethod
    def _compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def load_project_skills(self, project_id: str) -> List[Skill]:
        project_dir = os.path.join(self.skills_base, "projects", project_id)
        if os.path.exists(project_dir):
            return self._load_skills_from_directory(project_dir, SkillLevel.PROJECT)
        return []

    def load_agent_skills(self, agent_id: str) -> List[Skill]:
        agent_dir = os.path.join(self.skills_base, "agents", agent_id)
        if os.path.exists(agent_dir):
            return self._load_skills_from_directory(agent_dir, SkillLevel.AGENT)
        return []

    def get_skills_for_task(
        self, task_type: str, project_id: Optional[str] = None,
        agent_id: Optional[str] = None, available_context: Optional[Set[str]] = None,
    ) -> List[Skill]:
        skills: List[Skill] = []

        all_globals = self.registry.get_by_level(SkillLevel.GLOBAL)
        skills.extend(all_globals)

        if project_id:
            project_skills = self.load_project_skills(project_id)
            skills.extend([s for s in project_skills if s.metadata.applicable_to(task_type)])

        if agent_id:
            agent_skills = self.load_agent_skills(agent_id)
            skills.extend(agent_skills)

        skills.sort(key=lambda s: s.metadata.priority.value)

        if available_context is not None:
            skills = [
                s for s in skills
                if s.metadata.contexts_satisfied(available_context)[0]
            ]

        logger.info(
            "Retrieved %d skills for task=%s project=%s agent=%s",
            len(skills), task_type, project_id or "N/A", agent_id or "N/A",
        )
        return skills

    def inject_context(self, context: Dict[str, Any]) -> None:
        self._context.update(context)
        for skill in self.registry.list_all():
            skill.context.update(context)

    def execute_skill(self, skill_id: str, **kwargs) -> Any:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill not found: {skill_id}")
        return skill.execute(**kwargs)

    def execute_all(self, task_type: str, project_id: Optional[str] = None,
                    agent_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        skills = self.get_skills_for_task(task_type, project_id, agent_id)
        results: Dict[str, Any] = {}

        for skill in skills:
            try:
                result = skill.execute(**kwargs)
                results[skill.metadata.skill_id] = {"status": "success", "result": result}
            except Exception as e:
                results[skill.metadata.skill_id] = {"status": "error", "error": str(e)}
                logger.error("Skill execution failed %s: %s", skill.metadata.name, e)

        return results

    async def inject_skills(
        self, task_type: str, project_id: Optional[str] = None,
        agent_id: Optional[str] = None, available_context: Optional[Set[str]] = None,
    ) -> str:
        skills = self.get_skills_for_task(task_type, project_id, agent_id, available_context)
        return self._merge_skills_to_context(skills)

    def _merge_skills_to_context(self, skills: List[Skill]) -> str:
        if not skills:
            return ""

        lines: List[str] = [
            "## 已注入技能指南\n",
            "_以下技能为运行时动态注入，用于指导当前任务执行：_\n",
        ]

        for i, skill in enumerate(skills, 1):
            meta = skill.metadata
            lines.append(f"### {i}. {meta.display_name or meta.name} (v{meta.version})")
            if meta.description:
                lines.append(f"**描述**: {meta.description}")
            if meta.tags:
                lines.append(f"**标签**: {', '.join(meta.tags)}")

            level_labels = {
                SkillLevel.GLOBAL: "🌐 全局",
                SkillLevel.PROJECT: "📁 项目",
                SkillLevel.AGENT: "🤖 代理",
            }
            lines.append(f"**级别**: {level_labels.get(meta.level, meta.level.value)}")

            if meta.required_context:
                lines.append(f"**所需上下文**: {', '.join(meta.required_context)}")

            if meta.parameters:
                params_str = ", ".join(f"{k}={v}" for k, v in meta.parameters.items())
                lines.append(f"**参数**: {params_str}")

            if skill.body:
                lines.append("")
                lines.append(skill.body[:2000])
                if len(skill.body) > 2000:
                    lines.append("\n... (内容已截断)")

            if skill.code_blocks:
                lines.append("")
                lines.append("**代码块**:")
                for lang, code in skill.code_blocks[:3]:
                    lines.append(f"\n```{lang}\n{code[:1000]}\n```")

            lines.append("")

        return "\n".join(lines)

    def hot_reload(self, skill_id: Optional[str] = None) -> Dict[str, Any]:
        if skill_id:
            skill = self.registry.get(skill_id)
            if skill and skill.metadata.source_path:
                level = skill.metadata.level
                new_skill = self._load_skill_from_file(skill.metadata.source_path, level)
                if new_skill:
                    self.registry.register(new_skill)
                    return {"status": "reloaded", "skill_id": skill_id}
                return {"status": "error", "skill_id": skill_id, "message": "Parse failed"}
            return {"status": "not_found", "skill_id": skill_id}

        self._load_all_skills()
        return {"status": "full_reload", "count": len(self.registry.list_all())}

    def get_version_history(self, skill_id: str) -> Optional[List[Dict[str, Any]]]:
        skill = self.registry.get(skill_id)
        if skill is None:
            return None

        history = []
        for ver_str, ver_obj in sorted(skill.versions.items()):
            history.append({
                "version": ver_str,
                "content_hash": ver_obj.content_hash,
                "file_path": ver_obj.file_path,
                "created_at": ver_obj.created_at,
                "created_at_iso": datetime.fromtimestamp(
                    ver_obj.created_at, tz=timezone.utc
                ).isoformat(),
            })

        return history

    def save_skill_file(
        self, skill_id: str, content: str, level: SkillLevel = SkillLevel.PROJECT,
        sub_id: Optional[str] = None,
    ) -> str:
        if level == SkillLevel.GLOBAL:
            target_dir = os.path.join(self.skills_base, "global")
        elif level == SkillLevel.PROJECT:
            if not sub_id:
                raise ValueError("sub_id (project_id) required for PROJECT level skills")
            target_dir = os.path.join(self.skills_base, "projects", sub_id)
        elif level == SkillLevel.AGENT:
            if not sub_id:
                raise ValueError("sub_id (agent_id) required for AGENT level skills")
            target_dir = os.path.join(self.skills_base, "agents", sub_id)
        else:
            raise ValueError(f"Unknown skill level: {level}")

        os.makedirs(target_dir, exist_ok=True)

        file_name = f"{skill_id}.md"
        file_path = os.path.join(target_dir, file_name)

        if os.path.exists(file_path):
            backup_dir = os.path.join(target_dir, ".versions")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{skill_id}_{timestamp}.md")
            shutil.copy2(file_path, backup_path)
            logger.info("Backup created: %s", backup_path)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        skill = self._load_skill_from_file(file_path, level)
        if skill:
            self.registry.register(skill)

        logger.info("Skill saved: %s", file_path)
        return file_path

    def export_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        skill = self.registry.get(skill_id)
        if skill is None:
            return None

        return {
            "skill_id": skill.metadata.skill_id,
            "name": skill.metadata.name,
            "version": skill.metadata.version,
            "raw_content": skill.raw_content,
            "metadata": skill.metadata.to_dict(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    def import_skill(self, skill_package: Dict[str, Any],
                     level: SkillLevel = SkillLevel.PROJECT,
                     sub_id: Optional[str] = None) -> Optional[Skill]:
        skill_id = skill_package.get("skill_id")
        raw_content = skill_package.get("raw_content")

        if not skill_id or not raw_content:
            raise ValueError("Invalid skill package: missing skill_id or raw_content")

        file_path = self.save_skill_file(
            skill_id=skill_id,
            content=raw_content,
            level=level,
            sub_id=sub_id,
        )

        parsed = MarkdownSkillParser.parse(file_path)
        if parsed is None:
            return None

        meta_dict = parsed.get("metadata", {})
        priority = PRIORITY_MAP.get(level, SkillPriority.GLOBAL)

        metadata = SkillMetadata(
            skill_id=meta_dict.get("skill_id", skill_id),
            name=meta_dict.get("name", skill_id),
            display_name=meta_dict.get("display_name", ""),
            description=meta_dict.get("description", ""),
            version=meta_dict.get("version", "1.0.0"),
            level=level,
            priority=priority,
            applicable_tasks=meta_dict.get("applicable_tasks", ["*"]),
            required_context=meta_dict.get("required_context", []),
            author=skill_package.get("metadata", {}).get("author", ""),
            tags=meta_dict.get("tags", []),
            source_path=file_path,
        )

        skill = Skill(
            metadata=metadata,
            raw_content=raw_content,
            body=parsed.get("body", ""),
            code_blocks=parsed.get("code_blocks", []),
        )

        self.registry.register(skill)
        logger.info("Skill imported: %s", skill_id)
        return skill

    def rate_skill(self, skill_id: str, rating: float) -> Dict[str, Any]:
        if rating < 0 or rating > 5:
            raise ValueError("Rating must be between 0 and 5")

        skill = self.registry.get(skill_id)
        if skill is None:
            raise KeyError(f"Skill not found: {skill_id}")

        skill.metadata.ratings.append(rating)
        avg = sum(skill.metadata.ratings) / len(skill.metadata.ratings)

        logger.info("Skill rated: %s -> %.2f (%d ratings)", skill_id, rating, len(skill.metadata.ratings))
        return {
            "skill_id": skill_id,
            "rating": rating,
            "avg_rating": round(avg, 2),
            "rating_count": len(skill.metadata.ratings),
        }

    def get_stats(self) -> Dict[str, Any]:
        registry_stats = self.registry.get_stats()
        registry_stats["skills_base_dir"] = self.skills_base
        registry_stats["watcher_active"] = self._watcher is not None and self._watcher._running
        return registry_stats

    def shutdown(self) -> None:
        self.stop_watcher()
        logger.info("SkillLoader shut down")


_loader: Optional[SkillLoader] = None
_loader_lock = threading.Lock()


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        with _loader_lock:
            if _loader is None:
                _loader = SkillLoader()
    return _loader


def init_skill_loader(skills_base_dir: Optional[str] = None) -> SkillLoader:
    global _loader
    with _loader_lock:
        if _loader is not None:
            _loader.shutdown()
        _loader = SkillLoader(skills_base_dir)
    return _loader


async def inject_skills(
    task_type: str, project_id: Optional[str] = None,
    agent_id: Optional[str] = None, available_context: Optional[Set[str]] = None,
) -> str:
    loader = get_skill_loader()
    return await loader.inject_skills(task_type, project_id, agent_id, available_context)
