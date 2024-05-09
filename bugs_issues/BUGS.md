bugs should be visible by running file "bug_compilation.py"

#############
## pylance reports the following errors:
321  : "e2s" is not defined     
=> declared at line 328. should be moved before line 321)
3088 : "GF_PropVec2i" is not defined  
=> should be (PropVec2i * len(prop)) )
3164 :"_f" is not defined
=> ???
3240 : "URL" is not defined
=> should be raise Exception('Failed to create filter ' + fname + ': ' + e2s(err)) 
3833 : "not_in_final_flush" is not defined 
=> (???) there's a space/underscore typo in this line or previous one, but don't know where
3893 : "pname" is not defined
=> return _prop_to_python(pcode, propval)
3893 : "prop" is not defined
=> return _prop_to_python(pcode, propval)
4672 : "value" is not defined
=>def roll(self,value)
4712 : "value" is not defined
=>def seqnum(self, value)
4817 : "url" is not defined
=> replace url with _url)

###############
## there are trailing ";" in python code (copy paste from javascript?

###############
## set_prop (p,v GF_PROP_STRING|GF_PROP_STRING_LIST|GF_PROP_4CC)
@@ 2080
- for str in self.headers_out:
-     hdrs[i] = create_string_buffer(str.encode('utf-8'))
+ for s in self.headers_out:
+     hdrs[i] = create_string_buffer(s.encode('utf-8'))

@@ 3062
- for str in list:
-     prop_val.value.string_list.vals[i] = create_string_buffer(str.encode('utf-8'))
+ for p in prop:
+     prop_val.value.string_list.vals[i] = create_string_buffer(p.encode('utf-8'))

@@ 3076
- for str in list:
-     prop_val.value.string_list.vals[i] = create_string_buffer(str.encode('utf-8'))
+ for p in prop:
+     prop_val.value.string_list.vals[i] = create_string_buffer(p.encode('utf-8'))


NB: GF_PROP_STRING_LIST still does not work (incompatible ctypes pointers)

###############
## set_prop (p,v GF_PROP_FRACTION|gf_PROP_FRACTION64)
@@ 3003
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


same modifications for gpac.GF_PROP_FRACTION64 @@ 30013

################
## filter.ID may be None
@@ 2016
- @property
- def ID(self):
-   return _libgpac.gf_filter_get_id(self._filter).decode('utf-8')

+ @property
+ def ID(self):
+   try:
+       return _libgpac.gf_filter_get_id(self._filter).decode('utf-8')
+   except:
+       return None ##'_'+hex(id(self))[2:]+'_'

#################
## duplicated custom filters in session._filters
@@ 3244
- session._filters.append(self)

+ if not self._filter in [f._filter for f in session._filters]:
+   session._filters.append(self)


