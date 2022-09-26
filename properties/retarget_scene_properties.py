import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy.types import PropertyGroup, Scene

from ..core.retarget_list_base import FaceRegionsBase, RetargetShapesBase

# --------------- CLASSES --------------------
# | - Property Groups (Collection-/PointerProperty)
# ----------------------------------------------


class RetargetShapes(RetargetShapesBase, PropertyGroup):

    name: StringProperty(
        name='ARKit Expression',
        description='The ARKit Expression Name (Source Shape)',
        options=set(),
    )

    display_name: StringProperty(
        name='ARKit Expression',
        description='The ARKit Expression Display Name (Source Shape)',
        options=set(),
    )


# --------------- FUNCTIONS --------------------
# | - Update/Getter/Setter
# ----------------------------------------------


def update_retargeting_scheme(self, context):
    if context is None:
        return
    if self.faceit_arkit_retarget_shapes:
        bpy.ops.faceit.change_retargeting_name_scheme()


def update_retarget_index(self, context):
    if context is None:
        return
    if self.faceit_sync_shapes_index:
        active_shape_item = None
        if self.faceit_display_retarget_list == 'ARKIT':
            if self.faceit_arkit_retarget_shapes:
                active_shape_item = self.faceit_arkit_retarget_shapes[self.faceit_arkit_retarget_shapes_index]
        else:
            if self.faceit_a2f_retarget_shapes:
                active_shape_item = self.faceit_a2f_retarget_shapes[self.faceit_a2f_retarget_shapes_index]

        if active_shape_item:
            shape_name = active_shape_item.name
            bpy.ops.faceit.set_active_shape_key_index(
                'EXEC_DEFAULT', shape_name=shape_name, get_active_target_shapes=True)


def update_shape_sync(self, context):
    if context is None:
        return
    if self.faceit_sync_shapes_index:
        active_shape_item = None
        if self.faceit_display_retarget_list == 'ARKIT':
            if self.faceit_arkit_retarget_shapes:
                active_shape_item = self.faceit_arkit_retarget_shapes[self.faceit_arkit_retarget_shapes_index]
        else:
            if self.faceit_a2f_retarget_shapes:
                active_shape_item = self.faceit_a2f_retarget_shapes[self.faceit_a2f_retarget_shapes_index]

        if active_shape_item:
            shape_name = active_shape_item.name
            bpy.ops.faceit.set_active_shape_key_index(
                'EXEC_DEFAULT', shape_name=shape_name, get_active_target_shapes=True)
    # if self.faceit_sync_shapes_index:
    #     active_shape_item = self.faceit_arkit_retarget_shapes[self.faceit_arkit_retarget_shapes_index]
    #     if active_shape_item:
    #         bpy.ops.faceit.set_active_shape_key_index(
    #             'EXEC_DEFAULT', shape_name=active_shape_item.name, get_active_target_shapes=True)

# --------------- REGISTER/UNREGISTER --------------------


def register():
    ############## Retargeting Shapes ##################

    Scene.faceit_arkit_retarget_shapes = CollectionProperty(
        name='ARKIT Target Expressions',
        type=RetargetShapes,
    )

    Scene.faceit_arkit_retarget_shapes_index = IntProperty(
        name='Expression Index',
        default=0,
        update=update_retarget_index,
        options=set(),
    )
    Scene.faceit_a2f_retarget_shapes = CollectionProperty(
        name='Audio2Face Target Expressions',
        type=RetargetShapes,
    )
    Scene.faceit_a2f_retarget_shapes_index = IntProperty(
        name='Expression Index',
        default=0,
        update=update_retarget_index,
        options=set(),
    )

    Scene.faceit_face_regions = PointerProperty(
        name='Face Regions',
        type=FaceRegionsBase,
    )

    Scene.faceit_sync_shapes_index = BoolProperty(
        name='Sync Selection',
        default=True,
        update=update_shape_sync,
        description='Synchronize the index in the active faceit shape and the active shape key on all registered objects'
    )
    Scene.faceit_shape_key_lock = BoolProperty(
        name='Show Only Active',
        default=True,
        update=update_shape_sync,
        description='Show only the active shape key on all registered objects'
    )
    Scene.faceit_display_retarget_list = EnumProperty(
        items=(
            ('ARKIT', 'ARKit', 'ARKit Native'),
            ('A2F', 'Audio2Face', 'Nvidia Audio2Face'),
        ),
        default='ARKIT',
    )
    Scene.faceit_retargeting_naming_scheme = EnumProperty(
        items=(
            ('ARKIT', 'ARKit Native', 'ARKit Native'),
            ('FACECAP', 'FaceCap', 'bannaflak FaceCap'),
        ),
        default='ARKIT',
        update=update_retargeting_scheme,
    )


def unregister():
    del Scene.faceit_face_regions
    del Scene.faceit_arkit_retarget_shapes
    del Scene.faceit_arkit_retarget_shapes_index
    del Scene.faceit_a2f_retarget_shapes
    del Scene.faceit_a2f_retarget_shapes_index
    del Scene.faceit_sync_shapes_index
    del Scene.faceit_shape_key_lock
    del Scene.faceit_retargeting_naming_scheme
