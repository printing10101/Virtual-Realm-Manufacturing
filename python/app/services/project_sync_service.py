"""项目级 Git 同步服务层.

对应 ADR-011 阶段 6 p6-2：项目级 Git 同步业务逻辑。

职责：
    1. Git 操作封装：init / status / commit / push / pull / clone（subprocess.run）
    2. 资源引用管理：add_ref / remove_ref / update_ref_hash / list_refs
    3. 同步记录管理：record_sync_operation（每次 Git 写操作生成审计记录）
    4. 项目仓库 CRUD：create_project / get_project / list_projects / delete_project
    5. content_hash 计算：对 model/workflow/config/snapshot/template 资源计算 sha256
    6. .lomo-project.yaml 清单文件读写
    7. git 可用性检测：启动时 git --version，不可用时降级

并发安全：
    - Git 写操作通过 ``_project_locks[project_id]`` 串行化（同一项目内的
      commit/push/pull 互斥，不同项目可并发）
    - 数据库操作通过 SQLAlchemy 事务保证原子性，写操作显式 commit()

降级策略：
    - git 不可用时：init/commit/push/pull/clone 抛 ``GitUnavailableError``，
      查询类操作（list_projects / get_project / list_sync_records）仍可正常执行
    - 仓库目录不存在时：get_project_status 抛 ``ProjectNotFoundError``

仓库存储位置：``<output_dir>/project_sync/<project_id>/``
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import yaml
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.contracts.project_sync import (
    DEFAULT_SYNC_STRATEGY,
    RESOURCE_TYPES,
    SYNC_DIRECTIONS,
    SYNC_STATUS,
    SYNC_STRATEGIES,
    ProjectSyncManifest,
    ResourceRef,
    SyncRecord,
    build_resource_uri,
    parse_resource_uri,
)
from app.database.connection import get_sessionmaker
from app.database.models.project_sync import (
    ProjectRepo,
    ProjectResourceRef,
    ProjectSyncRecord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 单例服务
# ---------------------------------------------------------------------------


_service_singleton: Optional["ProjectSyncService"] = None
_service_lock = threading.Lock()


def get_project_sync_service() -> "ProjectSyncService":
    """获取全局 ProjectSyncService 单例."""
    global _service_singleton
    if _service_singleton is None:
        with _service_lock:
            if _service_singleton is None:
                _service_singleton = ProjectSyncService()
    return _service_singleton


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------


class ProjectSyncError(RuntimeError):
    """项目同步服务基类异常."""


class ProjectNotFoundError(LookupError):
    """项目不存在."""


class ProjectAlreadyExistsError(ValueError):
    """项目名或路径已存在."""


class GitUnavailableError(ProjectSyncError):
    """系统未安装 git 或 git 命令不可用."""


class GitOperationError(ProjectSyncError):
    """git 命令执行失败（非零退出码）."""

    def __init__(self, args: list[str], returncode: int, stderr: str) -> None:
        self.args_ = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"git {' '.join(args)} 失败 (rc={returncode}): {stderr.strip()}"
        )


class ResourceRefNotFoundError(LookupError):
    """资源引用不存在."""


class ResourceRefAlreadyExistsError(ValueError):
    """资源 URI 已存在（同项目内重复）."""


class InvalidProjectStateError(ProjectSyncError):
    """项目状态不允许该操作（如未配置 remote 时 push）."""


# ---------------------------------------------------------------------------
# Git 操作结果数据类
# ---------------------------------------------------------------------------


class _GitResult:
    """git 命令执行结果（内部使用）."""

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# ---------------------------------------------------------------------------
# 服务实现
# ---------------------------------------------------------------------------


class ProjectSyncService:
    """项目级 Git 同步服务.

    线程安全：
        - ``_project_locks``：按 project_id 维护独立的 Lock，确保同一项目内的
          Git 写操作串行化（commit/push/pull 互斥），不同项目可并发
        - ``_git_available_lock``：保护 git 可用性检测的缓存

    数据库事务：
        - 每个公共方法内部独立管理 session，写操作显式 commit
        - Git 操作失败时回滚已修改的 DB 状态，保持一致性
    """

    # git 命令默认超时（秒）
    _GIT_TIMEOUT = 60.0
    # clone/push 大仓库超时（秒）
    _GIT_TIMEOUT_LONG = 300.0
    # .lomo-project.yaml 文件名
    _MANIFEST_FILENAME = ".lomo-project.yaml"

    def __init__(self) -> None:
        # 按 project_id 维护独立的 Lock，确保同一项目 Git 写操作串行化
        self._project_locks: dict[str, threading.Lock] = {}
        self._project_locks_guard = threading.Lock()
        # git 可用性缓存（None 表示未检测；True/False 为检测结果）
        self._git_available: Optional[bool] = None
        self._git_available_lock = threading.Lock()
        # 仓库存储根目录：<output_dir>/project_sync/
        self._repos_root = os.path.join(
            os.path.abspath(config.storage.output_dir), "project_sync"
        )
        os.makedirs(self._repos_root, exist_ok=True)

    # ------------------------------------------------------------------
    # 内部辅助：锁管理
    # ------------------------------------------------------------------

    def _get_project_lock(self, project_id: str) -> threading.Lock:
        """获取（或创建）指定项目的专用锁."""
        with self._project_locks_guard:
            lock = self._project_locks.get(project_id)
            if lock is None:
                lock = threading.Lock()
                self._project_locks[project_id] = lock
            return lock

    # ------------------------------------------------------------------
    # 内部辅助：Git 命令执行
    # ------------------------------------------------------------------

    def _check_git_available(self) -> bool:
        """检测系统 git 是否可用（结果缓存）."""
        with self._git_available_lock:
            if self._git_available is not None:
                return self._git_available
            try:
                result = subprocess.run(
                    ["git", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                    shell=False,
                )
                self._git_available = result.returncode == 0
            except FileNotFoundError:
                logger.warning(
                    "ProjectSyncService: 系统未安装 git，"
                    "Git 写操作将不可用（查询类操作仍可执行）"
                )
                self._git_available = False
            except subprocess.TimeoutExpired:
                logger.warning(
                    "ProjectSyncService: git --version 超时，"
                    "Git 写操作将不可用"
                )
                self._git_available = False
            return self._git_available

    def _require_git(self) -> None:
        """断言 git 可用，否则抛 GitUnavailableError."""
        if not self._check_git_available():
            raise GitUnavailableError(
                "系统未安装 git 或 git 不可用，无法执行 Git 写操作。"
                "请安装 git 并确保其在 PATH 中。"
            )

    def _run_git(
        self,
        args: list[str],
        *,
        cwd: str,
        timeout: Optional[float] = None,
    ) -> _GitResult:
        """执行 git 命令，返回 _GitResult.

        Args:
            args: git 子命令参数列表（如 ``["init"]`` / ``["commit", "-m", msg]``）
            cwd: 工作目录（仓库根路径）
            timeout: 超时秒数（None 使用默认 _GIT_TIMEOUT）

        Returns:
            _GitResult 实例

        Raises:
            GitUnavailableError: git 未安装
            GitOperationError: git 命令返回非零退出码
        """
        self._require_git()
        actual_timeout = timeout or self._GIT_TIMEOUT
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=actual_timeout,
                shell=False,
            )
        except FileNotFoundError as e:
            raise GitUnavailableError("系统未安装 git") from e
        except subprocess.TimeoutExpired as e:
            raise GitOperationError(
                args, -1, f"git 命令超时 ({actual_timeout}s)"
            ) from e

        if result.returncode != 0:
            raise GitOperationError(args, result.returncode, result.stderr)
        return _GitResult(result.returncode, result.stdout, result.stderr)

    # ------------------------------------------------------------------
    # 内部辅助：路径与清单
    # ------------------------------------------------------------------

    def _get_repo_path(self, project_id: str) -> str:
        """返回项目仓库本地路径（不保证存在）."""
        return os.path.join(self._repos_root, project_id)

    def _write_manifest_yaml(
        self, repo_path: str, manifest_dict: dict[str, Any]
    ) -> None:
        """写入 .lomo-project.yaml 清单文件."""
        manifest_path = os.path.join(repo_path, self._MANIFEST_FILENAME)
        # 原子写入：先写临时文件，再 rename
        tmp_path = manifest_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    manifest_dict,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
            os.replace(tmp_path, manifest_path)
        except OSError:
            # 清理临时文件（若存在）
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def _read_manifest_yaml(self, repo_path: str) -> Optional[dict[str, Any]]:
        """读取 .lomo-project.yaml 清单文件（不存在返回 None）."""
        manifest_path = os.path.join(repo_path, self._MANIFEST_FILENAME)
        if not os.path.exists(manifest_path):
            return None
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None

    def _build_manifest_dict(
        self,
        project_orm: ProjectRepo,
        refs: list[ProjectResourceRef],
    ) -> dict[str, Any]:
        """根据 ORM 记录构造 .lomo-project.yaml 清单 dict."""
        return {
            "project_id": project_orm.project_id,
            "name": project_orm.name,
            "description": project_orm.description or "",
            "author": project_orm.author or "",
            "remote_url": project_orm.remote_url or "",
            "current_branch": project_orm.current_branch,
            "resource_refs": [
                {
                    "resource_type": ref.resource_type,
                    "resource_uri": ref.resource_uri,
                    "content_hash": ref.content_hash or "",
                    "sync_strategy": ref.sync_strategy,
                    "metadata": ref.metadata_json or {},
                }
                for ref in refs
            ],
            "schema_version": "1.0",
        }

    # ------------------------------------------------------------------
    # 内部辅助：数据库 session
    # ------------------------------------------------------------------

    async def _get_session(self) -> AsyncSession:
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            raise RuntimeError("数据库未配置，无法获取 session")
        return sessionmaker()

    # ------------------------------------------------------------------
    # 内部辅助：content_hash 计算
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        """计算 bytes 的 sha256 hex（64 字符）."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _sha256_file(file_path: str) -> str:
        """计算文件的 sha256 hex（分块读取，支持大文件）."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _sha256_json(obj: Any) -> str:
        """计算 JSON 序列化后的 sha256（sort_keys 确保确定性）."""
        import json

        payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    async def _compute_content_hash(
        self,
        resource_type: str,
        resource_uri: str,
    ) -> str:
        """根据资源类型计算 content_hash.

        Args:
            resource_type: RESOURCE_TYPES 之一
            resource_uri: 资源 URI

        Returns:
            sha256 hex 字符串；无法计算时返回空字符串（表示未计算）
        """
        try:
            _, path = parse_resource_uri(resource_uri)
        except ValueError:
            return ""

        try:
            if resource_type == RESOURCE_TYPES.DATASET:
                # dataset://<dataset_id>/<version> → 查 DatasetVersion.content_hash
                return await self._lookup_dataset_hash(path)
            if resource_type == RESOURCE_TYPES.MODEL:
                # model://<model_name>/<version> → 模型文件 sha256
                # 当前无 model_artifacts ORM，返回空字符串占位
                # （ADR-012 将补全 model_artifacts 表后启用文件路径查找）
                return ""
            if resource_type == RESOURCE_TYPES.WORKFLOW:
                # workflow://<run_id> → WorkflowRun.spec JSONB sha256
                return await self._lookup_workflow_hash(path)
            if resource_type == RESOURCE_TYPES.CONFIG:
                # config://<spec_name> → YAML 文件 sha256（ConfigStore）
                return await self._lookup_config_hash(path)
            if resource_type == RESOURCE_TYPES.SNAPSHOT:
                # snapshot://<snapshot_id> → ExperimentSnapshot.git_sha
                return await self._lookup_snapshot_hash(path)
            if resource_type == RESOURCE_TYPES.TEMPLATE:
                # template://<template_id>/<version> → manifest_snapshot sha256
                return await self._lookup_template_hash(path)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "ProjectSyncService: 计算 content_hash 失败 (%s): %s",
                resource_uri,
                e,
            )
            return ""
        return ""

    async def _lookup_dataset_hash(self, path: str) -> str:
        """从 DatasetVersion 表查询 content_hash.

        path 格式：<dataset_id>/<version>
        """
        parts = path.split("/", 1)
        if len(parts) != 2:
            return ""
        dataset_id, version = parts
        # 延迟导入，避免循环依赖
        from app.database.models.dataset import DatasetVersion

        async with await self._get_session() as session:
            stmt = select(DatasetVersion.content_hash).where(
                DatasetVersion.dataset_id == dataset_id,
                DatasetVersion.version == version,
            )
            result = await session.execute(stmt)
            row = result.first()
            return (row[0] if row else "") or ""

    async def _lookup_workflow_hash(self, run_id: str) -> str:
        """从 WorkflowRun 表查询 spec JSONB sha256."""
        from app.database.models.workflow import WorkflowRun

        async with await self._get_session() as session:
            stmt = select(WorkflowRun.spec).where(WorkflowRun.run_id == run_id)
            result = await session.execute(stmt)
            row = result.first()
            if not row or not row[0]:
                return ""
            return self._sha256_json(row[0])

    async def _lookup_config_hash(self, spec_name: str) -> str:
        """从 ConfigStore 查询 spec，序列化后计算 sha256.

        ConfigStore 当前是内存 + YAML 文件（无 DB 持久化），此处直接读
        ConfigStore 单例。
        """
        try:
            from app.config.spec import get_config_store

            store = get_config_store()
            spec = store.get_spec(spec_name)
            if spec is None:
                return ""
            return self._sha256_json(spec.to_dict() if hasattr(spec, "to_dict") else str(spec))
        except Exception:  # noqa: BLE001
            return ""

    async def _lookup_snapshot_hash(self, snapshot_id: str) -> str:
        """从 ExperimentSnapshot 表查询 git_sha 作为 content_hash."""
        from app.database.models.dataset import ExperimentSnapshot

        async with await self._get_session() as session:
            stmt = select(ExperimentSnapshot.git_sha).where(
                ExperimentSnapshot.snapshot_id == snapshot_id
            )
            result = await session.execute(stmt)
            row = result.first()
            return (row[0] if row else "") or ""

    async def _lookup_template_hash(self, path: str) -> str:
        """从 WorkflowTemplateVersion 表查询 manifest_snapshot sha256.

        path 格式：<template_id>/<version>
        """
        parts = path.split("/", 1)
        if len(parts) != 2:
            return ""
        template_id, version = parts
        from app.database.models.workflow_template import (
            WorkflowTemplateVersion as TemplateVersionORM,
        )

        async with await self._get_session() as session:
            stmt = select(TemplateVersionORM.manifest_snapshot).where(
                TemplateVersionORM.template_id == template_id,
                TemplateVersionORM.version == version,
            )
            result = await session.execute(stmt)
            row = result.first()
            if not row or not row[0]:
                return ""
            return self._sha256_json(row[0])

    # ------------------------------------------------------------------
    # 内部辅助：同步记录写入
    # ------------------------------------------------------------------

    async def _record_sync(
        self,
        session: AsyncSession,
        project_id: str,
        direction: str,
        *,
        commit_sha: str = "",
        status: str = "success",
        message: str = "",
        details: Optional[dict[str, Any]] = None,
    ) -> ProjectSyncRecord:
        """写入一条同步记录（不 commit，由调用方负责 commit）.

        Args:
            session: 当前 SQLAlchemy 异步 session
            project_id: 所属项目 ID
            direction: SYNC_DIRECTIONS 之一
            commit_sha: 涉及的 commit sha
            status: success / failed / conflict
            message: 操作消息
            details: 附加详情

        Returns:
            创建的 ProjectSyncRecord ORM 实例
        """
        if not SYNC_DIRECTIONS.is_valid(direction):
            raise ValueError(f"direction 不支持: {direction}")
        record = ProjectSyncRecord(
            project_id=project_id,
            direction=direction,
            commit_sha=commit_sha or None,
            status=status,
            message=message or None,
            details=details or {},
        )
        session.add(record)
        return record

    # ------------------------------------------------------------------
    # 内部辅助：状态查询
    # ------------------------------------------------------------------

    def _query_git_status(self, repo_path: str) -> dict[str, Any]:
        """执行 git status / rev-parse，返回状态信息.

        Returns:
            {
                "porcelain": str,         # git status --porcelain 输出
                "head_sha": str,          # 当前 HEAD sha（无 commit 时为空）
                "ahead": int,             # 本地领先远端的 commit 数
                "behind": int,            # 本地落后远端的 commit 数
                "has_remote": bool,       # 是否配置了远端
            }
        """
        result: dict[str, Any] = {
            "porcelain": "",
            "head_sha": "",
            "ahead": 0,
            "behind": 0,
            "has_remote": False,
        }

        # HEAD sha
        try:
            head_res = self._run_git(["rev-parse", "HEAD"], cwd=repo_path)
            result["head_sha"] = head_res.stdout.strip()
        except GitOperationError:
            # 无 commit 时 rev-parse HEAD 失败，正常情况
            pass

        # porcelain status
        status_res = self._run_git(["status", "--porcelain"], cwd=repo_path)
        result["porcelain"] = status_res.stdout.strip()

        # 远端配置检查
        remote_res = self._run_git(["remote"], cwd=repo_path)
        remotes = [r for r in remote_res.stdout.splitlines() if r.strip()]
        result["has_remote"] = bool(remotes)

        # ahead/behind（仅当有远端 + 有上游分支时计算）
        if result["has_remote"] and result["head_sha"]:
            try:
                ahead_res = self._run_git(
                    ["rev-list", "--count", "@{u}..HEAD"],
                    cwd=repo_path,
                )
                result["ahead"] = int(ahead_res.stdout.strip() or "0")
            except GitOperationError:
                # 无上游分支时静默
                pass
            try:
                behind_res = self._run_git(
                    ["rev-list", "--count", "HEAD..@{u}"],
                    cwd=repo_path,
                )
                result["behind"] = int(behind_res.stdout.strip() or "0")
            except GitOperationError:
                pass

        return result

    def _derive_status(self, git_status: dict[str, Any]) -> str:
        """根据 _query_git_status 结果推导 SYNC_STATUS."""
        if git_status["porcelain"]:
            return SYNC_STATUS.DIRTY
        if git_status["ahead"] > 0:
            return SYNC_STATUS.AHEAD
        if git_status["behind"] > 0:
            return SYNC_STATUS.BEHIND
        return SYNC_STATUS.CLEAN

    # ------------------------------------------------------------------
    # 项目仓库 CRUD
    # ------------------------------------------------------------------

    async def create_project(
        self,
        name: str,
        *,
        description: str = "",
        author: str = "",
        remote_url: str = "",
        branch: str = "main",
        initial_commit: bool = True,
    ) -> dict[str, Any]:
        """创建可同步项目（git init + DB 记录 + 初始清单 commit）.

        Args:
            name: 项目显示名
            description: 项目描述
            author: 项目作者
            remote_url: 远端仓库 URL（空表示纯本地仓库）
            branch: 初始分支名（默认 main）
            initial_commit: 是否创建初始 commit（写入 .lomo-project.yaml）

        Returns:
            项目详情 dict（含 project_id / repo_path / status）

        Raises:
            ProjectAlreadyExistsError: 项目名已存在
            GitUnavailableError: 系统未安装 git
            GitOperationError: git init / commit 失败
        """
        if not name:
            raise ValueError("项目名不能为空")
        self._require_git()

        repo_path = ""  # 由 ORM default 生成 project_id 后填充
        async with await self._get_session() as session:
            # 检查同名项目是否已存在
            existing_stmt = select(ProjectRepo).where(ProjectRepo.name == name)
            existing = (
                await session.execute(existing_stmt)
            ).scalar_one_or_none()
            if existing is not None:
                raise ProjectAlreadyExistsError(f"项目名已存在: {name}")

            # 先创建 ORM 记录获取 project_id（路径需要 project_id 拼接）
            project_orm = ProjectRepo(
                name=name,
                repo_path="__pending__",  # 占位，下面更新
                remote_url=remote_url or None,
                current_branch=branch,
                current_commit=None,
                status=SYNC_STATUS.CLEAN,
                description=description or None,
                author=author or None,
            )
            session.add(project_orm)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise ProjectAlreadyExistsError(
                    f"项目创建失败（可能 name 冲突）: {name}"
                ) from e

            # 刷新以获取 project_id（default 已触发）
            await session.refresh(project_orm)
            project_id = project_orm.project_id
            repo_path = self._get_repo_path(project_id)
            project_orm.repo_path = repo_path
            await session.commit()

        # git init + 初始清单（在锁外执行 git 操作，但用 project lock 保护）
        lock = self._get_project_lock(project_id)
        with lock:
            os.makedirs(repo_path, exist_ok=True)
            try:
                # git init（指定分支名，git 2.28+ 支持 -b）
                self._run_git(["init", "-b", branch], cwd=repo_path)
            except GitOperationError:
                # 旧版 git 不支持 -b，回退到 init + checkout
                self._run_git(["init"], cwd=repo_path)
                try:
                    self._run_git(["checkout", "-b", branch], cwd=repo_path)
                except GitOperationError:
                    pass  # 分支已存在时忽略

            # 配置远端（若提供）
            if remote_url:
                self._run_git(
                    ["remote", "add", "origin", remote_url], cwd=repo_path
                )

            # 写入初始清单
            manifest_dict = self._build_manifest_dict(project_orm, refs=[])
            self._write_manifest_yaml(repo_path, manifest_dict)

            head_sha = ""
            if initial_commit:
                self._run_git(["add", self._MANIFEST_FILENAME], cwd=repo_path)
                self._run_git(
                    ["commit", "-m", f"chore(project): init {name}"],
                    cwd=repo_path,
                )
                head_res = self._run_git(["rev-parse", "HEAD"], cwd=repo_path)
                head_sha = head_res.stdout.strip()

            # 更新 DB 中的 current_commit + 写入 init SyncRecord
            async with await self._get_session() as session:
                stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(stmt)).scalar_one()
                project_orm.current_commit = head_sha or None
                project_orm.status = SYNC_STATUS.CLEAN
                await self._record_sync(
                    session,
                    project_id,
                    SYNC_DIRECTIONS.INIT,
                    commit_sha=head_sha,
                    status="success",
                    message=f"初始化项目 {name}",
                    details={"branch": branch, "remote_url": remote_url},
                )
                await session.commit()

        logger.info("Created project_sync project: %s (%s)", name, project_id)
        return await self.get_project(project_id, include_refs=False)

    async def get_project(
        self,
        project_id: str,
        *,
        include_refs: bool = False,
        include_records: bool = False,
    ) -> dict[str, Any]:
        """获取项目详情.

        Raises:
            ProjectNotFoundError: 项目不存在
        """
        async with await self._get_session() as session:
            stmt = select(ProjectRepo).where(
                ProjectRepo.project_id == project_id
            )
            project_orm = (await session.execute(stmt)).scalar_one_or_none()
            if project_orm is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")
            return project_orm.to_dict(
                include_refs=include_refs,
                include_records=include_records,
            )

    async def list_projects(
        self,
        *,
        status_filter: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """分页列出项目（按 updated_at 倒序）."""
        limit = max(1, min(100, limit))
        offset = max(0, offset)

        async with await self._get_session() as session:
            stmt = select(ProjectRepo)
            count_stmt = select(func.count()).select_from(ProjectRepo)

            if status_filter:
                if not SYNC_STATUS.is_valid(status_filter):
                    raise ValueError(f"status_filter 不支持: {status_filter}")
                stmt = stmt.where(ProjectRepo.status == status_filter)
                count_stmt = count_stmt.where(ProjectRepo.status == status_filter)
            if author:
                stmt = stmt.where(ProjectRepo.author == author)
                count_stmt = count_stmt.where(ProjectRepo.author == author)

            total = (await session.execute(count_stmt)).scalar() or 0
            stmt = (
                stmt.order_by(desc(ProjectRepo.updated_at))
                .limit(limit)
                .offset(offset)
            )
            items = [
                row.to_dict()
                for row in (await session.execute(stmt)).scalars().all()
            ]
            return {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    async def delete_project(
        self, project_id: str, *, delete_repo_dir: bool = True
    ) -> dict[str, Any]:
        """删除项目（DB 记录 + 可选删除仓库目录）.

        Args:
            project_id: 项目 ID
            delete_repo_dir: 是否物理删除本地仓库目录（默认 True）

        Raises:
            ProjectNotFoundError: 项目不存在
        """
        # 先获取 repo_path 用于后续删除
        async with await self._get_session() as session:
            stmt = select(ProjectRepo).where(
                ProjectRepo.project_id == project_id
            )
            project_orm = (await session.execute(stmt)).scalar_one_or_none()
            if project_orm is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")
            repo_path = project_orm.repo_path
            # 删除 DB 记录（级联删除 resource_refs + sync_records）
            await session.delete(project_orm)
            await session.commit()

        # 物理删除仓库目录
        if delete_repo_dir and repo_path and os.path.isdir(repo_path):
            try:
                shutil.rmtree(repo_path)
            except OSError as e:
                logger.warning(
                    "ProjectSyncService: 删除仓库目录失败 (%s): %s",
                    repo_path,
                    e,
                )

        # 清理 project lock
        with self._project_locks_guard:
            self._project_locks.pop(project_id, None)

        logger.info("Deleted project_sync project: %s", project_id)
        return {"project_id": project_id, "deleted": True}

    # ------------------------------------------------------------------
    # 资源引用管理
    # ------------------------------------------------------------------

    async def add_resource_ref(
        self,
        project_id: str,
        resource_type: str,
        resource_uri: str,
        *,
        sync_strategy: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        compute_hash: bool = True,
    ) -> dict[str, Any]:
        """添加资源引用到项目.

        Args:
            project_id: 所属项目 ID
            resource_type: RESOURCE_TYPES 之一
            resource_uri: 资源 URI（scheme 必须与 resource_type 一致）
            sync_strategy: 同步策略（None 使用 DEFAULT_SYNC_STRATEGY）
            metadata: 附加元数据
            compute_hash: 是否立即计算 content_hash

        Returns:
            创建的资源引用 dict

        Raises:
            ProjectNotFoundError: 项目不存在
            ResourceRefAlreadyExistsError: 资源 URI 已存在
            ValueError: 参数非法
        """
        if not RESOURCE_TYPES.is_valid(resource_type):
            raise ValueError(f"resource_type 不支持: {resource_type}")
        # 校验 URI scheme 与 resource_type 一致
        scheme, _ = parse_resource_uri(resource_uri)
        if scheme != resource_type:
            raise ValueError(
                f"URI scheme ({scheme}) 与 resource_type ({resource_type}) 不匹配"
            )
        strategy = sync_strategy or DEFAULT_SYNC_STRATEGY[resource_type]
        if not SYNC_STRATEGIES.is_valid(strategy):
            raise ValueError(f"sync_strategy 不支持: {strategy}")

        content_hash = ""
        if compute_hash:
            content_hash = await self._compute_content_hash(
                resource_type, resource_uri
            )

        async with await self._get_session() as session:
            # 校验项目存在
            p_stmt = select(ProjectRepo).where(
                ProjectRepo.project_id == project_id
            )
            project_orm = (await session.execute(p_stmt)).scalar_one_or_none()
            if project_orm is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")

            # 校验 URI 不重复
            dup_stmt = select(ProjectResourceRef).where(
                ProjectResourceRef.project_id == project_id,
                ProjectResourceRef.resource_uri == resource_uri,
            )
            if (
                await session.execute(dup_stmt)
            ).scalar_one_or_none() is not None:
                raise ResourceRefAlreadyExistsError(
                    f"资源 URI 已存在: {resource_uri}"
                )

            ref_orm = ProjectResourceRef(
                project_id=project_id,
                resource_type=resource_type,
                resource_uri=resource_uri,
                content_hash=content_hash or None,
                sync_strategy=strategy,
                metadata_json=metadata or {},
            )
            session.add(ref_orm)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise ResourceRefAlreadyExistsError(
                    f"资源 URI 已存在: {resource_uri}"
                ) from e

            # 项目状态置 dirty（资源引用变化未 commit）
            project_orm.status = SYNC_STATUS.DIRTY
            await session.commit()

        logger.info(
            "Added resource ref to project %s: %s",
            project_id,
            resource_uri,
        )
        return ref_orm.to_dict()

    async def remove_resource_ref(
        self, project_id: str, resource_uri: str
    ) -> dict[str, Any]:
        """删除资源引用.

        Raises:
            ProjectNotFoundError: 项目不存在
            ResourceRefNotFoundError: 资源引用不存在
        """
        async with await self._get_session() as session:
            p_stmt = select(ProjectRepo).where(
                ProjectRepo.project_id == project_id
            )
            project_orm = (await session.execute(p_stmt)).scalar_one_or_none()
            if project_orm is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")

            ref_stmt = select(ProjectResourceRef).where(
                ProjectResourceRef.project_id == project_id,
                ProjectResourceRef.resource_uri == resource_uri,
            )
            ref_orm = (await session.execute(ref_stmt)).scalar_one_or_none()
            if ref_orm is None:
                raise ResourceRefNotFoundError(
                    f"资源引用不存在: {resource_uri}"
                )

            await session.delete(ref_orm)
            project_orm.status = SYNC_STATUS.DIRTY
            await session.commit()

        logger.info(
            "Removed resource ref from project %s: %s",
            project_id,
            resource_uri,
        )
        return {
            "project_id": project_id,
            "resource_uri": resource_uri,
            "deleted": True,
        }

    async def update_resource_hash(
        self, project_id: str, resource_uri: str
    ) -> dict[str, Any]:
        """重新计算并更新资源引用的 content_hash.

        Raises:
            ProjectNotFoundError: 项目不存在
            ResourceRefNotFoundError: 资源引用不存在
        """
        async with await self._get_session() as session:
            ref_stmt = select(ProjectResourceRef).where(
                ProjectResourceRef.project_id == project_id,
                ProjectResourceRef.resource_uri == resource_uri,
            )
            ref_orm = (await session.execute(ref_stmt)).scalar_one_or_none()
            if ref_orm is None:
                # 区分项目不存在 vs 资源不存在
                p_stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                if (
                    await session.execute(p_stmt)
                ).scalar_one_or_none() is None:
                    raise ProjectNotFoundError(f"项目不存在: {project_id}")
                raise ResourceRefNotFoundError(
                    f"资源引用不存在: {resource_uri}"
                )

            old_hash = ref_orm.content_hash or ""
            new_hash = await self._compute_content_hash(
                ref_orm.resource_type, ref_orm.resource_uri
            )
            ref_orm.content_hash = new_hash or None
            await session.commit()

        return {
            "project_id": project_id,
            "resource_uri": resource_uri,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "changed": old_hash != new_hash,
        }

    async def list_resource_refs(
        self,
        project_id: str,
        *,
        resource_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """列出项目的资源引用（可选按类型过滤）."""
        if resource_type is not None and not RESOURCE_TYPES.is_valid(resource_type):
            raise ValueError(f"resource_type 不支持: {resource_type}")

        async with await self._get_session() as session:
            # 校验项目存在
            p_stmt = select(ProjectRepo.project_id).where(
                ProjectRepo.project_id == project_id
            )
            if (await session.execute(p_stmt)).first() is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")

            stmt = select(ProjectResourceRef).where(
                ProjectResourceRef.project_id == project_id
            )
            if resource_type:
                stmt = stmt.where(
                    ProjectResourceRef.resource_type == resource_type
                )
            stmt = stmt.order_by(ProjectResourceRef.created_at)
            refs = [
                row.to_dict()
                for row in (await session.execute(stmt)).scalars().all()
            ]
            return {"project_id": project_id, "resource_refs": refs}

    # ------------------------------------------------------------------
    # Git 同步操作
    # ------------------------------------------------------------------

    async def get_project_status(self, project_id: str) -> dict[str, Any]:
        """查询项目当前 Git 状态（执行 git status）.

        返回的字段：
            - project_id / name / status（推导后的 SYNC_STATUS）
            - porcelain / head_sha / ahead / behind / has_remote
            - 更新 DB 中的 current_commit / status

        Raises:
            ProjectNotFoundError: 项目不存在
            GitUnavailableError: git 不可用
        """
        async with await self._get_session() as session:
            stmt = select(ProjectRepo).where(
                ProjectRepo.project_id == project_id
            )
            project_orm = (await session.execute(stmt)).scalar_one_or_none()
            if project_orm is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")
            repo_path = project_orm.repo_path
            name = project_orm.name

        if not os.path.isdir(repo_path):
            raise ProjectNotFoundError(
                f"项目仓库目录不存在: {repo_path}"
            )

        git_status = self._query_git_status(repo_path)
        derived = self._derive_status(git_status)

        # 更新 DB 中的 current_commit + status
        async with await self._get_session() as session:
            stmt = select(ProjectRepo).where(
                ProjectRepo.project_id == project_id
            )
            project_orm = (await session.execute(stmt)).scalar_one()
            project_orm.current_commit = git_status["head_sha"] or None
            project_orm.status = derived
            await session.commit()

        return {
            "project_id": project_id,
            "name": name,
            "status": derived,
            "porcelain": git_status["porcelain"],
            "head_sha": git_status["head_sha"],
            "ahead": git_status["ahead"],
            "behind": git_status["behind"],
            "has_remote": git_status["has_remote"],
        }

    async def commit_project(
        self,
        project_id: str,
        message: str,
    ) -> dict[str, Any]:
        """提交项目变更（更新清单 + git add + git commit）.

        流程：
            1. 重新计算所有资源引用的 content_hash
            2. 更新 .lomo-project.yaml 清单
            3. git add .lomo-project.yaml
            4. git commit -m <message>
            5. 更新 DB current_commit + status
            6. 写入 SyncRecord

        Args:
            project_id: 项目 ID
            message: commit message

        Returns:
            {project_id, commit_sha, status, changed_refs}

        Raises:
            ProjectNotFoundError: 项目不存在
            GitUnavailableError: git 不可用
            GitOperationError: git commit 失败
        """
        if not message:
            raise ValueError("commit message 不能为空")
        self._require_git()

        lock = self._get_project_lock(project_id)
        with lock:
            async with await self._get_session() as session:
                stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(stmt)).scalar_one_or_none()
                if project_orm is None:
                    raise ProjectNotFoundError(f"项目不存在: {project_id}")
                repo_path = project_orm.repo_path

                # 加载所有资源引用
                refs_stmt = (
                    select(ProjectResourceRef)
                    .where(ProjectResourceRef.project_id == project_id)
                    .order_by(ProjectResourceRef.created_at)
                )
                ref_orms = list(
                    (await session.execute(refs_stmt)).scalars().all()
                )

            if not os.path.isdir(repo_path):
                raise ProjectNotFoundError(
                    f"项目仓库目录不存在: {repo_path}"
                )

            # 重新计算 hash + 检测变更
            changed_refs: list[dict[str, Any]] = []
            for ref_orm in ref_orms:
                old_hash = ref_orm.content_hash or ""
                new_hash = await self._compute_content_hash(
                    ref_orm.resource_type, ref_orm.resource_uri
                )
                if new_hash != old_hash:
                    changed_refs.append(
                        {
                            "resource_uri": ref_orm.resource_uri,
                            "old_hash": old_hash,
                            "new_hash": new_hash,
                        }
                    )
                    # 更新 DB 中的 hash
                    async with await self._get_session() as session:
                        r_stmt = select(ProjectResourceRef).where(
                            ProjectResourceRef.id == ref_orm.id
                        )
                        r_orm = (await session.execute(r_stmt)).scalar_one()
                        r_orm.content_hash = new_hash or None
                        await session.commit()

            # 重新加载 project_orm（前面 session 已关闭）
            async with await self._get_session() as session:
                p_stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(p_stmt)).scalar_one()
                # 加载最新 refs 用于清单
                refs_stmt = (
                    select(ProjectResourceRef)
                    .where(ProjectResourceRef.project_id == project_id)
                    .order_by(ProjectResourceRef.created_at)
                )
                ref_orms = list(
                    (await session.execute(refs_stmt)).scalars().all()
                )
                manifest_dict = self._build_manifest_dict(
                    project_orm, ref_orms
                )

            # 更新清单文件
            self._write_manifest_yaml(repo_path, manifest_dict)

            # git add + commit
            self._run_git(["add", self._MANIFEST_FILENAME], cwd=repo_path)

            # 检查是否有变更待提交
            status_res = self._run_git(
                ["status", "--porcelain"], cwd=repo_path
            )
            commit_sha = ""
            if status_res.stdout.strip():
                self._run_git(
                    ["commit", "-m", message], cwd=repo_path
                )
                head_res = self._run_git(["rev-parse", "HEAD"], cwd=repo_path)
                commit_sha = head_res.stdout.strip()

            # 更新 DB + 写入 SyncRecord
            async with await self._get_session() as session:
                p_stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(p_stmt)).scalar_one()
                if commit_sha:
                    project_orm.current_commit = commit_sha
                project_orm.status = SYNC_STATUS.CLEAN
                await self._record_sync(
                    session,
                    project_id,
                    SYNC_DIRECTIONS.COMMIT,
                    commit_sha=commit_sha,
                    status="success",
                    message=message,
                    details={
                        "changed_refs": len(changed_refs),
                        "had_changes": bool(commit_sha),
                    },
                )
                await session.commit()

        logger.info(
            "Committed project %s: %s (changed_refs=%d)",
            project_id,
            commit_sha[:8] if commit_sha else "<no-changes>",
            len(changed_refs),
        )
        return {
            "project_id": project_id,
            "commit_sha": commit_sha,
            "status": SYNC_STATUS.CLEAN,
            "changed_refs": changed_refs,
        }

    async def push_project(self, project_id: str) -> dict[str, Any]:
        """推送到远端仓库.

        Raises:
            ProjectNotFoundError: 项目不存在
            GitUnavailableError: git 不可用
            InvalidProjectStateError: 未配置远端
            GitOperationError: git push 失败
        """
        self._require_git()
        lock = self._get_project_lock(project_id)
        with lock:
            async with await self._get_session() as session:
                stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(stmt)).scalar_one_or_none()
                if project_orm is None:
                    raise ProjectNotFoundError(f"项目不存在: {project_id}")
                repo_path = project_orm.repo_path
                branch = project_orm.current_branch
                remote_url = project_orm.remote_url or ""

            if not os.path.isdir(repo_path):
                raise ProjectNotFoundError(
                    f"项目仓库目录不存在: {repo_path}"
                )
            if not remote_url:
                raise InvalidProjectStateError(
                    f"项目未配置远端仓库 URL，无法 push: {project_id}"
                )

            push_status = "success"
            push_message = ""
            push_details: dict[str, Any] = {
                "remote_url": remote_url,
                "branch": branch,
            }
            try:
                res = self._run_git(
                    ["push", "origin", branch],
                    cwd=repo_path,
                    timeout=self._GIT_TIMEOUT_LONG,
                )
                push_message = res.stdout.strip() or "push 成功"
            except GitOperationError as e:
                push_status = "failed"
                push_message = e.stderr.strip() or str(e)
                push_details["returncode"] = e.returncode

            # 更新 DB 状态 + 写入 SyncRecord
            async with await self._get_session() as session:
                p_stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(p_stmt)).scalar_one()
                if push_status == "success":
                    project_orm.status = SYNC_STATUS.CLEAN
                else:
                    project_orm.status = SYNC_STATUS.ERROR
                head_sha = project_orm.current_commit or ""
                await self._record_sync(
                    session,
                    project_id,
                    SYNC_DIRECTIONS.PUSH,
                    commit_sha=head_sha,
                    status=push_status,
                    message=push_message,
                    details=push_details,
                )
                await session.commit()

            if push_status != "success":
                raise GitOperationError(
                    ["push", "origin", branch], -1, push_message
                )

        logger.info("Pushed project %s to %s", project_id, remote_url)
        return {
            "project_id": project_id,
            "status": SYNC_STATUS.CLEAN,
            "remote_url": remote_url,
            "branch": branch,
        }

    async def pull_project(self, project_id: str) -> dict[str, Any]:
        """从远端仓库拉取变更.

        Raises:
            ProjectNotFoundError: 项目不存在
            GitUnavailableError: git 不可用
            InvalidProjectStateError: 未配置远端
            GitOperationError: git pull 失败（含冲突）
        """
        self._require_git()
        lock = self._get_project_lock(project_id)
        with lock:
            async with await self._get_session() as session:
                stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(stmt)).scalar_one_or_none()
                if project_orm is None:
                    raise ProjectNotFoundError(f"项目不存在: {project_id}")
                repo_path = project_orm.repo_path
                branch = project_orm.current_branch
                remote_url = project_orm.remote_url or ""

            if not os.path.isdir(repo_path):
                raise ProjectNotFoundError(
                    f"项目仓库目录不存在: {repo_path}"
                )
            if not remote_url:
                raise InvalidProjectStateError(
                    f"项目未配置远端仓库 URL，无法 pull: {project_id}"
                )

            pull_status = "success"
            pull_message = ""
            pull_details: dict[str, Any] = {
                "remote_url": remote_url,
                "branch": branch,
            }
            try:
                res = self._run_git(
                    ["pull", "origin", branch],
                    cwd=repo_path,
                    timeout=self._GIT_TIMEOUT_LONG,
                )
                pull_message = res.stdout.strip() or "pull 成功"
            except GitOperationError as e:
                stderr = e.stderr.lower()
                if "conflict" in stderr or "merge conflict" in stderr:
                    pull_status = "conflict"
                    pull_message = e.stderr.strip()
                else:
                    pull_status = "failed"
                    pull_message = e.stderr.strip() or str(e)
                pull_details["returncode"] = e.returncode

            # 拉取后更新 DB（重新查询 git status）
            new_status = SYNC_STATUS.CLEAN
            new_commit = ""
            if os.path.isdir(repo_path):
                git_status = self._query_git_status(repo_path)
                new_commit = git_status["head_sha"]
                if pull_status == "conflict":
                    new_status = SYNC_STATUS.CONFLICT
                elif pull_status == "failed":
                    new_status = SYNC_STATUS.ERROR
                else:
                    new_status = self._derive_status(git_status)

            async with await self._get_session() as session:
                p_stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(p_stmt)).scalar_one()
                if new_commit:
                    project_orm.current_commit = new_commit
                project_orm.status = new_status
                await self._record_sync(
                    session,
                    project_id,
                    SYNC_DIRECTIONS.PULL,
                    commit_sha=new_commit,
                    status=pull_status,
                    message=pull_message,
                    details=pull_details,
                )
                await session.commit()

            if pull_status != "success":
                raise GitOperationError(
                    ["pull", "origin", branch], -1, pull_message
                )

        logger.info("Pulled project %s from %s", project_id, remote_url)
        return {
            "project_id": project_id,
            "status": new_status,
            "remote_url": remote_url,
            "branch": branch,
        }

    async def clone_project(
        self,
        remote_url: str,
        *,
        name: str = "",
        author: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        """克隆远端项目仓库.

        流程：
            1. 创建 DB 记录获取 project_id
            2. git clone <remote_url> <repo_path>
            3. 解析 .lomo-project.yaml 清单
            4. 同步资源引用到 DB
            5. 写入 clone SyncRecord

        Args:
            remote_url: 远端仓库 URL
            name: 项目显示名（空则使用清单中的 name 或 URL 末段）
            author: 项目作者
            description: 项目描述

        Returns:
            项目详情 dict

        Raises:
            GitUnavailableError: git 不可用
            GitOperationError: git clone 失败
        """
        if not remote_url:
            raise ValueError("remote_url 不能为空")
        self._require_git()

        # 先创建 DB 记录获取 project_id
        async with await self._get_session() as session:
            project_orm = ProjectRepo(
                name=name or remote_url.rstrip("/").split("/")[-1],
                repo_path="__pending__",
                remote_url=remote_url,
                current_branch="main",
                current_commit=None,
                status=SYNC_STATUS.CLEAN,
                description=description or None,
                author=author or None,
            )
            session.add(project_orm)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise ProjectAlreadyExistsError(
                    f"项目创建失败: {name}"
                ) from e
            await session.refresh(project_orm)
            project_id = project_orm.project_id
            repo_path = self._get_repo_path(project_id)
            project_orm.repo_path = repo_path
            await session.commit()

        lock = self._get_project_lock(project_id)
        with lock:
            # 清空目录后 clone（repo_path 由 create_project 创建为空目录）
            if os.path.isdir(repo_path):
                shutil.rmtree(repo_path)
            parent_dir = os.path.dirname(repo_path)
            os.makedirs(parent_dir, exist_ok=True)

            try:
                self._run_git(
                    ["clone", remote_url, repo_path],
                    cwd=parent_dir,
                    timeout=self._GIT_TIMEOUT_LONG,
                )
            except GitOperationError:
                # clone 失败，回滚 DB 记录
                async with await self._get_session() as session:
                    p_stmt = select(ProjectRepo).where(
                        ProjectRepo.project_id == project_id
                    )
                    p_orm = (await session.execute(p_stmt)).scalar_one_or_none()
                    if p_orm is not None:
                        await session.delete(p_orm)
                        await session.commit()
                raise

            # 解析清单
            manifest = self._read_manifest_yaml(repo_path)
            head_sha = ""
            try:
                head_res = self._run_git(["rev-parse", "HEAD"], cwd=repo_path)
                head_sha = head_res.stdout.strip()
            except GitOperationError:
                pass

            # 获取分支名
            try:
                branch_res = self._run_git(
                    ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path
                )
                branch = branch_res.stdout.strip() or "main"
            except GitOperationError:
                branch = "main"

            # 同步清单中的资源引用到 DB
            refs_added = 0
            if manifest and "resource_refs" in manifest:
                async with await self._get_session() as session:
                    for ref_data in manifest["resource_refs"]:
                        ref_orm = ProjectResourceRef(
                            project_id=project_id,
                            resource_type=ref_data.get("resource_type", ""),
                            resource_uri=ref_data.get("resource_uri", ""),
                            content_hash=ref_data.get("content_hash") or None,
                            sync_strategy=ref_data.get(
                                "sync_strategy", SYNC_STRATEGIES.HASH_REFERENCED
                            ),
                            metadata_json=ref_data.get("metadata") or {},
                        )
                        session.add(ref_orm)
                        refs_added += 1
                    await session.commit()

            # 更新 DB + 写入 clone SyncRecord
            async with await self._get_session() as session:
                p_stmt = select(ProjectRepo).where(
                    ProjectRepo.project_id == project_id
                )
                project_orm = (await session.execute(p_stmt)).scalar_one()
                project_orm.current_branch = branch
                project_orm.current_commit = head_sha or None
                project_orm.status = SYNC_STATUS.CLEAN
                if manifest:
                    if not name and manifest.get("name"):
                        project_orm.name = manifest["name"]
                    if manifest.get("description") and not description:
                        project_orm.description = manifest["description"]
                    if manifest.get("author") and not author:
                        project_orm.author = manifest["author"]
                await self._record_sync(
                    session,
                    project_id,
                    SYNC_DIRECTIONS.CLONE,
                    commit_sha=head_sha,
                    status="success",
                    message=f"克隆项目 {remote_url}",
                    details={
                        "remote_url": remote_url,
                        "branch": branch,
                        "refs_added": refs_added,
                    },
                )
                await session.commit()

        logger.info(
            "Cloned project %s from %s (refs=%d)",
            project_id,
            remote_url,
            refs_added,
        )
        return await self.get_project(project_id, include_refs=True)

    # ------------------------------------------------------------------
    # 同步记录查询
    # ------------------------------------------------------------------

    async def list_sync_records(
        self,
        project_id: str,
        *,
        direction: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """列出项目的同步记录（按时间倒序）.

        Raises:
            ProjectNotFoundError: 项目不存在
            ValueError: direction 不支持
        """
        if direction is not None and not SYNC_DIRECTIONS.is_valid(direction):
            raise ValueError(f"direction 不支持: {direction}")
        limit = max(1, min(100, limit))
        offset = max(0, offset)

        async with await self._get_session() as session:
            # 校验项目存在
            p_stmt = select(ProjectRepo.project_id).where(
                ProjectRepo.project_id == project_id
            )
            if (await session.execute(p_stmt)).first() is None:
                raise ProjectNotFoundError(f"项目不存在: {project_id}")

            stmt = select(ProjectSyncRecord).where(
                ProjectSyncRecord.project_id == project_id
            )
            count_stmt = select(func.count()).select_from(
                ProjectSyncRecord
            ).where(ProjectSyncRecord.project_id == project_id)
            if direction:
                stmt = stmt.where(ProjectSyncRecord.direction == direction)
                count_stmt = count_stmt.where(
                    ProjectSyncRecord.direction == direction
                )

            total = (await session.execute(count_stmt)).scalar() or 0
            stmt = (
                stmt.order_by(desc(ProjectSyncRecord.timestamp))
                .limit(limit)
                .offset(offset)
            )
            records = [
                row.to_dict()
                for row in (await session.execute(stmt)).scalars().all()
            ]
            return {
                "project_id": project_id,
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset,
            }


__all__ = [
    "ProjectSyncService",
    "get_project_sync_service",
    # 异常类
    "ProjectSyncError",
    "ProjectNotFoundError",
    "ProjectAlreadyExistsError",
    "GitUnavailableError",
    "GitOperationError",
    "ResourceRefNotFoundError",
    "ResourceRefAlreadyExistsError",
    "InvalidProjectStateError",
]
