import libgpac as gpac

gpac.init(0)
'''
the file .gpac/GPAC.cfg does not include -js-dirs option. 
we expect it to be present, so we don't have to specify it in gpac.set_args()
'''
gpac.set_args(["",
                "-js-dirs=/opt/gpac/share/gpac/scripts/jsf",
		"-cfg=temp:cuda_lib=/usr/lib64/libcuda.so",
                "-cfg=temp:cuvid_lib=/usr/lib64/libnvcuvid.so",
                "-logs=filter@info:container@debug"
                ])
'''
after setting gpac init args, do we have a way to retrieve options? something like gpac.get_args()->dict 
would it be usefull?
'''
class ForwardFilter(gpac.FilterCustom):
	'''
	a minimal filter that does nothing
	'''
	def __init__(self, session):
		gpac.FilterCustom.__init__(self, session,"MinimalForward")
		self.push_cap("StreamType", "Visual", gpac.GF_CAPS_INPUT_OUTPUT)
		self.push_cap("CodecID", "raw", gpac.GF_CAPS_INPUT_OUTPUT)

	def configure_pid(self, pid, is_remove):
		if not pid in self.ipids:
			pid.opid = self.new_pid()
			pid.opid.copy_props(pid)
			print("Pixel format is ",pid.get_prop('PixelFormat'))
		return 0

	def process(self):
		for pid in self.ipids:
			pck = pid.get_packet()
			if pck==None:
				if pid.eos:
					pid.opid.eos = True
				break
			pid.opid.forward(pck)
			pid.drop_packet()
		return 0

fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING)
pipeline=2
if pipeline==0:
	'''
	works! nothing to change!
	'''
	src = fs.load_src("./video.mp4")
	dec=fs.load("ffdec") ## "ffdec"->"yuv" ; "nvdec"->"nv12"
	reframer=fs.load("reframer")
	custom=ForwardFilter(fs)
	out = fs.load("vout:disp=gl")
elif pipeline==1:
	'''
	fails: have to replace $GSHARE by hardcoded absolute path in avgen/init.js to make it work (does not work with relative path)
	Failed to get default shared dir
	[avgen] Error initializing filter
	[avgen] Error: Failed to load texture: Requested URL is not valid or cannot be found
    	at <anonymous> (/opt/gpac/share/gpac/scripts/jsf/avgen/init.js:240)
	in shell, the command gpac avgen vout works
        symlink ln -s /opt/gpac/share/gpac /usr/local/share/gpac works
	'''
	src = fs.load("avgen:fps=30000/1001:dur=30")
	reframer=fs.load("reframer")
	out = fs.load("vout")
elif pipeline==2:
	'''
	fails: in addition to previous avgen/init.js hack
	in _prop_to_python: 
	     pname.decode('utf-8')
	     AttributeError: 'int' object has no attribute 'decode'
	have to change (even when specifying pfmt in avgen)
	libgpac.py@2451 - if type==GF_PROP_UINT:
    libgpac.py@2451 + if type==GF_PROP_UINT or type==GF_PROP_PIXFMT:
	'''
	src = fs.load("avgen:fps=30000/1001:dur=30")
	reframer=fs.load("reframer")
	custom=ForwardFilter(fs) ## ForwardFilter fails when src is avgen, but not when src is mp4 file
	out = fs.load("vout")

while True:
	fs.run()
	if fs.last_task:
		break
fs.print_graph()
