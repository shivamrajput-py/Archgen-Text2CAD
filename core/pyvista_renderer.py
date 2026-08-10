#!/usr/bin/env python3
"""
Headless STL Renderer for ArchgenCAD
======================================
Renders an STL file from multiple angles using pyrender (trimesh backend).

Key fixes vs v1:
  - Proper look-at camera math that doesn't degenerate at top/cardinal views
  - Auto-fit camera distance so model fills 70% of image frame
  - Mesh decimation + face-weighted vertex normals (eliminates wireframe artifacts)
  - Dark grey background so light geometry is visible
  - Blank-image detection — skips sending white renders to VLM
  - Higher resolution: 1024x1024 square images

Usage: python pyvista_renderer.py <stl_path> <output_dir>
"""

import sys
import os
import json
import numpy as np


# ── Helpers ──────────────────────────────────────────────────────────────────

def _lookat_matrix(eye: np.ndarray, target: np.ndarray, world_up=None) -> np.ndarray:
    """
    Compute an OpenGL-style camera pose (4x4) from eye/target.
    
    OpenGL convention: camera looks along -Z, Y is up, X is right.
    Returns a 4x4 pose matrix (camera-to-world transform).
    
    Handles the special case where forward ≈ world_up by swapping
    the world_up vector to avoid degenerate cross products.
    """
    if world_up is None:
        world_up = np.array([0.0, 0.0, 1.0])

    forward = np.array(target, dtype=float) - np.array(eye, dtype=float)
    dist = np.linalg.norm(forward)
    if dist < 1e-8:
        forward = np.array([0.0, -1.0, 0.0])
    else:
        forward /= dist

    # If forward is nearly parallel to world_up, swap world_up
    if abs(np.dot(forward, world_up)) > 0.99:
        # Use X-axis as fallback up
        world_up = np.array([1.0, 0.0, 0.0])

    right = np.cross(world_up, forward)
    right /= np.linalg.norm(right)

    up = np.cross(forward, right)
    up /= np.linalg.norm(up)

    # OpenGL: camera -Z = forward direction
    pose = np.eye(4, dtype=float)
    pose[:3, 0] = right       #  X axis
    pose[:3, 1] = up          #  Y axis
    pose[:3, 2] = -forward    # -Z axis (OpenGL convention)
    pose[:3, 3] = eye

    return pose


def _spherical_to_cartesian(center, radius, elev_deg, azim_deg):
    """
    Convert spherical coordinates to Cartesian camera position.
    
    Coordinate system: Z-up (FreeCAD default).
      azimuth = 0   → camera at +Y (front)
      azimuth = 90  → camera at +X (right)
      azimuth = 180 → camera at -Y (back)
      azimuth = 270 → camera at -X (left)
      elevation = 0 → equatorial, elevation = 90 → top
    """
    e = np.radians(elev_deg)
    a = np.radians(azim_deg)

    x = center[0] + radius * np.cos(e) * np.sin(a)
    y = center[1] + radius * np.cos(e) * np.cos(a)
    z = center[2] + radius * np.sin(e)

    return np.array([x, y, z], dtype=float)


def _is_blank(img_array: np.ndarray) -> bool:
    """
    Return True if the image is essentially just the background color
    (all-white, all-black, or any uniform color — meaning nothing was rendered).
    
    Uses per-channel standard deviation: a real render always has variation.
    A blank render has std ≈ 0 because every pixel is the same bg color.
    """
    if img_array is None or img_array.size == 0:
        return True
    # Clamp to float for statistics
    f = img_array.astype(np.float32)
    # Per-channel std across the whole image
    std = np.std(f.reshape(-1, f.shape[-1]), axis=0)
    # If max std across channels is very low, essentially uniform — blank
    return float(np.max(std)) < 3.0


def _compute_camera_distance(mesh, fov_y_rad: float, fill_factor: float = 0.65) -> float:
    """
    Compute camera distance so the mesh bounding sphere fills `fill_factor`
    fraction of the image height.
    
    Based on:  r / d = tan(fov_y/2) * fill_factor
    →          d = r / (tan(fov_y/2) * fill_factor)
    """
    bounds = mesh.bounds  # (2, 3)
    diag = np.linalg.norm(bounds[1] - bounds[0])
    bounding_sphere_radius = diag / 2.0
    half_fov = fov_y_rad / 2.0
    distance = bounding_sphere_radius / (np.tan(half_fov) * fill_factor)
    # Never closer than bounding sphere radius * 1.2 (avoid clipping)
    return max(distance, bounding_sphere_radius * 1.5)


