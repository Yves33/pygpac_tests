#!/usr/bin/env python
from OpenGL.GL import *
from sdl2 import *

import sys
sys.path.append("../")
from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from imgui.integrations.sdl2 import SDL2Renderer
import imgui

from itertools import pairwise
       
def main():
    VIDEOSRC="../../video.mp4"
    ## initialize sdl2 and imgui
    width, height = 1280, 720
    window, gl_context = impl_pysdl2_init(width,height)
    imgui.create_context()
    impl = SDL2Renderer(window)
    io = imgui.get_io()
    io.fonts.add_font_default()
    io.display_size = 1280, 720

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

    event = SDL_Event()
    running=True
    while running:
        fs.run()
        if fs.last_task:
            break
        ## SDL2 event handling    
        while SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == SDL_QUIT:
                running = False
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
        SDL_GL_SwapWindow(window)
        
    fs.print_graph()
    impl.shutdown()
    SDL_GL_DeleteContext(gl_context)
    SDL_DestroyWindow(window)
    SDL_Quit()


def impl_pysdl2_init(width, height):
    '''
    creates an SDL window - minimal error checking
    '''
    window_name = "minimal ImGui/SDL2 example"
    SDL_Init(SDL_INIT_EVERYTHING)
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1)
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24)
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8)
    SDL_GL_SetAttribute(SDL_GL_ACCELERATED_VISUAL, 1)
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1)
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 8)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_COMPATIBILITY) ## force compatibility profile as glpush uses GL_LUMINANCE
    SDL_SetHint(SDL_HINT_MAC_CTRL_CLICK_EMULATE_RIGHT_CLICK, b"1")
    SDL_SetHint(SDL_HINT_VIDEO_HIGHDPI_DISABLED, b"1")
    window = SDL_CreateWindow(
        window_name.encode("utf-8"),
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        width,
        height,
        SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE,
    )
    gl_context = SDL_GL_CreateContext(window)
    SDL_GL_MakeCurrent(window, gl_context)
    SDL_GL_SetSwapInterval(0)
    return window, gl_context


if __name__ == "__main__":
    main()
