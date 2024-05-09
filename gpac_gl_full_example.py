#!/usr/bin/env python
from __future__ import division
from OpenGL.GL import *
import pygame
from imgui.integrations.pygame import PygameRenderer
import imgui

from pygpacfilters import *         ## utility routines and filters. toGPU, Deadsink, ...

if __name__=='__main__':
     
    def link(f_chain,insert=False):
        for key,(f1,links) in f_chain.items():
            for src in links:
                src_str,link_args=src.split('#') if "#" in src else [src,None]
                if src_str in list(f_chain.keys()):
                    f2=f_chain[src_str][0]
                elif src.startswith("@@"):
                    idx=int(src_str[2:])
                    src_name=list(f_chain.keys())[idx]
                    f2=f_chain[src_name][0]
                elif src.startswith("@"):
                    offset=int(src_str[1:])
                    src_idx=list(f_chain.keys()).index(key)-(offset+1)
                    src_name=list(f_chain.keys())[src_idx]
                    f2=f_chain[src_name][0]
                if insert and f1 not in f2._session._filters:
                    f2.insert(f1)
                f1.set_source(f2,link_args)
                if insert:
                    f2.reconnect()
                    f1.reconnect()


    VIDEOSRC="../video.mp4"
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

    ## filter chain : dict {key : (gpac.filter, [srckey#linkargs,srckey#linkargs])}
    ## todo: overwrite FilterSession to load from json. requires to modify custom filters to enable string initialisation
    '''f_chain={
        'clip'   :   ( fs.load("fin:src="+VIDEOSRC),[] ),
        'vdec'  :   ( fs.load('ffdec'),['clip#video']),    ## 'nvdec'
        'adec'  :   ( fs.load('ffdec'),['clip#audio']),
        'ctl'   :   ( Controller(fs,rt=1.0),['vdec#video','adec#audio'] ),
        ## video chain
        'togpu' :   ( ToGLRGB(fs),['ctl#video']),
        ## insert your Video processing filters here
        'dst'   :   ( DeadSink(fs),['@0'] ),
        ## audio chain
        ### insert you audio processing filters here
        'resamp':   ( fs.load("resample"),['ctl#audio']),
        'aout'  :   (fs.load("aout"),['@0'])
    }
    ctl=f_chain["ctl"][0]        ## the controller
    tgt=f_chain["togpu"][0]      ## the filter owning texture/FBO to display in imgui
    vrec=f_chain["togpu"][0]     ## the filter owning texture/FBO to record
    arec=f_chain["ctl"][0]       ## the fiter from where audio is recorded
    '''
    f_chain={
        #'clip'   :   ( fs.load("fin:src="+VIDEOSRC+":gfreg=ffdmx,nvdec"),[] ),
        'fin'   :   ( fs.load_src("../playlist.m3u"),[]),
        'clip' :    ( fs.load("flist:timescale=30000:sigcues=1"),['fin']),
        ## video chain
        'togpu' :   ( ToGLRGB(fs),['clip#video']),
        ## insert your Video processing filters here
        'apass'  :  (PassThrough(fs,caps=['audio']),['clip#audio']),
        ## insert your audio processing filters here
        'ctl'   :   ( Controller(fs,rt=1.0),['togpu#video',"apass#audio"] ),
        'dst'   :   ( DeadSink(fs),['@0#video'] ),
        ## audio chain
        ### insert you audio processing filters here
        'resamp':   ( fs.load("resample"),['ctl#audio']),
        'aout'  :   (fs.load("aout"),['@0'])
    }
    ctl=f_chain["ctl"][0]        ## the controller
    tgt=f_chain["togpu"][0]      ## the filter owning texture/FBO to display in imgui
    vrec=f_chain["ctl"][0]       ## the filter owning texture/FBO to record
    arec=f_chain["ctl"][0]       ## the fiter from where audio is recorded
    
    '''f_chain={
        'clip'   :   ( fs.load("fin:src="+VIDEOSRC),[] ),
        'reframer': ( fs.load('reframer:rt=on:raw=av'),['@0']),
        'ctl'   :   ( Controller(fs,rt=0.0),['@0#video','@0#audio'] ),
        ## video chain
        'togpu' :   ( ToGLRGB(fs),['ctl#video']),
        'dst'   :   ( DeadSink(fs),['@0'] ),
        ## audio chain
        'resamp':   ( fs.load("resample"),['ctl#audio']),
        'aout'  :   (fs.load("aout"),['@0'])
    }
    ctl=f_chain["ctl"][0]        ## the controller
    tgt=f_chain["togpu"][0]      ## the filter owning texture/FBO to display in imgui
    vrec=f_chain["togpu"][0]     ## the filter owning texture/FBO to record
    arec=f_chain["ctl"][0]       ## the fiter from where audio is recorded
    '''
    link(f_chain)

    running=True
    ctl.pause()
    recording=False
    changed=False
    seekto=0
    while running:
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
                #ctl.resume()
                fs.abort(gpac.GF_FS_FLUSH_ALL if recording else 0)  ## don't need gpac.GF_FS_FLUSH_ALL as we are not recording
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_p:
                    ctl.toggle()
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
        ## playback controls
        if imgui.button("Play" if ctl.paused else "Pause"):
            ctl.toggle()
        imgui.internal.push_item_flag(imgui.internal.ITEM_DISABLED, not ctl.paused)
        imgui.push_style_var(imgui.STYLE_ALPHA, imgui.get_style().alpha *  [0.5,1.0][ctl.paused])
        imgui.same_line()
        if imgui.button("Step"):
            ctl.step()
            print("Control : ",ctl.sync_data[0].dts,"Renderer : ",tgt.dts)
        imgui.internal.pop_item_flag()
        imgui.pop_style_var()
        imgui.same_line()
        imgui.text(f"Position {ctl.clip_position_s:5.2f} / {ctl.clip_duration_s:5.2f}")
        _seek, seekto=imgui.input_float("Seek to",seekto,0,0,format='%.3f',flags=imgui.INPUT_TEXT_ENTER_RETURNS_TRUE)
        if _seek:
            ctl.seek(seekto)
        imgui.new_line()
        ## uniforms for toGPU shader
        u1, tgt.brightness=imgui.slider_float("Brightness",tgt.brightness,0,3.0)
        u2, tgt.saturation=imgui.slider_float("Saturation",tgt.saturation,0,3.0)
        u3, tgt.contrast=imgui.slider_float("Contrast",tgt.contrast,0,3.0)
        changed=u1 or u2 or u3 
        ## add instant record checkbox
        toggle,recording=imgui.checkbox("Record",recording)
        if toggle:
            _paused=ctl.paused
            ctl.pause()
            if recording:
                print("start recording")
                rec_chain={
                    'vrec' :    ( vrec,               []                  ), ## no need to relink here
                    'arec' :    ( arec,               []                  ), ## no need to relink here
                    'tocpu' :   ( FromGLRGB(fs),                     ['vrec#video']     ),
                    'enc_v' :   ( fs.load("enc:c=libx264:b=20M"),    ['tocpu#video',]   ),
                    'enc_a' :   ( fs.load("enc:c=aac:b=100k"),       ['arec#audio']     ),
                    'fout'  :   ( fs.load("fout:dst=./encode.mp4"),  ["enc_v#video","enc_a#audio"] ),
                    }
                link(rec_chain,insert=True)

            else:
                print("stop recording")
                rec_chain["tocpu"][0].remove()
                rec_chain["enc_a"][0].remove()
            if _paused:
                ctl.pause()
            else:
                ctl.resume()

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
