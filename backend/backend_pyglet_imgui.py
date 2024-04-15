#!/usr/bin/env python
from OpenGL.GL import *
import pyglet

from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from imgui.integrations.pyglet import create_renderer,PygletProgrammablePipelineRenderer
import imgui

from itertools import pairwise

class GLFilterSession(gpac.FilterSession):
    def __init__(self, flags=0, blacklist=None, nb_threads=0, sched_type=0,window=None,context=None):
        gpac.FilterSession.__init__(self, flags, blacklist, nb_threads, sched_type)
        self.window=window
        self.context=context

    def on_gl_activate(self,param):
        '''
        + nothing is required for pygame, works even without subclassing FilterSession
        + with sdl2 (but also with pyglet or glfw), we're supposed to run in single threaded mode.
        it should'nt be necessary to do anything here!
        '''
        if param:
            self.window.switch_to()
            #super(MyFilterSession).on_gl_activate(param) #<=should we call inherited method and when?
        print("GLFilterSession: activating GL",param)
        
class GLWindow(pyglet.window.Window):
    def __init__(self,*args,**kwargs):
        super(GLWindow, self).__init__(*args,**kwargs)
        VIDEOSRC="../../video.mp4"
         ## initialize imgui
        imgui.create_context()
        self.impl=PygletProgrammablePipelineRenderer(self)
        io = imgui.get_io()
        io.fonts.add_font_default()
        io.display_size = self.width,self.height
        
        ## initialize gpac
        gpac.init(0)
        gpac.set_args(["",
                    "-js-dirs=/opt/gpac/share/gpac/scripts/jsf",
                    "-cfg=temp:cuda_lib=/usr/lib64/libcuda.so",
                    "-cfg=temp:cuvid_lib=/usr/lib64/libnvcuvid.so",
                    "-logs=filter@info:container@debug"])
        if 0:
            self.fs = GLFilterSession(flags=gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, 
                                    blacklist=None, 
                                    nb_threads=0, 
                                    sched_type=0,
                                    window=self,
                                    context=None)
        else:
            self.fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")
        self.fs.external_opengl_provider()
        
        ## setup filter list
        self.in_chain={
            'src':self.fs.load_src(VIDEOSRC),
            'dec':self.fs.load("ffdec"), 
            'reframer':self.fs.load("reframer:rt=on"),
            'glpush':self.fs.load("glpush.js"),
            'togpu':ToGLRGB(self.fs,size=1.0),
            'dst':DeadSink(self.fs)
            }
        for f1,f2 in pairwise(self.in_chain.values()):
            f2.set_source(f1)

    def on_draw(self):
        fs=self.fs
        tgt=self.in_chain["togpu"]
        fs.run()
        if fs.last_task:
            return
        
        ## gui setup
        imgui.new_frame()
        imgui.begin("Texture window", True)
        wwidth = imgui.get_window_content_region_max()[0]-2*imgui.get_style().frame_padding.x 
        try:
            imgui.image(tgt.fbo_attachement, wwidth,wwidth*tgt.o_height//tgt.o_width, uv0=(0,1),uv1=(1,0),border_color=(0, 0, 0, 1))
        except:
            pass
        imgui.text("test")
        imgui.end()

        ## render loop
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        imgui.render()
        self.impl.render(imgui.get_draw_data())

    def on_resize(self,w,h):
        pass
        
    def kbhandle(self,*args):
        pass
        
    def on_key_press(self,symbol, modifiers):
        if imgui.get_io().want_capture_keyboard:
            return

    def on_key_release(self,symbol, modifiers):
        if imgui.get_io().want_capture_keyboard:
            return
            
    def on_text(self,text):
        if imgui.get_io().want_capture_keyboard:
            return
                
    def on_mouse_press(self,x, y, button, modifiers):
        if imgui.get_io().want_capture_mouse:
            return

    def on_mouse_release(self,x, y, button, modifiers):
        if imgui.get_io().want_capture_mouse:
            return
        
    def on_mouse_scroll(self,x, y, button, modifiers):
        if imgui.get_io().want_capture_mouse:
            return

    def on_mouse_motion(self,x, y, dx, dy):
        if imgui.get_io().want_capture_mouse:
            return

    def on_mouse_drag(self,x, y, dx, dy, buttons, modifiers):
        if imgui.get_io().want_capture_mouse:
            return

if __name__ == '__main__':
    glwindow=GLWindow(width=1080, height=720, vsync=True,resizable=True)
    pyglet.app.run()
