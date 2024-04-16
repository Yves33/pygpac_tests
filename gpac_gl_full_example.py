#!/usr/bin/env python
from __future__ import division
from OpenGL.GL import *
import pygame

from pygpacfilters import *         ## utility routines and filters. toGPU, Deadsink, ...
from imgui.integrations.pygame import PygameRenderer
import imgui

from itertools import pairwise

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
    VIDEOSRC="../../video.mp4"
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
        'src':fs.load_src(VIDEOSRC),
        'dec':fs.load("ffdec"), 
        'reframer':fs.load("reframer:rt=on"),
        'ctl':Controller(fs),
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs),
        'dst':DeadSink(fs)
        }
    for f1,f2 in zip(in_chain.values(),list(in_chain.values())[1:]):
        f2.set_source(f1)
    ctl=in_chain["ctl"]
    tgt=in_chain["togpu"]

    ratelimit=RateLimit(1*int(1e6))
    running=True
    ctl.pause()
    brightness=1.0
    contrast=1.0
    saturation=1.0
    recording=False
    changed=False
    seekto=0
    while running:
        if ratelimit.fire():
            fs.run()
            if fs.last_task:
                break
        if ctl.paused and (changed):
            for f in fs._filters:
                if hasattr(f,'render'):
                    f.render() ## safer
            changed=False
        
        ## pygame event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                ctl.resume()
                fs.abort(gpac.GF_FS_FLUSH_ALL if recording else 0)  ## don't need gpac.GF_FS_FLUSH_ALL as we are not recording
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_p:
                    ctl.toggle()
                elif event.key == pygame.K_r:
                    in_chain["dst"].remove()
            impl.process_event(event)
        impl.process_inputs()

        ## gui setup
        imgui.new_frame()
        imgui.begin("Texture window", True)
        wwidth = imgui.get_window_content_region_max()[0]-2*imgui.get_style().frame_padding.x 
        imgui.image(tgt.fbo_attachement, wwidth,wwidth*tgt.o_height//tgt.o_width, uv0=(0,1),uv1=(1,0),border_color=(0, 0, 0, 1))
        if imgui.button("Play" if ctl.paused else "Pause"):
            ctl.toggle()
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, not ctl.paused)
        imgui.push_style_var(imgui.STYLE_ALPHA, imgui.get_style().alpha *  [0.5,1.0][ctl.paused])
        imgui.same_line()
        if imgui.button("Step"):
            ctl.step()
            print("Control : ",ctl.dts,"Renderer : ",tgt.dts)
        imgui.internal.pop_item_flag()
        imgui.pop_style_var()
        imgui.same_line()
        imgui.text(f"dts: {ctl.dts:008d} {ctl.position_s:5.2f}")
        _seek, seekto=imgui.input_float("Seek to",seekto,0,0,format='%.3f',flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
        if _seek:
            ctl.seek(seekto)
        imgui.new_line()
        u1, tgt.brightness=imgui.slider_float("Brightness",tgt.brightness,0,3.0)
        u2, tgt.saturation=imgui.slider_float("Saturation",tgt.saturation,0,3.0)
        u3, tgt.contrast=imgui.slider_float("Contrast",tgt.contrast,0,3.0)
        changed=u1 or u2 or u3 
        ## add instant record button
        toggle,recording=imgui.checkbox("Record",recording)
        if toggle:
            if recording:
                print("start recording")
                '''
                removing in_chain["dst"] now works, but resets the stream to the first frame
                wherever remove is called (before of after inserting filters).
                + is it an intended or accidental behavior (I guess it's because the chain transiently has no sink at all)
                to overcome this behavior, I see three solutions:
                1 - keep DeadSink in filter chain. for now it just works. no problem (!), but we have two sinks.
                2 - remove DeadSink only after new graph is fully resolved and linked (what 'r' key does here), but that should be done automatically             
                3 - save current position, remove DeadSink and seek to saved position before recording. However, seeking immediately does not work, as the filter graph is not yet fully reolved

                =>question: is there a way to get informed that gpac has ended graph construction?
                '''
                rec_start=in_chain["ctl"].position_s
                #in_chain["dst"].remove()
                rec_chain={
                    'togpu':in_chain["togpu"],
                    'tocpu':FromGLRGB(fs),
                    'enc_v':fs.load("enc:c=libx264:b=20M"),
                    'dst':fs.load_dst("./encode.mp4")
                    }
                for f1,f2 in pairwise(rec_chain.values()):
                    f1.insert(f2)
                    f2.set_source(f1)
                    f1.reconnect()
                #in_chain["dst"].remove()
                ## seeking immediately does not work!, as the graph is not yet fully linked
                #in_chain["ctl"].seek(rec_start)
            else:
                print("stop recording")
                in_chain["ctl"].pause()
                rec_chain["tocpu"].remove() ## disconnects.this one works!
                dead_chain={
                    'togpu':in_chain["togpu"],
                    'dst':DeadSink(fs),
                    }
                for f1,f2 in pairwise(dead_chain.values()):
                    f1.insert(f2)
                    f2.set_source(f1)
                    f1.reconnect()
                in_chain["ctl"].resume()
        if imgui.button("graph"):
            fs.print_graph()
            
        imgui.end()

        ## render loop
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        imgui.render()
        impl.render(imgui.get_draw_data())
        pygame.display.flip()
    fs.print_graph()
