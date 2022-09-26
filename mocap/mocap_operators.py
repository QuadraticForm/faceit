from email.policy import default
from bpy_extras.io_utils import ImportHelper
from ..ctrl_rig.control_rig_animation_operators import CRIG_ACTION_SUFFIX
from ..ctrl_rig import control_rig_utils as ctrl_utils
from ..core.shape_key_utils import get_all_shape_key_actions, get_enum_shape_key_actions, has_shape_keys, get_shape_key_names_from_objects, set_rest_position_shape_keys
from ..core import retarget_list_utils as rutils
from ..core import fc_dr_utils
from ..core import faceit_utils as futils
from ..core import faceit_data as fdata
from ..core.retarget_list_base import FaceRegionsBaseProperties
import csv
import json
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty, FloatProperty

from .mocap_utils import convert_timecode_to_frames, add_zero_keyframe, remove_frame_range


class MocapLoadFromText():
    '''This class bundles utility functions to read Text or CSV mocap data and populate it to the respective action fcurves.'''

    shape_key_animation_values = []
    head_rotation_animation_values = []
    eye_L_rotation_animation_values = []
    eye_R_rotation_animation_values = []
    frames = []
    frame_count = 0

    def __init__(
            self, filename, mocap_engine, frame_start, laod_sk, load_head_rot, load_eye_rot, a2f_frame_rate):
        self.filename = filename
        self.mocap_engine = mocap_engine
        self.frame_start = frame_start
        self.read_shapekeys = laod_sk
        self.read_head_rotation = load_head_rot
        self.read_eye_rotation = load_eye_rot
        self.a2f_frame_rate = a2f_frame_rate
        self.read_mocap()

    def get_scene_frame_rate(self):
        '''Returns the current framerate'''
        return bpy.context.scene.render.fps

    def read_mocap(self):
        '''returns all animation values set by user in individual lists'''
        frames = []
        shape_key_animation_values = []
        head_rotation = []
        eye_L = []
        eye_R = []
        framerate = self.get_scene_frame_rate()

        if self.mocap_engine == 'EPIC':
            # first_frame = self.frame_start
            with open(self.filename) as csvfile:
                reader = csv.reader(csvfile)
                for i, row in enumerate(reader):
                    if not row:
                        continue
                    if i == 0:
                        continue
                    if i == 1:
                        first_frame = convert_timecode_to_frames(row[0], framerate) - self.frame_start
                    frames.append(convert_timecode_to_frames(row[0], framerate) - first_frame)

                    # Head Motion
                    if self.read_head_rotation:
                        head_rotation.append([float(v) for v in row[54:57]])
                    # Eyes Motion
                    if self.read_eye_rotation:
                        eye_L.append([float(v) for v in row[58:60]])
                        eye_R.append([float(v) for v in row[60:62]])
                    # Blendshapes Motion
                    if self.read_shapekeys:
                        shape_key_animation_values.append([float(v) for v in row[2:54]])

        elif self.mocap_engine == 'FACECAP':
            with open(self.filename) as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if not row:
                        continue
                    if row[0] != 'k':
                        continue
                    # Nano seconds since last frame
                    current_frame = self.frame_start + (float(row[1]) / 1000.0) * framerate
                    frames.append(current_frame)
                    # Head Motion
                    if self.read_head_rotation:
                        head_rotation.append(np.radians([float(v) for v in row[5:8]]))
                    # Eyes Motion
                    if self.read_eye_rotation:
                        eye_L.append(np.radians([float(v) for v in row[8:10]]))
                        eye_R.append(np.radians([float(v) for v in row[10:12]]))
                    # Blendshapes Motion
                    if self.read_shapekeys:
                        shape_key_animation_values.append([float(v) for v in row[12:]])

        elif self.mocap_engine == 'A2F':
            with open(self.filename, 'r') as f:
                data = json.load(f)
                for i, shape_key_values in enumerate(data['weightMat']):
                    # time += i * time_per_frame
                    current_frame = self.frame_start + i * framerate / self.a2f_frame_rate
                    frames.append(current_frame)
                    # Blendshapes Motion
                    shape_key_animation_values.append([float(v) for v in shape_key_values])

        self.frames = frames
        self.frame_count = len(frames)
        self.shape_key_animation_values = shape_key_animation_values
        self.head_rotation_animation_values = head_rotation
        self.eye_L_rotation_animation_values = eye_L
        self.eye_R_rotation_animation_values = eye_R

    def get_values_for_animation(self, animation_values, index):
        '''Returns list with the respective captured values per frame'''
        values = []
        if animation_values:
            for j in range(self.frame_count):
                if len(animation_values[j]) > 1:
                    try:
                        values.append(animation_values[j][index])
                    except IndexError:
                        pass
                        # print(f'length: {len(animation_values[j])}')
                        # print(f'index: {index}')
                else:
                    values.append(0)
        return values

    def populate_shape_key_motion_data_to_fcurve(self, fc, sk_index=0, scale_value=1.0):  # sk_name, sk_index):
        '''populate the shape key motion data into fcurves
        @fc [fcurve]: the animation fcurve that gets populated
        @sk_index [int]: the index of the expression in the recorded file
        '''

        values = self.get_values_for_animation(self.shape_key_animation_values, sk_index)

        mocap_keyframe_points = fc_dr_utils.frame_value_pairs_to_numpy_array(self.frames, values)
        if scale_value != 1:
            mocap_keyframe_points[:, 1] *= scale_value

        fc_dr_utils.populate_keyframe_points_from_np_array(
            fc,
            mocap_keyframe_points,
            add=True,
            join_with_existing=True
        )

    def populate_object_transform_motion_data_to_fcurve(
            self, action, dp, motion_type, channels_count, reroute_channels_matrix, scale_channels_vector=None):
        '''Populate the motion data into fcurves for each channel of a transform object.
        @part [string]: the part to animate - either eye L, R or head loc, rot
        @action [action id]: the action that should hold or holds the fcurves
        @dp [string]: the data_path of the fcurve (e.g. rotation_euler)
        @channels_count [int]: the number of channels that should be retargeted (e.g. 2 for x/y rotation)
        @reroute_channels_matrix [dict]: A ditionary that maps indices (e.g. to change rotation order)
        @scale_channels_vector [list]: A vector that holds multipliers for each channel (e.g. to negate a value)
        '''
        animation_values = None
        if motion_type == 'head_rot':
            animation_values = self.head_rotation_animation_values
        if motion_type == 'eye_L':
            animation_values = self.eye_L_rotation_animation_values
        if motion_type == 'eye_R':
            animation_values = self.eye_R_rotation_animation_values

        if animation_values:

            for i in range(channels_count):

                values = self.get_values_for_animation(animation_values, index=i)

                if scale_channels_vector:
                    # Scale compensation for unit differences
                    values = np.array(values) * scale_channels_vector[i]

                # indices for XYZ location - reroute to match other coordinate systems
                array_index = reroute_channels_matrix.get(i, i)
                fc = fc_dr_utils.get_fcurve_from_bpy_struct(action.fcurves, dp=dp, array_index=array_index)

                mocap_keyframe_points = fc_dr_utils.frame_value_pairs_to_numpy_array(self.frames, values)

                fc_dr_utils.populate_keyframe_points_from_np_array(
                    fc,
                    mocap_keyframe_points,
                    add=True,
                    join_with_existing=True  # (not self.overwrite_action)
                )


