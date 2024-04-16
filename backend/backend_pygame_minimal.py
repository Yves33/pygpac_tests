#!/usr/bin/env python
from OpenGL.GL import *
import pygame

from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from itertools import pairwise

def main():
    VIDEOSRC="../../video.mp4"
    ## initialize pygame and imgui
    width, height = 1280, 720
    pygame.init()
    pygame.display.set_mode((width, height), pygame.DOUBLEBUF|pygame.OPENGL|pygame.HWSURFACE, 0)

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

    running=True
    while running:
        fs.run()
        if fs.last_task:
            break
        ## pygame event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running=False
                break

        ## render loop
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        pygame.display.flip()
    fs.print_graph()

if __name__ == "__main__":
    main()
