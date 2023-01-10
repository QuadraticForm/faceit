
import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Vector

from .landmarks_utils import check_if_area_is_active, set_front_view, check_is_quad_view, unlock_3d_view

from ..core.mesh_utils import get_max_dim_in_direction

from ..panels.draw_utils import draw_text_block

from ..core import faceit_data as fdata
from ..core import faceit_utils as futils
from ..core import shape_key_utils as sk_utils
from ..core import vgroup_utils as vg_utils
from ..rigging import rig_utils
from . import landmarks_data as lm_data


class FACEIT_OT_FacialLandmarks(bpy.types.Operator):
    '''Place the facial landmarks. 1. Match Chin Position, 2. Match Eye Height, 3. Match Jaw Width'''
    bl_idname = 'faceit.facial_landmarks'
    bl_label = 'facial_landmarks'
    bl_options = {'UNDO', 'INTERNAL'}

    mouse_x: bpy.props.IntProperty()
    mouse_y: bpy.props.IntProperty()

    # initial cursor position to scale with mouse movement
    initial_mouse_scale = 0
    # to check if the scale has been initialized
    set_init_scale = False
    # the initial dimensions used abort scaling operation
    initial_dimensions = (0, 0, 0)

    area_width = 0
    area_height = 0
    area_x = 0
    area_y = 0

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return context.scene.faceit_face_objects

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        area = context.area
        self.area_width = area.width
        self.area_height = area.height
        self.area_x = area.x
        self.area_y = area.y
        self.execute(context)
        context.scene.tool_settings.use_snap = False
        self.set_face_pos(context, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):

        scene = context.scene
        bpy.ops.faceit.unlock_3d_view()

        if context.object:
            if not futils.get_hide_obj(context.object):  # context.object.hide_viewport == False:
                bpy.ops.object.mode_set(mode='OBJECT')

        # create the collection that holds faceit objects
        faceit_collection = futils.get_faceit_collection()

        futils.clear_object_selection()
        main_obj = futils.get_main_faceit_object()
        if main_obj is None:
            self.report({'ERROR'}, 'Please assign the Main Vertex Group to the Face Mesh! (Setup Tab)')
            return {'CANCELLED'}
        futils.set_active_object(main_obj.name)
        area = context.area
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                if space.local_view:
                    bpy.ops.view3d.localview()
                shading = space.shading
                # shading.type = 'SOLID'
                shading.show_xray = False
                shading.show_xray_wireframe = False
        if check_is_quad_view(area):
            bpy.ops.screen.region_quadview()
        bpy.ops.view3d.view_selected(use_all_regions=False)
        bpy.ops.view3d.view_axis(type='FRONT')
        # load the landmarks object
        filepath = fdata.get_landmarks_file()
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.objects = data_from.objects
        # add the objects to the scene
        for obj in data_to.objects:
            if obj.type == 'MESH':
                if scene.faceit_asymmetric:
                    if obj.name == 'facial_landmarks_asymmetric':
                        faceit_collection.objects.link(obj)
                        lm_obj = futils.get_object('facial_landmarks_asymmetric')
                    else:
                        bpy.data.objects.remove(obj)
                else:
                    if obj.name == 'facial_landmarks':
                        faceit_collection.objects.link(obj)
                        lm_obj = futils.get_object('facial_landmarks')
                    else:
                        bpy.data.objects.remove(obj)
        lm_obj.name = 'facial_landmarks'
        if main_obj:
            lm_obj.location.y = get_max_dim_in_direction(
                obj=main_obj, direction=Vector((0, -1, 0)), vertex_group_name="faceit_main")[1] - lm_obj.dimensions[1]
        futils.clear_object_selection()
        futils.set_active_object(lm_obj.name)
        # initialize the state prop
        if lm_obj:
            lm_obj["state"] = 0
        # Set scale to main obj height. Main obj can be a body mesh at this point.
        lm_obj.dimensions[2] = main_obj.dimensions[2] / 2
        lm_obj.scale = [lm_obj.scale[2], ] * 3
        self.report({'INFO'}, "Align the Landmarks with your characters chin!")

        return {'FINISHED'}

    def set_scale_to_head_height(self, lm_obj):
        '''Set scale after applying the chin position.'''
        main_obj = futils.get_main_faceit_object()
        mw = main_obj.matrix_world
        # get the global coordinates
        global_v_co = [mw @ v.co for v in main_obj.data.vertices]
        # get the highest point in head mesh (temple)
        v_highest = max([co.z for co in global_v_co])
        # get distance from chin to temple
        head_height = lm_obj.location[2] - v_highest
        # apply scale
        lm_obj.dimensions[2] = head_height
        lm_obj.scale = [lm_obj.scale[2], ] * 3

    def set_face_pos(self, context, event):
        obj = futils.get_object('facial_landmarks')
        if not obj:
            return
        _region = context.region
        _region_3d = context.space_data.region_3d
        coord = 0, event.mouse_region_y
        new_location = view3d_utils.region_2d_to_location_3d(_region, _region_3d, coord, obj.location)
        obj.location.z = new_location.z

    def set_face_scale(self, context, event, axis=2):

        obj = bpy.data.objects.get('facial_landmarks')
        if obj is None:
            return

        rv3d = context.region_data
        coord = event.mouse_region_x, event.mouse_region_y

        _region = context.region
        _region_3d = context.space_data.region_3d
        mouse_pos = view3d_utils.region_2d_to_origin_3d(_region, rv3d, coord)

        # initialize reference scale
        if not self.set_init_scale:
            # get the initial dimensions before altering - used to reset
            self.initial_dimensions = obj.dimensions[:]
            # set the initial relative mouse position for scaling
            self.initial_mouse_scale = mouse_pos[axis] - obj.dimensions[axis]

            self.set_init_scale = True

        # get the distance from initial mouse
        face_dim = mouse_pos[axis] - self.initial_mouse_scale
        # apply the dimension on x axis
        obj.dimensions[axis] = face_dim

    # modal operations depending on current state
    def modal(self, context, event):

        mouse_x = event.mouse_x
        mouse_y = event.mouse_y

        lm_obj = futils.get_object('facial_landmarks')
        if not lm_obj:
            self.report({'WARNING'}, 'No landmarks object, could not finish')
            return {'CANCELLED'}

        current_state = lm_obj["state"]

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}

        # modal operations: move, scale height, scale width
        if event.type == 'MOUSEMOVE':
            if mouse_x <= self.area_x:
                context.window.cursor_warp(self.area_x + self.area_width, mouse_y)
            if mouse_x >= self.area_x + self.area_width:
                context.window.cursor_warp(self.area_x, mouse_y)
            if mouse_y <= self.area_y:
                context.window.cursor_warp(mouse_x, self.area_y + self.area_height)
            if mouse_y >= self.area_y + self.area_height:
                context.window.cursor_warp(mouse_x, self.area_y)
            if lm_obj["state"] == 0:
                self.set_face_pos(context, event)
            elif lm_obj["state"] == 1:
                self.set_face_scale(context, event, axis=2)
            elif lm_obj["state"] == 2:
                self.set_face_scale(context, event, axis=0)

        # go into next state / finish
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if current_state == 0:
                self.report({'INFO'}, "Match the face height")
                lm_obj["state"] = 1
                self.set_init_scale = False
                # scale to the right dimensions:
                self.set_scale_to_head_height(lm_obj=lm_obj)
                bpy.ops.view3d.view_selected(use_all_regions=False)
                return {'RUNNING_MODAL'}

            if current_state == 1:
                self.report({'INFO'}, "Match the face width!")
                self.set_init_scale = False
                lm_obj["state"] = 2
                return {'RUNNING_MODAL'}

            if current_state == 2:
                self.report({'INFO'}, "Fine-tune the landmarks in Edit mode until they match the face.")
                final_mat = lm_obj.matrix_world
                lm_obj.matrix_world = final_mat
                futils.set_active_object(lm_obj.name)
                lm_obj["state"] = 3

                # Make big vertices
                context.tool_settings.mesh_select_mode = (True, False, False)
                bpy.ops.faceit.lock_3d_view_front('INVOKE_DEFAULT', lock_value=True)
                bpy.ops.object.mode_set(mode='EDIT')
                return {'FINISHED'}

        # go into previous state / cancel
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'RELEASE':

            if current_state == 3:
                self.report({'INFO'}, "Match the face width!")
            if current_state == 2:
                self.report({'INFO'}, "Match the face height")
                self.set_init_scale = False
            if current_state > 0:
                lm_obj["state"] -= 1
                self.report({'INFO'}, "Align the Landmarks with your characters chin!")
                return {'RUNNING_MODAL'}
            if current_state == 0:
                bpy.data.objects.remove(lm_obj)
                return {'CANCELLED'}

        context.area.tag_redraw()

        return {'RUNNING_MODAL'}


