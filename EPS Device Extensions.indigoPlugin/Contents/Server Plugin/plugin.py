#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Core libraries
import indigo
import os
import sys
import time
import datetime

# EPS 3.0 Libraries
import logging
from lib.eps import eps
from lib import ext
from lib import dtutil
from lib import iutil

# Plugin libraries
import string
from datetime import date, timedelta
import urllib2 # for URL device
from lib import calcs

eps = eps(None)

################################################################################
# plugin - 	Basically serves as a shell for the main plugin functions, it passes
# 			all Indigo commands to the core engine to do the "standard" operations
#			and raises onBefore_ and onAfter_ if it wants to do something 
#			interesting with it.  The meat of the plugin is in here while the
#			EPS library handles the day-to-day and common operations.
################################################################################
class Plugin(indigo.PluginBase):

	# Define the plugin-specific things our engine needs to know
	TVERSION	= "3.2.1"
	PLUGIN_LIBS = ["cache", "plugcache", "irr"]
	UPDATE_URL 	= ""
	
	#
	# Init
	#
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		eps.__init__ (self)
		eps.loadLibs (self.PLUGIN_LIBS)
		
		self.thermostats = []
		
		
	################################################################################
	# PLUGIN HANDLERS
	#
	# Raised onBefore_ and onAfter_ for interesting Indigo or custom commands that 
	# we want to intercept and do something with
	################################################################################	
	
	#
	# Upgrade check
	#
	def pluginUpgrade (self):
		try:
			upgradeSuccess = True
			
			if ext.valueValid (self.pluginPrefs, "currentVersion") == False:
				# They upgraded from 1.53 or earlier, start by finding all "lastChanged" states being used
				self.logger.warn ("Upgrading plugin from version 1.53 or earlier")
				
				for dev in indigo.devices.iter(self.pluginId):
					# Convert the legacy lastChanged state
					if ext.valueValid (dev.pluginProps, "states", True) and dev.pluginProps["states"] == "lastChanged":
						self.logger.warn ("Device '{0}' using obsolete 'lastChanged' state, upgrading to use the 'lastChanged' property instead".format(dev.name))
						props = dev.pluginProps
						props["states"] = "attr_lastChanged"
						dev.replacePluginPropsOnServer (props)
						
					# Check for .UI states in anything except conversions
					if dev.deviceTypeId != "epsdecon" and ext.valueValid (dev.pluginProps, "states", True) and dev.pluginProps["states"][-3:] == ".ui":
						self.logger.warn ("Device '{0}' using a UI state which can be unpredictable and cause errors at run-time, upgrade cannot complete until this is resolved.".format(dev.name))
						upgradeSuccess = False
						
			else:
				previousVersion = self.pluginPrefs["currentVersion"]
				
			if upgradeSuccess:
				pass
			
			else:
				self.logger.error ("One or more problems are preventing the plugin from upgrading your settings and devices, please correct the issues and restart the plugin.")
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Concurrent Thread
	#
	def onAfter_runConcurrentThread(self):
		try:
			# High/low resets
			resets = []
			
			for devId in eps.cache.pluginItems["epsdeth"]:
				if devId in indigo.devices:
					resets.append(devId)
					
			for devId in eps.cache.pluginItems["epsdews"]:
				if devId in indigo.devices:
					resets.append(devId)		
					
			for devId in resets:
				parent = indigo.devices[devId]
				
				if "lasthighlowreset" in parent.states: # In case they changed device types on the fly
					needsReset = False
					if parent.states["lasthighlowreset"] == "":
						needsReset = True
					else:
						d = indigo.server.getTime()
						if dtutil.dateDiff ("hours", d, str(parent.states["lasthighlowreset"]) + " 00:00:00") >= 24:
							needsReset = True
						
					if needsReset:
						self.resetHighsLows (parent)
						
			# Irrigation timers
			for devId in eps.cache.pluginItems["epsdeirr"]:
				self.calculateTimeRemaining (indigo.devices[devId])
									
			# Thermostat preset timers
			for devId in eps.cache.pluginItems["epsdeth"]:
				if devId in indigo.devices:
					parent = indigo.devices[devId]
					
					presetActive = 0
					for i in range (1, 5):
						if parent.states["presetOn" + str(i)]: 
							presetActive = i
							break
							
					if presetActive > 0:
						d = indigo.server.getTime()
						autoOff = datetime.datetime.strptime (parent.states["presetExpires"], "%Y-%m-%d %H:%M:%S")
						if dtutil.dateDiff ("seconds", autoOff, d) < 1:
							self.logger.info ("The preset {1} for '{0}' has expired, reverting to pre-preset settings".format(parent.name, str(presetActive)))
							self.thermostatPresetToggle (parent, presetActive)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Watch for state changes
	#
	def onWatchedStateRequest (self, dev):
		self.logger.threaddebug ("Returning watched states for {0}".format(dev.deviceTypeId))
		ret = {}
		
		try:
			if dev.deviceTypeId == "epsdecon":
				if dev.pluginProps["chdevice"] and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
					if dev.pluginProps["states"][0:5] != "attr_": ret[int(dev.pluginProps["device"])] = [dev.pluginProps["states"]]
								
			if dev.deviceTypeId == "epsdews":
				if ext.valueValid (dev.pluginProps, "device", True):
					states = []
				
					if ext.valueValid (dev.pluginProps, "temperature", True):
						states.append (dev.pluginProps["temperature"])
						
					if ext.valueValid (dev.pluginProps, "humidity", True):
						states.append (dev.pluginProps["humidity"])
						
					if ext.valueValid (dev.pluginProps, "rain", True):
						states.append (dev.pluginProps["rain"])
						
					if len(states) > 0: ret[int(dev.pluginProps["device"])] = states
							
			if dev.deviceTypeId == "epsdeth":	
				if ext.valueValid (dev.pluginProps, "device", True):
					states = []	
					child = indigo.devices[int(dev.pluginProps["device"])]
					
					if ext.valueValid (child.states, "temperatureInput1"): states.append ("temperatureInput1")
					if ext.valueValid (child.states, "humidityInput1"): states.append ("humidityInput1")
					if ext.valueValid (child.states, "hvacFanModeIsAuto"): states.append ("hvacFanModeIsAuto")
					if ext.valueValid (child.states, "hvacOperationModeIsOff"): states.append ("hvacOperationModeIsOff")
					if ext.valueValid (child.states, "setpointCool"): states.append ("setpointCool")
					if ext.valueValid (child.states, "setpointHeat"): states.append ("setpointHeat")
					
					
					if len(states) > 0: ret[int(dev.pluginProps["device"])] = states
					
			if dev.deviceTypeId == "epsdeirr":	
				if ext.valueValid (dev.pluginProps, "device", True):
					states = []	
					child = indigo.devices[int(dev.pluginProps["device"])]
					
					if ext.valueValid (child.states, "activeZone"): states.append ("activeZone")
					
					if dev.pluginProps["rain"]:
						if ext.valueValid (dev.pluginProps, "raindevice", True):
							if dev.pluginProps["states"][0:5] != "attr_": ret[int(dev.pluginProps["raindevice"])] = [dev.pluginProps["states"]]
					
					if len(states) > 0: ret[int(dev.pluginProps["device"])] = states
										
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return ret
		
	#
	# Watch for attribute changes
	#
	def onWatchedAttributeRequest (self, dev):
		self.logger.threaddebug ("Returning watched attributes for {0}".format(dev.deviceTypeId))
		ret = {}
		
		try:
			if dev.deviceTypeId == "epsdecon":
				if dev.pluginProps["chdevice"] and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
					if dev.pluginProps["states"][0:5] == "attr_": ret[int(dev.pluginProps["device"])] = [dev.pluginProps["states"]]
			
			if dev.deviceTypeId == "epsdeirr":	
				if ext.valueValid (dev.pluginProps, "device", True):
					attribs = []	
					child = indigo.devices[int(dev.pluginProps["device"])]
					
					attribs.append ("attr_" + "displayStateImageSel")
					attribs.append ("attr_" + "displayStateValRaw")
					attribs.append ("attr_" + "displayStateValUi")
					attribs.append ("attr_" + "pausedScheduleRemainingZoneDuration")
					attribs.append ("attr_" + "pausedScheduleZone")
					attribs.append ("attr_" + "zoneCount")
					attribs.append ("attr_" + "zoneEnableList")
					attribs.append ("attr_" + "zoneMaxDurations")
					attribs.append ("attr_" + "zoneNames")
					attribs.append ("attr_" + "zoneScheduledDurations")
					
					if dev.pluginProps["rain"]:
						if ext.valueValid (dev.pluginProps, "raindevice", True):
							if dev.pluginProps["states"][0:5] == "attr_": ret[int(dev.pluginProps["raindevice"])] = [dev.pluginProps["states"]]
										
					if len(attribs) > 0: ret[int(dev.pluginProps["device"])] = attribs
										
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return ret
	
	#
	# A watched device state has changed
	#
	def onWatchedStateChanged (self, origDev, newDev, change):
		try:
			#indigo.server.log(unicode(change))
			
			parent = indigo.devices[change.parentId]
			child = indigo.devices[change.childId]
			value = unicode(change.newValue).lower()
			
			if parent.deviceTypeId == "epsdeirr":	
				self.irrigationChildUpdated (parent, child, change)
			else:
				self.updateDevice (parent, child, value)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# A watched device attribute has changed
	#
	def onWatchedAttributeChanged (self, origDev, newDev, change):
		try:
			#indigo.server.log(unicode(change))
			
			parent = indigo.devices[change.parentId]
			child = indigo.devices[change.childId]
			value = unicode(change.newValue).lower()
			
			if parent.deviceTypeId == "epsdeirr":	
				self.irrigationChildUpdated (parent, child, change)
			else:
				self.updateDevice (parent, child, value)
		
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
	#
	# A plugin device was updated
	#
	def onAfter_pluginDevicePropChanged (self, origDev, newDev, changedProps):	
		try:
			self.updateFromPluginDevice (newDev)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# A plugin device was created
	#
	def onAfter_pluginDeviceCreated (self, dev):	
		try:
			self.updateFromPluginDevice (dev)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# A plugin device was started
	#
	def onAfter_deviceStartComm (self, dev):	
		try:
			self.updateFromPluginDevice (dev)
			
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
	#
	# A form field changed
	#
	def onAfter_formFieldChanged (self, valuesDict, typeId, devId):	
		try:
			if typeId == "epsdews":
				if ext.valueValid (valuesDict, "device", True):
					dev = indigo.devices[int(valuesDict["device"])]
					
					if dev.pluginId == "com.perceptiveautomation.indigoplugin.weathersnoop":
						if "temperature" in valuesDict: valuesDict["temperature"] = "temperature_F"
						if "humidity" in valuesDict: valuesDict["humidity"] = "humidity"
						if "rain" in valuesDict: valuesDict["rain"] = "weather"
						if "rainstatetype" in valuesDict: valuesDict["rainstatetype"] = "string"
						if "rainvalue" in valuesDict: valuesDict["rainvalue"] = "Rain"
					
					elif dev.pluginId == "com.perceptiveautomation.indigoplugin.NOAAWeather":
						if "temperature" in valuesDict: valuesDict["temperature"] = "temperatureF"
						if "humidity" in valuesDict: valuesDict["humidity"] = "humidity"
						if "rain" in valuesDict: valuesDict["rain"] = "currentCondition"
						if "rainstatetype" in valuesDict: valuesDict["rainstatetype"] = "string"
						if "rainvalue" in valuesDict: valuesDict["rainvalue"] = "Rain"
					
					elif dev.pluginId == "com.fogbert.indigoplugin.wunderground":
						if "temperature" in valuesDict: valuesDict["temperature"] = "temp"
						if "humidity" in valuesDict: valuesDict["humidity"] = "relativeHumidity"
						if "rain" in valuesDict: valuesDict["rain"] = "conditions1"
						if "rainstatetype" in valuesDict: valuesDict["rainstatetype"] = "string"
						if "rainvalue" in valuesDict: valuesDict["rainvalue"] = "Rain"
						
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict
		
	#
	# Device turned on
	#
	def onDeviceCommandTurnOn (self, dev):
		try:
			if dev.pluginProps["onCommand"] != "":
				if self.urlDeviceAction (dev, dev.pluginProps["onCommand"]) == False: 
					return False			
				else:
					return True
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False
		
	#
	# Device turned off
	#
	def onDeviceCommandTurnOff (self, dev):
		try:
			if dev.pluginProps["offCommand"] != "":
				if self.urlDeviceAction (dev, dev.pluginProps["onCommand"]) == False: 
					return False			
				else:
					return True
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False	
	
		
	################################################################################
	# PLUGIN SPECIFIC ROUTINES
	#
	# Routines not raised by plug events that are specific to this plugin
	################################################################################	
	
	################################################################################
	# GENERAL
	################################################################################
	
	#
	# Derive parent, child and value from a plugin device then update as if a watched state/attribute changed
	#
	def updateFromPluginDevice (self, dev):
		try:
			if dev.deviceTypeId == "epsdecon":
				if dev.pluginProps["chdevice"] and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
					child = indigo.devices[int(dev.pluginProps["device"])]
					
					if dev.pluginProps["states"][0:5] != "attr_": 
						self.updateDevice (dev, child, child.states[dev.pluginProps["states"]])
					else:
						attribName = dev.pluginProps["states"].replace ("attr_", "")
						attrib = getattr(child, attribName)
						
						self.updateDevice (dev, child, attrib)
						
			elif dev.deviceTypeId == "epsdeurl":
				# There isn't anything really to update for now until we parse URL return data, except the address	
				if dev.address != "URL Device":
					props = dev.pluginProps
					props["address"] = "URL Device"
					dev.replacePluginPropsOnServer (props)
			
			else:
				if ext.valueValid (dev.pluginProps, "device", True):
					child = indigo.devices[int(dev.pluginProps["device"])]
					self.updateDevice (dev, child, None)
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Update our device based on the criteria provided
	#
	def updateDevice (self, parent, child, value):
		try:
			if parent.deviceTypeId == "epsdecon":
				if parent.pluginProps["action"] == "true" or parent.pluginProps["action"] == "false":
					# These are static and have no device
					if parent.address != "Static Value Extension":
						props = parent.pluginProps
						props["address"] = "Static Value Extension"
						parent.replacePluginPropsOnServer (props)			
				else:
					self.updateDeviceAddress (parent, child)
			
				if parent.pluginProps["action"] == "boolstr": return self._booleanToString (parent, child, value)
				if parent.pluginProps["action"] == "strtocase": return self._stringToCase (parent, child, value)
				if parent.pluginProps["action"] == "strtonum": return self._stringToNumber (parent, child, value)
				if parent.pluginProps["action"] == "dtformat": return self._dateReformat (parent, child, value)
				if parent.pluginProps["action"] == "string": return self._convertToString (parent, child, value)
				if parent.pluginProps["action"] == "ctof": return self._celsiusToFahrenheit (parent, child, value)	
				if parent.pluginProps["action"] == "ftoc": return self._fahrenheitToCelsius (parent, child, value)	
				if parent.pluginProps["action"] == "lux": return self._luxToString (parent, child, value)
				if parent.pluginProps["action"] == "booltype": return self._booleanToType (parent, child, value)
				if parent.pluginProps["action"] == "true": return self._booleanStatic (parent, child, True)
				if parent.pluginProps["action"] == "false": return self._booleanStatic (parent, child, False)
				if parent.pluginProps["action"] == "dtmin": return self._datetimeToElapsedMinutes (parent, child, value)
				if parent.pluginProps["action"] == "bool": return self._stateToBoolean (parent, child, value)
				
			elif parent.deviceTypeId == "epsdews": 
				self.updateDeviceAddress (parent, child)
				return self._updateWeather (parent, child, value)
				
			elif parent.deviceTypeId == "epsdeth": 
				self.updateDeviceAddress (parent, child)
				return self._updateThermostat (parent, child, value)
				
			elif parent.deviceTypeId == "epsdeirr": 
				self.updateDeviceAddress (parent, indigo.devices[int(parent.pluginProps["device"])])
				return self._updateIrrigation (parent, child, value)
				
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Set the device address to the child name
	#
	def updateDeviceAddress (self, parent, child):
		try:
			if parent.address != child.name + " Extension":
				props = parent.pluginProps
				props["address"] = child.name + " Extension"
				parent.replacePluginPropsOnServer (props)
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
			
	################################################################################
	# URL TOGGLE EXTENSION
	################################################################################			
			
	#
	# Update a URL device
	#
	def _updateURL (self, parent, child, value):		
		try:
			pass
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# URL device action
	#
	def urlDeviceAction (self, dev, url):
		try:
			if dev.pluginProps["url"] != "" or dev.pluginProps["username"] != "" or dev.pluginProps["password"] != "":
				ret = urllib2.Request(url)
				if dev.pluginProps["url"] != "": ret = urllib2.Request(dev.pluginProps["url"])
			
				if dev.pluginProps["username"] != "" or dev.pluginProps["password"] != "":
					b64 = base64.encodestring('%s:%s' % (dev.pluginProps["username"], dev.pluginProps["password"])).replace('\n', '')
					ret.add_header("Authorization", "Basic %s" % b64)  
				
				ret = urllib2.urlopen(ret, url)
			
			else:
				ret = urllib2.urlopen(url)
				
			indigo.server.log(unicode(ret))
	
			if int(ret.getcode()) != 200: return False
		
			return True		
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			return False
			
	#
	# URL actions
	#
	def urlActions (self, devAction):
		try:
			parent = indigo.devices[devAction.deviceId]
			
			if devAction.pluginTypeId == "url-forceoff": 
				parent.updateStateOnServer("onOffState", False)
			
		except Exception as e:
			self.logger.error (ext.getException(e))				
			
	################################################################################
	# IRRIGATION EXTENSION
	################################################################################		
	
	#
	# Update time remaining countdown
	#
	def calculateTimeRemaining (self, parent):
		try:
			states = []
			
			if parent.states["timerRunning"] == False: return # only is on for an active schedule, pause hard stop or quick pause
			if ext.valueValid (parent.pluginProps, "device", True) == False: return
						
			child = indigo.devices[int(parent.pluginProps["device"])]
			
			if child.states["activeZone"] != 0:
				d = indigo.server.getTime()
			
				iutil.updateState ("scheduleRunTimeRemaining", self.calculateUITime (parent, "scheduleEndTime"), states)
				
				zoneTimeRemaining = self.calculateUITime (parent, "zoneEndTime")
				iutil.updateState ("zoneRunTimeRemaining", zoneTimeRemaining, states)
				iutil.updateState ("statedisplay", "Z" + str(child.displayStateValRaw) + " - " + zoneTimeRemaining, states)
				
			elif child.states["activeZone"] == 0 and child.pausedScheduleZone is not None:
				# We are paused, see if we need to hard stop due to rain or if we need to resume a quick pause
				if parent.pluginProps["rain"] and parent.pluginProps["resetrainaction"] and (parent.pluginProps["rainaction"] == "pause" or parent.pluginProps["rainaction"] == "resume"):
					uitime = self.calculateUITime (parent, "hardStopTime")
					
					if uitime == "00:00" or uitime == "00:00:00":
						self.logger.info ("'{0}' was paused due to rain and it has been raining for more than an hour, stopping '{1}'".format(parent.name, child.name))
						indigo.sprinkler.stop (child.id)				
						iutil.updateState ("timerRunning", False, states)
					else:
						iutil.updateState ("pauseTimeRemaining", uitime, states)
						
				elif parent.states["quickpaused"]:
					uitime = self.calculateUITime (parent, "quickPauseEndTime")
					
					if uitime == "00:00" or uitime == "00:00:00":
						#self.logger.info ("'{0}' was quick paused and the quick pause time is up, resuming '{1}'".format(parent.name, child.name))
						#indigo.sprinkler.resume (child.id)
						pass
						
					else:
						iutil.updateState ("pauseTimeRemaining", uitime, states)
				
			if len(states) > 0: parent.updateStatesOnServer (states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Calculate HH:MM:SS remaining for provided end date
	#
	def calculateUITime (self, dev, state):
		try:
			s = dtutil.dateDiff ("seconds", str(dev.states[state]), indigo.server.getTime())
			
			if s < 1:
				# Time is up
				if dev.pluginProps["timeformat"] == "ms": return "00:00"
				if dev.pluginProps["timeformat"] == "hms": return "00:00:00"
				
			else:
				lm, ls = divmod(s, 60)
				lh, lm = divmod(lm, 60)
				
				if dev.pluginProps["timeformat"] == "ms":
					if lh > 1:
						lm = 99
						ls = 99
					if lh == 1:
						if lm < 40: 
							lm = lm + 60 # We max at 99 minutes
						else:
							lm = 99
							ls = 99
							
				if dev.pluginProps["timeformat"] == "ms": return "%02d:%02d" % (lm, ls)
				if dev.pluginProps["timeformat"] == "hms": return "%02d:%02d:%02d" % (lh, lm, ls)
					
		except Exception as e:
			self.logger.error (ext.getException(e))			
	
	#
	# Update a sprinkler device
	#
	def _updateIrrigation (self, parent, child, value, states = None):
		try:
			if states is None: states = []
			
			if child.states["activeZone"] == 0 and child.pausedScheduleZone is None and parent.states["resuming"] == False:
				# Nothing going on, default values
				#indigo.server.log("SHUTTING IT OFF")
				parent.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOff)
				iutil.updateState ("statedisplay", "all zones off", states)
				iutil.updateState ("timerRunning", False, states)
				iutil.updateState ("scheduleRunTimeRemaining", "00:00", states)
				iutil.updateState ("zoneRunTimeRemaining", "00:00", states)
				
			elif child.states["activeZone"] == 0 and child.pausedScheduleZone is not None:
				# The schedule is paused, figure out what paused it
				parent.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOff)
				
				if parent.pluginProps["rain"] and parent.states["raining"]:
					# We paused for rain				
					iutil.updateState ("statedisplay", "rain paused", states)
					
				elif parent.states["quickpaused"]:
					# We paused for a period of time				
					iutil.updateState ("statedisplay", "quick paused", states)
					
				else:
					# Manually paused
					iutil.updateState ("statedisplay", "schedule paused", states)
				
			elif child.states["activeZone"] != 0:
				# A zone is running
				parent.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOn)
				iutil.updateState ("statedisplay", "Z" + str(child.displayStateValRaw) + " - " + parent.states["zoneRunTimeRemaining"], states)
				iutil.updateState ("currentZoneName", child.zoneNames[child.states["activeZone"] - 1])
							
			# Write the states
			if len(states) > 0: parent.updateStatesOnServer (states)		
					
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Handle irrigation device changes in real-time
	#
	def irrigationChildUpdated (self, parent, child, change):
		try:
			states = []
			
			##############################################################
			# Actions to take when the child is the irrigation controller
			##############################################################
			if str(child.id) == parent.pluginProps["device"]:
				if len(child.zoneScheduledDurations) > 0 and parent.pluginProps["lastschedule"]:
					# A schedule was run, remember it as the last known schedule
					for i in range (0, 8):
						if child.zoneEnableList[i]:
							states = iutil.updateState ("zone" + str(i + 1) + "Schedule", child.zoneScheduledDurations[i], states)
						else:
							states = iutil.updateState ("zone" + str(i + 1) + "Schedule", float(0), states)
							
				if change.name == "pausedScheduleZone" and change.oldValue is None and change.newValue is not None:
					# Schedule has been paused		
					indigo.server.log ("Paused schedule")
				
				elif change.name == "pausedScheduleZone" and change.oldValue is not None and change.newValue is None:			
					# A paused schedule has been resumed
					indigo.server.log ("Paused schedule resumed")
					
				elif change.name == "activeZone" and child.pausedScheduleZone is None:
					if parent.states["resuming"]:
						iutil.updateState ("resuming", False, states)
					else:										
						if len(child.zoneScheduledDurations) > 0 and change.oldValue == 0 and change.newValue != 0:
							# A schedule is being run, calculate the run times
							totalTime = self.calculateIrrigationRunTime (child.zoneScheduledDurations)
							zoneTime = self.calculateIrrigationRunTime (child.zoneScheduledDurations, change.newValue)
					
							totalEndTime = dtutil.dateAdd ("minutes", totalTime, indigo.server.getTime())
							zoneEndTime = dtutil.dateAdd ("minutes", zoneTime, indigo.server.getTime())
					
							self.logger.debug ("'{0}' has started running a schedule, the total run time is {1} minutes and should end at {2}".format(child.name, str(totalTime), totalEndTime.strftime ("%Y-%m-%d %H:%M:%S")))
							self.logger.debug ("'{0}' zone {1} should run for {2} minutes and complete by {3}".format(child.name, str(change.newValue), str(zoneTime), zoneEndTime.strftime ("%Y-%m-%d %H:%M:%S")))
										
							iutil.updateState ("timerRunning", True, states)					
							iutil.updateState ("scheduleEndTime", totalEndTime.strftime ("%Y-%m-%d %H:%M:%S"), states)
							iutil.updateState ("zoneEndTime", zoneEndTime.strftime ("%Y-%m-%d %H:%M:%S"), states)
							
						elif len(child.zoneScheduledDurations) == 0 and change.oldValue == 0 and change.newValue != 0:
							# Zone turned on manually with no schedule
							indigo.server.log ("Sprinkler zone turned on with no schedule")			
							
						elif change.oldValue != 0 and change.newValue == 0:
							# Sprinklers stopped, paused is caught before this so we don't need to test for a pause
							indigo.server.log ("Stopped sprinklers")
							
						elif change.oldValue != 0 and change.newValue != 0:
							# The zone changed
							indigo.server.log ("Zone changed")
							zoneTime = self.calculateIrrigationRunTime (child.zoneScheduledDurations, change.newValue)
							zoneEndTime = dtutil.dateAdd ("minutes", zoneTime, indigo.server.getTime())
							self.logger.debug ("'{0}' zone {1} should run for {2} minutes and complete by {3}".format(child.name, str(change.newValue), str(zoneTime), zoneEndTime.strftime ("%Y-%m-%d %H:%M:%S")))
							
							iutil.updateState ("timerRunning", True, states)					
							iutil.updateState ("zoneEndTime", zoneEndTime.strftime ("%Y-%m-%d %H:%M:%S"), states)
							
				# Finally, update the parent
				self._updateIrrigation (parent, child, None, states)			
							
			##############################################################				
			# Actions to take when the child is the rain detection device
			##############################################################
			if parent.pluginProps["rain"] and str(child.id) == parent.pluginProps["raindevice"]:
				controller = indigo.devices[int(parent.pluginProps["device"])]
				isRaining = parent.states["raining"] # What the device thinks is happening
				
				# What is really happening
				if parent.pluginProps["statetype"] == "string":
					if unicode(child.states[parent.pluginProps["states"]]).lower() == parent.pluginProps["rainvalue"].lower(): 
						# It's currently raining
						isRaining = True		
					else:
						isRaining = False
							
				else:
					# The rain value is not a string, figure it out
					pass
					
				# If the device thinks it's raining but the state disagrees then the rain condition has ended
				if parent.states["raining"] and isRaining == False:
					states = iutil.updateState ("raining", False, states)
					
					# We need to resume the sprinklers
					if parent.pluginProps["rainaction"] == "resume" and controller.pausedScheduleZone is not None:
						# Recalculate the schedule by how much time has elapsed since we paused for rain
						d = indigo.server.getTime()
						pausedAt = datetime.datetime.strptime (parent.states["rainDetectTime"], "%Y-%m-%d %H:%M:%S")
						secs = dtutil.dateDiff ("seconds", d, pausedAt)
						mins = round(secs/60, 2) # for reporting
						
						# Now add back the seconds to our two schedules
						scheduleEndTime = datetime.datetime.strptime (parent.states["scheduleEndTime"], "%Y-%m-%d %H:%M:%S")
						
						scheduleEndTime = dtutil.dateAdd ("seconds", secs, scheduleEndTime)
						zoneEndTime = dtutil.dateAdd ("minutes", controller.pausedScheduleRemainingZoneDuration, d)
						
						parent.updateStateOnServer ("resuming", True) # to keep other actions from firing, have to write it immediately
						
						iutil.updateState ("timerRunning", True, states)	
						iutil.updateState ("scheduleEndTime", scheduleEndTime.strftime ("%Y-%m-%d %H:%M:%S"), states)
						iutil.updateState ("zoneEndTime", zoneEndTime.strftime ("%Y-%m-%d %H:%M:%S"), states)
						
						self.logger.info ("'{0}' was paused for rain for {1} minutes and is now being resumed, the new end time is {2}".format(parent.name, str(mins), scheduleEndTime.strftime ("%Y-%m-%d %H:%M:%S")))
						
						indigo.sprinkler.resume (controller.id)
					
				elif parent.states["raining"] == False and isRaining:
					states = iutil.updateState ("raining", True, states)
				
					# We need to pause/stop the sprinklers if they are running
					if controller.states["activeZone"] != 0:
						# We are currently watering
						if parent.pluginProps["rainaction"] == "stop":
							self.logger.info ("'{0}' indicates it is raining and '{1}' is configured to stop when raining, stopping sprinkler schedule".format(child.name, parent.name))
							indigo.sprinkler.stop (controller.id)
							
						elif parent.pluginProps["rainaction"] == "pause":
							self.logger.info ("'{0}' indicates it is raining and '{1}' is configured to pause when raining, pausing sprinkler schedule".format(child.name, parent.name))
							indigo.sprinkler.pause (controller.id)
							
						elif parent.pluginProps["rainaction"] == "resume":
							d = indigo.server.getTime()
							self.logger.info ("'{0}' indicates it is raining and '{1}' is configured to pause when raining and resume when it stops, pausing sprinkler schedule".format(child.name, parent.name))
							indigo.sprinkler.pause (controller.id)
							states = iutil.updateState ("rainDetectTime", d.strftime("%Y-%m-%d %H:%M:%S"), states)
							
						# They can add a 1 hour hard stop to pause and resume actions
						if parent.pluginProps["rainaction"] == "pause" or parent.pluginProps["rainaction"] == "resume":	
							if parent.pluginProps["resetrainaction"]:
								stopat = dtutil.dateAdd ("hours", 1, d)
								iutil.updateState ("timerRunning", True, states)	
								states = iutil.updateState ("hardStopTime", stopat.strftime("%Y-%m-%d %H:%M:%S"), states)
							
							else:
								# No need to run the timer because we aren't checking for anything anymore
								iutil.updateState ("timerRunning", False, states)
						
				# Finally, update the parent
				self._updateIrrigation (parent, controller, None, states)			
			
			
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Thermostat actions
	#
	def irrigationAction (self, devAction):
		try:
			parent = indigo.devices[devAction.deviceId]
			child = indigo.devices[int(parent.pluginProps["device"])]
			
			if devAction.pluginTypeId == "ir-zone1toggle": self.zoneToggle (child, 1)
			if devAction.pluginTypeId == "ir-zone2toggle": self.zoneToggle (child, 2)
			if devAction.pluginTypeId == "ir-zone3toggle": self.zoneToggle (child, 3)
			if devAction.pluginTypeId == "ir-zone4toggle": self.zoneToggle (child, 4)
			if devAction.pluginTypeId == "ir-zone5toggle": self.zoneToggle (child, 5)
			if devAction.pluginTypeId == "ir-zone6toggle": self.zoneToggle (child, 6)
			if devAction.pluginTypeId == "ir-zone7toggle": self.zoneToggle (child, 7)
			if devAction.pluginTypeId == "ir-zone8toggle": self.zoneToggle (child, 8)
			
			if devAction.pluginTypeId == "ir-quickpause": 
				if child.states["activeZone"] == 0:
					self.logger.warn ("Unable to quick pause '{0}' because it is not running right now".format(child.name))
					
				else:
					states = []
					
					indigo.server.log(unicode(devAction))
					
					iutil.updateState ("timerRunning", True, states)	
					iutil.updateState ("quickpaused", True, states)	
					
					stopat = dtutil.dateAdd ("minutes", int(devAction.props["pauseminutes"]), indigo.server.getTime())	
					states = iutil.updateState ("quickPauseEndTime", stopat.strftime("%Y-%m-%d %H:%M:%S"), states)
					
					indigo.sprinkler.pause (child.id)
					parent.updateStatesOnServer (states)
					
			if devAction.pluginTypeId == "ir-runzone": 
				self.zoneRun (child, devAction.props["zone"], devAction.props["duration"])
			
			
		except Exception as e:
			self.logger.error (ext.getException(e))		
	
	
	#
	# Return list of zones
	#
	def zoneList (self, args, valuesDict):
		retList = []
		
		try:
			parent = indigo.devices[int(args["targetId"])]
			child = indigo.devices[int(parent.pluginProps["device"])]
			
			for i in range(0, 8):
				if child.zoneEnableList[i]:
					retList.append ((str(i + 1), child.zoneNames[i]))
			
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
		return retList
			
	# 
	# Turn zone on
	#
	def zoneRun (self, child, zoneNum, duration):		
		try:
			zoneNum = int(zoneNum)
			duration = int(duration)
			schedule = [0, 0, 0, 0, 0, 0, 0, 0]
			
			schedule[zoneNum - 1] = duration
			
			if child.states["activeZone"] != 0 or child.pausedScheduleZone is not None:
				# We are running, stop it first
				self.logger.info ("Stopping current sprinkler schedule on '{0}' so the Run Zone action can run".format(child.name))
				#indigo.sprinkler.stop (child.id) 
			
			self.logger.info ("Running '{0}' zone {1} for {2} minutes".format(child.name, str(zoneNum), str(duration)))
			self.logger.debug ("Running '{0}' schedule: {1}".format(child.name, unicode(schedule)))
			
			#indigo.sprinkler.run(child.id, schedule=schedule) 
						
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	# 
	# Toggle zone on/off
	#
	def zoneToggle (self, child, n):
		try:
			allOff = True
			for i in range(1,9):
				try: # 1.5.1
					if child.states["zone" + str(i)]: allOff = False
				except:
					X = 1 # placeholder
			
			# If everything is off then we just need to turn on the zone they want
			if allOff:
				indigo.sprinkler.setActiveZone(child.id, index=n)
			else:
				if child.states["zone" + str(n)]:
					# It's this zone that is on, so turn off everything because our toggle is OFF
					indigo.sprinkler.stop(child.id)
				else:
					# A different zone is on, meaning this zone is off and they want to toggle it ON
					indigo.sprinkler.setActiveZone(child.id, index=n)		
					
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
	#
	# Calculate an irrigation run time
	#
	def calculateIrrigationRunTime (self, scheduleDict, zone = 0):
		runTime = float(0)
		
		try:
			zone = int(zone) # failsafe
			
			index = 0
			for time in scheduleDict:
				index = index + 1
				if zone != 0 and index != zone: continue
				
				runTime = runTime + time
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return runTime
		
			
	################################################################################
	# THERMOSTAT EXTENSION
	################################################################################			
		
	#
	# Reset the highs and lows for a device
	#
	def resetHighsLows (self, parent):
		try:
			states = []
			d = indigo.server.getTime()
					
			if "hightemp" in parent.states: states = iutil.updateState ("hightemp", "", states)
			if "lowtemp" in parent.states: states = iutil.updateState ("lowtemp", "", states)
			if "highhumidity" in parent.states: states = iutil.updateState ("highhumidity", "", states)
			if "lowhumidity" in parent.states: states = iutil.updateState ("lowhumidity", "", states)
			if "isrecordhigh" in parent.states: states = iutil.updateState ("isrecordhigh", False, states)
			if "isrecordlow" in parent.states: states = iutil.updateState ("isrecordlow", False, states)
			
			if len(states) > 0:
				self.logger.debug ("Resetting high/low values for '{0}'".format(parent.name))
				states = iutil.updateState ("lasthighlowreset", d.strftime("%Y-%m-%d"), states)
				parent.updateStatesOnServer (states)	
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Update a weather device
	#
	def _updateThermostat (self, parent, child, value):
		try:
			states = []
			
			states = iutil.updateState ("hightemp", calcs.getHighFloatValue (child, "temperatureInput1", parent.states["hightemp"]), states)
			states = iutil.updateState ("lowtemp", calcs.getHighFloatValue (child, "temperatureInput1", parent.states["lowtemp"]), states)

			if "humidity" in child.states:
				states = iutil.updateState ("highhumidity", calcs.getHighFloatValue (child, "humidityInput1", parent.states["highhumidity"]), states)
				states = iutil.updateState ("lowhumidity", calcs.getHighFloatValue (child, "humidityInput1", parent.states["lowhumidity"]), states)
			
			if child.states["hvacFanModeIsAuto"]:
				states = iutil.updateState ("fanOn", False, states)
			else:
				states = iutil.updateState ("fanOn", True, states)
			
			if child.states["hvacOperationModeIsOff"]:
				states = iutil.updateState ("systemOn", False, states)
			else:
				states = iutil.updateState ("systemOn", True, states)
			
			if parent.states["setMode"]:
				# It's true (cool), get the current cool setpoint
				states = iutil.updateState ("setModeSetPoint", child.states["setpointCool"], states)
			else:
				# It's false (heat), get the current heat setpoint
				states = iutil.updateState ("setModeSetPoint", child.states["setpointHeat"], states)
				
			self._updateThermostatStates (parent, child, states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Update the display state for a thermostat device
	#		
	def _updateThermostatStates (self, parent, child, states):
		try:		
			stateSuffix = u"°F" 
			decimals = 1
			stateFloat = float(0)
			stateString = "NA"
		
			if "measurement" in parent.pluginProps:
				if parent.pluginProps["measurement"] == "C": stateSuffix = u"°C" 
			
			if parent.pluginProps["statedisplay"] == "currenthumidity": 
				stateSuffix = ""
			
				if "humidity" in child.states:
					stateFloat = float(child.states["humidity"])
					stateString = str(child.states["humidity"])
					parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
				else:
					parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
			elif parent.pluginProps["statedisplay"] == "highhumidity": 
				stateSuffix = ""
			
				stateFloat = float(parent.states["highhumidity"])
				stateString = str(parent.states["highhumidity"])
				parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
			elif parent.pluginProps["statedisplay"] == "lowhumidity": 
				stateSuffix = ""
			
				stateFloat = float(parent.states["lowhumidity"])
				stateString = str(parent.states["lowhumidity"])
				parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
			elif parent.pluginProps["statedisplay"] == "hightemp": 
				stateFloat = float(parent.states["hightemp"])
				stateString = str(parent.states["hightemp"]) + " " + stateSuffix
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
			elif parent.pluginProps["statedisplay"] == "lowtemp": 
				stateFloat = float(parent.states["lowtemp"])
				stateString = str(parent.states["lowtemp"]) + " " + stateSuffix
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
			elif parent.pluginProps["statedisplay"] == "currenttemp": 
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
				stateFloat = float(child.states["temperatureInput1"])
				stateString = str(child.states["temperatureInput1"]) + " " + stateSuffix
				
			elif parent.pluginProps["statedisplay"] == "preset": 
				if parent.childiceTypeId == "epsdeth":
					decimals = -1
				
					stateString = "No Preset"
					if parent.states["presetOn1"]: stateString = "Preset 1"
					if parent.states["presetOn2"]: stateString = "Preset 2"
					if parent.states["presetOn3"]: stateString = "Preset 3"
					if parent.states["presetOn4"]: stateString = "Preset 4"
				
					if stateString == "No Preset":
						parent.updateStateImageOnServer(indigo.kStateImageSel.TimerOff)
					else:
						parent.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
					
			elif parent.pluginProps["statedisplay"] == "setpoint": 
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
				if parent.states["setMode"]:
					stateFloat = float(child.states["setpointCool"])
					stateString = str(child.states["setpointCool"]) + " " + stateSuffix	
				else:
					stateFloat = float(child.states["setpointHeat"])
					stateString = str(child.states["setpointHeat"]) + " " + stateSuffix
				
			elif parent.pluginProps["statedisplay"] == "setcool": 
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
				stateFloat = float(child.states["setpointCool"])
				stateString = str(child.states["setpointCool"]) + " " + stateSuffix
			
			elif parent.pluginProps["statedisplay"] == "setheat": 
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
				stateFloat = float(child.states["setpointHeat"])
				stateString = str(child.states["setpointHeat"]) + " " + stateSuffix
			
			elif parent.pluginProps["statedisplay"] == "setmode": 
				decimals = -1
			
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
				if parent.states["setMode"]:
					stateString = "Heat"
				else:
					stateString = "Cool"	
			
			if decimals > -1:
				states = iutil.updateState ("statedisplay", stateFloat, states, stateString, decimals)
			else:
				states = iutil.updateState ("statedisplay", stateString, states)
			
			parent.updateStatesOnServer (states)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
	
	#
	# Toggle all presets that are currently on
	#
	def toggleAllThermostatPresets (self, dev):
		try:
			if dev.states["presetOn1"]: self.thermostatPresetToggle (dev, 1)
			if dev.states["presetOn2"]: self.thermostatPresetToggle (dev, 2)
			if dev.states["presetOn3"]: self.thermostatPresetToggle (dev, 3)
			if dev.states["presetOn4"]: self.thermostatPresetToggle (dev, 4)	
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Thermostat actions
	#
	def thermostatAction (self, devAction):
		try:
			parent = indigo.devices[devAction.deviceId]
			child = indigo.devices[int(parent.pluginProps["device"])]
		
			if devAction.pluginTypeId == "th-preset1toggle": self.thermostatPresetToggle (parent, 1)
			if devAction.pluginTypeId == "th-preset2toggle": self.thermostatPresetToggle (parent, 2)
			if devAction.pluginTypeId == "th-preset3toggle": self.thermostatPresetToggle (parent, 3)
			if devAction.pluginTypeId == "th-preset4toggle": self.thermostatPresetToggle (parent, 4)
			
			if devAction.pluginTypeId == "th-setmodeup":
				if child.states["hvacOperationModeIsOff"] == False:
					# Only change set point if the system is on
					if parent.states["setMode"]:
						# Cooling mode
						indigo.thermostat.increaseCoolSetpoint(child.id, delta=1)
					else:
						# Heating mode
						indigo.thermostat.increaseHeatSetpoint(child.id, delta=1)
					
			if devAction.pluginTypeId == "th-setmodedown":
				if child.states["hvacOperationModeIsOff"] == False:
					# Only change set point if the system is on
					if parent.states["setMode"]:
						# Cooling mode
						indigo.thermostat.decreaseCoolSetpoint(child.id, delta=1)
					else:
						# Heating mode
						indigo.thermostat.decreaseHeatSetpoint(child.id, delta=1)
			
			if devAction.pluginTypeId == "th-setmodetoggle":
				if parent.states["setMode"]:
					# It's true (cool), set it to false (heat)
					parent.updateStateOnServer ("setMode", False)
					parent.updateStateOnServer ("setModeSetPoint", child.states["setpointHeat"])
				else:
					# It's false (heat), set it to true (cool)
					parent.updateStateOnServer ("setMode", True)
					parent.updateStateOnServer ("setModeSetPoint", child.states["setpointCool"])
				
			
			if devAction.pluginTypeId == "th-fantoggle":
				varName = "hvacFanIsAuto"
			
				if parent.pluginProps["nest"]: varName = "hvacFanModeIsAuto"
			
				if child.states[varName]:
					indigo.thermostat.setFanMode(child.id, value=indigo.kFanMode.AlwaysOn)
				else:
					indigo.thermostat.setFanMode(child.id, value=indigo.kFanMode.Auto)
		
			if devAction.pluginTypeId == "th-systemtoggle":
				if parent.pluginProps["toggleparam"] == "auto":
					if child.states["hvacOperationModeIsOff"]:
						indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.HeatCool)
					else:
						indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Off)
						
				elif parent.pluginProps["toggleparam"] == "heat":
					if child.states["hvacOperationModeIsOff"]:
						indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Heat)
					else:
						indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Off)
						
				elif parent.pluginProps["toggleparam"] == "cool":
					if child.states["hvacOperationModeIsOff"]:
						indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Cool)
					else:
						indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Off)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Thermostat preset toggle
	#
	def thermostatPresetToggle (self, parent, n):
		try:
			# If this preset is on then toggle it off
			if parent.states["presetOn" + str(n)] == False:
				self.thermostatPresetOn (parent, n)
			
			else:
				# Restore memory and toggle off
				child = indigo.devices[int(parent.pluginProps["device"])]
			
				if parent.states["presetMemMode"] == 0:
					indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Off)
				elif parent.states["presetMemMode"] == 1:
					indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Heat)
				elif parent.states["presetMemMode"] == 2:
					indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Cool)
				elif parent.states["presetMemMode"] == 3:
					indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.HeatCool)
			
				if parent.states["presetMemMode"]:
					# Only restore temps if the previous mode was on, some thermostats store off state setpoints as 0
					heatset = parent.states["presetMemHeat"]
				
					if parent.pluginProps["failsafe"] != "0":
						if heatset > int(parent.pluginProps["failsafe"]): heatset = int(parent.pluginProps["failsafe"])
				
					indigo.thermostat.setCoolSetpoint(child.id, value=parent.states["presetMemCool"])
					indigo.thermostat.setHeatSetpoint(child.id, value=heatset)
			
				if parent.states["presetMemFanAuto"]:
					indigo.thermostat.setFanMode(child.id, value=indigo.kFanMode.Auto)
				else:
					indigo.thermostat.setFanMode(child.id, value=indigo.kFanMode.AlwaysOn)
			
				states = []
				states = iutil.updateState ("presetTimeout", 0, states)
				states = iutil.updateState ("presetOn" + str(n), False, states)
				parent.updateStatesOnServer (states)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Thermostat preset on
	#
	def thermostatPresetOn (self, parent, n):
		try:
			child = indigo.devices[int(parent.pluginProps["device"])]
			prefix = "preset" + str(n)
			states = []
		
			# Make sure this is the only active preset, there can be only one [true ring]
			self.toggleAllThermostatPresets (parent)
			
			self.logger.info ("Turning on '{0}' preset {1} for thermostat '{2}'".format(parent.name, str(n), child.name))
			self.logger.debug ("Preset sets cool to {0}, heat to {1}, system to {2}, fan to {3}".format(parent.pluginProps[prefix + "setcool"], parent.pluginProps[prefix + "setheat"], parent.pluginProps[prefix + "system"], parent.pluginProps[prefix + "fan"]))
		
			# Save current states to memory
			states = iutil.updateState ("presetMemHeat", child.states["setpointHeat"], states)
			states = iutil.updateState ("presetMemCool", child.states["setpointCool"], states)
			states = iutil.updateState ("presetMemFanAuto", child.states["hvacFanModeIsAuto"], states)
			states = iutil.updateState ("presetMemMode", child.states["hvacOperationMode"], states)
		
			# Set temps
			if parent.pluginProps[prefix + "setcool"] != "0": indigo.thermostat.setCoolSetpoint(child.id, value=int(parent.pluginProps[prefix + "setcool"]))
			if parent.pluginProps[prefix + "setheat"] != "0": indigo.thermostat.setHeatSetpoint(child.id, value=int(parent.pluginProps[prefix + "setheat"]))
		
			# Set system mode
			if parent.pluginProps[prefix + "system"] == "off": indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Off)
			if parent.pluginProps[prefix + "system"] == "heat": indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Heat)
			if parent.pluginProps[prefix + "system"] == "cool": indigo.thermostat.setHvacMode(child.id, value=indigo.kHvacMode.Cool)
		
			# Set fan mode
			if parent.pluginProps[prefix + "fan"] == "auto": indigo.thermostat.setFanMode(child.id, value=indigo.kFanMode.Auto)
			if parent.pluginProps[prefix + "fan"] == "always": indigo.thermostat.setFanMode(child.id, value=indigo.kFanMode.AlwaysOn)
		
			# Execute smart set if either setpoints was set to zero
			if parent.pluginProps["smartset"] != "0": 
				if parent.pluginProps[prefix + "setcool"] == "0" or parent.pluginProps[prefix + "setheat"] == "0":
					# Auto set the zero setting
					smartset = int(parent.pluginProps["smartset"])
				
					if parent.pluginProps[prefix + "setcool"] == "0":
						# Set cool to be X degrees above heating
						temp = int(parent.pluginProps[prefix + "setheat"])
						indigo.thermostat.setCoolSetpoint(child.id, value=temp + smartset)
						self.logger.debug ("Smart setting cooling setpoint to {0}".format(str(temp + smartset)))
					else:
						# Set heat to be X degrees below cooling
						temp = int(parent.pluginProps[prefix + "setcool"])
						indigo.thermostat.setHeatSetpoint(child.id, value=smartset - temp)
						self.logger.debug ("Smart setting heating setpoint to {0}".format(str(smartset - temp)))
					
			# If we have a timer then set the countdown
			if parent.pluginProps["timeout"] != "0":
				d = indigo.server.getTime()
				d = dtutil.dateAdd ("minutes", int(parent.pluginProps["timeout"]), d)
				states = iutil.updateState ("presetTimeout", int(parent.pluginProps["timeout"]), states)
				states = iutil.updateState ("presetExpires", d.strftime("%Y-%m-%d %H:%M:%S"), states)
				self.logger.info ("'{0}' will revert back to its pre-preset settings on {1}".format(child.name, d.strftime("%Y-%m-%d %H:%M:%S")))
			else:
				# Expire the timer in a month from now
				d = indigo.server.getTime()
				d = dtutil.dateAdd ("months", 1, d)
				states = iutil.updateState ("presetTimeout", 0, states)
				states = iutil.updateState ("presetExpires", d.strftime("%Y-%m-%d %H:%M:%S"), states)
				self.logger.info ("'{0}' will revert back to its pre-preset settings on {1}".format(child.name, d.strftime("%Y-%m-%d %H:%M:%S")))
				
			# Turn on preset
			states = iutil.updateState ("presetOn" + str(n), True, states)
			
			parent.updateStatesOnServer (states)			

		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	################################################################################
	# WEATHER EXTENSION
	################################################################################			
	
	#
	# Update a weather device
	#
	def _updateWeather (self, parent, child, value):
		try:
			tempVar = parent.pluginProps["temperature"]
			humVar = parent.pluginProps["humidity"]
			rainVar = parent.pluginProps["rain"]
		
			states = []
			states = iutil.updateState ("hightemp", calcs.getHighFloatValue (child, tempVar, parent.states["hightemp"]), states)
			states = iutil.updateState ("lowtemp", calcs.getLowFloatValue (child, tempVar, parent.states["lowtemp"]), states)
			states = iutil.updateState ("highhumidity", calcs.getHighFloatValue (child, humVar, parent.states["highhumidity"]), states)
			states = iutil.updateState ("lowhumidity", calcs.getHighFloatValue (child, humVar, parent.states["lowhumidity"]), states)
		
			if parent.pluginProps["rainstatetype"] == "string":
				if child.states[rainVar] == parent.pluginProps["rainvalue"]:
					states = iutil.updateState ("raining", True, states)
				else:
					states = iutil.updateState ("raining", False, states)

			elif parent.pluginProps["rainstatetype"] == "boolean":
				if child.states[rainVar]:
					states = iutil.updateState ("raining", True, states)
				else:
					states = iutil.updateState ("raining", False, states)
				
			# See if we hit the record high or record low temps on a WUnderground plugin (1.3.0)
			if child.pluginId == "com.fogbert.indigoplugin.wunderground":
				if parent.states["hightemp"] != "" and float(parent.states["hightemp"]) > float(child.states["historyHigh"]): parent.updateStateOnServer ("isrecordhigh", True)
				if parent.states["lowtemp"] != "" and float(parent.states["lowtemp"]) < float(child.states["historyLow"]): parent.updateStateOnServer ("isrecordlow", True)
		
			# Check the address
			if parent.address != child.name + " Extension":
				props = parent.pluginProps
				props["address"] = child.name + " Extension"
				parent.replacePluginPropsOnServer (props)
		
			self._updateWeatherStates (parent, child, states)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
	
	#
	# Update the display state for a weather device
	#		
	def _updateWeatherStates (self, parent, child, states):
		try:
			stateSuffix = u"°F" 
			decimals = 1
			stateFloat = float(0)
			stateString = "NA"
		
			if "measurement" in parent.pluginProps:
				if parent.pluginProps["measurement"] == "C": stateSuffix = u"°C" 
			
			if parent.pluginProps["statedisplay"] == "currenthumidity": 
				stateSuffix = ""
			
				if child.pluginId == "com.fogbert.indigoplugin.wunderground":
					stateFloat = float(child.states["relativeHumidity"])
					stateString = str(child.states["relativeHumidity"])
				else:
					stateFloat = float(child.states["humidity"])
					stateString = str(child.states["humidity"])
				
				parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
			
			elif parent.pluginProps["statedisplay"] == "highhumidity": 
				stateSuffix = ""
			
				stateFloat = float(parent.states["highhumidity"])
				stateString = str(parent.states["highhumidity"])
				parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
			elif parent.pluginProps["statedisplay"] == "lowhumidity": 
				stateSuffix = ""
			
				stateFloat = float(parent.states["lowhumidity"])
				stateString = str(parent.states["lowhumidity"])
				parent.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
			elif parent.pluginProps["statedisplay"] == "hightemp": 
				stateFloat = float(parent.states["hightemp"])
				stateString = str(parent.states["hightemp"]) + " " + stateSuffix
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
			elif parent.pluginProps["statedisplay"] == "lowtemp": 
				stateFloat = float(parent.states["lowtemp"])
				stateString = str(parent.states["lowtemp"]) + " " + stateSuffix
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
			elif parent.pluginProps["statedisplay"] == "currenttemp": 
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
				tempVar = parent.pluginProps["temperature"]
				stateFloat = float(child.states[tempVar])
				stateString = str(child.states[tempVar]) + " " + stateSuffix			
			
			if decimals > -1:
				states = iutil.updateState ("statedisplay", stateFloat, states, stateString, decimals)
			else:
				states = iutil.updateState ("statedisplay", stateString, states)
				
			parent.updateStatesOnServer (states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
		
	
	################################################################################
	# CONVERSIONS
	################################################################################
	
	#
	# Convert celsius to fahrenheit
	#
	def _celsiusToFahrenheit (self, parent, child, value):
		try:
			if "precision" in parent.pluginProps:
				value = calcs.temperature (value, False, int(parent.pluginProps["precision"]))
			else:
				value = calcs.temperature (value, False)
						
			stateSuffix = u" °F" 
			
			parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
			states = []
			states = iutil.updateState ("statedisplay", value, states, str(value) + stateSuffix, 1)
			states = iutil.updateState ("convertedValue", unicode(value), states)
			states = iutil.updateState ("convertedNumber", value, states)
		
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Convert fahrenheit to celsius
	#
	def _fahrenheitToCelsius (self, parent, child, value):
		try:
			if "precision" in parent.pluginProps:
				value = calcs.temperature (value, True, int(parent.pluginProps["precision"]))
			else:
				value = calcs.temperature (value, True)
						
			stateSuffix = u" °C" 
			
			parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
			states = []
			states = iutil.updateState ("statedisplay", value, states, str(value) + stateSuffix, 1)
			states = iutil.updateState ("convertedValue", unicode(value), states)
			states = iutil.updateState ("convertedNumber", value, states)
		
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")		
			
	#
	# Convert date from one format to another
	#
	def _dateReformat (self, parent, child, value):
		try:
			if ext.valueValid (parent.pluginProps, "inputdtformat", True) and ext.valueValid (parent.pluginProps, "outputdtformat", True):
				value = unicode(value)
				value = dtutil.dateStringFormat (value, parent.pluginProps["inputdtformat"], parent.pluginProps["outputdtformat"])
		
				parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
				states = []
				states = iutil.updateState ("statedisplay", value, states, value)
				states = iutil.updateState ("convertedValue", unicode(value), states)
			
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")	
			
	#
	# Convert date to elapsed minutes since date
	#
	def _datetimeToElapsedMinutes (self, parent, child, value):
		try:
			value = unicode(value)
			if value == "": return
		
			try:
				value = datetime.datetime.strptime (value, parent.pluginProps["dateformat"])
			except:
				self.logger.error (u"Error converting %s to a date/time with a format of %s, make sure the date format is correct and that the value is really a date/time string or datetime value!" % (value, parent.pluginProps["dateformat"]))
				parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")	
				return
			
			m = dtutil.dateDiff ("minutes", indigo.server.getTime(), value)
			m = int(m) # for state
		
			parent.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
	
			states = []
			states = iutil.updateState ("statedisplay", unicode(m).lower() + " Min", states)
			states = iutil.updateState ("convertedValue", unicode(m).lower(), states)
			states = iutil.updateState ("convertedNumber", m, states)
	
			parent.updateStatesOnServer(states)

		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")		
					
					
	#
	# Convert to a string and trim
	#
	def _convertToString (self, parent, child, value):
		try:
			value = unicode(value)
			
			if ext.valueValid (parent.pluginProps, "maxlength", True):
				if parent.pluginProps["maxlength"] != "0" and len(value) > int(parent.pluginProps["maxlength"]):
					self.debugLog("Shortening string to %i characters" % int(parent.pluginProps["maxlength"]))
					diff = len(value) - int(parent.pluginProps["maxlength"])
					diff = diff * -1
					value = value[:diff]
			
			if ext.valueValid (parent.pluginProps, "trimstart", True):
				if parent.pluginProps["trimstart"] != "0" and len(value) > int(parent.pluginProps["trimstart"]):
					self.debugLog("Removing %i characters from beginning of string" % int(parent.pluginProps["trimstart"]))
					diff = int(parent.pluginProps["trimstart"])
					value = value[diff:len(value)]		
					
			if ext.valueValid (parent.pluginProps, "trimend", True):
				if parent.pluginProps["trimend"] != "0" and len(value) > int(parent.pluginProps["trimend"]):
					self.debugLog("Removing %i characters from end of string" % int(parent.pluginProps["trimend"]))
					diff = int(parent.pluginProps["trimend"])
					diff = diff * -1
					value = value[:diff]		
			
			parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
			states = []
			states = iutil.updateState ("statedisplay", value, states, value)
			states = iutil.updateState ("convertedValue", unicode(value), states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Boolean to string
	#
	def _booleanToString (self, parent, child, value):
		try:
			value = unicode(value).lower()
			
			truevalue = unicode(parent.pluginProps["truewhen"])
			falsevalue = unicode(parent.pluginProps["falsewhen"])
	
			statevalue = falsevalue
			if value == "true": statevalue = truevalue
	
			parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
			states = []
			states = iutil.updateState ("statedisplay", unicode(statevalue), states)
			states = iutil.updateState ("convertedValue", unicode(statevalue), states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Lux value to string
	#
	def _luxToString (self, parent, child, value):
		try:
			if value is None:
				self.logger.warn ("'{0}' cannot convert the lux value for '{1}' because the value is None".format(parent.name, child.name))
				parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
				return
			
			value = float(value)
			term = "Direct Sunlight"
			
			if value < 100001: term = "Direct Sunlight"
			if value < 30001: term = "Cloudy Outdoors"
			if value < 10001: term = "Dim Outdoors"
			if value < 5001: term = "Bright Indoors"
			if value < 1001: term = "Normal Indoors"
			if value < 401: term = "Dim Indoors"
			if value < 201: term = "Dark Indoors"
			if value < 51: term = "Very Dark"
			if value < 11: term = "Pitch Black"
			
			if value < 1001:
				parent.updateStateImageOnServer(indigo.kStateImageSel.LightSensor)
			else:
				parent.updateStateImageOnServer(indigo.kStateImageSel.LightSensorOn)
			
			states = []
			states = iutil.updateState ("statedisplay", term, states)
			states = iutil.updateState ("convertedValue", term, states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))			
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# String to case
	#
	def _stringToCase (self, parent, child, value):
		try:
			value = unicode(value)
			
			if parent.pluginProps["strcase"] == "title": value = value.title()
			if parent.pluginProps["strcase"] == "initial": value = value.capitalize()
			if parent.pluginProps["strcase"] == "upper": value = value.upper()
			if parent.pluginProps["strcase"] == "lower": value = value.lower()
			
			parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
			states = []
			states = iutil.updateState ("statedisplay", value, states, value)
			states = iutil.updateState ("convertedValue", unicode(value), states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# String to number
	#
	def _stringToNumber (self, parent, child, value):
		try:
			value = unicode(value)
			states = []
			
			if ext.valueValid (parent.pluginProps, "trimstart", True):
				if parent.pluginProps["trimstart"] != "0" and len(value) > int(parent.pluginProps["trimstart"]):
					self.logger.debug ("Removing %i characters from beginning of string" % int(parent.pluginProps["trimstart"]))
					diff = int(parent.pluginProps["trimstart"])
					value = value[diff:len(value)]		
					
			if ext.valueValid (parent.pluginProps, "trimend", True):
				if parent.pluginProps["trimend"] != "0" and len(value) > int(parent.pluginProps["trimend"]):
					self.logger.debug ("Removing %i characters from end of string" % int(parent.pluginProps["trimend"]))
					diff = int(parent.pluginProps["trimend"])
					diff = diff * -1
					value = value[:diff]		
					
			try:
				dec = string.find (value, '.')
				numtype = parent.pluginProps["numtype"]
				
				if dec > -1 and numtype == "int":
					indigo.server.error ("Input value of %s on %s contains a decimal, forcing value to be a float.  Change the preferences for this device to get rid of this error." % (value, devEx.name))
					numtype = "float"
				
				if numtype == "int": 
					value = int(value)
					
					states = iutil.updateState ("statedisplay", value, states, unicode(value))
					states = iutil.updateState ("convertedValue", unicode(value), states)
					states = iutil.updateState ("convertedNumber", value, states)
					
				if numtype == "float": 
					value = float(value)
					
					states = iutil.updateState ("statedisplay", value, states, unicode(value), 2)
					states = iutil.updateState ("convertedValue", unicode(value), states)
					states = iutil.updateState ("convertedNumber", value, states)
					
			except Exception as e:
				self.logger.error (ext.getException(e))	
				parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
			parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")						
	
	#
	# Static boolean state
	#
	def _booleanStatic (self, parent, child, value):
		try:
			if value:
				parent.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
			else:
				parent.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
			
			states = []
			states = iutil.updateState ("statedisplay", unicode(value).lower(), states)
			states = iutil.updateState ("convertedValue", unicode(value).lower(), states)
			states = iutil.updateState ("convertedBoolean", value, states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# State to boolean
	#
	def _stateToBoolean (self, parent, child, value):
		try:
			value = unicode(value).lower()
			
			truevalue = unicode(parent.pluginProps["truewhen"]).lower()
			falsevalue = unicode(parent.pluginProps["falsewhen"]).lower()
			
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
				
			if statevalue:
				parent.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
			else:
				parent.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
			
			states = []
			states = iutil.updateState ("statedisplay", unicode(statevalue).lower(), states)
			states = iutil.updateState ("convertedValue", unicode(statevalue).lower(), states)
			states = iutil.updateState ("convertedBoolean", statevalue, states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
	
	#
	# Boolean to boolean type
	#
	def _booleanToType (self, parent, child, value):
		try:
			value = unicode(value).lower()
			
			statevalue = "na"
			statebool = False
			
			truevalue = "na"
			falsevalue = "na"
			
			if parent.pluginProps["booltype"] == "tf":
					truevalue = "true"
					falsevalue = "false"
					
			elif parent.pluginProps["booltype"] == "yesno":
					truevalue = "yes"
					falsevalue = "no"
					
			elif parent.pluginProps["booltype"] == "onoff":
					truevalue = "on"
					falsevalue = "off"
					
			elif parent.pluginProps["booltype"] == "oz":
					truevalue = "1"
					falsevalue = "0"
					
			elif parent.pluginProps["booltype"] == "oc":
					truevalue = "open"
					falsevalue = "closed"
					
			elif parent.pluginProps["booltype"] == "rdy":
					truevalue = "ready"
					falsevalue = "not ready"
					
			elif parent.pluginProps["booltype"] == "avail":
					truevalue = "available"
					falsevalue = "not available"
					
			elif parent.pluginProps["booltype"] == "gbad":
					truevalue = "good"
					falsevalue = "bad"	
					
			elif parent.pluginProps["booltype"] == "lock":
					truevalue = "locked"
					falsevalue = "unlocked"		
					
			if value == "true":
				statebool = True
				if parent.pluginProps["reverse"]: statebool = False
			else:
				statebool = False
				if parent.pluginProps["reverse"]: statebool = True
			
			if statebool: 
				statevalue = truevalue
			else:
				statevalue = falsevalue
				
			if statebool:
				parent.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
			else:
				parent.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
			
			states = []
			states = iutil.updateState ("statedisplay", unicode(statevalue).lower(), states)
			states = iutil.updateState ("convertedValue", unicode(statevalue).lower(), states)
			states = iutil.updateState ("convertedBoolean", statebool, states)
			if parent.pluginProps["booltype"] == "oz": states = iutil.updateState ("convertedNumber", int(statevalue), states)
			
			parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
	
	################################################################################
	# INDIGO COMMAND HAND-OFFS
	#
	# Everything below here are standard Indigo plugin actions that get handed off
	# to the engine, they really shouldn't change from plugin to plugin
	################################################################################
	
	################################################################################
	# INDIGO PLUGIN EVENTS
	################################################################################		
	
	# System
	def startup(self): return eps.plug.startup()
	def shutdown(self): return eps.plug.shutdown()
	def runConcurrentThread(self): return eps.plug.runConcurrentThread()
	def stopConcurrentThread(self): return eps.plug.stopConcurrentThread()
	def __del__(self): return eps.plug.delete()
	
	# UI
	def validatePrefsConfigUi(self, valuesDict): return eps.plug.validatePrefsConfigUi(valuesDict)
	def closedPrefsConfigUi(self, valuesDict, userCancelled): return eps.plug.closedPrefsConfigUi(valuesDict, userCancelled)
	
	################################################################################
	# INDIGO DEVICE EVENTS
	################################################################################
	
	# Basic comm events
	def deviceStartComm (self, dev): return eps.plug.deviceStartComm (dev)
	def deviceUpdated (self, origDev, newDev): return eps.plug.deviceUpdated (origDev, newDev)
	def deviceStopComm (self, dev): return eps.plug.deviceStopComm (dev)
	def deviceDeleted(self, dev): return eps.plug.deviceDeleted(dev)
	def actionControlDimmerRelay(self, action, dev): return eps.plug.actionControlDimmerRelay(action, dev)
	
	# UI Events
	def getDeviceDisplayStateId(self, dev): return eps.plug.getDeviceDisplayStateId (dev)
	def validateDeviceConfigUi(self, valuesDict, typeId, devId): return eps.plug.validateDeviceConfigUi(valuesDict, typeId, devId)
	def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId): return eps.plug.closedDeviceConfigUi(valuesDict, userCancelled, typeId, devId)		
	
	################################################################################
	# INDIGO PROTOCOL EVENTS
	################################################################################
	def zwaveCommandReceived(self, cmd): return eps.plug.zwaveCommandReceived(cmd)
	def zwaveCommandSent(self, cmd): return eps.plug.zwaveCommandSent(cmd)
	def insteonCommandReceived (self, cmd): return eps.plug.insteonCommandReceived(cmd)
	def insteonCommandSent (self, cmd): return eps.plug.insteonCommandSent(cmd)
	def X10CommandReceived (self, cmd): return eps.plug.X10CommandReceived(cmd)
	def X10CommandSent (self, cmd): return eps.plug.X10CommandSent(cmd)

	################################################################################
	# INDIGO VARIABLE EVENTS
	################################################################################
	
	# Basic comm events
	def variableCreated(self, var): return eps.plug.variableCreated(var)
	def variableUpdated (self, origVar, newVar): return eps.plug.variableUpdated (origVar, newVar)
	def variableDeleted(self, var): return self.variableDeleted(var)
		
	################################################################################
	# INDIGO EVENT EVENTS
	################################################################################
	
	# Basic comm events
	
	# UI
	def validateEventConfigUi(self, valuesDict, typeId, eventId): return eps.plug.validateEventConfigUi(valuesDict, typeId, eventId)
	def closedEventConfigUi(self, valuesDict, userCancelled, typeId, eventId): return eps.plug.closedEventConfigUi(valuesDict, userCancelled, typeId, eventId)
		
	################################################################################
	# INDIGO ACTION EVENTS
	################################################################################
	
	# Basic comm events
	def actionGroupCreated(self, actionGroup): eps.plug.actionGroupCreated(actionGroup)
	def actionGroupUpdated (self, origActionGroup, newActionGroup): eps.plug.actionGroupUpdated (origActionGroup, newActionGroup)
	def actionGroupDeleted(self, actionGroup): eps.plug.actionGroupDeleted(actionGroup)
		
	# UI
	def validateActionConfigUi(self, valuesDict, typeId, actionId): return eps.plug.validateActionConfigUi(valuesDict, typeId, actionId)
	def closedActionConfigUi(self, valuesDict, userCancelled, typeId, actionId): return eps.plug.closedActionConfigUi(valuesDict, userCancelled, typeId, actionId)
		
	################################################################################
	# INDIGO TRIGGER EVENTS
	################################################################################
	
	# Basic comm events
	def triggerStartProcessing(self, trigger): return eps.plug.triggerStartProcessing(trigger)
	def triggerStopProcessing(self, trigger): return eps.plug.triggerStopProcessing(trigger)
	def didTriggerProcessingPropertyChange(self, origTrigger, newTrigger): return eps.plug.didTriggerProcessingPropertyChange(origTrigger, newTrigger)
	def triggerCreated(self, trigger): return eps.plug.triggerCreated(trigger)
	def triggerUpdated(self, origTrigger, newTrigger): return eps.plug.triggerUpdated(origTrigger, newTrigger)
	def triggerDeleted(self, trigger): return eps.plug.triggerDeleted(trigger)
                                   
	# UI
	
	################################################################################
	# INDIGO SYSTEM EVENTS
	################################################################################
	
	# Basic comm events
	
	# UI
	
	################################################################################
	# EPS EVENTS
	################################################################################		
	
	# Plugin menu actions
	def pluginMenuSupportData (self): return eps.plug.pluginMenuSupportData ()
	def pluginMenuSupportDataEx (self): return eps.plug.pluginMenuSupportDataEx ()
	def pluginMenuSupportInfo (self): return eps.plug.pluginMenuSupportInfo ()
	def pluginMenuCheckUpdates (self): return eps.plug.pluginMenuCheckUpdates ()
	
	# UI Events
	def getCustomList (self, filter="", valuesDict=None, typeId="", targetId=0): return eps.ui.getCustomList (filter, valuesDict, typeId, targetId)
	def formFieldChanged (self, valuesDict, typeId, devId): return eps.plug.formFieldChanged (valuesDict, typeId, devId)
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	