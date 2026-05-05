"""
File Repository 实现

实现文件元数据管理、分块读写和哈希校验完整性验证。
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.repository.base import Repository
from app.core.repository.config import FileConfig
from app.core.repository.exceptions import (
    FileIntegrityError,
    RecordNotFoundError,
    StorageError,
)


class FileRepository(Repository):
    """
    文件系统存储库实现

    管理二进制文件存储，包括生成模型文件和日志文件。
    支持文件元数据管理、分块读写和哈希校验。
    """

    def __init__(self, config: FileConfig | None = None, subdirectory: str = ""):
        super().__init__(repository_type="file")
        self._config = config or FileConfig()
        self._base_dir = Path(self._config.base_directory)
        if subdirectory:
            self._base_dir = self._base_dir / subdirectory
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._metadata: dict[str, dict[str, Any]] = {}
        self._load_metadata()

    def _metadata_file(self) -> Path:
        return self._base_dir / ".file_metadata.json"

    def _load_metadata(self) -> None:
        import json
        metadata_file = self._metadata_file()
        if metadata_file.exists():
            with open(metadata_file, encoding="utf-8") as f:
                self._metadata = json.load(f)

    def _save_metadata(self) -> None:
        import json
        metadata_file = self._metadata_file()
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

    def _compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self._config.chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def _verify_hash(self, file_path: Path, expected_hash: str) -> bool:
        actual_hash = self._compute_hash(file_path)
        return actual_hash == expected_hash

    def _do_begin_transaction(self) -> None:
        self._transaction_metadata = dict(self._metadata)

    def _do_commit(self) -> None:
        self._save_metadata()
        if hasattr(self, "_transaction_metadata"):
            del self._transaction_metadata

    def _do_rollback(self) -> None:
        if hasattr(self, "_transaction_metadata"):
            self._metadata = self._transaction_metadata
            del self._transaction_metadata

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            file_id = data.get("id")
            if file_id is None:
                raise ValueError("Data must contain 'id' field")

            content = data.get("content")
            if content is None:
                raise ValueError("Data must contain 'content' field")

            file_path = self._base_dir / file_id

            if isinstance(content, str):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            elif isinstance(content, bytes):
                with open(file_path, "wb") as f:
                    f.write(content)
            elif hasattr(content, "read"):
                with open(file_path, "wb") as f:
                    while True:
                        chunk = content.read(self._config.chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)

            metadata = {
                "id": file_id,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "category": data.get("category", "default"),
                "description": data.get("description", ""),
            }

            if self._config.use_hash_verification:
                metadata["hash"] = self._compute_hash(file_path)

            metadata.update({k: v for k, v in data.items() if k not in ("id", "content", "category", "description")})

            self._metadata[file_id] = metadata
            if not self._in_transaction:
                self._save_metadata()

            return dict(metadata)
        except ValueError:
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="file", detail=str(e))

    def read(self, id: str) -> dict[str, Any] | None:
        metadata = self._metadata.get(id)
        if metadata is None:
            return None

        file_path = Path(metadata["path"])
        if not file_path.exists():
            return None

        if self._config.use_hash_verification and "hash" in metadata:
            if not self._verify_hash(file_path, metadata["hash"]):
                raise FileIntegrityError(
                    file_path=str(file_path),
                    message=f"File integrity check failed: {id}",
                    repository_type="file"
                )

        result = dict(metadata)
        result["exists"] = True
        return result

    def update(self, id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            if id not in self._metadata:
                raise RecordNotFoundError(id, repository_type="file")

            metadata = self._metadata[id]
            file_path = Path(metadata["path"])

            if "content" in data:
                content = data["content"]
                if isinstance(content, str):
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                elif isinstance(content, bytes):
                    with open(file_path, "wb") as f:
                        f.write(content)

                metadata["size"] = file_path.stat().st_size
                if self._config.use_hash_verification:
                    metadata["hash"] = self._compute_hash(file_path)

            metadata["updated_at"] = datetime.utcnow().isoformat()
            metadata.update({k: v for k, v in data.items() if k != "content"})

            if not self._in_transaction:
                self._save_metadata()

            return dict(metadata)
        except RecordNotFoundError:
            raise
        except Exception as e:
            raise StorageError(str(e), repository_type="file", detail=str(e))

    def delete(self, id: str) -> bool:
        try:
            if id not in self._metadata:
                return False

            metadata = self._metadata[id]
            file_path = Path(metadata["path"])

            if file_path.exists():
                file_path.unlink()

            del self._metadata[id]
            if not self._in_transaction:
                self._save_metadata()

            return True
        except Exception as e:
            raise StorageError(str(e), repository_type="file", detail=str(e))

    def list(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results = []
        for _file_id, metadata in self._metadata.items():
            if filters:
                match = all(metadata.get(k) == v for k, v in filters.items())
                if match:
                    results.append(dict(metadata))
            else:
                results.append(dict(metadata))
        return results

    def read_file_content(self, id: str) -> bytes | None:
        metadata = self._metadata.get(id)
        if metadata is None:
            return None

        file_path = Path(metadata["path"])
        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            return f.read()

    def write_file_chunk(self, id: str, offset: int, chunk: bytes) -> int:
        if id not in self._metadata:
            raise RecordNotFoundError(id, repository_type="file")

        metadata = self._metadata[id]
        file_path = Path(metadata["path"])

        with open(file_path, "r+b") as f:
            f.seek(offset)
            f.write(chunk)

        metadata["size"] = file_path.stat().st_size
        if self._config.use_hash_verification:
            metadata["hash"] = self._compute_hash(file_path)
        metadata["updated_at"] = datetime.utcnow().isoformat()

        if not self._in_transaction:
            self._save_metadata()

        return len(chunk)

    def get_file_size(self, id: str) -> int:
        metadata = self._metadata.get(id)
        if metadata is None:
            raise RecordNotFoundError(id, repository_type="file")
        return metadata.get("size", 0)

    def close(self) -> None:
        pass