class FACEIT_OT_MaskMainObject(bpy.types.Operator):
    '''	Mask all geometry that is not assigned to the main face. '''
    bl_idname = 'faceit.mask_main'
    bl_label = 'Mask Main Face'
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):

        main_obj = futils.get_main_faceit_object()
        main_group = main_obj.vertex_groups.get("faceit_main")
        if not main_group:
            self.report({'ERROR'}, "Couldn't find the faceit_main vertex group. Make sure to assign it in the setup tab.")
            return {'CANCELLED'}
        # add the mask modifier
        mod = main_obj.modifiers.get("Main Mask")
        if not mod:
            mod = main_obj.modifiers.new(type='MASK', name="Main Mask")
        mod.vertex_group = main_group.name
        mod.show_viewport = True
        # hide all other faceit objects
        faceit_objects = futils.get_faceit_objects_list()
        for obj in faceit_objects:
            if obj != main_obj:
                obj.hide_set(True)

        return {'FINISHED'}


class FACEIT_OT_MaskGroups(bpy.types.Operator):
    '''	Mask all geometry that is not assigned to the specified group '''
    bl_idname = 'faceit.mask_groups'
    bl_label = 'Mask Main Face'
    bl_options = {'UNDO', 'INTERNAL'}

    vgroup_name: StringProperty(
        name="Vertex Group",
        description="Vertex Group to use for the mask",
        default="",
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        faceit_objects = futils.get_faceit_objects_list()
        mod_name = "Mask " + self.vgroup_name
        for obj in faceit_objects:
            if self.vgroup_name in obj.vertex_groups:
                mod = obj.modifiers.get(mod_name)
                if not mod:
                    mod = obj.modifiers.new(type='MASK', name=mod_name)
                mod.vertex_group = self.vgroup_name
                mod.show_viewport = True
            else:
                # hide all other faceit objects
                obj.hide_set(True)
        return {'FINISHED'}


class FACEIT_OT_UnmaskMainObject(bpy.types.Operator):
    '''	Mask all geometry that is not assigned to the main face. '''
    bl_idname = 'faceit.unmask_main'
    bl_label = 'Remove Mask'
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):

        main_obj = futils.get_main_faceit_object()
        main_group = None
        if main_obj:
            main_group = main_obj.vertex_groups.get("faceit_main")
        if not main_group:
            self.report({'WARNING'}, "Couldn't find the faceit_main vertex group. Make sure to assign it in the setup tab.")
            return {'CANCELLED'}
        # add the mask modifier
        mod = main_obj.modifiers.get("Main Mask")
        if mod:
            main_obj.modifiers.remove(mod)
        # mod.vertex_group = main_group

        # hide all other faceit objects
        faceit_objects = futils.get_faceit_objects_list()
        for obj in faceit_objects:
            if obj != main_obj:
                obj.hide_set(False)

        return {'FINISHED'}


