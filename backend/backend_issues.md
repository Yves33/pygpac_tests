BACKEND issues
==============
Trying minimal examples of different python/GL backends for gpac
=>working (both ffdec or nvdev,with or without glpush)
+backend_pygame_minimal.py

=>not working (whatever the config)
+backend_sdl2_minimal.py
+backend_pyglet_minimal.py
+backend_glfw_minimal.py

Comments:
=========
+ I'd think that this is due to context switching, but don't know how to set appropriate context.
+ surprised that it does not work with SDL2 backend (which is very close to pygame)
+ sdl2, pyglet and glfw are supposed to run single thread. should not be necessary to overwrite on_gl_activate

Requirements:
=============
gpac, pyOpenGL [pygame | pyglet| pysdl2 | glfw]

Why:
====
Need to use imgui-bundle (https://github.com/pthom/imgui_bundle) to get access to imnodes from python
