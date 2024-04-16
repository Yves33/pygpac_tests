#!/usr/bin/env python
import numpy as np

## basic gl matrix utils
def ortho(left, right, top, bottom, z_near, z_far):
    m11 = 2 / (right-left)
    m22 = 2 / (top-bottom)
    m33 = -2 / (z_far-z_near)
    m34 = (right+left) / (right-left)
    m42 = (top+bottom) / (top-bottom)
    m43 = (z_far+z_near) / (z_far-z_near)
    return np.array([
        [m11, 0, 0,  0],
        [0, m22, 0,  0],
        [0, 0, m33, m34],
        [0, m42, m43, 1]
    ])

def scale(sx,sy,sz):
    return np.array([
        [sx,0,0,0],
        [0,sy,0,0],
        [0,0,sz,0],
        [0,0,0,1]
    ],dtype=np.float32)

def translate(tx,ty,tz):
    return np.array([
        [1,0,0,0],
        [0,1,0,0],
        [0,0,1,0],
        [tx,ty,tz,1]
    ],dtype=np.float32)

def rotate_x(a):
    c=np.cos(a*3.14159/180)
    s=np.sin(a*3.14159/180)
    return np.array([
        [ 1, 0, 0, 0],
        [ 0, c,-s, 0],
        [ 0, s, c, 0],
        [ 0, 0, 0, 1]
    ],dtype=np.float32)

def rotate_y(a):
    c=np.cos(a*3.14159/180)
    s=np.sin(a*3.14159/180)
    return np.array([
        [ c, 0, s, 0],
        [ 0, 1, 0, 0],
        [-s, 0, c, 0],
        [ 0, 0, 0, 1]
    ],dtype=np.float32)

def rotate_z(a):
    c=np.cos(a*3.14159/180)
    s=np.sin(a*3.14159/180)
    return np.array([
        [ c,-s, 0, 0],
        [ s, c, 0, 0],
        [ 0, 0, 1, 0],
        [ 0, 0, 0, 1]
    ],dtype=np.float32)
