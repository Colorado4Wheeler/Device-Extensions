import datetime
import time
import indigo
import sys
import string
import calendar

#
# Print library version - added optional return in 1.0.2
#
def libVersion (returnval = False):
	ver = "1.0.4"
	if returnval: return ver
	
	indigo.server.log ("##### EPS UI %s #####" % ver)
	

#
# Get all states for a device in a device UI
#
def getStatesForDevice(filter, valuesDict, typeId, targetId):
	myArray = [("default", "^^ SELECT A DEVICE ^^")]
	filter = str(filter)
	
	#indigo.server.log("PASSED FILTER: " + filter)
		
	try:		
		if valuesDict is None: return myArray
		if filter == "": return myArray
		if filter in valuesDict == False: return myArray
		if valuesDict[filter] == "": return myArray
			
		dev = indigo.devices[int(valuesDict[filter])]
	except:
		return myArray
	
	stateAry = []
	
	for stateName, stateValue in dev.states.iteritems():
		option = (stateName, stateName)
		stateAry.append(option)
		
	return stateAry
	
#
# Get all devices with a state matching filter (filter is treated as an OR, not AND)
#
def getDevicesWithStates(filter, valuesDict, typeId, targetId):
	myArray = [("default", "No compatible devices found")]
	filter = str(filter)
	
	stateList = filter.split(",")
	
	# i.e., "onOffState,brightnessLevel"
	
	try:		
		if filter == "": return myArray
		
		devAry = []
		
		for dev in indigo.devices:
			isMatch = False
			
			for s in stateList:
				if s in dev.states: isMatch = True
			
			if isMatch:
				option = (str(dev.id), dev.name)
				devAry.append(option)
			
		if len(devAry) > 0:
			return devAry
		else:
			return myArray
		
	except:
		return myArray

	
#
# Get all pluginprops or ownerprops for a device in a device UI
#
def getPropsForDevice(filter, valuesDict, typeId, targetId):
	myArray = [("default", "^^ SELECT A DEVICE ^^")]
	filter = str(filter)
	
	#indigo.server.log("PASSED FILTER: " + filter)
		
	try:		
		if valuesDict is None: return myArray
		if filter == "": return myArray
		if filter in valuesDict == False: return myArray
		if valuesDict[filter] == "": return myArray
			
		dev = indigo.devices[int(valuesDict[filter])]
	except:
		return myArray
	
	propsAry = []
	
	for propName, propValue in dev.ownerProps.iteritems():
		option = (propName, propName)
		propsAry.append(option)
		
	return propsAry
	
#
# Compose special data types for menus 1.0.1
#
def getDataList(filter, valuesDict=None, typeId="", targetId=0):
	myArray = [("default", "No compatible value items found")]
	filter = str(filter)
	
	#indigo.server.log("Looking for %s" % filter)
	
	# i.e., "times"
	# i.e., "xyz.dat"
	# i.e., "xyz.dat:abc" - Find 'abc' in list
	# i.e., "xyz.dat:#varname - Find value of field 'varname' in list
	# i.e., "xyz.dat:#varname|abc - Find value of field 'varname' in list, if valuesDict is empty find "abc" instead
	# i.e., "xyz.dat:#varname|* - Find value of field 'varname' in list, if valuesDict is empty return entire list with no filter instead
	# i.e., "dayofmonth:#varname" - Return each day of the month for the varname value
	
	try:		
		if filter == "": return myArray
		
		retAry = []
	
		# Create list of times for 24 hours every 15 minutes
		if filter.lower() == "times":
			for h in range (0, 24):
				for minute in range (0, 4):
					hour = h
					hourEx = h
					am = " AM"
				
					if hour == 0:
						hourEx = 12
				
					elif hour > 12:
						hourEx = hour - 12
						am = " PM"
					
					key = "%02d:%02d" % (hour, minute * 15)
					value = "%02d:%02d %s" % (hourEx, minute * 15, am)
				
					option = (key, value)
					retAry.append(option)
					
			return retAry
			
		# Return month strings with number values - 1.0.3
		if filter.lower() == "months":
			return _getMonths (filter, valuesDict)
			
		# Take a month variable number and return days in that month - 1.0.3
		if filter.lower() == "dayofmonth":
			# Always return either the current month or a future month, never the past
			z = string.find (filter, '#')
			if z < 0:
				# We didn't get a variable to use as the baseline, return 31 days generically
				for i in range (1, 32):
					option = (i, i)
					retAry.append(option)
					
				return retAry
			else: # The month variable must be a number
				data = filter.split("#")
				month = int(data[1])
				d = indigo.server.getTime()
				year = int(d.strftime("%Y"))
				
				if month < int(d.strftime("%-m")):
					# It's in the past, use next year
					m = calendar.monthrange(year + 1, month)
				else:
					# It's this year or this month
					m = calendar.monthrange(year, month)
					
				for i in range (1, m[1]):
					option = (i, i)
					retAry.append(option)
					
				return retAry
				
			
		# Read in a data file and use those options
		x = string.find (filter, '.')
		if x > -1:
			filterEx = ""
		
			y = string.find (filter, ':')
			if y > -1:
				# Filtering for term
				data = filter.split(":")
				filter = data[0]
				filterEx = data[1]
			
				if filterEx[0] == "#":
					# Filter value is based on another field
					field = filterEx[1:]
					if field in valuesDict: 
						filterEx = valuesDict[field]
					else:
						z = string.find (field, '|')
						if z > -1:
							# There is a default search term (generally in case valuesDict is empty like when a device first loads config)
							f = field.split("|")
							if f[0] in valuesDict:
								filterEx = valuesDict[f[0]]
							else:
								if f[1] == "*":
									filterEx = "" # * means no filtering
								else:
									filterEx = f[1] # Literal search
						else:
							# Field doesn't have a condition and it's not in valuesDict
							if field == "-nothing-": 
								filterEx = "-nothing-"
							else:
								filterEx = "---INVALID---"
								return myArray	
					
			lines = open("eps/" + filter).read().split('\n')
			
			for l in lines:
				details = l.split("\t")
				
				if len(details) == 2: # 2 option list (1 = value, 0 = display)
					if filterEx == "":
						option = (details[1], details[0])
						retAry.append(option)
					else:
						# Special condition, if filterEx is -nothing- then we are looking for empty values
						isnothing = False
						if filterEx == "-nothing-": 
							filterEx = ""
							isnothing = True
							
						if details[0] == filterEx or details[1] == filterEx:
							option = (details[1], details[0])
							retAry.append(option)
							
						if isnothing == True: filterEx = "-nothing-" # reset for next loop
						
				else:
					
					# 2 elements is a simple value/display lookup, more than that is follows the design of:
					# 0 = Index number, 1 = Filter, 2 = Display, 3+ = Filter & data
					if filterEx == "":
						data = ""
						for i in range (3, len(details)):
							data += details[i] + "|"
										
						data = details[0] + "|" + data[:-1] # add index and strip last delimiter
														
						option = (data, details[2])
						retAry.append(option)
						
					else:
						# Special condition, if filterEx is -nothing- then we are looking for empty values
						isnothing = False
						if filterEx == "-nothing-": 
							filterEx = ""
							isnothing = True
							
						# See if the main filter field matches, then check the data fields
						filterMatch = False
						data = ""
						
						if details[1] == filterEx: filterMatch = True
						for i in range (3, len(details)):
							if details[i] == filterEx: filterMatch = True
						
						if filterMatch:
							for i in range (3, len(details)):
								data += details[i] + "|"
										
							data = details[0] + "|" + data[:-1] # add index and strip last delimiter
							option = (data, details[2])
							
							retAry.append(option)
							
						if isnothing == True: filterEx = "-nothing-" # reset for next loop
						
				
				
					
								
			return retAry
		
	except Exception as e:
		indigo.server.log("Error in ui.getDataList: %s" % str(e), isError=True)
		return myArray
		
	return myArray
	
