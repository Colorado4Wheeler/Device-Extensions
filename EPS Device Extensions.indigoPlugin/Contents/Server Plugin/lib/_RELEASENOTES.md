Release Notes
==========

Until 2.3.1 these changes were pseudo logged elsewhere, this represents the official library release notes since then.

Version 2.4.2
---------------

* Fixed a bug in cache _autoCacheFields and addWatchedStates as well as ui _getStatesForDevice and _getActionsForDevice that did not check if a device ID was valid before trying to load the device, resulting in an error.  Now it will check beforehand and log an error to let the user know that there is an invalid Indigo device being referenced by a plugin device

Version 2.4.1
---------------

* Fixed minor issue with duplicating a preset list item where duplicating in rapid succession would create duplicate keys and, thus, cause two devices to share the same key and the entire list to act wonky by adding microseconds to the time variant of the key
* Fixed bug with validateActionConfigUi in plug where a returned error dict wouldn't pop an error
* ActionsV2 was trying to perform actions on devices without validating that the devices were valid, fixed runAction and getActionOptionUIList to check before attempting to fire
* UI was trying to perform actions on devices without validating that the devices were valid, fixed XXX to check before attempting to fire

Version 2.4.0
---------------

* Added a rewrite of the actions library that allows for faster development of new plugins based on actions called actionsv2
* Added actionoptionlist_v2 to ui for new action library
* Added actionsv2 loader to eps
* Added setUIDefaults callback to formFieldChanged in plug
* Found bug in actions getActionOptionUIList where the continue on listIdx in the loop was actually skipping all fields except for the first, added an argument to _getActionOptionUIList to pass the group number and then for that function to process only the field for that group number if it matched the newly required optionFieldId field in the form.  This removed the need to do passes on the loop and instead just return the options for the specific and proper field instead
* Added ability in actions to perform one-off list functions for plugins that would otherwise be rejected for having a "self" list (i.e., added SecuritySpy plugin)
* Added new getJSONDictForKey function in the Ext library for decoding JSON lists since all of our JSON lists will have a key value and will a dict wrapped into JSON
* Added advPluginDeviceSelected in plug for the v3.3.0 plugin version

Version 2.3.2
---------------

* If a 3rd party plugin action called by our plugin caused an exception the message was ambiguous as to what the other plugin is, added the plugin display name to the actionReturnedValue arguments in devices and changed the reference calls in actions to pass the name (appear in Homebridge Buddy, distributed with 1.0.7)

Version 2.3.1
---------------

* Changed a devices divide by zero exception by checking for a zero/null condition before trying to calculate runtime percentage in runConcurrentThread (found in Homebridge Buddy, distributed change with 1.0.6)
