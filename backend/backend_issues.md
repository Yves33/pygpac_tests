BACKEND issues:
==============
Trying minimal examples of different python/GL backends for gpac (tested: pygame, glfw, sdl2, pyglet, glut. not tested (yet): sfml, modernl)
=>working:
+backend_pygame_minimal.py  
+backend_glut_minimal.py  

=>not working (whatever the config):  
+backend_sdl2_minimal.py  
+backend_pyglet_minimal.py  
+backend_glfw_minimal.py  

HOW:
====
+ in all examples, setup a minimal context for GL, and a filter chain with
src->nvdec|ffdec->(glpush)->togpu->DeadSink (glpush is not mandatory)
+ in order to test for gl, I have a TestShape class that is drawn on top of video outside fs.run() loop
+ this shape can optionnaly be replaced by a Shaper filter (which just passes packets and draw the shape)

+ pygame and glut example works (with/without glpush, with/without Shaper filter, with ffdec and nvdec)
+ all other examples fail on OpenGL.error.GLError: GLError (often in glBindTexture, but depends on backend)

Comments:
=========
+ I'd think that this is due to context switching, but don't know how to set appropriate context. 
+ sdl2, pyglet and glfw are supposed to run single thread. should not be necessary to overwrite on_gl_activate if everything is running in the main thread!
+ if glpush and/or togpu are removed from filter chain, then everything works (shape is drawn)!
+ shape drawing works till the first packet processed by glpush/togpu
  
Requirements:
=============
gpac, pyOpenGL [pygame | pyglet| pysdl2 | glfw | freeglut]  

Why:
====
Need to use imgui-bundle (https://github.com/pthom/imgui_bundle) to get access to imnodes from python.

nb: examples with imgui can be ignored!
