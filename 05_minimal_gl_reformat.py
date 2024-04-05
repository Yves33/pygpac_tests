#!/usr/bin/env python
from __future__ import division
import os
from OpenGL.GL import *
import pygame

from glgpac import *         ## utility routines and filters. toGPU, Deadsink, ...
from imgui.integrations.pygame import PygameRenderer
import imgui

from itertools import pairwise

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
                    "-logs=filter@info:container@debug"
                    ])
    fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")
    fs.external_opengl_provider()

    ## setup filter list
    in_chain={
        'src':fs.load_src("../video.mp4"),
        'dec':fs.load("nvdec"),
        'reframer':fs.load("reframer:rt=on"),
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs),
        'reformat':fs.load(f"jsf:js={os.path.dirname(__file__)}/glreformat.js"), ## reformats GPU frames in gpac compliant,but with 0 data
        ## first option.
        ## redirect to vout. 
        ## with disp=gl|pbo, vout displays the texture *with* altered brightness, as expected
        ## with disp=blit|soft, program crahes with glerror, as pck.data is empty?
        'vout':fs.load("vout:vsync=1:disp=gl:wsize=640x320"),
        ## second option: 
        ## forward frame to ffenc / ffsws.
        ## it seems that ffmpeg filters cannot handle gl interface frames ? in fact, very few filters handle hardware frames without data
        #'ffsws':fs.load("ffsws:osize=640x0"),
        #'enc_v':fs.load("enc:c=libx264:b=20M"),
        #'dst':fs.load_dst("./encode.mp4")
        ## third option: display as ususal
        #'dst':DeadSink(fs)                          ## a sink is required
        }
    
    for f1,f2 in pairwise(in_chain.values()):
        f2.set_source(f1)

    ##awfull hack
    in_chain.__getattr__=in_chain.__getitem__
    tgt=in_chain["togpu"]

    running=True
    brightness=2.0
    recording=False
    changed=False
    while running:
        fs.run()
        if fs.last_task:
            break
        
        ## pygame event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                fs.abort(gpac.GF_FS_FLUSH_ALL)  ## don't need gpac.GF_FS_FLUSH_ALL as we are not recording
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_p:
                    fs.print_graph()
            impl.process_event(event)
        impl.process_inputs()

        ## gui setup. Doesn't work with vout, due to gl context switching?
        imgui.new_frame()
        imgui.begin("Texture window", True)
        wwidth = imgui.get_window_content_region_max()[0]-2*imgui.get_style().frame_padding.x 
        imgui.image(tgt.fbo_attachement, wwidth,wwidth*tgt.height//tgt.width, uv0=(0,1),uv1=(1,0),border_color=(0, 0, 0, 1))
        changed, brightness=imgui.slider_float("Brightness",brightness,0,3.0)

        glUseProgram(tgt.texture.prog.program)
        glUniform1f(tgt.texture.prog.getUniformLocation("brightness"),2.0)
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
