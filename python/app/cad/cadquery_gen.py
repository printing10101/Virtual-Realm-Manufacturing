import os
import asyncio
from pathlib import Path
from typing import Optional

from app.config import config
from app.ai.llm_client import get_llm_client


class CadQueryGenerator:
    def __init__(self):
        self.llm_client = get_llm_client()

    async def extract_geometry_params_from_views(self, views: dict) -> dict:
        front_path = views.get('front', '')
        top_path = views.get('top', '')
        left_path = views.get('left', '')
        
        from PIL import Image
        
        try:
            front_img = Image.open(front_path)
            top_img = Image.open(top_path)
            left_img = Image.open(left_path)
            
            width, height = front_img.size
            depth = top_img.size[1] if top_img else width
        except Exception:
            width, height, depth = 100, 100, 100
        
        prompt = f"""你是一个专业的CAD工程师。根据以下三视图信息，请分析几何形状并提取参数：

正视图尺寸: {width}x{height}
俯视图尺寸: {width}x{depth}
左视图尺寸: 需要推断

请分析这可能是什么几何形状，并返回JSON格式的参数：
{{
  "shape_type": "形状类型(box/cylinder/hole_box等)",
  "width": 宽度数值(单位mm),
  "height": 高度数值(单位mm),
  "depth": 深度数值(单位mm),
  "features": [
    {{"type": "hole/cutout/chamfer/fillet", "position": [x,y,z], "size": 尺寸, "description": "描述"}}
  ],
  "description": "形状描述"
}}

注意：
1. 基于标准工程制图推断
2. 尺寸单位统一为mm
3. 坐标系：X向右，Y向前，Z向上
4. 只返回JSON，不要其他解释"""

        try:
            import json
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3
            )
            
            content = response.get('content', '{}')
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                params = json.loads(content[start:end])
            else:
                params = self._default_params(width, height, depth)
            
        except Exception:
            params = self._default_params(width, height, depth)
        
        params.setdefault('width', width / 10)
        params.setdefault('height', height / 10)
        params.setdefault('depth', depth / 10)
        params.setdefault('shape_type', 'box')
        params.setdefault('features', [])
        
        return params

    def _default_params(self, width, height, depth):
        return {
            "shape_type": "box",
            "width": width / 10,
            "height": height / 10,
            "depth": depth / 10,
            "features": [],
            "description": "基础长方体"
        }

    async def generate_script_from_params(self, params: dict, library_matches: list) -> str:
        if library_matches and len(library_matches) > 0:
            best_match = library_matches[0]
            match_params = best_match.get('parameters', '{}')
            
            import json
            try:
                if json.loads(match_params) == params:
                    return best_match.get('cadquery_script', '')
            except Exception:
                pass
        
        shape_type = params.get('shape_type', 'box')
        width = params.get('width', 100)
        height = params.get('height', 100)
        depth = params.get('depth', 100)
        features = params.get('features', [])
        
        script = self._generate_basic_shape(shape_type, width, height, depth)
        
        for feature in features:
            feat_script = self._add_feature(feature)
            script += feat_script
        
        script += """
import cadquery as cq
from cadquery import exporters
import sys

result = shape
output_path = sys.argv[1] if len(sys.argv) > 1 else 'output.stl'
export_format = sys.argv[2] if len(sys.argv) > 2 else 'stl'

if export_format.lower() == 'stl':
    exporters.export(result, output_path)
elif export_format.lower() == 'step':
    exporters.export(result, output_path)
"""
        
        return script

    def _generate_basic_shape(self, shape_type: str, width: float, height: float, depth: float) -> str:
        if shape_type == 'box':
            return f"""import cadquery as cq

shape = cq.Workplane("XY").box({width}, {depth}, {height})
"""
        elif shape_type == 'cylinder':
            radius = min(width, depth) / 2
            return f"""import cadquery as cq

shape = cq.Workplane("XY").circle({radius}).extrude({height})
"""
        elif shape_type == 'sphere':
            radius = min(width, depth, height) / 2
            return f"""import cadquery as cq

shape = cq.Workplane("XY").sphere({radius})
"""
        else:
            return f"""import cadquery as cq

shape = cq.Workplane("XY").box({width}, {depth}, {height})
"""

    def _add_feature(self, feature: dict) -> str:
        feat_type = feature.get('type', '')
        position = feature.get('position', [0, 0, 0])
        size = feature.get('size', 10)
        
        if feat_type == 'hole':
            x, y, z = position
            return f"""
shape = shape.faces(">Z").workplane().center({x}, {y}).hole({size})
"""
        elif feat_type == 'cutout':
            x, y, z = position
            w = size if isinstance(size, (int, float)) else size.get('width', 10)
            d = size if isinstance(size, (int, float)) else size.get('depth', 10)
            return f"""
shape = shape.faces(">Z").workplane().center({x}, {y}).rect({w}, {d}).cutBlind(-{size if isinstance(size, (int, float)) else size.get('depth', 10)})
"""
        elif feat_type == 'chamfer':
            return f"""
shape = shape.edges(">Z").chamfer({size if isinstance(size, (int, float)) else 2})
"""
        elif feat_type == 'fillet':
            return f"""
shape = shape.edges(">Z").fillet({size if isinstance(size, (int, float)) else 2})
"""
        else:
            return ""

    async def execute_and_export(self, script: str, task_id: str, output_format: str) -> str:
        model_dir = Path(config.storage.output_dir) / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        model_path = model_dir / f"{task_id}.{output_format.lower()}"
        
        import tempfile
        import subprocess
        import sys
        
        script_with_args = script.replace(
            "output_path = sys.argv[1] if len(sys.argv) > 1 else 'output.stl'",
            f"output_path = r'{model_path}'"
        ).replace(
            "export_format = sys.argv[2] if len(sys.argv) > 2 else 'stl'",
            f"export_format = '{output_format}'"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("# -*- coding: utf-8 -*-\n")
            f.write(script_with_args)
            script_path = f.name
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"CadQuery execution failed: {result.stderr}")
            
            if not model_path.exists():
                raise RuntimeError(f"Model file not generated: {model_path}")
            
            return str(model_path)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("CadQuery script execution timeout (120s)")
        except Exception as e:
            raise RuntimeError(f"CadQuery execution error: {str(e)}")
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass
