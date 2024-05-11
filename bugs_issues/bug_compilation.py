import my_libgpac as gpac
'''
The game is to have this code work after removing *all* comments (but keep docstrings)!
+ pid.set_prop(gpac.GF_PROP_STRING)
+ pid.set_prop(gpac.GF_PROP_FRACTION|FRACTION64) when value is float or int
+ pid.set_prop(gpac.GF_PROP_STRING_LIST)
+ filter.clock_hint_mediatime()
+ filter.ID
+ duplicate custom filter insertion in sesssion._filters
+ filter.remove() not working as (I) expected
'''

'''
utility function. works, no need to check!!
retrieves all possible path from source node to dst node or sink (if sink_node is None)
https://stackoverflow.com/questions/3278481/list-of-all-paths-from-source-to-sink-in-directed-acyclic-graph
'''
def walk_chain(source_node, sink_node=None):
    if sink_node is None and source_node.nb_opid==0:
        return frozenset([(source_node,)])
    if sink_node and source_node._filter==sink_node._filter:
        return frozenset([(source_node,)])
    else:
        result = set()
        for idx in range(source_node.nb_opid):
            for node in source_node.opid_sinks(idx):
                paths = walk_chain(node, sink_node)
                for path in paths:
                    path = (source_node,) + path
                    result.add(path)
        result = frozenset(result)
        return result
'''
utility functions. works, no need to check!!
links filters according to instructions (see later in code for examples)
TODO: change dict structure from  {key:(filter,[link_args,])} to {key:[filter,link_args,...]} )
'''    
def link_graph(f_chain,dbg=False):
    for key,(f1,links) in f_chain.items():
        for link in links:
            link_from,link_args=link.split('#') if "#" in link else [link,None]
            if link_from in list(f_chain.keys()):
                f2=f_chain[link_from][0]
            elif link.startswith("@@"):
                idx=int(link_from[2:])
                src_name=list(f_chain.keys())[idx]
                f2=f_chain[src_name][0]
            elif link.startswith("@"):
                offset=int(link_from[1:])
                src_idx=list(f_chain.keys()).index(key)-(offset+1)
                src_name=list(f_chain.keys())[src_idx]
                f2=f_chain[src_name][0]
            if dbg:
                print(f"{f2.name} >>> {f1.name}")
            f1.set_source(f2,link_args)

def fract(f):
    '''converts gpac.Fraction to python fractions.Fraction'''
    import fractions
    return fractions.Fraction(f.num,f.den)

'''
minimal passthrough filter
used to test non working pid_set_prop(GF_PROP_STRING|GF_PROP_FRACTION|GF_PROP_STRING_LIST)
used to test repeated custom filter insertion
'''
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
            '''
            1) see previous comments in emails and BUGS.md
            set_prop(p,string,gpac.gpac.GF_PROP_STRING) does not work due to local overloading of type str by variable str
            set_prop(p,float_or_int, gpac.GF_PROP_FRACTION) does not work due to is_integer() not declared (javascript spotted!)
            set_prop(p,string_list,gpac.GF_PROP_STRING_LIST) does not work due to pointer incompatibility in ctypes (and that one is tricky to solve)
            '''
            pid.opid.set_prop("test_string",'gpac is buggy', gpac.GF_PROP_STRING)
            pid.opid.set_prop("test_frac",2.2, gpac.GF_PROP_FRACTION64)
            pid.opid.set_prop("test_string_list",['gpac','is','really','buggy'], gpac.GF_PROP_STRING_LIST)
        return 0

    def process(self):
        for pid in self.ipids:
            assert(pid.opid.get_prop('test_string')=='gpac is buggy')
            assert(fract(pid.opid.get_prop('test_frac'))==fract(gpac.Fraction64(2200000,1000000)))
            assert('buggy' in pid.opid.get_prop("test_string_list"))
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

gpac.init(0)
gpac.set_args([ "",
                "-js-dirs=/opt/gpac/share/gpac/scripts/jsf",
                "-cfg=temp:cuda_lib=/usr/lib64/libcuda.so",
                "-cfg=temp:cuvid_lib=/usr/lib64/libnvcuvid.so",
                #"-logs=filter@info:container@debug"
                ])

fs = gpac.FilterSession(gpac.GF_FS_FLAG_NON_BLOCKING | gpac.GF_FS_FLAG_REQUIRE_SOURCE_ID, "")

