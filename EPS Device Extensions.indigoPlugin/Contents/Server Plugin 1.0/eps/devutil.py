import datetime
import time
import indigo
import sys
import string

parent = ""

#
# Print library version
#
def libVersion ():
	indigo.server.log ("##### EPS DEV UTIL 1.0.0 #####")

#
# Get specified states of specified devices and return in a list dict
#
def stateValueDict (devices, states):
	parent.debugLog ("Values")

#
# Set state default values
#
def setStateDefaults (dev, stateAry, type = "string", option = ""):
	for s in stateAry:
		if s in dev.states:
			value = ""
			uivalue = ""
				
			if (type == "string" or type == "date" or type == "datetime" or type == "time") and dev.states[s] == "":
				if type == "date": value = indigo.server.getTime().strftime("%Y-%m-%d")
				if type == "datetime": value = indigo.server.getTime().strftime("%Y-%m-%d %H:%M:%S")
				if type == "time":
					if option == "": 
						value = indigo.server.getTime().strftime("%H:%M:%S")
					else:
						value = indigo.server.getTime().strftime(option)
			
			if uivalue == "": uivalue = unicode(value)
				
			dev.updateStateOnServer (s, value=value, uivalue = uivalue)
























