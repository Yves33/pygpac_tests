#!/usr/bin/env python
from OpenGL.GL import *
import numpy as np
import textwrap
import traceback

import libgpac as gpac
import time
fs_all_tx = textwrap.dedent("""\
    #version 130
    uniform sampler2D sTexture1; // luminance or rgb
    uniform sampler2D sTexture2; // interleaved uv or u
    uniform sampler2D sTexture3; // v
                            
    uniform int nbTextures;      //1=rgb, 2=nv12, 3=yuv 
    
    uniform float contrast;
    uniform float saturation;
    uniform float brightness;
                            
    //varying vec2 vTexCoord;  //deprecated in GL440
    in vec2 vTexCoord;
    out vec4 out_FragColor;
                            
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
        out_FragColor = vec4(CSB(res.rgb),1.0);
    }
""")

vs_single_tx = textwrap.dedent("""\
    #version 130                      
    uniform mat4 uMVMatrix;
    uniform mat4 uPMatrix;
    uniform int nbTextures; //1=rgb, 2=nv12, 3=yuv
    
    //varying vec2 vTexCoord;  //deprecated in GL440
    out vec2 vTexCoord;
    
    void main(){
        const vec2 vertices[4] = vec2[4](vec2(-0.5,  0.5),
                                        vec2( 0.5,  0.5),
                                        vec2( 0.5, -0.5),
                                        vec2(-0.5, -0.5));
        // Index into our array using gl_VertexID
        vec2 flip=vec2(1.0,1.0);
        vTexCoord=vertices[gl_VertexID]*flip+vec2(0.5,0.5);                       
        gl_Position = (uPMatrix * uMVMatrix)*vec4(2*vertices[gl_VertexID],1.0,1.0);
    }
    """)

#texture helper - we use up to 3 opengl textures
class Texture:
    def __init__(self, pid):
        self.nb_textures=0
        self.texture1 = 0
        self.texture2=0
        self.texture3=0
        self.w = 0
        self.h = 0
        self.pf = pid.get_prop('PixelFormat')
        self.internal_tx=True
        self.format = GL_RGB
        self.clone_pck=None

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
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, self.texture1)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

            if self.nb_textures>1:
                tx = pck.get_gl_texture(1)
                self.texture2 = tx.id
                if reset:
                    glActiveTexture(GL_TEXTURE1)
                    glBindTexture(GL_TEXTURE_2D, self.texture2)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                if self.nb_textures>2:
                    tx = pck.get_gl_texture(2)
                    self.texture3 = tx.id
                    if reset:
                        glActiveTexture(GL_TEXTURE2)
                        glBindTexture(GL_TEXTURE_2D, self.texture3)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            return

        #texture not in GPU, reset textures if needed
        #should never happen is glpush is inserted before
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

class DeadSink(gpac.FilterCustom):
    '''
    A filter that discards the packet it receives.
    '''
    def __init__(self, session):
        gpac.FilterCustom.__init__(self, session,"DeadSink")
        self.paused=False
        self.set_max_pids(20)
        self.fs=session

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
            pid.drop_packet()
        return 0

def _adjust_size(pid_size,req_size):
    if (req_size==1.0) or req_size==(-1,-1):
        return pid_size
    elif isinstance(req_size, float) or isinstance (req_size, int):
        assert (req_size!=0)
        return (int(pid_size[0]*req_size),int(pid_size[1]*req_size))
    elif isinstance (req_size, tuple):
        ar=pid_size[0]/pid_size[1]
        if req_size[1]==-1:
            return (req_size[0],int(req_size[0]/ar))
        elif req_size[0]==-1:
            return (int(req_size[1]*ar),req_size[1])
        else:
            return req_size
 
