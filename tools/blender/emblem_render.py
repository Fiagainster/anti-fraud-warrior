import bpy, math

bpy.ops.wm.read_factory_settings(use_empty=True)

# shield emblem: extruded shield-ish shape with bevel
bpy.ops.mesh.primitive_cube_add(size=2)
cube = bpy.context.active_object
cube.name = "shield"
cube.scale = (1.4, 0.35, 1.6)
bpy.ops.object.modifier_add(type='BEVEL')
bpy.context.object.modifiers["Bevel"].width = 0.18
bpy.context.object.modifiers["Bevel"].segments = 2

# second smaller cube in front (emblem core)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.55, 0.2))
core = bpy.context.active_object
core.scale = (0.9, 0.25, 0.9)
core.rotation_euler = (0, math.radians(45), 0)

mat = bpy.data.materials.new("green")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.05, 0.85, 0.35, 1)
bsdf.inputs["Metallic"].default_value = 0.7
bsdf.inputs["Roughness"].default_value = 0.35
cube.data.materials.append(mat)
core.data.materials.append(mat)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = 4.2
cam = bpy.data.objects.new("cam", cam_data)
cam.location = (3.2, -4.2, 2.6)
cam.rotation_euler = (math.radians(55), 0, math.radians(37))
bpy.context.collection.objects.link(cam)

key = bpy.data.lights.new("key", 'SUN')
key.energy = 3
key_l = bpy.data.objects.new("key", key)
key_l.rotation_euler = (math.radians(45), 0, math.radians(30))
bpy.context.collection.objects.link(key_l)

scene = bpy.context.scene
scene.camera = cam
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.show_shadows = True
scene.render.resolution_x = 220
scene.render.resolution_y = 220
scene.render.film_transparent = True
scene.render.filepath = r"D:/Project/反诈战士/build/emblem.png"
bpy.ops.render.render(write_still=True)
print("EMBLEM_OK")
