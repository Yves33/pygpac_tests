#!/usr/bin/env python
from __future__ import division
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
                    #"-logs=filter@info:container@debug"
                    ])
    fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")
    fs.external_opengl_provider()

    ## setup filter list
    in_chain={
        'src':fs.load_src("./video.mp4"),
        'dec':fs.load("nvdec"),
        'reframer':fs.load("reframer:rt=on"),
        'glpush':fs.load("glpush.js"),
        'togpu':ToGLRGB(fs),
        'dst':DeadSink(fs)                          ## a sink is required
        }
    
    for f1,f2 in pairwise(in_chain.values()):
        f2.set_source(f1)

    tgt=in_chain["togpu"]

    running=True
    brightness=1.0
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
                elif event.key == pygame.K_r:
                    in_chain["dst"].remove()
            impl.process_event(event)
        impl.process_inputs()

        ## gui setup
        imgui.new_frame()
        imgui.begin("Texture window", True)
        wwidth = imgui.get_window_content_region_max()[0]-2*imgui.get_style().frame_padding.x 
        imgui.image(tgt.fbo_attachement, wwidth,wwidth*tgt.height//tgt.width, uv0=(0,1),uv1=(1,0),border_color=(0, 0, 0, 1))
        changed, brightness=imgui.slider_float("Brightness",brightness,0,3.0)
        glUseProgram(tgt.texture.prog.program)
        glUniform1f(tgt.texture.prog.getUniformLocation("brightness"),brightness)
        glUniform1f(tgt.texture.prog.getUniformLocation("saturation"),1.0)
        glUniform1f(tgt.texture.prog.getUniformLocation("contrast"),1.0)
        toggle,recording=imgui.checkbox("Record",recording)
        if toggle:
            if recording:
                print("start recording")
                '''
                works, but not really sure this is the proper way to proceed:
                I'd expect that I need to
                - remove last sink
                - insert and connect filters
                when I start recording, in_chain["dst"].remove() blocks the stream or crashes, depending where I call
                '''
                #in_chain["dst"].remove() ## remove() here induces crash!
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
                #in_chain["dst"].remove() ## remove() yields "empty" frames
            else:
                '''works, but many frames displayed at max speed after I stop recording
                (my videos are huge and encoding cannot be done in RT. encode speed is ~0.5)
                '''
                print("stop recording")
                rec_chain["tocpu"].remove() ## disconnects.this one works!
                dead_chain={
                    'togpu':in_chain["togpu"],
                    'dst':in_chain["dst"],
                    }
                for f1,f2 in pairwise(dead_chain.values()):
                    f1.insert(f2)
                    f2.set_source(f1)
                    f1.reconnect()
        imgui.end()

        ## render loop
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        imgui.render()
        impl.render(imgui.get_draw_data())
        pygame.display.flip()
    fs.print_graph()