class ToGLRGB(gpac.FilterCustom):
    '''
    Converts input buffer/textures to RGB frame buffer
    '''
    def __init__(self, session,**kwargs):
        gpac.FilterCustom.__init__(self, session,"toGPU")
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT_OUTPUT)
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT_OUTPUT)
        self.set_max_pids(1)
        self.tex_helper=None
        self.dts=0
        self.fs=session
        ## now part of filter
        self.program=Program(vs_single_tx, fs_all_tx)
        self.size_request=kwargs.pop("size",1.0)
        self.pid_props=kwargs.pop("pid_props",dict())
        self.mirror=kwargs.pop("mirror",False)
        self.mirror_viewport=kwargs.pop("mirror_viewport",(-1,-1,-1,-1))
        if self.mirror and (self.mirror_viewport[2]<=0 or self.mirror_viewport[3]<=0):
            print("error: must specify valid viewport to use mirror option")
        ## program uniforms
        self.ortho_mx = ortho(-1, 1, 1, -1, -50, 50) # left right top bottom
        self.view_matrix = np.identity(4, dtype=np.float32)
        self.saturation=1.0
        self.contrast=1.0
        self.brightness=1.0
        ## we're using glVertexID to render, howver, the specs makes it mandatory to have one vao bound (empty vao is ok)
        self.vao=glGenVertexArrays(1)

    def _make_buffer(self,w,h):
        if hasattr(self,"fbo_attachment"):
            if glIsTexture(self.fbo_attachment):
                glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,0,0)
                glDeleteTextures(1,[self.fbo_attachment])
            #if glIsBuffer(self.depth_attachment):
            #    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, 0)
            if glIsBuffer(self.fbo):
                glDeleteFramebuffers(1,[self.fbo])
        self.fbo=glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER,self.fbo)
        self.fbo_attachement=glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.fbo_attachement)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,self.fbo_attachement,0)
        ## if a depth buffer is required. don't forget to also delete the attachment above
        #self.depth_attachment=glGenRenderbuffers(1)
        #glBindRenderbuffer(GL_RENDERBUFFER, self.depth_attachment)
        #glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, w, h)
        #glBindRenderbuffer(GL_RENDERBUFFER, 0)
        #glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_attachment)
        glBindTexture(GL_TEXTURE_2D,0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    #we accept input pids, we must configure them
    def configure_pid(self, pid, is_remove):
        if is_remove:
            return 0
        if pid in self.ipids:
            w=pid.get_prop("Width")
            h=pid.get_prop("Height")
            if w!=self.i_width or h!=self.i_height:
                self.o_width,self.o_height=_adjust_size((w,h),self.size_request)#w//2,h//2
                print("toGPU: Resizing fbo", self.o_width,self.o_height)
                self._make_buffer(self.o_width,self.o_height)
        else:
            w=pid.get_prop("Width")
            h=pid.get_prop("Height")
            self.o_width,self.o_height=_adjust_size((w,h),self.size_request)#w//2,h//2
            print("toGPU: New PID !", self.o_width,self.o_height)
            self._make_buffer(self.o_width,self.o_height)
            opid = self.new_pid()
            pid.opid = opid
            pid.opid.copy_props(pid)
            self.tex_helper = Texture(pid)
        self.tex_helper.pid_update(pid)

        #get width, height, stride and pixel format - get_prop may return None if property is not yet known
        #but this should not happen for these properties with raw video, except StrideUV which is None for non (semi) planar YUV formats
        self.i_width = pid.get_prop('Width')
        self.i_height = pid.get_prop('Height')
        self.i_pixfmt = pid.get_prop('PixelFormat')
        self.i_stride = pid.get_prop('Stride')
        self.i_stride_uv = pid.get_prop('StrideUV')
        pid.opid.set_prop('Width',self.o_width)
        pid.opid.set_prop('Height',self.o_height)
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
                self.tex_helper.pck_update(pck)
            except:
                traceback.print_exc()
                self.fs.abort()
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
        glViewport(0,0,self.o_width,self.o_height)

        self.program.use()
        glUniform1i(self.program.getUniformLocation("nbTextures"),self.tex_helper.nb_textures)
        if self.tex_helper.nb_textures>2:
            glActiveTexture(GL_TEXTURE0 + 2)
            glBindTexture(GL_TEXTURE_2D, self.tex_helper.texture3)
            glUniform1i(self.program.getUniformLocation("sTexture3"), 2)
        if self.tex_helper.nb_textures>1:
            glActiveTexture(GL_TEXTURE0 + 1)
            glBindTexture(GL_TEXTURE_2D, self.tex_helper.texture2)
            glUniform1i(self.program.getUniformLocation("sTexture2"), 1)
        glActiveTexture(GL_TEXTURE0 )
        glBindTexture(GL_TEXTURE_2D, self.tex_helper.texture1)
        glUniform1i(self.program.getUniformLocation("sTexture1"), 0)
        glUniformMatrix4fv(self.program.getUniformLocation("uPMatrix"), 1, GL_FALSE, self.ortho_mx)
        glUniformMatrix4fv(self.program.getUniformLocation("uMVMatrix"), 1, GL_FALSE, self.view_matrix)
        glUniform1f(self.program.getUniformLocation("brightness"),self.brightness)
        glUniform1f(self.program.getUniformLocation("saturation"),self.saturation)
        glUniform1f(self.program.getUniformLocation("contrast"),self.contrast)
        glUniformMatrix4fv(self.program.getUniformLocation("uMVMatrix"), 1, GL_FALSE, self.view_matrix*scale(1.0,1.0,1.0))
        glBindVertexArray(self.vao)
        glDrawArrays(GL_QUADS, 0, 4)
        if self.mirror:
            glBindFramebuffer(GL_FRAMEBUFFER,0)
            glViewport(*self.mirror_viewport)
            glUniform1i(self.program.getUniformLocation("nbTextures"),1)
            glUniform1f(self.program.getUniformLocation("brightness"),1.0)
            glUniform1f(self.program.getUniformLocation("saturation"),1.0)
            glUniform1f(self.program.getUniformLocation("contrast"),1.0)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.fbo_attachement)
            glUniform1i(self.program.getUniformLocation("sTexture1"), 0)
            glBindVertexArray(self.vao)
            glDrawArrays(GL_QUADS, 0, 4)
        glBindFramebuffer(GL_FRAMEBUFFER,0)
        glBindVertexArray(0)

