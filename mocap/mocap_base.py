
import math
import os
from math import degrees, pi as PI, radians
from pathlib import PurePath

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Object
from mathutils import Euler, Vector

from ..core import faceit_utils as futils
from ..core.fc_dr_utils import (frame_value_pairs_to_numpy_array,
                                populate_keyframe_points_from_np_array)
from ..core.retarget_list_base import FaceRegionsBaseProperties
from ..core.shape_key_utils import get_shape_key_names_from_objects
from ..ctrl_rig import control_rig_utils as ctrl_utils
from ..ctrl_rig.control_rig_animation_operators import CRIG_ACTION_SUFFIX
from ..panels.draw_utils import draw_head_targets_layout, draw_text_block
from .mocap_utils import get_scene_frame_rate

# Number of channels for each rotation mode
CHANNELS_ROTATION_MODE_DICT = {
    'EULER': 3,
    'AXIS_ANGLE': 4,
    'QUATERNION': 4
}
# FC coordinates to blender (swap Z and Y)
CHANNELS_FACECAP_TO_BLENDER = {
    0: 1,
    1: 2,
    2: 1,
}

FACECAP_SCALE_TO_BLENDER = .01


class MocapBase:
    '''Store mocap values and general functions for live, recording, loading of animations.'''

    fps = 24
    # shape key animation
    objects = None
    shape_ref = []
    target_shapes = None
    shape_count = 52
    use_region_filter = False
    active_regions_dict = {}
    animate_shapes = False
    # Head Transform animation; either object or bone
    head_obj = None
    head_bone = None
    head_bone_roll = 0
    # The intial position of the head target
    initial_location_offset = None
    # The rotation mode in EULER, QUATERNION, AXSI_ANGLE
    head_rotation_mode = 'EULER'
    # The data path in rotation_euler, rotation_quaternion, rotation_axis_angle
    head_rotation_data_path = 'rotation_euler'
    # Multiply the head location (set by user)
    head_location_multiplier = 1.0
    # scale transforms to blender
    scene_scale_multiplier = 0.01

    source_rotation_units = 'DEG'  # ,'RAD'

    animate_head_rotation = False
    animate_head_location = False
    aniamte_eyes = False
    # For Recording
    animation_timestamps = []
    sk_animation_lists = []
    head_rot_animation_lists = []
    head_loc_animation_lists = []
    eye_L_animation_lists = []
    eye_R_animation_lists = []

    sk_action = None
    head_action = None

    def __init__(self):
        self._initialize_mocap_settings()
        try:
            self.fps = get_scene_frame_rate()
        except AttributeError:
            pass

    def set_face_regions_dict(self, active_regions_dict):
        self.active_regions_dict = active_regions_dict

    def set_use_region_filter(self, use_region_filter):
        self.use_region_filter = use_region_filter

    def set_rotation_units(self, unit):
        '''Set rotation units in [DEGREES, RADIANS]'''
        self.source_rotation_units = unit

    def set_sk_action(self, action):
        self.sk_action = action

    def set_scene_frame_rate(self, fps):
        '''Overwrite the scene frame rate.'''
        self.fps = fps

    def set_head_action(self, action):
        self.head_action = action

    def set_shape_targets(self, objects=None, target_shapes=None):
        if not objects or not target_shapes:
            self.animate_shapes = False
            return
        self.objects = objects
        self.target_shapes = target_shapes
        self.shape_count = len(target_shapes)

    def normalizeAngle(self, angle):
        """
        :param angle: (float)
        :return: (float) Angle in radian in [-pi, pi]
        """
        while angle > np.pi:
            angle -= 2.0 * np.pi

        while angle < -np.pi:
            angle += 2.0 * np.pi

        return angle

    def set_head_targets(
        self,
        head_obj: Object,
        head_bone_name="",
        head_loc_mult=1.0,
        head_bone_roll=0,
    ) -> None:
        '''Set the head target objects. Optionally specify a bone target. Set which channels should be animated (rotation, location).'''
        self.head_obj = head_obj
        self.head_bone = None
        head_rot_mode = 'EULER'
        if head_obj:
            head_rot_mode = self._get_rotation_mode(head_obj)
            if self.head_obj.type == 'ARMATURE':
                if head_bone_name:
                    self.head_bone = self.head_obj.pose.bones.get(head_bone_name)
                    if self.head_bone:
                        head_rot_mode = self._get_rotation_mode(self.head_bone)
                    else:
                        print(f"Couldn't find the bone {head_bone_name} for head animation.")
        else:
            print("You need to specify a valid target object (Object or Armature) in order to animate the head.")
            self.animate_head_location = False
            self.animate_head_rotation = False
            return

        self.head_rotation_data_path = "rotation_" + head_rot_mode.lower()
        self.head_location_multiplier = head_loc_mult * FACECAP_SCALE_TO_BLENDER
        self.head_rotation_mode = head_rot_mode
        # get signed angle
        # print(math.degrees(head_bone_roll))
        self.head_bone_roll = self.normalizeAngle(head_bone_roll)
        # print(math.degrees(self.head_bone_roll))

    def _get_rotation_mode(self, target) -> str:
        '''Get the rotation mode from the target (object or bone)'''
        rot_mode = target.rotation_mode
        if len(rot_mode) <= 3:
            # EULER if rotation mode in ('XYZ','ZXY',...)
            rot_mode = 'EULER'
        return rot_mode

    def _initialize_mocap_settings(self):
        # self.shape_ref = list(get_face_cap_shape_data().keys())
        pass

    def _rotation_to_blender(self, value=None):
        '''Hacky method to bring the received rotation into the correct format and orientation.'''
        if len(value) < 3:
            return
        if not self.head_bone:
            # to Blender world coordinates (swap y and z and invert y)
            value = (value[0], -value[2], value[1])
        if self.source_rotation_units == 'DEG':
            rot = Euler(map(math.radians, value))
        else:
            rot = Euler(value)
        if round(self.head_bone_roll) != 0:
            if radians(175) < abs(self.head_bone_roll):
                # pi -> invert x and z
                rot.x *= -1
                rot.z *= -1
            elif radians(85) < self.head_bone_roll < radians(95):
                # pi halbe -> swap x and z and invert z
                temp_x = rot.x
                temp_z = -rot.z
                rot.x = - temp_z
                rot.z = temp_x
            elif radians(-85) > self.head_bone_roll > radians(-95):
                # minus pi halbe -> swap x and z and invert both
                temp_x = -rot.x
                temp_z = -rot.z
                rot.x = temp_z
                rot.z = temp_x

        if self.head_rotation_mode != 'EULER':
            rot = rot.to_quaternion()
            if self.head_rotation_mode == 'AXIS_ANGLE':
                vec, angle = rot.to_axis_angle()
                rot = [angle]
                rot.extend([i for i in vec])

        return rot

    def _location_to_blender(self, value=None):
        if not self.head_bone:
            loc = Vector((value[0], -value[2], value[1]))
        else:
            loc = Vector(value)
        loc *= self.head_location_multiplier
        return loc

    def _get_initial_location_offset(self, value):
        '''Calculate the location offset from the first incoming location value'''
        offset = Vector()
        # if not self.head_bone:
        if bpy.context.scene.faceit_use_head_location_offset:
            if not self.head_bone:
                offset = self.head_obj.location.copy()
            # else:
                # offset = self.head_bone.location.copy()
        # else:
        self.initial_location_offset = offset - self._location_to_blender(value)

    def _anim_values_to_keyframes(self, fc, frames, anim_values):
        '''Convert animation values to keyframes
        Args:
        fc: animation fcurve
        frames: list of timestamps
        anim_values: the animation values for this fcurve
        '''
        mocap_keyframe_points = frame_value_pairs_to_numpy_array(frames, anim_values)

        populate_keyframe_points_from_np_array(
            fc,
            mocap_keyframe_points,
            add=True,
            join_with_existing=True
        )

    def parse_animation_data(self, data, frame_start=0, record_frame_rate=1000):
        '''Parse and populate the animation data into animation lists.'''
        pass

    def clear_animation_targets(self):
        self.animate_shapes = False
        self.objects = []
        self.target_shapes = {}
        self.head_obj = None
        self.head_bone = None
        self.head_action = None

    def clear_animation_data(self):
        self.animation_timestamps = []
        self.sk_animation_lists = []
        self.head_rot_animation_lists = []
        self.head_loc_animation_lists = []
        # self.active_regions_dict = {}

    def recording_to_keyframes(self) -> bool:
        sk_animation_lists = self.sk_animation_lists
        head_rot_animation_lists = self.head_rot_animation_lists
        head_loc_animation_lists = self.head_loc_animation_lists
        keyframes_added = False
        if self.animate_shapes:
            if not self.sk_action:
                print("Couldn't find a valid shape key action.")
            if sk_animation_lists:
                sk_animation_lists = np.array(sk_animation_lists)
                # Shape Key animation (isolate all individual animation curves and convert to keyframes)
                for i in range(self.shape_count):
                    try:
                        anim_values = sk_animation_lists[:, i]
                    except IndexError:
                        print(f'failed at index {i}')
                        continue
                    name = self.shape_ref[i]
                    shape_item = self.target_shapes[name]
                    if getattr(shape_item, 'use_animation', True) is False:
                        print(f'Skipping Shape {shape_item.name}, because it is disabled in the shapes list.')
                        continue
                    if self.use_region_filter:
                        if hasattr(shape_item, 'region'):
                            region = shape_item.region.lower()
                            if self.active_regions_dict[region] is False:
                                print(f'skipping shape {shape_item.name} because of region filter')
                                continue
                    target_shapes = shape_item.target_shapes
                    for target_shape in target_shapes:
                        dp = f'key_blocks["{target_shape.name}"].value'
                        fc = self.sk_action.fcurves.find(dp)
                        if not fc:
                            fc = self.sk_action.fcurves.new(dp)
                        self._anim_values_to_keyframes(fc, self.animation_timestamps, anim_values)
                        keyframes_added = True

        # Head Transform Animation
        if self.animate_head_location or self.animate_head_rotation:
            head_dp_base = ""
            loc_dp = "location"
            # rot_dp = "rotation_euler"
            rot_channel_count = CHANNELS_ROTATION_MODE_DICT.get(self.head_rotation_mode, 3)

            if not self.head_obj.animation_data:
                self.head_obj.animation_data_create()
            self.head_obj.animation_data.action = self.head_action
            if self.head_bone:
                head_dp_base = f'pose.bones["{self.head_bone.name}"].'

            # Head Rotation
            if self.animate_head_rotation and head_rot_animation_lists:
                # print(head_rot_animation_lists)
                head_rot_animation_lists = list(map(self._rotation_to_blender, head_rot_animation_lists))
                head_rot_animation_lists = np.array(head_rot_animation_lists)
                for i in range(rot_channel_count):
                    try:
                        anim_values = head_rot_animation_lists[:, i]
                    except IndexError:
                        print('Index Error when getting anim values from head rot:')
                        continue
                    fc = self.head_action.fcurves.find(head_dp_base + self.head_rotation_data_path, index=i)
                    if not fc:
                        fc = self.head_action.fcurves.new(head_dp_base + self.head_rotation_data_path, index=i)
                    self._anim_values_to_keyframes(fc, self.animation_timestamps, anim_values)
                    keyframes_added = True
            # Head Location
            if self.animate_head_location and head_loc_animation_lists:
                head_loc_animation_lists = list(map(self._location_to_blender, head_loc_animation_lists))
                head_loc_animation_lists = np.array(head_loc_animation_lists)
                head_loc_animation_lists += self.initial_location_offset
                for i in range(3):
                    try:
                        anim_values = head_loc_animation_lists[:, i]
                    except IndexError:
                        print('Index Error when getting anim values from head loc:')
                        continue
                    # blender_index = self.CHANNELS_FACECAP_TO_BLENDER_[i]
                    fc = self.head_action.fcurves.find(head_dp_base + loc_dp, index=i)
                    if not fc:
                        fc = self.head_action.fcurves.new(head_dp_base + loc_dp, index=i)
                    self._anim_values_to_keyframes(fc, self.animation_timestamps, anim_values)
                    keyframes_added = True

        return keyframes_added


