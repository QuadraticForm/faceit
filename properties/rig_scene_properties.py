import bpy
from bpy.props import (PointerProperty, StringProperty, BoolProperty, EnumProperty)
from bpy.types import Bone, Object, Scene

from ..core.faceit_utils import is_faceit_original_armature
from ..core.faceit_data import FACEIT_CTRL_BONES


def is_armature_poll(self, obj):
    if obj.type == 'ARMATURE' and obj.name in self.objects:
        if not is_faceit_original_armature(obj):
            return True


def is_armature_object_rigify(rig_obj):
    if rig_obj is not None:
        if rig_obj.type == 'ARMATURE':
            if rig_obj.name in bpy.context.scene.objects:
                if len(set.intersection(set(FACEIT_CTRL_BONES), set(rig_obj.data.bones.keys()))) == len(FACEIT_CTRL_BONES):
                    return True


def is_armature_object(self, object):
    if object.type == 'ARMATURE':
        return True


def update_body_armature(self, context):
    rig = self.faceit_body_armature
    if rig is None:
        self.faceit_use_eye_pivots = False
        self.faceit_use_rigify_armature = False
        return
    self.faceit_is_rigify_armature = False
    self.faceit_use_rigify_armature = False
    is_rigify_face = is_armature_object_rigify(rig)
    if is_rigify_face:
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
        self.faceit_use_eye_pivots = False
    else:
        if self.faceit_armature == self.faceit_body_armature:
            self.faceit_armature = None


def update_eye_bone_pivots(self, context):
    rig = self.faceit_body_armature
    if not rig or not self.faceit_use_eye_pivots:
        self.faceit_anime_ref_eyebone_l = ""
        self.faceit_anime_ref_eyebone_r = ""
        return
    # Find the eye bones
    left_eye_bones = []
    right_eye_bones = []
    # Find DEF bones first.
    # deform_eye_bones = any(b.use_deform and "eye" in b.name.lower() for b in rig.data.bones)
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


def register():
    Scene.faceit_armature = PointerProperty(
        name='Faceit Armature',
        description='The armature to be used in the binding and baking operators. Needs to be a Rigify layout.',
        type=Object,
    )
    Scene.faceit_body_armature = PointerProperty(
        name='Existing Rig',
        type=Object,
        poll=is_armature_poll,
        update=update_body_armature
    )

    Scene.faceit_body_armature_head_bone = StringProperty(
        name='Bone',
        default='',
    )

    Scene.faceit_use_eye_pivots = BoolProperty(
        name="Eye Bones (Pivots)",
        default=False,
        description="Specify eye bones for perfect pivot placement. Useful for anime characters.",
        update=update_eye_bone_pivots
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
    del Scene.faceit_use_eye_pivots
    del Scene.faceit_anime_ref_eyebone_l
    del Scene.faceit_anime_ref_eyebone_r
    del Scene.faceit_use_rigify_armature
