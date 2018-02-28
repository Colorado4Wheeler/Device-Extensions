Release Notes
==========

Version 2.0.5: 2.1.0 preview (includes releases 2.0.4 forward as they were 2.1.0 previews)
---------------
* [ALL CONVERSIONS NOW AVAILABLE AS ACTIONS AS WELL AS DEVICES](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Actions#conversion-action)!  You can also output the result to a variable, the console log or to your speakers via text to speech
* Added new device [Virtual Color/Ambiant Hue Device Group](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Extension:-Color-Hue-Group) that allows you to group together Hue bulbs so you can control them in tandem, including changing colors
* Added new device [Relay To Dimmer Conversion](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Relay-to-Dimmer-Conversion) that allows you to mimic dimmer commands (i.e., brightness) on a relay device by calibrating the On/Off times to a full cycle to give you percentages of "On".  This was created as a result of my own need to have my curtains (which are on/off cycle) to work with HomeKit and be able to open to a certain percentage even though my curtains don't support that - now they do!
* Added new device [Filter Sensor](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Filter-Sensor), mostly a direct need for HomeKit that allows you to have a filter sensor come on when it's time to change a filter.  Can be based on days/weeks/months or the run time of your HVAC if you want to use it for your furnace filter
* Added new [action to direct speech to a specific Airfoil speaker](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Actions#extended-speech) or the system audio and then disconnect from the speaker (if using Airfoil), with the ability to inject variables or device states dynamically into the spoken phrase
* Added all remaining values and functions to the Thermostat Wrapper.  As of now you can only use device states for values and action groups for functions but if there is a call to do more in the future this may be added
* Added API hooks into HomeKit Bridge
* Added HomeKit Bridge integration into the recently created Thermostat Wrapper, thus beginning the process of migrating all Wrapper and Alias devices from Homebridge Buddy to this and other 3rd party applications instead
* Added ability to execute an action group on Time to Elapsed Minutes conversions if the elapsed minutes exceeds the provided threshold
* Added real-time updates for Conversion Extensions when using Convert Date/Time to Elapsed Minutes, meaning that the system will update these every 60 seconds from their source since in both of these cases the source data may not change but our status needs to.  Note that this will add a slight increase to the CPU usage, but probably not more than 0.1% to 0.3% depending on how many of these conversions you are doing
* Added plugin configuration for device address updates so that now a Conversion Extension can show the type of conversion it is doing in the address or than the device or variable it is doing it on (all previous versions did the latter)
* Changed the order of devices in the XML so they appear in a more logical order when selecting a device model
* Fixed bug where conversions on variables may not work, now all variable conversions work properly
* Changed the About URL in the plugin menu to point to the Git Wiki pages instead of the Indigo forums
* Removed Support Data Dump, Comprehensive Data Dump and Check for Updates from the plugin menu and added the Advanced Plugin Actions in its place to clean up the menu and to remove the version checker made obsolete by the Plugin Store
* Fixed upgrade issue where it would always indicate on plugin startup that it was upgrading from version 1.53, it will now only do that the first time and then go away
* Cleaned up user interface for Conversion Extensions
* Cleaned up user interface for the action menu and moved all device specific actions under devices
* Removed Conversion Extension checkbox to indicate the conversion is for a device or variable and made it a combobox so that other conversions can be easily integrated (i.e., action groups, schedules, etc)
* Changed logic so that if you choose Always True or Always False as a conversion method that the type will change to static and you will no longer see a device, variable or state
* Always True and Always False conversion devices will now always have an address of Static Value of True or Static Value of False in the UI
* Added utf8 encoding translations to some core library functions that reference name, particularly the ones that may reference a non-plugin object for thread debugging since certain latin characters over 128 may cause errors and it is confusing if it doesn't come from a D/E device

Version 2.0.4 (Interim Release)
---------------

* Added new Thermostat Wrapper device to allow you to either wrap an existing thermostat and re-assign select fields and functions or to create a thermostat from device states, variables and action groups (created as an option to use with voice control such as Homebridge Buddy)
* Improved idle performance by 100%: CPU performance at idle now at 50% of previous after moving extraneous concurrent threading calls into a conditional variable instead.  Before the fix the idle CPU usage of the plugin was between 0.6% and 0.8% and now is between 0.3% and 0.4%
* Added global variables for thermostat preset expiration times and high/low reset times to take them out of concurrent threading where it was checking all devices of that type every thread occurrence
* Fixed issue in the concurrent thread that could cause an error if a device of a certain type had not been created by the user

Version 2.0.3
---------------

* Added new field to the conversion for Lux to Word Value called Adjustment, this value will change the word value based on the upper limit of your light sensor.  For example, the Fibaro motion sensor only detects up to 32,767 lux (normally lux is detected up to 100,001), so entering .32767 in this adjustment field will change the calculation to be more accurate based on the equipment reporting the value.
* Added lux adjustment according to the value of the new lux Adjustment field, a value of 1 indicates that the sensor can go to the full 100,001 lux (direct sunlight)
* Fixed a bug when starting a device or editing a device that did not check if a referenced device ID was valid before trying to load the device, resulting in an error.  Now it will check beforehand and log an error to let the user know that there is an invalid Indigo device being referenced by a plugin device

Version 2.0.2
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

* Add ability to read responses from a web device to get status on URL Extension
* Allow using any kind of device as an Irrigation Extension device, even if it's not an Indigo.Sprinkler
* Add an "Average" conversion so you can take the same states of up to 5 devices and get the average value - this will know if it's one of our converted extensions and actaccordingly.  Must be a number or boolean mostly.
* Add ability to auto-pause for X seconds then auto-resume on Irrigation Extensions, each successive press of the button will increase the pause time by X more seconds, a manual resume will clear the timer
* Improve threading in extensions that have timers or countdowns so that the Indigo device list shows the timer in exact seconds instead of skipping around as it does because concurrentThreading is not precisely one second
* Add conditions like operators to give much more flexibility to state to boolean so it doesn't have to equal something, it can also contain, greater than, etc
* Presets for Irrigation Extensions
* Option for Irrigation Extension to, when togging a zone on, use the saved duration, a new quick saved duration or the default duration
* Ability to "quick-pause" a schedule for X minutes where X is defined in the action configUI
* On URL extensions add ability to use a variable or state for on/off state as well ability to read HTML, JSON or XML data returned by the calls
