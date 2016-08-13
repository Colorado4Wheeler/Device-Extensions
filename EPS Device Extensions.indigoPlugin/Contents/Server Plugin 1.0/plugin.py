#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo

import os
import sys
import time
import datetime
import urllib2 # for URL device
import string # 1.5.2

from eps import dtutil # 1.5.2

from eps.DevUtils import DevUtils
from eps.SmartThermostat import SmartThermostat
from eps.Weathersnoop import Weathersnoop
from eps.SmartIrrigation import SmartIrrigation

from eps import eps # 1.52
from eps import conv # 1.52
import re # 1.52
from datetime import timedelta # 1.52
from bs4 import BeautifulSoup # 1.52
from eps import dtutil # 1.52
import base64 # 1.52


################################################################################
class Plugin(indigo.PluginBase):
	
	#
	# Init
	#
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = False
		
		self.pluginUrl = "http://forums.indigodomo.com/viewtopic.php?f=197&t=16233&p=117513#p117513" # 1.52
		#pluginId = "com.eps.indigoplugin.device-extensions" # removed 1.52
		self.cache = DevUtils (pluginId)
		self.thermostat = SmartThermostat (self.cache)
		self.weather = Weathersnoop (self.cache)
		self.sprinkler = SmartIrrigation (self.cache)
		self.cache.cacheSubDevices ("device")
		eps.parent = self # 1.52
		conv.parent = self # 1.52
		
	#
	# Delete
	#
	def __del__(self):
		indigo.PluginBase.__del__(self)
		
	#
	# Support log dump
	#
	def supportLogDump (self):
		self.cache.supportLogDump()
		
	#
	# Device pre-save event
	#
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		return (True, valuesDict)
	
	#
	# Device menu selection changed
	#
	def deviceMenuChanged(self, valuesDict, typeId, devId):
		# Just here so we can refresh the states
		
		if typeId == "epsdews":
			valuesDict = self.weather.getDefaultValues (valuesDict)
				
		return valuesDict
	
	#
	# Return menu of device states for irrigation controller rain states
	#
	def getStatesForDeviceIr(self, filter="", valuesDict=None, typeId="", targetId=0):
		return self.cache.getDeviceStatesArray (filter, valuesDict, typeId, targetId, "raindevice")
		
	#
	# Return menu of device states
	#
	def getStatesForDevice(self, filter="", valuesDict=None, typeId="", targetId=0):
		states = self.cache.getDeviceStatesArray (filter, valuesDict, typeId, targetId, "device")
		
		option = ("lastChanged", "lastChanged (property)")
		states.append(option)
		
		return states
	
	#
	# Device properties changed
	#
	def didDeviceCommPropertyChange(self, origDev, newDev):
		return True	
		
	#
	# One of our monitored devices has changed
	# 
	def deviceUpdated(self, origDev, newDev):
		if self.cache.deviceInCache (newDev.id):
			self.debugLog ("Our plugin device %s changed" % newDev.name)
			
			if "device" in newDev.pluginProps and "device" in origDev.pluginProps:
				if newDev.pluginProps["device"] != origDev.pluginProps["device"]:
					# The device changed, force a re-cache of devices and subs - this will mean both are in cache but that's ok until we upgrade this to the new engine
					self.debugLog("Re-caching sub devices")
					self.cache.addSubDevice(newDev.pluginProps["device"])	
						
			self.updateDevice (newDev.id, "", "")
			
		else:
			if newDev.pluginId == self.pluginId:
				self.debugLog (u"Our plugin device %s changed and isn't in cache" % newDev.name)
				
				# It's one of our devices but isn't in our cache, could be new, fix that now
				if newDev.pluginProps:
					self.debugLog(u"Adding device not currently in cache: " + newDev.name)
					self.deviceValidate (newDev)
					self.cache.addDevice (newDev)
				
					
		
		if self.cache.subDeviceInCache (newDev.id):
			devs = self.cache.devicesForSubDevice (newDev.id, "device")
			
			for devId, tfVar in devs.iteritems():
				#self.debugLog("deviceUpdate for " + str(newDev.id))
				self.updateDevice (devId, origDev, newDev)
			
	#
	# Action to update from device
	#
	def updateFromDevice (self, devAction):	
		#indigo.server.log(unicode(devAction))
		self.updateDevice (devAction.deviceId, "", "")
	
	#
	# Device actions
	#
	def deviceActions (self, devAction):	
		# Run thermostat actions
		self.thermostat.deviceActions (devAction)
		self.sprinkler.deviceActions (devAction)
		
		# Generic actions
		if devAction.pluginTypeId == "resethighlow":
			devEx = indigo.devices[devAction.deviceId]
			self.resetHighLowForDevice (devEx)
			
		if devAction.pluginTypeId == "forceoff":
			devEx = indigo.devices[devAction.deviceId]
			devEx.updateStateOnServer("onOffState", False)
			
	#
	# Update device
	#
	def updateDevice (self, devId, origDev, newDev):
		dev = indigo.devices[int(devId)]
		
		try:
			typeId = self.cache.deviceTypeId (devId)
		except:
			# If we get here then they may have copied the device and the typeId isn't assigned yet
			return
			
		if typeId == "epsdecon": self.convertDeviceAction (dev)	
		if typeId == "epsdews": self.weather.updateWeather (dev)	
		if typeId == "epsdeth": self.thermostat.updateThermostat (dev)
		if typeId == "epsdeirr": 
			#self.debugLog("Sprinkler updated")
			self.sprinkler.updateIrrigation (dev, origDev, newDev)
	
	
			
		
	#
	# Convert device temperature value
	#
	def convertDeviceAction (self, devEx):
		if devEx.pluginProps["chdevice"]:
			dev = indigo.devices[int(devEx.pluginProps["device"])]
			
			# Added condition to check if it's in states, it will be if it's a state because we already verified this in the config (1.5.0)
			if devEx.pluginProps["states"] in dev.states:
				value = dev.states[devEx.pluginProps["states"]]
			else:
				# It's a special device property added in 1.5.0
				if devEx.pluginProps["states"] == "lastChanged": value = dev.lastChanged
			
		else:
			dev = ""
			value = indigo.variables[int(devEx.pluginProps["variable"])]
			
		if devEx.pluginProps["action"] == "strtocase": # 1.52
			value = unicode(value)
			
			if devEx.pluginProps["strcase"] == "title": value = value.title()
			if devEx.pluginProps["strcase"] == "initial": value = value.capitalize()
			if devEx.pluginProps["strcase"] == "upper": value = value.upper()
			if devEx.pluginProps["strcase"] == "lower": value = value.lower()
			
			
			devEx.updateStateOnServer("convertedValue", str(value))
			devEx.updateStateOnServer(key="statedisplay", value=value, uiValue=value)
		
		if devEx.pluginProps["action"] == "strtonum": # 1.52 # CONVERTED
			value = unicode(value)
			
			if eps.valueValid (devEx.pluginProps, "trimstart", True):
				if devEx.pluginProps["trimstart"] != "0" and len(value) > int(devEx.pluginProps["trimstart"]):
					self.debugLog("Removing %i characters from beginning of string" % int(devEx.pluginProps["trimstart"]))
					diff = int(devEx.pluginProps["trimstart"])
					value = value[diff:len(value)]		
					
			if eps.valueValid (devEx.pluginProps, "trimend", True):
				if devEx.pluginProps["trimend"] != "0" and len(value) > int(devEx.pluginProps["trimend"]):
					self.debugLog("Removing %i characters from end of string" % int(devEx.pluginProps["trimend"]))
					diff = int(devEx.pluginProps["trimend"])
					diff = diff * -1
					value = value[:diff]		
					
			try:
				dec = string.find (value, '.')
				numtype = devEx.pluginProps["numtype"]
				
				if dec > -1 and numtype == "int":
					indigo.server.log("Input value of %s on %s contains a decimal, forcing value to be a float.  Change the preferences for this device to get rid of this error." % (value, devEx.name), isError=True)
					numtype = "float"
				
				if numtype == "int": 
					value = int(value)
					devEx.updateStateOnServer("statedisplay", value, uiValue=unicode(value))
					devEx.updateStateOnServer("convertedValue", unicode(value))
					devEx.updateStateOnServer("convertedNumber", value)
				
				if numtype == "float": 
					value = float(value)
					
					devEx.updateStateOnServer("statedisplay", value, uiValue=unicode(value))
					devEx.updateStateOnServer("convertedValue", unicode(value))
					devEx.updateStateOnServer("convertedNumber", value)
				
			except Exception as e:
				eps.printException(e)
				devEx.updateStateOnServer(key="statedisplay", value="Error", uiValue="Error")
				return
			
		
		if devEx.pluginProps["action"] == "dtformat": # 1.52
			if eps.valueValid (devEx.pluginProps, "inputdtformat", True) and eps.valueValid (devEx.pluginProps, "outputdtformat", True):
				value = unicode(value)
				value = dtutil.DateStringFormat (value, devEx.pluginProps["inputdtformat"], devEx.pluginProps["outputdtformat"])
		
				devEx.updateStateOnServer("convertedValue", str(value))
				devEx.updateStateOnServer(key="statedisplay", value=value, uiValue=value)
				
		if devEx.pluginProps["action"] == "string": # 1.52
			value = unicode(value)
			
			if eps.valueValid (devEx.pluginProps, "maxlength", True):
				if devEx.pluginProps["maxlength"] != "0" and len(value) > int(devEx.pluginProps["maxlength"]):
					self.debugLog("Shortening string to %i characters" % int(devEx.pluginProps["maxlength"]))
					diff = len(value) - int(devEx.pluginProps["maxlength"])
					diff = diff * -1
					value = value[:diff]
			
			if eps.valueValid (devEx.pluginProps, "trimstart", True):
				if devEx.pluginProps["trimstart"] != "0" and len(value) > int(devEx.pluginProps["trimstart"]):
					self.debugLog("Removing %i characters from beginning of string" % int(devEx.pluginProps["trimstart"]))
					diff = int(devEx.pluginProps["trimstart"])
					value = value[diff:len(value)]		
					
			if eps.valueValid (devEx.pluginProps, "trimend", True):
				if devEx.pluginProps["trimend"] != "0" and len(value) > int(devEx.pluginProps["trimend"]):
					self.debugLog("Removing %i characters from end of string" % int(devEx.pluginProps["trimend"]))
					diff = int(devEx.pluginProps["trimend"])
					diff = diff * -1
					value = value[:diff]		
			
			devEx.updateStateOnServer("convertedValue", str(value))
			devEx.updateStateOnServer(key="statedisplay", value=value, uiValue=value)
		
		if devEx.pluginProps["action"] == "ctof":
			# 1.2 added precision
			if "precision" in devEx.pluginProps:
				#value = self.cache.convertTemperature (value, False, int(devEx.pluginProps["precision"]))
				value = conv.temperature (value, False, int(devEx.pluginProps["precision"])) # 1.52
			else:
				#value = self.cache.convertTemperature (value, False)
				value = conv.temperature (value, False) # 1.52
			
			
			stateSuffix = u" °F" 
			
			devEx.updateStateOnServer("convertedValue", str(value))
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			devEx.updateStateOnServer(key="statedisplay", value=value, decimalPlaces=1, uiValue=str(value) + stateSuffix)
			
		if devEx.pluginProps["action"] == "ftoc":
			# 1.2 added precision
			if "precision" in devEx.pluginProps:
				#value = self.cache.convertTemperature (value, True, int(devEx.pluginProps["precision"]))
				value = conv.temperature (value, True, int(devEx.pluginProps["precision"])) # 1.52
			else:
				#value = self.cache.convertTemperature (value, True)
				value = conv.temperature (value, True) # 1.52
			
			stateSuffix = u" °C" 
			
			devEx.updateStateOnServer("convertedValue", str(value))
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			devEx.updateStateOnServer(key="statedisplay", value=value, decimalPlaces=1, uiValue=str(value) + stateSuffix)
			
		if devEx.pluginProps["action"] == "lux":
			value = int(value)
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
				devEx.updateStateImageOnServer(indigo.kStateImageSel.LightSensor)
			else:
				devEx.updateStateImageOnServer(indigo.kStateImageSel.LightSensorOn)
			
			devEx.updateStateOnServer("convertedValue", term)
			devEx.updateStateOnServer("statedisplay", term)
			
		if devEx.pluginProps["action"] == "boolstr": # CONVERTED
			value = unicode(value).lower()
			
			truevalue = unicode(devEx.pluginProps["truewhen"])
			falsevalue = unicode(devEx.pluginProps["falsewhen"])
			
			statevalue = falsevalue
			if value == "true": statevalue = truevalue
			
			devEx.updateStateImageOnServer(indigo.kStateImageSel.None)
			devEx.updateStateOnServer("statedisplay", unicode(statevalue))
			devEx.updateStateOnServer("convertedValue", unicode(statevalue))
		
		if devEx.pluginProps["action"] == "booltype":
			value = unicode(value).lower()
			
			statevalue = "na"
			statebool = False
			
			truevalue = "na"
			falsevalue = "na"
			
			if devEx.pluginProps["booltype"] == "tf":
					truevalue = "true"
					falsevalue = "false"
					
			elif devEx.pluginProps["booltype"] == "yesno":
					truevalue = "yes"
					falsevalue = "no"
					
			elif devEx.pluginProps["booltype"] == "onoff":
					truevalue = "on"
					falsevalue = "off"
					
			elif devEx.pluginProps["booltype"] == "oz":
					truevalue = "1"
					falsevalue = "0"
					
			elif devEx.pluginProps["booltype"] == "oc":
					truevalue = "open"
					falsevalue = "closed"
					
			elif devEx.pluginProps["booltype"] == "rdy":
					truevalue = "ready"
					falsevalue = "not ready"
					
			elif devEx.pluginProps["booltype"] == "avail":
					truevalue = "available"
					falsevalue = "not available"
					
			elif devEx.pluginProps["booltype"] == "gbad":
					truevalue = "good"
					falsevalue = "bad"	
					
			elif devEx.pluginProps["booltype"] == "lock":
					truevalue = "locked"
					falsevalue = "unlocked"		
					
			if value == "true":
				statebool = True
				if devEx.pluginProps["reverse"]: statebool = False
			else:
				statebool = False
				if devEx.pluginProps["reverse"]: statebool = True
			
			if statebool: 
				statevalue = truevalue
			else:
				statevalue = falsevalue
				
			devEx.updateStateImageOnServer(indigo.kStateImageSel.None)
			devEx.updateStateOnServer("statedisplay", unicode(statevalue).lower())
			devEx.updateStateOnServer("convertedValue", unicode(statevalue).lower())
			devEx.updateStateOnServer("convertedBoolean", statebool)
			if devEx.pluginProps["booltype"] == "oz": devEx.updateStateOnServer("convertedNumber", int(statevalue))
			
		if devEx.pluginProps["action"] == "true": # CONVERTED
			devEx.updateStateImageOnServer(indigo.kStateImageSel.None)
			devEx.updateStateOnServer("statedisplay", "true")
			devEx.updateStateOnServer("convertedValue", "true")
			devEx.updateStateOnServer("convertedBoolean", True)
			
		if devEx.pluginProps["action"] == "false": # CONVERTED
			devEx.updateStateImageOnServer(indigo.kStateImageSel.None)
			devEx.updateStateOnServer("statedisplay", "false")
			devEx.updateStateOnServer("convertedValue", "false")
			devEx.updateStateOnServer("convertedBoolean", False)
					
		if devEx.pluginProps["action"] == "bool": # CONVERTED
			value = unicode(value).lower()
			#if devEx.pluginProps["booleanstatetype"] == "float": value = float(value)
			
			truevalue = unicode(devEx.pluginProps["truewhen"]).lower()
			falsevalue = unicode(devEx.pluginProps["falsewhen"]).lower()
			
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
				
			devEx.updateStateImageOnServer(indigo.kStateImageSel.None)
			devEx.updateStateOnServer("statedisplay", unicode(statevalue).lower())
			devEx.updateStateOnServer("convertedValue", unicode(statevalue).lower())
			devEx.updateStateOnServer("convertedBoolean", statevalue)
			
		if devEx.pluginProps["action"] == "dtmin":
			self.calcMinutes (devEx, value)
			
	#
	# Force update any devices that need to be checked periodically (called from concurrent threading)
	#
	def forceUpdate (self):
		# Get any lastUpdate conversions, we need to check this every minute
		devs = indigo.devices.iter("com.eps.indigoplugin.device-extensions.epsdecon")
		for devEx in devs:
			if devEx.pluginProps["action"] == "dtmin":
				dev = indigo.devices[int(devEx.pluginProps["device"])]
				d = devEx.lastChanged
				m = dtutil.DateDiff ("minutes", indigo.server.getTime(), d)

				if m > 1: 
					if devEx.pluginProps["states"] == "lastChanged":					
						self.calcMinutes(devEx, dev.lastChanged)
					else:
						self.calcMinutes(devEx, dev.states[devEx.pluginProps["states"]])
					
	#
	# Calculate minutes since a date for dtmin conversion and update the device
	#
	def calcMinutes (self, devEx, value):
		value = unicode(value)
		if value == "": return
		
		try:
			value = datetime.datetime.strptime (value, devEx.pluginProps["dateformat"])
		except:
			self.debugLog(u"Error converting %s to a date/time with a format of %s, make sure the date format is correct and that the value is really a date/time string or datetime value!" % (value, devEx.pluginProps["dateformat"]), isError=True)
			return
			
		m = dtutil.DateDiff ("minutes", indigo.server.getTime(), value)
		m = int(m) # for state
		
		devEx.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
		devEx.updateStateOnServer("statedisplay", unicode(m).lower() + " Min")
		devEx.updateStateOnServer("convertedValue", unicode(m).lower())
		devEx.updateStateOnServer("convertedNumber", m)
				
	#
	# Reset daily high/low values
	#
	def resetHighLow (self):
		devs = self.cache.devices
		
		for devId, pluginId in self.cache.devices.iteritems():
			dev = indigo.devices[int(devId)]
			if "lasthighlowreset" in dev.states:
				s = dtutil.DateDiff ("hours", indigo.server.getTime(), str(dev.states["lasthighlowreset"]) + " 00:00:00")
				if s > 24:
					# Reset the high lows
					self.resetHighLowForDevice (dev)
	
	#
	# Reset or force reset daily high/lows
	def resetHighLowForDevice (self, dev):
		d = indigo.server.getTime()
		
		if "hightemp" in dev.states: dev.updateStateOnServer ("hightemp", "")
		if "lowtemp" in dev.states: dev.updateStateOnServer ("lowtemp", "")
		if "highhumidity" in dev.states: dev.updateStateOnServer ("highhumidity", "")
		if "lowhumidity" in dev.states: dev.updateStateOnServer ("lowhumidity", "")
		
		# Added for 1.3.0 for Weather Extension
		if "isrecordhigh" in dev.states: dev.updateStateOnServer ("isrecordhigh", False)
		if "isrecordlow" in dev.states: dev.updateStateOnServer ("isrecordlow", False)
		
		indigo.server.log("High/Low Values Reset")
		
		dev.updateStateOnServer ("lasthighlowreset", d.strftime("%Y-%m-%d "))
	
	#
	# Device communications startup
	#
	def deviceStartComm(self, dev):
		self.debugLog(u"Starting device " + dev.name)
		dev.stateListOrDisplayStateIdChanged() # Force plugin to refresh states from devices.xml
		self.deviceValidate (dev)
		
	#
	# Device was deleted
	#
	def deviceDeleted(self, dev):
		self.debugLog(u"Deleting device " + dev.name)
		self.cache.cacheDevices ()
		self.cache.cacheSubDevices ("device")
		
	#
	# Device started or updated, force defaults and update
	#
	def deviceValidate (self, dev):
		# Make sure we aren't missing critical states
		if "statedisplay" in dev.states:
			if dev.states["statedisplay"] == "": dev.updateStateOnServer ("statedisplay", "N/A")
			
		if "setMode" in dev.states:
			if "setmode" in dev.pluginProps:
				if dev.pluginProps["setmode"] == "heat": dev.updateStateOnServer ("setMode", False)
				if dev.pluginProps["setmode"] == "cool": dev.updateStateOnServer ("setMode", True)
			
		
		if "lasthighlowreset" in dev.states:
			if dev.states["lasthighlowreset"] == "":
				d = indigo.server.getTime()
				dev.updateStateOnServer ("lasthighlowreset", d.strftime("%Y-%m-%d "))
				
		self.updateDevice (str(dev.id), "", "")
	
	#
	# Plugin startup
	#
	def startup(self):
		self.debugLog(u"Starting Device Extensions")
		indigo.devices.subscribeToChanges()
		
	
	#	
	# Plugin shutdown
	#
	def shutdown(self):
		self.debugLog(u"Device Extensions Shut Down")


	#
	# Threading
	#
	def runConcurrentThread(self):
		try:
			while True:
					self.resetHighLow()
					self.thermostat.timerTick() # Lazy mans 1 second timer
					self.sprinkler.irrigationTimerTick() # A smarter timer
					self.forceUpdate() # To check if conversions need refreshed
					self.updateCheck(True, False)
					self.sleep(1)
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.
			
			
	################################################################################
	# UPDATE CHECKS - 1.52
	################################################################################

	def updateCheck (self, onlyNewer = False, force = True):
		try:
			try:
				if self.pluginUrl == "": 
					if force: indigo.server.log ("This plugin currently does not check for newer versions", isError = True)
					return
			except:
				# Normal if pluginUrl hasn't been defined
				if force: indigo.server.log ("This plugin currently does not check for newer versions", isError = True)
				return
			
			d = indigo.server.getTime()
			
			if eps.valueValid (self.pluginPrefs, "latestVersion") == False: self.pluginPrefs["latestVersion"] = False
			
			if force == False and eps.valueValid (self.pluginPrefs, "lastUpdateCheck", True):
				last = datetime.datetime.strptime (self.pluginPrefs["lastUpdateCheck"], "%Y-%m-%d %H:%M:%S")
				lastCheck = dtutil.DateDiff ("hours", d, last)
								
				if self.pluginPrefs["latestVersion"]:
					if lastCheck < 72: return # if last check has us at the latest then only check once a day
				else:
					if lastCheck < 2: return # only check every four hours in case they don't see it in the log
			
			
			page = urllib2.urlopen(self.pluginUrl)
			soup = BeautifulSoup(page)
		
			versions = soup.find(string=re.compile("\#Version\|"))
			versionData = unicode(versions)
		
			versionInfo = versionData.split("#Version|")
			newVersion = float(versionInfo[1][:-1])
		
			if newVersion > float(self.pluginVersion):
				self.pluginPrefs["latestVersion"] = False
				indigo.server.log ("Version %s of %s is available, you are currently using %s." % (str(round(newVersion,2)), self.pluginDisplayName, str(round(float(self.pluginVersion), 2))), isError=True)
			
			else:
				self.pluginPrefs["latestVersion"] = True
				if onlyNewer == False: indigo.server.log("%s version %s is the most current version of the plugin" % (self.pluginDisplayName, str(round(float(self.pluginVersion), 2))))
				
			self.pluginPrefs["lastUpdateCheck"] = d.strftime("%Y-%m-%d %H:%M:%S")
			
				
		except Exception as e:
			eps.printException(e)

	
	################################################################################
	# INDIGO DEVICE EVENTS
	################################################################################
	
	#
	# URL device action - 1.52
	#
	def urlDeviceAction (self, dev, url):
		if dev.pluginProps["url"] != "" or dev.pluginProps["username"] != "" or dev.pluginProps["password"] != "":
			ret = urllib2.Request(url)
			if dev.pluginProps["url"] != "": ret = urllib2.Request(dev.pluginProps["url"])
			
			if dev.pluginProps["username"] != "" or dev.pluginProps["password"] != "":
				b64 = base64.encodestring('%s:%s' % (dev.pluginProps["username"], dev.pluginProps["password"])).replace('\n', '')
				ret.add_header("Authorization", "Basic %s" % b64)  
				
			ret = urllib2.urlopen(ret, url)
			
		else:
			ret = urllib2.urlopen(url)
	
		if int(ret.getcode()) != 200: return False
		
		return True
	
	#
	# Dimmer/relay actions
	#
	def actionControlDimmerRelay(self, action, dev):
		if action.deviceAction == indigo.kDimmerRelayAction.TurnOn:
			sendSuccess = True
			
			if dev.pluginProps["onCommand"] != "":
				if self.urlDeviceAction (dev, dev.pluginProps["onCommand"]) == False: sendSuccess = False
			else:
				sendSuccess = False
				
			if sendSuccess:
				indigo.server.log(u"sent \"%s\" %s" % (dev.name, "on"))
				dev.updateStateOnServer("onOffState", True)
			else:
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "on"), isError=True)

		elif action.deviceAction == indigo.kDimmerRelayAction.TurnOff:
			sendSuccess = True
			
			if dev.pluginProps["offCommand"] != "":
				if self.urlDeviceAction (dev, dev.pluginProps["offCommand"]) == False: sendSuccess = False
			else:
				sendSuccess = False

			if sendSuccess:
				indigo.server.log(u"sent \"%s\" %s" % (dev.name, "off"))
				dev.updateStateOnServer("onOffState", False)
			else:
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "off"), isError=True)

		elif action.deviceAction == indigo.kDimmerRelayAction.Toggle:
			newOnState = not dev.onState
			sendSuccess = True
			
			if dev.pluginProps["toggleCommand"] == "":
				if newOnState:
					indigo.device.turnOn(dev.id)
				else:
					indigo.device.turnOff(dev.id)
			else:
				if self.urlDeviceAction (dev, dev.pluginProps["toggleCommand"]) == False: sendSuccess = False
				

			if sendSuccess:
				indigo.server.log(u"sent \"%s\" %s" % (dev.name, "toggle"))
				dev.updateStateOnServer("onOffState", newOnState)
			else:
				indigo.server.log(u"send \"%s\" %s failed" % (dev.name, "toggle"), isError=True)

		elif action.deviceAction == indigo.kDimmerRelayAction.SetBrightness:
			newBrightness = action.actionValue
			sendSuccess = True

			if sendSuccess:
				indigo.server.log(u"sent \"%s\" %s to %d" % (dev.name, "set brightness", newBrightness))
				dev.updateStateOnServer("brightnessLevel", newBrightness)
			else:
				indigo.server.log(u"send \"%s\" %s to %d failed" % (dev.name, "set brightness", newBrightness), isError=True)

		elif action.deviceAction == indigo.kDimmerRelayAction.BrightenBy:
			newBrightness = dev.brightness + action.actionValue
			if newBrightness > 100:
				newBrightness = 100
			sendSuccess = True

			if sendSuccess:
				indigo.server.log(u"sent \"%s\" %s to %d" % (dev.name, "brighten", newBrightness))
				dev.updateStateOnServer("brightnessLevel", newBrightness)
			else:
				indigo.server.log(u"send \"%s\" %s to %d failed" % (dev.name, "brighten", newBrightness), isError=True)

		elif action.deviceAction == indigo.kDimmerRelayAction.DimBy:
			newBrightness = dev.brightness - action.actionValue
			if newBrightness < 0:
				newBrightness = 0
			sendSuccess = True

			if sendSuccess:
				indigo.server.log(u"sent \"%s\" %s to %d" % (dev.name, "dim", newBrightness))
				dev.updateStateOnServer("brightnessLevel", newBrightness)
			else:
				indigo.server.log(u"send \"%s\" %s to %d failed" % (dev.name, "dim", newBrightness), isError=True)