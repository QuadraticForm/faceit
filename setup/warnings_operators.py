
import bmesh
import bpy
from bpy.props import BoolProperty, StringProperty

from ..panels.draw_utils import draw_text_block

from ..core import faceit_utils as futils
from ..core import mesh_utils

WARNINGS_OUT = {
    'MIRROR': 'Object holds a MIRROR modifier. This can lead to problems in binding and/or baking! You should apply it first. If you need to preserve shape keys, check out the \'Apply Modifiers\' operator in bake tab/extra utils.',
    'MAIN_GROUP': 'The Main vertex group should only be assigned to one connected surface. Please make sure that it only contains linked vertices!',
    'TRANSFORMS_ANIM': 'The Object has animation keyframes on transform channels. This might leat to problems in binding. Clear the keyframes or disable the action.',
    'ANIMATED_ARMATURE': 'The Object is bound to an animated armature. Put the armature to Rest Position or disable the action.',
    'SURFACE_DEFORM': 'The Object is bound to another object with a Surface Deform modifier. Either remove the binding / modifier or register the source object instead of this object.'
    # 'AMBIGUOUS_TARGETS': 'Some shapes have been set as targets for other source shapes.'
}


def get_island_count(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # deselect all verts:
    for f in bm.faces:
        f.select = False
    bm.select_flush(False)

    # SelectionIslands finds and stores selected and non-selected islands
    island_count = mesh_utils.SelectionIslands(bm.verts).get_island_count()

    bm.free()

    return island_count


def all_verts_in_main_group(obj):
    '''Check if any vertices in @obj are assigned to faceit_main'''
    vg = obj.vertex_groups.get('faceit_main')
    if vg:
        for v in obj.data.vertices:
            if any(g.group == vg.index for g in v.groups):
                continue
            return False
        return True
    return False


def check_warnings_for_face_item(item):

    all_warnings = []
    obj = item.get_object()

    rig = futils.get_faceit_armature()

    if item.part == 'main' and 'faceit_main' not in obj.vertex_groups:
        if get_island_count(obj) > 1:
            all_warnings.append('MAIN_GROUP')

    elif 'faceit_main' in obj.vertex_groups:
        if all_verts_in_main_group(obj) and get_island_count(obj) > 1:
            all_warnings.append('MAIN_GROUP')

    if futils.get_modifiers_of_type(obj, 'MIRROR'):
        all_warnings.append('MIRROR')

    # other_rigs = []
    for mod in obj.modifiers:
        if not mod.show_viewport:
            continue
        if 'ANIMATED_ARMATURE' not in all_warnings:
            if mod.type == 'ARMATURE':
                rig_target = mod.object
                if rig_target != rig and rig_target is not None:
                    if rig_target.data.pose_position == 'REST':
                        continue
                    if getattr(rig_target, 'animation_data'):
                        if getattr(rig_target.animation_data, 'action'):
                            for fc in rig_target.animation_data.action.fcurves:
                                if any(a in fc.data_path
                                        for a in ['location', 'scale', 'rotation_euler', 'rotation_quaternion']):
                                    all_warnings.append('ANIMATED_ARMATURE')
                                    break

        if 'SURFACE_DEFORM' not in all_warnings:
            if mod.type == 'SURFACE_DEFORM':
                all_warnings.append('SURFACE_DEFORM')
                break

    if getattr(obj, 'animation_data'):
        if getattr(obj.animation_data, 'action'):
            for fc in obj.animation_data.action.fcurves:
                if any(a in fc.data_path
                        for a in ['location', 'scale', 'rotation_euler', 'rotation_quaternion']):
                    all_warnings.append('TRANSFORMS_ANIM')
                    break

    item.warnings = ''

    if all_warnings:
        for warn in all_warnings:
            item.warnings += warn + ','

    return all_warnings


class FACEIT_OT_CheckWarning(bpy.types.Operator):
    '''There are Warnings for this object'''
    bl_idname = 'faceit.face_object_warning_check'
    bl_label = 'Check Warnings'
    bl_options = {'INTERNAL'}

    # the name of the facial part
    item_name: StringProperty(options={'SKIP_SAVE'})

    set_show_warnings: BoolProperty(options={'SKIP_SAVE'})

    check_main: BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):

        scene = context.scene

        if self.item_name == 'ALL':
            items = scene.faceit_face_objects
        else:
            items = [scene.faceit_face_objects[self.item_name]]

        any_warning = False

        for item in items:

            all_warnings = check_warnings_for_face_item(item)

            if all_warnings:
                any_warning = True

                for warn in all_warnings:
                    self.report({'WARNING'}, f'[{item.name}]: {WARNINGS_OUT[warn]}')

        if any_warning:
            if self.set_show_warnings:
                scene.faceit_show_warnings = True
        else:
            scene.faceit_show_warnings = False
            self.report({'INFO'}, 'No Warnings found.')

        if not any('faceit_main' in obj.vertex_groups for obj in futils.get_faceit_objects_list()):
            self.report({'WARNING'}, 'Main Face Vertex Island could not be found. Please assign the Main Vertex Group!')

        return{'FINISHED'}


class FACEIT_OT_DisplayWarning(bpy.types.Operator):
    '''There are Warnings for this object'''
    bl_idname = 'faceit.face_object_warning'
    bl_label = 'Faceit Geometry Warnings'
    bl_options = {'INTERNAL'}

    item_name: StringProperty(name='Item Name')

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.label(text='WARNINGS')

        row = layout.row(align=True)
        web = row.operator('faceit.open_web', text='Prepare Geometry', icon='QUESTION')
        web.link = 'https://faceit-doc.readthedocs.io/en/latest/prepare/'

        layout.separator()

        item = context.scene.faceit_face_objects[self.item_name]
        warnings = item.warnings.split(',')

        for warn in warnings:
            if warn:
                # row = layout.row()
                # row.label(text=warn.replace('_', ' '), icon='ERROR')
                warning_message = WARNINGS_OUT[warn]
                draw_text_block(layout=layout, text=warning_message,
                                heading=warn.replace('_', ' '), heading_icon='ERROR')
                # for w_row in textwrap.wrap(warn, 50):
                #     row = layout.row()
                #     row.label(text=w_row)

        row = layout.row(align=True)
        icon_hide = 'HIDE_OFF' if context.scene.faceit_show_warnings else 'HIDE_ON'
        row.prop(context.scene, 'faceit_show_warnings', icon=icon_hide)

    def invoke(self, context, event):
        item = context.scene.faceit_face_objects[self.item_name]
        if not check_warnings_for_face_item(item):
            self.report({'INFO'}, 'No Warnings found.')
            return {'FINISHED'}
        else:
            wm = context.window_manager
            return wm. invoke_popup(self)

    def execute(self, context):

        return{'FINISHED'}
