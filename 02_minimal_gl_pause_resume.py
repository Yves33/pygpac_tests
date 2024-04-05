#!/usr/bin/env python
from __future__ import division
from OpenGL.GL import *
import pygame

from glgpac import *         ## utility routines and filters. toGPU, Deadsink, ...
from imgui.integrations.pygame import PygameRenderer
import imgui

from itertools import pairwise
    
class PlayPauseController(gpac.FilterCustom):
    '''
    Controls playback state of input pid
    '''
    def __init__(self, session,**kwargs):
        gpac.FilterCustom.__init__(self, session,"PlayPauseController")
        self.sink=kwargs.pop("sink",False)
        self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT if self.sink else gpac.GF_CAPS_INPUT_OUTPUT)
        self.prevent_blocking(True)  ## does not change the 100000 consecutive process issue. Is there something I misunderstand?
        self.paused=False
        self.dts=0
        self.timescale=1

    def configure_pid(self, pid, is_remove):
        if pid not in self.ipids:
            pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_PLAY))
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

    def resume(self):
        if self.paused:
            for pid in self.ipids:
                pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_RESUME))
        self.paused=False

    def stop(self):
        for pid in self.ipids:
            pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_STOP))

    def step(self):
        if self.paused:
            self.paused=False
            self.process()
            self.paused=True

    def process(self):
        if self.paused:
            '''
            ISSUE 1
            gpac stops the session  after 100000 process() calls (may take a while - quite fast using nvdec)
            [Filter] PlayPauseController (idx 6) not responding properly: 100000 consecutive process with no packet discarded or sent, but x packets pending
                      discarding all inputs and notifying end of stream on all outputs
            HOWTO:
            + start program, click play then pause, and wait...
            + issue does not appear if PlayPauseController is declared with GF_CAPS_INPUT instead of GF_CAPS_INPUT_OUTPUT,
            but this  prevents having several independant controllers (?) for multiple src
            + disabling check in src/filter.c@2879 prevents the issue, without obvious side effect (for this simple exemple).
            '''
            return 0
        ## otherwise process packet normally. see however comment
        for pid in self.ipids:
            pck = pid.get_packet()
            if pck==None:
                if pid.eos:
                    pid.opid.eos = True
                break
            self.dts=pck.dts
            if not self.sink:
                pid.opid.forward(pck)
            pid.drop_packet()
        return 0
    
    @property
    def duration_s(self):
        d=self.ipids[0].get_prop("Duration")
        return float(d.num/d.den)
        
    @property
    def position_s(self):
        return self.dts/self.timescale

import time
class RateLimit:
    def __init__(self,dt):
        self.dt=int(dt)
        self.current=-1

    def fire(self):
        if time.perf_counter_ns()-self.current>=self.dt:
            self.current=time.perf_counter_ns()
            return True
        return False

