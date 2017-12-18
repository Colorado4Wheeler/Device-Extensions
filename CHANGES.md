Release Notes
==========

Version 2.0
---------------

* Official Indigo 7 release
* Updated core libraries to fix issues with Prowl Indigo plugin


Version 1.61 (Version 2.0 Beta 2)
---------------

* Fixed a typo where low temps were not being calculated correctly on Weather devices

Version 1.6 (Version 2.0 Beta 1)
---------------

* Plugin, templates and libraries are now using the Indigo 7 libraries
* Conversion Extension devices upgraded to new structure and calls
* Conversion Extension states no longer show the raw state names and instead now show the actual proper state names
* Changed Conversion Extension to allow selecting not only a state but also a device property to key in on
* Added the power on/power off icon for Conversion Extensions resulting in a boolean value to better reflect what Indigo devices show when they are based on a true/false state in regards to a device
* Any Conversion Extension that generates an error will now show 'Error' in the state of the device
* Changed the preset timeout countdown routines to be date/time based
* Using presets on Thermostat Extensions will now log the preset being activated, when it will expire and when it actually does expire
* All of the state updates are now done in single calls rather than individually, reducing the footprint of the plugin
* Using the 'lastChanged' special state is no longer valid, all devices using that special state name upgrades to use the property name instead
* No longer allowing .UI states in non conversion devices, the user will get an upgrade warning/error if they are using these
* Extension Device addresses now reflect the device they are extending
* Improved rain detection routines for Weather Extension and Irrigation Extension
* Removed Irrigation Extension pause and resume actions since the tighter integration with sprinkler devices makes the redundant given that you can pause and resume the sprinkler itself and the extension handles it properly
* Moved all actions to their proper Device sub-menu rather than having them all piled up in the root of the actions menu
* Removed "Update From Device" action since all device updates are dynamic enough that it is no longer needed
* Removed "Reset daily highs and lows" action since there really is no need to reset it manually
* Added ability to use irrigation zones like devices by issuing on/off/dim commands where dim is the percentage of max duration, this to add support to Homebridge Buddy but also to use in scripting if desired


Development Notes
==========


Known Issues As Of The Most Current Release (Leftover from Legacy 1.x version, may no longer apply)
---------------

* For converting a state to boolean the type of boolean field shows up, which is a bug but also makes sense, so incorporate that into the results
* Need to convert thermostat devices to use date/time routines for preset countdowns when upgrading (we now use presetExpires for calculation and use presetTimeout as a minute countdown in case they want to use that on control pages)
* Low temperature not working, it always uses the current temperature
* Changing zones doesn't update the zone timer on the device list
* Errors reported by DC: http://forums.indigodomo.com/viewtopic.php?f=197&t=17294&p=130810#p130810
* Errors reported by gbreeze (see PM)

Wish List
---------------

* Replace "Use device when checked, variable when unchecked" (reference 'chdevice' in plugin code) with a combobox and write into device upgrade to convert all devices to use it
* For static true/false on conversions get rid of the need to have a device and state chosen and change the updates to act accordingly since state updates are not only no longer needed but will skip this device since it has no active state or device
* Add ability to read responses from a web device to get status on URL Extension
* Add ability to run an action group on Elapsed Minutes Conversion Extension if the elapsed minutes surpasses a set number of minutes
* Allow using any kind of device as an Irrigation Extension device, even if it's not an Indigo.Sprinkler
* Actions to do on-the-fly conversions without the need to create a device
* Add an "Average" conversion so you can take the same states of up to 5 devices and get the average value - this will know if it's one of our converted extensions and actaccordingly.  Must be a number or boolean mostly.
* Add ability to auto-pause for X seconds then auto-resume on Irrigation Extensions, each successive press of the button will increase the pause time by X more seconds, a manual resume will clear the timer
* Improve threading in extensions that have timers or countdowns so that the Indigo device list shows the timer in exact seconds instead of skipping around as it does because concurrentThreading is not precisely one second
* Add placeholders so that the form size remains the same (the largest forms size is state to boolean)
* Add conditions like operators to give much more flexibility to state to boolean so it doesn't have to equal something, it can also contain, greater than, etc
* Presets for Irrigation Extensions
* Option for Irrigation Extension to, when togging a zone on, use the saved duration, a new quick saved duration or the default duration
* Ability to "quick-pause" a schedule for X minutes where X is defined in the action configUI
* On URL extensions add ability to use a variable or state for on/off state as well ability to read HTML, JSON or XML data returned by the calls