def _prepare_mesh(raw_mesh, target_faces: int = 60_000):
    """
    Prepare mesh for rendering:
      1. Merge scene if needed
      2. Fix normals (critical for correct shading from all angles)
      3. Validate/fix mesh
      4. Decimate if very dense (to remove wireframe noise)
    Returns the prepared trimesh.Trimesh or None on failure.
    """
    import trimesh

    # Unwrap scene
    if isinstance(raw_mesh, trimesh.Scene):
        try:
            raw_mesh = raw_mesh.dump(concatenate=True)
        except Exception:
            geoms = list(raw_mesh.geometry.values())
            if not geoms:
                return None
            raw_mesh = trimesh.util.concatenate(geoms)

    if not isinstance(raw_mesh, trimesh.Trimesh):
        return None
    if raw_mesh.vertices.shape[0] == 0 or raw_mesh.faces.shape[0] == 0:
        return None

    # Fix face orientation + normals — CRITICAL for headless rendering
    # Without this, backface culling makes entire faces invisible
    try:
        trimesh.repair.fix_normals(raw_mesh, multibody=True)
        trimesh.repair.fix_winding(raw_mesh)
    except Exception:
        pass
    try:
        raw_mesh.process(validate=True)
        raw_mesh.fill_holes()
        raw_mesh.remove_duplicate_faces()
        raw_mesh.remove_degenerate_faces()
    except Exception:
        pass
    # Recompute vertex normals after all repairs
    try:
        raw_mesh.vertex_normals  # triggers recompute
    except Exception:
        pass

    # Decimate if too many faces (reduces wireframe noise from tessellation)
    face_count = raw_mesh.faces.shape[0]
    if face_count > target_faces:
        try:
            raw_mesh = raw_mesh.simplify_quadric_decimation(face_count=target_faces)
            trimesh.repair.fix_normals(raw_mesh, multibody=True)
        except Exception:
            pass  # Keep original if decimation fails

    return raw_mesh


# ── Main render function ──────────────────────────────────────────────────────

