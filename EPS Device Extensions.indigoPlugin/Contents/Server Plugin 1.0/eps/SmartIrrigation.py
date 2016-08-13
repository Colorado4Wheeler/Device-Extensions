# -*- coding: utf-8 -*-
#
# SmartIrrigation: Methods and actions for Smart Irrigation
#
#########################################################################

import indigo
import os
import sys
import time
import datetime
from DevUtils import DevUtils
import dtutil
import eps # 1.6

class SmartIrrigation:

	#
	# Initialize the class
	#
	def __init__ (self, DevUtilsLib):
		self.cache = DevUtilsLib
		
	#
	# Device actions
	#
	def deviceActions (self, devAction):	
		devEx = indigo.devices[devAction.deviceId]
		dev = indigo.devices[int(devEx.pluginProps["device"])]
		
		indigo.server.log("Sprinklers")
		
		if devAction.pluginTypeId == "ir-zone1toggle": self.zoneToggle (dev, 1)
		if devAction.pluginTypeId == "ir-zone2toggle": self.zoneToggle (dev, 2)
		if devAction.pluginTypeId == "ir-zone3toggle": self.zoneToggle (dev, 3)
		if devAction.pluginTypeId == "ir-zone4toggle": self.zoneToggle (dev, 4)
		if devAction.pluginTypeId == "ir-zone5toggle": self.zoneToggle (dev, 5)
		if devAction.pluginTypeId == "ir-zone6toggle": self.zoneToggle (dev, 6)
		if devAction.pluginTypeId == "ir-zone7toggle": self.zoneToggle (dev, 7)
		if devAction.pluginTypeId == "ir-zone8toggle": self.zoneToggle (dev, 8)
		if devAction.pluginTypeId == "ir-quickpause": self.quickPause (dev, devEx, devAction.props["pauseminutes"])
		
	#
	# Quick pause action - 1.6
	#
	def quickPause (self, dev, devEx, n):
		try:
			n = int(n)
		except:
			indigo.server.log("Value for quick pause doesn't seem to be a number", isError=True)
			return
		
		if n < 1: 
			indigo.server.log("Quick pause time sent as %i minutes, must be at least 1 minute" % n, isError=True)
		
		d = indigo.server.getTime()
		
		if devEx.states["quickpaused"] and dev.displayStateValUi == "schedule paused":
			# We are already paused, add time to the pause
			prevtime = datetime.datetime.strptime (dev.states["quickPauseEndTime"], "%Y-%m-%d %H:%M:%S")
			newtime = dtutil.DateAdd ("minutes", n, prevtime)
			devEx.updateStateOnServer("quickpaused", True)
			devEx.updateStateOnServer ("quickPauseEndTime", newtime.strftime("%Y-%m-%d %H:%M:%S"))
			
		else:
			# New quick pause, set the value and pause sprinklers
			newtime = dtutil.DateAdd ("minutes", n, d)
			devEx.updateStateOnServer("quickpaused", True)
			devEx.updateStateOnServer ("quickPauseEndTime", newtime.strftime("%Y-%m-%d %H:%M:%S"))
			devEx.updateStateOnServer("timerRunning", True)
			indigo.sprinkler.pause(dev.id)
			indigo.server.log("Quick Paused")		
	
	# 
	# Toggle zone on/off
	#
	def zoneToggle (self, dev, n):
		allOff = True
		for i in range(1,9):
			try: # 1.5.1
				if dev.states["zone" + str(i)]: allOff = False
			except:
				X = 1 # placeholder
			
		# If everything is off then we just need to turn on the zone they want
		if allOff:
			indigo.sprinkler.setActiveZone(dev.id, index=n)
		else:
			if dev.states["zone" + str(n)]:
				# It's this zone that is on, so turn off everything because our toggle is OFF
				indigo.sprinkler.stop(dev.id)
			else:
				# A different zone is on, meaning this zone is off and they want to toggle it ON
				indigo.sprinkler.setActiveZone(dev.id, index=n)
		
	
	#
	# Update irrigation device
	#
	def updateIrrigation (self, devEx, origDev, newDev):
		dev = indigo.devices[int(devEx.pluginProps["device"])]
		unpausing = False # 1.5.0
		
		# Failsafe to make sure we don't have blank displays
		if devEx.states["pauseTimeRemaining"] == "": devEx.updateStateOnServer("pauseTimeRemaining", "00:00:00")
		if devEx.states["zoneRunTimeRemaining"] == "": devEx.updateStateOnServer("zoneRunTimeRemaining", "00:00:00")
		if devEx.states["scheduleRunTimeRemaining"] == "": devEx.updateStateOnServer("scheduleRunTimeRemaining", "00:00:00")
		
		if unicode(origDev) != "":
			# Check for zone duration changes (1.4.1)
			if origDev.zoneMaxDurations != newDev.zoneMaxDurations or origDev.zoneScheduledDurations != newDev.zoneScheduledDurations:
				self.getTotalRunTime (dev, 1, devEx)
				
			# Check if we went from running to paused (1.5.0)
			if origDev.displayStateValUi == "schedule paused" and newDev.displayStateValUi == "schedule paused":
				# We are still paused, nothing to do
				return
			
			elif origDev.displayStateValUi == "schedule paused" and newDev.displayStateValUi != "schedule paused":
				# We went from paused to resume, recalculate the zone/total time remaining based on elapsed pause time
				if devEx.states["pauseDetectTime"] == "":
					indigo.server.log("Error - there was no pause time, was the plugin installed or enabled when you paused the sprinklers?")
					return
				
				devEx.updateStateOnServer("paused", False)
				pauseSecs = dtutil.DateDiff ("seconds", indigo.server.getTime(), str(devEx.states["pauseDetectTime"]))

				# Add those seconds to the zone run time
				oldZoneRunTime = datetime.datetime.strptime (devEx.states["zoneEndTime"], "%Y-%m-%d %H:%M:%S")
				newZoneRunTime = dtutil.DateAdd("seconds", pauseSecs, oldZoneRunTime)
				devEx.updateStateOnServer ("zoneEndTime", newZoneRunTime.strftime("%Y-%m-%d %H:%M:%S"))
			
				# Add those seconds to the total run time
				oldTotalRunTime = datetime.datetime.strptime (devEx.states["scheduleEndTime"], "%Y-%m-%d %H:%M:%S")
				newTotalRunTime = dtutil.DateAdd("seconds", pauseSecs, oldTotalRunTime)
				devEx.updateStateOnServer ("scheduleEndTime", newTotalRunTime.strftime("%Y-%m-%d %H:%M:%S"))
				
				devEx.updateStateOnServer("timerRunning", True)
				
				unpausing = True # so the start code below doesn't reset stuff
				
				
			elif origDev.displayStateValUi != "schedule paused" and newDev.displayStateValUi == "schedule paused":
				# The schedule was just paused, stamp everything and exit since there is nothing to do
				d = indigo.server.getTime()
				devEx.updateStateOnServer("paused", True)
				devEx.updateStateOnServer ("pauseDetectTime", d.strftime("%Y-%m-%d %H:%M:%S"))
				devEx.updateStateOnServer("timerRunning", False)
				return
				
			for i in range(1,9):
				try: # 1.5.1
					if origDev.states["zone" + str(i)] != newDev.states["zone" + str(i)]:
						# This zone just toggled from on to off or off to on
						if origDev.states["zone" + str(i)]:
							# We went from on to off
							shutoff = True
						
							if devEx.states["raining"]:
								# It's raining, see if we have rain management on
								if devEx.pluginProps["rain"]:
									# Ok, it's raining and we are using rain management, the timer takes it from here
									shutoff = False
								
							if newDev.displayStateValUi == "schedule paused": shutoff = False
						
							if shutoff:
								devEx.updateStateOnServer("timerRunning", False)
							
								devEx.updateStateOnServer("currentZoneName", "")
							
								if devEx.pluginProps["timeformat"] == "ms": devEx.updateStateOnServer("zoneRunTimeRemaining", "00:00")
								if devEx.pluginProps["timeformat"] == "hms": devEx.updateStateOnServer("zoneRunTimeRemaining", "00:00:00")
						else:
							# We went from off to on, if we are resuming then do nothing, the timer will take care of it
							devEx.updateStateOnServer("currentZoneName", origDev.zoneNames[i-1])
						
							if devEx.states["resuming"]:
								devEx.updateStateOnServer ("resuming", False) # We now know, turn it off
								devEx.updateStateOnServer("timerRunning", True) # Turn the timer back on
							elif unpausing:
								devEx.updateStateOnServer("timerRunning", True) # Turn the timer back on
							else:
								runtime = self.getMaxRunTime (newDev, i)	
								if int(runtime) < 1: return # We don't support float right now
						
								#runtime = 102 # Testing
						
								d = indigo.server.getTime()
								t = dtutil.DateAdd("minutes", int(runtime), d)
						
								devEx.updateStateOnServer("timerRunning", True)
								devEx.updateStateOnServer ("zoneEndTime", t.strftime("%Y-%m-%d %H:%M:%S"))
						
								# Now calculate total time remaining
								runtime = self.getTotalRunTime (newDev, i)	
								#if int(runtime) < 1: return # We don't support float right now
						
								t = dtutil.DateAdd("minutes", int(runtime), d)
						
								devEx.updateStateOnServer ("scheduleEndTime", t.strftime("%Y-%m-%d %H:%M:%S"))
				except:
					ZZ = 1 # placeholder
											
			self.updateStateDisplay (dev, devEx)
						
		else:
			# We are starting up or getting device state manually
			self.getTotalRunTime (dev, 1, devEx)
			self.updateStateDisplay (dev, devEx)

				
			
	#	
	# Update device states
	#
	def updateStateDisplay (self, dev, devEx):
		# See if we are paused (1.5.0
		if dev.displayStateValUi == "schedule paused":
			devEx.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOff)
			devEx.updateStateOnServer("statedisplay", "schedule paused")
		
		# See if any zones are on
		zonesOff = True
		currentZoneNum = 0
		for i in range(1,9):
			try: # 1.5.1
				if dev.states["zone" + str(i)]: 
					currentZoneNum = i
					zonesOff = False
			except:
				X = 1 # placeholder
			
		if zonesOff:
			devEx.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOff)
			devEx.updateStateOnServer("statedisplay", "all zones off")
		else:
			devEx.updateStateImageOnServer(indigo.kStateImageSel.SprinklerOn)
			devEx.updateStateOnServer("statedisplay", "Z" + str(currentZoneNum) + " - " + devEx.states["zoneRunTimeRemaining"])
			

	#
	# Determine total run time for all zones (devEx added 1.3.0)
	#
	def getTotalRunTime (self, dev, n, devEx = None):
		if len(dev.zoneScheduledDurations) > 0:
			# They are running a schedule, use that time
			calctime = dev.zoneScheduledDurations
		else:
			calctime = dev.zoneMaxDurations
			
		# Run through all the zones and get the run time for each zone and store it - 1.3.0
		if devEx != None:
			calctimeEx = calctime
			calcruntime = True
			
			# See if they are remembering the last schedule (1.5.0)
			if "lastschedule" in devEx.pluginProps:
				if devEx.pluginProps["lastschedule"]:
					if calctime == dev.zoneMaxDurations: calcruntime = False
						
			# Condition to get run times (1.5.0)
			if calcruntime:
				for i in range(1, 9):
					try: # 1.5.1 in case they don't have all 8 zones
						devEx.updateStateOnServer("zone" + str(i) + "Schedule", calctimeEx[i-1])
					except:
						X = 1 # placeholder
			
		# Since irrigation schedules are sequential, start at the current zone to zone 8 to calculate the times
		totaltime = float(0)
		for i in range (n - 1, 8): # Start at one index below our zone number since this is zero based
			try: # 1.5.1
				totaltime = totaltime + calctime[i]
			except:
				X = 1 # placeholder
		
		#indigo.server.log(unicode(devEx.states))
		#indigo.server.log(u"%s minutes runtime calculated" % unicode(totaltime))
		return totaltime
	
	#
	# Determine the max run time for the current zone
	#
	def getMaxRunTime (self, dev, n):
		# n is passed as the zone number, for reference we need to convert ot the zero based index number
		n = n - 1
		
		if len(dev.zoneScheduledDurations) > 0:
			# They are running a schedule, use that time
			#indigo.server.log(unicode(dev))
			return dev.zoneScheduledDurations[n]
		else:
			return dev.zoneMaxDurations[n]
			
	#
	# Irrigation runtime timer tick
	#
	def irrigationTimerTick (self):
		for dev in indigo.devices:
			if dev.deviceTypeId == "epsdeirr":
				# In case something happened outside of the plugin running, make sure if there are no zones on that
				# all timers are stopped
				d = indigo.server.getTime()
				
				allOff = True
				devEx = indigo.devices[int(dev.pluginProps["device"])]
				
				try: # 1.5.1
					for i in range(1,9):
						if devEx.states["zone" + str(i)]: allOff = False
				except:
					ZZ = 1 # placeholder
					
				if self.isRaining (dev):
					if dev.states["raining"] == False:
						#self.debugLog(u"" + dev.name + " now knows it's raining")
						
						dev.updateStateOnServer("raining", True)
						dev.updateStateOnServer ("rainDetectTime", d.strftime("%Y-%m-%d %H:%M:%S"))
						
						# It's raining, if our rain management is enabled take actions
						if dev.pluginProps["rain"]:
							#self.debugLog(u"Rain detection enabled on " + dev.name)
							
							# Set our hard stop time
							if dev.pluginProps["resetrainaction"]:
								#self.debugLog(u"Device configured to hard stop after one hour of rain")
								
								t = dtutil.DateAdd("minutes", 60, d)
								dev.updateStateOnServer ("hardStopTime", t.strftime("%Y-%m-%d %H:%M:%S"))
								
								# Fake the "allOff" so we continue into the loop
								allOff = False
						
							if dev.pluginProps["rainaction"] == "stop":
								indigo.sprinkler.stop(dev.id)
								dev.updateStateOnServer("timerRunning", False)
								if dev.pluginProps["timeformat"] == "ms":
									dev.updateStateOnServer("zoneRunTimeRemaining", "00:00")
									dev.updateStateOnServer("scheduleRunTimeRemaining", "00:00")
								else:
									dev.updateStateOnServer("zoneRunTimeRemaining", "00:00:00")
									dev.updateStateOnServer("scheduleRunTimeRemaining", "00:00:00")
									
								# There is nothing further to do here, no timers are running and no schedules are
								# set so exit out
								return
							
							elif dev.pluginProps["rainaction"] == "pause":
								indigo.sprinkler.pause(devEx.id)
															
							elif dev.pluginProps["rainaction"] == "resume":
								indigo.sprinkler.pause(devEx.id)
					else:
						# It's raining and we have already run our rain routine
						if dev.pluginProps["rain"]:
							if dev.pluginProps["resetrainaction"]:
								# Fake out allOn so we continue our timer
								allOff = False
							
				else:
					if dev.states["raining"] == True:
						#self.debugLog(u"" + dev.name + " now knows it's no longer raining")
					
						dev.updateStateOnServer("raining", False)
					
						# Reverse what we did when it started raining
						if dev.pluginProps["rain"]:
							# Set the hard stop far into the future just to be safe
							dev.updateStateOnServer ("hardStopTime", "2030-12-31 23:59:59")
						
							if dev.pluginProps["rainaction"] == "resume":
								# Recalculate the end time by calculating how many seconds it rained
								rainSecs = dtutil.DateDiff ("seconds", indigo.server.getTime(), str(dev.states["rainDetectTime"]))
							
								# Failsafe in case something is wrong
								if rainSecs < 0: rainSecs = rainSecs * -1
							
								# Add those seconds to the zone run time
								oldZoneRunTime = datetime.datetime.strptime (dev.states["zoneEndTime"], "%Y-%m-%d %H:%M:%S")
								newZoneRunTime = dtutil.DateAdd("seconds", rainSecs, oldZoneRunTime)
								dev.updateStateOnServer ("zoneEndTime", newZoneRunTime.strftime("%Y-%m-%d %H:%M:%S"))
							
								# Add those seconds to the total run time
								oldTotalRunTime = datetime.datetime.strptime (dev.states["scheduleEndTime"], "%Y-%m-%d %H:%M:%S")
								newTotalRunTime = dtutil.DateAdd("seconds", rainSecs, oldTotalRunTime)
								dev.updateStateOnServer ("scheduleEndTime", newTotalRunTime.strftime("%Y-%m-%d %H:%M:%S"))
							
								# Update resuming state on device so the start/stop trigger knows we are resuming
								dev.updateStateOnServer ("resuming", True)
							
								# Resume the zone if it's paused
								if devEx.states["activeZone.ui"] == "schedule paused": indigo.sprinkler.resume(devEx.id)
				
				if dev.states["quickpaused"]: allOff = False # Force timer run during quick pause
								
				if allOff:
					# See if we are paused rather than stopped (1.5.0)
					if devEx.displayStateValUi == "schedule paused": return
					
					dev.updateStateOnServer("timerRunning", False)
					dev.updateStateOnServer("quickpaused", False)
				
					if dev.pluginProps["timeformat"] == "ms":
						dev.updateStateOnServer("zoneRunTimeRemaining", "00:00")
						dev.updateStateOnServer("scheduleRunTimeRemaining", "00:00")
						dev.updateStateOnServer("pauseTimeRemaining", "00:00")
					else:
						dev.updateStateOnServer("zoneRunTimeRemaining", "00:00:00")
						dev.updateStateOnServer("scheduleRunTimeRemaining", "00:00:00")
						dev.updateStateOnServer("pauseTimeRemaining", "00:00:00")

					return
										
				if dev.states["timerRunning"]:
					# We only calculate rain time if rain management is off or it's on and not raining
					runTimers = False
					
					if dev.pluginProps["rain"] == False: runTimers = True
					if dev.pluginProps["rain"]:
						if dev.states["raining"] == False: runTimers = True	
					
					if runTimers:
						# Calculate the zone time remaining
						#indigo.server.log("### Getting Zone Run Time Report ###")
						self.irrigationTimerReport (dev, True, "zoneEndTime", "zoneRunTimeRemaining")
						#indigo.server.log(dev.states["zoneRunTimeRemaining"])
					
						# Calculate total time remaining
						#indigo.server.log("### Getting Total Run Time Report ###")
						self.irrigationTimerReport (dev, True, "scheduleEndTime", "scheduleRunTimeRemaining")

					# If quick pause is active - 1.6
					if dev.states["quickpaused"]:
						self.irrigationTimerReport (dev, False, "quickPauseEndTime", "pauseTimeRemaining")
						
						if dev.states["pauseTimeRemaining"] == "00:00" or dev.states["pauseTimeRemaining"] == "00:00:00":
							dev.updateStateOnServer("quickpaused", False)
							indigo.sprinkler.resume(devEx.id)
							
					# If rain management is on, hard stop is configured and it's raining then calc hard stop
					if dev.pluginProps["rain"]:
						if dev.pluginProps["resetrainaction"]:
							if dev.states["raining"]:
								self.irrigationTimerReport (dev, False, "hardStopTime", "pauseTimeRemaining")
								#indigo.server.log(dev.states["hardStopTime"])
								
								# If we reached our hard stop time then stop the sprinklers
								if dev.states["pauseTimeRemaining"] == "00:00" or dev.states["pauseTimeRemaining"] == "00:00:00":
									indigo.sprinkler.stop(devEx.id)
									dev.updateStateOnServer("timerRunning", False) # Stop the timer, we are done
					
						
	
	#
	# Irrigation timer reporting
	#
	def irrigationTimerReport (self, dev, changeTimer, timeState, displayState):
		s = dtutil.DateDiff ("seconds", str(dev.states[timeState]), indigo.server.getTime())
		#indigo.server.log(u"%s seconds calculated" % unicode(s))
					
		if s < 1:
			# Time is up
			if changeTimer: dev.updateStateOnServer("timerRunning", False)
			if dev.pluginProps["timeformat"] == "ms": dev.updateStateOnServer(displayState, "00:00")
			if dev.pluginProps["timeformat"] == "hms": dev.updateStateOnServer(displayState, "00:00:00")
		else:
			lm, ls = divmod(s, 60)
			lh, lm = divmod(lm, 60)
			
			#indigo.server.log(u"%s hours, %s minutes, %s seconds" % (unicode(lh), unicode(lm), unicode(ls)))
			
			# For displaying on 4 digit LCD's, we need show 99:99 if more than 1 hour
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
								
			#indigo.server.log("%02d:%02d:%02d - %s" % (lh, lm, ls, displayState))						
			if dev.pluginProps["timeformat"] == "ms": dev.updateStateOnServer(displayState, "%02d:%02d" % (lm, ls))
			if dev.pluginProps["timeformat"] == "hms": dev.updateStateOnServer(displayState, "%02d:%02d:%02d" % (lh, lm, ls))
			
	
	#
	# Check if our rain device reports rain
	#
	def isRaining (self, dev):
		if dev.pluginProps["rain"]:
			devRain = indigo.devices[int(dev.pluginProps["raindevice"])]
			stateName = dev.pluginProps["states"]
			stateValue = dev.pluginProps["rainvalue"]
			
			if dev.pluginProps["statetype"] == "string":
				if devRain.states[stateName] == stateValue: return True	
			else:
				# Return the device state as is
				return devRain.states[stateName]
				
		return False
		
