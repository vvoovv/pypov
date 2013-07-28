#!/usr/bin/env python

"""
PyPov-0.0.X Copyright (c) Simon Burton, 2003
See LICENSE file.

Some modifications by W.T. Bridgman, 2006-2007.

Mesh2 support and some modifications by Vladimir Elistratov, 2013

"""
from __future__ import nested_scopes
import sys, os
from math import sqrt

##################################################
class File:
	"""POV-Ray scene file object."""
	
	listItemsPerLine = 6
	
	def lock(self,item):
		#print "lock",id(item)
		assert self.__lock is None
		self.__lock = item
	
	def unlock(self,item):
		#print "unlock",id(item)
		assert self.__lock is item
		self.__lock = None
	
	def indent(self):
		self.__indent += 1
	
	def dedent(self):
		self.__indent -= 1
		assert self.__indent >= 0
	
	def block_begin(self):
		self.writeln( "{" )
		self.indent()
	
	def block_end(self):
		self.dedent()
		self.writeln( "}" )
		if self.__indent == 0:
			# blank line if this is a top level end
			self.writeln( )
	
	def writeln(self,s=""):
		#print "  "*self.__indent+s
		#assert self.__lock is None
		self.file.write("\t"*self.__indent+s+"\n")
	
	#######################################################
	# Public
	
	def __init__(self,fnam="out.pov",*items,**kwargs):
		"""Open POV-Ray scene file.

		Open file and write some components.

		@param fnam: POV-Ray scene file name.
		@type fnam: string

		"""
		assert type(fnam)==str
		self.file = open(fnam,"w")
		self.__indent = 0
		self.__lock = None
		for attr in kwargs: setattr(self,attr,kwargs[attr])
		self.write(*items)
	
	def include(self,*names):
		for name in names:
			self.writeln( '#include "%s"'%name )
		self.writeln()
	
	def declare(self,name,item):
		self.writeln("#declare %s = "%name)
		self.indent()
		self.write(item)
		self.dedent()
	
	def write(self,*items):
		"""Write commands into scene file."""
		for item in items:
			if type(item) == list:
				for _item in item:
					self.write(_item)
			elif type(item) == str:
				self.include(item)
			else:
				item.write(self)
	
	def close(self):
		"""Close POV-Ray scene file."""
		self.file.close()

class Vector:
	"""Generalized Vector class.
	
	Handles arbitrary component vectors."""
	def __init__(self,*args):
		if len(args) == 1:
			if isinstance(args[0],Vector):
				self.v = args[0].v
			else:
				self.v = list(args[0])
		else:
			self.v = args
		float(self.v[0]) # assert
	
	def __str__(self):
		return "<%s>"%(", ".join([str(x)for x in self.v]))
	
	def __repr__(self):
		return "Vector%s"%(tuple(self.v),)
	
	def __setitem__(self, i, item):
		self.v[i] = item
	
	def __getitem__(self, i):
		return self.v[i]
	
	def __mul__(self,other):
		" scalar multiplication "
		return Vector( [r*other for r in self.v] )
	
	def __rmul__(self,other):
		" scalar multiplication "
		return Vector( [r*other for r in self.v] )
	
	def __div__(self,other):
		return Vector( [r/other for r in self.v] )
	
	def __add__(self,other):
		return Vector([self.v[i]+other.v[i] for i in range(len(self.v))])
	
	def __sub__(self,other):
		return Vector([self.v[i]-other.v[i] for i in range(len(self.v))])
	
	def __neg__(self):
		return Vector([-x for x in self.v])
	
	def norm(self):
		"""Compute norm of vector."""
		r = 0.0
		for x in self.v:
			r += x*x
		return sqrt(r)
	
	def normalize(self):
		"""Normalize a vector"""
		r = self.norm()
		v = Vector( [x/r for x in self.v] )
		return v
	
	def dot(self,other):
		"""Dot product of two vectors"""
		r = 0.0
		for i in range(len(self.v)):
			r += self.v[i]*other.v[i]
		return r


