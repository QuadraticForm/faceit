import bpy
from mathutils import Matrix


def reset_pose(rig):
    '''Reset a rig to rest pose'''
    for pb in rig.pose.bones:
        reset_pb(pb)


def reset_pb(pb, reset_location=True, reset_rotation=True, reset_scale=True):
    '''Reset a pose bone to bind transforms'''
    M = pb.matrix_basis
    I = Matrix()
    if M == I:
        return
    loc, rot, scale = M.decompose()
    T = I if reset_location else Matrix.Translation(loc)
    R = I if reset_rotation else rot.to_matrix().to_4x4()
    S = I if reset_scale else Matrix.Diagonal(scale.to_4d())
    pb.matrix_basis = T @ R @ S


def is_pb_in_rest_pose(pb):
    '''Check if a pose bone is in rest pose'''
    return pb.matrix_basis == Matrix()  # pb.bone.matrix_local
