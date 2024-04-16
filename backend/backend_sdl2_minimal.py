#!/usr/bin/env python
from OpenGL.GL import *
from sdl2 import *

from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from itertools import pairwise
       
def main():
    VIDEOSRC="../../video.mp4"
    ## initialize sdl2 and imgui
    width, height = 1280, 720
    window, gl_context = impl_pysdl2_init(width,height)

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
        
        ## render loop
        glUseProgram(0)
        glDisable(GL_DEPTH_TEST)
        SDL_GL_SwapWindow(window)
        
    fs.print_graph()
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
