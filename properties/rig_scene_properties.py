import bpy
from bpy.props import (PointerProperty, StringProperty, BoolProperty, EnumProperty)
from bpy.types import Bone, Object, Scene

from ..core.modifier_utils import populate_bake_modifier_items
from ..core.faceit_utils import is_faceit_original_armature, is_rigify_armature, get_faceit_objects_list
from ..core.faceit_data import FACEIT_CTRL_BONES


def faceit_armature_poll(self, obj):
    '''Return True if the object is a valid faceit rig (armature).'''
    if obj.type == 'ARMATURE' and obj.name in self.objects:
        return True


def update_faceit_armature(self, context):
    if self.faceit_armature is not None:
        self.faceit_armature_missing = False


def body_armature_poll(self, obj):
    '''Return True if the object is a valid body rig (armature).'''
    if obj.type == 'ARMATURE' and obj.name in self.objects:
        if not is_faceit_original_armature(obj):
            return True


def update_body_armature(self, context):
    rig = self.faceit_body_armature
    self.faceit_use_rigify_armature = False
    self.faceit_is_rigify_armature = False
    if rig is None:
        return
    if not self.faceit_pivot_ref_armature:
        self.faceit_pivot_ref_armature = rig
    if is_rigify_armature(rig):
        self.faceit_use_rigify_armature = True
        self.faceit_is_rigify_armature = True
    # try to find head bone name
    for b in rig.data.bones:
        if b.use_deform:
            b_name = b.name.lower()
            if "head" in b_name:
                self.faceit_body_armature_head_bone = b.name
                break


def update_use_as_rigify_armature(self, context):
    if self.faceit_use_rigify_armature:
        if not self.faceit_armature:
            self.faceit_armature = self.faceit_body_armature
        self.faceit_show_warnings = False
        objects = get_faceit_objects_list()
        populate_bake_modifier_items(objects)
    else:
        if self.faceit_armature == self.faceit_body_armature:
            self.faceit_armature = None


def update_eye_bone_pivots(self, context):
    rig = self.faceit_pivot_ref_armature
    if not rig:
        return
    # Find the eye bones
    left_eye_bones = []
    right_eye_bones = []
    for b in rig.data.bones:
        if not b.use_deform:
            continue
        b_name = b.name.lower()
        if "eye" in b_name:
            if "left" in b_name or b_name.endswith("_l") or b_name.endswith(".l") or "_l_" in b_name:
                left_eye_bones.append(b.name)
            elif "right" in b_name or b_name.endswith("_r") or b_name.endswith(".r") or "_r_" in b_name:
                right_eye_bones.append(b.name)
    if left_eye_bones and right_eye_bones:
        self.faceit_anime_ref_eyebone_l = min(left_eye_bones, key=len)
        self.faceit_anime_ref_eyebone_r = min(right_eye_bones, key=len)


def update_eye_pivot_options(self, context):
    bpy.ops.faceit.update_eye_locators('EXEC_DEFAULT', set_active_object=self.faceit_eye_pivot_options == 'MANUAL')


def register():
    Scene.faceit_armature = PointerProperty(
        name='Faceit Armature',
        description='The armature to be used in the binding and baking operators. Needs to be a Rigify layout.',
        type=Object,
        poll=faceit_armature_poll,
        update=update_faceit_armature,
    )
    Scene.faceit_armature_missing = BoolProperty(
        name='Missing Armature',
        description='The armature is missing. Did you remove it intentionally?',
    )
    Scene.faceit_body_armature = PointerProperty(
        name='Existing Rig',
        type=Object,
        poll=body_armature_poll,
        update=update_body_armature
    )
    Scene.faceit_pivot_ref_armature = PointerProperty(
        name='Pivot Reference Armature',
        type=Object,
        poll=faceit_armature_poll,
        update=update_eye_bone_pivots
    )
    Scene.faceit_body_armature_head_bone = StringProperty(
        name='Bone',
        default='',
    )
    Scene.faceit_eye_pivot_options = EnumProperty(
        name='Eye Pivot Options',
        items=[
            ('EYE_GEO', 'Eyeball Geometry', 'Use the eyeball geometry to find the correct eye pivots.'),
            ('MANUAL', 'Manual', 'Manually set the eye pivots.'),
            ('BONE_PIVOT', 'Bone Pivot', 'Use the eye bone pivot to find the correct eye pivots.'),
        ],
        default=0,
        update=update_eye_pivot_options,
    )
    Scene.faceit_pivot_from_eye_deform_group = BoolProperty(
        name='Pivot from Deform Group',
        description='When active, the eye bones will be placed at the center of the deform groups (faceit_left_eyes_other, faceit_right_eye_other).',
        default=False, update=update_eye_pivot_options)
    Scene.faceit_show_eye_locators = BoolProperty(
        name='Show Locators',
        description='When active, the eye locators will be shown. Otherwise they are only visible in MANUAL mode.',
        default=False,
        update=update_eye_pivot_options
    )
    Scene.faceit_anime_ref_eyebone_l = StringProperty(
        name="Left Eye Bone",
        description="The left eye bone of the anime character.",
        default=""
    )
    Scene.faceit_anime_ref_eyebone_r = StringProperty(
        name="Right Eye Bone",
        description="The right eye bone of the anime character.",
        default=""
    )
    Scene.faceit_use_rigify_armature = BoolProperty(
        name='Use Existing Rigify Face Rig', default=False,
        description='When active, you can choose a Rigify Armature from the active scene. You can either use the Faceit Armature OR a Rigify Armature for creating the expressions.',
        update=update_use_as_rigify_armature)
    Scene.faceit_is_rigify_armature = BoolProperty(
        name="Is Rigify Armature",
        default=False,
    )


def unregister():
    del Scene.faceit_armature
    del Scene.faceit_body_armature_head_bone
    del Scene.faceit_eye_pivot_options
    del Scene.faceit_anime_ref_eyebone_l
    del Scene.faceit_anime_ref_eyebone_r
    del Scene.faceit_use_rigify_armature