class List:
	"""POV-Ray List class."""

	def __init__(self,l):
		self.l = l
	
	def write(self, file, name):
		l = self.l
		firstElementType = type(l[0])
		# calculating the number of items,
		# which may not equal to the number of elements len(self.l), see mesh2 POV-Ray documentation
		numItems = 0
		firstElementType = type(l[0])
		if (len(l)<2):
			numItems = len(l)
		else:
			for element in l:
				if (type(element)==firstElementType):
					numItems = numItems + 1
		file.writeln("%s { %s," % (name, numItems))
		file.indent()
		# printing list elements
		numItems = 0
		# treat complex elements separately
		if (firstElementType.__name__=="instance"):
			for element in l:
				element.write(file)
		else:
			line = ""
			for element in l:
				if (numItems>0):
					if (numItems % file.listItemsPerLine==0):
						file.writeln("%s," % line)
						line = ""
					else:
						line = "%s%s" % (line,",")
				if type(element) in (tuple, list):
					stringElement = "<%s>"%(",".join([str(x)for x in element]))
				else:
					stringElement = str(element)
				line = "%s%s" % (line,stringElement)
				if (type(element)==firstElementType):
					numItems = numItems + 1
			file.writeln(line)
		file.dedent()
		file.writeln("}")
	
	def __setitem__(self, i, item):
		self.l[i] = item
	
	def __getitem__(self, i):
		return self.l[i]

def map_arg(arg):
	"""Map an argument list to an appropriate format"""
	if type(arg) in ( tuple, list ):
		# if multiple-component, floating-point value, return a vector
		if len(arg) and hasattr( arg[0], "__float__" ):
			return Vector(arg)
	# else return the same format as the input value
	return arg

def flatten(seq):
	seq = list(seq)
	i=0
	while i < len(seq):
		if type(seq[i]) in (list,tuple):
			x = seq.pop(i)
			for item in x:
				seq.insert(i,item)
				i += 1
		else:
			i += 1
	return seq

######################################################
class Item:
	def __init__(self,name,args=[],opts=[],**kwargs):
		""" 
		Base class for POV objects.

		@param name: POV object name
		@param args: compulsory (comma separated?) pov args XX commas don't seem to matter?
		@param opts: eg. CSG items
		@param kwargs: key value pairs
		"""
		#print "Item",name,args,opts,kwargs
		self.name = name

		args = list(args)
		for i in range(len(args)):
			args[i] = map_arg(args[i])
		self.args = flatten( args )

		opts = list(opts)
		for i in range(len(opts)):
			opts[i] = map_arg(opts[i])
		self.opts = flatten( opts )

		self.kwargs = dict(kwargs) # take a copy
		for key,val in self.kwargs.items():
			if type(val)==tuple or type(val)==list:
				self.kwargs[key] = map_arg(val)
	
		#print "Item.__init__",self.name,self.args,self.opts
	def append(self, *opts, **kwargs):
		for item in flatten(opts):
			self.opts.append( item )
		for key,val in kwargs.items():
			self.kwargs[key]=val
	
	def begin_write(self, file):
		file.writeln( self.name )
		file.block_begin()
		if self.args:
			file.writeln( ", ".join([str(arg) for arg in self.args]) )
		file.lock(self) # assert
	
	def opt_write(self, file, opt):
		file.unlock(self) # assert
		if hasattr(opt,"write"):
			# opt is an Item
			opt.write(file)
		else:
			# whatever else
			file.writeln( str(opt) )
		file.lock(self) # assert

	def kwargs_write(self, file):
		writtenKwargs = {}
		if hasattr(self, "kwargsOrder"):
			for key in self.kwargsOrder:
				if key in self.kwargs:
					val = self.kwargs[key]
					if isinstance(val, List): val.write(file, key)
					else: file.writeln( "%s %s"%(key,val) )
					writtenKwargs[key] = True
		for key,val in self.kwargs.items():
			if key in writtenKwargs: continue
			if isinstance(val, List):
				# List may span several several lines.
				# We need to know the current File indent.
				# That's why List.write(file) is used
				val.write(file, key)
			else:
				file.writeln("%s %s"%(key,val))
	
	def end_write(self, file):
		file.unlock(self) # assert
		file.block_end()
	
	def write(self, file):
		#print "Item.write",self.name,self.args,self.opts
		self.begin_write(file)
		for opt in self.opts:
			#print opt
			self.opt_write(file,opt)
		self.kwargs_write(file)
		self.end_write(file)
	
	def __setattr__(self,name,val):
		self.__dict__[name]=val
		if name not in ["kwargs","args","opts","name","file"]: # "reserved" words
			self.__dict__["kwargs"][name]=map_arg(val)
			#print "Item",self.name,self.kwargs
	
	def __setitem__(self,i,item):
		if i < len(self.args):
			self.args[i] = map_arg(item)
		else:
			i += len(args)
			if i < len(self.opts):
				self.opts[i] = map_arg(item)
	
	def __getitem__(self,i):
		if i < len(self.args):
			return self.args[i]
		else:
			i += len(args)
			if i < len(self.opts):
				return self.opts[i]
	#def append(self, item):
		#self.opts.append( map_arg(item) )

