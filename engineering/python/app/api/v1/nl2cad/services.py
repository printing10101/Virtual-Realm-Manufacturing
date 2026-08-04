"""NL to CAD parameter conversion service."""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any

from app.ai.llm_client import BaseLLMClient, get_llm_client
from app.api.v1.nl2cad.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    REFINEMENT_PROMPT,
)
from app.cad.cadquery_gen import CadQueryGenerator

logger = logging.getLogger(__name__)


class NL2CADService:
    """Natural language to CAD parameter conversion service."""

    def __init__(self) -> None:
        self._llm_client: BaseLLMClient | None = None
        self._cad_generator = CadQueryGenerator()

    async def _get_llm_client(self) -> BaseLLMClient:
        """Get or create LLM client."""
        if self._llm_client is None:
            self._llm_client = await get_llm_client()
        return self._llm_client

    async def extract_params_from_nl(self, description: str) -> dict[str, Any]:
        """Extract CAD parameters from natural language description.

        Args:
            description: Natural language description of the part

        Returns:
            Dictionary containing CAD parameters
        """
        logger.info("Extracting CAD params from NL: %s", description[:100])

        client = await self._get_llm_client()
        user_prompt = USER_PROMPT_TEMPLATE.format(description=description)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await client.chat_completion(
                messages=messages,
                max_tokens=2048,
                temperature=0.3,
            )

            content = response.get("content", "")
            params = self._parse_llm_response(content)

            logger.info("Extracted params: %s", params)
            return params

        except Exception as e:
            # 软依赖降级：LLM 不可用时，使用基于规则的参数提取，避免整个 NL2CAD 功能崩溃。
            # 与 app/rag/query_rewriter.py 的 _rule_based_rewrite 降级模式一致。
            logger.warning("LLM 不可用，NL2CAD 降级到规则参数提取。原因: %s", e, exc_info=True)
            params = self._rule_based_extract_params(description)
            params["confidence"] = 0.3  # 降级标志：低置信度
            params["_fallback"] = "rule_based"
            return params

    async def refine_params(
        self,
        current_params: dict[str, Any],
        instruction: str,
    ) -> dict[str, Any]:
        """Refine CAD parameters based on user instruction.

        Args:
            current_params: Current CAD parameters
            instruction: User's refinement instruction

        Returns:
            Updated CAD parameters
        """
        logger.info("Refining params with instruction: %s", instruction[:100])

        client = await self._get_llm_client()
        prompt = REFINEMENT_PROMPT.format(
            current_params=json.dumps(current_params, indent=2, ensure_ascii=False),
            instruction=instruction,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await client.chat_completion(
                messages=messages,
                max_tokens=2048,
                temperature=0.2,
            )

            content = response.get("content", "")
            refined_params = self._parse_llm_response(content)

            logger.info("Refined params: %s", refined_params)
            return refined_params

        except Exception as e:
            # 软依赖降级：LLM 不可用时，保持原参数不变，避免整个精炼流程崩溃。
            logger.warning("LLM 不可用，NL2CAD 精炼降级为返回原参数。原因: %s", e, exc_info=True)
            fallback_params = dict(current_params)
            fallback_params["confidence"] = 0.3  # 降级标志：低置信度
            fallback_params["_fallback"] = "rule_based"
            return fallback_params

    def _rule_based_extract_params(self, description: str) -> dict[str, Any]:
        """基于规则的 CAD 参数提取（LLM 不可用时的降级实现）。

        通过关键词匹配识别形状类型，通过正则提取数值尺寸，
        返回与 LLM 提取等价结构的参数字典。

        Args:
            description: 自然语言描述

        Returns:
            CAD 参数字典
        """
        text = description.lower()

        # 形状类型识别
        shape_type = "box"  # 默认形状
        if any(kw in text for kw in ["圆柱", "cylinder", "圆筒", "轴"]):
            shape_type = "cylinder"
        elif any(kw in text for kw in ["球", "sphere", "ball"]):
            shape_type = "sphere"
        elif any(kw in text for kw in ["锥", "cone", "taper"]):
            shape_type = "cone"
        elif any(kw in text for kw in ["长方", "box", "立方", "块", "矩形"]):
            shape_type = "box"

        # 数值提取：支持 "长度50" "length=50" "50mm" "50毫米" 等格式
        def _extract_dim(patterns: list[str]) -> float | None:
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        return float(match.group(1))
                    except (ValueError, IndexError):
                        continue
            return None

        dimensions: dict[str, float] = {}

        if shape_type == "box":
            length = _extract_dim(
                [
                    r"长度\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"length\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                    r"长\s*(\d+(?:\.\d+)?)",
                ]
            )
            width = _extract_dim(
                [
                    r"宽度\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"width\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                    r"宽\s*(\d+(?:\.\d+)?)",
                ]
            )
            height = _extract_dim(
                [
                    r"高度\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"height\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                    r"高\s*(\d+(?:\.\d+)?)",
                ]
            )
            if length is not None:
                dimensions["length"] = length
            if width is not None:
                dimensions["width"] = width
            if height is not None:
                dimensions["height"] = height
        elif shape_type in ("cylinder", "cone"):
            radius = _extract_dim(
                [
                    r"半径\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"radius\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                    r"直径\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"diameter\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                ]
            )
            height = _extract_dim(
                [
                    r"高度\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"height\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                    r"高\s*(\d+(?:\.\d+)?)",
                ]
            )
            if radius is not None:
                # 若匹配到"直径"，需转换为半径
                if re.search(r"直径|diameter", text):
                    radius = radius / 2
                dimensions["radius"] = radius
            if height is not None:
                dimensions["height"] = height
        elif shape_type == "sphere":
            radius = _extract_dim(
                [
                    r"半径\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"radius\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                    r"直径\s*[:：]?\s*(\d+(?:\.\d+)?)",
                    r"diameter\s*[:：=]?\s*(\d+(?:\.\d+)?)",
                ]
            )
            if radius is not None:
                if re.search(r"直径|diameter", text):
                    radius = radius / 2
                dimensions["radius"] = radius

        params: dict[str, Any] = {
            "shape_type": shape_type,
            "dimensions": dimensions,
            "position": {"x": 0, "y": 0, "z": 0},
            "features": [],
        }

        # 通过 _validate_params 补全默认值
        return self._validate_params(params)

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response to extract JSON parameters.

        Args:
            content: LLM response content

        Returns:
            Parsed parameters dictionary
        """
        content = content.strip()

        # Try to extract JSON from markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()

        try:
            params = json.loads(content)
            return self._validate_params(params)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            raise ValueError(f"无法解析LLM响应为JSON: {e}") from e

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize CAD parameters.

        Args:
            params: Raw parameters from LLM

        Returns:
            Validated and normalized parameters
        """
        # Ensure required fields
        if "shape_type" not in params:
            params["shape_type"] = "box"

        if "dimensions" not in params:
            params["dimensions"] = {}

        # Normalize dimensions based on shape type
        shape_type = params["shape_type"]
        dims = params["dimensions"]

        if shape_type == "box":
            dims.setdefault("length", 50.0)
            dims.setdefault("width", 30.0)
            dims.setdefault("height", 20.0)
        elif shape_type == "cylinder":
            dims.setdefault("radius", 15.0)
            dims.setdefault("height", 30.0)
            # Map radius to width/length for compatibility
            dims["length"] = dims["radius"] * 2
            dims["width"] = dims["radius"] * 2
        elif shape_type == "sphere":
            dims.setdefault("radius", 20.0)
            dims["length"] = dims["radius"] * 2
            dims["width"] = dims["radius"] * 2
            dims["height"] = dims["radius"] * 2
        elif shape_type == "cone":
            dims.setdefault("radius", 15.0)
            dims.setdefault("height", 30.0)
            dims["length"] = dims["radius"] * 2
            dims["width"] = dims["radius"] * 2

        if "position" not in params:
            params["position"] = {"x": 0, "y": 0, "z": 0}

        if "features" not in params:
            params["features"] = []

        if "confidence" not in params:
            params["confidence"] = 0.8

        return params

    async def generate_model_from_nl(
        self,
        description: str,
        output_format: str = "stl",
    ) -> tuple[str, dict[str, Any]]:
        """Generate 3D model from natural language description.

        Args:
            description: Natural language description
            output_format: Output file format (stl, step, obj, gltf)

        Returns:
            Tuple of (model_path, extracted_params)
        """
        params = await self.extract_params_from_nl(description)

        model_path = self._cad_generator.generate_with_features(
            params=params,
            features=params.get("features"),
            output_format=output_format,
        )

        return model_path, params

    async def refine_model(
        self,
        current_params: dict[str, Any],
        instruction: str,
        output_format: str = "stl",
    ) -> tuple[str, dict[str, Any]]:
        """Refine existing model based on instruction.

        Args:
            current_params: Current model parameters
            instruction: Refinement instruction
            output_format: Output file format

        Returns:
            Tuple of (new_model_path, updated_params)
        """
        refined_params = await self.refine_params(current_params, instruction)

        model_path = self._cad_generator.generate_with_features(
            params=refined_params,
            features=refined_params.get("features"),
            output_format=output_format,
        )

        return model_path, refined_params


# Singleton instance (双重检查锁，线程安全)
_service_instance: NL2CADService | None = None
_service_lock = threading.Lock()


def get_nl2cad_service() -> NL2CADService:
    """Get or create NL2CAD service instance."""
    global _service_instance
    if _service_instance is not None:
        return _service_instance
    with _service_lock:
        if _service_instance is None:
            _service_instance = NL2CADService()
    return _service_instance
