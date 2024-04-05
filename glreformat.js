import {WebGLContext} from 'webgl'

//metadata
filter.set_name("glreformat");
filter.set_desc("GPU frame reformater");
filter.set_version("1.0");
filter.set_author("Yves33");
filter.set_help("This filter generates packets with frame_ifce_gl=True, taking texture ids from packet data\n"+
"The current python api does not enable creating packets with fame_ifce_gl=True\n"+
"A workaround is to :\n"+
" - use packet data / pid custom properties to pass textures to next filter\n"+
" - use the present filter to generate frame_ifce_gl compliant packets\n"+
" - send these packets to standard gpac filters (e.g vout)\n"
);

//raw video in and out
filter.set_cap({id: "StreamType", value: "Video", inout: true} );
filter.set_cap({id: "CodecID", value: "raw", inout: true} );

let gl=null;
filter.initialize = function() {
  // creating gl context is required, also we are not using any gl functions here  
  gl = new WebGLContext(16, 16);
}

let pids=[];

function cleanup_texture(pid)
{
  pid.o_textures.forEach( t => {
    // we did not create the texture. let's do nothing!!
    //gl.deleteTexture(t.id);
  });
  pid.o_textures = [];  
}
filter.configure_pid = function(pid)
{
  if (typeof pid.o_pid == 'undefined') {
      pid.o_pid = this.new_pid();
      pid.o_pid.i_pid = pid;
      pid.o_w = 0;
      pid.o_h = 0;
      pid.o_pf = '';
      pid.o_textures = [];
      pid.frame_pending = false;
      pid.cache_pck = null;
      pids.push(pid);
  }
  pid.o_pid.copy_props(pid);
  pid.o_pid.set_prop('Stride', null);
  pid.o_pid.set_prop('StrideUV', null);
  pid.o_pid.set_prop("CodecID", "raw");
  pid.o_pid.set_prop('PixelFormat','rgb');
  pid.o_pid.set_prop("StreamType", "Video");
}

filter.remove_pid = function(pid)
{
  cleanup_texture(pid);
  pids.splice(pids.indexOf(pid), 1);
}

filter.process = function()
{

  pids.forEach(pid => {
    if (pid.frame_pending) return;
    let ipck = pid.get_packet();
    if (!ipck) {
      if (pid.eos) pid.o_pid.eos = true;
      return;
    }
    //frame is already in gpu, simply forward
    if (ipck.frame_ifce_gl) {
      pid.o_pid.forward(ipck);
      pid.drop_packet();
      return;
    }

    //frame is an interface, force fetching data (no per-plane access in JS)
    let clone_pck = null;
    if (ipck.frame_ifce) {
      clone_pck = ipck.clone(pid.cache_pck);
      ipck = clone_pck;
    }
    /*
    the Python filters ToGLRGB currently sends output packets (opck) on output pid (opid), setting the following properties:
      opck.data=np.array([fboID, texID])
      opck.set_prop("texID",texID)
      opid.set_prop("texID",texID)
    we can retrieve the correct texID using either of the next lines
    */
    //let texID = parseInt(ipck.get_prop("texID",true)); // not working
    //let texID = parseInt(pid.get_prop("texID",true));  // not working
    let texID = (new Uint8Array(ipck.data, 0, 2))[1];
    /* 
    send new frame interface in blocking mode since the same set of textures is used for each packet
    */
    let opck = pid.o_pid.new_packet( 
        (pid, pck, plane_idx) => {
          if (plane_idx >= 1) return null; // we only deal with rgb buffers
          /* retrieve texID from constant or pid/pck property (does not work with pck)*/
          //return {"id":texID, 'fmt': gl.TEXTURE_2D};                     // variation #1, Ok
          return {'id':pid.get_prop("texID",true),'fmt':gl.TEXTURE_2D};    // variation #2, Ok
          //return {'id':pck.get_prop("texID",true),'fmt':gl.TEXTURE_2D};  // variation #3, Error: Invalid value in function jsf_pck_get_property
        },
        (pid, pck) => {
            let i_pid = pid.i_pid;
            i_pid.frame_pending = false;
        },
        true
    );
    opck.copy_props(ipck);
    // theoretically, we should be able to write texID in pid.opid, opck, or opck.data
    pid.o_pid.set_prop("texID",texID,true); // required for variation 2
    opck.set_prop("texID",texID,true);      // required for variation 3
    // in order to process these packets with ffenc, ffsws, etc, one would need to push back texture data in opck.data
    pid.frame_pending = true;
    opck.send();
    pid.drop_packet();
    if (clone_pck)
        clone_pck.discard();
  }); 

  return GF_OK;
}

