#!/usr/bin/env python
from OpenGL.GL import *
import glfw

from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from itertools import pairwise
from testshape import TestShape,Shaper

import sys

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
            glfw.make_context_current(self.window)
            #super(MyFilterSession).on_gl_activate(param) #<=should we call inherited method and when?
        print("GLFilterSession: activating GL",param)

def main():
    VIDEOSRC="../../video.mp4"
    ## initialize glfw and imgui
    width, height = 1280, 720
    window = impl_glfw_init(width,height)

    ## initialize gpac
    gpac.init(0)
    gpac.set_args(["",
                    "-js-dirs=/opt/gpac/share/gpac/scripts/jsf",
                    "-cfg=temp:cuda_lib=/usr/lib64/libcuda.so",
                    "-cfg=temp:cuvid_lib=/usr/lib64/libnvcuvid.so",
                    "-logs=filter@info:container@debug"])
    if 0:
        fs = GLFilterSession(flags=gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, 
                                        blacklist=None, 
                                        nb_threads=0, 
                                        sched_type=0,
                                        window=window,
                                        context=None)
    else:
        fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")
    fs.external_opengl_provider()

    ## setup filter list
    in_chain={
        'src':fs.load_src(VIDEOSRC),
        'dec':fs.load("ffdec"), 
        'reframer':fs.load("reframer:rt=on"),
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs,size=1.0,mirror=True, mirror_viewport=(0,0,width,height)),
        #'shaper':Shaper(fs),
        'dst':DeadSink(fs)
        }
    for f1,f2 in pairwise(in_chain.values()):
        f2.set_source(f1)
    shape=TestShape()
    while not glfw.window_should_close(window):
        fs.run()
        if fs.last_task:
            break
        glfw.poll_events()

        ## render loop
        shape.draw()
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        glfw.swap_buffers(window)
    glfw.terminate()
    fs.print_graph()


def impl_glfw_init(width,height):
    window_name = "minimal ImGui/GLFW3 example"

    if not glfw.init():
        print("Could not initialize OpenGL context")
        sys.exit(1)

    # OS X supports only forward-compatible core profiles from 3.2
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)

    # Create a windowed mode window and its OpenGL context
    window = glfw.create_window(int(width), int(height), window_name, None, None)
    glfw.make_context_current(window)

    if not window:
        glfw.terminate()
        print("Could not initialize Window")
        sys.exit(1)

    return window


if __name__ == "__main__":
    main()