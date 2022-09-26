import os
import pathlib

import addon_utils
import bpy

from . import arkit_shapes as shapes

RIG_FILE = '/resources/FaceitRig.blend'
CONTROL_RIG_FILE = '/resources/FaceitControlRig.blend'
LANDMARKS_FILE = '/resources/FaceitLandmarks.blend'
RETARGET_PRESETS = '/resources/retarget_presets/'
EXPRESSION_PRESETS = '/resources/expressions/'

FACEIT_VERTEX_GROUPS = [
    'faceit_right_eyeball',
    'faceit_left_eyeball',
    'faceit_left_eyes_other',
    'faceit_right_eyes_other',
    'faceit_upper_teeth',
    'faceit_lower_teeth',
    'faceit_tongue',
    'faceit_eyelashes',
    'faceit_rigid',
    'faceit_main',
]


def get_faceit_current_version():

    version = '2'
    # return version
    for mod in addon_utils.modules():
        if mod.bl_info.get("name") == 'FACEIT':
            version = '.'.join([str(x) for x in mod.bl_info.get('version')])
            break
    return version


def get_addon_dir():
    return str(pathlib.Path(os.path.dirname(__file__)).parent.resolve())


def get_retargeting_presets():
    return get_addon_dir() + RETARGET_PRESETS


def get_expression_presets():
    return get_addon_dir() + EXPRESSION_PRESETS


def get_rig_file():
    return get_addon_dir() + RIG_FILE


def get_control_rig_file():
    return get_addon_dir() + CONTROL_RIG_FILE


def get_landmarks_file():
    return get_addon_dir() + LANDMARKS_FILE


def get_engine_settings(engine):
    if engine == 'FACECAP':
        engine_settings = bpy.context.scene.faceit_face_cap_mocap_settings
        engine_settings.indices_order = 'FACECAP'
    elif engine == 'EPIC':
        engine_settings = bpy.context.scene.faceit_epic_mocap_settings
        engine_settings.indices_order = 'ARKIT'
    elif engine == 'A2F':
        engine_settings = bpy.context.scene.faceit_a2f_mocap_settings
    return engine_settings


def get_arkit_shape_data():
    '''Returns list of the original arkit expression names'''
    return shapes.ARKIT['Data']


def get_face_cap_shape_data():
    '''Returns list of the original arkit expression names'''
    return shapes.FACECAP['Data']


def get_epic_shape_data():
    '''Returns list of the original arkit expression names'''
    return shapes.EPIC['Data']


def get_a2f_shape_data():
    '''Returns list of the original arkit expression names'''
    return shapes.A2F['Data']


def get_tongue_shape_data():
    '''Returns list of the original arkit expression names'''
    return shapes.TONGUE['Data']


def get_phonemes_shape_data():
    '''Returns list of the original arkit expression names'''
    return shapes.PHONEMES['Data']


def get_shape_data_for_mocap_engine(mocap_engine=None):
    '''Takes the original expression name and returns the new index for the specified mocap engine
    @arkit_name: must be in ARKIT['Names']
    @mocap_engine: value in [ARKIT, FACECAP, EPIC]
    '''
    if not mocap_engine:
        return
    if mocap_engine == 'ARKIT':
        return get_arkit_shape_data()
    if mocap_engine == 'FACECAP':
        return get_face_cap_shape_data()
    if mocap_engine == 'EPIC':
        return get_epic_shape_data()
    if mocap_engine == 'A2F':
        return get_a2f_shape_data()


def get_list_faceit_groups():

    return FACEIT_VERTEX_GROUPS


def get_face_region_items(self, context):
    ''' Returns the regions dictionary keys as enum items '''
    region_items = []
    for r in FACE_REGIONS_BASE.keys():
        region_items.append((r, r, r))
    return region_items


def get_regions_dict():
    region_dict = {}
    for region, shapes in FACE_REGIONS_BASE.items():
        for shape in shapes:
            region_dict[shape] = region

    return region_dict