def py2pov(name):
	# eg. Color -> color
	return name.lower() # XX underscores ?

class KWItem(object):
	"""Keyword item handler
	
	@param val: data value
	@type val: many formats allowed
	@param name: parameter name
	@type name: string
	"""
	def __init__(self,val,name=None):
		if name is None:
			name = py2pov( self.__class__.__name__) 
		self.name = name
		self.val = map_arg(val)
	
	def __str__(self):
		return "%s %s"%(self.name,self.val)

#
# Problem with forcing ordering of these keywords.  POVray ordering
# does seem to matter.
#
for name in "Color Translate Scale Rotate Angle".split(): 
	globals()[name] = type( name, (KWItem,), {} ) # nifty :)
#print globals().keys()

class Texture(Item):
	"""Create a texture"""
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"texture",(),opts,**kwargs)

class Pigment(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"pigment",(),opts,**kwargs)

class ColorEntry:
	"""Single line entry for a color map"""
	def __init__(self,x,color):
		self.x = x
		self.color = color
	
	def __str__(self):
		return "[ %s %s ]"%(self.x, self.color)

class ColorMap(Item):
	"""Assemble a color map from a collection of color entries."""
	def __init__(self,*opts):
		opts = list(opts)
		for i in range(len(opts)):
			x, color = opts[i]
			opts[i] = ColorEntry( x, color )
		Item.__init__(self,"color_map",(),opts)

class ImageMap(Item):
	"""Map an image to an object"""
	def __init__(self,filename,*opts,**kwargs):
		hf_type=filename.split(".")[-1]
		if hf_type=="jpg":
			hf_type="jpeg"
		if hf_type=="tif":
			hf_type="tiff"
		opts = list(opts)
		opts.insert(0,"\"%s\""%filename)
		opts.insert(0,hf_type)
		Item.__init__(self,"image_map",(),opts,**kwargs)

class Finish(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"finish",(),opts,**kwargs)

class Normal(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"normal",(),opts,**kwargs)

class Camera(Item):
	"""Create a camera object"""
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"camera",(),opts,**kwargs)

class LightSource(Item):
	"""Place light source object at specified position
	
	@param v: position
	@type v: tuple
	"""
	#def __init__(self,v,c,*opts,**kwargs):
		#Item.__init__(self,"light_source",(Vector(v),Vector(c)),
			#opts,**kwargs)
	def __init__(self,v,*opts,**kwargs):
		Item.__init__(self,"light_source",(Vector(v),),
			opts,**kwargs)

class Background(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"background",(),opts,**kwargs)

class Box(Item):
	def __init__(self,v1,v2,*opts,**kwargs):
		"""Construct a box object

		@param v1: vertex of box
		@type v1: Vector()
		@param v2: opposing vertex of box
		@type v2: Vector()
		"""
		Item.__init__(self,"box",(v1,v2),opts,**kwargs)

class Cylinder(Item):
	"""Construct cylinder object
	
	@param v1: coordinates of base point
	@type v1: L{Vector}
	@param v2: coordinates of cap point
	@type v2: L{Vector}
	@param r: radius of sphere
	@type r: float
	"""
	def __init__(self,v1,v2,r,*opts,**kwargs):
		" opts: open "
		Item.__init__(self,"cylinder",(v1,v2,r),opts,**kwargs)

class Plane(Item):
	def __init__(self,v,r,*opts,**kwargs):
		Item.__init__(self,"plane",(v,r),opts,**kwargs)

class Torus(Item):
	def __init__(self,r1,r2,*opts,**kwargs):
		Item.__init__(self,"torus",(r1,r2),opts,**kwargs)

