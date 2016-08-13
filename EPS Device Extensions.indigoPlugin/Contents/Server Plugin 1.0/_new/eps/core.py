import indigo
import datetime
import time

# EPS core Indigo shortcuts

def log (t):
	indigo.server.log (t)
	
#
# Indigo server time stamp converted to exclude microseconds
#
def Now ():
	d = indigo.server.getTime()
	d = d.strftime("%Y-%m-%d %H:%M:%S")
	return datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S") 	