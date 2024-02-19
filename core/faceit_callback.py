import bpy
from ..landmarks.landmarks_utils import unlock_3d_view


class FACEIT_OT_SubscribeSettings(bpy.types.Operator):
    '''Subscribe msgbus to the active object'''
    bl_idname = "faceit.subscribe_settings"
    bl_label = "Subscribe"

    def execute(self, context):
        context.scene.faceit_subscribed = False
        msgbus(self, context)
        return {'FINISHED'}


def msgbus(self, context):
    '''Activates the subscribtion to the active object'''
    if context.scene.faceit_subscribed is True:
        return

    subscribe_to_active_object = bpy.types.LayerObjects, "active"
    bpy.msgbus.subscribe_rna(
        key=subscribe_to_active_object,
        owner=self,
        args=(context,),
        notify=faceit_active_object_callback,
    )
    subscribe_to_mode = bpy.types.Object, "mode"
    bpy.msgbus.subscribe_rna(
        key=subscribe_to_mode,
        owner=self,
        args=(context,),
        notify=faceit_switch_modes_callback,
    )

    # subscribe_to_modifier = bpy.context.object.path_resolve("modifiers.active", False)
    # subscribe_to_modifier = bpy.types.Object, "modifiers"
    # subscribe_to_modifier = bpy.types.Modifier, "is_active"
    # print("subscribe to", subscribe_to_modifier)
    # bpy.msgbus.subscribe_rna(
    #     key=subscribe_to_modifier,
    #     owner=self,
    #     args=(context,),
    #     notify=modifiers_callback,
    # )

    context.scene.faceit_subscribed = True


def faceit_switch_modes_callback(context):
    '''Runs when the object mode changes'''
    if context.preferences.addons['faceit'].preferences.auto_lock_3d_view:
        obj = context.object
        if obj is None:
            return
        if obj.name == "facial_landmarks":
            if obj.mode == 'EDIT':
                if obj["state"] == 3:
                    bpy.ops.faceit.lock_3d_view_front('INVOKE_DEFAULT', set_edit_mode=False,
                                                      find_area_by_mouse_position=True)
            else:
                unlock_3d_view()


def faceit_active_object_callback(context):
    '''Runs every time the active object changes'''
    scene = context.scene
    active_object = bpy.context.active_object
    if active_object is None:
        return
    if active_object.name == "facial_landmarks":
        if bpy.context.preferences.addons["faceit"].preferences.use_vertex_size_scaling:
            bpy.context.preferences.themes[0].view_3d.vertex_size = bpy.context.preferences.addons["faceit"].preferences.landmarks_vertex_size
    else:
        if bpy.context.preferences.addons["faceit"].preferences.use_vertex_size_scaling:
            bpy.context.preferences.themes[0].view_3d.vertex_size = bpy.context.preferences.addons["faceit"].preferences.default_vertex_size
    # set the active control rig
    # NID, this sets the active control rig on active object change, which is kinda annoying.
    # NID, xiaohua's face rig is a little in compatible with FaceIt's Contrl Rig Panel, and it doesn't need faceit_control_armature to be set to work.
    # NID, so we normally keep faceit_control_armature to None.
    # NID, and, when faceit_control_armature is set, live mocap preview is disabled (easonable on original faceit rig, cuz shapekeys are driven by ctrl_rig OR live mocap, so ctrl_rig need to be disconnected to enable live mocap preview)
    # NID, so it's kinda annoying that faceit_control_armature automatically sets every time user click on the armature object
    #if active_object.get("ctrl_rig_version"):
    #    scene.faceit_control_armature = active_object
    # Set the active faceit_objects index
    if scene.faceit_workspace.active_tab in ('SETUP', 'BAKE'):
        if active_object.name in scene.faceit_face_objects:
            index = scene.faceit_face_objects.find(active_object.name)
            if index not in (-1, scene.faceit_face_index):
                scene.faceit_face_index = index


# def modifiers_callback(context):
#     print("yo")
#     print("yoooo")
#     scene = context.scene
#     active_object = bpy.context.active_object
#     if active_object is None:
#         return
#     obj = scene.faceit_face_objects.get(active_object.name)
#     if obj:
#         print("found change.")
#         obj.modifiers.clear()
#         for mod in active_object.modifiers:
#             mod_item = obj.modifiers.add()
#             mod_item.name = mod.name
#             mod_item.type = mod.type
#             mod_item.show_viewport = mod.show_viewport
#             mod_item.show_render = mod.show_render
#             mod_item.show_in_editmode = mod.show_in_editmode
#             mod_item.show_on_cage = mod.show_on_cage
#             mod_item.show_expanded = mod.show_expanded
#             mod_item.show_in_editmode = mod.show_in_editmode
#             mod_item.show_in_editmode = mod.show_in_editmode
