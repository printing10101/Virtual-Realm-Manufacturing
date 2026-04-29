import httpx
from typing import Optional, AsyncGenerator


RECOMMENDED_MODELS = [
    {"name": "qwen2.5:7b", "size": "4.7 GB", "category": "通用"},
    {"name": "qwen2.5:3b", "size": "2.0 GB", "category": "通用"},
    {"name": "deepseek-r1:7b", "size": "4.7 GB", "category": "推理"},
    {"name": "qwen2.5-coder:7b", "size": "4.7 GB", "category": "代码"},
]


class OllamaManager:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/version")
                return response.status_code == 200
        except Exception:
            return False

    async def get_version(self) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/version")
                response.raise_for_status()
                return response.json().get("version")
        except Exception:
            return None

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("models", []):
                    models.append({
                        "name": m.get("name"),
                        "size": self._format_size(m.get("size", 0)),
                        "digest": m.get("digest", ""),
                        "modified_at": m.get("modified_at", ""),
                    })
                return models
        except Exception:
            return []

    async def pull_model(self, model_name: str) -> AsyncGenerator[dict, None]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": True},
                timeout=None
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "status" in data:
                                yield {
                                    "status": data["status"],
                                    "progress": data.get("completed", 0) / max(data.get("total", 1), 1) if "completed" in data and "total" in data else None,
                                    "completed": data.get("completed"),
                                    "total": data.get("total"),
                                }
                        except json.JSONDecodeError:
                            continue

    async def delete_model(self, model_name: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.delete(
                    f"{self.base_url}/api/delete",
                    json={"name": model_name}
                )
                return response.status_code == 200
        except Exception:
            return False

    async def show_model_info(self, model_name: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model_name}
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "name": model_name,
                    "modelfile": data.get("modelfile", ""),
                    "parameters": data.get("parameters", ""),
                    "template": data.get("template", ""),
                    "details": data.get("details", {}),
                }
        except Exception:
            return None

    async def get_gpu_info(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/version")
                response.raise_for_status()
                ollama_version = response.json().get("version", "unknown")

            gpus = []
            import subprocess
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            parts = [p.strip() for p in line.split(",")]
                            if len(parts) >= 4:
                                gpus.append({
                                    "index": int(parts[0]),
                                    "name": parts[1],
                                    "memory_total": f"{parts[2]} MB",
                                    "memory_free": f"{parts[3]} MB",
                                })
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            return {
                "ollama_version": ollama_version,
                "gpus": gpus,
                "gpu_count": len(gpus),
            }
        except Exception:
            return {
                "ollama_version": "unknown",
                "gpus": [],
                "gpu_count": 0,
            }

    @staticmethod
    def _format_size(size_bytes: float) -> str:
        if size_bytes == 0:
            return "0 B"
        if size_bytes < 1024:
            return f"{size_bytes:.0f} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
