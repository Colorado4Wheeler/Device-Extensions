# -*- coding: utf-8 -*-
#
# Weathersnoop: Methods and actions for Weathersnoop
#
#########################################################################

import indigo
import os
import sys
import time
import datetime
from DevUtils import DevUtils

class Weathersnoop:

	#
	# Initialize the class
	#
	def __init__ (self, DevUtilsLib):
		self.cache = DevUtilsLib
	
	#
	# Update weather device
	#
	def updateWeather (self, devEx):
		dev = indigo.devices[int(devEx.pluginProps["device"])]
		
		#tempVar = "temperature_" + devEx.pluginProps["measurement"]
		tempVar = devEx.pluginProps["temperature"]
		humVar = devEx.pluginProps["humidity"]
		rainVar = devEx.pluginProps["rain"]
		
		devEx.updateStateOnServer("hightemp", self.cache.getHighFloatValue (dev, tempVar, devEx.states["hightemp"]))
		devEx.updateStateOnServer("lowtemp", self.cache.getLowFloatValue (dev, tempVar, devEx.states["lowtemp"]))
		devEx.updateStateOnServer("highhumidity", self.cache.getHighFloatValue (dev, humVar, devEx.states["highhumidity"]))
		devEx.updateStateOnServer("lowhumidity", self.cache.getLowFloatValue (dev, humVar, devEx.states["lowhumidity"]))
		
		if devEx.pluginProps["rainstatetype"] == "string":
			if dev.states[rainVar] == devEx.pluginProps["rainvalue"]:
				devEx.updateStateOnServer ("raining", True)
			else:
				devEx.updateStateOnServer ("raining", False)
		elif devEx.pluginProps["rainstatetype"] == "boolean":
			if dev.states[rainVar]:
				devEx.updateStateOnServer ("raining", True)
			else:
				devEx.updateStateOnServer ("raining", False)
				
		# See if we hit the record high or record low temps on a WUnderground plugin (1.3.0)
		if dev.pluginId == "com.fogbert.indigoplugin.wunderground":
			if float(devEx.states["hightemp"]) > float(dev.states["historyHigh"]): devEx.updateStateOnServer ("isrecordhigh", True)
			if float(devEx.states["lowtemp"]) < float(dev.states["historyLow"]): devEx.updateStateOnServer ("isrecordlow", True)
			
		self.updateStateDisplay (dev, devEx)
	
	#
	# Return default values to a configuration dialog
	#
	def getDefaultValues (self, valuesDict, device = "device"):
		if valuesDict[device] != "":
			dev = indigo.devices[int(valuesDict[device])]
		
			# Give them some defaults for known devices
			#indigo.server.log(unicode(dev))
		
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
				
		return valuesDict
	
	#	
	# Update device states
	#
	def updateStateDisplay (self, dev, devEx):
		stateSuffix = u"°F" 
		decimals = 1
		stateFloat = float(0)
		stateString = "NA"
		
		if "measurement" in devEx.pluginProps:
			if devEx.pluginProps["measurement"] == "C": stateSuffix = u"°C" 
			
		if devEx.pluginProps["statedisplay"] == "currenthumidity": 
			stateSuffix = ""

			
			if dev.pluginId == "com.fogbert.indigoplugin.wunderground":
				stateFloat = float(dev.states["relativeHumidity"])
				stateString = str(dev.states["relativeHumidity"])
			else:
				stateFloat = float(dev.states["humidity"])
				stateString = str(dev.states["humidity"])
				
			devEx.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
			
		elif devEx.pluginProps["statedisplay"] == "highhumidity": 
			stateSuffix = ""
			
			stateFloat = float(devEx.states["highhumidity"])
			stateString = str(devEx.states["highhumidity"])
			devEx.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
		elif devEx.pluginProps["statedisplay"] == "lowhumidity": 
			stateSuffix = ""
			
			stateFloat = float(devEx.states["lowhumidity"])
			stateString = str(devEx.states["lowhumidity"])
			devEx.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
		
		elif devEx.pluginProps["statedisplay"] == "hightemp": 
			stateFloat = float(devEx.states["hightemp"])
			stateString = str(devEx.states["hightemp"]) + " " + stateSuffix
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
		
		elif devEx.pluginProps["statedisplay"] == "lowtemp": 
			stateFloat = float(devEx.states["lowtemp"])
			stateString = str(devEx.states["lowtemp"]) + " " + stateSuffix
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
		elif devEx.pluginProps["statedisplay"] == "currenttemp": 
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			tempVar = devEx.pluginProps["temperature"]
			stateFloat = float(dev.states[tempVar])
			stateString = str(dev.states[tempVar]) + " " + stateSuffix			
			
		if decimals > -1:
			devEx.updateStateOnServer(key="statedisplay", value=stateFloat, decimalPlaces=decimals, uiValue=stateString)
		else:
			devEx.updateStateOnServer("statedisplay", stateString)