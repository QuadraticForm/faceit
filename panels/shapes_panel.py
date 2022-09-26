
import os

import bpy

from ..core import faceit_data as fdata
from ..core.retarget_list_base import (DrawRegionsFilterBase,
                                       DrawTargetShapesListBase,
                                       ResetRegionsOperatorBase,
                                       RetargetShapesListBase,
                                       TargetShapesListBase)
from ..retargeting.retarget_list_operators import get_active_retarget_list

from.ui import FACEIT_PT_Base


class FACEIT_PT_BaseRetargetShapes(FACEIT_PT_Base):
    UI_TAB = 'SHAPES'


class FACEIT_PT_TargetShapeLists(FACEIT_PT_BaseRetargetShapes, bpy.types.Panel):
    bl_label = 'Target Shapes'
    bl_options = set()
    bl_idname = 'FACEIT_PT_TargetShapeLists'

    @classmethod
    def poll(cls, context):
        return super().poll(context)

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        col = layout.column()

        box = col.box()
        row = box.row()
        row.label(text='Display Expressions')
        row = box.row()
        row.prop(scene, 'faceit_display_retarget_list', expand=True)

        col.separator()

        if scene.faceit_display_retarget_list == 'ARKIT':
            # ARKIT
            if scene.faceit_arkit_retarget_shapes:
                row = col.row()
                row.label(text='  Source Shape')
                row.label(text='Target Shape')
                col.template_list('FACEIT_UL_ShapeRetargetList', '', bpy.context.scene,
                                  'faceit_arkit_retarget_shapes', scene, 'faceit_arkit_retarget_shapes_index')
                row = col.row(align=True)
                row.prop(scene, 'faceit_sync_shapes_index', icon='UV_SYNC_SELECT')
                if scene.faceit_sync_shapes_index:
                    if scene.faceit_shape_key_lock:
                        pin_icon = 'PINNED'
                    else:
                        pin_icon = 'UNPINNED'
                    row.prop(scene, 'faceit_shape_key_lock', icon=pin_icon)
            else:
                row = col.row(align=True)
                row.operator_context = 'EXEC_DEFAULT'
                op = row.operator('faceit.init_retargeting', text='Find ARKit Shapes', icon='FILE_REFRESH')
                op.expression_sets = 'ARKIT'
                row = col.row()
                row.label(text='Presets')

                row = col.row(align=True)
                row.operator_context = 'INVOKE_DEFAULT'

                row.operator('faceit.import_retargeting_map').expression_sets = 'ARKIT'
                row.menu('FACEIT_MT_PresetImport', text='', icon='DOWNARROW_HLT')
                row.operator('faceit.export_retargeting_map').expression_sets = 'ARKIT'

        elif scene.faceit_display_retarget_list == 'A2F':
            # A2F
            if scene.faceit_a2f_retarget_shapes:
                row = col.row()
                row.label(text='  Source Shape')
                row.label(text='Target Shape')
                col.template_list('FACEIT_UL_ShapeRetargetList', '', bpy.context.scene,
                                  'faceit_a2f_retarget_shapes', scene, 'faceit_a2f_retarget_shapes_index')
                row = col.row(align=True)
                row.prop(scene, 'faceit_sync_shapes_index', icon='UV_SYNC_SELECT')
                if scene.faceit_sync_shapes_index:
                    # row = col.row()
                    if scene.faceit_shape_key_lock:
                        pin_icon = 'PINNED'
                    else:
                        pin_icon = 'UNPINNED'
                    row.prop(scene, 'faceit_shape_key_lock', icon=pin_icon)
            else:
                row = col.row(align=True)
                row.operator_context = 'EXEC_DEFAULT'
                op = row.operator('faceit.init_retargeting', text='Find A2F Shapes', icon='FILE_REFRESH')
                op.expression_sets = 'A2F'
                row = col.row()
                row.label(text='Presets')

                row = col.row(align=True)
                row.operator_context = 'INVOKE_DEFAULT'
                row.operator('faceit.import_retargeting_map').expression_sets = 'A2F'
                # row.menu('FACEIT_MT_PresetImport', text='', icon='DOWNARROW_HLT')
                row.operator('faceit.export_retargeting_map').expression_sets = 'A2F'


