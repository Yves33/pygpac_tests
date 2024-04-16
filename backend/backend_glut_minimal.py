from OpenGL.GLUT import *
from OpenGL.GLU import *
from OpenGL.GL import *

from pygpacfilters import *         ## utility filters: toGLRGB,fromGLRGB, DeadSink, Controller, FPSCounter...
from itertools import pairwise

def draw():
    fs.run()
    if fs.last_task:
        return
    glutSwapBuffers()
    glutPostRedisplay()

def keyboard(c, x, y):
    if c == chr(27):
        exit()

def reshape(x, y):
    glViewport(0, 0, x, y)


if __name__ == "__main__":
    VIDEOSRC="../../video.mp4"
    width, height = 1280, 720
    glutInit()
    glutInitWindowPosition(112, 84)
    glutInitWindowSize(width, height)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH | GLUT_MULTISAMPLE)
    glutCreateWindow("Minimal glut exemple")
    glutDisplayFunc(draw)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
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
    
    glClearDepth(1.0)
    glClearColor(0.0, 0.0, 0.0, 0.0)
    glutMainLoop()