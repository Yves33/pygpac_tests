#!/usr/bin/env python
from __future__ import division
from OpenGL.GL import *
import numpy as np
import textwrap
import ctypes
import traceback

import libgpac as gpac

fs_all_tx = textwrap.dedent("""\
    uniform sampler2D sTexture1; // luminance or rgb
    uniform sampler2D sTexture2; // interleaved uv or u
    uniform sampler2D sTexture3; // v
                            
    uniform int nbTextures;      //1=rgb, 2=nv12, 3=yuv 
    
    uniform float contrast;
    uniform float saturation;
    uniform float brightness;
                            
    varying vec2 vTexCoord;
    vec3 CSB(vec3 color){
        // Increase or decrease theese values to adjust r, g and b color channels seperately
        const float AvgLumR = 0.5;
        const float AvgLumG = 0.5;
        const float AvgLumB = 0.5;
	
	    const vec3 LumCoeff = vec3(0.2125, 0.7154, 0.0721);
	
        vec3 AvgLumin  = vec3(AvgLumR, AvgLumG, AvgLumB);
        vec3 brtColor  = color * brightness;
        vec3 intensity = vec3(dot(brtColor, LumCoeff));
        vec3 satColor  = mix(intensity, brtColor, saturation);
        vec3 conColor  = mix(AvgLumin, satColor, contrast);
	
	    return conColor;
    }
                            
    vec4 main_rgb(vec2 TexCoord){
        return texture2D(sTexture1, TexCoord);                  
    }
                            
    vec4 main_yuv(vec2 TexCoord) {
        float y = texture2D(sTexture1, TexCoord).r;
        float u = texture2D(sTexture2, TexCoord).r;
        float v = texture2D(sTexture3, TexCoord).r;
        u = u - 0.5;
        v = v - 0.5;
        vec3 rgb;
        rgb.r = y + (1.403 * v);
        rgb.g = y - (0.344 * u) - (0.714 * v);
        rgb.b = y + (1.770 * u);
        return vec4(rgb, 1.0);
    }
    
    vec4 main_nv12(vec2 TexCoord) {
        float y = texture2D(sTexture1, TexCoord).r;
        vec4 chroma = texture2D(sTexture2, TexCoord);
        float u = chroma.r;
        float v = chroma.a;
        u = u - 0.5;
        v = v - 0.5;
        vec3 rgb;
        rgb.r = y + (1.403 * v);
        rgb.g = y - (0.344 * u) - (0.714 * v);
        rgb.b = y + (1.770 * u);
        return vec4(rgb, 1.0);
    }
                                               
    void main(){
        vec4 res;
        switch(nbTextures){
            case 0:
                res = vec4(0.0,0.0,0.0,1.0);
                break;
            case 1:
                res = main_rgb(vTexCoord);
                break;
            case 2:
                res = main_nv12(vTexCoord);
                break;
            case 3:
                res = main_yuv(vTexCoord);
                break;
        }
        gl_FragColor = vec4(CSB(res.rgb),1.0);
    }
""")

vs_single_tx = textwrap.dedent("""\
    uniform mat4 uMVMatrix;
    uniform mat4 uPMatrix;
    uniform int nbTextures; //1=rgb, 2=nv12, 3=yuv
       
    attribute vec3 aVertex;
    attribute vec2 aTexCoord;
    
    varying vec2 vTexCoord;
    
    void main(){
       vTexCoord = aTexCoord;
       gl_Position = (uPMatrix * uMVMatrix)  * vec4(aVertex, 1.0);
    }
    """)

class Shape:
    def __init__(self, name):
        self.name = name
        self.vertex_vbo = None
        self.texcoord_vbo = None
        self.normal_vbo = None
        self.att_vertex = -1
        self.att_normal = -1
        self.att_texcoord = -1
        self.nb_points = 0
        self.np_texcoord = None

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

