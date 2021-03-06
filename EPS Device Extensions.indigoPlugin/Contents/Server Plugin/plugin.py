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
import json
import thread

from lib.ivoice import IndigoVoice
ivoice = IndigoVoice()


eps = eps(None)

# Enumerations
kCurtainPositionOpening = u'opening'
kCurtainPositionPartOpen = u'partopen'
kCurtainPositionHalfOpen = u'halfopen'
kCurtainPositionOpen = u'open'
kCurtainPositionClosing = u'closing'
kCurtainPositionPartClosed = u'partclosed'
kCurtainPositionHalfClosed = u'halfclosed'
kCurtainPositionClosed = u'closed'
kCurtainSwingOpen = u'open'
kCurtainSwingClosed = u'closed'

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
	
	# For the Relay To Dimmer Converter
	StartCalibrationTime = None
	StopCalibrationTime = None
		
	CalibrationTimes = []
	
	#
	# Init
	#
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		eps.__init__ (self)
		eps.loadLibs (self.PLUGIN_LIBS)
		
		self.thermostats = []
		self.resetDevices = [] # Devices that get high/low resets every 24 hours
		self.thermostatPreset = [] # Thermostats that have active presets to expire
		self.updateDevices = [] # Anything that needs to have the status updated regularly but the referenced device doesn't have a state to trigger it
		
		
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
			self.logger.threaddebug ("Checking for plugin upgrades")
			
			upgradeSuccess = True
			
			if ext.valueValid (self.pluginPrefs, "currentVersion") == False:
				previousVersion = 153 # Force it to think we are upgrading from 1.53 to ensure all updates are done
			else:
				previousVersion = self.pluginPrefs["currentVersion"]
				previousVersion = int(previousVersion.replace(".", ""))
				
			# Perform upgrades in REVERSE order so that each one gets done as needed before we write the current version
			if previousVersion < 210: # 2.1.0
				# Upgrade devices modified in 2.0.5+ (2.1.0 previews) and earlier
				self.logger.warn ("Upgrading plugin from version 2.0.6 (version 2.1.0 preview builds) or later")
				
				# Changing from using the checkbox to indicate a device to using a dropdown box
				for dev in indigo.devices.iter(self.pluginId):
					if "chdevice" in dev.pluginProps:
						self.logger.info ("...upgrading {1} device '{0}' device checkbox to combobox".format(dev.name, dev.model))
						
						props = dev.pluginProps
						
						if props["chdevice"]:
							props["objectype"] = "device"
						else:
							props["objectype"] = "variable"
							indigo.server.log("variable")
							
						# While we are here lets ensure that static True/False gets the new objectype
						if (props["action"] == "true" or props["action"] == "false") and props["objectype"] != "static":
							self.logger.info ("......static true/false detected, upgrading object to static")
							props["objectype"] = "static"
							
						# Add new fields since this is a conversion device
						self.logger.info ("......adding fields to device created in 2.1.0")
						if "extraaction" not in props: props["extraaction"] = ""
						if "threshold" not in props: props["threshold"] = "60"
						
						dev.replacePluginPropsOnServer (props)
						
				# Add the conversion address preference to the plugin prefs
				if "conversionAddress" not in self.pluginPrefs:
					self.logger.info ("...adding plugin preference for Conversion Extension address format")
					
					self.pluginPrefs["conversionAddress"] = "object"
					
				# Clean up potential plugin pref garbage:
				self.logger.info ("...cleaning up unused values from plugin prefs")
				
				if "deviceList" in self.pluginPrefs: del self.pluginPrefs["deviceList"]
				if "homebridgeHost" in self.pluginPrefs: del self.pluginPrefs["homebridgeHost"]
				if "homebridgeName" in self.pluginPrefs: del self.pluginPrefs["homebridgeName"]
				if "homebridgePass" in self.pluginPrefs: del self.pluginPrefs["homebridgePass"]
				if "homebridgePort" in self.pluginPrefs: del self.pluginPrefs["homebridgePort"]
				if "homebridgeUser" in self.pluginPrefs: del self.pluginPrefs["homebridgeUser"]
				if "lastUpdateCheck" in self.pluginPrefs: del self.pluginPrefs["lastUpdateCheck"]
						
			if previousVersion < 205:
				self.logger.warn ("Upgrading plugin from version 2.0.5 or earlier")
			
				# finding all "lastChanged" states being used
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
					
			if upgradeSuccess:
				self.pluginPrefs["currentVersion"] = self.pluginVersion
			
			else:
				self.logger.error ("One or more problems are preventing the plugin from upgrading your settings and devices, please correct the issues and restart the plugin.")
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Concurrent Thread (.6 to .8 CPU)
	#
	def onAfter_runConcurrentThread(self):
		try:
			#eps.memory_summary()
			
			# Check any devices that require high/low reset in the local reset cache
			if len(self.resetDevices) > 0:
				d = indigo.server.getTime()
				
				for devDetail in self.resetDevices:
					needsReset = False
					
					if devDetail["lastreset"] != "":
						if dtutil.dateDiff ("hours", d, str(devDetail["lastreset"]) + " 00:00:00") >= 24:
							needsReset = True
					
					else:
						needsReset = True
							
					if needsReset:
						self.logger.debug ("Resetting highs and lows for device '{0}'".format(devDetail["name"]))
						if devDetail["id"] in indigo.devices:
							parent = indigo.devices[devDetail["id"]]
							self.resetHighsLows (parent)
			
			# Devices needing ongoing refreshes
			if len(self.updateDevices) > 0:
				d = indigo.server.getTime()
				
				for udev in self.updateDevices:
					if udev in indigo.devices:
						dev = indigo.devices[udev]
						if dtutil.dateDiff ("seconds", d, str(dev.lastChanged)) >= 59:
							self.updateFromPluginDevice (dev)
		
			# Irrigation timers (returns quickly if irrigation is idle)
			if "epsdeirr" in eps.cache.pluginItems:
				for devId in eps.cache.pluginItems["epsdeirr"]:
					self.calculateTimeRemaining (indigo.devices[devId])
					
			#return here for .3 to .4 CPU
					
			# Thermostat preset timers
			if len(self.thermostatPreset) > 0:
				d = indigo.server.getTime()
				
				for tdev in self.thermostatPreset:
					needsReset = False
					
					if devDetail["expiration"] != "":
						autoOff = datetime.datetime.strptime (devDetail["expiration"], "%Y-%m-%d %H:%M:%S")
						if dtutil.dateDiff ("seconds", autoOff, d) < 1:
							self.logger.info ("The preset {1} for '{0}' has expired, reverting to pre-preset settings".format(devDetail["name"], str(devDetail["preset"])))
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
				#if dev.pluginProps["chdevice"] and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
				if dev.pluginProps["objectype"] == "device" and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
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
					
			if dev.deviceTypeId == "thermostat-wrapper":	
				deviceSettings = json.loads(dev.pluginProps["deviceSettings"])
				for d in deviceSettings:
					states = []	
					
					if d["option1Type"] == "device" and d["option1Device"] != "" and d["option1State"] != "": 
						states.append(d["option1State"])
						ret[int(d["option1Device"])] = states
						
					if d["key"] == "thermostat":
						child = indigo.devices[int(d["thermostatdevice"])]
						statelist = ["hvacFanMode", "hvacOperationMode", "setpointCool", "setpointHeat", "temperatureInput1", "temperatureInputsAll", "humidityInput1", "humidityInputsAll"]
						
						for s in statelist:
							if ext.valueValid (child.states, s): states.append (s)
						
						ret[int(d["thermostatdevice"])] = states
						
			if dev.deviceTypeId == "hue-color-group":
				if "huelights" in dev.pluginProps:
					for d in dev.pluginProps["huelights"]:
						states = ["whiteLevel", "greenLevel", "redLevel", "blueLevel", "whiteTemperature", "onOffState", "brightnessLevel"]	
						
						ret[int(d)] = states
						
			if dev.deviceTypeId == "Filter-Sensor":	
				if ext.valueValid (dev.pluginProps, "device", True):
					states = []	
					child = indigo.devices[int(dev.pluginProps["device"])]
					
					# Some of these aren't actually needed but when they change (like temperature) it's regularly updating our device without having to put it in concurrent thread :)
					if ext.valueValid (child.states, "temperatureInput1"): states.append ("temperatureInput1")
					if ext.valueValid (child.states, "humidityInput1"): states.append ("humidityInput1")
					if ext.valueValid (child.states, "hvacFanModeIsAuto"): states.append ("hvacFanModeIsAuto")
					if ext.valueValid (child.states, "hvacFanModeIsAlwaysOn"): states.append ("hvacFanModeIsAlwaysOn")
					if ext.valueValid (child.states, "hvacOperationModeIsOff"): states.append ("hvacOperationModeIsOff")
					if ext.valueValid (child.states, "setpointCool"): states.append ("setpointCool")
					if ext.valueValid (child.states, "setpointHeat"): states.append ("setpointHeat")
					if ext.valueValid (child.states, "hvacFanIsOn"): states.append ("hvacFanIsOn")

					if ext.valueValid (child.states, "iscooling"): states.append ("iscooling") # Nest
					if ext.valueValid (child.states, "isheating"): states.append ("isheating") # Nest
					if ext.valueValid (child.states, "fan_timer_active"): states.append ("fan_timer_active") # Nest
					
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
				#if dev.pluginProps["chdevice"] and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
				if dev.pluginProps["objectype"] == "device" and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
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
			self.logger.threaddebug ("Running plugin onWatchedStateChanged")
			
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
			self.logger.threaddebug ("Running plugin onWatchedAttributeChanged")
			
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
			self.logger.threaddebug ("Running plugin onAfter_pluginDevicePropChanged")
			self.updateFromPluginDevice (newDev)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# A plugin device was created
	#
	def onAfter_pluginDeviceCreated (self, dev):	
		try:
			self.logger.threaddebug ("Running plugin onAfter_pluginDeviceCreated")
			
			self.updateFromPluginDevice (dev)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Validate device config
	#
	def onAfter_validateDeviceConfigUi(self, valuesDict, typeId, devId):
		try:
			errorDict = indigo.Dict()
			success = True
			
			if typeId == "Relay-To-Dimmer":
				return self.relayToDimmerValidateDeviceConfigUi (valuesDict, typeId, devId)
			
			# Make sure if this device is not doing elapsed minutes that is is not getting constantly polled
			if typeId == "epsdecon":
				dev = indigo.devices[devId]
				if dev.deviceTypeId == "epsdecon" and dev.pluginProps["action"] != "dtmin":
					if dev.id in self.updateDevices:
						newdevices = []
						for d in self.updateDevices:
							if d != dev.id:
								newdevices.append(d)
								
						self.updateDevices = newdevices
			
			# If we have filter sensors that aren't using HVAC runtime we need to check them regularly			
			if typeId == "Filter-Sensor":
				dev = indigo.devices[devId]
				if dev.deviceTypeId == "Filter-Sensor" and dev.pluginProps["method"] != "runtime":
					if dev.id not in self.updateDevices:
						self.updateDevices.append (dev.id)
				else:
					# If it's doing HVAC make sure it is NOT getting polled regularly
					if dev.id in self.updateDevices:
						newdevices = []
						for d in self.updateDevices:
							if d != dev.id:
								newdevices.append(d)
								
						self.updateDevices = newdevices
			
			if typeId == "thermostat-wrapper":
				(hbbValuesDict, hbbErrorsDict) = hbb.validateDeviceConfigUi (valuesDict, typeId, devId)
				if len(hbbErrorsDict) > 0:
					return (False, hbbValuesDict, hbbErrorsDict)
				
				if "deviceSettings" not in valuesDict:
					valuesDict["deviceSettings"] = json.dumps([])
			
				deviceSettings = json.loads(valuesDict["deviceSettings"])
				
				# Set device defaults, we'll change these below if needed
				valuesDict["NumTemperatureInputs"] 			= "0"
				valuesDict["NumHumidityInputs"] 			= "0"
				valuesDict["SupportsHeatSetpoint"] 			= False
				valuesDict["SupportsCoolSetpoint"] 			= False
				valuesDict["SupportsHvacOperationMode"] 	= False
				valuesDict["SupportsHvacFanMode"] 			= False
				valuesDict["ShowCoolHeatEquipmentStateUI"] 	= False
				
				for d in deviceSettings:
					if d["key"] == "thermostat" and d["thermostatdevice"] != "":
						if int(d["thermostatdevice"]) in indigo.devices:
							dev = indigo.devices[int(d["thermostatdevice"])]
							
							valuesDict["NumTemperatureInputs"] 			= dev.temperatureSensorCount
							valuesDict["NumHumidityInputs"] 			= dev.humiditySensorCount
							valuesDict["SupportsHeatSetpoint"] 			= dev.supportsHeatSetpoint
							valuesDict["SupportsCoolSetpoint"] 			= dev.supportsCoolSetpoint
							valuesDict["SupportsHvacOperationMode"] 	= dev.supportsHvacOperationMode
							valuesDict["SupportsHvacFanMode"] 			= dev.supportsHvacFanMode
							#valuesDict["ShowCoolHeatEquipmentStateUI"] = dev.humiditySensorCount
					
					# Temperature (allows for only 1 temperature input at the moment)
					if d["key"] == "temp":
						# Device
						if d["option1Type"] == "device" and d["option1Device"] != "" and d["option1State"] != "":
							if int(d["option1Device"]) in indigo.devices:
								dev = indigo.devices[int(d["option1Device"])]
								if d["option1State"] in dev.states:
									valuesDict["NumTemperatureInputs"]	= "1"
					
					# Humidity (only supports 1)		
					if d["key"] == "humidity":
						# Device
						if d["option1Type"] == "device" and d["option1Device"] != "" and d["option1State"] != "":
							if int(d["option1Device"]) in indigo.devices:
								dev = indigo.devices[int(d["option1Device"])]
								if d["option1State"] in dev.states:
									valuesDict["NumHumidityInputs"]	= "1"
							
							
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return (success, valuesDict, errorDict)
			
	#
	# A plugin device was started
	#
	def onAfter_deviceStartComm (self, dev):	
		try:
			self.logger.threaddebug ("Running plugin onAfter_deviceStartComm")
			
			# Update the status of the devices
			self.updateFromPluginDevice (dev)
			
			# If this is a thermostat or weather device then we have 24 hour high/low resets to cache, save them to the global variable so we can check on it
			# This routine was taken out of concurrent threading as of 2.0.4 to save .2 to .4 CPU utilization at idle
			if dev.deviceTypeId == "epsdeth" or dev.deviceTypeId == "epsdews":
				if "lasthighlowreset" in dev.states: 
					devDetail = {}
					d = indigo.server.getTime()

					devDetail["id"] = dev.id
					devDetail["name"] = dev.name
					devDetail["lastreset"] = ""

					devDetail["lastreset"] = dev.states["lasthighlowreset"]				
					if devDetail["lastreset"] == "":
						self.resetHighsLows (dev)
						devDetail["lastreset"] = d.strftime("%Y-%m-%d") # Because it's always at midnight, we only need to store the date, not the time
						
					self.resetDevices.append (devDetail)
					
			# For Date Time to Elapsed Minutes we have to monitor constantly, add to update devices
			if dev.deviceTypeId == "epsdecon" and dev.pluginProps["action"] == "dtmin":
				self.updateDevices.append (dev.id)
				
			if dev.deviceTypeId == "Filter-Sensor" and dev.pluginProps["method"] != "runtime":
				self.updateDevices.append (dev.id)	
							
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
	#
	# A form field changed
	#
	def onAfter_formFieldChanged (self, valuesDict, typeId, devId):	
		try:
			if typeId == "thermostat-wrapper": return self.onAfter_formFieldChanged_Thermostat_Wrapper (valuesDict, typeId, devId)	
			if typeId == "hue-color-group": return self.onAfter_formFieldChanged_Hue_Color_Group (valuesDict, typeId, devId)	
			if typeId == "Relay-To-Dimmer": return self.relayToDimmerFormFieldChanged (valuesDict, typeId, devId)	
			
			if typeId == "epsdecon":
				if valuesDict["action"] == "true" or valuesDict["action"] == "false":
					valuesDict["objectype"] = "static"
					valuesDict["device"] = ""
					valuesDict["states"] = ""
				
				else:
					if valuesDict["objectype"] == "static": valuesDict["objectype"] = "device"
					
				if valuesDict["objectype"] == "static" and valuesDict["action"] != "true" and valuesDict["action"] != "false":
					values["objectType"] = "true" # Default to one of the static values if they choose static and aren't on one already
					
			
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
	# A form field changed
	#
	def onAfter_formFieldChanged_Hue_Color_Group (self, valuesDict, typeId, devId):
		try:
			if valuesDict["keepsync"] == "": valuesDict["keepsync"] = "none"
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict	
		
	#
	# A form field changed
	#
	def onAfter_formFieldChanged_Thermostat_Wrapper (self, valuesDict, typeId, devId):		
		try:
			if "deviceSettings" not in valuesDict:
				valuesDict["deviceSettings"] = json.dumps([])
			
			deviceSettings = json.loads(valuesDict["deviceSettings"])
			
			# Find and update this setting in the JSON
			settingFound = False
			for d in deviceSettings:
				if d["key"] == valuesDict["optionSelect"]:
					settingFound = True
				
					if valuesDict["loadedoption"] != d["key"]: # Only load the stored JSON once
						valuesDict["loadedoption"] = d["key"]
				
						valuesDict["option1Type"] = d["option1Type"]
						valuesDict["option1Device"] = d["option1Device"]
						valuesDict["option1State"] = d["option1State"]
						valuesDict["option1Action"] = d["option1Action"]
						valuesDict["option1Variable"] = d["option1Variable"]
				
						valuesDict["temperatureType"] = d["temperatureType"] # Temperature
						valuesDict["thermostatdevice"] = d["thermostatdevice"] # Thermostat Wrap
						
					break # we found what we need, break out of the loop
				
			if not settingFound: 
				d = {}
			
				# Reset all fields to defaults		
				if valuesDict["loadedoption"] != "" and valuesDict["loadedoption"] != valuesDict["optionSelect"]:
					valuesDict["option1Type"] = "device"
					valuesDict["option1Device"] = ""
					valuesDict["option1State"] = ""
					valuesDict["option1Action"] = ""
					valuesDict["option1Variable"] = ""
		
					# Device type specific fields
					valuesDict["temperatureType"] = "F" # Temperature
					valuesDict["thermostatdevice"] = "" # Thermostat wrap
				
					#indigo.server.log ("CLEARED!")
		
			valuesDict["loadedoption"] = valuesDict["optionSelect"]
		
			d["key"] 				= valuesDict["optionSelect"]
			d["option1Type"] 		= valuesDict["option1Type"]
			d["option1Device"] 		= valuesDict["option1Device"]
			d["option1State"] 		= valuesDict["option1State"]
			d["option1Action"] 		= valuesDict["option1Action"]
			d["option1Variable"] 	= valuesDict["option1Variable"]

			d["temperatureType"] = valuesDict["temperatureType"]
			d["thermostatdevice"] = valuesDict["thermostatdevice"]
			
			# At least during testing we have locked out changing from device to anything else but we will force it here for some settings
			indigo.server.log(valuesDict["optionSelect"])
			if valuesDict["optionSelect"] == "temp" or valuesDict["optionSelect"] == "humidity":
				valuesDict["option1Type"] = "device"
			
			elif valuesDict["optionSelect"] == "heatsetpoint" or valuesDict["optionSelect"] == "coolsetpoint":
				valuesDict["option1Type"] = "device"
			
			elif valuesDict["optionSelect"] == "thermostat":
				valuesDict["option1Type"] = "thermostat"	
			
			else:
				valuesDict["option1Type"] = "action"	
				
			# Sanity check so we don't add empty values to the JSON table
			if d["option1Device"] == "" and d["option1Action"]  == "" and d["option1Variable"]  == "" and d["thermostatdevice"] == "":
				return valuesDict	
	
			# Save new JSON data
			newDeviceSettings = []
			for old in deviceSettings:
				if old["key"] != d["key"]: newDeviceSettings.append (old)
		
			newDeviceSettings.append (d) # Write this data
		
			valuesDict["deviceSettings"] = json.dumps(newDeviceSettings)
	
			#indigo.server.log(unicode(valuesDict))		
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict
		
	#
	# Device turned on
	#
	def onDeviceCommandTurnOn (self, dev):
		try:
			if dev.deviceTypeId == "Relay-To-Dimmer":
				return self.relayToDimmerTurnedOn (dev)
			
			if "onCommand" in dev.pluginProps and dev.pluginProps["onCommand"] != "":
				if self.urlDeviceAction (dev, dev.pluginProps["onCommand"]) == False: 
					return False			
				else:
					return True
					
			if dev.deviceTypeId == "hue-color-group":
				for d in dev.pluginProps["huelights"]:
					if int(d) in indigo.devices:
						hue = indigo.devices[int(d)]
						indigo.dimmer.turnOn (int(d))
						
				return True
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False
		
	#
	# Device turned off
	#
	def onDeviceCommandTurnOff (self, dev):
		try:
			if dev.deviceTypeId == "Relay-To-Dimmer":
				return self.relayToDimmerTurnedOff (dev)
				
			if "offCommand" in dev.pluginProps and dev.pluginProps["offCommand"] != "":
				if self.urlDeviceAction (dev, dev.pluginProps["onCommand"]) == False: 
					return False			
				else:
					return True
					
			if dev.deviceTypeId == "hue-color-group":
				for d in dev.pluginProps["huelights"]:
					if int(d) in indigo.devices:
						hue = indigo.devices[int(d)]
						
						# See if they have an OFF setting
						if "beforeoff" in dev.pluginProps and dev.pluginProps["beforeoff"]:
							value = 0
							
							if dev.pluginProps["resettemp"] != "":
								value = int(dev.pluginProps["resettemp"])
							else:
								value = 0
								
							indigo.dimmer.setColorLevels (int(d), whiteTemperature=value)	
							
							if dev.pluginProps["resetwhite"] != "":
								value = int(dev.pluginProps["resetwhite"])
							else:
								value = 0
								
							indigo.dimmer.setColorLevels (int(d), whiteLevel=value)	
							
							valred = 0
							valgreen = 0
							valblue = 0
							
							if dev.pluginProps["resetred"] != "":
								valred = int(dev.pluginProps["resetred"])
							else:
								valred = 0
								
							if dev.pluginProps["resetgreen"] != "":
								valgreen = int(dev.pluginProps["resetgreen"])
							else:
								valgreen = 0	
								
							if dev.pluginProps["resetblue"] != "":
								valblue = int(dev.pluginProps["resetblue"])
							else:
								valblue = 0		
							
							indigo.dimmer.setColorLevels (int(d), redLevel=valred, greenLevel=valgreen, blueLevel=valblue)
							
							if dev.pluginProps["resetbrightness"] != "":
								value = int(dev.pluginProps["resetbrightness"])
							else:
								value = 0
								
							indigo.dimmer.setBrightness (int(d), value=value)	
										
						
						indigo.dimmer.turnOff (int(d))	
						
				return True	
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False	
		
	#
	# Set brightness
	#
	def onDeviceCommandSetBrightness (self, dev, amount):
		try:
			if dev.deviceTypeId == "Relay-To-Dimmer":
				return self.relayToDimmerSetBrightness (dev, amount)
				
			if dev.deviceTypeId == "hue-color-group":
				for d in dev.pluginProps["huelights"]:
					if int(d) in indigo.devices:
						hue = indigo.devices[int(d)]
						indigo.dimmer.setBrightness (int(d), value=amount)	
						
				return True	
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False	
		
	#
	# Set color
	#
	def onDeviceCommandSetColor (self, dev, amount):
		try:
			if dev.deviceTypeId == "hue-color-group":
				for d in dev.pluginProps["huelights"]:
					if int(d) in indigo.devices:
						hue = indigo.devices[int(d)]
						indigo.server.log(unicode(amount))
						
						if 'redLevel' in amount and 'greenLevel' in amount and 'blueLevel' in amount:
							indigo.dimmer.setColorLevels (int(d), redLevel=amount['redLevel'], greenLevel=amount['greenLevel'], blueLevel=amount['blueLevel'])
						elif 'whiteLevel' in amount:
							indigo.dimmer.setColorLevels (int(d), whiteLevel=amount['whiteLevel'])	
						elif 'whiteLevel2' in amount:
							indigo.dimmer.setColorLevels (int(d), whiteLevel2=amount["whiteLevel2"])	
						elif 'whiteTemperature' in amount:
							indigo.dimmer.setColorLevels (int(d), whiteTemperature=amount["whiteTemperature"])	
						
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
	# INDIGO VOICE API INTEGRATION
	################################################################################
	
	def voiceIntegrationFieldChange (self, valuesDict, typeId, devId): return ivoice.integrationFieldChange (valuesDict, typeId, devId)
	def voiceHKBIntegrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.HKBIntegrationServerList (filter, valuesDict, typeId, targetId)
	def voiceAHBIntegrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.AHBIntegrationServerList (filter, valuesDict, typeId, targetId)
	def voiceIntegrationHKBDeviceTypeList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.IntegrationHKBDeviceTypeList (filter, valuesDict, typeId, targetId)
	def voiceIntegrationPluginList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.IntegrationPluginList (filter, valuesDict, typeId, targetId)
	def voiceAPICall (self, action): return ivoice.APICall (action)
	
	################################################################################
	# FILTER SENSOR
	################################################################################	
	
	#
	# Filter Sensor Actions
	#
	def filterSensorAction (self, devAction):
		try:
			parent = indigo.devices[devAction.deviceId]
			
			# Reset all states
			states = []

			states = iutil.updateState ("hvacRunning", False, states)
			states = iutil.updateState ("hvacruntime", 0, states)
			states = iutil.updateState ("runtime", 0, states, "")
			states = iutil.updateState ("lifeLevel", 0, states)
			states = iutil.updateState ("onOffState", False, states)
			states = iutil.updateState ("sensorValue", 100, states, "100.0%")
						
			parent.updateStatesOnServer (states)
									
			indigo.server.log(unicode(devAction))
			
		except Exception as e:
			self.logger.error (ext.getException(e))
	
	#
	# Update filter sensor
	#
	def _updateFilterSensor (self, parent, child, value):
		try:
			hvacruntime = parent.states["hvacruntime"]
			d = indigo.server.getTime()
			
			if parent.states["lastChanged"] == "":
				parent.updateStateOnServer(key="lastChanged", value=d.strftime("%Y-%m-%d %H:%M:%S"))	
				
			if parent.states["lastUpdate"] == "":
				parent.updateStateOnServer(key="lastUpdate", value=d.strftime("%Y-%m-%d %H:%M:%S"))	
			
			# Calculate minutes since last reset - mostly used for our date based reset sensors
			hours = dtutil.dateDiff ("hours", indigo.server.getTime(), datetime.datetime.strptime (parent.states["lastChanged"], "%Y-%m-%d %H:%M:%S"))
			days = round(hours / 24, 5)
			weeks = round(days / 7, 5)
			months = round(days / 30, 5)
			runtimeUI = str(round(hours, 5)) + " Hours"
			
			# Set up the UI
			if parent.pluginProps["method"] == "days": runtimeUI = str(round(days, 1)) + " Days"
			if parent.pluginProps["method"] == "weeks": runtimeUI = str(round(weeks, 1)) + " Weeks"
			if parent.pluginProps["method"] == "months": runtimeUI = str(round(months, 1)) + " Months"
			
						
			# If it's a thermostat based sensor then calculate run times if needed
			if parent.pluginProps["method"] == "runtime":
				if child.pluginId != "com.corporatechameleon.nestplugBeta":
					if child.fanIsOn and not parent.states["hvacRunning"]:
						parent.updateStateOnServer(key="hvacStart", value=d.strftime("%Y-%m-%d %H:%M:%S")) # Start tracking on time
						parent.updateStateOnServer(key="hvacRunning", value=True)
				
					elif not child.fanIsOn and parent.states["hvacRunning"]:
						parent.updateStateOnServer(key="hvacStop", value=d.strftime("%Y-%m-%d %H:%M:%S")) # Start tracking on time
						parent.updateStateOnServer(key="hvacRunning", value=False)
						hvacruntime = hvacruntime + dtutil.dateDiff ("hours", datetime.datetime.strptime (parent.states["hvacStop"], "%Y-%m-%d %H:%M:%S"), datetime.datetime.strptime (parent.states["hvacStart"], "%Y-%m-%d %H:%M:%S"))
				
				elif child.pluginId == "com.corporatechameleon.nestplugBeta":	
					if not parent.states["hvacRunning"]:
						if child.states["iscooling"] == "Yes" or child.states["isheating"] == "Yes" or child.states["fan_timer_active"] or unicode(child.fanMode) == "AlwaysOn":
							parent.updateStateOnServer(key="hvacStart", value=d.strftime("%Y-%m-%d %H:%M:%S")) # Start tracking on time
							parent.updateStateOnServer(key="hvacRunning", value=True)
							#indigo.server.log ("HVAC TRACKING ON: \n" + unicode(child.states))
				
					elif parent.states["hvacRunning"]:
						#indigo.server.log ("3\n{}\n{}\n{}\n{}".format(unicode(child.states["iscooling"]), unicode(child.states["isheating"]), unicode(child.states["fan_timer_active"]), unicode(child.states["hvacFanModeIsAlwaysOn"])))
						if child.states["iscooling"] == "No" and child.states["isheating"] == "No" and child.states["fan_timer_active"] == False and child.states["hvacFanModeIsAlwaysOn"] == False:
							parent.updateStateOnServer(key="hvacStop", value=d.strftime("%Y-%m-%d %H:%M:%S")) # Start tracking on time
							parent.updateStateOnServer(key="hvacRunning", value=False)
							hvacruntime = hvacruntime + dtutil.dateDiff ("hours", datetime.datetime.strptime (parent.states["hvacStop"], "%Y-%m-%d %H:%M:%S"), datetime.datetime.strptime (parent.states["hvacStart"], "%Y-%m-%d %H:%M:%S"))
							#indigo.server.log ("HVAC TRACKING OFF")
						
			calcvalue = 0
			threshold = 0
			
			if parent.pluginProps["method"] == "runtime":
				calcvalue = hvacruntime
				if parent.pluginProps["runtime"] != "": threshold = float(parent.pluginProps["runtime"])
			
			else:
				if parent.pluginProps["timespan"] != "": threshold = float(parent.pluginProps["timespan"])
				if parent.pluginProps["method"] == "days": calcvalue = days
				if parent.pluginProps["method"] == "weeks": calcvalue = weeks
				if parent.pluginProps["method"] == "months": calcvalue = months
				
			if calcvalue >= threshold and not parent.states["onOffState"]:
				parent.updateStateOnServer(key="onOffState", value=True)
			elif calcvalue < threshold and parent.states["onOffState"]:
				parent.updateStateOnServer(key="onOffState", value=False)	
			
			# Calculate the sensor value of percent until the filter is used
			sensorvalue = 100 - (float(calcvalue / threshold) * 100) # 100% is max filter, so subtract our value from 100 to get the life left
					
			# Always set our update
			parent.updateStateOnServer(key="lastUpdate", value=d.strftime("%Y-%m-%d %H:%M:%S"))	
			parent.updateStateOnServer(key="runtime", value=hours, uiValue=runtimeUI)
			parent.updateStateOnServer(key="hvacruntime", value=round(hvacruntime, 5), uiValue=str(round(hvacruntime, 1)) + " Hours")	
			parent.updateStateOnServer(key="sensorValue", value=round(sensorvalue, 1), uiValue = str(round(sensorvalue, 1)) + "%" )
			
			return
			
			states = []
			bulbs = []
			allOn = True
			anyOn = False
			master = 0
			
			if parent.pluginProps["keepsync"] != "none" and parent.pluginProps["keepsync"] != "": master = int(parent.pluginProps["keepsync"])
			
			for d in parent.pluginProps["huelights"]:
				if int(d) in indigo.devices:
					bulb = indigo.devices[int(d)]
					if not bulb.states["onOffState"]: allOn = False
					if bulb.states["onOffState"]: anyOn = True
					bulbs.append(bulb)
					
			for b in bulbs:
				# If there is a master bulb then we ignore all others, otherwise we just take whatever
				if master != 0 and b.id != master:
					continue
					
				for state in b.states:
					if state in parent.states:
						states = iutil.updateState (state, b.states[state], states)
						
			parent.updateStatesOnServer (states)
			
			# If we are synchronizing then do that now
			if master !=0:
				bulb = indigo.devices[master]
				
				for b in bulbs:
					if b.id != bulb.id:
						if b.onState != bulb.onState:
							if bulb.onState:
								indigo.dimmer.turnOn (b.id)
							else:
								indigo.dimmer.turnOff (b.id)
								
						if b.brightness != bulb.brightness:
							indigo.dimmer.setBrightness (b.id, value=bulb.brightness)	
							
						if b.whiteLevel != bulb.whiteLevel:
							indigo.dimmer.setColorLevels (b.id, whiteLevel=bulb.whiteLevel)
						
						if b.whiteLevel2 != bulb.whiteLevel2:
							indigo.dimmer.setColorLevels (b.id, whiteLevel2=bulb.whiteLevel2)
						
						if b.whiteTemperature != bulb.whiteTemperature:
							indigo.dimmer.setColorLevels (b.id, whiteTemperature=bulb.whiteTemperature)
						
						if b.redLevel != bulb.redLevel or b.greenLevel != bulb.greenLevel or b.blueLevel != bulb.blueLevel:
							indigo.dimmer.setColorLevels (b.id, redLevel=bulb.redLevel, greenLevel=bulb.greenLevel, blueLevel=bulb.blueLevel)
						
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")	
	
	################################################################################
	# RELAY TO DIMMER CONVERSION
	################################################################################
	
	#
	# Validate form
	#
	def relayToDimmerValidateDeviceConfigUi (self, valuesDict, typeId, devId):
		try:
			success = True
			errorsDict = indigo.Dict()
			
			if valuesDict["device"] == "":
				errorsDict["showAlertText"] = "You must enter a relay device that this converted dimmer will be attached to."
				errorsDict["device"] = "Invalid device"
				return (False, valuesDict, errorsDict)
				
			(voiceSuccess, valuesDict, voiceErrors) = ivoice.validateDeviceConfigUi (valuesDict, typeId, devId)
			if not voiceSuccess: return (False, valuesDict, voiceErrors)
				
			valuesDict["address"] = indigo.devices[int(valuesDict["device"])].name
			
			if valuesDict["calibrate"]:
				indigo.devices[devId].updateStateOnServer("position", kCurtainPositionOpen)
				indigo.devices[devId].updateStateOnServer("onOffState", False, uiValue=kCurtainPositionOpen)

				msg = eps.ui.debugHeader ("CALIBRATION MODE")
				msg += eps.ui.debugLine ("Your device is in calibration mode, all on/off commands will be ")
				msg += eps.ui.debugLine ("used for calibration for the next six cycles.  To calibrate ")
				msg += eps.ui.debugLine ("use the following steps: ")
				msg += eps.ui.debugLine (" ")
				msg += eps.ui.debugLine ("Before you begin make sure that your source is ON or OPEN.")
				msg += eps.ui.debugLine (" ")
				msg += eps.ui.debugLine ("1. Turn ON the device, OFF when source is OFF or CLOSED")
				msg += eps.ui.debugLine ("2. Turn ON the device, OFF when source ON or OPEN")
				msg += eps.ui.debugLine ("3. Repeat steps 1-2 again (total of 6 ON/OFF cycles)")					
				msg += eps.ui.debugLine (" ")
				msg += eps.ui.debugLine ("When calibration is complete it will take the device out of  ")
				msg += eps.ui.debugLine ("calibration mode and it can be controlled normally.")
					
				msg += eps.ui.debugHeaderEx ()	
				self.logger.warning (msg)
				
			self.relayToDimmerUpdateStateIcon (devId)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return (success, valuesDict, errorsDict)
		
	#
	# Device ON received
	#
	def relayToDimmerTurnedOn (self, dev):
		try:
			if not "device" in dev.pluginProps or dev.pluginProps["device"] == "":
				self.logger.error ("The device that '{}' is supposed to be converting has not been defined".format(dev.name))
				return False
								
			outlet = indigo.devices[int(dev.pluginProps["device"])]
			
			if not dev.pluginProps["calibrate"]:
				# Open
				thread.start_new_thread(self.relayToDimmerSetToPercentage, (dev, outlet, 100))
				#self.relayToDimmerSetDeviceState (dev, 100)
				return True
				
			else:
				msg = eps.ui.debugHeader ("CALIBRATION #{} BEGIN".format(len(self.CalibrationTimes) + 1))
				self.logger.info (msg)
				
				self.StartCalibrationTime = indigo.server.getTime()
				indigo.device.turnOn (outlet.id)
				return True
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	
	#
	# Device OFF received
	#
	def relayToDimmerTurnedOff (self, dev):
		try:
			if not "device" in dev.pluginProps or dev.pluginProps["device"] == "":
				self.logger.error ("The device that '{}' is supposed to be converting has not been defined".format(dev.name))
				return False
								
			outlet = indigo.devices[int(dev.pluginProps["device"])]
				
			if not dev.pluginProps["calibrate"]:
				# Close
				thread.start_new_thread(self.relayToDimmerSetToPercentage, (dev, outlet, 0))
				#self.relayToDimmerSetDeviceState (dev, 0)
				return True	
			else:
				if dev.pluginProps["calibrate"]:
					self.relayToDimmerCurtainCalibration (dev, outlet)
				
				return True
		
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
	#
	# Set brightness of the curtains
	#
	def relayToDimmerSetBrightness (self, dev, amount):
		try:
			if not "device" in dev.pluginProps or dev.pluginProps["device"] == "":
				self.logger.error ("The device that '{}' is supposed to be converting has not been defined".format(dev.name))
				return False
								
			outlet = indigo.devices[int(dev.pluginProps["device"])]
			
			thread.start_new_thread(self.relayToDimmerSetToPercentage, (dev, outlet, amount))
			return True
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Run curtains for a number of seconds
	#
	def relayToDimmerSetToPercentage (self, dev, outlet, percentage, delay = 0.0):		
		try:
			if delay != 0: time.sleep(delay)
			if dev.brightness == percentage: return
			
			self.logger.info ("Processing '{}' to set to {}% from {}% that it is currently at".format(dev.name, percentage, dev.brightness))
			
			calibration = float(dev.states["calibration"])
			calibrationFraction = calibration / 100 # seconds per percent
			currentengagement = float(dev.states["currentengagement"]) # How many seconds we have run if we are not open or closed
			thisengagement = 0 # How many ACTUAL seconds we run if not opening or closing during this function
			
			swingLevel = dev.brightness # This will change if our swing is closed
			percentLevel = percentage # This will change if our swing is closed
			brightnessLevel = dev.brightness # Constant
			
			sleeptime = 0
			padding = 5 # Seconds to pad when we are opening or closing to ensure we get all the way there
			transitionState = kCurtainPositionOpening
						
			if dev.brightness == 100 and percentage == 0: # Open to close
				sleeptime = calibration
				transitionState = kCurtainPositionClosing
			
			elif dev.brightness == 0 and percentage == 100: # Close to open
				sleeptime = calibration

			else:
				if dev.states["swing"] == "open":
					# Brightness if face value (75% brightness is almost all the way open)
					if percentage < dev.brightness:
						# In order to go back we have to fully open, then reverse (and invert the value) to get to the destination
						self.relayToDimmerSetToPercentage (dev, outlet, 100)
						time.sleep(3) # Give it time to finish the cycle, otherwise it may cycle off-on-off too fast
						transitionState = kCurtainPositionClosing	
						swingLevel = 100 - dev.brightness
						percentLevel = 100 - percentage
						indigo.devices[dev.id].updateStateOnServer ("currentengagement", 0) # Reset as we would below
						currentengagement = 0
					
				else:
					transitionState = kCurtainPositionClosing
					
					# We have to reverse things because 75% brightness is actually 25% closed from an open state
					swingLevel = 100 - dev.brightness
					percentLevel = 100 - percentage
					
					if dev.brightness < percentage:
						# In order to go back we have to fully close, then reverse (and invert the value) to get to the destination
						self.relayToDimmerSetToPercentage (dev, outlet, 0)
						time.sleep(3) # Give it time to finish the cycle, otherwise it may cycle off-on-off too fast
						transitionState = kCurtainPositionOpening
						swingLevel = dev.brightness
						percentLevel = percentage
						indigo.devices[dev.id].updateStateOnServer ("currentengagement", 0) # Reset as we would below
						currentengagement = 0
										
				sleeptime = (percentLevel * calibrationFraction) - currentengagement						
				thisengagement = sleeptime
				
				
			# Everything now is common no matter what the percentage is
			if percentage == 100 or percentage == 0: sleeptime = sleeptime + padding

			self.logger.info ("Running {} for {} seconds".format(dev.name, str(sleeptime)))
			
			indigo.devices[dev.id].updateStateOnServer ("brightnessLevel", dev.brightness, uiValue=transitionState)
			
			self.logger.info ("Turning on '{}'".format(outlet.name))
			indigo.device.turnOn (outlet.id)
			time.sleep(sleeptime)
			indigo.device.turnOff (outlet.id)
			self.logger.info ("Just turned off '{}'".format(outlet.name))
			
			if percentage != 0 and percentage != 100:
				indigo.devices[dev.id].updateStateOnServer ("currentengagement", currentengagement + thisengagement)
			else:
				indigo.devices[dev.id].updateStateOnServer ("currentengagement", 0)
				
			
			self.relayToDimmerSetDeviceState (indigo.devices[dev.id], percentage)
		
		except Exception as e:
			self.logger.error (ext.getException(e))		
			
	#
	# Set state to match brightness
	#
	def relayToDimmerSetDeviceState (self, dev, percentage):
		try:
			if percentage == 100: 
				indigo.devices[dev.id].updateStateOnServer("onOffState", True, uiValue=kCurtainPositionOpen)
				indigo.devices[dev.id].updateStateOnServer("brightnessLevel", percentage, uiValue=kCurtainPositionOpen)
				
				indigo.devices[dev.id].updateStateOnServer("position", kCurtainPositionOpen)
				indigo.devices[dev.id].updateStateOnServer("swing", kCurtainSwingClosed) # Next action starts closing
				
			elif percentage == 0: 
				indigo.devices[dev.id].updateStateOnServer("onOffState", False, uiValue=kCurtainPositionClosed)
				indigo.devices[dev.id].updateStateOnServer("brightnessLevel", percentage, uiValue=kCurtainPositionClosed)
				
				indigo.devices[dev.id].updateStateOnServer("position", kCurtainPositionClosed)
				indigo.devices[dev.id].updateStateOnServer("swing", kCurtainSwingOpen) # Next action starts opening	
				
			elif percentage == 50: 
				if dev.states["swing"] == "open":
					indigo.devices[dev.id].updateStateOnServer("onOffState", True, uiValue=kCurtainPositionHalfOpen)
					indigo.devices[dev.id].updateStateOnServer("brightnessLevel", percentage, uiValue=kCurtainPositionHalfOpen)
				
					indigo.devices[dev.id].updateStateOnServer("position", kCurtainPositionHalfOpen)	
				else:
					indigo.devices[dev.id].updateStateOnServer("onOffState", True, uiValue=kCurtainPositionHalfClosed)
					indigo.devices[dev.id].updateStateOnServer("brightnessLevel", percentage, uiValue=kCurtainPositionHalfClosed)
					
					indigo.devices[dev.id].updateStateOnServer("position", kCurtainPositionHalfClosed)	
					
			else: 
				if dev.states["swing"] == "open":
					indigo.devices[dev.id].updateStateOnServer("onOffState", True, uiValue=kCurtainPositionPartOpen)
					indigo.devices[dev.id].updateStateOnServer("brightnessLevel", percentage, uiValue=kCurtainPositionPartOpen)
					
					indigo.devices[dev.id].updateStateOnServer("position", kCurtainPositionPartOpen)	
				else:
					indigo.devices[dev.id].updateStateOnServer("onOffState", True, uiValue=kCurtainPositionPartClosed)
					indigo.devices[dev.id].updateStateOnServer("brightnessLevel", percentage, uiValue=kCurtainPositionPartClosed)
					
					indigo.devices[dev.id].updateStateOnServer("position", kCurtainPositionPartClosed)	
				
			self.relayToDimmerUpdateStateIcon (dev.id)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Curtain calibration
	#
	def relayToDimmerCurtainCalibration (self, dev, outlet):
		try:
			self.StopCalibrationTime = indigo.server.getTime()
			d  = dtutil.dateDiff ("seconds", self.StopCalibrationTime, self.StartCalibrationTime)
			indigo.device.turnOff (outlet.id)
			
			calibrationruns = len(self.CalibrationTimes) + 1
			self.CalibrationTimes.append(d)
								
			msg = eps.ui.debugHeader ("CALIBRATION #{} COMPLETE IN {} SECONDS)".format(str(calibrationruns), str(d)))
			self.logger.info (msg)
			
			if calibrationruns == 6:
				total = 0
				for n in self.CalibrationTimes:
					total = total + n
					
				total = total / 6
				total = round(total, 2)
			
				msg = eps.ui.debugHeader ("CALIBRATION COMPLETE")
				msg += eps.ui.debugLine ("Results: ")
				msg += eps.ui.debugLine (" ")
				msg += eps.ui.debugLine ("Average time to cycle between OPEN and CLOSED: {} seconds".format(str(total)))
				msg += eps.ui.debugHeaderEx ()

				self.logger.warning (msg)
				
				indigo.devices[dev].updateStateOnServer("position", kCurtainPositionOpen)
				
				indigo.devices[dev].updateStateOnServer("calibration", total)
				indigo.devices[dev].updateStateOnServer("onOffState", True, uiValue=kCurtainPositionOpen)
				
				sourceProps = dev.pluginProps
				sourceProps["calibrate"] = False
				dev.replacePluginPropsOnServer(sourceProps)
				
				self.CalibrationTimes = [] # Reset for next calibration
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Form field changed
	#
	def relayToDimmerFormFieldChanged (self, valuesDict, typeId, devId):
		try:
			if valuesDict["iconOn"] == "":
				valuesDict["iconOn"] = "WindowSensorOpened"
				
			if valuesDict["iconOff"] == "":
				valuesDict["iconOff"] = "WindowSensorClosed"	
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict
		
	#
	# Change the icon
	#
	def relayToDimmerUpdateStateIcon (self, devId):
		try:
			if int(devId) in indigo.devices:
				dev = indigo.devices[int(devId)]
				
				if dev.onState:
					dev.updateStateImageOnServer(eps.ui.getIndigoIconForKeyword(dev.pluginProps["iconOn"]))
				else:
					dev.updateStateImageOnServer(eps.ui.getIndigoIconForKeyword(dev.pluginProps["iconOff"]))
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	################################################################################
	# FUNCTIONS BELOW THIS LINE NEED TO BE CLEANED UP AND MIGRATED TO THE NAMING
	# SYSTEM ABOVE
	################################################################################	
	
	################################################################################
	# GENERAL
	################################################################################
	
	#
	# Thermostat wrapper clear button
	#
	def btnClearThermostatOption (self, valuesDict, typeId, devId):
		try:
			if "deviceSettings" not in valuesDict:
				valuesDict["deviceSettings"] = json.dumps([])
					
			deviceSettings = json.loads(valuesDict["deviceSettings"])
			
			# Clear all fields	
			valuesDict["option1Type"] = "device"
			valuesDict["option1Device"] = ""
			valuesDict["option1State"] = ""
			valuesDict["option1Action"] = ""
			valuesDict["option1Variable"] = ""
			
			valuesDict["temperatureType"] = "F" # Temperature
			valuesDict["thermostatdevice"] = "" # Thermostat wrap
		
			# Write back all settings but this one
			newDeviceSettings = []
			for old in deviceSettings:
				if old["key"] != valuesDict["optionSelect"]: newDeviceSettings.append (old)
			
			valuesDict["deviceSettings"] = json.dumps(newDeviceSettings)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict
		
	#
	# Clear conversion settings
	#
	def btnClearConversionSettings (self, valuesDict, typeId, devId):
		try:
			# Clear fields	
			if valuesDict["action"] == "dtmin":
				valuesDict["extraaction"] = ""
				valuesDict["threshold"] = "60"
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return valuesDict	
	
	#
	# Derive parent, child and value from a plugin device then update as if a watched state/attribute changed
	#
	def updateFromPluginDevice (self, dev):
		try:
			self.logger.threaddebug ("Running plugin updateFromPluginDevice")
			
			if dev.deviceTypeId == "epsdecon":
				#if dev.pluginProps["chdevice"] and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
				if dev.pluginProps["objectype"] == "device"  and ext.valueValid (dev.pluginProps, "device", True) and ext.valueValid (dev.pluginProps, "states", True):
					if int(dev.pluginProps["device"]) not in indigo.devices:
						self.logger.error ("Device '{0}' is referencing device ID {1} but that device is no longer an Indigo device.  Please change the device reference or remove '{0}' to prevent this error".format(dev.name, dev.pluginProps["device"]))
						return False
				
					child = indigo.devices[int(dev.pluginProps["device"])]
					
					if dev.pluginProps["states"][0:5] != "attr_": 
						self.updateDevice (dev, child, child.states[dev.pluginProps["states"]])
					else:
						attribName = dev.pluginProps["states"].replace ("attr_", "")
						attrib = getattr(child, attribName)
						
						self.updateDevice (dev, child, attrib)
						
				if dev.pluginProps["objectype"] == "variable"  and ext.valueValid (dev.pluginProps, "variable", True):		
					if int(dev.pluginProps["variable"]) in indigo.variables:
						child = indigo.variables[int(dev.pluginProps["variable"])]
						
						self.updateDevice (dev, child, child.value)
						
				if dev.pluginProps["objectype"] == "static":	
					if dev.pluginProps["action"] == "true":
						value = True
					else:
						value = False
							
					self.updateDevice (dev, None, value)
						
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
					
				elif dev.deviceTypeId == "thermostat-wrapper": # Thermostat wrapper
					self.updateDevice (dev, None, None)
					
				elif dev.deviceTypeId == "hue-color-group": # Thermostat wrapper
					self.updateDevice (dev, None, None)
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Update our device based on the criteria provided
	#
	def updateDevice (self, parent, child, value):
		try:
			self.logger.threaddebug ("Running plugin updateDevice")
			
			if parent.deviceTypeId == "epsdecon":
				if parent.pluginProps["action"] == "true" or parent.pluginProps["action"] == "false":
					# These are static and have no device
					if parent.address != "Static Value of " + "True" and parent.address != "Static Value of " + "False":
						props = parent.pluginProps
						props["address"] = "Static Value of "
						if parent.pluginProps["action"] == "true":
							props["address"] += "True"
						else:
							props["address"] += "False"
							
						parent.replacePluginPropsOnServer (props)			
				else:
					self.updateDeviceAddress (parent, child)
			
				return self.getConvertedValue (parent.pluginProps, parent, child, value)
				
				#if parent.pluginProps["action"] == "boolstr": return self._booleanToString (parent, child, value)
				#if parent.pluginProps["action"] == "strtocase": return self._stringToCase (parent, child, value)
				#if parent.pluginProps["action"] == "strtonum": return self._stringToNumber (parent, child, value)
				#if parent.pluginProps["action"] == "dtformat": return self._dateReformat (parent, child, value)
				#if parent.pluginProps["action"] == "string": return self._convertToString (parent, child, value)
				#if parent.pluginProps["action"] == "ctof": return self._celsiusToFahrenheit (parent, child, value)	
				#if parent.pluginProps["action"] == "ftoc": return self._fahrenheitToCelsius (parent, child, value)	
				#if parent.pluginProps["action"] == "lux": return self._luxToString (parent, child, value)
				#if parent.pluginProps["action"] == "booltype": return self._booleanToType (parent, child, value)
				#if parent.pluginProps["action"] == "true": return self._booleanStatic (parent, child, True)
				#if parent.pluginProps["action"] == "false": return self._booleanStatic (parent, child, False)
				#if parent.pluginProps["action"] == "dtmin": return self._datetimeToElapsedMinutes (parent, child, value)
				#if parent.pluginProps["action"] == "bool": return self._stateToBoolean (parent, child, value)
				
			elif parent.deviceTypeId == "epsdews": 
				self.updateDeviceAddress (parent, child)
				return self._updateWeather (parent, child, value)
				
			elif parent.deviceTypeId == "epsdeth": 
				self.updateDeviceAddress (parent, child)
				return self._updateThermostat (parent, child, value)
				
			elif parent.deviceTypeId == "epsdeirr": 
				self.updateDeviceAddress (parent, indigo.devices[int(parent.pluginProps["device"])])
				return self._updateIrrigation (parent, child, value)
				
			elif parent.deviceTypeId == "thermostat-wrapper": 
				self.updateDeviceAddress (parent, None)
				return self._updateThermostatWrapper (parent, child, value)
				
			elif parent.deviceTypeId == "hue-color-group": 
				self.updateDeviceAddress (parent, None)
				return self._updateVirtualColorHueGroup (parent, child, value)	
				
			elif parent.deviceTypeId == "Filter-Sensor":	
				self.updateDeviceAddress (parent, None)
				return self._updateFilterSensor (parent, child, value)	
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	#
	# Set the device address to the child name
	#
	def updateDeviceAddress (self, parent, child):
		try:
			if self.pluginPrefs["conversionAddress"] == "object":
				if parent.address != child.name + " Extension":
					props = parent.pluginProps
					props["address"] = child.name + " Extension"
					parent.replacePluginPropsOnServer (props)
								
			elif self.pluginPrefs["conversionAddress"] == "method":
				address = "Unknown Conversion"
				
				if "action" in parent.pluginProps:
					if parent.pluginProps["action"] == "ftoc": address = "Fahrenheit to Celsius"
					if parent.pluginProps["action"] == "ctof": address = "Celsius to Fahrenheit"
					if parent.pluginProps["action"] == "lux": address = "Lux to Word State"
					if parent.pluginProps["action"] == "bool": address = "State to Boolean"
					if parent.pluginProps["action"] == "dtmin": address = "Date/Time to Elapsed Minutes"
					if parent.pluginProps["action"] == "boolstr": address = "Boolean to String"
					if parent.pluginProps["action"] == "booltype": address = "Boolean Type"
					if parent.pluginProps["action"] == "true": address = "Always True"
					if parent.pluginProps["action"] == "false": address = "Always False"
					if parent.pluginProps["action"] == "string": address = "To String"
					if parent.pluginProps["action"] == "dtformat": address = "Date/Time Format"
					if parent.pluginProps["action"] == "strtonum": address = "String to Number"
					if parent.pluginProps["action"] == "strtocase": address = "String to Cased String"
					
					if parent.address != address:
						props = parent.pluginProps
						props["address"] = address
						parent.replacePluginPropsOnServer (props)
						
			if parent.deviceTypeId == "thermostat-wrapper":			
				props = parent.pluginProps
				
				deviceSettings = json.loads(parent.pluginProps["deviceSettings"])
				thermostatdevice = ""
				
				for d in deviceSettings:
					if d["key"] == "thermostat" and d["thermostatdevice"] != "": 
						thermostatdevice = d["thermostatdevice"]
						break
				
				if thermostatdevice != "":
					props["address"] = indigo.devices[int(thermostatdevice)].name + " Wrap"
				
				else:
					props["address"] = "Custom Functions"
					
				parent.replacePluginPropsOnServer (props)	
				
			if parent.deviceTypeId == "hue-color-group":
				props = parent.pluginProps
				props["address"] = str(len(props["huelights"])) + " Group Members"
				parent.replacePluginPropsOnServer (props)
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
	################################################################################
	# MISC ACTIONS
	################################################################################	
	
	#
	# Conversion action
	#
	def conversionAction (self, devAction):
		try:
			valuesDict = devAction.props
			value = ""
			
			if devAction.props["objectype"] == "device"  and ext.valueValid (devAction.props, "device", True) and ext.valueValid (devAction.props, "states", True):
				if int(devAction.props["device"]) not in indigo.devices:
					self.logger.error ("Device '{0}' is referencing device ID {1} but that device is no longer an Indigo device.  Please change the device reference or remove '{0}' to prevent this error".format("Conversion Action", devAction.props))
					return False
			
				child = indigo.devices[int(devAction.props["device"])]
				
				if devAction.props["states"][0:5] != "attr_": 
					value = self.getConvertedValue (devAction.props, devAction, child, child.states[devAction.props["states"]], True)
					
				else:
					attribName = devAction.props["states"].replace ("attr_", "")
					attrib = getattr(child, attribName)
					
					value = self.getConvertedValue (devAction.props, devAction, child, attrib, True)
					
			if devAction.props["objectype"] == "variable"  and ext.valueValid (devAction.props, "variable", True):		
				if int(devAction.props["variable"]) in indigo.variables:
					child = indigo.variables[int(devAction.props["variable"])]
					
					value = self.getConvertedValue (devAction.props, devAction, child, child.value, True)
					
			if devAction.props["objectype"] == "static":	
					if devAction.props["action"] == "true":
						xvalue = True
					else:
						xvalue = False
							
					value = self.getConvertedValue (devAction.props, devAction, None, xvalue, True)		

			# OUTPUT			
			if devAction.props["outputVariable"]:
				if devAction.props["saveToVariable"] != "" and int(devAction.props["saveToVariable"]) in indigo.variables:
					var = indigo.variables[int(devAction.props["saveToVariable"])]
					var.value = value
					var.replaceOnServer()
				
			if devAction.props["outputConsole"]:
				self.logger.info ("Conversion Action Output: " + value)
			
			if devAction.props["outputSpeech"]:
				self.extendedSpeak (devAction, None, None, value)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
	#
	# Speak to Airfoil speaker
	#
	def extendedSpeak (self, devAction, unknown, unknown2, forceSay=""):
		try:
			say = devAction.props["say"]
			if forceSay != "": say = forceSay # For calling this from another action
			
			if say == "": 
				self.logger.error ("An action was raised to speak but nothing was entered to say")
				return
			
			# Check for up to 10 keywords
			for i in range (0, 10):
				keywords = dict([nvstring.split(":") for nvstring in [line for line in say.split("%%") if ":" in line]])
				
				if "v" in keywords:
					if int(keywords["v"]) in indigo.variables:
						say = say.replace ("%%v:" + keywords["v"] + "%%", unicode(indigo.variables[int(keywords["v"])].value) )
					else:
						self.logger.error ("Unable to find variable {0} to inject into speech action, ignoring".format(keywords["v"]))
						say = say.replace ("%%v:" + keywords["v"] + "%%", "")
					
				# Device state
				if "ds" in keywords:
					devstate = keywords["ds"]
					devstate = devstate.split("|")
					
					if int(devstate[0]) in indigo.devices:
						dev = indigo.devices[int(devstate[0])]
						if devstate[1] in dev.states:
							say = say.replace ("%%ds:" + devstate[0] + "|" + devstate[1] + "%%", unicode(dev.states[devstate[1]]) )
						else:
							self.logger.error ("Unable to find state '{0}' in device '{1}' states to inject into speech action, ignoring".format(devstate[1], dev.name))
							
					else:
						self.logger.error ("Unable to find device {0} to inject into speech action, ignoring".format(devstate[0]))

			# If we aren't being called from another function
			if forceSay == "": self.logger.info ("Extended speech is saying: {0}".format(say))

			if devAction.props["useAirfoil"]:			
				airfoilPlugin = indigo.server.getPlugin("com.perceptiveautomation.indigoplugin.airfoilpro")
			
				SPEAKERID = int(devAction.props["speaker"])

				if airfoilPlugin.isEnabled():
					try:
						result = airfoilPlugin.executeAction("connect", deviceId=SPEAKERID, waitUntilDone=True)
					except Exception as ex:
						self.logger.error ("Extended speech was unable to connect to the Airfoil speaker, the message from Airfoil is: " + unicode(ex))
						return
						
					if devAction.props["delay"] !="": time.sleep(int(devAction.props["delay"]))
				
					indigo.server.speak(say, waitUntilDone=True)

					if devAction.props["disconnect"] !="": time.sleep(int(devAction.props["disconnect"]))
					result = airfoilPlugin.executeAction("disconnect", deviceId= SPEAKERID, waitUntilDone=True)
					
				else: 
					self.logger.error ("Extended speech action wants to use Airfoil but Airfoil Pro isn't enabled, aborting.")
					return
					
			else:
				if devAction.props["delay"] !="": time.sleep(int(devAction.props["delay"]))
				indigo.server.speak(say, waitUntilDone=True)
		
		except Exception as e:
			self.logger.error (ext.getException(e))
			return False	
				
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
			
			self.logger.threaddebug ("Running plugin calculateTimeRemaining")
						
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
			self.logger.threaddebug ("Running plugin calculateUITime")
			
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
			self.logger.threaddebug ("Running plugin _updateIrrigation")
			
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
			self.logger.threaddebug ("Running plugin irrigationChildUpdated")
			
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
			self.logger.threaddebug ("Running plugin irrigationAction")
			
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
			self.logger.threaddebug ("Running plugin resetHighsLows")
			
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
			self.logger.threaddebug ("Running plugin _updateThermostat")
			
			states = []
			
			states = iutil.updateState ("hightemp", calcs.getHighFloatValue (child, "temperatureInput1", parent.states["hightemp"]), states)
			states = iutil.updateState ("lowtemp", calcs.getHighFloatValue (child, "temperatureInput1", parent.states["lowtemp"]), states)

			#indigo.server.log(unicode(child))

			# Nest plugin 2.0.50+ - added in 2.0.3, the "humidityInput1" no longer exists in favor of "humidity"
			if "humidity" in child.states:
				states = iutil.updateState ("highhumidity", calcs.getHighFloatValue (child, "humidity", parent.states["highhumidity"]), states)
				states = iutil.updateState ("lowhumidity", calcs.getHighFloatValue (child, "humidity", parent.states["lowhumidity"]), states)
				
			# Nest plugin prior to 2.0.50 - modified in 2.0.3	
			if "humidityInput1" in child.states:
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
			self.logger.threaddebug ("Running plugin _updateThermostatStates")
			
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
			self.logger.threaddebug ("Running plugin toggleAllThermostatPresets")
			
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
			self.logger.threaddebug ("Running plugin thermostatAction")
			
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
			self.logger.threaddebug ("Running plugin thermostatPresetToggle")
			
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
			self.logger.threaddebug ("Running plugin thermostatPresetOn")
			
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
				
				tinfo = {}
				tinfo["id"] = parent.id
				tinfo["name"] = parent.name
				tinfo["preset"] = n
				tinfo["expiration"] = d.strftime("%Y-%m-%d %H:%M:%S")				
				self.thermostatPreset.append(tinfo)
				
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
	# THERMOSTAT WRAPPER
	################################################################################	
	
	#
	# Thermostat control master action (only called by actionControlThermostat custom actions)
	#
	def runCustomThermostatAction (self, action, dev, d, msg):
		try:
			# Device
			if d["option1Type"] == "device" and d["option1Device"] != "" and d["option1State"] != "":
				if int(d["option1Device"]) in indigo.devices:
					X = 1
					
					return True
					
			if d["option1Type"] == "action" and d["option1Action"] != "":
				if int(d["option1Action"]) in indigo.actionGroups:
					indigo.actionGroup.execute(int(d["option1Action"]))
				
					return True
					
				else:
					self.logger.error ("Thermostat Wrapper '{0}' is configured to use action group {1} to {3} but that action group doesn't exist in Indigo".format(dev.name, str(d["option1Action"]), msg))
					
					return False
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False
	
	#
	# Thermostat control action (thermostat wrapper)
	#
	def actionControlThermostat(self, action, dev):
		try:
			#indigo.server.log(unicode(action))
			
			deviceSettings = json.loads(dev.pluginProps["deviceSettings"])
			thermostatDev = False
			
			# Check if we have a default device
			for d in deviceSettings:
				if d["key"] == "thermostat" and d["thermostatdevice"] != "":
					if int(d["thermostatdevice"]) in indigo.devices:
						thermostatDev = indigo.devices[int(d["thermostatdevice"])]
						
			# Increase heat setpoint by actionValue
			if action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
				for d in deviceSettings:
					if d["key"] == "increaseheat":
						return self.runCustomThermostatAction (action, dev, d, "increase heat set point")
								
				if thermostatDev:
					return indigo.thermostat.increaseHeatSetpoint(thermostatDev.id, delta=action.actionValue)
					
			# Decrease heat setpoint by actionValue
			if action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
				for d in deviceSettings:
					# Device
					if d["key"] == "decreaseheat":
						return self.runCustomThermostatAction (action, dev, d, "decrease heat set point")
								
				if thermostatDev:
					return indigo.thermostat.decreaseHeatSetpoint(thermostatDev.id, delta=action.actionValue)		
					
			# Increase cool setpoint by actionValue
			if action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
				for d in deviceSettings:
					if d["key"] == "increasecool":
						return self.runCustomThermostatAction (action, dev, d, "increase cool set point")
								
				if thermostatDev:
					return indigo.thermostat.increaseCoolSetpoint(thermostatDev.id, delta=action.actionValue)	
					
			# Decrease cool setpoint by actionValue
			if action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
				for d in deviceSettings:
					if d["key"] == "decreasecool":
						return self.runCustomThermostatAction (action, dev, d, "decrease cool set point")
								
				if thermostatDev:
					return indigo.thermostat.decreaseCoolSetpoint(thermostatDev.id, delta=action.actionValue)				
					
					
			# Set HVAC mode
			if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
				for d in deviceSettings:
					if action.actionMode == 0 and d["key"] == "hvacmodeoff":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to off")
						
					if action.actionMode == 1 and d["key"] == "hvacmodeheat":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to heat")
						
					if action.actionMode == 2 and d["key"] == "hvacmodecool":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to cool")
						
					if action.actionMode == 3 and d["key"] == "hvacmodeauto":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to auto heat/cool")	
						
					if action.actionMode == 4 and d["key"] == "hvacmodeprogramauto":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to program auto heat/cool")	
					
					if action.actionMode == 5 and d["key"] == "hvacmodeprogramcool":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to program cool")
					
					if action.actionMode == 6 and d["key"] == "hvacmodeprogramheat":
						return self.runCustomThermostatAction (action, dev, d, "turn HVAC mode to program heat")
						
				if thermostatDev:
					if action.actionMode == 0: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.Off)	
					if action.actionMode == 1: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.Heat)	
					if action.actionMode == 2: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.Cool)	
					if action.actionMode == 3: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.HeatCool)	
					if action.actionMode == 4: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.ProgramHeatCool)	
					if action.actionMode == 5: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.ProgramCool)	
					if action.actionMode == 6: return indigo.thermostat.setHvacMode(thermostatDev.id, value=indigo.kHvacMode.ProgramHeat)	
					
			# Set fan mode
			if action.thermostatAction == indigo.kThermostatAction.SetFanMode:
				for d in deviceSettings:
					if action.actionMode == 0 and d["key"] == "hvacfanmodeauto":
						return self.runCustomThermostatAction (action, dev, d, "turn fan mode to auto")
						
					if action.actionMode == 1 and d["key"] == "hvacfanmodealways":
						return self.runCustomThermostatAction (action, dev, d, "turn fan mode to always on")
								
				if thermostatDev:
					if action.actionMode == 0: return indigo.thermostat.setFanMode(thermostatDev.id, value=indigo.kFanMode.Auto)	
					if action.actionMode == 1: return indigo.thermostat.setFanMode(thermostatDev.id, value=indigo.kFanMode.AlwaysOn)
			
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return False	
		
	
	#
	# Update a thermostat wrapper
	#
	def _updateThermostatWrapper (self, parent, child, value):
		try:
			self.logger.threaddebug ("Running plugin _updateThermostatWrapper")
			
			# We don't actually use child in this routine but have it there for continuity
			if "deviceSettings" not in parent.pluginProps: return
			deviceSettings = json.loads(parent.pluginProps["deviceSettings"])
			
			states = []
			
			# If we are wrapping a thermostat then start with all values from that and we'll change to another device below
			for d in deviceSettings:
				if d["key"] == "thermostat" and d["thermostatdevice"] != "":
					if int(d["thermostatdevice"]) in indigo.devices:
						thermostatDev = indigo.devices[int(d["thermostatdevice"])]
						
						statelist = ["hvacFanMode", "hvacOperationMode", "setpointCool", "setpointHeat", "temperatureInput1", "temperatureInputsAll", "humidityInput1", "humidityInputsAll"]

						for s in statelist:
							if s in thermostatDev.states and s in parent.states:		
								states = iutil.updateState (s, thermostatDev.states[s], states)
								
					break
			
			for d in deviceSettings:
				if d["key"] == "temp":
					devOption1 = indigo.devices[int(d["option1Device"])]
			
					stateSuffix = u" °" + d["temperatureType"]
					stateString = str(devOption1.states[d["option1State"]]) + stateSuffix
						
					states = iutil.updateState ("temperatureInput1", devOption1.states[d["option1State"]], states, stateString)
					states = iutil.updateState ("temperatureInputsAll", devOption1.states[d["option1State"]], states, stateString)
					states = iutil.updateState ("statedisplay", str(devOption1.states[d["option1State"]]) + stateSuffix , states)
					
				elif d["key"] == "humidity":
					devOption1 = indigo.devices[int(d["option1Device"])]
			
					stateString = str(devOption1.states[d["option1State"]])
						
					states = iutil.updateState ("humidityInput1", devOption1.states[d["option1State"]], states, stateString)
					states = iutil.updateState ("humidityInputsAll", devOption1.states[d["option1State"]], states, stateString)
					
				elif d["key"] == "heatsetpoint":
					devOption1 = indigo.devices[int(d["option1Device"])]
			
					stateString = str(devOption1.states[d["option1State"]])
						
					states = iutil.updateState ("setpointHeat", devOption1.states[d["option1State"]], states, stateString)
					
				elif d["key"] == "coolsetpoint":
					devOption1 = indigo.devices[int(d["option1Device"])]
			
					stateString = str(devOption1.states[d["option1State"]])
						
					states = iutil.updateState ("setpointCool", devOption1.states[d["option1State"]], states, stateString)	
			
			
			parent.updateStateImageOnServer(eps.ui.getIndigoIconForKeyword(parent.pluginProps["icon"]))
			
			parent.updateStatesOnServer (states)
			
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")		
			
	################################################################################
	# VIRTUAL COLOR HUE GROUP
	################################################################################	
	
	#
	# Options for Hue group to synchronize
	#
	def listHueSyncTo (self, args, valuesDict):
		try:
			ret = [("default", "No data")]
						
			retList = [("none", "Keep individual settings")]
			
			retList = eps.ui.addLine (retList)
			
			for d in valuesDict["huelights"]:
				dev = indigo.devices[int(d)]
				retList.append ((d, dev.name))
				
			return retList
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			
		return ret
			
	
	#
	# Dimmer controls
	#
	def xxxonAfter_actionControlDimmerRelay(self, action, dev):
		try:
			command = action.deviceAction
			
			if command == indigo.kDeviceAction.TurnOn:
				for d in dev.pluginProps["huelights"]:
					if int(d) in indigo.devices:
						hue = indigo.devices[int(d)]
						indigo.dimmer.turnOn (int(d))
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
			
	#
	# Update a thermostat wrapper
	#
	def _updateVirtualColorHueGroup (self, parent, child, value):
		try:
			states = []
			bulbs = []
			allOn = True
			anyOn = False
			master = 0
			
			if parent.pluginProps["keepsync"] != "none" and parent.pluginProps["keepsync"] != "": master = int(parent.pluginProps["keepsync"])
			
			for d in parent.pluginProps["huelights"]:
				if int(d) in indigo.devices:
					bulb = indigo.devices[int(d)]
					if not bulb.states["onOffState"]: allOn = False
					if bulb.states["onOffState"]: anyOn = True
					bulbs.append(bulb)
					
			for b in bulbs:
				# If there is a master bulb then we ignore all others, otherwise we just take whatever
				if master != 0 and b.id != master:
					continue
					
				for state in b.states:
					if state in parent.states:
						states = iutil.updateState (state, b.states[state], states)
						
			parent.updateStatesOnServer (states)
			
			# If we are synchronizing then do that now
			if master !=0:
				bulb = indigo.devices[master]
				
				for b in bulbs:
					if b.id != bulb.id:
						if b.onState != bulb.onState:
							if bulb.onState:
								indigo.dimmer.turnOn (b.id)
							else:
								indigo.dimmer.turnOff (b.id)
								
						if b.brightness != bulb.brightness:
							indigo.dimmer.setBrightness (b.id, value=bulb.brightness)	
							
						if b.whiteLevel != bulb.whiteLevel:
							indigo.dimmer.setColorLevels (b.id, whiteLevel=bulb.whiteLevel)
						
						if b.whiteLevel2 != bulb.whiteLevel2:
							indigo.dimmer.setColorLevels (b.id, whiteLevel2=bulb.whiteLevel2)
						
						if b.whiteTemperature != bulb.whiteTemperature:
							indigo.dimmer.setColorLevels (b.id, whiteTemperature=bulb.whiteTemperature)
						
						if b.redLevel != bulb.redLevel or b.greenLevel != bulb.greenLevel or b.blueLevel != bulb.blueLevel:
							indigo.dimmer.setColorLevels (b.id, redLevel=bulb.redLevel, greenLevel=bulb.greenLevel, blueLevel=bulb.blueLevel)
						
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")	
	
			
	################################################################################
	# WEATHER EXTENSION
	################################################################################			
	

	
	#
	# Update a weather device
	#
	def _updateWeather (self, parent, child, value):
		try:
			self.logger.threaddebug ("Running plugin _updateWeather")
			
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
			self.logger.threaddebug ("Running plugin _updateWeatherStates")
			
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
	# Get converted value
	#
	def getConvertedValue (self, props, parent, child, value, isAction=False):
		try:
			if props["action"] == "boolstr": return self._booleanToString (parent, child, value, isAction)
			if props["action"] == "strtocase": return self._stringToCase (parent, child, value, isAction)
			if props["action"] == "strtonum": return self._stringToNumber (parent, child, value, isAction)
			if props["action"] == "dtformat": return self._dateReformat (parent, child, value, isAction)
			if props["action"] == "string": return self._convertToString (parent, child, value, isAction)
			if props["action"] == "ctof": return self._celsiusToFahrenheit (parent, child, value, isAction)	
			if props["action"] == "ftoc": return self._fahrenheitToCelsius (parent, child, value, isAction)	
			if props["action"] == "lux": return self._luxToString (parent, child, value, isAction)
			if props["action"] == "booltype": return self._booleanToType (parent, child, value, isAction)
			if props["action"] == "true": return self._booleanStatic (parent, child, True, isAction)
			if props["action"] == "false": return self._booleanStatic (parent, child, False, isAction)
			if props["action"] == "dtmin": return self._datetimeToElapsedMinutes (parent, child, value, isAction)
			if props["action"] == "bool": return self._stateToBoolean (parent, child, value, isAction)
				
		except Exception as e:
			self.logger.error (ext.getException(e))	
	
	#
	# Convert celsius to fahrenheit
	#
	def _celsiusToFahrenheit (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
			else:
				props = parent.props # the devAction.props
				
			if "precision" in props:
				value = calcs.temperature (value, False, int(props["precision"]))
			else:
				value = calcs.temperature (value, False)
						
			if not isAction:									
				stateSuffix = u" °F" 
			
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
				states = []
				states = iutil.updateState ("statedisplay", value, states, str(value) + stateSuffix, 1)
				states = iutil.updateState ("convertedValue", unicode(value), states)
				states = iutil.updateState ("convertedNumber", value, states)
		
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
			
	#
	# Convert fahrenheit to celsius
	#
	def _fahrenheitToCelsius (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
			else:
				props = parent.props # the devAction.props
		
			if "precision" in props:
				value = calcs.temperature (value, True, int(props["precision"]))
			else:
				value = calcs.temperature (value, True)
			
			if not isAction:			
				stateSuffix = u" °C" 
			
				parent.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
				states = []
				states = iutil.updateState ("statedisplay", value, states, str(value) + stateSuffix, 1)
				states = iutil.updateState ("convertedValue", unicode(value), states)
				states = iutil.updateState ("convertedNumber", value, states)
		
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")		
			
		return value # Mostly for actions
			
						
	#
	# Convert date from one format to another
	#
	def _dateReformat (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			if ext.valueValid (props, "inputdtformat", True) and ext.valueValid (props, "outputdtformat", True):
				value = unicode(value)
				value = dtutil.dateStringFormat (value, props["inputdtformat"], props["outputdtformat"])
		
				if not isAction:
					parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
					states = []
					states = iutil.updateState ("statedisplay", value, states, value)
					states = iutil.updateState ("convertedValue", unicode(value), states)
			
					parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")	
			
		return value # Mostly for actions
			
						
	#
	# Convert date to elapsed minutes since date
	#
	def _datetimeToElapsedMinutes (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value)
			if value == "": return
		
			try:
				value = datetime.datetime.strptime (value, props["dateformat"])
			except:
				self.logger.error (u"Error converting %s to a date/time with a format of %s, make sure the date format is correct and that the value is really a date/time string or datetime value!" % (value, props["dateformat"]))
				if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")	
				return
				
			m = dtutil.dateDiff ("minutes", indigo.server.getTime(), value)
			m = int(m) # for state	
			
			value = m
			
			if not isAction:
				parent.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
	
				states = []
				states = iutil.updateState ("statedisplay", unicode(m).lower() + " Min", states)
				states = iutil.updateState ("convertedValue", unicode(m).lower(), states)
				states = iutil.updateState ("convertedNumber", m, states)
	
				parent.updateStatesOnServer(states)
			
				# If we enabled running an action on a threshold then check that now
				if parent.pluginProps["extraaction"] != "":
					if int(parent.pluginProps["extraaction"]) in indigo.actionGroups:
						if parent.pluginProps["threshold"] != "":
							if m > int(parent.pluginProps["threshold"]):
								self.logger.info ("Threshold exceeded for '{0}', running action group".format(parent.name))
								indigo.actionGroup.execute(int(parent.pluginProps["extraaction"]))
						else:
							self.logger.error ("Unable to run the action group for '{0}' because the threshold is 0 or blank".format(parent.name))
										
					else:
						self.logger.error ("Unable to run the action group for '{0}' because Indigo doesn't have an action group for ID {1}".format(parent.name, parent.pluginProps["extraaction"]))

		except Exception as e:
			self.logger.error (ext.getException(e))	
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")		
					
		return value # Mostly for actions
								
					
	#
	# Convert to a string and trim
	#
	def _convertToString (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value)
			
			if ext.valueValid (props, "maxlength", True):
				if props["maxlength"] != "0" and len(value) > int(props["maxlength"]):
					#self.debugLog("Shortening string to %i characters" % int(props["maxlength"]))
					diff = len(value) - int(props["maxlength"])
					diff = diff * -1
					value = value[:diff]
			
			if ext.valueValid (props, "trimstart", True):
				if props["trimstart"] != "0" and len(value) > int(props["trimstart"]):
					#self.debugLog("Removing %i characters from beginning of string" % int(props["trimstart"]))
					diff = int(props["trimstart"])
					value = value[diff:len(value)]		
					
			if ext.valueValid (props, "trimend", True):
				if props["trimend"] != "0" and len(value) > int(props["trimend"]):
					#self.debugLog("Removing %i characters from end of string" % int(props["trimend"]))
					diff = int(props["trimend"])
					diff = diff * -1
					value = value[:diff]		
			
			if not isAction:
				parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
				states = []
				states = iutil.updateState ("statedisplay", value, states, value)
				states = iutil.updateState ("convertedValue", unicode(value), states)
			
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
						
	#
	# Boolean to string
	#
	def _booleanToString (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value).lower()
			
			truevalue = unicode(props["truewhen"])
			falsevalue = unicode(props["falsewhen"])

			statevalue = falsevalue
			if value == "true": statevalue = truevalue

			value = statevalue
			
			if not isAction:	
				parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
				states = []
				states = iutil.updateState ("statedisplay", unicode(statevalue), states)
				states = iutil.updateState ("convertedValue", unicode(statevalue), states)
			
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
						
	#
	# Lux value to string
	#
	def _luxToString (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			if value is None:
				self.logger.warn ("'{0}' cannot convert the lux value for '{1}' because the value is None".format(parent.name, child.name))
				if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
				return
			
			value = float(value)
			factor = 1 # 1 = 100001 or 100% of normal lux values
			
			if "luxfactor" in props:
				if props["luxfactor"] != "0" and props["luxfactor"] != "":
					self.logger.threaddebug ("'{0}' has a lux factor of '{1}', adjusting values".format(name, props["luxfactor"]))
					factor = float(props["luxfactor"])
			
			term = "Direct Sunlight"
			
			if value < (100001 * factor): term = "Direct Sunlight"
			if value < (30001 * factor): term = "Cloudy Outdoors"
			if value < (10001 * factor): term = "Dim Outdoors"
			if value < (5001 * factor): term = "Bright Indoors"
			if value < (1001 * factor): term = "Normal Indoors"
			if value < (401 * factor): term = "Dim Indoors"
			if value < (201 * factor): term = "Dark Indoors"
			if value < (51 * factor): term = "Very Dark"
			if value < (11 * factor): term = "Pitch Black"
			
			value = term
			
			if not isAction:			
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
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
						
	#
	# String to case
	#
	def _stringToCase (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value)
			
			if props["strcase"] == "title": value = value.title()
			if props["strcase"] == "initial": value = value.capitalize()
			if props["strcase"] == "upper": value = value.upper()
			if props["strcase"] == "lower": value = value.lower()
			
			if not isAction:			
				parent.updateStateImageOnServer(indigo.kStateImageSel.None)
			
				states = []
				states = iutil.updateState ("statedisplay", value, states, value)
				states = iutil.updateState ("convertedValue", unicode(value), states)
			
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
						
	#
	# String to number
	#
	def _stringToNumber (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value)
			states = []
			
			if ext.valueValid (pprops, "trimstart", True):
				if props["trimstart"] != "0" and len(value) > int(props["trimstart"]):
					#self.logger.debug ("Removing %i characters from beginning of string" % int(parent.pluginProps["trimstart"]))
					diff = int(props["trimstart"])
					value = value[diff:len(value)]		
					
			if ext.valueValid (props, "trimend", True):
				if props["trimend"] != "0" and len(value) > int(props["trimend"]):
					#self.logger.debug ("Removing %i characters from end of string" % int(parent.pluginProps["trimend"]))
					diff = int(props["trimend"])
					diff = diff * -1
					value = value[:diff]		
					
			try:
				dec = string.find (value, '.')
				numtype = props["numtype"]
				
				if dec > -1 and numtype == "int":
					indigo.server.error ("Input value of %s on %s contains a decimal, forcing value to be a float.  Change the preferences for this device to get rid of this error." % (value, name))
					numtype = "float"
				
				if numtype == "int": 
					value = int(value)
					
					if not isAction:
						states = iutil.updateState ("statedisplay", value, states, unicode(value))
						states = iutil.updateState ("convertedValue", unicode(value), states)
						states = iutil.updateState ("convertedNumber", value, states)
					
				if numtype == "float": 
					value = float(value)

					if not isAction:					
						states = iutil.updateState ("statedisplay", value, states, unicode(value), 2)
						states = iutil.updateState ("convertedValue", unicode(value), states)
						states = iutil.updateState ("convertedNumber", value, states)
					
			except Exception as e:
				self.logger.error (ext.getException(e))	
				if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")

			if not isAction:			
				parent.updateStateImageOnServer(indigo.kStateImageSel.None)
				parent.updateStatesOnServer(states)
		
		except Exception as e:
			self.logger.error (ext.getException(e))	
			parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")						
			
		return value # Mostly for actions
			
				
	#
	# Static boolean state
	#
	def _booleanStatic (self, parent, child, value, isAction=False):
		try:
			if not isAction:
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
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
						
	#
	# State to boolean
	#
	def _stateToBoolean (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value).lower()
			
			truevalue = unicode(props["truewhen"]).lower()
			falsevalue = unicode(props["falsewhen"]).lower()
			
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
			
			value = statevalue
			
			if not isAction:				
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
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
				
	#
	# Boolean to boolean type
	#
	def _booleanToType (self, parent, child, value, isAction=False):
		try:
			if not isAction:
				props = parent.pluginProps
				name = parent.name
			else:
				props = parent.props # the devAction.props
				name = "Conversion Action"
				
			value = unicode(value).lower()
			
			statevalue = "na"
			statebool = False
			
			truevalue = "na"
			falsevalue = "na"
			
			if props["booltype"] == "tf":
					truevalue = "true"
					falsevalue = "false"
					
			elif props["booltype"] == "yesno":
					truevalue = "yes"
					falsevalue = "no"
					
			elif props["booltype"] == "onoff":
					truevalue = "on"
					falsevalue = "off"
					
			elif props["booltype"] == "oz":
					truevalue = "1"
					falsevalue = "0"
					
			elif props["booltype"] == "oc":
					truevalue = "open"
					falsevalue = "closed"
					
			elif props["booltype"] == "rdy":
					truevalue = "ready"
					falsevalue = "not ready"
					
			elif props["booltype"] == "avail":
					truevalue = "available"
					falsevalue = "not available"
					
			elif props["booltype"] == "gbad":
					truevalue = "good"
					falsevalue = "bad"	
					
			elif props["booltype"] == "lock":
					truevalue = "locked"
					falsevalue = "unlocked"		
					
			if value == "true":
				statebool = True
				if props["reverse"]: statebool = False
			else:
				statebool = False
				if props["reverse"]: statebool = True
			
			if statebool: 
				statevalue = truevalue
			else:
				statevalue = falsevalue
				
			value = statevalue
			
			if not isAction:
				
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
			if not isAction: parent.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
			
		return value # Mostly for actions
			
				
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
	
	
	################################################################################
	# ADVANCED PLUGIN ACTIONS (v3.3.0)
	################################################################################

	# Plugin menu advanced plugin actions 
	def advPluginDeviceSelected (self, valuesDict, typeId): return eps.plug.advPluginDeviceSelected (valuesDict, typeId)
	def btnAdvDeviceAction (self, valuesDict, typeId): return eps.plug.btnAdvDeviceAction (valuesDict, typeId)
	def btnAdvPluginAction (self, valuesDict, typeId): return eps.plug.btnAdvPluginAction (valuesDict, typeId)
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	