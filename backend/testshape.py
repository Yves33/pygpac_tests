#!/usr/bin/env python
from OpenGL.GL import *
import libgpac as gpac
from pygpacfilters import Program         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...

class TestShape:
    vtx='''
    #version 130
    void main(){
        const vec2 vertices[3] = vec2[3](vec2(-0.0,  0.25), vec2( 0.15,  -0.2), vec2( -0.15, -0.2));          
        gl_Position = vec4(vertices[gl_VertexID],1.0,1.0);
        }
    '''
    frag='''
    #version 130
    out vec4 out_FragColor;
    void main(){
        out_FragColor=vec4(1.0,0.0,0.0,0.0);
        }
    '''
    def __init__(self):
        self.program=Program(self.vtx,self.frag)
        self.vao=glGenVertexArrays(1)

    def draw(self):
        self.program.use()
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES,0,3)
        glBindVertexArray(0)

class Shaper(gpac.FilterCustom):
    '''
    draws red triangle
    '''
    def __init__(self, session,**kwargs):
        gpac.FilterCustom.__init__(self, session,"FPSCounter")
        self.sink=kwargs.pop("sink",False)
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.shape=TestShape()
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
            pid.opid.forward(pck)
            pid.drop_packet()
        self.shape.draw()
        return 0