class FACEIT_OT_AddZeroKeyframe(FaceRegionsBaseProperties, bpy.types.Operator):
    '''Add a 0.0 keyframe for all target shapes in the specified list(s)'''
    bl_idname = 'faceit.add_zero_keyframe'
    bl_label = 'Add Zero Keyframe'
    bl_options = {'UNDO'}

    expression_sets: EnumProperty(
        name='Expression Sets',
        items=(
            ('ALL', 'All', 'Search for all available expressions'),
            ('ARKIT', 'ARKit', 'The 52 ARKit Expressions that are used in all iOS motion capture apps'),
            ('A2F', 'Audio2Face', 'The 46 expressions that are used in Nvidias Audio2Face app by default.'),
        ),
        default='ALL'
    )

    use_region_filter: BoolProperty(
        name='Filter Face Regions',
        default=True,
        description='Filter face regions that should be animated.'
        # options={'SKIP_SAVE', }
    )

    existing_action: EnumProperty(
        name='Action',
        items=get_enum_shape_key_actions,
        options={'SKIP_SAVE', }
    )

    data_paths: EnumProperty(
        name='Fcurves',
        items=(
            ('EXISTING', 'Existing', 'Add a zero keyframe to all fcurves that are currently found in the specified action'),
            ('ALL', 'All', 'Add a Keyframe for all target shapes in the specified list(s). Create a new fcurve if it doesn\'t exist')
        ),
        default='EXISTING',
        options={'SKIP_SAVE', }
    )

    frame: IntProperty(
        name='Frame',
        default=0,
        options={'SKIP_SAVE', }
    )

    def invoke(self, context, event):

        # Check if the main object has a Shape Key Action applied
        main_obj = futils.get_main_faceit_object()
        sk_action = None
        if has_shape_keys(main_obj):
            if main_obj.data.shape_keys.animation_data:
                sk_action = main_obj.data.shape_keys.animation_data.action

        if sk_action:
            self.existing_action = sk_action.name

        self.frame = context.scene.frame_current

        # face_regions_prop = context.scene.faceit_face_regions
        # props = [x for x in face_regions_prop.keys()]
        # for p in props:
        #     face_regions_prop.property_unset(p)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text='Affect Expressions')
        row = layout.row()
        row.prop(self, 'expression_sets', expand=True)

        row = layout.row()
        row.label(text='Choose a Shape Key Action:')
        row = layout.row()
        row.prop(self, 'existing_action', text='', icon='ACTION')

        row = layout.row()
        row.prop(self, 'frame', icon='KEYTYPE_KEYFRAME_VEC')

        row = layout.row(align=True)
        row.label(text='Region Filter')
        row = layout.row(align=True)
        row.prop(self, 'use_region_filter', icon='USER')

        if self.use_region_filter:

            col = layout.column(align=True)

            row = col.row(align=True)

            icon_value = 'CHECKBOX_HLT' if self.brows else 'CHECKBOX_DEHLT'
            row.prop(self, 'brows', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.eyes else 'CHECKBOX_DEHLT'
            row.prop(self, 'eyes', icon=icon_value)

            row = col.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.cheeks else 'CHECKBOX_DEHLT'
            row.prop(self, 'cheeks', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.nose else 'CHECKBOX_DEHLT'
            row.prop(self, 'nose', icon=icon_value)

            row = col.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.mouth else 'CHECKBOX_DEHLT'
            row.prop(self, 'mouth', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.tongue else 'CHECKBOX_DEHLT'
            row.prop(self, 'tongue', icon=icon_value)

    @classmethod
    def poll(cls, context):
        return get_all_shape_key_actions() and futils.get_faceit_objects_list()

    def execute(self, context):

        scene = context.scene

        shape_names = []
        if self.expression_sets in ('ALL', 'ARKIT'):
            retarget_list = scene.faceit_arkit_retarget_shapes
            for region, active in self.get_active_regions().items():
                if active:
                    shape_names.extend(rutils.get_all_set_target_shapes(retarget_list=retarget_list, region=region))
        if self.expression_sets in ('ALL', 'A2F'):
            retarget_list = scene.faceit_a2f_retarget_shapes
            for region, active in self.get_active_regions().items():
                if active:
                    shape_names.extend(rutils.get_all_set_target_shapes(retarget_list=retarget_list, region=region))

        action = bpy.data.actions.get(self.existing_action)
        if not action:
            self.report({'WARNING'}, f'Couldn\'t find the action {self.existing_action}')
            return{'CANCELLED'}
        fcurves_to_operate_on = [fc for fc in action.fcurves if any(
            shape_name in fc.data_path for shape_name in shape_names)]
        add_zero_keyframe(fcurves=fcurves_to_operate_on, frame=self.frame)
        scene.frame_set(scene.frame_current)

        return{'FINISHED'}


def update_frame_start(self, context):
    if self.frame_start >= self.frame_end:
        self.frame_start = self.frame_end - 1


def update_frame_end(self, context):
    if self.frame_end <= self.frame_start:
        self.frame_end = self.frame_start + 1


class FACEIT_OT_RemoveFrameRange(FaceRegionsBaseProperties, bpy.types.Operator):
    '''Remove a range of frames from the specified Shape Key action'''
    bl_idname = 'faceit.remove_frame_range'
    bl_label = 'Remove Keyframes Filter'
    bl_options = {'UNDO'}

    expression_sets: EnumProperty(
        name='Expression Sets',
        items=(
            ('ALL', 'All', 'Search for all available expressions'),
            ('ARKIT', 'ARKit', 'The 52 ARKit Expressions that are used in all iOS motion capture apps'),
            ('A2F', 'Audio2Face', 'The 46 expressions that are used in Nvidias Audio2Face app by default.'),
        ),
        default='ALL'
    )

    use_region_filter: BoolProperty(
        name='Filter Face Regions',
        default=True,
        description='Filter face regions that should be animated.'
        # options={'SKIP_SAVE', }
    )

    existing_action: EnumProperty(
        name='Action',
        items=get_enum_shape_key_actions,
        options={'SKIP_SAVE', }
    )

    frame_range: EnumProperty(
        name='Effect Frames',
        items=(
            ('CUSTOM', 'Custom', 'Specify a frame range that should be affected'),
            ('ALL', 'All', 'Affect all keys in the specified action'),
        )
    )

    frame_start: IntProperty(
        name='Frame Start',
        default=0,
        soft_min=0,
        soft_max=50000,
        update=update_frame_start
        # options={'SKIP_SAVE', }
    )
    frame_end: IntProperty(
        name='Frame End',
        default=10,
        soft_min=0,
        soft_max=50000,
        update=update_frame_end
        # options={'SKIP_SAVE', }
    )

    def invoke(self, context, event):

        # Check if the main object has a Shape Key Action applied
        main_obj = futils.get_main_faceit_object()
        sk_action = None
        if has_shape_keys(main_obj):
            if main_obj.data.shape_keys.animation_data:
                sk_action = main_obj.data.shape_keys.animation_data.action

        if sk_action:
            self.existing_action = sk_action.name

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text='Affect Expressions')
        row = layout.row()
        row.prop(self, 'expression_sets', expand=True)

        row = layout.row()
        row.label(text='Choose a Shape Key Action:')
        row = layout.row()
        row.prop(self, 'existing_action', text='', icon='ACTION')

        row = layout.row()
        row.label(text='Frame Range:')
        row = layout.row()
        row.prop(self, 'frame_range', expand=True)

        if self.frame_range == 'CUSTOM':
            row = layout.row(align=True)
            row.prop(self, 'frame_start', icon='KEYTYPE_KEYFRAME_VEC')
            row.prop(self, 'frame_end', icon='KEYTYPE_KEYFRAME_VEC')

        row = layout.row(align=True)
        row.label(text='Region Filter')
        row = layout.row(align=True)
        row.prop(self, 'use_region_filter', icon='USER')

        if self.use_region_filter:

            col = layout.column(align=True)

            row = col.row(align=True)

            icon_value = 'CHECKBOX_HLT' if self.brows else 'CHECKBOX_DEHLT'
            row.prop(self, 'brows', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.eyes else 'CHECKBOX_DEHLT'
            row.prop(self, 'eyes', icon=icon_value)

            row = col.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.cheeks else 'CHECKBOX_DEHLT'
            row.prop(self, 'cheeks', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.nose else 'CHECKBOX_DEHLT'
            row.prop(self, 'nose', icon=icon_value)

            row = col.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.mouth else 'CHECKBOX_DEHLT'
            row.prop(self, 'mouth', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.tongue else 'CHECKBOX_DEHLT'
            row.prop(self, 'tongue', icon=icon_value)

    @classmethod
    def poll(cls, context):
        return get_all_shape_key_actions() and futils.get_faceit_objects_list()

    def execute(self, context):

        scene = context.scene

        shape_names = []
        if self.expression_sets in ('ALL', 'ARKIT'):
            retarget_list = scene.faceit_arkit_retarget_shapes
            for region, active in self.get_active_regions().items():
                if active:
                    shape_names.extend(rutils.get_all_set_target_shapes(retarget_list=retarget_list, region=region))
        if self.expression_sets in ('ALL', 'A2F'):
            retarget_list = scene.faceit_a2f_retarget_shapes
            for region, active in self.get_active_regions().items():
                if active:
                    shape_names.extend(rutils.get_all_set_target_shapes(retarget_list=retarget_list, region=region))

        action = bpy.data.actions.get(self.existing_action)
        if not action:
            self.report({'WARNING'}, f'Couldn\'t find the action {self.existing_action}')
            return{'CANCELLED'}
        fcurves_to_operate_on = [fc for fc in action.fcurves if any(
            shape_name in fc.data_path for shape_name in shape_names)]
        if self.frame_range == 'CUSTOM':
            remove_frame_range(action=action, fcurves=fcurves_to_operate_on,
                               frame_start=self.frame_start, frame_end=self.frame_end)
        else:
            # Just remove the entire fcurves
            for fc in fcurves_to_operate_on:
                action.fcurves.remove(fc)

        set_rest_position_shape_keys()

        scene.frame_set(scene.frame_current)

        return{'FINISHED'}


def update_load_action_type(self, context):
    if self.load_action_type == 'ACTIVE':
        if self.overwrite_action == 'OVERWRITE':
            self.overwrite_action = 'MIX'


def update_new_action_name(self, context):
    self.new_action_exists = bool(bpy.data.actions.get(self.new_action_name))


class FACEIT_OT_ImportMocap(FaceRegionsBaseProperties, bpy.types.Operator):
    '''Import raw mocap data from text or csv files'''
    bl_idname = 'faceit.import_mocap'
    bl_label = 'Import'
    bl_options = {'UNDO', 'INTERNAL'}

    engine: bpy.props.EnumProperty(
        name='mocap engine',
        items=(
            ('FACECAP', 'Face Cap', 'Face Cap TXT'),
            ('EPIC', 'Live Link Face', 'Live Link Face CSV'),
            ('A2F', 'Audio2Face', 'Nvidia Audio2Face'),
        ),
        options={'SKIP_SAVE', }
    )
    load_action_type: EnumProperty(
        name='New or Active Action',
        items=(
            ('NEW', 'New Action', 'Create a new Action and load the mocap data.'),
            ('ACTIVE', 'Active Action', 'Load the mocap data into an existing Action.'),
        ),
        update=update_load_action_type,
        options={'SKIP_SAVE', }
    )
    new_action_name: StringProperty(
        name='New Action Name',
        update=update_new_action_name,
        options={'SKIP_SAVE', }
    )
    new_action_exists: BoolProperty(
        name='Action Exists',
        default=False,
        options={'SKIP_SAVE', }
    )
    existing_action: EnumProperty(
        name='Action',
        items=get_enum_shape_key_actions,
        options={'SKIP_SAVE', }
    )
    overwrite_action: EnumProperty(
        name='Overwrite Action',
        items=(
            ('OVERWRITE', 'Overwrite', 'Overwrite the entire Action. All existing keyframes will be removed.'),
            ('MIX', 'Mix', 'Mix in the new Action. The existing keyframes will be preserved.'),
            ('APPEND', 'Append', 'Append the new keyframes to the end. All existing keyframes will be preserved.'),
        ),
        options={'SKIP_SAVE', }
    )
    bake_to_control_rig: BoolProperty(
        name='Bake to Control Rig',
        default=False,
        description='Loads the mocap action directly on the control rig. Creates a temp Action with the 52 Shape Keys.',
        options={'SKIP_SAVE', }
    )

    frame_start: IntProperty(
        name='Start Frame',
        description='Start frame for the new keyframes. If append method is selected, the specified frame will present an offset to existing keyframes in the given action.',
        default=0,
        soft_min=0,
        soft_max=50000,
        # options={'SKIP_SAVE', }
    )
    use_region_filter: BoolProperty(
        name='Filter Face Regions',
        default=True,
        description='Filter face regions that should be animated.'
        # options={'SKIP_SAVE', }
    )
    set_scene_frame_range: BoolProperty(
        name='Set Scene Frame Range',
        description='Sets the scene frame range to the range of the new action',
        default=True,
    )
    a2f_frame_rate: FloatProperty(
        name='Export Frame Rate',
        default=60,
        description='Only change this if you changed the default framerate for audio2face exports',
        options={'SKIP_SAVE', }
    )
    audio_file_name: StringProperty(
        name='Strip Name',
        default='',
        description='The name of the audio strip in sequencer',
        options={'SKIP_SAVE', }
    )
    load_audio_file: BoolProperty(
        name='Load Audio',
        default=False,
        options={'SKIP_SAVE', }
    )
    remove_audio_tracks_with_same_name: BoolProperty(
        name='Remove Identical Soundstrips',
        default=True,
        # options={'SKIP_SAVE', }
    )

    can_load_audio = False

    @classmethod
    def poll(cls, context):
        return context.scene.faceit_face_objects

    def invoke(self, context, event):

        # Check if the main object has a Shape Key Action applied
        main_obj = futils.get_main_faceit_object()
        sk_action = None
        if has_shape_keys(main_obj):
            if main_obj.data.shape_keys.animation_data:
                sk_action = main_obj.data.shape_keys.animation_data.action

        if sk_action:
            self.existing_action = sk_action.name

        engine_settings = fdata.get_engine_settings(self.engine)
        self.new_action_name = self.get_clean_filename(engine_settings.filename)
        if not self.check_file_path(engine_settings.filename):
            self.report({'ERROR'}, 'Mocap File not set or invalid')
            return {'CANCELLED'}

        audio_file = engine_settings.audio_filename
        if audio_file:
            self.audio_file_name = self.get_clean_filename(audio_file)
            self.can_load_audio = True
            self.load_audio_file = True

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        if self.engine != 'A2F' and futils.get_faceit_control_armature():
            row.prop(self, 'bake_to_control_rig', icon='CON_ARMATURE')

        if self.bake_to_control_rig is not True:
            row = layout.row()
            row.prop(self, 'load_action_type', icon='ACTION', expand=True)
            row = layout.row()
            frame_start_txt = 'Frame Start'
            if self.load_action_type == 'NEW':
                row.label(text='New Action Name:')
                row = layout.row()
                row.prop(self, 'new_action_name', text='', icon='ACTION')
            else:
                row = layout.row()
                row.label(text='Choose a Shape Key Action:')
                row = layout.row()
                row.prop(self, 'existing_action', text='', icon='ACTION')

            if self.new_action_exists or self.load_action_type == 'ACTIVE':
                if self.new_action_exists:
                    row = layout.row(align=True)
                    row.label(text='This Action already exists.')
                row = layout.row(align=True)
                row.label(text='Choose Mix Method')
                row = layout.row()
                row.prop(self, 'overwrite_action', expand=True)

                if self.overwrite_action == 'APPEND':
                    frame_start_txt = 'Frame Offset'

            row = layout.row()
            row.prop(self, 'frame_start', text=frame_start_txt, icon='CON_TRANSFORM')

        if self.engine == 'A2F':
            row = layout.row()
            row.label(text='Audio2Face Frame Rate')
            row = layout.row()
            row.prop(self, 'a2f_frame_rate')

        row = layout.row(align=True)
        row.label(text='Region Filter')
        row = layout.row(align=True)
        row.prop(self, 'use_region_filter', icon='USER')

        if self.use_region_filter:

            col = layout.column(align=True)

            row = col.row(align=True)

            icon_value = 'CHECKBOX_HLT' if self.brows else 'CHECKBOX_DEHLT'
            row.prop(self, 'brows', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.eyes else 'CHECKBOX_DEHLT'
            row.prop(self, 'eyes', icon=icon_value)

            row = col.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.cheeks else 'CHECKBOX_DEHLT'
            row.prop(self, 'cheeks', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.nose else 'CHECKBOX_DEHLT'
            row.prop(self, 'nose', icon=icon_value)

            row = col.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.mouth else 'CHECKBOX_DEHLT'
            row.prop(self, 'mouth', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.tongue else 'CHECKBOX_DEHLT'
            row.prop(self, 'tongue', icon=icon_value)

        if self.can_load_audio:
            row = layout.row()
            row.label(text='Audio (Sequencer)')
            row = layout.row()
            row.prop(self, 'load_audio_file', icon='SEQUENCE')
            if self.load_audio_file:
                row = layout.row()
                row.prop(self, 'audio_file_name', icon='SEQUENCE')
                row = layout.row()
                row.prop(self, 'remove_audio_tracks_with_same_name', icon='TRASH')
            layout.separator()

    def check_file_path(self, filename):
        '''Returns True when filename is valid'''
        if not filename or not os.path.exists(filename) or not os.path.isfile(filename):
            return False
        return True

    def get_clean_filename(self, filename):
        '''Returns the string filename - strips directories and file extension'''
        return (filename.split('\\')[-1]).split('.')[0]  # .strip('.{}'.format(file_extension))

    def get_action(self, action_name):
        '''
        Get an action by name, create it if it does not exist
        '''
        action = bpy.data.actions.get(action_name)
        if not action:
            self.report({'INFO'}, 'Creating new Action with name {}'.format(action_name))
            action = bpy.data.actions.new(name=action_name)
        return action

    def execute(self, context):

        scene = context.scene
        new_frame_range = scene.frame_start, scene.frame_end
        start_frame_mocap = self.frame_start

        engine_settings = fdata.get_engine_settings(self.engine)

        filename = engine_settings.filename
        if self.load_audio_file:
            audio_file = engine_settings.audio_filename
            if audio_file:
                if not self.check_file_path(audio_file):
                    self.report({'WARNING'}, 'Audio File not set or invalid')

        if self.bake_to_control_rig:
            c_rig = futils.get_faceit_control_armature()
            if not c_rig:
                self.report(
                    {'ERROR'},
                    'Can\'t find the active control rig. Please create/choose control rig first or import directly to the meshes.')
                return{'CANCELLED'}

            a_remove = bpy.data.actions.get('mocap_import')
            if a_remove:
                bpy.data.actions.remove(a_remove)
            mocap_action = bpy.data.actions.new('mocap_import')
        else:
            if self.load_action_type == 'NEW':
                if self.new_action_name in bpy.data.actions:
                    mocap_action = bpy.data.actions[self.new_action_name]

                else:
                    bpy.ops.faceit.new_action('EXEC_DEFAULT', action_name=self.new_action_name,
                                              populate_animation_data=True)
                    mocap_action = scene.faceit_mocap_action
            else:
                mocap_action = bpy.data.actions.get(self.existing_action)

            if not mocap_action:
                self.report({'WARNING'}, 'The action couldn\'t be loaded.')
                return({'CANCELLED'})

            action_name = mocap_action.name

            if self.overwrite_action == 'OVERWRITE':
                # Remove the target action and recreate
                bpy.data.actions.remove(mocap_action, do_unlink=True)
                mocap_action = bpy.data.actions.new(action_name)

            elif self.overwrite_action == 'APPEND':
                # Add offset to framestart
                kf_end = int(futils.get_action_frame_range(mocap_action)[1])
                start_frame_mocap = start_frame_mocap + kf_end
            else:
                pass

            bpy.ops.faceit.populate_action(action_name=action_name)

        laod_sk, load_head_rot, load_eye_rot = \
            scene.faceit_mocap_motion_types.read_settings()
        if not (laod_sk or load_head_rot or load_eye_rot):
            self.report({'ERROR'}, 'You have to choose wich type of motion you want to import')
            return {'CANCELLED'}

        mocap_loaded = MocapLoadFromText(filename, self.engine, start_frame_mocap,
                                         laod_sk, load_head_rot, load_eye_rot, self.a2f_frame_rate)

        # Load Audio
        if self.load_audio_file:
            channel = 1
            create_new = True
            if not scene.sequence_editor:
                scene.sequence_editor_create()
            else:
                soundstrip = scene.sequence_editor.sequences.get(self.audio_file_name)
                if soundstrip:
                    if soundstrip.frame_start == start_frame_mocap:
                        self.report(
                            {'INFO'},
                            f'The audio file {self.audio_file_name} is already loaded on frame {start_frame_mocap}')
                        create_new = False
                    else:
                        if self.remove_audio_tracks_with_same_name:
                            # print('removing soundstrip')
                            scene.sequence_editor.sequences.remove(soundstrip)

            if create_new:
                # Find the first free channel if the sequencer isn't empty
                occupied_channels = set((x.channel for x in scene.sequence_editor.sequences))
                if occupied_channels:
                    possible_channels = set(range(1, max(occupied_channels) + 2))
                    channel = min(possible_channels - occupied_channels)
                soundstrip = scene.sequence_editor.sequences.new_sound(
                    self.audio_file_name, audio_file, channel, start_frame_mocap)

            if soundstrip is not None:
                soundstrip.faceit_audio = True

        if laod_sk:

            if self.bake_to_control_rig:
                target_objects = ctrl_utils.get_crig_objects_list(c_rig)
                retarget_list = c_rig.faceit_crig_targets
            else:
                if self.engine == 'A2F':
                    retarget_list = scene.faceit_a2f_retarget_shapes
                else:
                    retarget_list = scene.faceit_arkit_retarget_shapes
                target_objects = futils.get_faceit_objects_list()

            if not target_objects:
                self.report(
                    {'WARNING'},
                    'No registered objects found. {}'.format(
                        'Please update the control rig'
                        if self.bake_to_control_rig else 'Please register objects in Setup panel'))
                return{'CANCELLED'}

            if not retarget_list or not rutils.get_all_set_target_shapes(retarget_list):
                self.report(
                    {'WARNING'},
                    'Target Shapes are not properly configured. {}'.format(
                        'Please update the control rig'
                        if self.bake_to_control_rig else 'Set up {} target shapes in Shapes panel.'.format(
                            'Audio2Face' if self.engine == 'A2F' else 'ARKit')))
                return{'CANCELLED'}

            if not get_shape_key_names_from_objects(objects=target_objects):
                self.report(
                    {'WARNING'},
                    'The registered objects hold no Shape Keys. Please create Shape Keys before loading mocap data.')
                return{'CANCELLED'}

            shape_reference_data = fdata.get_shape_data_for_mocap_engine(mocap_engine=self.engine)

            regions_filter = self.get_active_regions()

            for shape_item in retarget_list:

                if getattr(shape_item, 'use_animation', True) is False:
                    # print(f'Skipping Shape {shape_item.name}, because it is disabled in the shapes list.')
                    continue

                if hasattr(shape_item, 'region'):
                    region = shape_item.region.lower()
                    if regions_filter[region] is False:
                        # print(f'skipping shape {shape_item.name} because of region filter')
                        continue

                shape_data = shape_reference_data.get(shape_item.name)
                if not shape_data:
                    # This is a custom slider
                    continue

                shape_index = shape_data['index']

                for target_shape in shape_item.target_shapes:

                    dp = f'key_blocks["{target_shape.name}"].value'
                    fc = mocap_action.fcurves.find(dp)
                    if not fc:
                        fc = mocap_action.fcurves.new(dp)

                    mocap_loaded.populate_shape_key_motion_data_to_fcurve(
                        fc, sk_index=shape_index)

            if self.bake_to_control_rig:
                if mocap_action.fcurves:
                    bpy.ops.faceit.bake_shape_keys_to_control_rig(
                        'INVOKE_DEFAULT',
                        action_source=mocap_action.name,
                        action_target='NEW',
                        new_action_name=self.new_action_name + CRIG_ACTION_SUFFIX,
                        compensate_amplify_values=True,
                        remove_sk_action=True,
                    )
                else:
                    self.report({'WARNING'}, 'No target shapes found. Please update control rig first!')
                    bpy.data.actions.remove(mocap_action)
                    return{'CANCELLED'}
            frame_range = futils.get_action_frame_range(mocap_action)
            if (frame_range[1] - frame_range[0]) > 1:
                new_frame_range = frame_range

        # Create new Actions for rotation/location targets with suffixes
        action_prefix = mocap_action.name

        if (load_head_rot):
            # the rotation/location objects set by user
            head_empty = futils.get_object(scene.faceit_mocap_target_head)

            if head_empty:
                # Populate the head motion action with mocap values
                head_action = self.get_action(action_prefix + '_head')

                if not head_empty.animation_data:
                    head_empty.animation_data_create()

                head_empty.animation_data.action = head_action

                # Yaw Pitch Roll
                reroute_UE = {
                    0: 2,
                    1: 0,
                    2: 1,
                }

                reroute_FC = {
                    0: 0,
                    1: 2,
                    2: 1,
                }

                scale_rotation_vec_UE = [
                    1,
                    -1,
                    1,
                ]

                if self.engine == 'FACECAP':
                    reroute_matrix = reroute_FC
                    scale_rotation_vec = None
                else:
                    reroute_matrix = reroute_UE
                    scale_rotation_vec = scale_rotation_vec_UE

                # Head Rotation
                if load_head_rot:

                    mocap_loaded.populate_object_transform_motion_data_to_fcurve(
                        head_action,
                        dp='rotation_euler',
                        motion_type='head_rot',
                        channels_count=3,
                        reroute_channels_matrix=reroute_matrix,
                        scale_channels_vector=scale_rotation_vec

                    )

                new_frame_range = futils.get_action_frame_range(head_action)
            else:
                self.report({'WARNING'}, 'You did not specify a target for head motion')

        if load_eye_rot:

            eye_L_empty = futils.get_object(scene.faceit_mocap_target_eye_l)
            eye_R_empty = futils.get_object(scene.faceit_mocap_target_eye_r)

            reroute_YZ = {
                0: 0,
                1: 2,
            }

            if eye_L_empty:

                eye_L_action = self.get_action(action_prefix + '_eye_L')

                if not eye_L_empty.animation_data:
                    eye_L_empty.animation_data_create()

                eye_L_empty.animation_data.action = eye_L_action

                mocap_loaded.populate_object_transform_motion_data_to_fcurve(
                    eye_L_action,
                    dp='rotation_euler',
                    motion_type='eye_L',
                    channels_count=2,
                    reroute_channels_matrix=reroute_YZ,
                )
                new_frame_range = futils.get_action_frame_range(eye_L_action)

            else:
                self.report({'WARNING'}, 'You did not specify a target for Left Eye motion')

            if eye_R_empty:

                eye_R_action = self.get_action(action_prefix + '_eye_R')

                if not eye_R_empty.animation_data:
                    eye_R_empty.animation_data_create()

                eye_R_empty.animation_data.action = eye_R_action

                mocap_loaded.populate_object_transform_motion_data_to_fcurve(
                    eye_R_action,
                    dp='rotation_euler',
                    motion_type='eye_R',
                    channels_count=2,
                    reroute_channels_matrix=reroute_YZ,
                )

                new_frame_range = futils.get_action_frame_range(eye_R_action)

            else:
                self.report({'WARNING'}, 'You did not specify a target for Left Eye motion')

        if self.set_scene_frame_range:
            scene.frame_start, scene.frame_end = (int(x) for x in new_frame_range)

        return{'FINISHED'}


class FACEIT_OT_LoadMotionFile(bpy.types.Operator):
    '''Choose a catured file to import as keyframes'''
    bl_idname = 'faceit.load_motion_file'
    bl_label = 'Load mocap'
    bl_options = {'UNDO', 'INTERNAL'}

    engine: bpy.props.EnumProperty(
        name='mocap engine',
        items=(
            ('FACECAP', 'Face Cap', 'Face Cap TXT'),
            ('EPIC', 'Live Link Face', 'Live Link Face CSV'),
            ('A2F', 'Audio2Face', 'Nvidia Audio2Face'),
        ),
        options={'HIDDEN', },
    )

    filter_glob: bpy.props.StringProperty(
        default='*.txt',
        options={'HIDDEN'}
    )

    filepath: bpy.props.StringProperty(
        name='File Path',
        description='Filepath used for importing txt files',
        maxlen=1024,
        default='',
    )

    files: bpy.props.CollectionProperty(
        name='File Path',
        type=bpy.types.OperatorFileListElement,
    )

    def execute(self, context):

        fdata.get_engine_settings(self.engine).filename = self.filepath

        # Update UI
        for region in context.area.regions:
            if region.type == 'UI':
                region.tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):

        if self.engine == 'FACECAP':
            self.filter_glob = '*.txt'
        elif self.engine == 'EPIC':
            self.filter_glob = '*.csv'
        elif self.engine == 'A2F':
            self.filter_glob = '*.json'

        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


class FACEIT_OT_LoadAudioFile(bpy.types.Operator):
    '''Choose a audio file to import into sequencer'''
    bl_idname = 'faceit.load_audio_file'
    bl_label = 'Load Audio'
    bl_options = {'UNDO', 'INTERNAL'}

    engine: bpy.props.EnumProperty(
        name='mocap engine',
        items=(
            ('FACECAP', 'Face Cap', 'Face Cap TXT'),
            ('EPIC', 'Live Link Face', 'Live Link Face CSV'),
            ('A2F', 'Audio2Face', 'Nvidia Audio2Face'),
        ),
        options={'HIDDEN', },
    )

    filter_glob: bpy.props.StringProperty(
        default='*.mp3;*.wav',
        options={'HIDDEN'}
    )

    filepath: bpy.props.StringProperty(
        name='File Path',
        description='Filepath used for importing txt files',
        maxlen=1024,
        default='',
    )

    files: bpy.props.CollectionProperty(
        name='File Path',
        type=bpy.types.OperatorFileListElement,
    )

    def execute(self, context):

        fdata.get_engine_settings(self.engine).audio_filename = self.filepath

        # Update UI
        for region in context.area.regions:
            if region.type == 'UI':
                region.tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):

        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


class FACEIT_OT_ClearAudioFile(bpy.types.Operator):
    '''Clear the specified audio file'''
    bl_idname = 'faceit.clear_audio_file'
    bl_label = 'Clear Audio'
    bl_options = {'UNDO', 'INTERNAL'}

    engine: bpy.props.EnumProperty(
        name='mocap engine',
        items=(
            ('FACECAP', 'Face Cap', 'Face Cap TXT'),
            ('EPIC', 'Live Link Face', 'Live Link Face CSV'),
            ('A2F', 'Audio2Face', 'Nvidia Audio2Face'),
        ),
        options={'HIDDEN', },
    )

    def execute(self, context):

        fdata.get_engine_settings(self.engine).audio_filename = ''

        # Update UI
        # for region in context.area.regions:
        #     if region.type == 'UI':
        #         region.tag_redraw()
        return {'FINISHED'}


class FACEIT_OT_ClearMotionFile(bpy.types.Operator):
    '''Clear the specified motion file'''
    bl_idname = 'faceit.clear_motion_file'
    bl_label = 'Clear File'
    bl_options = {'UNDO', 'INTERNAL'}

    engine: bpy.props.EnumProperty(
        name='mocap engine',
        items=(
            ('FACECAP', 'Face Cap', 'Face Cap TXT'),
            ('EPIC', 'Live Link Face', 'Live Link Face CSV'),
            ('A2F', 'Audio2Face', 'Nvidia Audio2Face'),
        ),
        options={'HIDDEN', },
    )

    def execute(self, context):

        fdata.get_engine_settings(self.engine).filename = ''
        return {'FINISHED'}