if __name__=='__main__':
    ## initialize pygame and imgui
    width, height = 1280, 720
    pygame.init()
    pygame.display.set_mode((width, height), pygame.DOUBLEBUF|pygame.OPENGL|pygame.HWSURFACE, 0)
    imgui.create_context()
    impl = PygameRenderer()
    io = imgui.get_io()
    io.fonts.add_font_default()
    io.display_size = width,height

    ## initialize gpac
    gpac.init(0)
    gpac.set_args(["",
                    "-js-dirs=/opt/gpac/share/gpac/scripts/jsf",
                    "-cfg=temp:cuda_lib=/usr/lib64/libcuda.so",
                    "-cfg=temp:cuvid_lib=/usr/lib64/libnvcuvid.so",
                    "-logs=filter@info:container@debug"])
    fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")
    fs.external_opengl_provider()

    ## setup filter list
    in_chain={
        'src':fs.load_src("./video.mp4"),
        'dec':fs.load("ffdec"),                     ## issue appears with "nvdec" & "ffdec"
        'reframer':fs.load("reframer:rt=on"),       ## issue appears with or without reframer
        'ctl':PlayPauseController(fs,sink=False),    ## issue appears wherever controller is inserted.See also issue 2 in step()
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs),
        #'ctl':PlayPauseController(fs,sink=False),  ## issue appears wherever controller is inserted.See also issue 2 in step()
        #'ctl':PlayPauseController(fs,sink=True),   ## issue does not appear if controller is a sink, but would not allow multiple independant controllers.
        'dst':DeadSink(fs)                         ## a sink is required
        }
    
    for f1,f2 in pairwise(in_chain.values()):
        f2.set_source(f1)

    ctl=in_chain["ctl"]
    tgt=in_chain["togpu"]

    running=True
    ctl.pause()
    brightness=1.0
    changed=False
    stepped=False
    ratelimit=RateLimit(0*int(1e6)) ## in ns
    while running:
        '''
        ISSUE 1
        conditionnally running fs.run() (if not ctl.paused:fs.run()) prevents the "100000 consecutive process issue" (obviously), but
        + I may need several streams with independant controllers
        '''
        if ratelimit.fire():
            fs.run()
            if fs.last_task:
                break
        '''
        QUESTION
        when controller is paused, process() is not called and updating uniforms has no effect
        iterating through custom filters to render, do we have a guarantee that the order will be the same as in fs.run(), 
        even for complex graphs (multiple sources)?
        '''
        if ctl.paused and (changed or stepped):
            for f in fs._filters:
                if hasattr(f,'render'):
                    #f.process() ## <=if ToGLRGB is inserted before PlayPauseController
                    f.render() ## <=if ToGLRGB is inserted after PlayPauseController
            changed=False
            stepped=False
        
        ## pygame event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                fs.abort(gpac.GF_FS_FLUSH_ALL if "enc_v" in in_chain.keys() else 0)  ## don't need gpac.GF_FS_FLUSH_ALL as we are not recording
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_p:
                    ctl.toggle()
            impl.process_event(event)
        impl.process_inputs()

        ## gui setup
        imgui.new_frame()

        imgui.begin("Free stream", True)
        wwidth = imgui.get_window_content_region_max()[0]-2*imgui.get_style().frame_padding.x 
        imgui.image(tgt2.fbo_attachement, wwidth,wwidth*tgt2.height//tgt2.width, uv0=(0,1),uv1=(1,0),border_color=(0, 0, 0, 1))
        imgui.end()

        imgui.begin("Controlled stream", True)
        wwidth = imgui.get_window_content_region_max()[0]-2*imgui.get_style().frame_padding.x 
        imgui.image(tgt.fbo_attachement, wwidth,wwidth*tgt.height//tgt.width, uv0=(0,1),uv1=(1,0),border_color=(0, 0, 0, 1))
        if imgui.button("Play" if ctl.paused else "Pause"):
            ctl.toggle()
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, not ctl.paused)
        imgui.push_style_var(imgui.STYLE_ALPHA, imgui.get_style().alpha *  [0.5,1.0][ctl.paused])
        imgui.same_line()
        if imgui.button("Step"):
            ctl.step()
            print("Control : ",ctl.dts,"Renderer : ",tgt.dts)
            stepped=True
        imgui.internal.pop_item_flag()
        imgui.pop_style_var()
        imgui.same_line()
        imgui.text(f"dts: {ctl.dts:008d} {ctl.position_s:5.2f}")
        changed, brightness=imgui.slider_float("Brightness",brightness,0,3.0)
        glUseProgram(tgt.texture.prog.program)
        glUniform1f(tgt.texture.prog.getUniformLocation("brightness"),brightness)
        glUniform1f(tgt.texture.prog.getUniformLocation("saturation"),1.0)
        glUniform1f(tgt.texture.prog.getUniformLocation("contrast"),1.0)
        imgui.end()

        ## render loop
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        imgui.render()
        impl.render(imgui.get_draw_data())
        pygame.display.flip()
    fs.print_graph()
