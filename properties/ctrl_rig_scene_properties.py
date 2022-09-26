
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, IntProperty, PointerProperty,
                       StringProperty)
from bpy.types import Object, PropertyGroup, Scene

from ..core.retarget_list_base import FaceRegionsBase, RetargetShapesBase
from ..ctrl_rig.custom_slider_utils import \
    get_custom_sliders_from_faceit_objects_enum


def is_armature_object(self, obj):
    if obj.library:
        return False
    if obj.type == 'ARMATURE' and obj.name in bpy.context.scene.objects:
        if 'FaceitControlRig' in obj.name or 'ctrl_rig_id' in obj:
            return True


class Target_Objects(PropertyGroup):
    name: StringProperty(
        name='Object Name',
        description='object name'
    )
    # Problem with object ids, they have to be deleted globally,
    # otherwise they will never be none. Even if deleted from scene..
    obj_pointer: PointerProperty(
        name='Object',
        type=Object
    )


class ControlRigShapes(RetargetShapesBase, PropertyGroup):

    custom_slider: BoolProperty(
        name='Custom Slider',
        default=False,
        description='Whether this is a custom slider or standart ARKit target',
    )

    slider_name: StringProperty(
        name='Bone Name',
        description='The name of the slider controlling this shape',
        default='',
    )
    if bpy.app.version >= (2, 90, 0):
        amplify: FloatProperty(
            name='Amplify Value',
            default=1.0,
            description='Use the Amplify Value to multiply all animation values by a factor. Increase Shape Key ranges to aninate beyond the range [0,1]',
            soft_min=0.0,
            soft_max=10.0,
            override={'LIBRARY_OVERRIDABLE'},
        )
    else:
        amplify: FloatProperty(
            name='Amplify Value',
            default=1.0,
            description='Use the Amplify Value to multiply all animation values by a factor. Increase Shape Key ranges to aninate beyond the range [0,1]',
            soft_min=0.0,
            soft_max=10.0,
        )


def register():

    Scene.faceit_draw_handler_name = StringProperty(
        name='draw handler',
        default=''
    )

    Scene.faceit_control_armature = PointerProperty(
        name='The Control Rig',
        description='the control rig used to control and manipulate the Faceit Expressions. Create override to load linked control rigs.',
        type=Object, poll=is_armature_object)

    Scene.faceit_crig_targets = CollectionProperty(
        name='Control Rig Target Expressions',
        type=ControlRigShapes,
    )
    Scene.faceit_crig_targets_index = IntProperty(
        name='CRig Shapes Index',
        default=0,
        options=set(),
    )

    Scene.faceit_new_slider = EnumProperty(
        name='Target',
        items=get_custom_sliders_from_faceit_objects_enum,
        description='The Shape that will be driven by the new controller',
    )
    if bpy.app.version >= (2, 90, 0):
        Object.faceit_crig_targets_index = IntProperty(
            name='CRig Shapes Index',
            default=0,
            options=set(),
            override={'LIBRARY_OVERRIDABLE'},
        )

        Object.faceit_crig_targets = CollectionProperty(
            name='Control Rig Target Expressions',
            type=ControlRigShapes,
            override={'LIBRARY_OVERRIDABLE'},
        )

        Object.faceit_crig_objects = CollectionProperty(
            name='Objects Driven',
            type=Target_Objects,
        )

        Object.faceit_crig_objects_index = IntProperty(
            name='CRig Objects Index',
            default=0,
            options=set(),
            override={'LIBRARY_OVERRIDABLE'},
        )

        Object.faceit_crig_face_regions = PointerProperty(
            name='Face Regions (Control Rig)',
            type=FaceRegionsBase,
            override={'LIBRARY_OVERRIDABLE'},
        )
    else:
        Object.faceit_crig_targets_index = IntProperty(
            name='CRig Shapes Index',
            default=0,
            options=set(),
        )

        Object.faceit_crig_targets = CollectionProperty(
            name='Control Rig Target Expressions',
            type=ControlRigShapes,
        )

        Object.faceit_crig_objects = CollectionProperty(
            name='Objects Driven',
            type=Target_Objects,
        )

        Object.faceit_crig_objects_index = IntProperty(
            name='CRig Objects Index',
            default=0,
            options=set(),
        )
        Object.faceit_crig_face_regions = PointerProperty(
            name='Face Regions (Control Rig)',
            type=FaceRegionsBase,
        )


def unregister():

    del Scene.faceit_draw_handler_name
    del Scene.faceit_control_armature

    del Scene.faceit_crig_targets
    del Scene.faceit_crig_targets_index
    del Scene.faceit_new_slider

    del Object.faceit_crig_targets
    del Object.faceit_crig_objects_index
    del Object.faceit_crig_objects
    del Object.faceit_crig_face_regions
