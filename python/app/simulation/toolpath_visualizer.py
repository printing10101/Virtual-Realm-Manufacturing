"""Toolpath 3D visualization module.

Provides multi-angle visualization of CNC toolpaths using matplotlib 3D,
supporting both PNG static images and HTML interactive output formats.

The visualizer renders:
    - Stock bounding box as a wireframe
    - Toolpath segments colored by motion type (G00=red, G01=green, arc=blue, dwell=yellow)
    - Axis labels and coordinate system
    - Interactive rotation/zoom in HTML output via Three.js

Example:
    >>> viz = ToolpathVisualizer(stock_model)
    >>> viz.render_png(segments, "output/toolpath.png")
    >>> viz.render_html(segments, "output/toolpath.html")
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
    """3D visualizer for CNC toolpath segments and stock geometry.

    Renders toolpaths with color-coded motion types and optional stock
    bounding box wireframe. Supports static PNG output and interactive
    HTML output with Three.js-based 3D navigation.

    Attributes:
        stock: Optional stock model for rendering the workpiece boundary.

    Example:
        >>> viz = ToolpathVisualizer(stock)
        >>> viz.render_png(segments, "output/view.png")
    """

    def __init__(self, stock: StockModel | None = None) -> None:
        """Initialize the visualizer with an optional stock model.

        Args:
            stock: Stock model to render as a bounding box. If None,
                only the toolpath is rendered.
        """
        self.stock = stock

    def render_png(
        self,
        segments: list[ToolpathSegment],
        output_path: str,
    ) -> str:
        """Render the toolpath as a static PNG image.

        Creates a 3D matplotlib plot with stock wireframe (if available),
        color-coded toolpath segments, axis labels, and title.

        Args:
            segments: List of toolpath segments to render.
            output_path: Destination file path for the PNG image.

        Returns:
            Absolute path to the saved PNG file.
        """
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
        """Render the toolpath as an interactive HTML page.

        Generates a self-contained HTML file with Three.js-based 3D
        viewer supporting mouse rotation, zoom, and pan controls.

        Args:
            segments: List of toolpath segments to render.
            output_path: Destination file path for the HTML file.

        Returns:
            Absolute path to the saved HTML file.
        """
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
        """Draw the stock bounding box as a wireframe.

        Renders the top, bottom, and side faces of the stock bounding
        box as semi-transparent gray surfaces.

        Args:
            ax: Matplotlib 3D axes object.
        """
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
        """Draw all toolpath segments with color coding by motion type.

        Colors:
            - rapid (G00): Red
            - linear (G01): Green
            - arc (G02/G03): Blue
            - dwell (G04): Yellow

        Args:
            ax: Matplotlib 3D axes object.
            segments: List of toolpath segments to draw.
        """
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
        """Apply axis labels, title, and view limits.

        Sets X/Y/Z labels in mm, applies a Chinese title for the
        visualization, and adjusts the view range based on stock
        dimensions or defaults.

        Args:
            ax: Matplotlib 3D axes object.
        """
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")
        ax.set_title("NC Toolpath 3D Simulation Visualization", fontsize=14)

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
        """Build a self-contained interactive HTML page with Three.js.

        Generates HTML with embedded Three.js scene, camera, lighting,
        and orbit controls for interactive 3D toolpath viewing.

        Args:
            fig: Matplotlib figure (used for legend extraction).
            ax: Matplotlib 3D axes (used for legend extraction).

        Returns:
            Complete HTML string for the interactive viewer page.
        """
        legend_html = ""
        if ax.get_legend_handles_labels()[0]:
            legend_html = (
                "<p>Legend: <b style='color:#f44336'>G00 Rapid</b> | "
                "<b style='color:#4caf50'>G01 Linear</b> | "
                "<b style='color:#2196f3'>G02/G03 Arc</b> | "
                "<b style='color:#ffc107'>G04 Dwell</b></p>"
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NC Toolpath 3D Simulation</title>
<style>
  body {{ margin:0; overflow:hidden; font-family:'Segoe UI',sans-serif; background:#1a1a2e; }}
  #info {{ position:absolute; top:10px; left:10px; color:#ccc; font-size:12px;
           background:rgba(0,0,0,0.7); padding:8px 14px; border-radius:6px; z-index:10; }}
  #controls {{ position:absolute; bottom:10px; left:10px; color:#ccc; font-size:11px;
               background:rgba(0,0,0,0.7); padding:6px 12px; border-radius:4px; z-index:10; }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
<div id="info">
  <h2>NC Toolpath 3D Simulation</h2>
  {legend_html}
</div>
<div id="controls">Left-click: rotate | Scroll: zoom | Right-click: pan</div>
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
