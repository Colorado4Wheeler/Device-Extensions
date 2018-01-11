# Homebridge Buddy Plugin API
# Copyright (c) 2018 ColoradoFourWheeler / EPS
# Version 1.0.0
#
# Include this library in your plugin using the following syntax at the top of your Indigo plugin:
#
#	If saving hbb.py to a subfolder under Server Plugin called "lib" (for example):
# 		from lib.hbb import HomebridgeBuddy
# 		hbb = HomebridgeBuddy()
#
#		If you include it from a subfolder please ensure that the folder has a file named __init__.py as well. This file can be blank but MUST be present.
#
#	If saving hbb.py to the same folder as plugin.py:
#		
#		from hbb import HomebridgeBuddy
#		hbb = HomebridgeBuddy()
#
# Place the following function definitions into your plugin.py file to utilize this library:
#	def checkForPlugin (self): return hbb.hbbCheckForPlugin ()
#	def integrationFieldChange (self, valuesDict, typeId, devId): return hbb.hbbIntegrationFieldChange (valuesDict, typeId, devId)
#	def integrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0): return hbb.hbbIntegrationServerList (filter, valuesDict, typeId, targetId)
#	def integrationTreatAsList (self, filter="", valuesDict=None, typeId="", targetId=0): return hbb.hbbIntegrationTreatAsList (filter=, valuesDict, typeId, targetId)
#



import indigo
import logging
import linecache
import sys

class HomebridgeBuddy:
	
	#
	# Initialize the class
	#
	def __init__ (self):
		self.logger = logging.getLogger ("Plugin.hbb")
		self.version = "1.0.0"
		
		self.logger.debug ("Starting Homebridge Buddy plugin API version {0}".format(self.version))
		
	#
	# Report back our version number (in case the calling plugin wants to include that in their support dump)
	#
	def version (self):
		return self.version
		
	#
	# Check for Homebridge Buddy
	#
	def checkForPlugin (self):
		try:
			return indigo.server.getPlugin("com.eps.indigoplugin.homebridge")
			
		except Exception as e:
			success = False
			errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
		
	
	#
	# An HBB Integration API form field changed
	#
	def integrationFieldChange (self, valuesDict, typeId, devId):
		try:
			errorDict = indigo.Dict()
			
			if "hbbIntegrated" in valuesDict:
				if valuesDict["hbbIntegrated"]:
					hbb = self.checkForPlugin()
					
					if hbb.pluginDisplayName == "- plugin not installed -":
						valuesDict["hbbIntegrated"] 	= False
						errorDict["hbbIntegrated"] 		= "Homebridge Buddy not installed"
						errorDict["showAlertText"] 		= "Please install Homebridge Buddy from the Indigo plugin store to enable this device for HomeKit."
						return (valuesDict, errorDict)
						
					if hbb.isEnabled() == False:
						valuesDict["hbbIntegrated"] 	= False
						errorDict["hbbIntegrated"] 		= "Homebridge Buddy not enabled"
						errorDict["showAlertText"] 		= "Homebridge Buddy is currently disabled and this plugin cannot talk to it, please re-enable Homebridge Buddy before trying to add this device to HomeKit."
						return (valuesDict, errorDict)	
						
					hbbVer = int(hbb.pluginVersion.replace(".", ""))
					if hbbVer < 107:
						valuesDict["hbbIntegrated"] 	= False
						errorDict["hbbIntegrated"] 		= "Homebridge Buddy needs upgraded"
						errorDict["showAlertText"] 		= "You are running a version of Homebridge Buddy that does not support this feature, please upgrade to the latest version to enable this device for HomeKit."
						return (valuesDict, errorDict)	
					
					if valuesDict["hbbServer"] == "": valuesDict["hbbServer"] 	= "default" # In case there is a problem
					if valuesDict["hbbTreatAs"] == "": valuesDict["hbbTreatAs"] = "default"
					
			
		except Exception as e:
			success = False
			errorDict["showAlertText"] = unicode(e)
			self.logger.error (self.getException(e))
			
		return (valuesDict, errorDict)	
		

	#
	# Request a list of valid servers from Homebridge Buddy
	#
	def integrationServerList (self, filter="", valuesDict=None, typeId="", targetId=0):
		try:
			ret = [("default", "No Homebridge Buddy servers found")]
			
			if "hbbIntegrated" in valuesDict:
				if valuesDict["hbbIntegrated"]:
					hbb = self.checkForPlugin()
					if hbb.isEnabled():
						X = 1

		except Exception as e:
			self.logger.error (self.getException(e))
			
		return ret
	
	#
	# Request a list of valid device types from Homebridge Buddy
	#	
	def integrationTreatAsList (self, filter="", valuesDict=None, typeId="", targetId=0):
		try:
			ret = [("default", "No Homebridge types found")]
			
			if "hbbIntegrated" in valuesDict:
				if valuesDict["hbbIntegrated"]:
					hbb = self.checkForPlugin()
					if hbb.isEnabled():
						X = 1

		except Exception as e:
			self.logger.error (self.getException(e))
			
		return ret	
		
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