def render_stl_views(stl_path: str, output_dir: str) -> dict:
    """
    Render an STL file from multiple angles using pyrender.

    Returns:
        {
          "success": bool,
          "images": [{"view": str, "path": str, "width": int, "height": int}],
          "errors": [str],
          "skipped_blank": [str]   ← views that were blank and skipped
        }
    """
    result = {"success": False, "images": [], "errors": [], "skipped_blank": []}

    if not os.path.exists(stl_path):
        result["errors"].append(f"STL file not found: {stl_path}")
        return result

    os.makedirs(output_dir, exist_ok=True)

    # ── Imports ──
    try:
        import trimesh
    except ImportError:
        result["errors"].append("trimesh not installed: pip install trimesh")
        return result

    try:
        import pyrender
    except ImportError:
        result["errors"].append("pyrender not installed: pip install pyrender PyOpenGL")
        return result

    try:
        from PIL import Image
    except ImportError:
        result["errors"].append("Pillow not installed: pip install Pillow")
        return result

    # ── Load & prepare mesh ──
    try:
        raw = trimesh.load(stl_path, force='mesh')
    except Exception as e:
        result["errors"].append(f"Failed to load STL: {e}")
        return result

    mesh = _prepare_mesh(raw)
    if mesh is None:
        result["errors"].append("Mesh preparation failed — empty or invalid geometry")
        return result

    # Mesh center for camera targeting
    center = mesh.centroid.copy()

    # ── Render settings ──
    IMG_W, IMG_H = 1024, 1024
    FOV_Y = np.radians(40)           # 40° vertical FOV — good for architectural
    BG_COLOR = [0.08, 0.08, 0.08, 1.0]  # Near-black background — best contrast with light grey model

    # Camera distance: auto-fit so mesh fills ~65% of frame
    cam_dist = _compute_camera_distance(mesh, FOV_Y, fill_factor=0.65)

    # ── Views: (name, elevation°, azimuth°) ──
    # azimuth 0=front(+Y), 90=right(+X), 180=back(-Y), 270=left(-X)
    # Higher elevation for cardinal views (20°) so we see over the floor slab
    VIEWS = [
        ("front",      20,   0),   # Front with moderate elevation
        ("top",        85,   0),   # Near-top (85° to avoid gimbal lock)
        ("right",      20,  90),   # Right side
        ("back",       20, 180),   # Back
        ("left",       20, 270),   # Left side
    ]

    # ── Materials & lighting ──
    material = pyrender.MetallicRoughnessMaterial(
        baseColorFactor=[0.78, 0.80, 0.86, 1.0],   # Cool grey
        metallicFactor=0.05,
        roughnessFactor=0.70,
        doubleSided=True                             # Render both face sides (critical!)
    )

    # ── Build scene ──
    try:
        # Ambient light is critical — high value ensures even dark sides are lit
        scene = pyrender.Scene(bg_color=BG_COLOR, ambient_light=[0.55, 0.55, 0.55])

        py_mesh = pyrender.Mesh.from_trimesh(mesh, material=material, smooth=True)
        scene.add(py_mesh)

        # Key light — upper-right-front
        key_light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.5)
        key_pose = _lookat_matrix(
            eye=center + np.array([cam_dist*0.6, -cam_dist*0.8, cam_dist*1.2]),
            target=center
        )
        scene.add(key_light, pose=key_pose)

        # Fill light — left side, soft
        fill_light = pyrender.DirectionalLight(color=[0.75, 0.82, 1.0], intensity=1.8)
        fill_pose = _lookat_matrix(
            eye=center + np.array([-cam_dist*0.8, cam_dist*0.2, cam_dist*0.5]),
            target=center
        )
        scene.add(fill_light, pose=fill_pose)

        # Rim/back light — from below-back to get edge separation
        rim_light = pyrender.DirectionalLight(color=[0.9, 0.95, 1.0], intensity=1.2)
        rim_pose = _lookat_matrix(
            eye=center + np.array([0, cam_dist*0.9, -cam_dist*0.4]),
            target=center
        )
        scene.add(rim_light, pose=rim_pose)

    except Exception as e:
        result["errors"].append(f"Scene construction failed: {e}")
        return result

    # ── Renderer ──
    try:
        renderer = pyrender.OffscreenRenderer(
            viewport_width=IMG_W,
            viewport_height=IMG_H,
            point_size=1.0
        )
    except Exception as e:
        result["errors"].append(f"OffscreenRenderer init failed: {e}")
        return result

    persp_camera = pyrender.PerspectiveCamera(
        yfov=FOV_Y,
        aspectRatio=IMG_W / IMG_H,
        znear=cam_dist * 0.0005,  # Very close near plane so nothing clips
        zfar=cam_dist * 25.0
    )

    # Orthographic camera for top-down / plan view
    # xmag/ymag = half-size of the projection box (in scene units)
    orth_size = _compute_camera_distance(mesh, FOV_Y, fill_factor=0.70)
    orth_camera = pyrender.OrthographicCamera(
        xmag=orth_size * 0.5,
        ymag=orth_size * 0.5,
        znear=cam_dist * 0.0005,
        zfar=cam_dist * 25.0
    )

    # ── Render each view ──
    for view_name, elev_deg, azim_deg in VIEWS:
        try:
            eye = _spherical_to_cartesian(center, cam_dist, elev_deg, azim_deg)

            # For top view, use Y-axis as world_up to avoid gimbal lock
            if elev_deg >= 80:
                cam_pose = _lookat_matrix(eye, center, world_up=np.array([0.0, 1.0, 0.0]))
                camera = orth_camera  # Orthographic for top view
            else:
                cam_pose = _lookat_matrix(eye, center)
                camera = persp_camera

            cam_node = scene.add(camera, pose=cam_pose)
            color, depth = renderer.render(scene)
            scene.remove_node(cam_node)

            # If perspective rendered blank, try orthographic as fallback
            if _is_blank(color) and camera is persp_camera:
                cam_node2 = scene.add(orth_camera, pose=cam_pose)
                color, depth = renderer.render(scene)
                scene.remove_node(cam_node2)

            # Check for blank image — uniform color means view missed mesh
            if _is_blank(color):
                result["skipped_blank"].append(view_name)
                result["errors"].append(f"View '{view_name}' rendered blank — skipped")
                continue

            # Save image
            image_path = os.path.join(output_dir, f"render_{view_name}.png")
            img = Image.fromarray(color)
            
            # Sharpen slightly to improve VLM edge detection
            try:
                from PIL import ImageFilter, ImageEnhance
                img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=3))
                img = ImageEnhance.Contrast(img).enhance(1.15)
                img = ImageEnhance.Brightness(img).enhance(1.05)
            except Exception:
                pass  # PIL enhancement is optional

            img.save(image_path, "PNG", optimize=False)

            if os.path.exists(image_path):
                result["images"].append({
                    "view": view_name,
                    "path": image_path,
                    "width": IMG_W,
                    "height": IMG_H
                })

        except Exception as ve:
            result["errors"].append(f"Error rendering view '{view_name}': {ve}")

    try:
        renderer.delete()
    except Exception:
        pass

    result["success"] = len(result["images"]) > 0
    return result


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"success": False, "errors": ["Usage: pyvista_renderer.py <stl_path> <output_dir>"]}))
        sys.exit(1)

    stl_path = sys.argv[1]
    output_dir = sys.argv[2]

    result = render_stl_views(stl_path, output_dir)

    print("===RENDERER_RESULT_START===")
    print(json.dumps(result, indent=2))
    print("===RENDERER_RESULT_END===")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
