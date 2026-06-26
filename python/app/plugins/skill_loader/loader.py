"""技能加载器主模块 - 三级分层架构 + 热更新 + 版本控制。"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import sys
import time
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from app.config import config

from .models import (
    Skill,
    SkillLevel,
    SkillMetadata,
    SkillPriority,
    SkillVersion,
    PRIORITY_MAP,
)
from .registry import SkillRegistry
from .validator import MarkdownSkillParser
from .lifecycle import SkillFileWatcher

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """沙箱安全异常 - 当检测到代码试图绕过安全沙箱时抛出。"""
    pass


DEFAULT_SKILLS_BASE = config.paths.skills_dir


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

    @staticmethod
    def _sanitize_path_segment(segment: str) -> str:
        sanitized = re.sub(r'[<>:"|?*\\/]', "_", str(segment))
        sanitized = sanitized.strip(". ")
        if not sanitized:
            raise ValueError(f"路径段净化后为空: '{segment}'")
        return sanitized

    def _resolve_safe_subpath(self, *segments: str) -> str:
        safe = [self._sanitize_path_segment(s) for s in segments]
        result = os.path.normpath(os.path.join(self.skills_base, *safe))
        normalized_base = os.path.normpath(self.skills_base)
        if not result.startswith(normalized_base):
            raise ValueError(f"路径遍历检测: {result}")
        return result

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

        logger.info("All skills loaded: total=%d", len(self.registry.list_all()))

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

    def _load_skills_from_directory(
        self, directory: str, level: SkillLevel
    ) -> List[Skill]:
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

    def _load_skill_from_file(
        self, file_path: str, level: SkillLevel
    ) -> Optional[Skill]:
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
                except (OSError, RuntimeError, ValueError, TypeError, NameError) as e:
                    logger.warning(
                        "Failed to load code block from %s: %s", file_path, e,
                        exc_info=True,
                    )

        return skill

    _SAFE_BUILTINS = {
        "True": True, "False": False, "None": None,
        "bool": bool, "float": float, "int": int, "str": str,
        "abs": abs, "divmod": divmod, "max": max, "min": min,
        "pow": pow, "round": round, "sum": sum,
        "all": all, "any": any, "enumerate": enumerate, "len": len,
        "list": list, "range": range, "sorted": sorted,
    }

    _FORBIDDEN_BUILTINS = frozenset({
        "__import__", "exec", "eval", "compile", "open",
        "input", "breakpoint",
        "type", "vars", "dir", "getattr", "setattr", "delattr", "hasattr",
        "object", "super", "callable", "isinstance", "issubclass",
        "print", "memoryview", "property", "staticmethod",
        "classmethod", "ascii", "repr", "hash",
        "iter", "next", "map", "filter", "bytes", "bytearray",
    })

    _USE_SUBPROCESS_ISOLATION = os.environ.get("SKILL_USE_SUBPROCESS", "0") == "1"
    _SUBPROCESS_TIMEOUT_SEC = float(os.environ.get("SKILL_SUBPROCESS_TIMEOUT", "10"))

    def _compile_code(self, code: str, skill_id: str) -> Optional[Callable]:
        self._audit_code_security(code, skill_id)

        if self._USE_SUBPROCESS_ISOLATION:
            return _SubprocessSkillExecutor(
                code=code,
                skill_id=skill_id,
                timeout=self._SUBPROCESS_TIMEOUT_SEC,
            )

        try:
            from RestrictedPython import compile_restricted
            from RestrictedPython.Guards import (
                safe_builtins as rp_safe_builtins,
                guarded_iter_unpack_sequence,
            )
        except ImportError:
            logger.error(
                "RestrictedPython is required for secure skill execution but is not installed. "
                "Skill '%s' cannot be loaded. Install it with: pip install RestrictedPython",
                skill_id,
            )
            raise RuntimeError(
                f"Cannot load skill '{skill_id}': RestrictedPython is required for secure "
                "code execution but is not installed. Install it with: pip install RestrictedPython"
            )

        try:
            byte_code = compile_restricted(code, f"<skill:{skill_id}>", "exec")
        except SyntaxError as e:
            logger.error("Skill '%s' syntax error: %s", skill_id, e)
            return None

        restricted_globals = {
            "__builtins__": rp_safe_builtins,
            "_getattr_": getattr,
            "_write_": lambda x: None,
            "_getiter_": iter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "__name__": f"skill:{skill_id}",
            "__metaclass__": type,
        }

        try:
            exec(byte_code, restricted_globals)
        except (SyntaxError, NameError, AttributeError, TypeError,
                ValueError, RuntimeError, OSError) as e:
            logger.error(
                "Skill '%s' execution error: %s", skill_id, e, exc_info=True,
            )
            return None

        return self._extract_callable(restricted_globals, skill_id)

    def _compile_code_in_process(self, code: str, skill_id: str) -> Optional[Callable]:
        """备用编译方法：当 RestrictedPython 不可用时使用受限 builtins。
        
        注意：此方法不提供与 compile_restricted 相同级别的安全保护，
        仅通过限制 __builtins__ 来降低风险。生产环境应优先使用 RestrictedPython。
        """
        try:
            compiled = compile(code, f"<skill:{skill_id}>", "exec")
        except SyntaxError as e:
            logger.error("Skill '%s' syntax error: %s", skill_id, e)
            return None

        # 安全修复：使用受限的 builtins，移除危险函数
        namespace: Dict[str, Any] = {"__builtins__": self._SAFE_BUILTINS}
        try:
            exec(compiled, namespace)
        except (SyntaxError, NameError, AttributeError, TypeError,
                ValueError, RuntimeError, OSError) as e:
            logger.error(
                "Skill '%s' execution error: %s", skill_id, e, exc_info=True,
            )
            return None

        return self._extract_callable(namespace, skill_id)

    def _extract_callable(
        self, namespace: Dict[str, Any], skill_id: str
    ) -> Optional[Callable]:
        for name in ("execute", "run", "main", "handler"):
            if name in namespace and callable(namespace[name]):
                return namespace[name]

        if "SkillExecutor" in namespace:
            cls = namespace["SkillExecutor"]
            try:
                return cls()
            except (TypeError, ValueError, RuntimeError, OSError) as e:
                logger.debug(
                    "SkillExecutor instantiation failed, fallback to attribute scan: %s",
                    e, exc_info=True,
                )

        for attr_name, attr_val in namespace.items():
            if not attr_name.startswith("_") and callable(attr_val):
                return attr_val

        return None

    @staticmethod
    def _audit_code_security(code: str, skill_id: str) -> None:
        import re as _re

        dangerous_patterns = [
            (r"__import__\s*\(", "直接调用 __import__"),
            (r"\bimport\b\s+(?!.*\b(?:os|sys|subprocess|ctypes|socket|shutil)\b)", "import 语句"),
            (r"\bexec\s*\(", "exec() 调用"),
            (r"\beval\s*\(", "eval() 调用"),
            (r"\bcompile\s*\(", "compile() 调用"),
            (r"\bopen\s*\(", "open() 调用"),
            (r"\binput\s*\(", "input() 调用"),
            (r"\bbreakpoint\s*\(", "breakpoint() 调用"),
            (r"__subclasses__\s*\(\)", "访问 __subclasses__()"),
            (r"__bases__", "访问 __bases__"),
            (r"__mro__", "访问 __mro__"),
            (r"__globals__", "访问 __globals__"),
            (r"__code__", "访问 __code__"),
            (r"__builtins__", "访问 __builtins__"),
            (r"__class__", "访问 __class__"),
            (r"__dict__", "访问 __dict__"),
            (r"__func__", "访问 __func__"),
            (r"__self__", "访问 __self__"),
            (r"\bos\b", "引用 os 模块"),
            (r"\bsys\b", "引用 sys 模块"),
            (r"\bsubprocess\b", "引用 subprocess 模块"),
            (r"\bctypes\b", "引用 ctypes 模块"),
            (r"\bsocket\b", "引用 socket 模块"),
            (r"\bshutil\b", "引用 shutil 模块"),
            (r"\bimportlib\b", "引用 importlib 模块"),
            (r"\bpickle\b", "引用 pickle 模块"),
            (r"\bmarshal\b", "引用 marshal 模块"),
            (r"getattr\s*\(", "getattr() 调用"),
            (r"hasattr\s*\(", "hasattr() 调用"),
            (r"\btype\s*\(", "type() 调用"),
            (r"\bvars\s*\(", "vars() 调用"),
            (r"\bdir\s*\(", "dir() 调用"),
            (r"\._module_\b", "访问 .__module__"),
            (r"load_module\s*\(", "load_module() 调用"),
        ]

        for pattern, description in dangerous_patterns:
            if _re.search(pattern, code):
                raise SecurityError(
                    f"技能 '{skill_id}' 包含危险的代码模式: {description}。"
                    f"该模式可能用于沙箱逃逸，已被拒绝执行。"
                )

    @staticmethod
    def _compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def load_project_skills(self, project_id: str) -> List[Skill]:
        project_dir = self._resolve_safe_subpath("projects", project_id)
        if os.path.exists(project_dir):
            return self._load_skills_from_directory(project_dir, SkillLevel.PROJECT)
        return []

    def load_agent_skills(self, agent_id: str) -> List[Skill]:
        agent_dir = self._resolve_safe_subpath("agents", agent_id)
        if os.path.exists(agent_dir):
            return self._load_skills_from_directory(agent_dir, SkillLevel.AGENT)
        return []

    def get_skills_for_task(
        self,
        task_type: str,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        available_context: Optional[Set[str]] = None,
    ) -> List[Skill]:
        skills: List[Skill] = []

        all_globals = self.registry.get_by_level(SkillLevel.GLOBAL)
        skills.extend(all_globals)

        if project_id:
            project_skills = self.load_project_skills(project_id)
            skills.extend(
                [s for s in project_skills if s.metadata.applicable_to(task_type)]
            )

        if agent_id:
            agent_skills = self.load_agent_skills(agent_id)
            skills.extend(agent_skills)

        skills.sort(key=lambda s: s.metadata.priority.value)

        if available_context is not None:
            skills = [
                s for s in skills if s.metadata.contexts_satisfied(available_context)[0]
            ]

        logger.info(
            "Retrieved %d skills for task=%s project=%s agent=%s",
            len(skills),
            task_type,
            project_id or "N/A",
            agent_id or "N/A",
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

    def execute_all(
        self,
        task_type: str,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        skills = self.get_skills_for_task(task_type, project_id, agent_id)
        results: Dict[str, Any] = {}

        for skill in skills:
            try:
                result = skill.execute(**kwargs)
                results[skill.metadata.skill_id] = {
                    "status": "success",
                    "result": result,
                }
            except (TypeError, ValueError, RuntimeError, KeyError,
                    AttributeError, OSError) as e:
                from app.core.safe_errors import safe_error_message

                safe = safe_error_message(
                    e,
                    context=f"skill.execute.{skill.metadata.skill_id}",
                    fallback="技能执行失败",
                )
                results[skill.metadata.skill_id] = {
                    "status": "error",
                    "error": safe["message"],
                    "error_id": safe["error_id"],
                }
                logger.error(
                    "Skill execution failed %s: %s",
                    skill.metadata.name, e, exc_info=True,
                )

        return results

    async def inject_skills(
        self,
        task_type: str,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        available_context: Optional[Set[str]] = None,
    ) -> str:
        skills = self.get_skills_for_task(
            task_type, project_id, agent_id, available_context
        )
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
                new_skill = self._load_skill_from_file(
                    skill.metadata.source_path, level
                )
                if new_skill:
                    self.registry.register(new_skill)
                    return {"status": "reloaded", "skill_id": skill_id}
                return {
                    "status": "error",
                    "skill_id": skill_id,
                    "message": "Parse failed",
                }
            return {"status": "not_found", "skill_id": skill_id}

        self._load_all_skills()
        return {"status": "full_reload", "count": len(self.registry.list_all())}

    def get_version_history(self, skill_id: str) -> Optional[List[Dict[str, Any]]]:
        skill = self.registry.get(skill_id)
        if skill is None:
            return None

        history = []
        for ver_str, ver_obj in sorted(skill.versions.items()):
            history.append(
                {
                    "version": ver_str,
                    "content_hash": ver_obj.content_hash,
                    "file_path": ver_obj.file_path,
                    "created_at": ver_obj.created_at,
                    "created_at_iso": datetime.fromtimestamp(
                        ver_obj.created_at, tz=timezone.utc
                    ).isoformat(),
                }
            )

        return history

    def save_skill_file(
        self,
        skill_id: str,
        content: str,
        level: SkillLevel = SkillLevel.PROJECT,
        sub_id: Optional[str] = None,
    ) -> str:
        safe_skill_id = self._sanitize_path_segment(skill_id)

        if level == SkillLevel.GLOBAL:
            target_dir = os.path.join(self.skills_base, "global")
        elif level == SkillLevel.PROJECT:
            if not sub_id:
                raise ValueError(
                    "sub_id (project_id) required for PROJECT level skills"
                )
            target_dir = self._resolve_safe_subpath("projects", sub_id)
        elif level == SkillLevel.AGENT:
            if not sub_id:
                raise ValueError("sub_id (agent_id) required for AGENT level skills")
            target_dir = self._resolve_safe_subpath("agents", sub_id)
        else:
            raise ValueError(f"Unknown skill level: {level}")

        os.makedirs(target_dir, exist_ok=True)

        file_name = f"{safe_skill_id}.md"
        file_path = os.path.join(target_dir, file_name)

        if os.path.exists(file_path):
            backup_dir = os.path.join(target_dir, ".versions")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{safe_skill_id}_{timestamp}.md")
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

    def import_skill(
        self,
        skill_package: Dict[str, Any],
        level: SkillLevel = SkillLevel.PROJECT,
        sub_id: Optional[str] = None,
    ) -> Optional[Skill]:
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

        logger.info(
            "Skill rated: %s -> %.2f (%d ratings)",
            skill_id,
            rating,
            len(skill.metadata.ratings),
        )
        return {
            "skill_id": skill_id,
            "rating": rating,
            "avg_rating": round(avg, 2),
            "rating_count": len(skill.metadata.ratings),
        }

    def get_stats(self) -> Dict[str, Any]:
        registry_stats = self.registry.get_stats()
        registry_stats["skills_base_dir"] = self.skills_base
        registry_stats["watcher_active"] = (
            self._watcher is not None and self._watcher._running
        )
        return registry_stats

    def shutdown(self) -> None:
        self.stop_watcher()
        logger.info("SkillLoader shut down")


class _SubprocessSkillExecutor:
    """子进程隔离的技能执行代理。"""

    _WORKER_SCRIPT = '''\
# -*- coding: utf-8 -*-
"""子进程 worker 脚本 - 在隔离进程中执行技能代码。"""
import sys
import json
import base64

SAFE_BUILTINS = {
    "True": True, "False": False, "None": None,
    "bool": bool, "float": float, "int": int, "str": str,
    "abs": abs, "divmod": divmod, "max": max, "min": min,
    "pow": pow, "round": round, "sum": sum,
    "all": all, "any": any, "enumerate": enumerate, "len": len,
    "list": list, "range": range, "sorted": sorted,
}

try:
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8"))
except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
    sys.stdout.write(
        json.dumps({"status": "error", "error": "input parse failed"})
    )
    sys.exit(1)

try:
    code = base64.b64decode(data["code"]).decode("utf-8")
    skill_id = data["skill_id"]
    args = data.get("args", {})
except (KeyError, UnicodeDecodeError, binascii.Error, TypeError, ValueError):
    sys.stdout.write(
        json.dumps({"status": "error", "error": "input decode failed"})
    )
    sys.exit(1)

try:
    namespace = {"__builtins__": SAFE_BUILTINS, "__name__": "skill:" + skill_id}
    compiled = compile(code, "<skill:" + skill_id + ">", "exec")
    exec(compiled, namespace)

    entry = None
    for name in ("execute", "run", "main", "handler"):
        if name in namespace and callable(namespace[name]):
            entry = namespace[name]
            break

    if entry is None:
        sys.stdout.write(json.dumps({"status": "error", "error": "no entry point found"}))
        sys.exit(1)

    result = entry(**args)
    sys.stdout.write(json.dumps({"status": "ok", "result": result}, default=str))
except (RuntimeError, ValueError, TypeError, OSError, NameError, AttributeError, KeyError) as e:
    sys.stdout.write(json.dumps({
        "status": "error",
        "error": str(e),
        "type": type(e).__name__,
    }))
    sys.exit(1)
'''

    def __init__(self, code: str, skill_id: str, timeout: float = 10.0):
        self.code = code
        self.skill_id = skill_id
        self.timeout = timeout
        self._worker_path: Optional[str] = None

    def _ensure_worker(self) -> str:
        if self._worker_path is not None and os.path.exists(self._worker_path):
            return self._worker_path
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="skill_worker_")
        self._worker_path = os.path.join(tmp_dir, "worker.py")
        try:
            with open(self._worker_path, "w", encoding="utf-8") as f:
                f.write(self._WORKER_SCRIPT)
        except Exception as e:
            # 写入失败时清理临时目录，避免泄漏
            logger.error("Failed to write skill worker script to %s: %s", self._worker_path, e, exc_info=True)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self._worker_path = None
            raise
        return self._worker_path

    def __call__(self, *args, **kwargs):
        import base64
        import subprocess
        import json as _json

        worker_path = self._ensure_worker()
        input_data = {
            "code": base64.b64encode(self.code.encode("utf-8")).decode("ascii"),
            "skill_id": self.skill_id,
            "args": kwargs,
        }

        try:
            proc = subprocess.run(
                [sys.executable, worker_path],
                input=_json.dumps(input_data),
                capture_output=True,
                timeout=self.timeout,
                text=True,
            )
        except subprocess.TimeoutExpired as e:
            logger.error(
                "Skill '%s' subprocess timed out after %.1fs",
                self.skill_id, self.timeout,
            )
            raise TimeoutError(
                f"Skill '{self.skill_id}' execution timed out after {self.timeout}s"
            ) from e

        if not proc.stdout:
            raise RuntimeError(
                f"Skill '{self.skill_id}' subprocess produced no output. "
                f"stderr: {proc.stderr}"
            )

        try:
            result = _json.loads(proc.stdout)
        except _json.JSONDecodeError as e:
            raise RuntimeError(
                f"Skill '{self.skill_id}' produced invalid JSON output: {e}. "
                f"stdout: {proc.stdout[:500]} | stderr: {proc.stderr[:500]}"
            )

        if result.get("status") == "error":
            error_type = result.get("type", "RuntimeError")
            error_msg = result.get("error", "Unknown error")
            exc_class = globals().get(error_type, RuntimeError)
            if isinstance(exc_class, type) and issubclass(exc_class, BaseException):
                raise exc_class(error_msg)
            raise RuntimeError(error_msg)

        return result.get("result")


class _LoaderHolder:
    """Thread-safe lazy holder for the :class:`SkillLoader` singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instance: Optional[SkillLoader] = None

    def get(self) -> SkillLoader:
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is None:
                self._instance = SkillLoader()
            return self._instance

    def init(self, skills_base_dir: Optional[str] = None) -> SkillLoader:
        with self._lock:
            if self._instance is not None:
                self._instance.shutdown()
            self._instance = SkillLoader(skills_base_dir)
            return self._instance

    def reset(self) -> None:
        with self._lock:
            self._instance = None


_holder = _LoaderHolder()


def get_skill_loader() -> SkillLoader:
    """获取共享的 :class:`SkillLoader` 单例；首次访问时懒初始化。"""
    return _holder.get()


def init_skill_loader(skills_base_dir: Optional[str] = None) -> SkillLoader:
    """初始化技能加载器，行为与重构前完全一致。"""
    return _holder.init(skills_base_dir)


async def inject_skills(
    task_type: str,
    project_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    available_context: Optional[Set[str]] = None,
) -> str:
    loader = get_skill_loader()
    return await loader.inject_skills(
        task_type, project_id, agent_id, available_context
    )
