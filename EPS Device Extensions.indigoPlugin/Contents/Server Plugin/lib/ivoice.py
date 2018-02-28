# Indigo Voice Plugin API
# Copyright (c) 2018 ColoradoFourWheeler / EPS
# Version 1.0.0
#
# Include this library in your plugin using the following syntax at the top of your Indigo plugin:
#
#	If saving ivoice.py to a subfolder under Server Plugin called "lib" (for example):
# 		from lib.ivoice import IndigoVoice
# 		hbb = HomebridgeBuddy()
#
#		If you include it from a subfolder please ensure that the folder has a file named __init__.py as well. This file can be blank but MUST be present.
#
#	If saving ivoice.py to the same folder as plugin.py:
#		
#		from ivoice import IndigoVoice
#		ivoice = IndigoVoice()
#
# Place the following definition in your Actions.xml so the voice apps can notify your plugin of actions or changes:
#
#	<Action id="voiceAPI" uiPath="hidden">
#		<Name>API</Name>
#		<CallbackMethod>voiceAPICall</CallbackMethod>
#	</Action>	
#
# Place the following state on any devices you want to have implement extended Indigo Voice API properties (optional):
#
#	<State id="voiceAPIData">
#		<ValueType>String</ValueType>
#		<TriggerLabel>Indigo Voice API Data</TriggerLabel>
#		<ControlPageLabel>Indigo Voice API Data</ControlPageLabel>
#	</State>
#
# Place the following function definitions into your plugin.py file to utilize this library:
#
#	def voiceIntegrationFieldChange (self, valuesDict, typeId, devId): return ivoice.integrationFieldChange (valuesDict, typeId, devId)
#	def voiceHKBIntegrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.HKBIntegrationServerList (filter, valuesDict, typeId, targetId)
#	def voiceAHBIntegrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.AHBIntegrationServerList (filter, valuesDict, typeId, targetId)
#	def voiceIntegrationHKBDeviceTypeList (self, filter="", valuesDict=None, typeId="", targetId=0): return ivoice.IntegrationHKBDeviceTypeList (filter, valuesDict, typeId, targetId)
#	
#	def voiceAPICall (self, action):
#		try:		
#			success = True
#			errors = indigo.Dict()
#			data = indigo.Dict() # Default, can be changed as needed
#			payload = {}
#			
#			props = action.props
#			
#			libversion = props["libversion"]
#			libver = libversion.split(".")
#			
#			errors["param"] = "command"
#			errors["message"] = "{0} Voice API received the '{1}' command, but that command is not implemented.  Unable to complete API response.".format(self.pluginDisplayName, props["command"])
#			return (False, data, payload, errors)
#			
#		except Exception as e:
#			self.logger.error (unicode(e))
#			
#		return (success, data, payload, errors)


import indigo, logging, linecache, sys, json

# Enumerations
kIndigoVoiceAPIVersion = u'1.0.0'

kHomeKitPlugin = u'com.eps.indigoplugin.homekit-bridge'
kAlexaPlugin = u'com.indigodomo.opensource.alexa-hue-bridge'

kVoiceAPIActionName = u'voiceAPI'

