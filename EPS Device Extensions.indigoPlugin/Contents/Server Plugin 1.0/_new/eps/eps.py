import indigo
import string
import linecache # exception reporting
import sys # exception reporting

import conv # only until all previous EPS libraries prior to 2.1.0 routed out

parent = None # for debug logging

#
# Debug log - 2.0.4
#
def debugLog (value):
	if parent is None: return
	parent.debugLog (value)

#
# Print library version - added optional return in 2.0.1
#
def libVersion (returnval = False):
	ver = "2.1.0"
	if returnval: return ver
	
	indigo.server.log ("##### EPS LIB %s #####" % ver)
		
	
# Check validity of a value in a dictionary 2.0.1
def valueValid (dict, value, ifBlank=False):
	if dict:
		if value != "":
			if value in dict:
				if ifBlank:
					if unicode(dict[value]) != "": return True
				else:
					return True
					
	return False

#	
# Check validity of a value in dictionary and return that value if valid or default value if not - 2.05
#
def getDictValue (dict, value, default="No value"):
	default = unicode(default) # always return a string
	
	if valueValid (dict, value, True):
		return unicode(dict[value])
	else:
		return default
	

					
#
# Check if props changed between devices
#
def dictChanged (origDict, newDict):
	if origDict.pluginProps and newDict.pluginProps:
		for key, value in origDict.pluginProps.iteritems():
			if newDict.pluginProps[key] != value: return True
					
	return False
		
#
# Check if a device is newly created - 2.0.2
#
def isNewDevice (origDev, newDev):
	if len(origDev.pluginProps) == 0 and len(newDev.pluginProps) != 0: return True
	
	return False
		
		
#
# Return debug header 1 - 2.0.1
#
def debugHeader (label, character = "#"):
	# Return 69 character strings
	ret =  "\n\n" + debugHeaderEx(character)
	ret += debugLine(label, character)
	ret += debugHeaderEx(character)

	return ret

#
# Return debug header 2 - 2.0.1
#
def debugHeaderEx (character = "#"):
	# Return 69 character strings
	
	if character == "#":
		ret =  "#####################################################################\n"
			
	elif character == "=":
		ret =  "=====================================================================\n"
			
	elif character == "-":
		ret =  "---------------------------------------------------------------------\n"
			
	elif character == "+":
		ret =  "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
				
	elif character == "*":
		ret =  "*********************************************************************\n"
		
	elif character == "!":
		ret =  "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
		
	return ret

#
# Return debug line - 2.0.1
#	
def debugLine (label, character = "#"):
	# Return 69 character strings
	return "%s %s %s\n" % (character, label.ljust(65), character)
	
	
#
# Print exception details
#
def printException (e):
	exc_type, exc_obj, tb = sys.exc_info()
	f = tb.tb_frame
	lineno = tb.tb_lineno
	filenameEx = f.f_code.co_filename
	filename = filenameEx.split("/")
	filename = filename[len(filename)-1]
	filename = filename.replace(".py", "")
	filename = filename.replace(".pyc","")
	linecache.checkcache(filename)
	line = linecache.getline(filenameEx, lineno, f.f_globals)
	exceptionDetail = "Exception in %s.%s line %i: %s\n\t\t\t\t\t\t\t CODE: %s" % (filename, f.f_code.co_name, lineno, str(e), line.replace("\t",""))
	indigo.server.log (exceptionDetail, isError=True)	
	
################################################################################
# DEPRECIATED METHODS
################################################################################	

#
# Convert celsius to fahrenheit and fahrenheit to celsius 2.0.1
#
def convertTemperature (value, convertC = False, precision = 1):
	debugLog (debugHeader("convertTemperature is depreciated in 2.1.0, use conv.temperature instead", "!"))
	return conv.temperature (value, convertC, precision)

	# DEPRECIATED - REDIRECT TO conv.temperature (2.1.0)

	if convertC:
		# Convert value to celsius
		value = float(value)
		value = (value - 32) / 1.8000
		value = round(value, precision)
		
		if precision == 0: return int(value)
		
		return value
		
	else:
		# Default: convert value to fahrenheit
		value = float(value)
		value = (value * 1.8000) + 32
		value = round(value, precision)
		
		if precision == 0: return int(value)
		
		return value
	
#
# Check validity of a state on a device
#
def stateValid (dev, value, ifBlank=False):
	debugLog (debugHeader("stateValid is depreciated in 2.0.1, use valueValid instead", "!"))
	if dev.states: return valueValid (dev.states, value, ifBlank)
	return False
	
	# DEPRECIATED - REDIRECT TO valueValid (2.0.1)
	
	
	if dev.states:
		if value in dev.states:
			if ifBlank:
				if unicode(dev.states[value]) != "": return True
			else:
				return True
	
	return False
		
#
# Check validity of a plugin prop on a device
#
def propValid (dev, value, ifBlank=False):
	debugLog (debugHeader("propValid is depreciated in 2.0.1, use valueValid instead", "!"))
	if dev.pluginProps: return valueValid (dev.pluginProps, value, ifBlank)
	return False
	
	# DEPRECIATED - REDIRECT TO valueValid (2.0.1)
	
	if dev.pluginProps:
		if value in dev.pluginProps:
			if ifBlank:
				if unicode(dev.pluginProps[value]) != "": return True
			else:
				return True
	
	return False	
	
	
	
#
# Check if props changed between devices
#
def propsChanged (origDev, newDev):
	debugLog (debugHeader("propsChanged is depreciated in 2.0.3, use dictChanged instead", "!"))
	return dictChanged (origDev, newDev)

	# DEPRECIATED - REDIRECT TO dictChanged (2.0.3)

	if origDev.pluginProps and newDev.pluginProps:
		for propName, propValue in origDev.pluginProps.iteritems():
			if newDev.pluginProps[propName] != propValue: return True
					
	return False
	
#
# Get value of dictionary key if valid
#
def getDictValueEx (dict, value):
	return getDictValue (dict, value)
	
	# DEPRECIATED - REDIRECT TO getDictValue (2.0.5)

	if dict:
		if value:
			if value in dict:
				return dict[value]
				
	return "No value"
	
	