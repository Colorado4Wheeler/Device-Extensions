import datetime
import time
import indigo
import sys
import dtutil

################################################################################
# RELEASE NOTES
#
# 1.0.0
#	- I really don't like to talk about my flare
# 2.0.0
#	- Total rewrite
# 2.1.0
#	- Look for devicelist - devicelist3 in props
#	- Trap error in watchStateChanged if state missing from original device
################################################################################

class cache:

	#
	# Initialize the class
	#
	def __init__ (self, parent, pluginId, pollingMode = "realTime", pollingInterval = 1, pollingFrequency = "s"):
		self.version = "2.2.1"
		
		self.pluginId = pluginId
		self.parent = parent
						
		self.setPollingOptions (pollingMode, pollingInterval, pollingFrequency)
		
		self.devices = {}
		self.deviceIdCache = []
		
		self.deviceChangeCache = {}
		self.deviceChangeCacheThreshold = 3 # How many seconds repetitive device updates must wait until being processed
		
		self.dumpTxt = ""
		
		self.subDeviceVars = ["device", "device2", "device3", "device4", "device5", "device6", "device7", "device8", "devicelist", "devicelist2", "devicelist3"]
		
		#self.cacheDevices()
		
		
		self.parent.debugLog ("Cache initialized for " + self.pluginId)
			
	#
	# Set polling options
	#
	def setPollingOptions (self, pollingMode, pollingInterval, pollingFrequency):
		self.pollingMode = pollingMode
		self.pollingInterval = int(pollingInterval)
		self.pollingFrequency = pollingFrequency
		
		self.parent.debugLog ("Polling set to: Mode = " + pollingMode + " | Interval = " + str(pollingInterval) + " | Frequency = " + pollingFrequency)
	
	#
	# Update pluginPrefs - 2.2.0
	#	
	def setPluginPrefs (self, pluginPrefs):
		self.pluginPrefs = pluginPrefs
		self.cachePluginPrefs()
	
	#
	# Print library version
	#
	def libVersion (self):
		indigo.server.log (u"##### EPS Cache %s #####" % self.version)
		
	################################################################################
	# PLUGIN ROUTINES - 2.2.0
	################################################################################
	def cachePluginPrefs (self):
		self.parent.debugLog("Caching plugin preferences")
		self.updateCache (self.parent.pluginPrefs, 0, "PLUGIN PREFERENCES", self.pluginId)
		


	################################################################################
	# DEVICE ROUTINES
	################################################################################
	
	#
	# Remove main device from cache
	#
	def removeDevice (self, devId):
		if devId in self.devices: 
			del self.devices[devId]
			self.deviceIdCache.remove (str(devId))
		
		#self.dictDump (self.devices)
		#self.parent.debugLog(unicode(self.deviceIdCache))
		
		return
	
	#
	# Add device id to cached ids
	#
	def cacheDeviceId (self, devId):
		devId = str(devId)
		
		for cacheId in self.deviceIdCache:
			if cacheId == devId: return
			
		self.deviceIdCache.append(devId)
		
		#self.parent.debugLog ("Device id cache updated: " + unicode(self.deviceIdCache))
		
		return
		
	#
	# Check if a device id is being monitored
	#
	def deviceInCache (self, devId):
		devId = str(devId)
		
		for cacheId in self.deviceIdCache:
			if cacheId == devId: return True
			
		return False
		
	#
	# Find all sub devices for the plugin device
	#
	def getSubDevices (self, dev):
		retval = []
		
		for s in self.subDeviceVars:
			if s in dev.pluginProps:
				if dev.pluginProps[s] != "":
					retval.append(dev.pluginProps[s])
					
		return retval
	
	#
	# Find all devices belonging to this pluginId
	#	
	def cacheDevices (self):
		for dev in indigo.devices.iter("self"):
			self.updateCache (dev.pluginProps, dev.id, dev.name, dev.deviceTypeId)
			
		return
		
		### DEPRECIATED IN 2.2.0 ###
		
		for dev in indigo.devices.iter("self"):
			# Add to cache if not already there
			deviceExists = False
			for devId, devProps in self.devices.iteritems():
				if str(devId) == str(dev.id): deviceExists = True
				
			if deviceExists == False:
				self.cacheDeviceId (dev.id)
				
				devProps = {}
				devProps["name"] = dev.name
				devProps["id"] = dev.id
				devProps["deviceTypeId"] = dev.deviceTypeId
				devProps["subDevices"] = {}
				
				for varname in self.subDeviceVars:
					if varname in dev.pluginProps:
						if dev.pluginProps[varname] != "":
							if varname == "devicelist" or varname == "devicelist2" or varname == "devicelist3":
								#indigo.server.log(unicode(dev.pluginProps[varname]))
								counter = 1
								for sDevId in dev.pluginProps[varname]:
									sDev = indigo.devices[int(sDevId)]
							
									devProps["subDevices"][sDev.id] = self.addSubProps (sDev, varname + "_" + str(counter))
									
									counter = counter + 1
									
							else:							
								sDev = indigo.devices[int(dev.pluginProps[varname])]
								devProps["subDevices"][sDev.id] = self.addSubProps (sDev, varname)
				
				self.devices[dev.id] = devProps
			
			else:
				# Requery subdevices
				d = self.devices[dev.id]
				for varname in self.subDeviceVars:
					if varname in dev.pluginProps:
						if dev.pluginProps[varname] != "":
							varPresent = False
							for subId, subProps in d["subDevices"].iteritems():
								if subProps["varName"] == varname: varPresent = True
							
							if varPresent == False:		
								# New sub device found - shortened in 2.2.0
								sDev = indigo.devices[int(dev.pluginProps[varname])]
								sProp = self.addSubProps (sDev, varname)
								self.devices[dev.id]["subDevices"][sDev.id] = sProp
				
						
				
		#self.dictDump (self.devices)
		
		return
		
	#
	# Loop through provided dict and add/update matching subdevices in cache - 2.2.0
	#
	def updateCache (self, dict, devExId, devExName, devExTypeId):
		# Add to cache if not already there
		deviceExists = False
		for devId, devProps in self.devices.iteritems():
			if str(devId) == str(devExId): deviceExists = True
		
		if deviceExists == False:
			self.parent.debugLog (u"Adding %s and any of its subdevices to cache" % devExName)
			self.cacheDeviceId (devExId)
		
			devProps = {}
			devProps["name"] = devExName
			devProps["id"] = devExId
			devProps["deviceTypeId"] = devExTypeId
			devProps["subDevices"] = {}
		
			for varname in self.subDeviceVars:
				if varname in dict:
					if dict[varname] != "":
						if varname == "devicelist" or varname == "devicelist2" or varname == "devicelist3":
							#indigo.server.log(unicode(dev.pluginProps[varname]))
							counter = 1
							for sDevId in dict[varname]:
								sDev = indigo.devices[int(sDevId)]
								self.parent.debugLog (u"\tAdding device list item %s from %s" % (sDev.name, devExName))
							
								devProps["subDevices"][sDev.id] = self.addSubProps (sDev, varname + "_" + str(counter))
							
								counter = counter + 1
							
						else:							
							sDev = indigo.devices[int(dict[varname])]
							self.parent.debugLog (u"\tAdding device item %s from %s" % (sDev.name, devExName))
							devProps["subDevices"][sDev.id] = self.addSubProps (sDev, varname)
		
			self.devices[devExId] = devProps
	
		else:
			# Requery subdevices
			d = self.devices[devExId]
			for varname in self.subDeviceVars:
				if varname in dict:
					if dict[varname] != "":
						varPresent = False
						for subId, subProps in d["subDevices"].iteritems():
							if subProps["varName"] == varname: varPresent = True
					
						if varPresent == False:		
							# New sub device found - shortened in 2.2.0
							sDev = indigo.devices[int(dict[varname])]
							sProp = self.addSubProps (sDev, varname)
							self.devices[devExId]["subDevices"][sDev.id] = sProp
		
		
	#
	# Return sub-device props (1.2.0)
	#
	def addSubProps (self, sDev, varname):
		self.cacheDeviceId (sDev.id)
		
		sProp = {}
		sProp["name"] = sDev.name
		sProp["id"] = sDev.id
		sProp["deviceTypeId"] = sDev.deviceTypeId
		sProp["varName"] = varname
		sProp["watchStates"] = []
		sProp["watchProperties"] = []
		
		return sProp
		
	#
	# Add sub device variable name to the cache list and re-cache
	#
	def addSubDeviceVar (self, value, reload = True):
		self.subDeviceVars.append(value)
		
		if reload: 
			self.cacheDevices()
			self.parent.debugLog(self.subDeviceVars)
			
				
	################################################################################
	# SUBDEVICE ROUTINES
	################################################################################
	
	#
	# Check if one of our sub device var names changed
	#
	def didSubDeviceVarChange (self, origDev, newDev):
		for varname in self.subDeviceVars:
			if varname in origDev.pluginProps:
				if origDev.pluginProps[varname] != newDev.pluginProps[varname]: return True
	
		return False
		
	#
	# Find all plugin devices with this devId as a subdevice
	#
	def getDevicesForSubId (self, subDevId):
		retary = []
		
		for devId, devProps in self.devices.iteritems():
			for subId, subProps in devProps["subDevices"].iteritems():
				if str(subId) == str(subDevId): retary.append(str(devId))
		
		if len(retary) == 0: return False
		
		return retary
	
	#
	# Check subdevices from a device update and make sure they are correct
	#
	def verifySubDevices (self, origDev, newDev):
		if self.didSubDeviceVarChange (origDev, newDev) == False: return
		needsCached = False
		
		for varname in self.subDeviceVars:
			if varname in origDev.pluginProps:
				if origDev.pluginProps[varname] != newDev.pluginProps[varname]:
					if origDev.pluginProps[varname] != "": # Make sure it wasn't blank before or we get an error
						# The device changed, remove it and plan to re-cache
						for devId, devProps in self.devices.iteritems():
							if str(devId) == str(origDev.id):
								self.parent.debugLog (origDev.name + " " + varname + " changed from device " + origDev.pluginProps[varname] + " to " + newDev.pluginProps[varname])
								del self.devices[devId]["subDevices"][int(origDev.pluginProps[varname])]
								self.deviceIdCache.remove (origDev.pluginProps[varname]) # So we don't monitor it any longer
								needsCached = True
							
		if needsCached:
			self.cacheDevices()
			return True # To let the caller know they may need to rebuild watched states, etc
			
		return False
	
	#
	# Add a watch state to a sub device
	#
	def addWatchState (self, stateName, subDevId = "*", deviceTypeId = "*", mainDevId = "*"):
		self.parent.debugLog(u"Adding watched state %s on sub device %s, device type %s, main device %s" % (stateName, subDevId, deviceTypeId, mainDevId))
		
		for devId, devProps in self.devices.iteritems():
			if devProps["deviceTypeId"] == deviceTypeId or deviceTypeId == "*":
				if str(devId) == str(mainDevId) or mainDevId == "*":
					for subId, subProps in devProps["subDevices"].iteritems():
						if str(subId) == str(subDevId) or subDevId == "*":
							# Match
							s = subProps["watchStates"]
							
							# Make sure we aren't already watching this state
							isWatched = False
							for st in s:
								if st == stateName: isWatched = True
								
							if isWatched == False:
								s.append(stateName)
								subProps["watchStates"] = s
								self.devices[devId]["subDevices"][subId] = subProps
						
		#self.dictDump (self.devices)
		
		return
		
	#
	# Add a watch property to a sub device - 2.2.1
	#
	def addWatchProperty (self, propName, subDevId = "*", deviceTypeId = "*", mainDevId = "*"):
		self.parent.debugLog(u"Adding watched property %s on sub device %s, device type %s, main device %s" % (propName, subDevId, deviceTypeId, mainDevId))
		
		for devId, devProps in self.devices.iteritems():
			if devProps["deviceTypeId"] == deviceTypeId or deviceTypeId == "*":
				if str(devId) == str(mainDevId) or mainDevId == "*":
					for subId, subProps in devProps["subDevices"].iteritems():
						if str(subId) == str(subDevId) or subDevId == "*":
							# Match
							s = subProps["watchProperties"]
							
							# Make sure we aren't already watching this state
							isWatched = False
							for st in s:
								if st == propName: isWatched = True
								
							if isWatched == False:
								s.append(propName)
								subProps["watchProperties"] = s
								self.devices[devId]["subDevices"][subId] = subProps
						
		#self.dictDump (self.devices)
		
		return
		
	#
	# Add change to device change cache
	# EXPERIMENTAL - NOT CURRENTLY IMPLEMENTED
	#
	def addDeviceChange (self, devId, value):
		d = indigo.server.getTime()
		
		isCached = False
		for cacheDevId, cacheProps in self.deviceChangeCache.iteritems():
			if str(cacheDevId) == str(devId):
				isCached = True
				break
				
		if isCached == False:
			devCache = {}
			devCache["id"] = devId
			devCache["changedStates"] = []
			devCache["added"] = d.strftime("%Y-%m-%d %H:%M:%S")
			devCache["updated"] = d.strftime("%Y-%m-%d %H:%M:%S")
			devCache["changedStates"].append(value)			
			
			self.deviceChangeCache[int(devId)] = devCache
		else:
			devCache = self.deviceChangeCache[int(devId)]
			
			isStored = False
			for s in devCache["changedStates"]:
				if s == value: isStored = True
				
			if isStored == False:
				self.deviceChangeCache[int(devId)]["changedStates"].append(value)
			else:
				self.deviceChangeCache[int(devId)]["updated"] = d.strftime("%Y-%m-%d %H:%M:%S")
				
		self.dictDump (self.deviceChangeCache)
		
	#
	# Can device change be reported
	# EXPERIMENTAL - NOT CURRENTLY IMPLEMENTED
	#
	def checkDeviceChange (self, devId):
		d = indigo.server.getTime()
		
		for cacheDevId, cacheProps in self.deviceChangeCache.iteritems():
			if str(cacheDevId) == str(devId):
				t = datetime.datetime.strptime (self.deviceChangeCache[int(devId)]["added"], "%Y-%m-%d %H:%M:%S")
				s = dtutil.DateDiff("seconds", d, t)
				indigo.server.log(str(s) + " seconds have passed")
				
		return False
		
	#
	# Return array of monitor states as if all changed (in case caller needs to do an immediate update of all states and relies on this lib)
	#
	def deviceUpdate (self, dev):
		retval = {}
		
		for devId, devProps in self.devices.iteritems():
			if str(devId) == str(dev.id):
				ret = {}
				ret["id"] = devId
				ret["stateChanges"] = []
			
				for subId, subProps in devProps["subDevices"].iteritems():
					for s in subProps["watchStates"]:
						ret["stateChanges"].append(s)
						
				if len(ret["stateChanges"]) > 0:
					retval[devId] = ret
					
		return retval
		
	#
	# Check if a monitored state has changed
	#
	def watchedStateChanged (self, origDev, newDev):
	
		retval = {}
		
		if self.deviceInCache (origDev.id) == False: return False
		
		if self.okToPoll (origDev.id):
			for devId, devProps in self.devices.iteritems():
				ret = {}
				ret["id"] = devId
				ret["stateChanges"] = []
				
				for subId, subProps in devProps["subDevices"].iteritems():
					if str(subId) == str(origDev.id):
						for s in subProps["watchStates"]:
							if s in newDev.states:
								if s in origDev.states: # 1.2.0 - prevents an error if the state is missing from orig
									if origDev.states[s] != newDev.states[s]:
										ret["stateChanges"].append(s)
										#self.addDeviceChange (origDev.id, s)
										self.parent.debugLog("%s watched state %s has changed for %s" % (origDev.name, s, devProps["name"]))
									
				if len(ret["stateChanges"]) > 0:
					retval[devId] = ret
		
			if len(retval) == 0:
				#self.parent.debugLog("The monitored device " + origDev.name + " was updated but a watched state did not change")
				return False
			else:
				#self.checkDeviceChange (origDev.id)
				self.parent.debugLog("The monitored device " + origDev.name + " was updated and a watched state changed")
				return retval
					
		else:
			self.parent.debugLog("The monitored device " + origDev.name + " was updated but is not eligible to be polled yet")
		
		return False # Failsafe
		
	#
	# Check if a monitored property has changed - 2.2.1
	#
	def watchedPropertyChanged (self, origDev, newDev):
	
		retval = {}
		
		if self.deviceInCache (origDev.id) == False: return False
		
		if self.okToPoll (origDev.id):
			for devId, devProps in self.devices.iteritems():
				ret = {}
				ret["id"] = devId
				ret["stateChanges"] = []
				
				for subId, subProps in devProps["subDevices"].iteritems():
					if str(subId) == str(origDev.id):
						for s in subProps["watchProperties"]:
							if s == "lastChanged":
								if origDev.lastChanged != newDev.lastChanged:
									ret["stateChanges"].append(s)
									self.parent.debugLog("%s watched property %s has changed for %s" % (origDev.name, s, devProps["name"]))
									
				if len(ret["stateChanges"]) > 0:
					retval[devId] = ret
		
			if len(retval) == 0:
				#self.parent.debugLog("The monitored device " + origDev.name + " was updated but a watched state did not change")
				return False
			else:
				#self.checkDeviceChange (origDev.id)
				self.parent.debugLog("The monitored device " + origDev.name + " was updated and a watched property changed")
				return retval
					
		else:
			self.parent.debugLog("The monitored device " + origDev.name + " was updated but is not eligible to be polled yet")
		
		return False # Failsafe
		
	
	################################################################################
	# MISC ROUTINES
	################################################################################
	
	#
	# See if it's ok for the device to poll
	#
	def okToPoll (self, devId):
		if self.pollingMode == "realTime": return True
		
		return False
	
	#
	# Dump and then print the value
	#
	def dictDump (self, value):
		self.dump(value)
		indigo.server.log("\n" + self.dumpTxt)
		self.dumpTxt = ""
	
	#
	# Iterate through nested vars to output cleaner logging
	#
	def dump(self, obj, nested_level=0, output=sys.stdout):
		spacing = '   '
		if type(obj) == dict:
			self.dumpTxt += '%s{' % ((nested_level) * spacing) + "\n"
			for k, v in obj.items():
				if hasattr(v, '__iter__'):
					self.dumpTxt += '%s%s:' % ((nested_level + 1) * spacing, k) + "\n"
					self.dump(v, nested_level + 1, output)
				else:
					self.dumpTxt += '%s%s: %s' % ((nested_level + 1) * spacing, k, v) + "\n"
			self.dumpTxt += '%s}' % (nested_level * spacing) + "\n"
		elif type(obj) == list:
			self.dumpTxt += '%s[' % ((nested_level) * spacing) + "\n"
			for v in obj:
				if hasattr(v, '__iter__'):
					self.dump(v, nested_level + 1, output)
				else:
					self.dumpTxt += '%s%s' % ((nested_level + 1) * spacing, v) + "\n"
			self.dumpTxt += '%s]' % ((nested_level) * spacing) + "\n"
		else:
			self.dumpTxt += '%s%s' % (nested_level * spacing, obj) + "\n"
			