#!/usr/bin/env python
from __future__ import division
from OpenGL.GL import *
import pygame

from glgpac import *         ## utility routines and filters. toGPU, Deadsink, ...
from imgui.integrations.pygame import PygameRenderer
import imgui


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
        self.seeking=False
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
        self._pause_after_seek=False

    def stop(self):
        for pid in self.ipids:
            pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_STOP))

    def step(self):
        #run for one frame and pause. won't run if the controller is not in paused state
        if self.paused:
            self.paused=False
            self.process()
            self.paused=True

    def seek(self,time_in_s):
        self._paused_after_seek=self.paused
        for pid in self.ipids:
            pid.send_event(gpac.FilterEvent(gpac.GF_FEVT_STOP))
            evt=gpac.FilterEvent(gpac.GF_FEVT_PLAY)
            evt.play.start_range=min(time_in_s,self.duration_s)
            #evt.hw_buffer_reset=True
            #evt.play.end_range=self.duration_s
            pid.send_event(evt)
        self.paused=False ## as we just sent an event.play!
        self.seeking=True
        if self._paused_after_seek:
            while self.seeking:
                '''
                ISSUE 2
                if we are in paused mode, image will not update after seek completed. 
                we need to let the session run till we get one packet and update image.
                + using self._session.run() works, but may(?) advance other concurrent streams even if they are in paused state
                '''
                self._session.run() ## can take up to >500 iterations. depending on gop size?
                ##self.process() does not work as seek event is only processed in next fs.run() is called
                '''
                ISSUE 3 
                using nvdec instead of ffdec, the first frames returned after seek are not at appropriate times, 
                most surely due to some buffering mechanism.
                for instance, using play->pause->seek(xx)->step->step, the first frames do not have appropriate dts/positions
                (on my computer, 6 frames before reaching correct frame)
                Solution(s): 
                + wait for pck.dts to be in correct range?
                + flush nvdec output buffer->How?
                '''
            self.pause()

    def process(self):
        if self.paused and not self.seeking:
            '''
            ISSUE 1
            gpac stops the session  after 100000 process() calls (may take a while)
            [Filter] PlayPauseController (idx 6) not responding properly: 100000 consecutive process with no packet discarded or sent, but x packets pending
                      discarding all inputs and notifying end of stream on all outputs
            HOWTO:
            + start program, click play then pause, and wait...
            + issue does not appear if PlayPauseController is declared with GF_CAPS_INPUT instead of GF_CAPS_INPUT_OUTPUT,
            but this  prevents having several independant controllers (?)
            + disabling check in src/filter.c@2879 prevents the issue, without obvious side effect (for this simple exemple).
            '''
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
                self.seeking=False                  ## self seeking must remain till we got a packet
            if not self.sink:
                pid.opid.forward(pck)
            pid.drop_packet()
        return 1
    
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
        'dec':fs.load("nvdec"),                  ## seeking issue (extra frames) appears with "nvdec" but not ffdec
        'reframer':fs.load("reframer:rt=off"),    ## issue appears with or without reframer
        'ctl':Controller(fs),                   ## issue appears wherever controller is inserted
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs),
        #'ctl':Controller(fs,sink=False),           ## issue appears wherever controller is inserted
        'dst':DeadSink(fs)                       ## a sink is required
        }
    for f1,f2 in zip(in_chain.values(),list(in_chain.values())[1:]):
        f2.set_source(f1)
    ctl=in_chain["ctl"]
    tgt=in_chain["togpu"]

    ratelimit=RateLimit(1*int(1e6))
    running=True
    ctl.pause()
    brightness=1.0
    changed=False
    stepped=False
    seekto=0
    while running:
        '''
        due to "100000 consecutive process" issue, we need to limit processing rate
        '''
        if ratelimit.fire():
            fs.run()
            if fs.last_task:
                break
        if ctl.paused and (changed or stepped):
            for f in fs._filters:
                if hasattr(f,'render'):
                    f.process() ## <=if ToGLRGB is inserted before PlayPauseController
                    #f.render() ## <=if ToGLRGB is inserted after PlayPauseController
            changed=False
            stepped=False
        
        ## pygame event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                ctl.resume()
                fs.abort()  ## don't need gpac.GF_FS_FLUSH_ALL as we are not recording
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_p:
                    ctl.toggle()
            impl.process_event(event)
        impl.process_inputs()

        ## gui setup
        imgui.new_frame()
        imgui.begin("Texture window", True)
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
        ## ctl.dts is delayed 1 fame for some unknown reason
        imgui.text(f"dts: {ctl.dts:008d} {ctl.position_s:5.2f}")
        _seek, seekto=imgui.input_float("Seek to",seekto,0,0,format='%.3f',flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
        if _seek:
            ctl.seek(seekto)
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