#texture helper - we use up to 3 opengl textures
class Texture:
    def __init__(self, pid):
        self.nb_textures=0
        self.texture1 = 0
        self.texture2=0
        self.texture3=0
        self.uTexture1=0
        self.uTexture2=0
        self.uTexture3=0
        self.pf=''
        self.w = 0
        self.h = 0
        self.pf = pid.get_prop('PixelFormat')
        self.pid=pid
        self.internal_tx=True
        self.format = GL_RGB
        self.clone_pck=None
        self.prog = Program(vs_single_tx, fs_all_tx)

    #update foramt
    def pid_update(self, pid):
        w = pid.get_prop('Width')
        h = pid.get_prop('Height')
        pf = pid.get_prop('PixelFormat')
        
        #we assume no stride
        if w==self.w and h==self.h and pf==self.pf:
            return

        self.w = w
        self.h = h
        self.pf = pf
        print('PID configured ' + str(self.w) + 'x' + str(self.h) + '@' + self.pf)
        self.nb_textures = 0
        #recreate program but don't create textures until we know if they are on GPU or in system memory
        if self.pf == 'yuv':
            self.nb_textures=3
            self.format = GL_RGB
        elif self.pf == 'nv12':
            self.nb_textures=2
            self.format = GL_RGB
        elif self.pf == 'rgb':
            self.nb_textures=1
            self.format = GL_RGB
        elif self.pf == 'rgba':
            self.nb_textures=1
            self.format = GL_RGBA
        else:
            raise Exception("Pixel format " + pf + " not supported in this demo")
        self.uTexture1 = self.prog.getUniformLocation("sTexture1")
        self.uTexture2 = self.prog.getUniformLocation("sTexture2")
        self.uTexture3 = self.prog.getUniformLocation("sTexture3")
        self.unbTextures = self.prog.getUniformLocation("nbTextures")


    def pck_update(self, pck):
        #textures are already on GPU
        if pck.frame_ifce_gl:
            reset=True #False                     ## YVES : reset=False works on GTX3060, but not on Quadro P2200 (have to force reset=True)

            #reset if needed
            if self.internal_tx:
                reset=True
                glDeleteTextures([self.texture1])
                if self.texture2:
                    glDeleteTextures([self.texture2])
                if self.texture3:
                    glDeleteTextures([self.texture3])
                self.internal_tx=False
                self.texture1=0
                self.texture2=0
                self.texture3=0

            tx = pck.get_gl_texture(0)
            self.texture1 = tx.id
            if reset:
                glBindTexture(GL_TEXTURE_2D, self.texture1)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

            if self.nb_textures>1:
                tx = pck.get_gl_texture(1)
                self.texture2 = tx.id
                if reset:
                    glBindTexture(GL_TEXTURE_2D, self.texture2)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                if self.nb_textures>2:
                    tx = pck.get_gl_texture(2)
                    self.texture3 = tx.id
                    if reset:
                        glBindTexture(GL_TEXTURE_2D, self.texture3)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            return

        #texture not in GPU, reset textures if needed
        if not self.internal_tx:
            self.internal_tx=True
            self.texture1=0
            self.texture2=0
            self.texture3=0

        #if planes are in decoder memory and not as packet, force packet reassembly using clone - no stride is used in this case
        #we keep the clone packet for later clone (avoids mem alloc/free )
        data = pck.data
        if pck.frame_ifce:
            self.clone_pck = pck.clone(self.clone_pck)
            data = self.clone_pck.data
        #otherwise we can directly use pck.data - WARNING: this example assumes no stride after each line

        if self.pf == 'yuv':
            #push Y plane
            if not self.texture1:
                self.texture1 = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture1)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glBindTexture(GL_TEXTURE_2D, self.texture1)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, self.w, self.h, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, data)

            #push U plane, get a sub-array without copy
            if not self.texture2:
                self.texture2 = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture2)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glBindTexture(GL_TEXTURE_2D, self.texture2)
            offset=self.w*self.h
            ar = data[offset:]
            glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, self.w/2, self.h/2, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, ar)

            #push C plane, get a sub-array without copy
            if not self.texture3:
                self.texture3 = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture3)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glBindTexture(GL_TEXTURE_2D, self.texture3)
            offset+=int(self.w*self.h/4)
            ar = data[offset:]
            glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, self.w/2, self.h/2, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, ar)
        elif self.pf == 'nv12':
            #push Y plane
            if not self.texture1:
                self.texture1 = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture1)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glBindTexture(GL_TEXTURE_2D, self.texture1)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE, self.w, self.h, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE, data)

            #push UV plane as luminance alpha, get a sub-array without copy
            if not self.texture2:
                self.texture2 = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture2)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glBindTexture(GL_TEXTURE_2D, self.texture2)
            offset=self.w*self.h
            ar = data[offset:]
            glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE_ALPHA, self.w/2, self.h/2, 0, GL_LUMINANCE_ALPHA, GL_UNSIGNED_BYTE, ar)
        else:
            if not self.texture1:
                self.texture1 = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture1)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glBindTexture(GL_TEXTURE_2D, self.texture1)
            glTexImage2D(GL_TEXTURE_2D, 0, self.format, self.w, self.h, 0, self.format, GL_UNSIGNED_BYTE, data)

    def activate(self):
        if self.uTexture1 == 0:
            self.uTexture1 = self.prog.getUniformLocation("sTexture1")
        if self.nb_textures>2:
            glActiveTexture(GL_TEXTURE0 + 2)
            glBindTexture(GL_TEXTURE_2D, self.texture3)
            glUniform1i(self.uTexture3, 2)
        if self.nb_textures>1:
            glActiveTexture(GL_TEXTURE0 + 1)
            glBindTexture(GL_TEXTURE_2D, self.texture2)
            glUniform1i(self.uTexture2, 1)
        glActiveTexture(GL_TEXTURE0 )
        glBindTexture(GL_TEXTURE_2D, self.texture1)
        glUniform1i(self.uTexture1, 0)
        glUniform1i(self.unbTextures,self.nb_textures)

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

        self.u_mv_mx = glGetUniformLocation(self.program, "uMVMatrix")
        self.u_proj_mx = glGetUniformLocation(self.program, "uPMatrix")

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

    def use(self, proj_mx, view_mx):
        glUseProgram(self.program)
        glUniformMatrix4fv(self.u_proj_mx, 1, GL_FALSE, proj_mx)
        glUniformMatrix4fv(self.u_mv_mx, 1, GL_FALSE, view_mx)

    def getUniformLocation(self, name):
        return glGetUniformLocation(self.program, name)

