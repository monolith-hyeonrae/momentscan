"""blender-내부 측정-메쉬 렌더 스크립트 — recipe_preview 가 subprocess 로만 실행.

`blender --background --python _meshref_blender.py -- <payload.json>` 로 호출된다.
momentscan 은 이 파일을 **절대 import 하지 않는다**(bpy 는 venv 에 없고 blender 번들
python 에만 있음 — `_recipe_blender.py` 와 동일 경계). payload =
{faces: [[i,j,k]…], render_px, jobs: [{name, vertices: [[x,y,z]×468], out_png}]}.

리그 렌더(`_recipe_blender.py`)와 달리 **blend 파일이 없다** — empty scene 에
from_pydata 로 측정 메쉬(likeness neutral, 정준 프레임 y-up·z-out·RMS≈1)를 세워
클레이 가면으로 렌더한다. 카메라는 +Z 에서 -Z 응시 = 가면 정면.

출처: 루트 scratchpad_meshref_blender.py 승격 (2026-07-20 user 검수 조명/각도 —
표현력-격차 몽타주 승인본). 아래 고정값(EEVEE 단일 enum·world bg·클레이
색/roughness·cam lens/위치·¾뷰 회전·SUN key+AREA fill·subsurf 2·smooth)은
그 승인 스펙이다 — 승격 = 코드 조직화이지 재디자인이 아니다. 값 변경 금지.
"""

import json
import sys
from pathlib import Path

import bpy


def _build_scene(render_px):
    """승인 스펙의 고정 무대: empty scene + world bg + 클레이 재질 + 카메라 + 조명.
    → 클레이 material (잡마다 메시에 부착)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = render_px
    scene.render.engine = "BLENDER_EEVEE"   # blender 5.2: EEVEE(Next 통합) 단일 enum
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.32, 0.35, 1.0)
    scene.world = world

    mat = bpy.data.materials.new("Clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.87, 0.83, 0.78, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 55
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, 0.05, 5.6)
    cam.rotation_euler = (0.0, 0.0, 0.0)          # -Z 응시 = 가면 정면
    scene.camera = cam

    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", type="SUN"))
    key.data.energy = 6.0
    key.rotation_euler = (0.9, 0.15, 1.1)   # raking side-top — 부조 강조
    scene.collection.objects.link(key)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", type="AREA"))
    fill.data.energy = 40.0
    fill.location = (-1.5, -0.5, 2.5)
    scene.collection.objects.link(fill)
    return mat


def _render_job(job, faces, mat):
    """측정 정점 → from_pydata 메시 → ¾뷰 클레이 렌더 → 오브젝트 철거(다음 잡 무대 재사용)."""
    scene = bpy.context.scene
    mesh = bpy.data.meshes.new(job["name"])
    mesh.from_pydata([tuple(v) for v in job["vertices"]], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(job["name"], mesh)
    obj.rotation_euler = (0.0, -0.32, 0.0)   # 3/4 뷰(-18deg) — 윤곽·코 부조 가시화
    obj.data.materials.append(mat)
    scene.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = True
    mod = obj.modifiers.new("Subd", "SUBSURF")
    mod.levels = mod.render_levels = 2

    Path(job["out_png"]).parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = job["out_png"]
    bpy.ops.render.render(write_still=True)
    print(f"rendered {job['out_png']} (verts={len(job['vertices'])})")
    bpy.data.objects.remove(obj, do_unlink=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    payload = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    faces = [tuple(f) for f in payload["faces"]]
    render_px = int(payload.get("render_px", 512))

    mat = _build_scene(render_px)
    for job in payload["jobs"]:
        _render_job(job, faces, mat)
    print("MESH_RENDER_DONE", len(payload["jobs"]))


main()