class FromGLRGB(gpac.FilterCustom):
    '''
    Converts rgb texture on gpu to normal packets 
    '''
    def __init__(self, session):
        gpac.FilterCustom.__init__(self, session,"GPU2CPU")
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT_OUTPUT)  ## modified to be GF_CAPS_INPUT_OUTPUT
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT_OUTPUT)
        self.set_max_pids(1)
        self.fs=session

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

class FPSCounter(gpac.FilterCustom):
    '''
    Counts number of packets processed over 1 second period
    '''
    def __init__(self, session,**kwargs):
        gpac.FilterCustom.__init__(self, session,"FPSCounter")
        self.sink=kwargs.pop("sink",False)
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.fps=0
        self._last_time=0
        self._pck_cnt=0
        self.fs=session

    def configure_pid(self, pid, is_remove):
        if pid not in self.ipids:
            #pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_PLAY))
            if not self.sink:
                ## if we are not declared as a sink, then we should have one controller/pid
                assert(len(self.ipids)==0)
                pid.opid = self.new_pid()
                pid.opid.copy_props(pid)
        return 0

    def process(self):
        for pid in self.ipids:
            pck = pid.get_packet()
            if pck==None:
                if pid.eos:
                    pid.opid.eos = True
                break
            self._pck_cnt+=1
            if time.perf_counter()>self._last_time+1:
                self.fps=self._pck_cnt
                self._pck_cnt=0
                self._last_time=time.perf_counter()
            pid.opid.forward(pck)
            pid.drop_packet()
        return 0
    
class PidProp:
    def __init__(self):
        pass
    def on_prop_enum(self,prop_name,propval):
      print(prop_name,propval)

class Controller(gpac.FilterCustom):
    '''
    Controls playback state of input pid
    '''
    def __init__(self, session,**kwargs):
        gpac.FilterCustom.__init__(self, session,"PlayPauseController")
        self.sink=kwargs.pop("sink",False)
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.paused=False
        self.step_mode=False
        self.seeking=False
        self.dts=0
        self.timescale=1
        self.fs=session

    def configure_pid(self, pid, is_remove):
        if pid not in self.ipids:
            #pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_PLAY))
            if not self.sink:
                ## if we are not declared as a sink, then we should have one controller/pid
                assert(len(self.ipids)==0)
                pid.opid = self.new_pid()
                pid.opid.copy_props(pid)
            self.timescale=pid.timescale
        return 0

    def toggle(self):
        self.resume() if self.paused else self.pause()

    def pause(self):
        if not self.paused:
            for pid in self.ipids:
                pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_PAUSE))
        self.paused=True
        self.step_mode=True

    def resume(self):
        if self.paused:
            for pid in self.ipids:
                pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_RESUME))
        self.paused=False
        self.step_mode=False

    def stop(self):
        for pid in self.ipids:
            pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_STOP))

    def step(self):
        if self.paused:
            self.paused=False

    def seek(self,time_in_s):
        self._paused_after_seek=self.paused
        for pid in self.ipids:
            pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_STOP))
            evt=gpac.FilterEvent(gpac.GF_FEVT_PLAY)
            evt.play.start_range=min(time_in_s,self.duration_s)
            pid.send_event(evt)
        self.paused=False
        self.seeking=True

    def process(self):
        if self.paused and not self.seeking:
            self.reschedule(10000)  ## warn ligbpac that we're doing nothing
            return 0
        ## otherwise process packet normally
        for pid in self.ipids:
            pck = pid.get_packet()
            if pck==None:
                if pid.eos:
                    pid.opid.eos = True
                break
            self.dts=pck.dts
            if self.seeking:
                self.seeking=False                  ## self.seeking must remain till we got a packet
            if not self.sink:
                pid.opid.forward(pck)
            pid.drop_packet()
        if self.step_mode:
            self.paused=True
        return 1
    
    @property
    def duration_s(self):
        d=self.ipids[0].get_prop("Duration")
        return float(d.num/d.den)
        
    @property
    def position_s(self):
        return self.dts/self.timescale
        
class RateLimit:
    def __init__(self,dt):
        self.dt=int(dt)
        self.current=-1

    def fire(self):
        if time.perf_counter_ns()-self.current>=self.dt:
            self.current=time.perf_counter_ns()
            return True
        return False
