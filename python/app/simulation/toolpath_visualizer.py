"""刀具路径3D可视化模块。

基于matplotlib 3D实现工具路径的多角度可视化，
支持PNG静态图和HTML交互图两种输出格式。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from app.simulation.stock_model import StockModel  # noqa: E402
from app.simulation.toolpath_parser import ToolpathSegment  # noqa: E402


class ToolpathVisualizer:
    def __init__(self, stock: StockModel | None = None) -> None:
        self.stock = stock

    def render_png(
        self,
        segments: list[ToolpathSegment],
        output_path: str,
    ) -> str:
        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(111, projection="3d")
        self._draw_stock(ax)
        self._draw_segments(ax, segments)
        self._apply_labels(ax)
        plt.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.02)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out), dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(out)

    def render_html(
        self,
        segments: list[ToolpathSegment],
        output_path: str,
    ) -> str:
        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(111, projection="3d")
        self._draw_stock(ax)
        self._draw_segments(ax, segments)
        self._apply_labels(ax)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        html = self._build_interactive_html(fig, ax)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        plt.close(fig)
        return str(out)

    def _draw_stock(self, ax: Any) -> None:
        if self.stock is None:
            return
        bbox = self.stock.get_bbox()
        x = [bbox.x_min, bbox.x_max]
        y = [bbox.y_min, bbox.y_max]
        z = [bbox.z_min, bbox.z_max]
        xx, yy = np.meshgrid(x, y)

        ax.plot_surface(xx, yy, np.full_like(xx, z[0]), alpha=0.2, color="gray")
        ax.plot_surface(xx, yy, np.full_like(xx, z[1]), alpha=0.15, color="gray")

        for z_plane in z:
            ax.plot_wireframe(
                xx,
                yy,
                np.full_like(xx, z_plane),
                color="gray",
                alpha=0.4,
                linewidth=0.5,
            )

        for y_val in y:
            xz_x, xz_z = np.meshgrid(x, z)
            ax.plot_surface(
                xz_x, np.full_like(xz_x, y_val), xz_z, alpha=0.1, color="gray"
            )

        for x_val in x:
            yz_y, yz_z = np.meshgrid(y, z)
            ax.plot_surface(
                np.full_like(yz_y, x_val), yz_y, yz_z, alpha=0.1, color="gray"
            )

    def _draw_segments(self, ax: Any, segments: list[ToolpathSegment]) -> None:
        colors = {
            "rapid": "#f44336",
            "linear": "#4caf50",
            "arc": "#2196f3",
            "dwell": "#ffc107",
        }
        labels_used: set[str] = set()

        for seg in segments:
            c = colors.get(seg.type, "#333")
            lbl = seg.type if seg.type not in labels_used else None
            if lbl:
                labels_used.add(seg.type)

            sx, sy, sz = seg.start_point
            ex, ey, ez = seg.end_point

            ax.plot(
                [sx, ex],
                [sy, ey],
                [sz, ez],
                color=c,
                linewidth=1.5,
                label=lbl,
            )

            if seg.type == "rapid":
                ax.scatter(ex, ey, ez, color=c, s=8, marker="o", alpha=0.7)
            elif seg.type == "dwell":
                ax.scatter(ex, ey, ez, color=c, s=30, marker="s", alpha=0.8)

        if labels_used:
            ax.legend(loc="upper right", fontsize=9)

    def _apply_labels(self, ax: Any) -> None:
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")
        ax.set_title("NC刀具路径3D仿真可视化", fontsize=14)

        if self.stock:
            bbox = self.stock.get_bbox()
            padding = 30
            ax.set_xlim(bbox.x_min - padding, bbox.x_max + padding)
            ax.set_ylim(bbox.y_min - padding, bbox.y_max + padding)
            ax.set_zlim(bbox.z_min - padding, bbox.z_max + padding + 30)
        else:
            ax.set_xlim(-100, 100)
            ax.set_ylim(-100, 100)
            ax.set_zlim(-10, 110)

    def _build_interactive_html(self, fig: Any, ax: Any) -> str:
        legend_html = ""
        if ax.get_legend_handles_labels()[0]:
            legend_html = (
                "<p>图例: <b style='color:#f44336'>G00快速</b> | "
                "<b style='color:#4caf50'>G01直线</b> | "
                "<b style='color:#2196f3'>G02/G03圆弧</b> | "
                "<b style='color:#ffc107'>G04暂停</b></p>"
            )

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NC刀具路径3D仿真</title>
<style>
  body {{ margin:0; overflow:hidden; font-family:'Microsoft YaHei',sans-serif; background:#1a1a2e; }}
  #info {{ position:absolute; top:10px; left:10px; color:#ccc; font-size:12px; background:rgba(0,0,0,0.7); padding:8px 14px; border-radius:6px; z-index:10; }}
  #controls {{ position:absolute; bottom:10px; left:10px; color:#ccc; font-size:11px; background:rgba(0,0,0,0.7); padding:6px 12px; border-radius:4px; z-index:10; }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
<div id="info">
  <h2>NC刀具路径3D仿真</h2>
  {legend_html}
</div>
<div id="controls">鼠标左键旋转 | 滚轮缩放 | 右键平移</div>
<script>
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);
  const camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 1, 5000);
  camera.position.set(250, -250, 200);
  camera.lookAt(0, 0, 50);
  const renderer = new THREE.WebGLRenderer({{ antialias: true }});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  document.body.appendChild(renderer.domElement);
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 30);
  controls.update();

  const grid = new THREE.GridHelper(300, 20, 0x444444, 0x222222);
  scene.add(grid);

  const ambient = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambient);
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(200, 300, 400);
  scene.add(dirLight);

  window.addEventListener('resize', () => {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }});

  function animate() {{ requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }}
  animate();
</script>
</body>
</html>"""
