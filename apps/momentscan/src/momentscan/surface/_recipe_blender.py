"""blender-내부 apply/render 스크립트 — recipe_preview 가 subprocess 로만 실행.

`blender --background --python _recipe_blender.py -- <payload.json>` 로 호출된다.
momentscan 은 이 파일을 **절대 import 하지 않는다**(bpy 는 venv 에 없고 blender 번들
python 에만 있음 — 흡수 설계). payload = {blend, render_px, jobs:[{shape_key_values,
chosen_hair, out_png}]}. blend 를 한 번만 열고(449M) 잡을 순회 렌더한다.

출처: appearance-engine `blender_render.py` 하니스 흡수 (2026-07-20, absorption-plan §1
A5). re-open=Basis 리셋, 비-Basis 0 리셋, hair 가시성, bbox 자동 카메라(50mm),
key/fill, EEVEE Next 폴백, 512². 헤드-온리 정면 창.

이식 정정(2026-07-20 실측): 디자이너 blend 의 shape key 이름 일부가 선행 제어문자
(\x08)를 달고 있다(예 '\x08Eyebrow_Thickness'). 구 하니스의 identity-map 은 그 2키를
조용히 누락했다 — 여기선 이름을 정리(strip)해 매칭하므로 13키가 전부 적용된다.
매칭 실패 키는 조용히 넘기지 않고 print 로 자백한다(code-style §3 정직 열화).
"""

import json
import sys
import unicodedata
from pathlib import Path

import bpy

# head-only 정면 창을 위해 숨기는 몸통 파츠(구 하니스 HIDE_NAMES).
HIDE_NAMES = (
    "shose_feet_left", "shose_feet_right",
    "basic+body", "belt",
    "glove_Hand_left", "glove_Hand_Right",
    "Armature",
)
HEAD_MESH_OBJECT_NAME = "head+base"
# body+basic_260527.blend 의 hair 메시(hair08·hair10 부재).
ALL_HAIR_NAMES = (
    "hair01", "hair02", "hair03", "hair04", "hair05", "hair06", "hair07",
    "hair09", "hair10", "hair11", "hair12", "hair13", "hair14", "hair15",
)


def _clean(name):
    """shape key 이름에서 선행 제어문자/공백 제거 — blend 데이터 quirk(\x08) 흡수."""
    return "".join(c for c in name if unicodedata.category(c)[0] != "C").strip()


def _setup_camera_and_lights(head_obj):
    """헤드 bbox 중심에 정면 카메라(50mm) + key(sun)/fill(area) 배치. 구 하니스 그대로."""
    from mathutils import Euler, Vector

    corners = [head_obj.matrix_world @ Vector(c) for c in head_obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    head_height = max(zs) - min(zs)
    head_depth = max(ys) - min(ys)

    for name in ("RenderCam", "RenderKey", "RenderFill"):
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)

    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.lens = 50
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    distance = max(head_height * 2.0, head_depth + 0.6)
    cam_obj.location = (cx, cy - distance, cz)
    cam_obj.rotation_euler = Euler((1.5708, 0.0, 0.0), "XYZ")
    bpy.context.scene.camera = cam_obj

    key_data = bpy.data.lights.new("RenderKey", type="SUN")
    key_data.energy = 4.0
    key_obj = bpy.data.objects.new("RenderKey", key_data)
    bpy.context.scene.collection.objects.link(key_obj)
    key_obj.location = (cx + 1.0, cy - 1.5, cz + 1.5)
    key_obj.rotation_euler = Euler((0.9, 0.4, 0.0), "XYZ")

    fill_data = bpy.data.lights.new("RenderFill", type="AREA")
    fill_data.energy = 80.0
    fill_data.size = 1.5
    fill_obj = bpy.data.objects.new("RenderFill", fill_data)
    bpy.context.scene.collection.objects.link(fill_obj)
    fill_obj.location = (cx - 1.0, cy - 1.5, cz + 0.5)
    fill_obj.rotation_euler = Euler((1.0, -0.4, 0.0), "XYZ")

    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("RenderWorld")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node is not None:
        bg_node.inputs["Color"].default_value = (0.92, 0.93, 0.95, 1.0)
        bg_node.inputs["Strength"].default_value = 1.0


def _apply_shape_keys(head_obj, shape_key_values):
    """비-Basis 키를 0 리셋 후 요청 값 적용(clean-name 매칭). (적용수, 미스키) 반환."""
    blocks = head_obj.data.shape_keys.key_blocks
    for sk in blocks:
        if sk.name != "Basis":
            sk.value = 0.0

    by_clean = {_clean(sk.name): sk for sk in blocks if sk.name != "Basis"}
    applied, missing = 0, []
    for name, val in shape_key_values.items():
        sk = by_clean.get(_clean(name))
        if sk is None:
            missing.append(name)
            continue
        sk.value = float(max(0.0, min(1.0, val)))
        applied += 1
    return applied, missing


def _set_hair_visibility(chosen_hair):
    """chosen_hair 만 렌더 가시(None 이면 전부 숨김)."""
    for hname in ALL_HAIR_NAMES:
        h = bpy.data.objects.get(hname)
        if h is None:
            continue
        h.hide_render = (chosen_hair is None) or (hname != chosen_hair)
        h.hide_viewport = h.hide_render


def _hide_body():
    for name in HIDE_NAMES:
        o = bpy.data.objects.get(name)
        if o is not None:
            o.hide_render = True
            o.hide_viewport = True


def _render_to(out_png, render_px):
    scene = bpy.context.scene
    requested = "BLENDER_EEVEE_NEXT" if hasattr(scene.render, "use_motion_blur") else "BLENDER_EEVEE"
    try:
        scene.render.engine = requested
    except Exception:  # noqa: BLE001 — 엔진 미가용 시 legacy 폴백(경계 캐치)
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = render_px
    scene.render.resolution_y = render_px
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(out_png)
    scene.render.image_settings.file_format = "PNG"
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 16
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    payload = json.loads(Path(argv[0]).read_text(encoding="utf-8"))

    blend = payload["blend"]
    render_px = int(payload.get("render_px", 512))
    bpy.ops.wm.open_mainfile(filepath=blend)

    head_obj = bpy.data.objects.get(HEAD_MESH_OBJECT_NAME)
    if head_obj is None or head_obj.data.shape_keys is None:
        sys.exit(f"head mesh '{HEAD_MESH_OBJECT_NAME}' (with shape keys) missing in {blend}")

    _hide_body()
    for job in payload["jobs"]:
        applied, missing = _apply_shape_keys(head_obj, job["shape_key_values"])
        _set_hair_visibility(job.get("chosen_hair"))
        _setup_camera_and_lights(head_obj)
        Path(job["out_png"]).parent.mkdir(parents=True, exist_ok=True)
        _render_to(job["out_png"], render_px)
        print(f"rendered {job['out_png']} (applied={applied}/13, hair={job.get('chosen_hair') or '—'})")
        if missing:
            print(f"  WARNING unmatched shape keys: {missing}")


main()