class DeadSink(gpac.FilterCustom):
    '''A filter that discards the packet it receives'''
    def __init__(self, session):
        gpac.FilterCustom.__init__(self, session,"DeadSink")
        self.paused=False
        self.set_max_pids(20)

    def configure_pid(self, pid, is_remove):
        if is_remove:
            return 0
        print('DeadSink: PID reconfigured'if pid in self.ipids else 'DeadSink: New PID !')
        if not pid in self.ipids:
            evt = gpac.FilterEvent(gpac.GF_FEVT_PLAY)
            pid.send_event(evt)
        return 0

    def process(self):
        if self.paused:
            return 0
        for pid in self.ipids:
            pck = pid.get_packet()
            if pck==None:
                break
            #print(pck.cts)
            pid.drop_packet()
        return 0
 
class ToGLRGB(gpac.FilterCustom):
    '''converts input buffer/textures to RGB frame buffer'''
    def __init__(self, session,**kwargs):
        gpac.FilterCustom.__init__(self, session,"toGPU")
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT_OUTPUT)
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT_OUTPUT)
        self.set_max_pids(1)
        self.texture=None
        self.dts=0
        ## now part of filter
        self.ortho_mx = ortho(-1, 1, 1, -1, -50, 50) # left right top bottom
        self.view_matrix = np.identity(4, dtype=np.float32)
        self.rect=Rectangle('rect', True)

    def _makebuffer(self,pid):
        if hasattr(self,"fbo_attachment"):
            if glIsTexture(self.fbo_attachment):
                glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,0,0)
                glDeleteTextures(1,[self.fbo_attachment])
            if glIsBuffer(self.fbo):
                glDeleteFramebuffers(1,[self.fbo])
        w=pid.get_prop("Width")
        h=pid.get_prop("Height")
        # create a minimal framebuffer with simple rgb color attachment with hard coded dimensions
        self.fbo=glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER,self.fbo)
        self.fbo_attachement=glGenTextures(1)
        self.pid = pid
        glBindTexture(GL_TEXTURE_2D, self.fbo_attachement)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,self.fbo_attachement,0)
        glBindTexture(GL_TEXTURE_2D,0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    #we accept input pids, we must configure them
    def configure_pid(self, pid, is_remove):
        if is_remove:
            return 0
        if pid in self.ipids:
            if pid.get_prop("width")!=self.width or pid.get_prop("Height")!=self.height:
                print("toGPU: Resizing fbo")
                self._makebuffer(pid)
        else:
            print('toGPU: New PID !')
            self._makebuffer(pid)
            opid = self.new_pid()
            pid.opid = opid
            pid.opid.copy_props(pid)
            self.texture = Texture(pid)
        self.texture.pid_update(pid)

        #get width, height, stride and pixel format - get_prop may return None if property is not yet known
        #but this should not happen for these properties with raw video, except StrideUV which is None for non (semi) planar YUV formats
        self.width = pid.get_prop('Width')
        self.height = pid.get_prop('Height')
        self.pixfmt = pid.get_prop('PixelFormat')
        self.stride = pid.get_prop('Stride')
        self.stride_uv = pid.get_prop('StrideUV')
        pid.opid.set_prop('Width',self.width)
        pid.opid.set_prop('Height',self.height)
        pid.opid.set_prop("StreamType", "Video")
        pid.opid.set_prop("CodecID", "raw")
        pid.opid.set_prop("fboID", self.fbo, gpac.GF_PROP_UINT)
        pid.opid.set_prop("texID", self.fbo_attachement, gpac.GF_PROP_UINT)
        return 0

    def process(self):
        for pid in self.ipids:
            pck = pid.get_packet()
            if pck==None:
                if pid.eos:
                    pid.opid.eos = True
                break
            try:
                self.texture.pck_update(pck)
            except:
                traceback.print_exc()
                fs.abort()
            self.dts=pck.dts
            ## as we cannot set custom packet property
            ## we send a packet with data consisting of fbo and fbo_attachment
            pck_data=np.array([self.fbo,self.fbo_attachement], dtype=np.uint8)
            opck=pid.opid.new_pck(pck_data.nbytes)
            opck.copy_props(pck)
            np.copyto(opck.data, pck_data)
            opck.set_prop("fboID", self.fbo, gpac.GF_PROP_UINT)
            opck.set_prop("texID", self.fbo_attachement, gpac.GF_PROP_UINT)
            opck.send()
            pid.drop_packet()
        self.render()
        return 0
    
    def render(self):
        glBindFramebuffer(GL_FRAMEBUFFER,self.fbo)
        glViewport(0,0,self.width,self.height)
        self.texture.prog.use(self.ortho_mx, self.view_matrix)
        self.texture.activate()
        self.rect.draw(self.texture.prog)
        glBindFramebuffer(GL_FRAMEBUFFER,0)

class FromGLRGB(gpac.FilterCustom):
    def __init__(self, session):
        gpac.FilterCustom.__init__(self, session,"GPU2CPU")
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT_OUTPUT)  ## modified to be GF_CAPS_INPUT_OUTPUT
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT_OUTPUT)
        self.set_max_pids(1)

    #we accept input pids, we must configure them
    def configure_pid(self, pid, is_remove):
        if is_remove:
            return 0
        if pid in self.ipids:
            print('PID reconfigured')
        else:
            print('New PID !')
            opid = self.new_pid()
            pid.opid = opid
            pid.opid.copy_props(pid)

        #get width, height, stride and pixel format - get_prop may return None if property is not yet known
        #but this should not happen for these properties with raw video, except StrideUV which is None for non (semi) planar YUV formats
        self.width = pid.get_prop('Width')
        self.height = pid.get_prop('Height')
        try:
            self.pixfmt = pid.get_prop('PixelFormat')  ## <-assumes that the bug in libgpac.py@2461 is corrected
        except:
            self.pixfmt= 'rgb'
        self.stride = pid.get_prop('Stride')
        self.stride_uv = pid.get_prop('StrideUV')
        pid.opid.set_prop('Width',self.width)
        pid.opid.set_prop('Height',self.height)
        pid.opid.set_prop('PixelFormat','rgb')
        pid.opid.set_prop('Stride',0)
        pid.opid.set_prop('StrideUV',0)
        pid.opid.set_prop("CodecID", "raw")
        pid.opid.set_prop("StreamType", "Video")
        return 0

    def process(self):
        for pid in self.ipids:
            pck = pid.get_packet()
            if pck==None:
                if pid.eos:
                    pid.opid.eos = True
                break
            ##########################################
            ## fetching pixels from the GL
            pck_data=np.frombuffer(pck.data,dtype=np.uint8)
            fbo=pck_data[0]
            texid=pck_data[1]
            fbo = pck.get_prop("fboID")
            if not fbo:
                print('fboID not set !')
                fbo=pck_data[0]
            glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo)
            cpupixels=glReadPixels(0,0,self.width,self.height,GL_RGB,GL_UNSIGNED_BYTE)
            glBindFramebuffer(GL_READ_FRAMEBUFFER,0)
            opck=pid.opid.new_pck(self.width*self.height*3)
            opck.copy_props(pck)
            np.copyto(opck.data,np.frombuffer(cpupixels,dtype=np.uint8))
            opck.send()
            pid.drop_packet()
        return 0
