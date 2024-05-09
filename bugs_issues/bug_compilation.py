import libgpac as gpac
import numpy

class PassThrough(gpac.FilterCustom):
    def __init__(self, session,caps=["Visual","Audio"]):
        gpac.FilterCustom.__init__(self, session, f"{'-'.join(caps)}PassThrough")
        for cap in caps:
            self.push_cap("StreamType", cap, gpac.GF_CAPS_INPUT_OUTPUT)
        self.set_max_pids(len(caps))

    def configure_pid(self, pid, is_remove):
        if is_remove:
            return 0
        if pid not in self.ipids:
            pid.opid = self.new_pid()
            pid.opid.copy_props(pid)
            #pid.opid.set_prop("test_string",'gpac is buggy', gpac.GF_PROP_STRING)   ## see previous mail about GF_PROP_STRING
            #pid.opid.set_prop("test_frac",2.2, gpac.GF_PROP_FRACTION64)             ## see previous mail about GF_PROP_FRACTION
            #pid.opid.set_prop("test_list",['one','two','three','four'], gpac.GF_PROP_STRING_LIST)  does not work. pointer incompatibility in ctypes
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

    def on_prop_enum(self,prop_name,propval):
        print(f"Property : {prop_name}\tValue : {propval}")

def link(f_chain,dbg=False):
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
                if dbg:
                    print(f"{f2.name} >>> {f1.name}")
                f1.set_source(f2,link_args)

gpac.init(0)
gpac.set_args(["",
            "-js-dirs=/opt/gpac/share/gpac/scripts/jsf",
            "-cfg=temp:cuda_lib=/usr/lib64/libcuda.so",
            "-cfg=temp:cuvid_lib=/usr/lib64/libnvcuvid.so",
            "-logs=filter@info:container@debug"])

fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")

layout=2
if layout==0:
    '''
    illustrates bug on filter ID and clock_hint_(media)time
    '''
    fsgraph={
        'src'   :   ( fs.load_src("/home/yves/Bureau/Delilah.mp4"),[] ),
        'aout'  :   (   fs.load("aout"),["src#audio"]),
        'vout'  :   (   fs.load("vout"),["src#video"]),
        }
if layout==1:
    '''
    illustrates double insertion of custom filters
    '''
    fsgraph={
        'src'   :   ( fs.load_src("/home/yves/Bureau/Delilah.mp4"),[] ),
        'pass' :   ( PassThrough(fs,["Video"]),['@0'] ),
        'vout'  :   (   fs.load("vout"),["@0#video"]),
        }
if layout==2:
    '''
    illustrates double insertion of custom filters
    '''
    fsgraph={
        'src'   :   ( fs.load_src("/home/yves/Bureau/Delilah.mp4"),[] ),
        'vpass' :   ( PassThrough(fs,["Video"]),['@0'] ),
        'vout'  :   (   fs.load("vout"),["@0#video"]),
        'apass' :   ( PassThrough(fs,["Audio"]),['src'] ),
        'aout'  :   (   fs.load("aout"),["@0#audio"]),
        }

link(fsgraph,dbg=True)
cnt=0
while True:
    fs.run()
    if fs.last_task:
        break
    cnt+=1
    if not cnt%30:
        for idx,f in enumerate (fs._filters):
            '''
            few bugs here!
            1) clock_hint_mediatime does not exist (same for clock_hint_time) neither on FIlter nore CustomFilter. 
            + either should exist (optionnally return None), or should be stated in the docs that attribute is not always present
            
            2) f.ID is sometimes None, but the case is not properly handled in libgpac line ~2917.
            @property
            def ID(self):
                try:
                    return _libgpac.gf_filter_get_id(self._filter).decode('utf-8')
                except:
                    return None ## return '_'+hex(id(self))[2:]+'_' to overwrite None ID
                    
            NB: I would naively expect every filter to have a unique ID. In the present demo, demuxer, decoder, vout, aout have None as an ID
                    
            3) filter PassThrough is inserted twice in fs._filters (this is the case for all custom filters). Didn't cath everything, but:
            + first insertion in on_filter_new_del()->session._to_filter(self, f) ## conditionnal insertion
            + second insertion in FilterCustom.__init__()                         ## no check at all
            conditionnally inserting filter in FilterCustom.__init__() solves the problem (but should be tested more extensively!)
            if not self._filter in [f._filter for f in session._filters]:
                session._filters.append(self)
            NB: I have many problems with filter.remove(), but I guess it is linked to that problem
            '''
            print(idx, f.name, f.ID, f.clock_hint_mediatime, f.clock_hint_time)
        fs.print_graph()
        break
        
fs.abort(gpac.GF_FS_FLUSH_ALL)
fs.print_graph()
