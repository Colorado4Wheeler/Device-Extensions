# Device Extensions Overview
Device Extensions is a plugin for the [Indigo](http://indigodomo.com) home automation platform for Mac.  Originally it was designed as a way to enhance [control pages](http://wiki.indigodomo.com/doku.php?id=indigo_7_documentation:overview#control_pages) by converting or otherwise manipulating the values of other device states, properties or configuration to represent a value more useful for your control page, although many people use the plugin for its ability to convert data in a number of ways rather than just for the sake of control pages.

Most notably Device Extensions performs the following functions:

* Read a variable, device state, device attribute or device property and convert the data to another format
* Represent an alternative device state in the Indigo user interface
* Wrap devices in order to manipulate some or all of the standard device functions or data
* Wrap and Alias devices to work with voice controlled home automation systems such as HomeKit (via [Homebridge Buddy](http://www.indigodomo.com/pluginstore/31/)), Amazon Echo (via [Alexa Hue Bridge](http://www.indigodomo.com/pluginstore/13/)) or Google Assistant (TBD).

The plugin works by creating a device and then referencing other devices, variables and action groups from the configuration options and selecting the operation that you need it to perform, thus creating a new device with a new device state and new device functions - thereby extending the original referenced device.

## Thermostat Wrapper (Available in 2.1.0 or earlier)

Instead of extending a device, this allows you to wrap a device and completely change how it works or simply create a one-off device not attached to any other thermostat device for your voice controlled automation.  It will work with any built-in or third party thermostat device and gives you the ability to:

* Optionally wrap another thermostat so that any functions not specifically overridden will pass through to the referenced thermostat
* Override the temperature value from any device state, device property or device attribute as well as any variable value so long as the value is a number
* Override the humidity value from any device state, device property or device attribute as well as any variable value so long as the value is a number
* Allow Indigo to specify the device icon or select from any Indigo device icon you wish to use in the UI

### Voice Controlled Home Automation (i.e., Siri or Alexa)

This device will detect if you have a valid voice controlled HA system and enable you to attach to supported systems.  Currently you can only attach to Homebridge Buddy for HomeKit.

## Conversion Extension
The following conversions can be performed by Device Extensions by referencing a variable or a device state, property or configuration and then performing one of the following conversions:

* [Fahrenheit to Celsius and Celsius to Fahrenheit](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#temperature-conversions-celsius-to-fahrenheit-or-fahrenheit-to-celsius)
* [Device State to Boolean Value](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#device-state-or-variable-to-boolean)
* [LUX Value to Human Readable Word](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-a-lux-value-to-a-word)
* [Date and Time to Elapsed Minutes](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-a-date-and-time-value-to-elapsed-minutes)
* [Boolean Value to String](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-a-boolean-to-a-string)
* [Boolean Type to Boolean Type](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-between-boolean-types)
* [Value Is Always True or Always False](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#device-that-is-always-is-true-or-always-is-false)
* [Value to String With Ability To Trim String](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-to-string-and-optionally-trim-result)
* [Date and Time Reformatting (from any Python format to any Python format)](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-between-date-formats)
* [Strings to Numbers](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-string-to-a-number)
* [Strings to Cased Strings (mixed, proper, lower, upper)](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion-Devices#convert-string-to-cased-string)

### Boolean Type Conversions
Because of the [variety of ways that Indigo can represent a boolean value](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Conversion:-Boolean-Types#indigo-device-boolean-wording-variations), the following conversions can be made:

* True/False
* Yes/No
* Open/Closed
* 1/0
* Ready/Not Ready
* Available/Not Available
* On/Off
* Good/Bad
* Locked/Unlocked

## Weather Extension

Use the [Weather Extension](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Extension:-Weather) to convert the value of any device state, attribute or property - including all weather plugin devices - to track and represent the following:

* Daily High Temperature
* Daily Low Temperature
* Daily High Humidity
* Daily Low Humidity
* Is It Raining?

### Device State For UI
Once created you can have the Indigo device list represent any of the following as the device state:

* Current Temperature in F or C
* Current Humidity
* High Temperature
* Low Temperature
* High Humidity
* Low Humidity

## Thermostat Extension

Using any valid Indigo thermostat device, either native or from a plugin, the following new abilities are provided to you when using the [Thermostat Extension](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Extension:-Thermostat):

* Represent temperature in F or C regardless of the "Parent" thermostat
* Have up to four presets that can be called to set the heat point, cool point, HVAC mode and fan
* Change the increment/decrement of heat or cool points from the default of 1 to any amount, giving you the ability to have, say, a control page change the temperature by X degrees on each tap instead of 1
* Auto preset time out allowing you to use a preset and have it return to where it started at the end of the time out
* Means to toggle the HVAC mode on and off with a single action in a control page

### Device State For UI
Once created you can have the Indigo device list represent any of the following as the device state:

* Current Temperature in F or C
* Current Humidity
* High Temperature
* Low Temperature
* High Humidity
* Low Humidity
* Preset Number
* Current Setpoint
* Cool Setpoint
* Heat Setpoint
* Operation Mode (heat/cool)

## Irrigation Controller Extension

Using any valid Indigo irrigation controller device, either native or from a plugin, the following new abilities are provided to you when using the [Irrigation Extension](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Extension:-Irrigation):

* Automatic rain control (turn off when rain is detected) using any Indigo device, including all weather devices, with the ability to either stop the running schedule or pause it until the selected device no longer reports a rain condition
* Automatically resume a paused schedule and pick up right where it left off

### Device State For UI
Once created you can have the Indigo device list represent any of the following as the device state:

* Zone run time remaining as HH:MM:SS, HH:MM, MM:SS, MM or :SS
* All zone times remaining, aka the time remaining for the full schedule
* Current running zone name
* If the schedule is paused

## URL Extension

The [URL Extension](https://github.com/Colorado4Wheeler/Device-Extensions/wiki/Extension:-URL) allows you to treat a URL as an on/off device in Indigo by allowing you to:

* Use a URL for an ON command
* Use a URL for an OFF command
* Use a URL for a TOGGLE command
* Force off a device if the ability to auto detect it's on state isn't possible