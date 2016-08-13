import datetime
import time
import indigo
import sys
import string
import calendar

import eps

parent = None # for debug logging

#
# Print library version - added optional return in 1.0.2
#
def libVersion (returnval = False):
	ver = "2.0.0"
	if returnval: return ver
	
	indigo.server.log ("##### DE Conversion %s #####" % ver)
	

#
# Debug log
#
def debugLog (value):
	if parent is None: return
	parent.debugLog (value)
	
	
#
# A watched device changed
#
def updateDevice (devId, changedStates):
	try:
		dev = indigo.devices[devId] # Our device
		
		if dev.pluginProps["chdevice"]:
			devEx = indigo.devices[int(dev.pluginProps["device"])] # Device we are watching
			
			if eps.valueValid (devEx.states, dev.pluginProps["states"]):
				value = devEx.states[dev.pluginProps["states"]]
			else:
				# It's a property
				if dev.pluginProps["states"] == "lastChanged": value = devEx.lastChanged
			
		else:
			devEx = ""
			value = indigo.variables[int(dev.pluginProps["variable"])]
	
		debugLog ("Processing changes on %s for value of '%s'" % (dev.name, unicode(value)))
	
		# ALWAYS TRUE
		if dev.pluginProps["action"] == "true":
			debugLog ("\tConverting to 'Always true'")
			setStates (dev, "true", "true", None, True)
		
		# ALWAYS FALSE
		if dev.pluginProps["action"] == "false":
			debugLog ("\tConverting to 'Always false'")
			dev.updateStateImageOnServer(indigo.kStateImageSel.None)
			setStates (dev, "false", "false", None, False)
			
		# VALUE TO BOOLEAN
		if dev.pluginProps["action"] == "bool":
			debugLog ("\tConverting value to boolean (bool)")
			value = unicode(value).lower()
			#if devEx.pluginProps["booleanstatetype"] == "float": value = float(value)
			
			truevalue = unicode(dev.pluginProps["truewhen"]).lower()
			falsevalue = unicode(dev.pluginProps["falsewhen"]).lower()
			
			statevalue = False
			
			if truevalue != "*else*":
				if value == truevalue: 
					statevalue = True
				else:
					if falsevalue == "*else*": statevalue = False
			
			if falsevalue != "*else*":
				if value == falsevalue: 
					statevalue = False
				else:
					if truevalue == "*else*": statevalue = True
			
			setStates (dev, unicode(statevalue).lower(), unicode(statevalue).lower(), None, statevalue)
			
		# BOOLEAN TO STRING
		if dev.pluginProps["action"] == "boolstr":
			debugLog ("\tConverting boolean value to string (boolstr)")
			value = unicode(value).lower()
			
			truevalue = unicode(dev.pluginProps["truewhen"])
			falsevalue = unicode(dev.pluginProps["falsewhen"])
			
			statevalue = falsevalue
			if value == "true": statevalue = truevalue
			
			setStates (dev, unicode(statevalue), unicode(statevalue))
			
			
		# STRING TO NUMBER
		if dev.pluginProps["action"] == "strtonum": 
			debugLog ("\tConverting string to number (strtonum)")
			value = unicode(value)
			
			if eps.valueValid (dev.pluginProps, "trimstart", True):
				if dev.pluginProps["trimstart"] != "0" and len(value) > int(dev.pluginProps["trimstart"]):
					self.debugLog("\tRemoving %i characters from beginning of string" % int(dev.pluginProps["trimstart"]))
					diff = int(dev.pluginProps["trimstart"])
					value = value[diff:len(value)]		
					
			if eps.valueValid (dev.pluginProps, "trimend", True):
				if dev.pluginProps["trimend"] != "0" and len(value) > int(dev.pluginProps["trimend"]):
					self.debugLog("\tRemoving %i characters from end of string" % int(dev.pluginProps["trimend"]))
					diff = int(dev.pluginProps["trimend"])
					diff = diff * -1
					value = value[:diff]		
					
			try:
				dec = string.find (value, '.')
				numtype = dev.pluginProps["numtype"]
				
				if dec > -1 and numtype == "int":
					indigo.server.log("Input value of %s on %s contains a decimal, forcing value to be a float.  Change the preferences for this device to get rid of this error." % (value, devEx.name), isError=True)
					numtype = "float"
				
				if numtype == "int": value = int(value)
				if numtype == "float": value = float(value)
					
				setStates (dev, value, value)
				
			except Exception as e:
				eps.printException(e)
				devEx.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
				return
						
	except Exception as e:
		eps.printException(e)	
	
#
# Set conversion custom states
#
def setStates (dev, stateDisplay, value, number = None, boolean = None, image = indigo.kStateImageSel.None):	
	try:
		dev.updateStateOnServer("statedisplay", stateDisplay)
		dev.updateStateOnServer("convertedValue", value)
		
		if number is not None: dev.updateStateOnServer("convertedNumber", number)
		if boolean is not None: dev.updateStateOnServer("convertedBoolean", boolean)
		
		dev.updateStateImageOnServer(image)
	
	except Exception as e:
		eps.printException(e)
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	