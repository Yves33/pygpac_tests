#!/usr/bin/env python
from OpenGL.GL import *
import pygame

import sys
sys.path.append("../")
from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from imgui.integrations.pygame import PygameRenderer
import imgui

from itertools import pairwise
    
def main():
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
        'dec':fs.load("nvdec"), 
        'reframer':fs.load("reframer:rt=on"),
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs,size=1.0),
        'dst':DeadSink(fs)
        }
    for f1,f2 in pairwise(in_chain.values()):
        f2.set_source(f1)
    tgt=in_chain["togpu"]

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
            impl.process_event(event)
        impl.process_inputs()

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
        impl.render(imgui.get_draw_data())
        pygame.display.flip()
    fs.print_graph()
    impl.shutdown()

if __name__ == "__main__":
    main()