class FACEIT_OT_ResetFacial(bpy.types.Operator):
    '''	Discard Landmarks and start over '''
    bl_idname = 'faceit.reset_facial_landmarks'
    bl_label = 'Reset Landmarks'
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        # if bpy.data.objects.get('facial_landmarks'):
        return True

    def execute(self, context):
        obj = futils.get_object('facial_landmarks')
        # delete face
        if obj is not None:
            bpy.data.objects.remove(obj)

        # Remove locators
        bpy.ops.faceit.edit_locator_empties('EXEC_DEFAULT', hide_value=True)
        # bpy.ops.faceit.edit_locator_empties('EXEC_DEFAULT', remove=True)
        bpy.ops.faceit.unlock_3d_view()
        context.scene.tool_settings.use_snap = False

        return {'FINISHED'}


class FACEIT_OT_ProjectLandmarks(bpy.types.Operator):
    '''Project the Landmarks onto the Main Object. (Make sure you assigned to Main Vertex Group correctly) '''
    bl_idname = 'faceit.project_landmarks'
    bl_label = 'Project Landmarks'
    bl_options = {'REGISTER', 'UNDO'}
    mouse_x: bpy.props.IntProperty()
    mouse_y: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return context.scene.objects.get('facial_landmarks')

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        return self.execute(context)

    def execute(self, context):

        scene = context.scene
        bpy.ops.faceit.unlock_3d_view()
        lm_obj = futils.get_object('facial_landmarks')
        bpy.ops.faceit.mask_main('EXEC_DEFAULT')

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        futils.set_active_object(lm_obj.name)
        # get the main object
        surface_obj = futils.get_main_faceit_object()
        # move in front of face
        if surface_obj:
            lm_obj.location.y = get_max_dim_in_direction(
                obj=surface_obj, direction=Vector((0, -1, 0)))[1] - lm_obj.dimensions[1]
        else:
            self.report({'ERROR'}, 'Please assign the main group to the face mesh (Setup tab)')
            return {'CANCELLED'}

        # get vert positions before and after projecting
        vert_pos_before = [Vector(round(x, 3) for x in v.co) for v in lm_obj.data.vertices]
        # projection modifier
        mod = lm_obj.modifiers.new(name='ShrinkWrap', type='SHRINKWRAP')
        mod.target = surface_obj
        mod.wrap_method = 'PROJECT'
        mod.use_project_y = True
        mod.use_positive_direction = True
        mod.show_on_cage = True
        # apply the modifier
        bpy.ops.object.modifier_apply(modifier=mod.name)

        bpy.ops.view3d.view_selected(use_all_regions=False)
        bpy.ops.view3d.view_axis(type='RIGHT')

        chin_vert = 0 if scene.faceit_asymmetric else 1
        obj_origin = lm_obj.matrix_world @ lm_obj.data.vertices[chin_vert].co
        context.scene.cursor.location = obj_origin
        # bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        scene.tool_settings.use_snap = True
        scene.tool_settings.snap_elements = {'FACE'}
        scene.tool_settings.snap_target = 'CLOSEST'
        scene.tool_settings.use_snap_project = True

        # get vert positions after projecting
        vert_pos_after = [Vector(round(x, 3) for x in v.co) for v in lm_obj.data.vertices]
        success = True
        for i in range(len(vert_pos_before)):
            if vert_pos_after[i] == vert_pos_before[i]:
                success = False
                break
        if not success:
            self.report(
                {'WARNING'},
                "It looks like not all vertices were projected correctly. Align them manually or repeat the projection.")
            # return {'CANCELLED'}
        else:
            self.report({'INFO'}, "Fine-tune the landmarks in Edit mode until they match the face.")

        bpy.ops.ed.undo_push()
        lm_obj["state"] = 4
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.faceit.unmask_main('EXEC_DEFAULT')
        return {'FINISHED'}


