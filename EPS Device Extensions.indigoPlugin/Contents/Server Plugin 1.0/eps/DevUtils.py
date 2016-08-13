#
# devcache - methods to store and find devices for plugin
#
#########################################################################

import indigo

class DevUtils:

	#
	# Initialize the class
	#
	def __init__ (self, pluginId):
		self.pluginId = pluginId
		self.cacheDevices()
	
	#	
	# Support log dump
	#
	def supportLogDump (self):
		logtext =  "\n#####################################################################\n"
		logtext += "# SUPPORT DEBUG LOG                                                 #\n"
		logtext += "#####################################################################\n"
		
		for devId, pluginId in self.devices.iteritems():
			devEx = indigo.devices[int(devId)]
			
			logtext += "#####################################################################\n"
			logtext += "# EPS DEVICE: " + devEx.name + "                                    #\n"
			logtext += "#####################################################################\n"
			
			logtext += ("=====================================================================\n")
			logtext += ("= pluginId: " + devEx.pluginId + ", typeId: " + devEx.deviceTypeId + "\n")
			#indigo.server.log(unicode(devEx))
			logtext += ("*********************************************************************\n")
			logtext += ("* STATES                                                            *\n")
			logtext += ("*********************************************************************\n")
			logtext += (unicode(devEx.states) + "\n")
			logtext += ("*********************************************************************\n")
			logtext += ("* CONFIGURATION                                                     *\n")
			logtext += ("*********************************************************************\n")
			logtext += (unicode(devEx.pluginProps) + "\n")
			
			if "device" in devEx.pluginProps:
				dev = indigo.devices[int(devEx.pluginProps["device"])]
				logtext += ("*********************************************************************\n")
				logtext += ("* DEVICE: " + dev.name + " (id: " + str(dev.id) + ", pluginId: " + dev.pluginId + ", typeId: " + dev.deviceTypeId + ")\n")
				logtext += ("*********************************************************************\n")
				logtext += ("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n")
				logtext += ("+ DEVICE INFO FOR " + dev.name + "                         +\n")
				logtext += ("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n")
				logtext += (unicode(dev) + "\n")
							
			logtext += ("=====================================================================\n\n\n")
			
		indigo.server.log(logtext)
	
	#
	# Find all devices belonging to this pluginId
	#	
	def cacheDevices (self):
		self.devices = {}
		devs = indigo.devices
		
		i = 0
		
		for dev in devs:
			if dev.pluginId == self.pluginId:
				self.devices[dev.id] = dev.deviceTypeId
				
	#
	# Determine if the device is in cache
	#
	def deviceInCache (self, findId):
		for devId, pluginId in self.devices.iteritems():
			if str(devId) == str(findId): return True
			
		return False
		
	#
	# Manually add device
	#
	def addDevice (self, dev):
		self.devices[int(dev.id)] = dev.deviceTypeId
		
	#
	# Find all monitored devices of our device
	#
	def cacheSubDevices (self, propName):
		self.subdevices = {}
		
		for devId, pluginId in self.devices.iteritems():
			dev = indigo.devices[int(devId)]
			if propName in dev.pluginProps:
				self.subdevices[int(dev.pluginProps[propName])] = True
				
	#
	# Manually add subdevice
	#
	def addSubDevice (self, devId):
		self.subdevices[int(devId)] = True
				
	#
	# Determine if subdevice is in cache
	#
	def subDeviceInCache (self, findId):
		for devId, tfVar in self.subdevices.iteritems():
			if str(devId) == str(findId): return True
			
		return False
		
	#
	# Get the devices associated with a subdevice
	#
	def devicesForSubDevice (self, subdevId, propName):
		retval = {}
		
		for devId, pluginId in self.devices.iteritems():
			dev = indigo.devices[int(devId)]
			
			if propName in dev.pluginProps:
				if str(dev.pluginProps[propName]) == str(subdevId):
					retval[dev.id] = True
					
		return retval
		
	#
	# Get type for device
	#
	def deviceTypeId (self, devId):
		return self.devices[int(devId)]
		
	#
	# Determine high float value from string and device state
	#
	def getHighFloatValue (self, dev, stateName, strVar):
		if stateName in dev.states == False: return ""
		
		if strVar == "" or float(dev.states[stateName]) > float(strVar):
			return str(dev.states[stateName])
		else:
			return strVar
			
	#
	# Determine low float value from string and device state
	#
	def getLowFloatValue (self, dev, stateName, strVar):
		if stateName in dev.states == False: return ""
		
		if strVar == "" or float(dev.states[stateName]) < float(strVar):
			return str(dev.states[stateName])
		else:
			return strVar

	#
	# Convert celsius to fahrenheit and fahrenheit to celsius
	#
	def convertTemperature (self, value, convertC = False, precision = 1):
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
	# Return menu of device states
	#
	def getDeviceStatesArray (self, filter="", valuesDict=None, typeId="", targetId=0, valueName="device"):
		myArray = [("option1", "SELECT A DEVICE")]
		
		try:		
			if valuesDict is None: return myArray
			if valueName in valuesDict == False: return myArray
			if valuesDict[valueName] == "": return myArray
				
			dev = indigo.devices[int(valuesDict[valueName])]
		except:
			return myArray
		
		stateAry = []
		
		for stateName, stateValue in dev.states.iteritems():
			option = (stateName, stateName)
			stateAry.append(option)
			
		return stateAry
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			
			