class FACEIT_PT_RetargetShapesSetup(FACEIT_PT_BaseRetargetShapes, bpy.types.Panel):
    bl_label = 'Target Shapes Setup'
    bl_options = set()
    bl_idname = 'FACEIT_PT_RetargetShapesSetup'
    faceit_predecessor = 'FACEIT_PT_TargetShapeLists'

    @classmethod
    def poll(cls, context):
        if super().poll(context):
            scene = context.scene
            if scene.faceit_display_retarget_list == 'ARKIT' and scene.faceit_arkit_retarget_shapes:
                return True
            if scene.faceit_display_retarget_list == 'A2F' and scene.faceit_a2f_retarget_shapes:
                return True

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        box = layout.box()
        col = box.column(align=True)

        if not scene.faceit_face_objects:
            row = col.row()
            row.alert = True
            op = row.operator('faceit.go_to_tab', text='Register Objects First...')
            op.tab = 'SETUP'
        else:
            row = col.row()
            row.label(text='Initialize List')

            row = col.row(align=True)
            op = row.operator('faceit.init_retargeting', text='Find Target Shapes', icon='FILE_REFRESH')
            op.expression_sets = scene.faceit_display_retarget_list
            row = col.row(align=True)
            op = row.operator('faceit.reset_retarget_shapes', text='Reset', icon='LOOP_BACK')
            op.expression_sets = scene.faceit_display_retarget_list

            row = col.row()
            row.label(text='Presets')

            row = col.row(align=True)
            row.operator_context = 'INVOKE_DEFAULT'

            op = row.operator('faceit.import_retargeting_map')
            op.expression_sets = scene.faceit_display_retarget_list
            if scene.faceit_display_retarget_list == 'ARKIT':
                row.menu('FACEIT_MT_PresetImport', text='', icon='DOWNARROW_HLT')
            op = row.operator('faceit.export_retargeting_map')
            op.expression_sets = scene.faceit_display_retarget_list

            row = col.row(align=True)
            row.label(text='Face Regions')
            row = col.row(align=True)
            row.operator('faceit.set_default_regions')

            if scene.faceit_display_retarget_list == 'ARKIT' and scene.faceit_arkit_retarget_shapes:
                row = col.row()
                row.label(text='Names and Indices')
                row = col.row()
                row.prop(scene, 'faceit_retargeting_naming_scheme', text='Name Scheme', expand=True)

                row = col.row()
                row.operator('faceit.retarget_names', icon='FILE_FONT')
                row = col.row()
                row.operator_context = 'EXEC_DEFAULT'
                row.operator('faceit.reorder_keys', icon='FILE_FONT').order = scene.faceit_retargeting_naming_scheme
                row.operator_context = 'INVOKE_DEFAULT'


class FACEIT_UL_TargetShapes(TargetShapesListBase, bpy.types.UIList):
    # the edit target shapes operator
    edit_target_shapes_operator = 'faceit.edit_target_shape'
    # the edit target shapes operator
    remove_target_shapes_operator = 'faceit.remove_target_shape'


class FACEIT_OT_DrawTargetShapesList(DrawTargetShapesListBase, bpy.types.Operator):
    bl_label = "Target Shapes"
    bl_idname = 'faceit.draw_target_shapes_list'

    edit_target_shapes_operator = 'faceit.edit_target_shape'
    target_shapes_list = 'FACEIT_UL_TargetShapes'
    use_display_name = True

    @classmethod
    def poll(cls, context):
        return super().poll(context)

    @staticmethod
    def get_retarget_shapes():
        ''' Get the retarget_list property group '''
        return get_active_retarget_list()
        # return bpy.context.scene.faceit_arkit_retarget_shapes

# --------------- Expression Retarget Listen  --------------------
# | - ARKit retarget shapes
# | - A2F retarget shapes
# ----------------------------------------------


class FACEIT_UL_ShapeRetargetList(RetargetShapesListBase, bpy.types.UIList):
    # the edit target shapes operator
    edit_target_shapes_operator = 'faceit.edit_target_shape'
    # the remove target shapes operator
    remove_target_shapes_operator = 'faceit.remove_target_shape'
    # the clear target shapes operator
    clear_target_shapes_operator = 'faceit.clear_target_shapes'

    draw_target_shapes_operator = 'faceit.draw_target_shapes_list'

    draw_region_filter_operator = 'faceit.draw_regions_filter'
    reset_regions_filter_operator = 'faceit.reset_regions_filter'

    property_name = 'display_name'


class FACEIT_MT_PresetImport(bpy.types.Menu):
    bl_label = 'Import Retargeting Preset'

    file_path = fdata.get_retargeting_presets()

    def draw(self, _context):
        layout = self.layout
        row = layout.row()
        row.operator_context = 'EXEC_DEFAULT'
        row.operator('faceit.import_retargeting_map', text='CC3').filepath = os.path.join(self.file_path, 'cc3.json')
        row = layout.row()
        row.operator('faceit.import_retargeting_map', text='CC3+').filepath = os.path.join(self.file_path, 'cc3+.json')


class FACEIT_OT_DrawRegionsFilter(DrawRegionsFilterBase, bpy.types.Operator):
    ''' Filter the displayed expressions by face regions'''

    bl_label = "Filter Regions"
    bl_idname = 'faceit.draw_regions_filter'

    @classmethod
    def poll(cls, context):
        return super().poll(context)


class FACEIT_OT_ResetRegionsFilter(ResetRegionsOperatorBase, bpy.types.Operator):
    ''' Reset the regions filter to default settings'''
    bl_idname = 'faceit.reset_regions_filter'

    @staticmethod
    def get_face_regions(context):
        # return get_active_retarget_list()
        return context.scene.faceit_face_regions