class Cone(Item):
	"""Construct cylinder object
	
	@param v1: coordinates of base point
	@type v1: L{Vector}
	@param r1: radius of base
	@type r1: float
	@param v2: coordinates of cap point
	@type v2: L{Vector}
	@param r2: radius of cap point
	@type r2: float
	"""
	def __init__(self,v1,r1,v2,r2,*opts,**kwargs):
		" opts: open "
		Item.__init__(self,"cone", (v1,r1,v2,r2),opts,**kwargs)

class Sphere(Item):
	"""Sphere object
	
	@param v: position of center of sphere
	@type v: L{Vector}
	@param r: radius of sphere
	@type r: float
	"""
	def __init__(self,v,r,*opts,**kwargs):
		Item.__init__(self,"sphere",(v,r),opts,**kwargs)

class Plane(Item):
	def __init__(self,v,r,*opts,**kwargs):
		Item.__init__(self,"plane",(v,r),opts,**kwargs)

class LooksLike(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"looks_like",(),opts,**kwargs)

class Fog(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"fog",(),opts,**kwargs)

class Disc(Item):
	def __init__(self,v1,v2,r1,*opts,**kwargs):
		Item.__init__(self,"disc",(v1,v2,r1),opts,**kwargs)

##############################################
# Constructive Solid Geometry (CSG) components

class Union(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"union",(),opts,**kwargs)

class Intersection(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"intersection",(),opts,**kwargs)

class Difference(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"difference",(),opts,**kwargs)

class Merge(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"merge",(),opts,**kwargs)

class Polygon(Item):
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"polygon",(),opts,**kwargs)

class Text(Item):
	def __init__(self,font,string,thickness,offset,*opts,**kwargs):
		Item.__init__(self,"text",('ttf "'+font+'" "'+string+'"',thickness,offset),opts,**kwargs)

class ThickCylinder(Difference):
	def __init__(self,v1,v2,r1,r2,*opts,**kwargs):
		v1 = Vector(v1)
		v2 = Vector(v2)
		v = 0.001*(v2 - v1).normalize() # we make the second cyl a bit longer
		#print (v1,v2,r2), (v1-v,v2+v,r1), opts,kwargs
		Difference.__init__(
			self, Cylinder(v1,v2,r2), Cylinder(v1-v,v2+v,r1), *opts,**kwargs
		)

ThickCyl = ThickCylinder

##############################################

class Triangle(Item):
	def __init__(self,v1,v2,v3,*opts,**kwargs):
		Item.__init__(self,"triangle",(v1,v2,v3),opts,**kwargs)

class Mesh(Item):
	def __init__(self,file=None,*opts,**kwargs):
		Item.__init__(self,"mesh",(),opts,**kwargs)
		self.file = file # "reserved" word
		if file is not None:
			self.begin_write(file)
	
	def append(self,item):
		if self.file is not None:
			self.opt_write(self.file,item)
		else:
			Item.append(self,item)
	
	def write(self, file):
		#print "Item.write",self.name,self.args,self.opts
		if self.file is None:
			self.begin_write(file)
			for opt in self.opts:
				#print opt
				self.opt_write(file,opt)
		self.end_write(file)

class Mesh2(Item):
	kwargsOrder = [
		"vertex_vectors",
		"normal_vectors",
		"uv_vectors",
		"texture_list",
		"face_indices",
		"normal_indices",
		"uv_indices",
		"texture"
	]
	def __init__(self,*opts,**kwargs):
		Item.__init__(self,"mesh2",(),opts,**kwargs)

	def write(self, file):
		self.begin_write(file)
		self.kwargs_write(file)
		for opt in self.opts:
			#print opt
			self.opt_write(file,opt)
		self.end_write(file)

##############################################

class HeightField(Item):
	def __init__(self,filename,*opts,**kwargs):
		hf_type=filename.split(".")[-1]
		if hf_type=="jpg":
			hf_type="jpeg"
		opts = list(opts)
		opts.insert(0,"\"%s\""%filename)
		opts.insert(0,hf_type)
		Item.__init__(self,"height_field",(),opts,**kwargs)

from FieldIm import *

#
######################################################

X = x = Vector(1,0,0)
Y = y = Vector(0,1,0)
Z = z = Vector(0,0,1)
white = Texture(Pigment(color=(1,1,1)))


