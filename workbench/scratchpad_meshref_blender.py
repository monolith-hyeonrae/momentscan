"""blender-내부: 측정 neutral(468정점) → 클레이 가면 렌더. payload JSON 경유.
승격됨 → surface/_meshref_blender.py (track/lk-meshref — 이 파일이 승인 스펙 원본).
payload = {faces: [[i,j,k]...], render_px, jobs: [{name, vertices: [[x,y,z]x468], out_png}]}
좌표 = momentscan 정준 프레임(y-up, z-out, RMS≈1) → 카메라 +Z에서 -Z 응시."""
import json
import sys

import bpy

payload = json.loads(open(sys.argv[-1], encoding="utf-8").read())
faces = [tuple(f) for f in payload["faces"]]
px = payload.get("render_px", 512)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = scene.render.resolution_y = px
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

for job in payload["jobs"]:
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

    scene.render.filepath = job["out_png"]
    bpy.ops.render.render(write_still=True)
    obj.hide_render = True
    bpy.data.objects.remove(obj, do_unlink=True)
print("MESH_RENDER_DONE", len(payload["jobs"]))
