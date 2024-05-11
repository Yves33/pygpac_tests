## About:
This file recapitulates missing, broken (or just unclear) features in the gpac test suite.  

### howto.  
In order to reproduce the examples, one can generate the following clips:  
```
gpac uncvg:vsize=320x240:dur=10:pal=yellow,green ffavf::f=drawtext=text=%{pts}:fontsize=36 ffenc:c=avc -o ygstripes.mp4
gpac uncvg:vsize=320x240:dur=10:pal=cyan,white ffavf::f=drawtext=text=%{pts}:fontsize=36 ffenc:c=avc -o cwstripes.mp4
gpac uncvg:vsize=320x240:dur=10:pal=grey,orange ffavf::f=drawtext=text=%{pts}:fontsize=36 ffenc:c=avc -o gostripes.mp4
```

### 1 - seeking in playlist does not work.  
When a playlist is used as input, sending gpac.GF_FEVT_PLAY with evt.start_range=x does not seek to appropriate file/time in playlist. The expected behavior would be to:  
+ seek to correct src and position in src if src is seekable.  
+ play src for adjusted duration if stream is not seekable.  

With playlist:
```
##begin playlist.m3u
#start=2.0 stop=8.0 CHAPTER="test0"
ygstripes.mp4
##start=3.0 stop=7.0 CHAPTER="test1"
cwstripes.mp4
#start=0.0 stop=10.0 CHAPTER="test2"
gostripes.mp4
##end playlist
```
seek(8.5) should:  
+jump to file cwstripes.mp4 / time  8.5-(8.0-2.0)+3.0=5.5s if cwstripes.mp4 is seekable,  
+or play cwstripes.mp4 for 1.5s if cwstripes.mp4 is not seekable.  
  
When playing with right/left keys (should go backward/forward 1% the total duration).  
```
gpac -i playlist.m3u vout
[VideoOut] Media PID does not support seek, ignoring start directive
[VideoOut] Media PID does not support seek, ignoring start directive
[VideoOut] Media PID does not support seek, ignoring start directive
```

in addition, when enumerating output pid properties (python api):  
'URL'       ->reports first URL in playlist, should report currently playing url  
'SourcePath'->reports first URL in playlist, should report currently playing url  
'MovieTime' ->reports first URL media duration. should return playlist duration (if all media src have known duration)

### 2 - seeking in file with reframer does not work.
```
gpac -i ygstripes.mp4 reframer:rt=on:xs=5.0 vout  
```
+ video playback starts at 4.6xx (should be exactly 5.0).  
+ pressing once "left" does not seek back.  
+ pressing several times "left" does not seek but leads to "reframer (idx 2) not responding properly: 100000 consecutive(...)"  

After inserting "reframer:xs=2.5:xe=8.5",  
+ seek(0.0) should seek to t=2.5 in stream and play for 6s (if seekable).   
+ seek(12.0) should set eos flag.  

### 3 - seeking in avmix does not work.
```
gpac avmix vout
```
NB Ideally, it should be also possible to seek, step in avmix or compositor scene, etc

### 3 -dynamic filter insertion/removal (solved after removing duplicated custom filters?).
(see also illustration in bug_compilation.py)  
Suppose I have `fin:file.mp4->nvdec6->jsf:js=my_fancy_filter.js->vout.  
If I dynamically want to record the output of jsf, I may add:  
```
encoder=fs.load("enc:libx264")
writer=fs.load("fout:dst=myfile.out")
encode.set_source(my_fancy_js_filter)
writer.set_source(encoder)
```
gpac will dynamically insert a bunch of filters  (with dyn_idx).  
```
fs.print_graph()
(---)
------(PID V1) ffsws (dyn_idx=16)
-------(PID V1) ffenc "ffenc:libx264" (c=libx264:b=20M) (idx=11)
--------(PID V1) rfnalu (dyn_idx=15)
---------(PID V1) mp4mx (dyn_idx=14)
----------(PID V1) fout (dst=./encode.mp4) (idx=13)
```
when I stop recording, removing `ffenc` and `fout` may leave the filters `rfnalu` and `mp4mx` in the unconnected filters reported by print_graph(because they are linked together, they are not removed).  
+ how can I get the list of unconnected filters (see also how to determine filter caps in misc questions)

### 4 - questions and observations
+ pid.query_caps() works on pid, and is therefore accessible ONLY for custom filters. how can I query the caps of all filters (something like [f.query_caps() for f in session._filters] )

+ gpac -i xx glpush vout works, but not gpac -i glpush compositor. Isnt't vout supposed to load compositor?  

+ packets on audio pid: how can i get access to the different channels (get left/right uncompressed buffer) from pck.data

+ avmix should handle sources in the form 
ipid://#URL=some url @ glpush @jsf:myfancyglshader.js
then in python code
src1=fs.load_src('clip1.mp4:id=V1')
src2=fs.load_src('clip2.mp4:id=V2')
avmix=fs.load('avmix')
avmix.set_source(src1,"id=V1")
avmix.set_source(src2,"id=V2")