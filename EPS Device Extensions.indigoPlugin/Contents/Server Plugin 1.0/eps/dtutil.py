import datetime
from datetime import date, timedelta
import time
import indigo
import eps

# Various date/time (or datetime) utilities


#
# Print library version - added optional return in 1.1.1
#
def libVersion (returnval = False):
	ver = "1.2.2"
	if returnval: return ver
	
	indigo.server.log ("##### EPS UI %s #####" % ver)

#
# Format total seconds into a HH:MM:SS type format
#
def secondsToClock (value, format = "HH:MM:SS"):
	if int(value) < 0:
		indigo.server.log("secondsToClock value must be greater than zero", isError=True)
		return "00:00"
		
	format = str(format).lower()
	s = timedelta(seconds=int(value))
	
	d = datetime.datetime(1,1,1) + s
	
	ld = d.day
	lh = d.hour
	lm = d.minute
	ls = d.second
	
	if format == "hh:mm:ss": return "%02d:%02d:%02d" % (lh, lm, ls)
	if format == "hh:mm": return "%02d:%02d" % (lh, lm)
	if format == "mm:ss": 
		if lh > 0: lm = lm + (lh * 60)
		if lm > 99: return "%002dM" % lm
		return "%02d:%02d" % (lm, ls)
	
	if format == "relative":
		if ld > 1: return "+%02dD" % ld
		if lh > 1: return "+%02dH" % lh
		if lm > 1: return "+%02dM" % lm
		if ls > 1: return "+%02dS" % ls
		
	if format == "relative-hour":
		if ld > 1: return "+%02dD" % ld
		if lh > 1: return "+%02dH" % lh
		return "%02d:%02d" % (lm, ls)
	
	return "00:00:00" # failsafe

#
# Like .NET datediff, takes days, house, minutes or seconds as t
# If dates are sent as string they must be Y-m-d H:M:S
# If d1 is earlier than d2 then a negative is returned, else a postitive is returned
#
def DateDiff (t, d1, d2):
	try:
		if type(d1) is str:
			if d1 == "":
				d1 = "2000-01-01 00:00:00"
			d1 = datetime.datetime.strptime(d1, "%Y-%m-%d %H:%M:%S") 
		if type(d2) is str:
			if d2 == "":
				d2 = "2000-01-01 00:00:00"
			d2 = datetime.datetime.strptime(d2, "%Y-%m-%d %H:%M:%S") 

	except:
		log ("DateDiff ERROR: Got an error converting strings to datetimes, make sure they are in the format of Y-m-d H:M:S!")
		raise
		return

	try:
		sum = time.mktime(d1.timetuple()) - time.mktime(d2.timetuple())
		if sum == 0:
			return 0

		if t.lower() == "days":
			ret = sum / 86400

		if t.lower() == "hours":
			ret = (sum / 86400) * 24

		if t.lower() == "minutes":
			ret = ((sum / 86400) * 24) * 60

		if t.lower() == "seconds":
			ret = (((sum / 86400) * 24) * 60) * 60

		return ret
	
	except:
		log ("DateDiff ERROR: Got an error converting to " + t)
		raise
		return

#
# Like .NET dateadd, takes days, house, minutes or seconds as t
# If dates are sent as string they must be Y-m-d H:M:S
#		
def DateAdd (t, n, d):
	try:
		if type(d) is str:
			if d == "":
				d = "2000-01-01 00:00:00"
			d = datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S") 
		
	except:
		log ("DateDiff ERROR: Got an error converting strings to datetimes, make sure they are in the format of Y-m-d H:M:S!")
		raise
		return
	
	if n > -1:
		if t.lower() == "days":
			ret = d + datetime.timedelta(0,float( ((n * 60) * 60) * 24 ))

		if t.lower() == "hours":
			ret = d + datetime.timedelta(0,float( (n * 60) * 60 ))

		if t.lower() == "minutes":
			ret = d + datetime.timedelta(0,float(n * 60))
			
		if t.lower() == "seconds":
			ret = d + datetime.timedelta(0,float(n))
	else:
		n = n * -1
		
		if t.lower() == "days": ret = d - timedelta(days=n)
		if t.lower() == "hours": ret = d - timedelta(hours=n)
		if t.lower() == "minutes": ret = d - timedelta(minutes=n)
		if t.lower() == "seconds": ret = d - timedelta(seconds=n)
				
	return ret
	
	
#
# Convert seconds to HH:MM:SS/MM:SS - 1.1.1
#
def SecondsToDurationString (n, format = "HH:MM:SS"):
	n = int(n)
	if n == 0: 
		if format == "HH:MM:SS": return "00:00:00"
		if format == "MM:SS": return "00:00"
	
	s = timedelta(seconds=n)
	d = datetime.datetime(1,1,1) + s

	if format == "HH:MM:SS": return "%02d:%02d:%02d" % (d.hour, d.minute, d.second)
	if format == "MM:SS": return "%02d:%02d" % (d.minute, d.second)

	return "00:00"


#
# Convert string date/time from one format to another
#
def DateStringFormat (value, oldFormat, newFormat):
	try:
		oldDate = datetime.datetime.strptime (value, oldFormat)
		return oldDate.strftime (newFormat)
	
	except Exception as e:
			eps.printException(e)


















