# -*- coding: utf-8 -*-
#
# Smart Thermostat: Methods and actions for Smart Thermostat
#
#########################################################################

import indigo
import os
import sys
import time
import datetime
from DevUtils import DevUtils

class SmartThermostat:

	#
	# Initialize the class
	#
	def __init__ (self, DevUtilsLib):
		self.cache = DevUtilsLib
		self.timerseconds = {}
		
	#
	# Tick the timer (from concurrent thread)
	#
	def timerTick (self):
		newseconds = {}
		
		for devId, seconds in self.timerseconds.iteritems():	
			if seconds > 0:
				newsecs = seconds - 1
				newseconds[devId] = newsecs
				
		for devId, seconds in newseconds.iteritems():
			devEx = indigo.devices[int(devId)]
			
			if seconds == 0:
				# A minute has passed, reduce the device timer by 1
				curmins = int(devEx.states["presetTimeout"])
				
				if curmins < 1: continue # If its zero it's already been handled or is disabled
				
				curmins = curmins - 1
				
				if curmins <= 0:
					# The timer has run out, toggle off the preset
					self.toggleAllPresets (devEx)
				else:
					self.timerseconds[devEx.id] = 60 # Set timer for another minute
					devEx.updateStateOnServer ("presetTimeout", int(curmins))
			else:
				# Update the counter
				self.timerseconds[devEx.id] = seconds # write the new timer value
	
	#
	# Toggle all presets that are currently on
	#
	def toggleAllPresets (self, devEx):
		if devEx.states["presetOn1"]: self.thermostatPresetToggle (devEx, 1)
		if devEx.states["presetOn2"]: self.thermostatPresetToggle (devEx, 2)
		if devEx.states["presetOn3"]: self.thermostatPresetToggle (devEx, 3)
		if devEx.states["presetOn4"]: self.thermostatPresetToggle (devEx, 4)
				
	#
	# Device actions
	#
	def deviceActions (self, devAction):	
		devEx = indigo.devices[devAction.deviceId]
		dev = indigo.devices[int(devEx.pluginProps["device"])]
		
		if devAction.pluginTypeId == "th-preset1toggle": self.thermostatPresetToggle (devEx, 1)
		if devAction.pluginTypeId == "th-preset2toggle": self.thermostatPresetToggle (devEx, 2)
		if devAction.pluginTypeId == "th-preset3toggle": self.thermostatPresetToggle (devEx, 3)
		if devAction.pluginTypeId == "th-preset4toggle": self.thermostatPresetToggle (devEx, 4)
			
		if devAction.pluginTypeId == "th-setmodeup":
			if dev.states["hvacOperationModeIsOff"] == False:
				# Only change set point if the system is on
				if devEx.states["setMode"]:
					# Cooling mode
					indigo.thermostat.increaseCoolSetpoint(dev.id, delta=1)
				else:
					# Heating mode
					indigo.thermostat.increaseHeatSetpoint(dev.id, delta=1)
					
		if devAction.pluginTypeId == "th-setmodedown":
			if dev.states["hvacOperationModeIsOff"] == False:
				# Only change set point if the system is on
				if devEx.states["setMode"]:
					# Cooling mode
					indigo.thermostat.decreaseCoolSetpoint(dev.id, delta=1)
				else:
					# Heating mode
					indigo.thermostat.decreaseHeatSetpoint(dev.id, delta=1)
			
		if devAction.pluginTypeId == "th-setmodetoggle":
			if devEx.states["setMode"]:
				# It's true (cool), set it to false (heat)
				devEx.updateStateOnServer ("setMode", False)
				devEx.updateStateOnServer ("setModeSetPoint", dev.states["setpointHeat"])
			else:
				# It's false (heat), set it to true (cool)
				devEx.updateStateOnServer ("setMode", True)
				devEx.updateStateOnServer ("setModeSetPoint", dev.states["setpointCool"])
				
			
		if devAction.pluginTypeId == "th-fantoggle":
			varName = "hvacFanIsAuto"
			
			if devEx.pluginProps["nest"]: varName = "hvacFanModeIsAuto"
			
			if dev.states[varName]:
				indigo.thermostat.setFanMode(dev.id, value=indigo.kFanMode.AlwaysOn)
			else:
				indigo.thermostat.setFanMode(dev.id, value=indigo.kFanMode.Auto)
		
		if devAction.pluginTypeId == "th-systemtoggle":
			if devEx.pluginProps["toggleparam"] == "auto":
				if dev.states["hvacOperationModeIsOff"]:
					indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.HeatCool)
				else:
					indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Off)
			elif devEx.pluginProps["toggleparam"] == "heat":
				if dev.states["hvacOperationModeIsOff"]:
					indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Heat)
				else:
					indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Off)
			elif devEx.pluginProps["toggleparam"] == "cool":
				if dev.states["hvacOperationModeIsOff"]:
					indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Cool)
				else:
					indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Off)

	#
	# Update thermostat device
	#
	def updateThermostat (self, devEx):
		dev = indigo.devices[int(devEx.pluginProps["device"])]
		
		devEx.updateStateOnServer("hightemp", self.cache.getHighFloatValue (dev, "temperatureInput1", devEx.states["hightemp"]))
		devEx.updateStateOnServer("lowtemp", self.cache.getLowFloatValue (dev, "temperatureInput1", devEx.states["lowtemp"]))
		
		if "humidity" in dev.states:
			devEx.updateStateOnServer("highhumidity", self.cache.getHighFloatValue (dev, "humidityInput1", devEx.states["highhumidity"]))
			devEx.updateStateOnServer("lowhumidity", self.cache.getLowFloatValue (dev, "humidityInput1", devEx.states["lowhumidity"]))
			
		if dev.states["hvacFanModeIsAuto"]:
			devEx.updateStateOnServer ("fanOn", False)
		else:
			devEx.updateStateOnServer ("fanOn", True)
			
		if dev.states["hvacOperationModeIsOff"]:
			devEx.updateStateOnServer ("systemOn", False)
		else:
			devEx.updateStateOnServer ("systemOn", True)
			
		if devEx.states["setMode"]:
			# It's true (cool), get the current cool setpoint
			devEx.updateStateOnServer ("setModeSetPoint", dev.states["setpointCool"])
		else:
			# It's false (heat), get the current heat setpoint
			devEx.updateStateOnServer ("setModeSetPoint", dev.states["setpointHeat"])
		
		self.updateStateDisplay (dev, devEx)

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
			
			if "humidity" in dev.states:
				stateFloat = float(dev.states["humidity"])
				stateString = str(dev.states["humidity"])
				devEx.updateStateImageOnServer(indigo.kStateImageSel.HumiditySensor)
			else:
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
			
			stateFloat = float(dev.states["temperatureInput1"])
			stateString = str(dev.states["temperatureInput1"]) + " " + stateSuffix
				
		elif devEx.pluginProps["statedisplay"] == "preset": 
			if devEx.deviceTypeId == "epsdeth":
				decimals = -1
				
				stateString = "No Preset"
				if devEx.states["presetOn1"]: stateString = "Preset 1"
				if devEx.states["presetOn2"]: stateString = "Preset 2"
				if devEx.states["presetOn3"]: stateString = "Preset 3"
				if devEx.states["presetOn4"]: stateString = "Preset 4"
				
				if stateString == "No Preset":
					devEx.updateStateImageOnServer(indigo.kStateImageSel.TimerOff)
				else:
					devEx.updateStateImageOnServer(indigo.kStateImageSel.TimerOn)
					
		elif devEx.pluginProps["statedisplay"] == "setpoint": 
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			
			if devEx.states["setMode"]:
				stateFloat = float(dev.states["setpointCool"])
				stateString = str(dev.states["setpointCool"]) + " " + stateSuffix	
			else:
				stateFloat = float(dev.states["setpointHeat"])
				stateString = str(dev.states["setpointHeat"]) + " " + stateSuffix
				
		elif devEx.pluginProps["statedisplay"] == "setcool": 
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			stateFloat = float(dev.states["setpointCool"])
			stateString = str(dev.states["setpointCool"]) + " " + stateSuffix
			
		elif devEx.pluginProps["statedisplay"] == "setheat": 
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			stateFloat = float(dev.states["setpointHeat"])
			stateString = str(dev.states["setpointHeat"]) + " " + stateSuffix
			
		elif devEx.pluginProps["statedisplay"] == "setmode": 
			decimals = -1
			
			devEx.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)
			if devEx.states["setMode"]:
				stateString = "Heat"
			else:
				stateString = "Cool"	
			
			
		if decimals > -1:
			devEx.updateStateOnServer(key="statedisplay", value=stateFloat, decimalPlaces=decimals, uiValue=stateString)
		else:
			devEx.updateStateOnServer("statedisplay", stateString)

	#
	# Thermostat preset toggle
	#
	def thermostatPresetToggle (self, devEx, n):
		# If this preset is on then toggle it off
		if devEx.states["presetOn" + str(n)] == False:
			self.thermostatPresetOn (devEx, n)
			
		else:
			# Restore memory and toggle off
			dev = indigo.devices[int(devEx.pluginProps["device"])]
			
			if devEx.states["presetMemMode"] == 0:
				indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Off)
			elif devEx.states["presetMemMode"] == 1:
				indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Heat)
			elif devEx.states["presetMemMode"] == 2:
				indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Cool)
			elif devEx.states["presetMemMode"] == 3:
				indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.HeatCool)
			
			if devEx.states["presetMemMode"]:
				# Only restore temps if the previous mode was on, some thermostats store off state setpoints as 0
				heatset = devEx.states["presetMemHeat"]
				
				if devEx.pluginProps["failsafe"] != "0":
					if heatset > int(devEx.pluginProps["failsafe"]): heatset = int(devEx.pluginProps["failsafe"])
				
				indigo.thermostat.setCoolSetpoint(dev.id, value=devEx.states["presetMemCool"])
				indigo.thermostat.setHeatSetpoint(dev.id, value=heatset)
			
			if devEx.states["presetMemFanAuto"]:
				indigo.thermostat.setFanMode(dev.id, value=indigo.kFanMode.Auto)
			else:
				indigo.thermostat.setFanMode(dev.id, value=indigo.kFanMode.AlwaysOn)
			
			devEx.updateStateOnServer("presetTimeout", 0)
			devEx.updateStateOnServer("presetOn" + str(n), False)
			
			self.timerseconds[devEx.id] = -1 # Kill the timer
			
	#
	# Thermostat preset on
	#
	def thermostatPresetOn (self, devEx, n):
		dev = indigo.devices[int(devEx.pluginProps["device"])]
		prefix = "preset" + str(n)
		
		# Make sure this is the only active preset, there can be only one [true ring]
		self.toggleAllPresets (devEx)
		
		# Save current states to memory
		devEx.updateStateOnServer("presetMemHeat", dev.states["setpointHeat"])
		devEx.updateStateOnServer("presetMemCool", dev.states["setpointCool"])
		devEx.updateStateOnServer("presetMemFanAuto", dev.states["hvacFanModeIsAuto"])
		devEx.updateStateOnServer("presetMemMode", dev.states["hvacOperationMode"])
		
		# Set temps
		if devEx.pluginProps[prefix + "setcool"] != "0": indigo.thermostat.setCoolSetpoint(dev.id, value=int(devEx.pluginProps[prefix + "setcool"]))
		if devEx.pluginProps[prefix + "setheat"] != "0": indigo.thermostat.setHeatSetpoint(dev.id, value=int(devEx.pluginProps[prefix + "setheat"]))
		
		# Set system mode
		if devEx.pluginProps[prefix + "system"] == "off": indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Off)
		if devEx.pluginProps[prefix + "system"] == "heat": indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Heat)
		if devEx.pluginProps[prefix + "system"] == "cool": indigo.thermostat.setHvacMode(dev.id, value=indigo.kHvacMode.Cool)
		
		# Set fan mode
		if devEx.pluginProps[prefix + "fan"] == "auto": indigo.thermostat.setFanMode(dev.id, value=indigo.kFanMode.Auto)
		if devEx.pluginProps[prefix + "fan"] == "always": indigo.thermostat.setFanMode(dev.id, value=indigo.kFanMode.AlwaysOn)
		
		# Execute smart set if either setpoints was set to zero
		if devEx.pluginProps["smartset"] != "0": 
			if devEx.pluginProps[prefix + "setcool"] == "0" or devEx.pluginProps[prefix + "setheat"] == "0":
				# Auto set the zero setting
				smartset = int(devEx.pluginProps["smartset"])
				
				if devEx.pluginProps[prefix + "setcool"] == "0":
					# Set cool to be X degrees above heating
					temp = int(devEx.pluginProps[prefix + "setheat"])
					indigo.thermostat.setCoolSetpoint(dev.id, value=temp + smartset)
					
				else:
					# Set heat to be X degrees below cooling
					temp = int(devEx.pluginProps[prefix + "setcool"])
					indigo.thermostat.setHeatSetpoint(dev.id, value=smartset - temp)
					
		# Set preset countdown timer
		devEx.updateStateOnServer("presetTimeout", int(devEx.pluginProps["timeout"]))
		
		# If we have a timer then set the countdown
		if devEx.pluginProps["timeout"] != "0":
			self.timerseconds[devEx.id] = 60 # Start the timer for one minute
		else:
			self.timerseconds[devEx.id] = -1 # Kill the timer
			
		# Turn on preset
		devEx.updateStateOnServer("presetOn" + str(n), True)