layout=0
VIDEOSRC="/home/yves/Bureau/Delilah.mp4"
if layout==0:
    '''
    illustrates bug on filter ID and clock_hint_(media)time
    '''
    fsgraph={
        'src'   :   ( fs.load_src(VIDEOSRC),[] ),
        'aout'  :   (   fs.load("aout"),["src#audio"]),
        'vout'  :   (   fs.load("vout"),["src#video"]),
        }
if layout==1:
    '''
    illustrates double insertion of custom filters
    '''
    fsgraph={
        'src'   :   ( fs.load_src(VIDEOSRC),[] ),
        'pass' :   ( PassThrough(fs,["Video"]),['@0'] ),
        'vout'  :   (   fs.load("vout"),["@0#video"]),
        }
if layout==2:
    '''
    illustrates double insertion of custom filters and filter removal
    '''
    fsgraph={
        'src'   :   ( fs.load_src(VIDEOSRC),[] ),
        'vpass' :   ( PassThrough(fs,["Video"]),['@0'] ),
        'vout'  :   (   fs.load("vout"),["@0#video"]),
        'apass' :   ( PassThrough(fs,["Audio"]),['src'] ),
        'aout'  :   (   fs.load("aout"),["@0#audio"]),
        }

link_graph(fsgraph,dbg=True)
cnt=0
while True:
    fs.run()
    if fs.last_task:
        break
    cnt+=1
    if not cnt%30:
        for idx,f in enumerate (fs._filters):
            '''
            1) clock_hint_mediatime
            TypeError: byref() argument must be a ctypes instance, not '_ctypes.PyCStructType'
            (val must be an allocated struct (Fraction64()) and not a type (Fraction64).
            not really sure of the correction!)
            @property 
            def clock_hint_mediatime(self):
                val = Fraction64()
                _libgpac.gf_filter_get_clock_hint(self._filter, None, byref(val))
                return val
            
            2) f.ID is sometimes None, but the case is not properly handled in libgpac @@ 2917.
            @property
            def ID(self):
                try:
                    return _libgpac.gf_filter_get_id(self._filter).decode('utf-8')
                except:
                    return None ## return '_'+hex(id(self))+'_' to overwrite None ID. But maybe the bug is in C code?
                    
            NB: I would naïvely expect every filter to have a unique ID. In the present case, demuxer, decoder, vout, aout have None as an ID
            '''
            if isinstance(f,gpac.FilterCustom):
                print(idx, type(f), f.name, f.ID, f.clock_hint_mediatime, f.clock_hint_time)
            else:
                print(idx, type(f), f.name, f.ID)
            '''        
            3) Custom filters are inserted twice in fs._filters
            + once as gpac.Filter (@@ 3240)
            + once as __main__.FilterCustom (@@3247)
            both have the same value for _filter ( assert (fs._filters[1]._filter==fs._filters[2]._filter) )
            
            is it an intended behavior? and if not, then we could we either
            + prevent custom filter insertion (but then, we cannot access FilterCustom specific fields and methods):
            if not self._filter in [f._filter for f in session._filters]:
                session._filters.append(self) ## should never happen! in fact simply commenting out the line would be enough
            + remove the gpac.Filter instance added by libgpac and add the FilterCustom
            session._filters.pop()
            session._filters.append(self)
            '''
            fnames=[f.name for f in fs._filters]
            assert( len(fnames)==len(set(fnames)) )
        fs.print_graph()

        '''
        4) Not yet sure how to handle the problem (if it's a gpac problem)

        remove apass and aout filters after 30 frames and wait another 30 frames
        + this leaves some connected filters (ffdec:aac, resample)
        + this does not remove aout
        + trying to force remove all dynamically inserted filters (ffdec:aac, resample) does not solve the problem
        '''
        if layout==2 and  'apass' in fsgraph.keys():
            fs.fire_event(gpac.FilterEvent(gpac.GF_FEVT_STOP))
            #fsgraph['apass'][0].remove()
            #fsgraph['aout'][0].remove()
            for f in list(walk_chain(fsgraph['apass'][0],fsgraph['aout'][0]))[0][::1]:
                print(f"removing {f.name}")
                f.remove()
            del fsgraph['apass']
            del fsgraph['aout']
            fs.fire_event(gpac.FilterEvent(gpac.GF_FEVT_PLAY))

    if not cnt%60:
        if layout==2:
            assert( 'resample' not in [f.name for f in fs._filters] )
        break
        
fs.abort(gpac.GF_FS_FLUSH_ALL)
fs.print_graph()