#
# Return list of months (called from getDataList) - 1.0.3
#
def _getMonths (filter, valuesDict):
	default = [("default", "No compatible value items found")]
	retAry = []
	
	try:
		m = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
		for i in range(0, 12):
			option = (i + 1, m[i])
			retAry.append(option)
			
		return retAry
	
	except Exception as e:
		indigo.server.log("Error in ui._getMonths: %s" % str(e), isError=True)
		return default
	
	
#
# Return list of indigo folders for various components
#
def getIndigoFolders(filter, valuesDict, typeId, targetId):
	myArray = [("default", "No folders found")]
	filter = str(filter)
	
	try:
		if filter == "": return myArray
		
		folderAry = []
		
		# Add a "default" option
		option = (0, "- Top Level Folder -")
		folderAry.append(option)
		option = (1, "- Create Plugin Folder -")
		folderAry.append(option)
		
		if filter.lower() == "device":
			for f in indigo.devices.folders:
				option = (f.id, f.name)
				folderAry.append(option)		
					
	except:
		return myArray
		
	return folderAry
	
#
# Find plugin devices matching array of plugin ids
#
def getPluginDevices(filter, valuesDict, typeId, targetId):
	myArray = [("default", "No compatible devices found")]
	filter = str(filter)
	
	devList = filter.split(",")
	excludes = {}
	
	# i.e., "- TOP OPTION -" (add option) 1.0.1
	# i.e., "#propname" (filter out the id of this property name)
	# i.e., "com.perceptiveautomation.indigoplugin.xyz:xyzplugintypeid"
	# i.e., "com.perceptiveautomation.indigoplugin.xyz"
	
	try:		
		if filter == "": return myArray
		
		devAry = []
	
		# Add any default options
		for pluginId in devList:
			if pluginId[0] == "-":
				option = (pluginId, pluginId)
				devAry.append(option)
				
			elif pluginId[0] == "#": # 1.0.1
				value = pluginId[1:]
				if value in valuesDict:
					excludes[int(valuesDict[value])] = True
		
		for dev in indigo.devices:
			isMatch = False
			
			if len(excludes) > 0: # 1.0.1
				if dev.id in excludes: 
					continue
			
			for pluginId in devList:
				x = string.find (pluginId, ':')
				if x > -1 : 
					plugin = pluginId.split(":")
					if dev.pluginId == plugin[0] and dev.deviceTypeId == plugin[1]: isMatch = True
				else:
					if dev.pluginId == pluginId: isMatch = True
				
			if isMatch:
				option = (str(dev.id), dev.name)
				devAry.append(option)
			
		if len(devAry) > 0:
			return devAry
		else:
			return myArray
		
	except:
		return myArray
	
	return stateAry
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	