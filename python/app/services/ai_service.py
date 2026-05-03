import time
import asyncio
from typing import Optional, Dict, Any, List
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType


class AIService:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self._prompt_templates: Dict[str, str] = {}
        self._max_retries = 3
        self._retry_delay = 1.0

    def register_template(self, name: str, template: str):
        self._prompt_templates[name] = template

    def get_template(self, name: str, **kwargs) -> str:
        template = self._prompt_templates.get(name, "")
        return template.format(**kwargs) if kwargs else template

    async def call_llm(self, task_id: str, agent_name: str,
                       prompt: str, system_prompt: Optional[str] = None,
                       model: Optional[str] = None, max_retries: int = 3) -> Dict[str, Any]:
        for attempt in range(max_retries):
            try:
                with self.logger.log_step(
                    task_id=task_id,
                    agent_name=agent_name,
                    step_type=StepType.LLM_CALL,
                    input_data={
                        "system_prompt": system_prompt,
                        "prompt_length": len(prompt),
                        "attempt": attempt + 1
                    },
                    model_name=model or self.config.ai.ollama_model
                ) as log_entry:
                    start_time = time.time()

                    response = await self._execute_llm_call(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        model=model
                    )

                    duration_ms = (time.time() - start_time) * 1000
                    log_entry.output = {
                        "response_length": len(response.get("content", "")),
                        "model_used": response.get("model", ""),
                        "finish_reason": response.get("finish_reason", "")
                    }
                    log_entry.duration_ms = duration_ms

                    if response.get("usage"):
                        log_entry.token_usage = response["usage"]

                    return response

            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                else:
                    raise

    async def _execute_llm_call(self, prompt: str, system_prompt: Optional[str] = None,
                                 model: Optional[str] = None) -> Dict[str, Any]:
        if self.config.ai.mode == "local":
            return await self._call_ollama(prompt, system_prompt, model)
        else:
            return await self._call_cloud(prompt, system_prompt, model)

    async def _call_ollama(self, prompt: str, system_prompt: Optional[str] = None,
                           model: Optional[str] = None) -> Dict[str, Any]:
        import httpx

        base_url = self.config.ai.ollama_base_url
        model_name = model or self.config.ai.ollama_model
        timeout = self.config.ai.timeout

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2048
                    }
                }
            )
            response.raise_for_status()
            data = response.json()

            return {
                "content": data.get("message", {}).get("content", ""),
                "model": model_name,
                "finish_reason": "stop",
                "usage": None
            }

    async def _call_cloud(self, prompt: str, system_prompt: Optional[str] = None,
                          model: Optional[str] = None) -> Dict[str, Any]:
        import httpx

        base_url = self.config.ai.cloud_base_url
        model_name = model or self.config.ai.cloud_model
        api_key = self.config.ai.cloud_api_key
        timeout = self.config.ai.timeout

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.7
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage = data.get("usage")

            return {
                "content": message.get("content", ""),
                "model": model_name,
                "finish_reason": choice.get("finish_reason", ""),
                "usage": usage
            }

    async def is_available(self) -> bool:
        try:
            if self.config.ai.mode == "local":
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{self.config.ai.ollama_base_url}/api/version")
                    return response.status_code == 200
            else:
                return True
        except Exception:
            return False