class FACEIT_OT_RevertProjection(bpy.types.Operator):
    '''Revert landmark projection and edit in front view'''
    bl_idname = 'faceit.revert_projection'
    bl_label = 'Revert Projection (Edit Front)'
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        lm_obj = futils.get_object("facial_landmarks")
        futils.set_hidden_state_object(lm_obj, False, False)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        futils.clear_object_selection()
        futils.set_active_object(lm_obj.name)
        # bpy.ops.object.mode_set(mode='EDIT')
        for v in lm_obj.data.vertices:
            v.select = True
            v.co.y = 0
        # return {'FINISHED'}
        main_obj = futils.get_main_faceit_object()
        lm_obj.location.y = get_max_dim_in_direction(
            obj=main_obj, direction=Vector((0, -1, 0)))[1] - lm_obj.dimensions[1]
        # bpy.ops.ed.undo_push()
        lm_obj["state"] -= 1
        bpy.ops.faceit.lock_3d_view_front('INVOKE_DEFAULT')
        return {'FINISHED'}


class FACEIT_OT_Lock3DViewFront(bpy.types.Operator):
    '''Lock the 3D view rotation and enable Front view'''
    bl_idname = 'faceit.lock_3d_view_front'
    bl_label = 'Set Front View'
    bl_options = {'UNDO', 'INTERNAL'}

    mouse_x: bpy.props.IntProperty()
    mouse_y: bpy.props.IntProperty()

    lock_value: BoolProperty(
        name='Lock',
        default=False,
        description='Lock the 3D view rotation',
        options={'SKIP_SAVE'}
    )
    set_edit_mode: BoolProperty(
        name="Edit",
        default=True,
        description="useful when the context area is not available (e.g. in handlers)",
        options={'SKIP_SAVE'}
    )

    find_area_by_mouse_position: BoolProperty(
        name="Edit",
        default=False,
        description="useful when the context area is not available (e.g. in handlers)",
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        return self.execute(context)

    def execute(self, context):
        # scene = context.scene
        # TODO: Exit local view
        active_area = context.area
        region_3d = None
        original_context = False
        if active_area:
            original_context = True
            region_3d = active_area.spaces.active.region_3d
        else:
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    if check_if_area_is_active(area, self.mouse_x, self.mouse_y):
                        active_area = area
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                region_3d = space.region_3d
                                break
        lm_obj = futils.get_object('facial_landmarks')
        if self.set_edit_mode:
            context.view_layer.objects.active = lm_obj
            bpy.ops.object.mode_set()
            futils.clear_object_selection()
            lm_obj.select_set(state=True)

        set_front_view(region_3d)
        if original_context:
            if check_is_quad_view(active_area):
                bpy.ops.screen.region_quadview()
        #     bpy.ops.view3d.view_selected(use_all_regions=False)
        if self.set_edit_mode:
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class FACEIT_OT_Unlock3DView(bpy.types.Operator):
    '''Lock the 3D view rotation and enable Front view'''
    bl_idname = 'faceit.unlock_3d_view'
    bl_label = 'Unlock 3D View'
    bl_options = {'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        unlock_3d_view()
        return {'FINISHED'}


class FACEIT_OT_ResetSnapSettings(bpy.types.Operator):
    '''Set the correct Snap to Face Settings automatically.'''
    bl_idname = 'faceit.reset_snap_settings'
    bl_label = 'Reset Snap Settings'
    bl_options = {'UNDO', 'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        draw_text_block(layout, text="Reset to optimal Snap to Face Settings?")

    def execute(self, context):
        scene = context.scene
        scene.tool_settings.use_snap = True
        scene.tool_settings.snap_elements = {'FACE'}
        scene.tool_settings.snap_target = 'CLOSEST'
        scene.tool_settings.use_snap_project = True
        return {'FINISHED'}


class FACEIT_OT_MirrorSelectedVerts(bpy.types.Operator):
    '''Mirror selected Landmarks Vertices - In case MirrorX fails'''
    bl_idname = 'faceit.mirror_selected_verts'
    bl_label = 'Mirror Selected Vertices'
    bl_options = {'UNDO', 'INTERNAL', 'REGISTER'}

    mirror_dir: bpy.props.EnumProperty(
        items=[
            ('L_R', 'Left to Right', 'left to right side mirror (x+ -> x-)'),
            ('R_L', 'Right to Left', 'right to left side mirror (x- -> x+)'),
        ],
        name='Mirror Direction'
    )

    @ classmethod
    def poll(cls, context):
        obj = context.object
        if obj:
            if obj.name == 'facial_landmarks' and context.mode == 'EDIT_MESH':
                return True

    def execute(self, context):

        obj = futils.get_object('facial_landmarks')
        bpy.ops.object.mode_set(mode='OBJECT')
        mirror_dict = lm_data.LANDMARKS_MIRROR_VERTICES_DICT
        m_world = obj.matrix_world
        m_loc = m_world.inverted()

        left_verts_indices = mirror_dict.keys()
        left_verts = [v for v in obj.data.vertices if v.index in left_verts_indices]
        right_verts_indices = mirror_dict.values()
        right_verts = [v for v in obj.data.vertices if v.index in right_verts_indices]
        selected_verts = [v for v in obj.data.vertices if v.select]

        if all(v in left_verts for v in selected_verts):
            self.mirror_dir = 'L_R'
        elif all(v in right_verts for v in selected_verts):
            self.mirror_dir = 'R_L'
        else:
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'WARNING'}, 'Select either Left or Right Side Vertices')
            return {'FINISHED'}

        for left_vert, right_vert in zip(left_verts, right_verts):
            if self.mirror_dir == 'L_R':
                if not left_vert.select:
                    continue
                mirror_co = left_vert.co @ m_world
                mirror_co[0] = mirror_co[0] * -1
                right_vert.co = mirror_co @ m_loc
            else:
                if not right_vert.select:
                    continue
                mirror_co = right_vert.co @ m_world
                mirror_co[0] = mirror_co[0] * -1
                left_vert.co = mirror_co @ m_loc

        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class FACEIT_OT_ResetToLandmarks(bpy.types.Operator):
    '''Go back to editing the landmarks'''
    bl_idname = 'faceit.reset_to_landmarks'
    bl_label = 'Back to Landmarks'
    bl_options = {'UNDO', 'INTERNAL'}

    keep_weights: BoolProperty(
        name='Keep Binding Weights',
        description='Keep all Binding Vertex Groups to Restore with the Rig',
        default=False,
    )

    keep_expressions: BoolProperty(
        name='Keep Expressions',
        description='Keep all generated expressions.',
        default=False,
    )

    keep_corrective_shape_keys: BoolProperty(
        name='Keep Corrective Shape Keys',
        description='Keep all corrective Shape Keys and try to apply them on a new expression.',
        default=True,
    )

    expressions_generated = False
    rig_bound = False
    corr_sk = False

    @ classmethod
    def poll(cls, context):
        rig = futils.get_faceit_armature()

        if rig and context.mode == 'OBJECT' and rig.hide_viewport is False:
            return True

    def invoke(self, context, event):
        if context.scene.faceit_expression_list:
            self.expressions_generated = True
        rig = futils.get_faceit_armature()
        if rig:
            deform_groups = vg_utils.get_deform_bones_from_armature(rig)
            all_registered_objects_vgroups = vg_utils.get_vertex_groups_from_objects()
            if any(grp in deform_groups for grp in all_registered_objects_vgroups):
                self.rig_bound = True

        self.corr_sk = any([sk_name.startswith('faceit_cc_')
                            for sk_name in sk_utils.get_shape_key_names_from_objects()])

        if self.expressions_generated or self.rig_bound:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        else:
            return self.execute(context)

    def draw(self, context):
        layout = self.layout

        row = layout.row()

        if self.expressions_generated:
            row.prop(self, 'keep_expressions')
        if self.rig_bound:
            row.prop(self, 'keep_weights')
        if self.corr_sk:
            row = layout.row()
            row.prop(self, 'keep_corrective_shape_keys')

    def execute(self, context):
        scene = context.scene

        sh_action = bpy.data.actions.get('faceit_shape_action')
        ow_action = bpy.data.actions.get('overwrite_shape_action')
        if self.keep_expressions:
            if sh_action:
                sh_action.use_fake_user = True
            if ow_action:
                ow_action.use_fake_user = True
            context.scene.faceit_expressions_restorable = True

        else:
            if sh_action:
                bpy.data.actions.remove(sh_action)
            if ow_action:
                bpy.data.actions.remove(ow_action)
            context.scene.faceit_expression_list.clear()
            context.scene.faceit_expressions_restorable = False

        if self.corr_sk:
            faceit_objects = futils.get_faceit_objects_list()

            # Keep corrective shape keys

            corrective_sk_action = bpy.data.actions.get('faceit_corrective_shape_keys', None)

            for obj in faceit_objects:

                if sk_utils.has_shape_keys(obj):
                    for sk in obj.data.shape_keys.key_blocks:
                        if sk.name.startswith('faceit_cc_'):
                            # mute corrective shapes!
                            if self.keep_corrective_shape_keys:
                                sk.mute = True
                                scene.faceit_corrective_sk_restorable = True
                            else:
                                obj.shape_key_remove(sk)
                                scene.faceit_corrective_sk_restorable = False

                    if obj.data.shape_keys.animation_data:
                        if obj.data.shape_keys.animation_data.action == corrective_sk_action:
                            obj.data.shape_keys.animation_data.action = None

                    if len(obj.data.shape_keys.key_blocks) == 1:
                        obj.shape_key_clear()

        bpy.ops.faceit.unbind_facial(remove_deform_groups=not self.keep_weights)
        scene.faceit_weights_restorable = self.keep_weights
        # remove rig
        rig = futils.get_faceit_armature()
        bpy.data.objects.remove(rig)

        # turn on landmarks visibility
        lm = bpy.data.objects.get('facial_landmarks')
        # bpy.ops.faceit.edit_locator_empties('EXEC_DEFAULT', hide_value=False)

        if lm:
            futils.set_hidden_state_object(lm, False, False)
        else:
            self.report({'ERROR'}, 'Landmarks mesh does not exist anymore.')
            return {'CANCELLED'}

        bpy.ops.faceit.edit_landmarks('EXEC_DEFAULT')
        bpy.ops.outliner.orphans_purge()
        scene.tool_settings.use_snap = True
        scene.tool_settings.mesh_select_mode = (True, False, False)
        return {'FINISHED'}


class FACEIT_OT_EditLandmarks(bpy.types.Operator):
    '''Edit the landmarks'''
    bl_idname = 'faceit.edit_landmarks'
    bl_label = 'Edit Landmarks'
    bl_options = {'UNDO', 'INTERNAL'}

    @ classmethod
    def poll(cls, context):
        lm_obj = bpy.data.objects.get('facial_landmarks')
        if lm_obj:
            return context.object != lm_obj or context.mode != 'EDIT_MESH'

    def execute(self, context):
        scene = context.scene
        lm = bpy.data.objects.get('facial_landmarks')
        futils.set_hidden_state_object(lm, False, False)

        if context.mode != 'OBJECT':
            # if not context.object:
            #     context.view_layer.objects.active = lm
            bpy.ops.object.mode_set(mode='OBJECT')
        # else:
        futils.clear_object_selection()
        futils.set_active_object(lm.name)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class FACEIT_OT_FinishEditLandmarks(bpy.types.Operator):
    '''Edit the landmarks'''
    bl_idname = 'faceit.finish_edit_landmarks'
    bl_label = 'Edit Landmarks'
    bl_options = {'UNDO', 'INTERNAL'}

    @ classmethod
    def poll(cls, context):
        if context.object:
            return context.object.name == 'facial_landmarks' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        scene = context.scene

        lm = bpy.data.objects.get('facial_landmarks')
        # rig = futils.get_faceit_armature(force_original=True)
        # if rig:
        # bpy.ops.faceit.edit_locator_empties('EXEC_DEFAULT', hide_value=True)

        # turn off landmarks visibility
        # if lm:
        #     futils.set_hidden_state_object(lm, True, False)

        bpy.ops.faceit.unmask_main('EXEC_DEFAULT')
        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