def update_new_action_name(self, context):
    self.new_action_exists = bool(bpy.data.actions.get(self.new_action_name))


def update_bake_ctrl_rig(self, context):
    crig = futils.get_faceit_control_armature()
    if not crig.animation_data:
        crig.animation_data_create()


class MocapImporterBase(FaceRegionsBaseProperties):
    '''Base class for importing raw mocap data from text or csv files'''
    bl_label = "Import"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

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
    overwrite_method: EnumProperty(
        name='Overwrite Method',
        items=(
            ('REPLACE', 'Replace', 'Replace the entire Action. All existing keyframes will be removed.'),
            ('MIX', 'Mix', 'Mix with existing keyframes, replacing only the new range.'),
        ),
        options={'SKIP_SAVE', }
    )
    bake_to_control_rig: BoolProperty(
        name='Bake to Control Rig',
        default=False,
        description='Loads the mocap action directly on the control rig. Creates a temp Action with the 52 Shape Keys.',
        update=update_bake_ctrl_rig,
        options={'SKIP_SAVE', }
    )
    frame_start: IntProperty(
        name='Start Frame',
        description='Start frame for the new keyframes. If append method is selected, the specified frame will present an offset to existing keyframes in the given action.',
        default=0,
        soft_min=0,
        soft_max=50000,
    )
    use_region_filter: BoolProperty(
        name='Filter Face Regions',
        default=False,
        description='Filter face regions that should be animated.'
        # options={'SKIP_SAVE', }
    )
    set_scene_frame_range: BoolProperty(
        name='Set Scene Frame Range',
        description='Sets the scene frame range to the range of the new action',
        default=True,
    )
    audio_filename: StringProperty(
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
    animate_head_rotation: BoolProperty(
        name="Rotation",
        default=True,
        description="Whether the recorded head rotation should be animated."
    )
    animate_head_location: BoolProperty(
        name="Location",
        default=False,
        description="Whether the recorded head location should be animated."
    )
    animate_shapes: BoolProperty(
        name="Animate Shapes",
        default=True,
        description="Whether the recorded expressions should be animated."
    )

    can_load_audio = False
    engine_settings_prop_name = "faceit_face_cap_mocap_settings"
    target_shapes_prop_name = "faceit_arkit_retarget_shapes"
    engine_settings = None
    record_frame_rate = 1000
    filename = ""
    can_bake_control_rig = True
    can_import_head_location = True
    can_import_head_rotation = True

    @classmethod
    def poll(cls, context):
        return True

    def _get_engine_specific_settings(self, context):
        self.engine_settings = getattr(context.scene, self.engine_settings_prop_name)

    def _get_mocap_importer(self) -> MocapBase:
        return MocapBase()

    def _get_engine_target_shapes(self, scene):
        return getattr(scene, self.target_shapes_prop_name)

    def _get_engine_target_objects(self, scene):
        return getattr(scene, self.target_objects_prop_name)

    def invoke(self, context, event):
        self._get_engine_specific_settings(context)
        raw_animation_data = self._get_raw_animation_data()
        if not raw_animation_data:
            self.report({'WARNING'}, "No recorded data found.")
            return {'CANCELLED'}
        if not self._check_file_path(self.engine_settings.filename):
            self.report({'ERROR'}, 'Mocap File not set or invalid')
            return {'CANCELLED'}
        self.filename = self._get_clean_filename(self.engine_settings.filename)
        faceit_objects = futils.get_faceit_objects_list()
        if not faceit_objects:
            self.report({'WARNING'}, "You need to register the character meshes in the setup tab.")
            return {'CANCELLED'}
        self.new_action_name = self.filename
        audio_file = self.engine_settings.audio_filename
        if audio_file:
            self.audio_filename = self._get_clean_filename(audio_file)
            self.can_load_audio = True
            self.load_audio_file = True
        if futils.get_faceit_control_armature() and self.can_bake_control_rig:
            self.bake_to_control_rig = True
            self.can_bake_control_rig = True
        else:
            self.can_bake_control_rig = False

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="Shapes Animation")
        row = col.row(align=True)
        row.prop(self, "animate_shapes", icon='BLANK1')
        if self.animate_shapes:
            self._draw_control_rig_ui(col)
            self._draw_region_filter_ui(col)

        self._draw_head_motion_types(col)
        if self.animate_head_location or self.animate_head_rotation:
            draw_head_targets_layout(col, show_head_action=False)

        if self.animate_shapes or self.animate_head_location or self.animate_head_rotation:
            self._draw_load_to_action_ui(col, context)
        else:
            if not (self.animate_head_location or self.animate_head_rotation):
                draw_text_block(
                    layout=layout,
                    text='Enable at least one type of motion.',
                    heading='WARNING'
                )
        self._draw_load_audio_ui(col)

    def _draw_control_rig_ui(self, layout):
        row = layout.row()
        if self.can_bake_control_rig:
            if futils.get_faceit_control_armature():
                row.prop(self, 'bake_to_control_rig', icon='CON_ARMATURE')

    def _draw_head_motion_types(self, layout):
        '''Draw the motion types for this operator.'''
        row = layout.row(align=True)
        # if self.can_import_head_location or self.can_import_head_rotation:
        row.label(text="Head Animation")
        row = layout.row(align=True)
        sub_row = row.row(align=True)
        sub_row.prop(self, "animate_head_rotation", icon='BLANK1')
        sub_row.enabled = self.can_import_head_rotation
        sub_row = row.row(align=True)
        sub_row.prop(self, "animate_head_location", icon='BLANK1')
        sub_row.enabled = self.can_import_head_location

    def _draw_load_to_action_ui(self, layout, context):
        scene = context.scene
        prop_split = layout.use_property_split
        layout.use_property_split = True
        row = layout.row()
        row.label(text='Action Settings')

        if self.bake_to_control_rig:
            ctrl_rig = futils.get_faceit_control_armature()
            row = layout.row(align=True)
            if ctrl_rig.animation_data:
                row.prop_search(ctrl_rig.animation_data,
                                'action', bpy.data, 'actions', text="Ctrl Rig Action")
            op = row.operator('faceit.new_ctrl_rig_action', icon='ADD', text="")
            op.action_name = self.new_action_name + CRIG_ACTION_SUFFIX

        elif self.animate_shapes:
            row = layout.row(align=True)
            row.prop(scene, "faceit_mocap_action", icon='ACTION')
            op = row.operator('faceit.new_action', icon='ADD', text="")
            op.action_name = self.new_action_name

        if self.animate_head_location or self.animate_head_rotation:
            head_obj = scene.faceit_head_target_object
            if head_obj:
                row = layout.row(align=True)
                # if head_obj.animation_data:
                #     row.prop_search(head_obj.animation_data,
                #                     'action', bpy.data, 'actions', text="Head Action")
                row.prop(scene, "faceit_head_action", icon='ACTION')
                op = row.operator('faceit.new_head_action', icon='ADD', text="")
                # op.action_name = self.new_action_name

        layout.separator()

        # def action_contains_keyframes(obj=None, action=None):
        #     if obj:
        #         if obj.animation_data:
        #             action = obj.animation_data.action
        #     if action:
        #         return bool(action.fcurves)
        #     return True

        # if action_contains_keyframes(scene.faceit_mocap_action) or
        # action_contains_keyframes(head_obj) or
        # action_contains_keyframes()
        # draw_text_block(
        #     layout,
        #     self=self,
        #     code="row.prop(self, 'overwrite_method', expand=True)",
        #     text="One or multiple Actions contain Keyframes",
        #     heading='WARNING'
        # )
        row = layout.row()
        row.prop(self, 'overwrite_method', expand=True)
        row = layout.row()
        row.prop(self, 'frame_start', icon='CON_TRANSFORM')

        layout.use_property_split = prop_split

    def _draw_load_audio_ui(self, layout):
        if self.can_load_audio:
            row = layout.row()
            row.label(text='Audio (Sequencer)')
            row = layout.row()
            row.prop(self, 'load_audio_file', icon='SEQUENCE')
            if self.load_audio_file:
                row = layout.row()
                row.prop(self, 'audio_filename', icon='SEQUENCE')
                row = layout.row()
                row.prop(self, 'remove_audio_tracks_with_same_name', icon='TRASH')
            layout.separator()

    def _draw_region_filter_ui(self, layout):

        row = layout.row(align=True)
        if self.use_region_filter:
            icon = 'TRIA_DOWN'
        else:
            icon = 'TRIA_RIGHT'
        row.prop(self, "use_region_filter", icon=icon)

        if self.use_region_filter:
            layout = layout.column(align=True)

            row = layout.row(align=True)

            icon_value = 'CHECKBOX_HLT' if self.brows else 'CHECKBOX_DEHLT'
            row.prop(self, 'brows', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.eyes else 'CHECKBOX_DEHLT'
            row.prop(self, 'eyes', icon=icon_value)

            row = layout.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.cheeks else 'CHECKBOX_DEHLT'
            row.prop(self, 'cheeks', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.nose else 'CHECKBOX_DEHLT'
            row.prop(self, 'nose', icon=icon_value)

            row = layout.row(align=True)
            icon_value = 'CHECKBOX_HLT' if self.mouth else 'CHECKBOX_DEHLT'
            row.prop(self, 'mouth', icon=icon_value)

            icon_value = 'CHECKBOX_HLT' if self.tongue else 'CHECKBOX_DEHLT'
            row.prop(self, 'tongue', icon=icon_value)

    def _check_file_path(self, filename):
        '''Returns True when filename is valid'''
        if not filename or not os.path.exists(filename) or not os.path.isfile(filename):
            return False
        return True

    def _get_clean_filename(self, filename):
        '''Returns the string filename - strips directories and file extension'''
        if filename:
            return PurePath(filename).stem

    def _get_action(self, action_name, replace=False):
        '''Get an action by name, create it if it does not exist'''
        action = bpy.data.actions.get(action_name)
        if action and replace:
            bpy.data.actions.remove(action, do_unlink=True)
            action = None
        if not action:
            self.report({'INFO'}, 'Creating new Action with name {}'.format(action_name))
            action = bpy.data.actions.new(name=action_name)
        return action

    def _load_new_audio_file(self, scene, start_frame_mocap, audio_file):
        channel = 1
        create_new = True
        if not scene.sequence_editor:
            scene.sequence_editor_create()
        else:
            soundstrip = scene.sequence_editor.sequences.get(self.audio_filename)
            if soundstrip:
                if soundstrip.frame_start == start_frame_mocap:
                    self.report(
                        {'INFO'},
                        f'The audio file {self.audio_filename} is already loaded on frame {start_frame_mocap}')
                    create_new = False
                else:
                    if self.remove_audio_tracks_with_same_name:
                        scene.sequence_editor.sequences.remove(soundstrip)

        if create_new:
            # Find the first free channel if the sequencer isn't empty
            occupied_channels = set((x.channel for x in scene.sequence_editor.sequences))
            if occupied_channels:
                possible_channels = set(range(1, max(occupied_channels) + 2))
                channel = min(possible_channels - occupied_channels)
            soundstrip = scene.sequence_editor.sequences.new_sound(
                self.audio_filename, audio_file, channel, start_frame_mocap)

        if soundstrip is not None:
            soundstrip.faceit_audio = True

    def _get_raw_animation_data(self):
        '''Return the raw animation data. Filename or osc queue for live animation'''
        return self.engine_settings.filename

    def _get_audio_file(self):
        '''Get the audio file.'''
        if self.load_audio_file:
            audio_file = self.engine_settings.audio_filename
            if not self._check_file_path(audio_file):
                self.report({'WARNING'}, 'Audio File not set or invalid')
                self.load_audio_file = False
                return None
            return audio_file
            # if audio_file:

    def execute(self, context):
        state_dict = futils.save_scene_state(context)

        animate_loc = self.animate_head_location
        animate_rot = self.animate_head_rotation
        animate_shapes = self.animate_shapes

        if not (animate_shapes or animate_loc or animate_rot):
            self.report({'ERROR'}, "You need to enable at least one type of motion!")
            return {'CANCELLED'}

        raw_animation_data = self._get_raw_animation_data()
        if not raw_animation_data:
            self.report({'ERROR'}, "No recorded data found.")
            return {'CANCELLED'}

        # obj_save = None
        # mode_save = futils.get_object_mode_from_context_mode(context.mode)
        for obj in context.scene.objects:
            futils.set_hidden_state_object(obj, False, False)
        if context.object is not None:
            bpy.ops.object.mode_set()

        audio_file = self._get_audio_file()

        mocap_importer = self._get_mocap_importer()
        mocap_importer.clear_animation_targets()
        mocap_importer.animate_head_location = animate_loc
        mocap_importer.animate_head_rotation = animate_rot
        mocap_importer.animate_shapes = animate_shapes

        scene = context.scene
        start_frame_mocap = self.frame_start

        if animate_shapes:
            if self.bake_to_control_rig:
                c_rig = futils.get_faceit_control_armature()
                if not c_rig:
                    self.report(
                        {'ERROR'},
                        'Can\'t find the active control rig. Please create/choose control rig first or import directly to the meshes.')
                    return {'CANCELLED'}
                # Get target action
                mocap_action = self._get_action("mocap_import", replace=True)
                # Get target objects and shapes
                target_objects = ctrl_utils.get_crig_objects_list(c_rig)
                target_shapes = c_rig.faceit_crig_targets
            else:
                # Get target action
                if scene.faceit_mocap_action is None or self.overwrite_method == 'REPLACE':
                    bpy.ops.faceit.new_action(
                        'EXEC_DEFAULT',
                        action_name=self.new_action_name,
                        overwrite_action=self.overwrite_method == 'REPLACE',
                        use_fake_user=True,
                    )
                mocap_action = scene.faceit_mocap_action
                target_objects = futils.get_faceit_objects_list()
                target_shapes = self._get_engine_target_shapes(scene)

            if not target_objects:
                self.report(
                    {'WARNING'},
                    'No registered objects found. {}'.format(
                        'Please update the control rig'
                        if self.bake_to_control_rig else 'Please register objects in Setup panel'))
                futils.restore_scene_state(context, state_dict)
                return {'CANCELLED'}

            if not target_shapes:  # or not rutils.get_all_set_target_shapes(retarget_list):
                self.report({'WARNING'}, 'Target Shapes are not properly configured. {}'.format(
                    'Please update the control rig' if self.bake_to_control_rig else 'Set up target shapes in Shapes panel.'))
                futils.restore_scene_state(context, state_dict)
                return {'CANCELLED'}

            if not get_shape_key_names_from_objects(objects=target_objects):
                self.report(
                    {'WARNING'},
                    'The registered objects hold no Shape Keys. Please create Shape Keys before loading mocap data.')
                futils.restore_scene_state(context, state_dict)
                return {'CANCELLED'}

            # Shape Settings
            mocap_importer.set_shape_targets(
                objects=target_objects,
                target_shapes=target_shapes
            )
            mocap_importer.use_region_filter = self.use_region_filter
            mocap_importer.active_regions_dict = self.get_active_regions()
            mocap_importer.set_sk_action(mocap_action)

        if animate_loc or animate_rot:
            # Head Settings
            head_obj = context.scene.faceit_head_target_object
            head_loc_multiplier = context.scene.faceit_osc_head_location_multiplier
            head_bone_name = context.scene.faceit_head_sub_target
            head_bone_roll = 0
            if head_obj:
                if head_obj.type == 'ARMATURE':
                    futils.set_active_object(head_obj.name)
                    bpy.ops.object.mode_set(mode='EDIT')
                    edit_bone = head_obj.data.edit_bones.get(head_bone_name)
                    if edit_bone:
                        head_bone_roll = round(edit_bone.roll % (2 * PI), 3)
                        # head_bone_roll = round(edit_bone.roll, 3)
                    bpy.ops.object.mode_set()
            mocap_importer.set_head_targets(
                head_obj=head_obj,
                head_bone_name=head_bone_name,
                head_loc_mult=head_loc_multiplier,
                head_bone_roll=head_bone_roll
            )
            if head_obj:
                if scene.faceit_head_action is None or self.overwrite_method == 'REPLACE':
                    bpy.ops.faceit.new_head_action(
                        'EXEC_DEFAULT',
                        overwrite_action=self.overwrite_method == 'REPLACE',
                        use_fake_user=True,
                    )
                mocap_importer.set_head_action(scene.faceit_head_action)

        # Process & Import Animation
        mocap_importer.fps = get_scene_frame_rate()
        mocap_importer.parse_animation_data(
            raw_animation_data,
            frame_start=self.frame_start,
            record_frame_rate=self.record_frame_rate
        )
        mocap_importer.recording_to_keyframes()

        if animate_shapes:
            if self.bake_to_control_rig:
                if mocap_action.fcurves:
                    # crig_action_name = mocap_action.name + CRIG_ACTION_SUFFIX
                    scene.faceit_bake_sk_to_crig_action = mocap_action
                    bpy.ops.faceit.bake_shape_keys_to_control_rig(
                        'EXEC_DEFAULT',
                        use_mocap_action=False,
                        overwrite_method=self.overwrite_method,
                        # action_source=mocap_action.name,
                        new_action_name=self.new_action_name + CRIG_ACTION_SUFFIX,
                        compensate_amplify_values=True,
                    )
                    # bpy.data.actions.remove(mocap_action, do_unlink=True)
                else:
                    self.report({'WARNING'}, 'No target shapes found. Please update control rig first!')
                    bpy.data.actions.remove(mocap_action, do_unlink=True)
                    futils.restore_scene_state(context, state_dict)
                    return {'CANCELLED'}
            else:
                bpy.ops.faceit.populate_action(action_name=mocap_action.name)
                scene.frame_start, scene.frame_end = (int(x) for x in futils.get_action_frame_range(mocap_action))
        # else:
        #     scene.frame_start, scene.frame_end = (int(x) for x in futils.get_action_frame_range(scene.faceit_head_action))

        # if obj_save:
        #     futils.clear_object_selection()
        #     futils.set_active_object(obj_save.name)
        # bpy.ops.object.mode_set(mode=mode_save)

        # ----------- Load Audio ----------------
        if self.load_audio_file:
            self._load_new_audio_file(scene, start_frame_mocap, audio_file)
        futils.restore_scene_state(context, state_dict)

        return {'FINISHED'}
