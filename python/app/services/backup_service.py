"""
灵境制造 - 数据备份与恢复服务
支持自动备份、手动导出和导入恢复
"""
from __future__ import annotations

import datetime
import logging
import os
import zipfile
from pathlib import Path
from typing import Any

from typing_extensions import TypedDict

from app.config import config

logger = logging.getLogger(__name__)


class BackupInfo(TypedDict, total=False):
    """备份信息"""
    path: str
    size: int
    created_at: str
    name: str


class BackupService:
    """数据备份与恢复服务"""

    def __init__(self) -> None:
        self.backup_dir = Path(config.paths.get("backup_dir", "./backups"))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(config.paths.get("db_path", "./data/app.db"))
        self.vector_db_path = Path(config.paths.get("vector_db_path", "./data/chroma_db"))
        self.config_path = Path(config.paths.get("config_path", "./config.json"))
        self.max_backup_days = 7

    def auto_backup(self) -> str | None:
        """自动备份 - 定期备份 SQLite 和 ChromaDB"""
        try:
            now = datetime.datetime.now()
            backup_name = f"auto_{now.strftime('%Y%m%d_%H%M%S')}"
            backup_file = self.backup_dir / f"{backup_name}.zip"

            self._create_backup(backup_file, include_configs=True)

            self._cleanup_old_backups()

            logger.info(f"自动备份完成: {backup_file}")
            return str(backup_file)
        except Exception as e:
            logger.error(f"自动备份失败: {e!s}")
            return None

    def export_all(self, output_path: str | None = None) -> str:
        """手动导出 - 导出所有数据为压缩包"""
        now = datetime.datetime.now()
        if output_path is None:
            output_path = str(self.backup_dir / f"export_{now.strftime('%Y%m%d_%H%M%S')}.zip")

        backup_file = Path(output_path)
        self._create_backup(backup_file, include_configs=True, include_generated=True)

        logger.info(f"手动导出完成: {backup_file}")
        return str(backup_file)

    def import_backup(self, backup_path: str, selective: bool = False, include_items: list[str] | None = None) -> dict[str, bool]:
        """从备份压缩包恢复数据"""
        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        results: dict[str, bool] = {}

        with zipfile.ZipFile(backup_file, 'r') as zf:
            members = zf.namelist()

            # 恢复数据库
            if not selective or include_items is None or "database" in include_items:
                db_files = [m for m in members if m.startswith("database/")]
                results["database"] = self._restore_files(zf, db_files, self.db_path.parent)

            # 恢复向量库
            if not selective or include_items is None or "vector_db" in include_items:
                vector_files = [m for m in members if m.startswith("vector_db/")]
                results["vector_db"] = self._restore_files(zf, vector_files, self.vector_db_path.parent)

            # 恢复配置文件
            if not selective or include_items is None or "config" in include_items:
                config_files = [m for m in members if m.startswith("config/")]
                results["config"] = self._restore_files(zf, config_files, self.config_path.parent)

        logger.info(f"备份恢复完成: {backup_path}, 结果: {results}")
        return results

    def list_backups(self) -> list[BackupInfo]:
        """查看备份列表"""
        backups: list[BackupInfo] = []
        for zip_file in self.backup_dir.glob("*.zip"):
            stat = zip_file.stat()
            created_at = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            backups.append({
                "path": str(zip_file),
                "size": stat.st_size,
                "created_at": created_at,
                "name": zip_file.name
            })

        # 按创建时间倒序
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    def delete_old_backups(self, days: int | None = None) -> int:
        """删除旧备份"""
        days_to_keep = days if days is not None else self.max_backup_days
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)

        deleted_count = 0
        for backup in self.list_backups():
            created = datetime.datetime.fromisoformat(backup["created_at"])
            if created < cutoff_date:
                Path(backup["path"]).unlink()
                deleted_count += 1
                logger.info(f"删除旧备份: {backup['name']}")

        return deleted_count

    def delete_backup(self, backup_path: str) -> bool:
        """删除指定备份"""
        try:
            Path(backup_path).unlink()
            logger.info(f"删除备份: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"删除备份失败: {e!s}")
            return False

    def _create_backup(
        self,
        output_file: Path,
        include_configs: bool = True,
        include_generated: bool = False
    ) -> None:
        """创建备份压缩包"""
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 备份数据库
            if self.db_path.exists():
                zf.write(self.db_path, f"database/{self.db_path.name}")

            # 备份向量库
            if self.vector_db_path.exists():
                for root, _dirs, files in os.walk(self.vector_db_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = f"vector_db/{file_path.relative_to(self.vector_db_path.parent)}"
                        zf.write(file_path, arcname)

            # 备份配置文件
            if include_configs and self.config_path.exists():
                zf.write(self.config_path, f"config/{self.config_path.name}")

            # 备份生成文件
            if include_generated:
                generated_dir = Path("./generated")
                if generated_dir.exists():
                    for root, _dirs, files in os.walk(generated_dir):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = f"generated/{file_path.relative_to(generated_dir.parent)}"
                            zf.write(file_path, arcname)

    def _restore_files(
        self,
        zf: zipfile.ZipFile,
        members: list[str],
        target_dir: Path
    ) -> bool:
        """从压缩包恢复文件"""
        if not members:
            return True

        target_dir.mkdir(parents=True, exist_ok=True)

        for member in members:
            try:
                zf.extract(member, target_dir.parent)
            except Exception as e:
                logger.error(f"恢复文件失败 {member}: {e!s}")
                return False

        return True

    def _cleanup_old_backups(self) -> None:
        """清理超过保留期的备份"""
        self.delete_old_backups()

    def get_backup_status(self) -> dict[str, Any]:
        """获取备份状态"""
        backups = self.list_backups()
        total_size = sum(b["size"] for b in backups)

        return {
            "total_backups": len(backups),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_backup": backups[0]["created_at"] if backups else None,
            "oldest_backup": backups[-1]["created_at"] if backups else None,
            "retention_days": self.max_backup_days
        }
