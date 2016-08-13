import indigo
import string
import eps

parent = None # for debug logging

#
# Debug log
#
def debugLog (value):
	if parent is None: return
	parent.debugLog (value)

#
# Print library version
#
def libVersion (returnval = False):
	ver = "2.0.0"
	if returnval: return ver
	
	indigo.server.log ("##### Conversions %s #####" % ver)


#
# Convert celsius to fahrenheit and fahrenheit to celsius
#
def temperature (value, convertC = False, precision = 1):
	try:
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
			
	except Exception as e:
			eps.printException(e)
			