FACE_REGIONS_BASE = {
    'Eyes': [
        'eyeBlinkLeft',
        'eyeLookDownLeft',
        'eyeLookInLeft',
        'eyeLookOutLeft',
        'eyeLookUpLeft',
        'eyeSquintLeft',
        'eyeWideLeft',
        'eyeBlinkRight',
        'eyeLookDownRight',
        'eyeLookInRight',
        'eyeLookOutRight',
        'eyeLookUpRight',
        'eyeSquintRight',
        'eyeWideRight',
        'eyesLookLeft',
        'eyesLookRight',
        'eyesLookUp',
        'eyesLookDown',
        'eyesCloseL',
        'eyesCloseR',
        'eyesUpperLidRaiserL',
        'eyesUpperLidRaiserR',
        'squintL',
        'squintR',
    ],
    'Brows': [
        'browDownLeft',
        'browDownRight',
        'browInnerUp',
        'browOuterUpLeft',
        'browOuterUpRight',
        'browLowerL',
        'browLowerR',
        'innerBrowRaiserL',
        'innerBrowRaiserR',
        'outerBrowRaiserL',
        'outerBrowRaiserR',
    ],
    'Cheeks': [
        'cheekPuff',
        'cheekSquintLeft',
        'cheekSquintRight',
        'cheekRaiserL',
        'cheekRaiserR',
        'cheekPuffL',
        'cheekPuffR',
    ],
    'Nose': [
        'noseSneerLeft',
        'noseSneerRight',
        'noseWrinklerL',
        'noseWrinklerR',
    ],
    'Mouth': [
        'jawForward',
        'jawLeft',
        'jawRight',
        'jawOpen',
        'mouthClose',
        'mouthFunnel',
        'mouthPucker',
        'mouthRight',
        'mouthLeft',
        'mouthSmileLeft',
        'mouthSmileRight',
        'mouthFrownRight',
        'mouthFrownLeft',
        'mouthDimpleLeft',
        'mouthDimpleRight',
        'mouthStretchLeft',
        'mouthStretchRight',
        'mouthRollLower',
        'mouthRollUpper',
        'mouthShrugLower',
        'mouthShrugUpper',
        'mouthPressLeft',
        'mouthPressRight',
        'mouthLowerDownLeft',
        'mouthLowerDownRight',
        'mouthUpperUpLeft',
        'mouthUpperUpRight',
        'aa_ah_ax_01',
        'aa_02',
        'ao_03',
        'ey_eh_uh_04',
        'er_05',
        'y_iy_ih_ix_06',
        'w_uw_07',
        'ow_08',
        'aw_09',
        'oy_10',
        'ay_11',
        'h_12',
        'r_13',
        'l_14',
        's_z_15',
        'sh_ch_jh_zh_16',
        'th_dh_17',
        'f_v_18',
        'd_t_n_19',
        'k_g_ng_20',
        'p_b_m_21',
        'jawDrop',
        'jawDropLipTowards',
        'jawThrust',
        'jawSlideLeft',
        'jawSlideRight',
        'mouthSlideLeft',
        'mouthSlideRight',
        'dimplerL',
        'dimplerR',
        'lipCornerPullerL',
        'lipCornerPullerR',
        'lipCornerDepressorL',
        'lipCornerDepressorR',
        'lipStretcherL',
        'lipStretcherR',
        'upperLipRaiserL',
        'upperLipRaiserR',
        'lowerLipDepressorL',
        'lowerLipDepressorR',
        'chinRaiser',
        'lipPressor',
        'pucker',
        'funneler',
        'lipSuck',

    ],
    'Tongue': [
        'tongueOut',
        'tongueBack',
        'tongueTwistLeft',
        'tongueTwistRight',
        'tongueLeft',
        'tongueRight',
        'tongueWide',
        'tongueThin',
        'tongueCurlUp',
        'tongueCurlUp',
        'tongueCurlUp',
        'tongueCurlDown',
    ],
    'Other': [

    ]
}
