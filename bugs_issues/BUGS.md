some of the bugs are illustrated by running minimal example bugs_compilation.py
as I have made lots of corrections in my libgpac.py, line numbers may not be 100% accurate

#############
## pylance reports the following errors:
(errors and possible solutions below

@@ 321  : "e2s" is not defined     
=> e2s declared at line 328. should be moved before line 321)  
@@ 3088 : "GF_PropVec2i" is not defined  
=> should be (PropVec2i * len(prop))   
@@ 3164 :"_f" is not defined  
=> ???  
@@ 3240 : "URL" is not defined  
=> should be raise Exception('Failed to create filter ' + fname + ': ' + e2s(err))  
@@ 3833 : "not_in_final_flush" is not defined  
=> there's a space/underscore typo in this line or previous one, but don't know where.  (not_in_final_flush = not in_final_flush ?)
@@ 3893 : "pname" is not defined  
=> return _prop_to_python(pcode, propval)  
@@ 3893 : "prop" is not defined  
=> return _prop_to_python(pcode, propval)  
@@ 4672 : "value" is not defined  
=>def roll(self,value)  
@@ 4712 : "value" is not defined  
=>def seqnum(self, value)  
@@ 4817 : "url" is not defined  
=> if not fio_ref.factory.root_obj.exists(_url):

###############
## there are trailing ";" in python code (copy paste from javascript)
@@ 2083  
@@ 2093  
@@ 2112  
@@ 4805  
@@ 4876  

###############
## set_prop (p,v GF_PROP_STRING|GF_PROP_STRING_LIST|GF_PROP_4CC)
see previous (email) comments.  
the code overwrites the type str in locals() dict, which makes it impossible to later transtype using str() (@@3051)

@@ 2080
```
- for str in self.headers_out:
-     hdrs[i] = create_string_buffer(str.encode('utf-8'))
+ for header in self.headers_out:
+     hdrs[i] = create_string_buffer(header.encode('utf-8'))
```
@@ 3062
```
- for str in list:
-     prop_val.value.string_list.vals[i] = create_string_buffer(str.encode('utf-8'))
+ for p in prop:
+     prop_val.value.string_list.vals[i] = create_string_buffer(p.encode('utf-8'))
```

@@ 3076
```
- for str in list:
-     prop_val.value.string_list.vals[i] = create_string_buffer(str.encode('utf-8'))
+ for p in prop:
+     prop_val.value.string_list.vals[i] = create_string_buffer(p.encode('utf-8'))
```


NB: GF_PROP_STRING_LIST still does not work (incompatible ctypes pointers)  

###############
## set_prop (p,v GF_PROP_FRACTION|gf_PROP_FRACTION64)
is_integer() is not defined (javascript spotted!)  
the code does not ensure that frac.num is an int

@@ 3003
```
- elif is_integer(prop):
-   prop_val.value.frac.num = prop
-   prop_val.value.frac.den = 1
- else:
-   prop_val.value.frac.num = 1000*prop
-   prop_val.value.frac.den = 1000
            
+ elif isinstance(prop,int) or ( isinstance(prop,float) and prop%1==0) :
+    prop_val.value.frac.num = int(prop)
+    prop_val.value.frac.den = 1
+ else:
+    prop_val.value.frac.num = int(1000*prop)
+    prop_val.value.frac.den = 1000
```

same modifications for gpac.GF_PROP_FRACTION64 @@ 30013

NB: documentation states: "Properties values are automatically converted to or from python types whenever possible. Types with no python equivalent (vectors, fractions) are defined as classes in python."   
But python has fractions.Fraction in standard lib  

################
## filter.ID may be None
filter.ID may be None (or is it a bug in C lib), but the case is not properly handled by libgpac
NB: I would naïvely expect all filters to have an ID (unique).

@@ 2016
```
- @property
- def ID(self):
-   return _libgpac.gf_filter_get_id(self._filter).decode('utf-8')

+ @property
+ def ID(self):
+   try:
+       return _libgpac.gf_filter_get_id(self._filter).decode('utf-8')
+   except:
+       return None ##'_'+hex(id(self))+'_' ## should we overwrite None ID with python specific id?
```

#################
## clock_hint_mediatime
(not that sure, but at least does not raise error!)

@@ 3424   byref() argument must be a ctypes instance, not '_ctypes.PyCStructType'
```
- @property 
- def clock_hint_mediatime(self):
-   val = Fraction64
-   _libgpac.gf_filter_get_clock_hint(self._filter, None, byref(val))
-   return val.value

+ @property 
+ def clock_hint_mediatime(self):
+   val = Fraction64()
+   _libgpac.gf_filter_get_clock_hint(self._filter, None, byref(val))
+   return val
```


#################
## opid_prop
filter.opid_prop() does not work. the return statement in def _pid_prop() is erronated
@@2675
```
- return self._pid_prop_ex(self, prop_name, pid, False)
+ return self._pid_prop_ex(prop_name, pid, False)
```

#################
## duplicated custom filters in session._filters
Custom filters are inserted twice in fs._filters
once as gpac.Filter (@@ 3240)
once as __main__.FilterCustom (@@3247)
both have the same value for `_filter` ( assert (fs._filters[1]._filter==fs._filters[2]._filter) )

Is it an intended behavior? and if not, then we could we *either*:  
=>prevent custom filter insertion (but then, we cannot access FilterCustom specific fields and methods):

(@@3247)
```
- session._filters.append(self)

+ if not self._filter in [f._filter for f in session._filters]:
+    session._filters.append(self) ## should never happen!
```

=>remove the gpac.Filter instance added by libgpac and add the FilterCustom
(@@3247)
```
- session._filters.append(self)

+ session._filters.pop()
+ session._filters.append(self)
```

###########
## filter.remove() sometimes does not work
see additional tests in bug_compilation.py, layout=2