class IndigoVoice:
	
	#
	# Initialize the class
	#
	def __init__ (self):
		self.logger = logging.getLogger ("Plugin.ivoice")
		
		self.logger.debug ("Starting Indigo Voice plugin API version {0}".format(self.version))
		
	#
	# Report back our version number (in case the calling plugin wants to include that in their support dump)
	#
	def version (self):
		return kIndigoVoiceAPIVersion
		
	#
	# Check that props/valuesDict has the required fields
	#
	def checkFields (self, valuesDict):
		try:
			errorDict = indigo.Dict()
			success = True
			
			requiredFields = ["voiceIntegrated", "voiceHKBAvailable", "voiceAHBAvailable", "voiceHKBServer", "voiceAHBServer", "voiceHKBDeviceType"]
			
			for r in requiredFields:		
				if "voiceIntegrated" not in valuesDict:
					errorDict["showAlertText"] 		= "Indigo voice integration failure.  Device is missing the voiceIntegrated field, integration is not possible."
					return (False, valuesDict, errorDict)
		
		except Exception as e:
			success = False
			errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
			
		return (success, valuesDict, errorDict)
		
	#
	# Voice API Hidden Action Received
	#
	def APICall (self, action):
		try:		
			success = True
			errors = indigo.Dict()
			data = indigo.Dict() # Default, can be changed as needed
			payload = {}
			
			props = action.props
			
			if props["command"] == "updateDevice":
				dev = indigo.devices[action.deviceId]
				self.logger.info ("Processing inbound device update request for {}".format(dev.name))
				
				vdict = dev.pluginProps
				
				for key, value in props["valuesDict"].iteritems():
					vdict[key] = value
					
				dev.replacePluginPropsOnServer (vdict)
				
			else:
				errors["param"] = "command"
				errors["message"] = "{0} Voice API received the '{1}' command, but that command is not implemented.  Unable to complete API response.".format(self.pluginDisplayName, props["command"])
				return (False, data, payload, errors)
			
		except Exception as e:
			self.logger.error (ext.getException(e))
			
		return (success, data, payload, errors)			
			
	#
	# Request that voice API plugins update their plugin for this device (or add it if they need to, it's up to the plugin)
	#
	def saveDevice (self, devId, valuesDict):
		try:
			# Check for all required fields
			(chSuccess, chValues, chErrors) = self.checkFields (valuesDict)
			if not chSuccess:
				return False
				
			success = True
			#indigo.server.log(unicode(valuesDict))
			#indigo.devices[devId].updateStateOnServer("voiceAPIData", True)
			
			# Build the dict that will go into voiceAPIData
			api = {}
			apiHKB = {}
			apiAHB = {}
			
			hkb = indigo.server.getPlugin(kHomeKitPlugin)
			if hkb.isEnabled(): # and valuesDict["voiceHKBAvailable"] and (valuesDict["voiceIntegration"] == "ALL" or valuesDict["voiceIntegration"] == "HomeKit"): 
				if self._saveDevice (devId, valuesDict, hkb):
					apiHKB["devId"] = int(devId)
					if valuesDict["voiceHKBServer"] != "": 
						apiHKB["serverId"] = int(valuesDict["voiceHKBServer"])
					else:
						apiHKB["serverId"] = 0
						
				else:
					return False
			
			ahb = indigo.server.getPlugin(kAlexaPlugin)
			if ahb.isEnabled() and valuesDict["voiceAHBAvailable"] and (valuesDict["voiceIntegration"] == "ALL" or valuesDict["voiceIntegration"] == "Alexa"): 
				self._saveDevice (devId, valuesDict, ahb)
				
			api["hkb"] = apiHKB
			api["ahb"] = apiAHB
			indigo.devices[devId].updateStateOnServer("voiceAPIData", json.dumps(api))
			
									
		except Exception as e:
			success = False
			#errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
			
		return success
		
	#
	# Request that voice API plugins update their plugin for this device (or add it if they need to, it's up to the plugin) (called from updateDevice)
	#
	def _saveDevice (self, devId, valuesDict, plugin):		
		try:
			success = True
			
			if plugin.isEnabled():
				apiprops = {}
				apiprops["libversion"] = self.version()
				apiprops["command"] = "updateDevice"
				apiprops["params"] = "none" #(devId, valuesDict)
				apiprops["devId"] = devId
				apiprops["valuesDict"] = valuesDict
				
				(success, data, payload, errors) = plugin.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
			
				if not success:
					self.logger.error (errors["message"])
					return False

			else:
				self.logger.error ("Attempting to add a device to {} but it is not enabled.".format(plugin.pluginDisplayName))
				return False
						
		except Exception as e:
			success = False
			#errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
			
		return success
		
		
		
	#
	# Request that HBB update a device
	#
	def updateDeviceXXX (self, devId, valuesDict, plug = kHomeKitPlugin):
		try:
			# Check for all required fields
			(chSuccess, chValues, chErrors) = self.checkFields (valuesDict)
			if not chSuccess:
				return False
				
			success = True
			plugin = indigo.server.getPlugin(plug)
			
			if plugin.isEnabled():
				apiprops = {}
				apiprops["libversion"] = self.version()
				apiprops["command"] = "updateDevice"
				apiprops["params"] = (devId, valuesDict)
				
				(success, data, payload, errors) = plugin.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
				
				if not success:
					self.logger.error (errors["message"])
					return False
				
			else:
				self.logger.error ("Attempting to update a device on {} but it is not enabled.".format(plugin.pluginDisplayName))
				return False
						
		except Exception as e:
			success = False
			errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
			
		return success	
	
	#
	# An HBB Integration API form field changed
	#
	def integrationFieldChange (self, valuesDict, typeId, devId):
		try:
			errorDict = indigo.Dict()
			
			hkb = indigo.server.getPlugin(kHomeKitPlugin)
			ahb = indigo.server.getPlugin(kAlexaPlugin)
			
			# Check for all required fields
			(chSuccess, chValues, chErrors) = self.checkFields (valuesDict)
			if not chSuccess:
				return (chValues, chErrors)
			
			if valuesDict["voiceIntegrated"]:
				# Set fields based on integraton
				valuesDict["voiceHKBAvailable"] = True
				valuesDict["voiceAHBAvailable"] = False # Until we get Alexa integration keep this at false
				if hkb.pluginDisplayName == "- plugin not installed -": valuesDict["voiceHKBAvailable"] = False
				if ahb.pluginDisplayName == "- plugin not installed -": valuesDict["voiceAHBAvailable"] = False
								
				# Make sure they have the required fields
				if not valuesDict["voiceHKBAvailable"] and not valuesDict["voiceAHBAvailable"]:
					valuesDict["voiceIntegrated"] 		= False
					errorDict["voiceIntegrated"] 		= "Voice integration plugin not installed"
					errorDict["showAlertText"] 			= "Please install HomeKit Bridge from the Indigo plugin store to enable this device for HomeKit."
					#errorDict["showAlertText"] 		= "Please install HomeKit Bridge from the Indigo plugin store to enable this device for HomeKit and/or the Alexa-Hue Bridge from the Indigo plugin store to enable this device for Alexa."
					return (valuesDict, errorDict)
					
				# If the have HKB and it's disabled and AHB is not installed at all
				if hkb.isEnabled() == False and not valuesDict["voiceAHBAvailable"]:
					valuesDict["voiceIntegrated"] 		= False
					errorDict["voiceIntegrated"] 		= "HomeKit Bridge not enabled"
					errorDict["showAlertText"] 			= "HomeKit Bridge is currently disabled and this plugin cannot talk to it, please re-enable HomeKit Bridge before trying to add this device to HomeKit."
					return (valuesDict, errorDict)
					
				# If the have AHB and it's disabled and HKB is not installed at all
				#if ahb.isEnabled() == False and not valuesDict["voiceHKBAvailable"]:
				#	valuesDict["voiceIntegrated"] 		= False
				#	errorDict["voiceIntegrated"] 		= "Alexa-Hue Bridge not enabled"
				#	errorDict["showAlertText"] 			= "Alexa-Hue Bridge is currently disabled and this plugin cannot talk to it, please re-enable Alexa-Hue Bridge before trying to add this device to Alexa."
				#	return (valuesDict, errorDict)	
				
				# If all voice integration is not enabled
				#if hkb.isEnabled() == False and ahb.isEnabled() == False:
				#	valuesDict["voiceIntegrated"] 		= False
				#	errorDict["voiceIntegrated"] 		= "Voice integration plugins are not enabled"
				#	errorDict["showAlertText"] 			= "All voice integration plugins are currently disabled and this plugin cannot talk to them, please re-enable HomeKit Bridge and/or Alexa-Hue Bridge before trying to add this device to HomeKit or Alexa."
				#	return (valuesDict, errorDict)
				
				# Just to be safe, do a blank call to the API to make sure our version is OK
				success = False
				apiprops = {}
				params = {}
				
				if "voiceHKBDeviceTypeList" in valuesDict:
					params["validTypes"] = valuesDict["voiceHKBDeviceTypeList"].replace(" ", "")
				
				apiprops["libversion"] = self.version()
				apiprops["command"] = "loadDevice"
				apiprops["params"] = "none"
				apiprops["devId"] = devId
				apiprops["typeId"] = typeId
				apiprops["valuesDict"] = valuesDict
				
				if hkb.isEnabled():	
					hkbVer = int(hkb.pluginVersion.replace(".", ""))
					if hkbVer < 110:
						valuesDict["voiceIntegrated"] 		= False
						errorDict["voiceIntegrated"] 		= "HomeKit Bridge needs upgraded"
						errorDict["showAlertText"] 			= "You are running a version of HomeKit Bridge that does not support this feature, please upgrade to the latest version to enable this device for HomeKit."
						return (valuesDict, errorDict)	
						
					(success, data, payload, errors) = hkb.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
					
					if success:
						#indigo.server.log(unicode(payload))
						if "serverId" in payload:
							if valuesDict["voiceHKBServer"] == "" or valuesDict["voiceHKBServer"] == "default": valuesDict["voiceHKBServer"] = str(payload["serverId"])
							
						if "voiceDataType" in payload:
							#indigo.server.log(valuesDict["voiceHKBDeviceType"])
							if valuesDict["voiceHKBDeviceType"] == "" or valuesDict["voiceHKBDeviceType"] == "default": valuesDict["voiceHKBDeviceType"] = str(payload["voiceDataType"])	
							
						if "eligible" in payload:
							valuesDict["voiceHKBEnabled"] = payload["eligible"]
						
						if "uimessage" in payload:
							errorDict["showAlertText"] = payload["uimessage"]
					
				#if ahb.isEnabled():	
				#	ahbVer = int(ahb.pluginVersion.replace(".", ""))
				#	if ahbVer < 130:
				#		valuesDict["voiceIntegrated"] 		= False
				#		errorDict["voiceIntegrated"] 		= "HomeKit Bridge needs upgraded"
				#		errorDict["showAlertText"] 			= "You are running a version of HomeKit Bridge that does not support this feature, please upgrade to the latest version to enable this device for HomeKit."
				#		return (valuesDict, errorDict)		
					
				#	(success, data, errors) = ahb.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
				
				if not success:
					self.logger.error (errors["message"])
					valuesDict["voiceIntegrated"] 		= False
					valuesDict["voiceHKBServer"] 		= "none"
					valuesDict["voiceHKBDeviceType"] 	= "default"
					errorDict["showAlertText"]			= errors["message"]
					return (valuesDict, errorDict)	
				
				if valuesDict["voiceHKBServer"] == "": valuesDict["voiceHKBServer"]			= "default" # In case there is a problem
				if valuesDict["voiceHKBDeviceType"] == "": valuesDict["voiceHKBDeviceType"] = "default"
				if valuesDict["voiceIntegration"] == "": valuesDict["voiceIntegration"] = "ALL"
				
				# At this point if we CAN use an integration then it's set to true, set it to false if the user has decided to exclude it
				if valuesDict["voiceIntegration"] != "ALL":
					if valuesDict["voiceIntegration"] == "HomeKit" and valuesDict["voiceHKBAvailable"]: 
						valuesDict["voiceHKBAvailable"] = True
						valuesDict["voiceAHBAvailable"] = False
						
					elif valuesDict["voiceIntegration"] == "Alexa" and valuesDict["voiceAHBAvailable"]: 
						valuesDict["voiceHKBAvailable"] = False
						valuesDict["voiceAHBAvailable"] = True
						
					else:
						valuesDict["voiceIntegration"] = "ALL"
						errorDict["showAlertText"] = "That integration is not currently available, reverting your integration selection to All."
				
			else:
				# Turn off the integration
				valuesDict["voiceHKBAvailable"] = False
				valuesDict["voiceAHBAvailable"] = False
					
			
		except Exception as e:
			success = False
			valuesDict["voiceIntegrated"] = False
			valuesDict["voiceHKBAvailable"] = False
			valuesDict["voiceAHBAvailable"] = False
			errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
			
		return (valuesDict, errorDict)	
		

	#
	# Request a list of valid voice plugins
	#
	def IntegrationPluginList (self, filter="", valuesDict=None, typeId="", targetId=0):
		try:
			ret = [("default", "None found")]
			
			hkb = indigo.server.getPlugin(kHomeKitPlugin)
			ahb = indigo.server.getPlugin(kAlexaPlugin)
			
			retList = []
			
			retList.append (("ALL", "All Indigo Voice Plugins"))
			if hkb.isEnabled(): retList.append (("HomeKit", hkb.pluginDisplayName))
			#if ahb.isEnabled(): retList.append (("Alexa", ahb.pluginDisplayName))
			
			return retList
							
		except Exception as e:
			self.logger.error (self.getException(e))
			
		return ret

	#
	# Request a list of valid servers from HomeKit Bridge
	#
	def HKBIntegrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0):
		try:
			ret = [("default", "No HomeKit Bridge servers found")]
			
			if "voiceHKBAvailable" in valuesDict:
				if valuesDict["voiceHKBAvailable"]:
					hkb = indigo.server.getPlugin(kHomeKitPlugin)
					if hkb.isEnabled():
						apiprops = {}
						apiprops["libversion"] = self.version()
						apiprops["command"] = "getServerList"
						apiprops["params"] = "server" # Cannot add devices to guests or customs for now since guest is an exclusion of a server and custom doesn't integrate into Indog
						apiprops["devId"] = targetId
						apiprops["typeId"] = typeId
						apiprops["valuesDict"] = valuesDict
				
						(success, data, payload, errors) = hkb.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
						
						if success:
							ret = []
							for d in data:
								ret.append ((d[0], d[1]))
						else:
							self.logger.error (errors["message"])
							
		except Exception as e:
			self.logger.error (self.getException(e))
			
		return ret
		
	#
	# Request a list of valid servers from Alexa Hue Bridge
	#
	def AHBIntegrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0):
		try:
			ret = [("default", "No Alexa-Hue Bridge servers found")]
			
			if "voiceAHBAvailable" in valuesDict:
				if valuesDict["voiceAHBAvailable"]:
					ahb = indigo.server.getPlugin(kAlexaPlugin)
					if ahb.isEnabled():
						apiprops = {}
						apiprops["libversion"] = self.version()
						apiprops["command"] = "getServerList"
						apiprops["params"] = "server" # Cannot add devices to guests or customs for now since guest is an exclusion of a server and custom doesn't integrate into Indog
						
						(success, data, payload, errors) = ahb.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
						
						if success:
							ret = []
							for d in data:
								ret.append ((d[0], d[1]))
						else:
							self.logger.error (errors["message"])

		except Exception as e:
			self.logger.error (self.getException(e))
			
		return ret		
	
	#
	# Request a list of valid device types from HomeKit Bridge
	#	
	def IntegrationHKBDeviceTypeList (self, filter="", valuesDict=None, typeId="", targetId=0):
		try:
			ret = [("default", "No Homebridge types found")]
			
			if "voiceHKBAvailable" in valuesDict:
				if valuesDict["voiceHKBAvailable"]:
					hkb = indigo.server.getPlugin(kHomeKitPlugin)
					if hkb.isEnabled():
						apiprops = {}
						apiprops["libversion"] = self.version()
						apiprops["command"] = "getDeviceTypes"
						apiprops["params"] = "allowNone"
						apiprops["devId"] = targetId
						apiprops["typeId"] = typeId
						apiprops["valuesDict"] = valuesDict
						
						(success, data, payload, errors) = hkb.executeAction(kVoiceAPIActionName, deviceId=0, waitUntilDone=True, props=apiprops)
						
						if success:
							ret = []
							for d in data:
								ret.append ((d[0], d[1]))
						else:
							self.logger.error (errors["message"])

		except Exception as e:
			self.logger.error (self.getException(e))
			
		return ret	
		
	#
	# Validate device config
	#
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		try:
			errorDict = indigo.Dict()
			success = True
			
			if "voiceIntegrated" in valuesDict:
				if valuesDict["voiceIntegrated"]:
					if valuesDict["voiceHKBAvailable"]:
						if valuesDict["voiceHKBServer"] == "":
							errorDict["voiceHKBServer"] 	= "Select a HomeKit Bridge server"
							errorDict["showAlertText"] 		= "If you opt to integrate with HomeKit Bridge then you must select which server to attach this device to."
							return (False, valuesDict, errorDict)
						
						if valuesDict["voiceHKBDeviceType"] == "":
							errorDict["voiceHKBDeviceType"] = "Select a HomeKit Bridge device type"
							errorDict["showAlertText"] 		= "If you opt to integrate with HomeKit Bridge then you must select how you want this device treated."
							return (False, valuesDict, errorDict)
						
					# Save the config to the voice plugins	
					self.saveDevice (devId, valuesDict)
				
				else:
					# See if they have stashed api data, if they do then they have removed integration
					dev = indigo.devices[int(devId)]
					saveneeded = False
				
					if "voiceAPIData" in dev.states and dev.states["voiceAPIData"] != "":
						api = json.loads(dev.states["voiceAPIData"])
						if "hkb" in api and len(api["hkb"]) > 0:
							# HomeKit was removed, call the API so it can de-integrate	
							saveneeded = True
						
					if saveneeded:
						if self.saveDevice (devId, valuesDict):
							api = {}
							api["hkb"] = {}
							api["ahb"] = {}
					
							# Rewrite the state so we don't try to call the voice servers anymore
							indigo.devices[devId].updateStateOnServer("voiceAPIData", json.dumps(api))
						
						else:
							success = False
							errorDict["showAlertText"] = "Unable to remove voice integration, please cancel this dialog and check the log for errors."
							
		except Exception as e:
			self.logger.error (self.getException(e))
			
		return (success, valuesDict, errorDict)
		
	#
	# Get exception details
	#
	def getException (self, e):
		exc_type, exc_obj, tb = sys.exc_info()
		f = tb.tb_frame
		lineno = tb.tb_lineno
		filenameEx = f.f_code.co_filename
		filename = filenameEx.split("/")
		filename = filename[len(filename)-1]
		filename = filename.replace(".py", "")
		filename = filename.replace(".pyc","")
		linecache.checkcache(filename)
		line = linecache.getline(filenameEx, lineno, f.f_globals)
		exceptionDetail = "Exception in %s.%s line %i: %s\n\t\t\t\t\t\t\t CODE: %s" % (filename, f.f_code.co_name, lineno, str(e), line.replace("\t",""))
	
		return exceptionDetail		