#!/usr/bin/env python
from OpenGL.GL import *
import numpy as np
from glmath import *

class Shape:
    def __init__(self, name, vertices=None, normals=None,tex_coords=None):
        self.name = name
        self.vertex_vbo = None
        self.texcoord_vbo = None
        self.normal_vbo = None
        self.att_vertex = -1
        self.att_normal = -1
        self.att_texcoord = -1
        self.nb_points = 0
        self.np_texcoord = None
        if vertices:
            self.build_buffers(vertices, normals, tex_coords)

    def build_buffers(self, vertices, normals, tex_coords, lines=False):
        for val in vertices:
            if len(val) != 3:
                print('Invalid number of points in vertice ' + str(val))
                exit()
        self.nb_points = int(len(vertices))
        vertices = np.array(vertices, dtype=np.float32)
        if lines:
            self.type = GL_LINE_STRIP
        else:
            self.type = GL_TRIANGLES

        if normals and len(normals)==0:
            normals = None

        if tex_coords and len(tex_coords)==0:
            tex_coords = None

        # Generate buffers to hold our vertices
        self.vertex_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vertex_vbo)
        glBufferData(GL_ARRAY_BUFFER, self.nb_points*3*4, vertices, GL_STATIC_DRAW)

        if normals != None:
            if self.nb_points != len(normals):
                print('Invalid number of points in normals')
                exit()
            for val in normals:
                if len(val) != 3:
                    print('Invalid number of points in normals ' + str(val))
                    exit()
            normals = np.array(normals, dtype=np.float32)
            self.normal_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.normal_vbo)
            glBufferData(GL_ARRAY_BUFFER, self.nb_points*3*4, normals, GL_STATIC_DRAW)

        if tex_coords != None:
            if self.nb_points != len(tex_coords):
                print('Invalid number of points in tex_coords ' + str(len(tex_coords)) + ' expecting ' + str(self.nb_points * 2))
                exit()
            for val in tex_coords:
                if len(val) != 2:
                    print('Invalid number of points in normals ' + str(val))
                    exit()
            tex_coords = np.array(tex_coords, dtype=np.float32)
            self.texcoord_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.texcoord_vbo)
            glBufferData(GL_ARRAY_BUFFER, self.nb_points*2*4, tex_coords, GL_STATIC_DRAW)
            self.np_texcoord = tex_coords

        #print('Buffers generated - Number of points ' + str(self.nb_points) + ' vertex_vbo ' + str(self.vertex_vbo) + ' normal_vbo ' + str(self.normal_vbo) + ' texcoord_vbo ' + str(self.texcoord_vbo))
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def draw(self, prog):
        program = prog.program
        self.att_vertex = glGetAttribLocation(program, "aVertex")
        glBindBuffer(GL_ARRAY_BUFFER, self.vertex_vbo)
        glEnableVertexAttribArray(self.att_vertex)
        glVertexAttribPointer(self.att_vertex, 3, GL_FLOAT, False, 0, ctypes.c_void_p(0))

        if self.normal_vbo:
            self.att_normal = glGetAttribLocation(program, "aNormal")
            if self.att_normal>=0:
                glBindBuffer(GL_ARRAY_BUFFER, self.att_normal)
                glEnableVertexAttribArray(self.att_normal)
                glVertexAttribPointer(self.att_normal, 3, GL_FLOAT, False, 0, ctypes.c_void_p(0))

        if self.texcoord_vbo:
            self.att_texcoord = glGetAttribLocation(program, "aTexCoord")
            if self.att_texcoord>=0:
                glBindBuffer(GL_ARRAY_BUFFER, self.texcoord_vbo)
                glEnableVertexAttribArray(self.att_texcoord)
                glVertexAttribPointer(self.att_texcoord, 2, GL_FLOAT, False, 0, ctypes.c_void_p(0))

        #print('Buffers ready -  vertex_att ' + str(self.att_vertex) + ' normal_att ' + str(self.att_normal) + ' texcoord_att ' + str(self.att_texcoord))

        glDrawArrays(self.type, 0, self.nb_points)
        #disable vertex attrib arrays
        glDisableVertexAttribArray(self.att_vertex)
        if self.att_normal>=0:
            glDisableVertexAttribArray(self.att_normal)
        if self.att_texcoord>=0:
            glDisableVertexAttribArray(self.att_texcoord)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

class Rectangle(Shape):
    def __init__(self, name, flip = False):
        Shape.__init__(self, name)
        ty_min = 0.0
        ty_max = 1.0
        if flip == True:
            ty_min = 1.0
            ty_max = 0.0

        self.build_buffers(
            [( -1.000000, -1.000000, 0.000000),
            ( 1.000000, -1.000000, 0.000000),
            ( 1.000000, 1.000000, 0.000000),
            ( -1.000000, -1.000000, 0.000000),
            ( 1.000000, 1.000000, 0.000000),
            ( -1.000000, 1.000000, 0.000000)],
            None,
            [(0.0, ty_min),
            (1.0, ty_min),
            (1.0, ty_max),
            (0.0, ty_min),
            (1.0, ty_max),
            (0.0, ty_max)]
        )

class Program:
    def __init__(self, vshader_src, fshader_src):
        self.vertex_shader = 0
        self.fragment_shader = 0
        self.program = 0
        self.load(vshader_src, fshader_src)

    def load(self, vshader_src, fshader_src):
        if self.vertex_shader:
            glDeleteShader(self.vertex_shader)

        if self.fragment_shader:
            glDeleteShader(self.fragment_shader)

        if self.program:
            glDeleteProgram(self.program)

        self.vertex_shader = self.__load_shader__(GL_VERTEX_SHADER, vshader_src)
        if self.vertex_shader == 0:
            exit()

        self.fragment_shader = self.__load_shader__(GL_FRAGMENT_SHADER, fshader_src)
        if self.fragment_shader == 0:
            exit()

        self.program = glCreateProgram()
        if self.program == 0:
            print('Failed to allocate GL program')
            exit()

        glAttachShader(self.program, self.vertex_shader)
        glAttachShader(self.program, self.fragment_shader)
        glLinkProgram(self.program)

        if glGetProgramiv(self.program, GL_LINK_STATUS, None) == GL_FALSE:
            glDeleteProgram(self.program)
            print('Failed to link GL program')
            exit()

    def __load_shader__(self, shader_type, source):
        shader = glCreateShader(shader_type)
        if shader == 0:
            return 0
        glShaderSource(shader, source)
        glCompileShader(shader)
        if glGetShaderiv(shader, GL_COMPILE_STATUS, None) == GL_FALSE:
            info_log = glGetShaderInfoLog(shader)
            print(info_log)
            glDeleteProgram(shader)
            return 0
        return shader

    def use(self, proj_mx=None, view_mx=None):
        glUseProgram(self.program)

    def getUniformLocation(self, name):
        return glGetUniformLocation(self.program, name)