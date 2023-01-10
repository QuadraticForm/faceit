import bpy
from bpy.app.handlers import persistent

from ..core.modifier_utils import get_bake_modifiers
from ..landmarks.landmarks_utils import set_front_view, unlock_3d_view

landmarks_state_pre = 0
landmarks_active_pre = False


@persistent
def faceit_scene_update_handler(scene):
    active_object = bpy.context.object
    if active_object is not None:
        if active_object.name == "facial_landmarks":
            if bpy.context.preferences.addons["faceit"].preferences.use_vertex_size_scaling:
                bpy.context.preferences.themes[0].view_3d.vertex_size = bpy.context.preferences.addons["faceit"].preferences.landmarks_vertex_size
        else:
            if bpy.context.preferences.addons["faceit"].preferences.use_vertex_size_scaling:
                bpy.context.preferences.themes[0].view_3d.vertex_size = bpy.context.preferences.addons["faceit"].preferences.default_vertex_size
    ctrl_rig = scene.faceit_control_armature
    if ctrl_rig is not None:
        if ctrl_rig.name not in scene.objects:
            scene.faceit_control_armature = None
            # Remove old drivers etc.
            bpy.ops.faceit.clear_old_ctrl_rig_data()
    body_rig = scene.faceit_body_armature
    if body_rig is not None:
        if body_rig.name not in scene.objects:
            scene.faceit_body_armature = None
    faceit_objects = scene.faceit_face_objects
    if faceit_objects:
        for obj_item in faceit_objects:
            if obj_item.name not in scene.objects:
                index = scene.faceit_face_objects.find(obj_item.name)
                scene.faceit_face_objects.remove(index)
                continue
        if scene.faceit_workspace.active_tab in ('BAKE'):
            if not scene.faceit_shapes_generated and active_object is not None:
                get_bake_modifiers(objects=[active_object])
    if scene.faceit_shapes_generated:
        head_obj = scene.faceit_head_target_object
        if head_obj:  # and not scene.faceit_head_action:
            if head_obj.animation_data:
                action = head_obj.animation_data.action
                if action is not None and action != scene.faceit_head_action:
                    scene.faceit_head_action = action


@persistent
def faceit_modifiers_callback(scene):
    active_object = bpy.context.active_object
    if active_object is None:
        return


@persistent
def faceit_undo_post_handler(scene):
    global landmarks_state_pre, landmarks_active_pre
    lm_obj = scene.objects.get("facial_landmarks")
    landmarks_active_post = False
    if lm_obj:
        landmarks_active_post = not (lm_obj.hide_viewport or lm_obj.hide_get())
    if landmarks_active_post:
        if landmarks_state_pre != 3 and lm_obj["state"] == 3:
            set_front_view(bpy.context.area, view_selected=False)
    else:
        if landmarks_active_pre:
            unlock_3d_view()
            landmarks_active_pre = False


@persistent
def faceit_undo_pre_handler(scene):
    global landmarks_state_pre, landmarks_active_pre
    lm_obj = scene.objects.get("facial_landmarks")
    landmarks_active_pre = False
    if lm_obj:
        landmarks_active_pre = not (lm_obj.hide_viewport or lm_obj.hide_get())
        landmarks_state_pre = lm_obj["state"]


@persistent
def faceit_load_handler(_dummy):
    bpy.ops.faceit.subscribe_settings()
    scene = bpy.context.scene
    if not scene.faceit_shapes_generated and scene.faceit_face_objects:
        bpy.ops.faceit.load_bake_modifiers("EXEC_DEFAULT", object_target='ALL')


def register():
    if faceit_scene_update_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(faceit_scene_update_handler)
    if faceit_load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(faceit_load_handler)
    if faceit_undo_pre_handler not in bpy.app.handlers.undo_pre:
        bpy.app.handlers.undo_pre.append(faceit_undo_pre_handler)
    if faceit_undo_post_handler not in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.append(faceit_undo_post_handler)
    # Subscribe to the active object for the current file.


def unregister():
    if faceit_scene_update_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(faceit_scene_update_handler)
    if faceit_load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(faceit_load_handler)
    if faceit_undo_post_handler in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(faceit_undo_post_handler)
    if faceit_undo_pre_handler in bpy.app.handlers.undo_pre:
        bpy.app.handlers.undo_pre.remove(faceit_undo_pre_handler)
