#!/usr/bin/env python
from OpenGL.GL import *
import glfw

from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from itertools import pairwise

import sys

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
    fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")
    fs.external_opengl_provider()

    ## setup filter list
    in_chain={
        'src':fs.load_src(VIDEOSRC),
        'dec':fs.load("nvdec"), 
        'reframer':fs.load("reframer:rt=off"),
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs,size=1.0,mirror=True, mirror_viewport=(0,0,width,height)),
        'dst':DeadSink(fs)
        }
    for f1,f2 in pairwise(in_chain.values()):
        f2.set_source(f1)
    while not glfw.window_should_close(window):
        fs.run()
        if fs.last_task:
            break
        glfw.poll_events()
        ## render loop
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
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_COMPAT_PROFILE) ## force compatibility profile as glpush and python filters use GL_LUMINANCE and GL_LUMINANCE_ALPHA
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)

    # Create a windowed mode window and its OpenGL context
    window = glfw.create_window(int(width), int(height), window_name, None, None)
    glfw.make_context_current(window)
    glfw.swap_interval( 0 )

    if not window:
        glfw.terminate()
        print("Could not initialize Window")
        sys.exit(1)
    return window


if __name__ == "__main__":
    main()