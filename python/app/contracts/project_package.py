"""项目导入导出契约：定义 ``.lomo`` 包格式与导入导出操作的数据结构.

对应 ADR-015（项目导入导出）。本文件只定义数据结构与接口契约，
实现见 app/services/project_package_service.py（服务层）、
app/api/v1/project_packages.py（路由层）、
app/database/models/project_package.py（ORM 持久化）。

契约稳定性：Stable（v1.0.0），向后兼容扩展。

设计要点：
    1. ``.lomo`` 包本质是 ZIP 归档（扩展名 ``.lomo``），与 ADR-011 Git 同步互补——
       Git 同步是"引用同步"（仅 hash），``.lomo`` 包是"内容同步"（含文件）
    2. ``manifest.json`` 是包清单，含格式版本 + 项目元数据 + 资源清单 + 校验和，
       导入时优先校验 ``format_version`` 兼容性，再校验 ``checksum`` 完整性
    3. ``ContentPolicy`` 决定打包范围：``metadata_only`` / ``include_content`` /
       ``small_files_only``，适配车间大文件与网络受限场景
    4. ``ConflictStrategy`` 决定冲突处理：``skip`` / ``overwrite`` / ``rename`` /
       ``fail``，覆盖安全导入与事务性导入需求
    5. 资源 URI 体系与 ADR-005 / ADR-011 / ADR-012 对齐：
       ``dataset://<dataset_id>/<version>`` / ``model://<name>/<version>`` /
       ``workflow://<run_id>`` / ``config://<spec_name>`` / ``snapshot://<snapshot_id>``

包文件结构详见 ADR-015 第 1 节。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 包格式版本常量
# ---------------------------------------------------------------------------


class PackageFormatVersion:
    """``.lomo`` 包格式版本常量.

    遵循 semver：``MAJOR.MINOR.PATCH``。
    - MAJOR：不兼容的清单结构变更（如字段重命名 / 删除）
    - MINOR：向后兼容的字段新增（导入旧版本包仍可用）
    - PATCH：错误修复与澄清

    导入时校验 ``manifest.format_version`` 的 MAJOR 是否与当前版本一致；
    MINOR / PATCH 差异通过兼容性矩阵处理。
    """

    V1_0_0 = "1.0.0"  # 初始版本：ZIP + manifest.json + 内容寻址

    CURRENT = V1_0_0  # 当前实现版本

    @classmethod
    def all(cls) -> list[str]:
        """返回所有支持的包格式版本."""
        return [cls.V1_0_0]

    @classmethod
    def is_supported(cls, version: str) -> bool:
        """判断包格式版本是否受支持.

        Args:
            version: 待校验的版本字符串

        Returns:
            True 表示当前实现可读取该版本包
        """
        return version in cls.all()

    @classmethod
    def is_major_compatible(cls, version: str) -> bool:
        """判断包格式版本的 MAJOR 段是否与当前版本一致.

        用于导入时兼容性预检：MAJOR 一致表示清单结构兼容，
        可尝试导入（MINOR / PATCH 差异由字段缺省值兜底）。

        Args:
            version: 待校验的版本字符串

        Returns:
            True 表示 MAJOR 段一致
        """
        if not version or "." not in version:
            return False
        try:
            major = int(version.split(".", 1)[0])
            current_major = int(cls.CURRENT.split(".", 1)[0])
            return major == current_major
        except (ValueError, IndexError):
            return False


# ---------------------------------------------------------------------------
# 内容策略常量
# ---------------------------------------------------------------------------


class ContentPolicy:
    """内容策略常量：决定 ``.lomo`` 包打包资源内容的范围.

    - ``METADATA_ONLY``：仅打包元数据，不打包资源内容。适用项目结构分享、
      文档归档场景。包体积小，但导入后无法直接运行工作流。
    - ``INCLUDE_CONTENT``：打包所有资源内容（默认）。适用跨机器迁移、
      完整备份场景。包体积大，但导入后立即可用。
    - ``SMALL_FILES_ONLY``：仅打包 ≤ ``max_file_size_bytes`` 的资源文件，
      大文件仅元数据。适用网络受限场景（如邮件附件），平衡包体积与可用性。
    """

    METADATA_ONLY = "metadata_only"
    INCLUDE_CONTENT = "include_content"
    SMALL_FILES_ONLY = "small_files_only"

    @classmethod
    def all(cls) -> list[str]:
        """返回所有内容策略."""
        return [cls.METADATA_ONLY, cls.INCLUDE_CONTENT, cls.SMALL_FILES_ONLY]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """判断内容策略是否合法."""
        return value in cls.all()

    @classmethod
    def default(cls) -> str:
        """返回默认内容策略."""
        return cls.INCLUDE_CONTENT


# ---------------------------------------------------------------------------
# 冲突策略常量
# ---------------------------------------------------------------------------


class ConflictStrategy:
    """冲突策略常量：导入时目标机器已存在同 URI 资源的处理方式.

    - ``SKIP``：跳过冲突资源（保留目标机器已有版本，默认）。最安全，但可能
      导致项目状态与源机器不一致。
    - ``OVERWRITE``：覆盖目标机器已有版本。危险，需前端二次确认；适用于
      目标机器资源明显过时的场景。
    - ``RENAME``：重命名导入资源（URI 追加 ``_imported_<timestamp>`` 后缀）。
      保留两份资源，由用户后续手动合并。
    - ``FAIL``：遇到冲突立即报错，不导入任何资源（事务性）。适用于要求
      "全有或全无"的批量导入场景。
    """

    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"
    FAIL = "fail"

    @classmethod
    def all(cls) -> list[str]:
        """返回所有冲突策略."""
        return [cls.SKIP, cls.OVERWRITE, cls.RENAME, cls.FAIL]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """判断冲突策略是否合法."""
        return value in cls.all()

    @classmethod
    def default(cls) -> str:
        """返回默认冲突策略."""
        return cls.SKIP


# ---------------------------------------------------------------------------
# 任务状态常量（导出 / 导入共用）
# ---------------------------------------------------------------------------


class PackageTaskStatus:
    """包任务状态常量：导出 / 导入任务的异步执行状态.

    状态机：
        PENDING → RUNNING → COMPLETED
                ↘ FAILED
    """

    PENDING = "pending"  # 已创建任务记录，未开始执行
    RUNNING = "running"  # 正在执行（导出打包 / 导入解压）
    COMPLETED = "completed"  # 成功完成
    FAILED = "failed"  # 执行失败（error_message 记录原因）

    @classmethod
    def all(cls) -> list[str]:
        """返回所有任务状态."""
        return [cls.PENDING, cls.RUNNING, cls.COMPLETED, cls.FAILED]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """判断任务状态是否合法."""
        return value in cls.all()

    @classmethod
    def is_terminal(cls, value: str) -> bool:
        """判断任务状态是否为终态（不可再变更）."""
        return value in (cls.COMPLETED, cls.FAILED)


# ---------------------------------------------------------------------------
# 默认值常量
# ---------------------------------------------------------------------------


#: ``small_files_only`` 策略的默认文件大小阈值（10 MB）。
DEFAULT_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024

#: 流式读写缓冲区大小（64 KB），避免内存爆炸。
STREAM_BUFFER_SIZE: int = 64 * 1024

#: ``.lomo`` 包文件扩展名。
PACKAGE_FILE_EXTENSION: str = ".lomo"

#: 导出包文件名模板（``<project_name>_<timestamp>.lomo``）。
PACKAGE_FILENAME_TEMPLATE: str = "{name}_{timestamp}.lomo"

#: 源机器信息兜底默认值（socket.gethostname() / platform.system() 返回空时使用）。
SOURCE_MACHINE_INFO_DEFAULTS: dict[str, str] = {
    "hostname": "unknown-host",
    "app_version": "4.0.0",
    "platform": "unknown",
}


# ---------------------------------------------------------------------------
# 数据结构：包资源条目
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageResourceEntry:
    """包资源条目契约：``manifest.resources`` 数组中的一项.

    一个 PackageResourceEntry 对应包内一个资源文件，记录其 URI / 内容 hash /
    包内相对路径 / 大小 / 元数据。导入时按 ``resource_uri`` 寻址目标位置，
    按 ``content_hash`` 校验完整性。

    属性:
        resource_type: 资源类型（dataset/model/workflow/config/snapshot/lineage）
        resource_uri: 资源 URI（与 ADR-005 / ADR-011 / ADR-012 对齐）
        content_hash: 内容 sha256，格式 ``sha256:<hex>``；元数据策略下为空字符串
        path_in_package: 包内相对路径（如 ``datasets/<id>/versions/1.0.0/data.parquet``）
        size_bytes: 资源文件大小（字节）；元数据策略下为 0
        metadata: 资源元数据（如 row_count / schema / model_type / framework）
    """

    resource_type: str
    resource_uri: str
    content_hash: str
    path_in_package: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.resource_type:
            raise ValueError("PackageResourceEntry.resource_type 不能为空")
        if not self.resource_uri:
            raise ValueError("PackageResourceEntry.resource_uri 不能为空")
        if not self.path_in_package:
            raise ValueError("PackageResourceEntry.path_in_package 不能为空")
        if self.size_bytes < 0:
            raise ValueError(
                f"PackageResourceEntry.size_bytes 不能为负数: {self.size_bytes}"
            )

    @property
    def has_content(self) -> bool:
        """是否包含内容（content_hash 非空且 size_bytes > 0）."""
        return bool(self.content_hash) and self.size_bytes > 0

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 manifest.json 与 API 响应）."""
        return {
            "resource_type": self.resource_type,
            "resource_uri": self.resource_uri,
            "content_hash": self.content_hash,
            "path_in_package": self.path_in_package,
            "size_bytes": self.size_bytes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageResourceEntry":
        """从 dict 反序列化（用于读取 manifest.json）."""
        return cls(
            resource_type=str(data["resource_type"]),
            resource_uri=str(data["resource_uri"]),
            content_hash=str(data.get("content_hash", "")),
            path_in_package=str(data["path_in_package"]),
            size_bytes=int(data.get("size_bytes", 0)),
            metadata=dict(data.get("metadata") or {}),
        )


# ---------------------------------------------------------------------------
# 数据结构：源机器信息
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceMachineInfo:
    """源机器信息契约：导出时记录源机器环境，用于诊断兼容性问题.

    属性:
        hostname: 主机名（如 ``workshop-pc-01``）
        app_version: 导出时应用版本（如 ``4.0.0``）
        platform: 平台标识（``win32`` / ``linux`` / ``darwin``）
    """

    hostname: str
    app_version: str
    platform: str

    def __post_init__(self) -> None:
        if not self.hostname:
            raise ValueError("SourceMachineInfo.hostname 不能为空")
        if not self.app_version:
            raise ValueError("SourceMachineInfo.app_version 不能为空")
        if not self.platform:
            raise ValueError("SourceMachineInfo.platform 不能为空")

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict."""
        return {
            "hostname": self.hostname,
            "app_version": self.app_version,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceMachineInfo":
        """从 dict 反序列化."""
        return cls(
            hostname=str(data["hostname"]),
            app_version=str(data["app_version"]),
            platform=str(data["platform"]),
        )


# ---------------------------------------------------------------------------
# 数据结构：包项目元数据
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageProjectInfo:
    """包项目元数据契约：``manifest.project`` 字段.

    与 ADR-011 ``ProjectSyncManifest`` 的核心字段对齐，导入时用于创建目标项目
    或匹配已有项目。

    属性:
        project_id: 源项目 ID（UUID）；导入时若 ``reinit_git=True`` 会生成新 ID
        name: 项目显示名
        description: 项目描述
        author: 项目作者
        remote_url: 源项目远端仓库 URL（空字符串表示纯本地项目）
        current_branch: 源项目当前分支名
        current_commit: 源项目当前 HEAD commit sha
    """

    project_id: str
    name: str
    description: str = ""
    author: str = ""
    remote_url: str = ""
    current_branch: str = "main"
    current_commit: str = ""

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("PackageProjectInfo.project_id 不能为空")
        if not self.name:
            raise ValueError("PackageProjectInfo.name 不能为空")
        if not self.current_branch:
            raise ValueError("PackageProjectInfo.current_branch 不能为空")

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "remote_url": self.remote_url,
            "current_branch": self.current_branch,
            "current_commit": self.current_commit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageProjectInfo":
        """从 dict 反序列化."""
        return cls(
            project_id=str(data["project_id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            remote_url=str(data.get("remote_url", "")),
            current_branch=str(data.get("current_branch", "main")),
            current_commit=str(data.get("current_commit", "")),
        )


# ---------------------------------------------------------------------------
# 数据结构：包清单
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageManifest:
    """包清单契约：``.lomo`` 包的 ``manifest.json`` 投影.

    一个 PackageManifest 对应一个 ``.lomo`` 包，记录格式版本 + 导出时间 +
    导出者 + 源机器 + 项目元数据 + 资源清单 + 内容策略 + 总大小 + 校验和。

    属性:
        format_version: 包格式版本（PackageFormatVersion 常量）
        exported_at: 导出时间（ISO8601 字符串）
        exported_by: 导出者 user_id 或 plugin_id
        source_machine: 源机器信息
        project: 项目元数据
        resources: 资源清单（按 resource_uri 唯一）
        content_policy: 内容策略（ContentPolicy 常量）
        total_size_bytes: 包内所有资源文件总大小（未压缩前）
        checksum: manifest.json 自身的 sha256（不含此字段），由服务层计算
    """

    format_version: str
    exported_at: str
    exported_by: str
    source_machine: SourceMachineInfo
    project: PackageProjectInfo
    resources: tuple[PackageResourceEntry, ...] = field(default_factory=tuple)
    content_policy: str = ContentPolicy.INCLUDE_CONTENT
    total_size_bytes: int = 0
    checksum: str = ""

    def __post_init__(self) -> None:
        if not PackageFormatVersion.is_supported(self.format_version):
            raise ValueError(
                f"PackageManifest.format_version 不受支持: {self.format_version}，"
                f"受支持版本: {PackageFormatVersion.all()}"
            )
        if not self.exported_at:
            raise ValueError("PackageManifest.exported_at 不能为空")
        if not self.exported_by:
            raise ValueError("PackageManifest.exported_by 不能为空")
        if not ContentPolicy.is_valid(self.content_policy):
            raise ValueError(
                f"PackageManifest.content_policy 不合法: {self.content_policy}，"
                f"合法值: {ContentPolicy.all()}"
            )
        if self.total_size_bytes < 0:
            raise ValueError(
                f"PackageManifest.total_size_bytes 不能为负数: {self.total_size_bytes}"
            )
        # resources 唯一性校验
        uris = [entry.resource_uri for entry in self.resources]
        if len(uris) != len(set(uris)):
            raise ValueError(
                "PackageManifest.resources 存在重复的 resource_uri"
            )

    @property
    def resource_count(self) -> int:
        """资源条目数量."""
        return len(self.resources)

    @property
    def has_content(self) -> bool:
        """是否包含任何资源内容（至少一个条目 has_content=True）."""
        return any(entry.has_content for entry in self.resources)

    def get_entry(self, resource_uri: str) -> Optional[PackageResourceEntry]:
        """按 URI 查询资源条目."""
        for entry in self.resources:
            if entry.resource_uri == resource_uri:
                return entry
        return None

    def list_entries_by_type(self, resource_type: str) -> list[PackageResourceEntry]:
        """按资源类型过滤资源条目."""
        return [
            entry for entry in self.resources if entry.resource_type == resource_type
        ]

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 manifest.json 写入）.

        注意：``checksum`` 字段由服务层在写入 manifest.json 后单独计算并回填，
        此处序列化时若 ``checksum`` 为空则不写入该字段（避免空值污染清单）。
        """
        result: dict[str, Any] = {
            "format_version": self.format_version,
            "exported_at": self.exported_at,
            "exported_by": self.exported_by,
            "source_machine": self.source_machine.to_dict(),
            "project": self.project.to_dict(),
            "resources": [entry.to_dict() for entry in self.resources],
            "content_policy": self.content_policy,
            "total_size_bytes": self.total_size_bytes,
        }
        if self.checksum:
            result["checksum"] = self.checksum
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageManifest":
        """从 dict 反序列化（用于读取 manifest.json）."""
        resources_data = data.get("resources") or []
        return cls(
            format_version=str(data["format_version"]),
            exported_at=str(data["exported_at"]),
            exported_by=str(data["exported_by"]),
            source_machine=SourceMachineInfo.from_dict(
                data["source_machine"]  # type: ignore[arg-type]
            ),
            project=PackageProjectInfo.from_dict(
                data["project"]  # type: ignore[arg-type]
            ),
            resources=tuple(
                PackageResourceEntry.from_dict(item) for item in resources_data
            ),
            content_policy=str(data.get("content_policy", ContentPolicy.default())),
            total_size_bytes=int(data.get("total_size_bytes", 0)),
            checksum=str(data.get("checksum", "")),
        )


# ---------------------------------------------------------------------------
# 数据结构：导出选项
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportOptions:
    """导出选项契约：``POST /export`` 请求体的核心字段.

    属性:
        content_policy: 内容策略（ContentPolicy 常量，默认 INCLUDE_CONTENT）
        include_datasets: 是否打包数据集资源（默认 True）
        include_models: 是否打包模型产物资源（默认 True）
        include_workflows: 是否打包工作流定义（默认 True）
        include_configs: 是否打包配置规格（默认 True）
        include_snapshots: 是否打包实验快照元数据（默认 True）
        include_lineage: 是否打包血缘记录（默认 True）
        max_file_size_bytes: ``small_files_only`` 策略下的文件大小阈值，
            默认 10MB（``DEFAULT_MAX_FILE_SIZE_BYTES``）
        output_filename: 自定义输出文件名（不含路径，服务层追加扩展名）；
            空字符串表示使用默认模板 ``<project_name>_<timestamp>.lomo``
    """

    content_policy: str = ContentPolicy.INCLUDE_CONTENT
    include_datasets: bool = True
    include_models: bool = True
    include_workflows: bool = True
    include_configs: bool = True
    include_snapshots: bool = True
    include_lineage: bool = True
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES
    output_filename: str = ""

    def __post_init__(self) -> None:
        if not ContentPolicy.is_valid(self.content_policy):
            raise ValueError(
                f"ExportOptions.content_policy 不合法: {self.content_policy}，"
                f"合法值: {ContentPolicy.all()}"
            )
        if self.max_file_size_bytes <= 0:
            raise ValueError(
                f"ExportOptions.max_file_size_bytes 必须为正数: {self.max_file_size_bytes}"
            )

    def should_include(self, resource_type: str) -> bool:
        """根据资源类型判断是否打包.

        Args:
            resource_type: 资源类型（dataset/model/workflow/config/snapshot/lineage）

        Returns:
            True 表示该类型资源应被打包
        """
        mapping = {
            "dataset": self.include_datasets,
            "model": self.include_models,
            "workflow": self.include_workflows,
            "config": self.include_configs,
            "snapshot": self.include_snapshots,
            "lineage": self.include_lineage,
        }
        return mapping.get(resource_type, True)

    def should_pack_content(self, size_bytes: int) -> bool:
        """根据内容策略与文件大小判断是否打包内容.

        Args:
            size_bytes: 资源文件大小（字节）

        Returns:
            True 表示应打包该资源的内容
        """
        if self.content_policy == ContentPolicy.METADATA_ONLY:
            return False
        if self.content_policy == ContentPolicy.INCLUDE_CONTENT:
            return True
        # SMALL_FILES_ONLY
        return size_bytes <= self.max_file_size_bytes

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict."""
        return {
            "content_policy": self.content_policy,
            "include_datasets": self.include_datasets,
            "include_models": self.include_models,
            "include_workflows": self.include_workflows,
            "include_configs": self.include_configs,
            "include_snapshots": self.include_snapshots,
            "include_lineage": self.include_lineage,
            "max_file_size_bytes": self.max_file_size_bytes,
            "output_filename": self.output_filename,
        }


# ---------------------------------------------------------------------------
# 数据结构：导入选项
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportOptions:
    """导入选项契约：``POST /import`` 请求体的核心字段.

    属性:
        conflict_strategy: 冲突策略（ConflictStrategy 常量，默认 SKIP）
        target_owner_id: 导入资源的目标所有者 user_id（默认继承源 manifest.exported_by）
        reinit_git: 导入后是否重新 ``git init``（默认 True）；False 时仅在文件系统
            恢复资源，不创建 Git 仓库
        dry_run: 仅校验不实际写入（默认 False）；True 时服务层返回预导入结果，
            不修改任何文件或数据库
        target_project_name: 目标项目名（空字符串表示使用源 manifest.project.name）；
            用于"导入为副本"场景
    """

    conflict_strategy: str = ConflictStrategy.SKIP
    target_owner_id: str = ""
    reinit_git: bool = True
    dry_run: bool = False
    target_project_name: str = ""

    def __post_init__(self) -> None:
        if not ConflictStrategy.is_valid(self.conflict_strategy):
            raise ValueError(
                f"ImportOptions.conflict_strategy 不合法: {self.conflict_strategy}，"
                f"合法值: {ConflictStrategy.all()}"
            )

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict."""
        return {
            "conflict_strategy": self.conflict_strategy,
            "target_owner_id": self.target_owner_id,
            "reinit_git": self.reinit_git,
            "dry_run": self.dry_run,
            "target_project_name": self.target_project_name,
        }


# ---------------------------------------------------------------------------
# 数据结构：导出结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportResult:
    """导出结果契约：``ProjectPackageService.export_project()`` 返回值.

    属性:
        export_id: 导出任务 ID（``pexp_`` 前缀 + uuid）
        project_id: 源项目 ID
        package_path: 生成的 ``.lomo`` 文件绝对路径
        manifest: 包清单（含 checksum）
        resource_count: 资源条目总数
        packed_count: 实际打包内容的资源数（含内容的条目数）
        skipped_resources: 因策略跳过的资源 URI 列表（如 small_files_only 策略下
            的大文件）
        total_size_bytes: 包内所有资源文件总大小（未压缩前）
        package_size_bytes: ``.lomo`` 文件实际大小（压缩后）
        status: 任务状态（PackageTaskStatus 常量）
        error_message: 失败原因（status=FAILED 时非空）
        created_at: 任务创建时间
        completed_at: 任务完成时间（status=COMPLETED/FAILED 时非空）
    """

    export_id: str
    project_id: str
    package_path: str
    manifest: PackageManifest
    resource_count: int
    packed_count: int
    skipped_resources: tuple[str, ...] = field(default_factory=tuple)
    total_size_bytes: int = 0
    package_size_bytes: int = 0
    status: str = PackageTaskStatus.COMPLETED
    error_message: str = ""
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.export_id:
            raise ValueError("ExportResult.export_id 不能为空")
        if not self.project_id:
            raise ValueError("ExportResult.project_id 不能为空")
        if not self.package_path:
            raise ValueError("ExportResult.package_path 不能为空")
        if not PackageTaskStatus.is_valid(self.status):
            raise ValueError(
                f"ExportResult.status 不合法: {self.status}，"
                f"合法值: {PackageTaskStatus.all()}"
            )
        if self.resource_count < 0:
            raise ValueError(
                f"ExportResult.resource_count 不能为负数: {self.resource_count}"
            )
        if self.packed_count < 0 or self.packed_count > self.resource_count:
            raise ValueError(
                f"ExportResult.packed_count 不合法: {self.packed_count}，"
                f"应在 [0, {self.resource_count}] 范围内"
            )

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 API 响应）."""
        return {
            "export_id": self.export_id,
            "project_id": self.project_id,
            "package_path": self.package_path,
            "manifest": self.manifest.to_dict(),
            "resource_count": self.resource_count,
            "packed_count": self.packed_count,
            "skipped_resources": list(self.skipped_resources),
            "total_size_bytes": self.total_size_bytes,
            "package_size_bytes": self.package_size_bytes,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
        }


# ---------------------------------------------------------------------------
# 数据结构：导入结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportResourceRecord:
    """导入资源记录：单个资源的导入结果.

    属性:
        resource_uri: 资源 URI
        action: 导入动作（imported/skipped/renamed/failed）
        target_uri: 目标 URI（rename 策略下与 resource_uri 不同；其他策略下相同）
        error_message: 失败原因（action=failed 时非空）
    """

    resource_uri: str
    action: str  # imported / skipped / renamed / failed
    target_uri: str = ""
    error_message: str = ""

    def __post_init__(self) -> None:
        if not self.resource_uri:
            raise ValueError("ImportResourceRecord.resource_uri 不能为空")
        if self.action not in ("imported", "skipped", "renamed", "failed"):
            raise ValueError(
                f"ImportResourceRecord.action 不合法: {self.action}"
            )
        if not self.target_uri:
            # 默认 target_uri = resource_uri（rename 策略下由服务层覆盖）
            object.__setattr__(self, "target_uri", self.resource_uri)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict."""
        return {
            "resource_uri": self.resource_uri,
            "action": self.action,
            "target_uri": self.target_uri,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class ImportResult:
    """导入结果契约：``ProjectPackageService.import_project()`` 返回值.

    属性:
        import_id: 导入任务 ID（``pimp_`` 前缀 + uuid）
        source_project_id: 源项目 ID（来自 manifest）
        target_project_id: 目标项目 ID（导入后创建或匹配的项目）
        source_package_path: 源 ``.lomo`` 文件路径
        format_version: 包格式版本
        conflict_strategy: 使用的冲突策略
        resource_records: 每个资源的导入记录（按 resource_uri 唯一）
        imported_count: 成功导入资源数
        skipped_count: 跳过资源数
        renamed_count: 重命名资源数
        failed_count: 失败资源数
        warnings: 警告信息列表（非致命问题）
        status: 任务状态（PackageTaskStatus 常量）
        error_message: 失败原因（status=FAILED 时非空）
        created_at: 任务创建时间
        completed_at: 任务完成时间
    """

    import_id: str
    source_project_id: str
    target_project_id: str
    source_package_path: str
    format_version: str
    conflict_strategy: str
    resource_records: tuple[ImportResourceRecord, ...] = field(default_factory=tuple)
    imported_count: int = 0
    skipped_count: int = 0
    renamed_count: int = 0
    failed_count: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    status: str = PackageTaskStatus.COMPLETED
    error_message: str = ""
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.import_id:
            raise ValueError("ImportResult.import_id 不能为空")
        if not self.source_project_id:
            raise ValueError("ImportResult.source_project_id 不能为空")
        if not self.target_project_id:
            raise ValueError("ImportResult.target_project_id 不能为空")
        if not self.source_package_path:
            raise ValueError("ImportResult.source_package_path 不能为空")
        if not PackageFormatVersion.is_supported(self.format_version):
            raise ValueError(
                f"ImportResult.format_version 不受支持: {self.format_version}"
            )
        if not ConflictStrategy.is_valid(self.conflict_strategy):
            raise ValueError(
                f"ImportResult.conflict_strategy 不合法: {self.conflict_strategy}"
            )
        if not PackageTaskStatus.is_valid(self.status):
            raise ValueError(
                f"ImportResult.status 不合法: {self.status}"
            )
        # 计数一致性校验
        total = self.imported_count + self.skipped_count + self.renamed_count + self.failed_count
        if total != len(self.resource_records):
            raise ValueError(
                f"ImportResult 计数不一致：imported({self.imported_count}) + "
                f"skipped({self.skipped_count}) + renamed({self.renamed_count}) + "
                f"failed({self.failed_count}) = {total}，"
                f"但 resource_records 长度为 {len(self.resource_records)}"
            )

    @property
    def total_count(self) -> int:
        """资源总数."""
        return len(self.resource_records)

    @property
    def is_partial_failure(self) -> bool:
        """是否部分失败（有失败但整体未 FAILED）."""
        return self.failed_count > 0 and self.status == PackageTaskStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 API 响应）."""
        return {
            "import_id": self.import_id,
            "source_project_id": self.source_project_id,
            "target_project_id": self.target_project_id,
            "source_package_path": self.source_package_path,
            "format_version": self.format_version,
            "conflict_strategy": self.conflict_strategy,
            "resource_records": [record.to_dict() for record in self.resource_records],
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "renamed_count": self.renamed_count,
            "failed_count": self.failed_count,
            "total_count": self.total_count,
            "warnings": list(self.warnings),
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "completed_at": self.completed_at.isoformat() if self.completed_at else "",
        }


# ---------------------------------------------------------------------------
# 数据结构：校验结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """包校验结果契约：``ProjectPackageService.validate_package()`` 返回值.

    校验项：
        1. ``manifest.json`` 可解析
        2. ``format_version`` 受支持
        3. ``checksum`` 与重新计算的 sha256 一致
        4. 每个资源条目的 ``content_hash`` 与包内文件实际 sha256 一致
        5. ``path_in_package`` 指向的文件存在于包内

    属性:
        package_path: ``.lomo`` 文件路径
        is_valid: 整体是否通过校验
        format_version: 包格式版本（解析失败时为空字符串）
        checksum_verified: checksum 是否一致
        resource_count: 资源条目总数
        verified_count: 通过校验的资源数
        errors: 错误信息列表（致命问题）
        warnings: 警告信息列表（非致命问题）
        validated_at: 校验时间
    """

    package_path: str
    is_valid: bool
    format_version: str = ""
    checksum_verified: bool = False
    resource_count: int = 0
    verified_count: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    validated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.package_path:
            raise ValueError("ValidationResult.package_path 不能为空")
        if self.resource_count < 0:
            raise ValueError(
                f"ValidationResult.resource_count 不能为负数: {self.resource_count}"
            )
        if self.verified_count < 0 or self.verified_count > self.resource_count:
            raise ValueError(
                f"ValidationResult.verified_count 不合法: {self.verified_count}"
            )

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 API 响应）."""
        return {
            "package_path": self.package_path,
            "is_valid": self.is_valid,
            "format_version": self.format_version,
            "checksum_verified": self.checksum_verified,
            "resource_count": self.resource_count,
            "verified_count": self.verified_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "validated_at": self.validated_at.isoformat() if self.validated_at else "",
        }


# ---------------------------------------------------------------------------
# 接口契约：服务接口
# ---------------------------------------------------------------------------


class IProjectPackageService:
    """项目包服务接口契约：定义导入导出服务的方法签名.

    实现见 app/services/project_package_service.py: ProjectPackageService。
    所有方法均应线程安全（按 project_id / package_path 串行化）。
    """

    def export_project(
        self,
        project_id: str,
        output_dir: str,
        options: ExportOptions,
        exported_by: str,
    ) -> ExportResult:
        """导出项目为 ``.lomo`` 包.

        Args:
            project_id: 源项目 ID
            output_dir: 输出目录（.lomo 文件将写入此目录）
            options: 导出选项
            exported_by: 导出者 user_id 或 plugin_id

        Returns:
            导出结果

        Raises:
            LookupError: 项目不存在
            ValueError: 选项不合法
            RuntimeError: 导出失败（IO 错误 / 资源缺失）
        """
        raise NotImplementedError

    def import_project(
        self,
        package_path: str,
        options: ImportOptions,
        imported_by: str,
    ) -> ImportResult:
        """从 ``.lomo`` 包导入项目.

        Args:
            package_path: ``.lomo`` 文件路径
            options: 导入选项
            imported_by: 导入者 user_id 或 plugin_id

        Returns:
            导入结果

        Raises:
            LookupError: 包文件不存在
            ValueError: 包格式不合法 / 版本不兼容
            RuntimeError: 导入失败（IO 错误 / 冲突策略 fail 触发）
        """
        raise NotImplementedError

    def validate_package(
        self,
        package_path: str,
    ) -> ValidationResult:
        """校验 ``.lomo`` 包完整性（不实际导入）.

        Args:
            package_path: ``.lomo`` 文件路径

        Returns:
            校验结果

        Raises:
            LookupError: 包文件不存在
            ValueError: 包格式不合法（无法解析 manifest）
        """
        raise NotImplementedError

    def preview_import(
        self,
        package_path: str,
    ) -> PackageManifest:
        """预览 ``.lomo`` 包内容（返回 manifest，不实际导入）.

        Args:
            package_path: ``.lomo`` 文件路径

        Returns:
            包清单

        Raises:
            LookupError: 包文件不存在
            ValueError: 包格式不合法 / 版本不兼容
        """
        raise NotImplementedError
