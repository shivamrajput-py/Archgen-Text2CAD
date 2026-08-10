"""
2D Engineering Drawing Generator — Fast Version
Uses random vertex point-cloud projection (not cross-sections) for speed.
Generates orthographic Front, Top, Right views as SVG with title block.
Runs in < 5 seconds even on dense 100k-face meshes.
"""

import logging

logger = logging.getLogger(__name__)

VIEW_SIZE = 100.0   # each view box size in pyplot "units"
GAP       = 14.0
TITLE_H   = 36.0
PAD       = 10.0
MAX_PTS   = 12_000  # max points sampled from mesh surface for projection


def generate_2d_drawing(stl_path: str, output_svg_path: str, prompt: str = "") -> bool:
    """
    Generate a 2D engineering drawing SVG from an STL file.

    Uses random surface point sampling + 2D scatter projection per view
    for fast, robust rendering. Runs in < 5 seconds regardless of mesh size.

    Returns True on success, False on failure.
    """
    try:
        import trimesh
        import numpy as np
        import matplotlib
        try:
            matplotlib.use("Agg")
        except Exception:
            pass
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError as e:
        logger.error(f"Missing deps: {e}. Run: pip install trimesh matplotlib numpy")
        return False

    try:
        # ── Load mesh ─────────────────────────────────────────────────────────
        mesh = trimesh.load(stl_path, force="mesh")
        if mesh is None:
            logger.error("Could not load STL")
            return False

        if isinstance(mesh, trimesh.Scene):
            pieces = [g for g in mesh.geometry.values()
                      if isinstance(g, trimesh.Trimesh)]
            if not pieces:
                logger.error("Scene has no Trimesh objects")
                return False
            mesh = trimesh.util.concatenate(pieces)

        if not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
            logger.error("Empty mesh")
            return False

        import numpy as np

        # Centre at origin
        mesh.apply_translation(-mesh.bounding_box.centroid)

        bounds = mesh.bounds   # [[xmin,ymin,zmin],[xmax,ymax,zmax]]
        ext    = mesh.extents  # [dx, dy, dz]
        dx, dy, dz = float(ext[0]), float(ext[1]), float(ext[2])
        width_mm  = round(dx, 1)
        depth_mm  = round(dy, 1)
        height_mm = round(dz, 1)

        # ── Fast projection via random surface points ─────────────────────────
        n_pts = min(MAX_PTS, max(len(mesh.vertices), 500))
        try:
            pts, _ = trimesh.sample.sample_surface(mesh, n_pts)
        except Exception:
            # Fall back to vertex sampling if sample_surface fails
            verts = mesh.vertices
            idx = np.random.choice(len(verts), min(n_pts, len(verts)), replace=False)
            pts = verts[idx]

        if len(pts) == 0:
            logger.error("No points sampled for protection.")
            return False

        # Each view is a 2D scatter of the projected points
        # Front (look along +Y): X vs Z
        front_x, front_y = pts[:, 0], pts[:, 2]
        # Top   (look down  -Z): X vs Y
        top_x,   top_y   = pts[:, 0], pts[:, 1]
        # Right (look along -X): Y vs Z
        right_x, right_y = pts[:, 1], pts[:, 2]

        # ── Canvas layout ─────────────────────────────────────────────────────
        CANVAS_W = VIEW_SIZE + GAP + VIEW_SIZE + 4
        CANVAS_H = TITLE_H + GAP + VIEW_SIZE + GAP + VIEW_SIZE + 4

        fig, ax = plt.subplots(figsize=(12, 9))
        ax.set_aspect("equal")
        ax.set_xlim(0, CANVAS_W)
        ax.set_ylim(0, CANVAS_H)
        ax.axis("off")

        BG = "#0D1117"; VBG = "#0F1923"; BORDER = "#2D3748"
        PT_C = "#A8C8DC"; EDGE_C = "#3A5A72"
        DIM_C = "#5DA9E9"; TITLE_C = "#F0F4F8"; LABEL_C = "#718096"

        fig.patch.set_facecolor(BG)
        ax.set_facecolor(BG)

        # Outer border
        ax.add_patch(patches.Rectangle(
            (1, 1), CANVAS_W - 2, CANVAS_H - 2, lw=0.8, ec=BORDER, fc="none"
        ))

        inner = VIEW_SIZE - 2 * PAD

        def view_box(x, y, w, h, label):
            ax.add_patch(patches.Rectangle(
                (x, y), w, h, lw=0.5, ec=BORDER, fc=VBG))
            ax.text(x + 2.5, y + h - 2, label,
                    color=LABEL_C, fontsize=5, fontfamily="monospace", va="top")

        def normalize_and_draw(raw_x, raw_y, box_x, box_y):
            """Normalize raw projection coords into box and draw as scatter/outline."""
            xlo, xhi = float(raw_x.min()), float(raw_x.max())
            ylo, yhi = float(raw_y.min()), float(raw_y.max())
            xspan = max(xhi - xlo, 1e-6)
            yspan = max(yhi - ylo, 1e-6)

            nx = box_x + PAD + (raw_x - xlo) / xspan * inner
            ny = box_y + PAD + (raw_y - ylo) / yspan * inner

            # Draw as tiny dots (fast, works for any mesh density)
            ax.scatter(nx, ny, s=0.2, c=PT_C, alpha=0.55,
                       linewidths=0, rasterized=True)

            # Draw convex hull outline for crisp silhouette
            try:
                from scipy.spatial import ConvexHull
                pts2d = np.column_stack([nx, ny])
                hull = ConvexHull(pts2d)
                for simplex in hull.simplices:
                    ax.plot(pts2d[simplex, 0], pts2d[simplex, 1],
                            color=EDGE_C, lw=0.6, alpha=0.9, solid_capstyle="round")
            except Exception:
                pass  # convex hull optional

        # ── FRONT VIEW ────────────────────────────────────────────────────────
        fv_bx = 2;  fv_by = TITLE_H + GAP + VIEW_SIZE + GAP
        view_box(fv_bx, fv_by, VIEW_SIZE, VIEW_SIZE, "FRONT  (Y→)")
        normalize_and_draw(front_x, front_y, fv_bx, fv_by)

        # ── TOP VIEW ──────────────────────────────────────────────────────────
        tv_bx = 2;  tv_by = TITLE_H + GAP
        view_box(tv_bx, tv_by, VIEW_SIZE, VIEW_SIZE, "TOP  (Z↓)")
        normalize_and_draw(top_x, top_y, tv_bx, tv_by)

        # ── RIGHT VIEW ────────────────────────────────────────────────────────
        rv_bx = 2 + VIEW_SIZE + GAP;  rv_by = TITLE_H + GAP + VIEW_SIZE + GAP
        view_box(rv_bx, rv_by, VIEW_SIZE, VIEW_SIZE, "RIGHT  (X→)")
        normalize_and_draw(right_x, right_y, rv_bx, rv_by)

        # ── DIMENSION ANNOTATIONS ─────────────────────────────────────────────
        def dim_h(x0, x1, y, label):
            ax.annotate("", (x1, y), (x0, y),
                        arrowprops=dict(arrowstyle="<->", color=DIM_C, lw=0.55))
            ax.text((x0+x1)/2, y + 1.5, label, color=DIM_C,
                    fontsize=4, ha="center", fontfamily="monospace")

        def dim_v(x, y0, y1, label):
            ax.annotate("", (x, y1), (x, y0),
                        arrowprops=dict(arrowstyle="<->", color=DIM_C, lw=0.55))
            ax.text(x + 1.5, (y0+y1)/2, label, color=DIM_C,
                    fontsize=4, va="center", fontfamily="monospace", rotation=90)

        dim_h(fv_bx, fv_bx + VIEW_SIZE, fv_by - 5,  f"W: {width_mm}mm")
        dim_v(fv_bx + VIEW_SIZE + 2, fv_by, fv_by + VIEW_SIZE, f"H: {height_mm}mm")
        dim_v(tv_bx + VIEW_SIZE + 2, tv_by, tv_by + VIEW_SIZE, f"D: {depth_mm}mm")

        # ── TITLE BLOCK ───────────────────────────────────────────────────────
        ax.plot([1, CANVAS_W - 1], [TITLE_H, TITLE_H], color=BORDER, lw=0.5)

        ax.text(4, TITLE_H / 2 + 5, "ARCHGEN",
                color=DIM_C, fontsize=12, fontweight="bold",
                fontfamily="monospace", va="center")
        ax.text(4, TITLE_H / 2 - 5, "archgen.in",
                color=LABEL_C, fontsize=5, fontfamily="monospace", va="center")

        t = (prompt[:68] + "…") if len(prompt) > 68 else prompt
        ax.text(CANVAS_W / 2, TITLE_H / 2 + 5,
                t or "ENGINEERING DRAWING",
                color=TITLE_C, fontsize=7.5, fontweight="bold",
                fontfamily="monospace", ha="center", va="center")
        ax.text(CANVAS_W / 2, TITLE_H / 2 - 4,
                f"SCALE: {_best_scale(max(dx, dy, dz))}   |   DIMS: mm   |   3RD ANGLE PROJECTION",
                color=LABEL_C, fontsize=4, fontfamily="monospace",
                ha="center", va="center")

        ax.text(CANVAS_W - 3, TITLE_H / 2 + 5,
                f"W:{width_mm} × D:{depth_mm} × H:{height_mm} mm",
                color=DIM_C, fontsize=5, fontfamily="monospace",
                ha="right", va="center")
        ax.text(CANVAS_W - 3, TITLE_H / 2 - 4,
                "TOL: ±0.5mm   |   MAT: As specified",
                color=LABEL_C, fontsize=4, fontfamily="monospace",
                ha="right", va="center")

        # ── Save ─────────────────────────────────────────────────────────────
        fig.savefig(output_svg_path, format="svg",
                    bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        logger.info(f"2D drawing saved: {output_svg_path} "
                    f"({round(Path(output_svg_path).stat().st_size/1024)}KB)")
        return True

    except Exception as e:
        logger.error(f"2D drawing failed: {e}", exc_info=True)
        try:
            import matplotlib.pyplot as _p; _p.close("all")
        except Exception:
            pass
        return False


def _best_scale(max_dim_mm: float) -> str:
    if max_dim_mm < 50:   return "2:1"
    if max_dim_mm < 200:  return "1:1"
    if max_dim_mm < 1000: return "1:2"
    if max_dim_mm < 5000: return "1:10"
    return "1:50"


# ── allow scipy to be optional ──────────────────────────────────────────────
try:
    from scipy.spatial import ConvexHull as _CH  # noqa: F401
except ImportError:
    pass

# ── expose Path for logging ───────────────────────────────────────────────────
from pathlib import Path  # noqa: E402


if __name__ == "__main__":
    import sys, logging as _logging
    _logging.basicConfig(level=logging.INFO)
    if len(sys.argv) >= 3:
        ok = generate_2d_drawing(sys.argv[1], sys.argv[2],
                                  sys.argv[3] if len(sys.argv) > 3 else "")
        print("OK" if ok else "FAILED")
    else:
        print("Usage: python drawing_generator.py input.stl output.svg [prompt]")
