## pypresenter 
* * *
A minimalistic approach to building a cross-platform tool to use a spotlight and laser pointer tool for presentations.

This project was born primarily to add the virtual laser and spotlight features to the Norwii N97s presenter on Linux, and extended to have the same behavior on MacOS without having to install or use the official Norwii presenter software.

## Norwii N97s presenter
The Norwii 97s functions as an air mouse when you hold the spotlight button, so the only thing needed is to intercept any buttons pressed on the Norwii. Those buttons could maybe be reprogrammed using the Norwii presenter software, but here we will use the default settings. 

* Pressing the spotlight button sends Ctrl+L, releasing it sends Ctrl+A
* Pressing the erase button sends 'e'
* Pressing the annotate button sends Ctrl+P (and a mouse click?), releasing it sends Ctrl+A
* Double clicking the spotlight button changes the spotlight mode of the presenter; try to change the spotlight mode if the presenter does not function as an air mouse while the spotlight button is pressed.

pypresenter uses the spotlight button to enable/disable the on screen indicator (virtual laser or spotlight). The erase button is used to switch between virtual laser and spotlight mode.

Of course the virtual laser function is not really needed for most presentation software (microsoft powerpoint, google slides), because  those applications supply their own virtual laser which works fine with Norwii 97s in air mouse mode. However, it is still useful when sharing screen etc. 

Because of the minimalistic approach, it is not possible to fully consume the button presses of the Norwii 97s presenter, meaning that the active application on the screen will also receive the button presses (that is why pypresenter does not use the annotate button). This can be solved with some lowlevel io stuff, but that's outside the scope of the project right now. The upside of this is that pypresenter can also be used without the Norwii presenter, just using the normal keyboard to send the button press codes and using the normal mouse to move the virtual laser or spotlight.

## Status
Almost perfect for norwii on linux (and using google slides).
Fine for macos, but can create a spotlight ghost in specific situations (but always removed in next trigger).

**Known Issues**
* Pressing a button on the presenter is also passed to the application active on the screen. To make it work would require systemlevel changes that break the simplistic approach of this tool.
* On MacOS pypresenter needs permission for "Input event monitoring". This must be set manually in Settings->Privacy & Security->Input Monitoring. If pypresenter is started from the command line, the Terminal will need that permission.
* On MacOS when pypresenter is installed from the provide zip package, it will probably complain that the app is damaged because it is not a commercially signed package. To fix it, either manually clear the warning from the command line, or run the python version.
 

## Requirements
For Linux and MacOS:
* PySide6
* pynput

Additionally for MacOS:
* pyobjc

## Usage
```
python ./pypresenter.py
```

A config file will be created in $HOME/.config/config.ini at the first run. It contains some options that can be used to change the presenter look and feel. The default is:

```
[General]
modes = SPOTLIGHT_HOLD, LASER, SPOTLIGHT_TOGGLE

[Spotlight]
spot_radius = 150.0
background_alpha = 220
ring_thickness = 0.05
ring_color_rgba = 255, 105, 180, 255

[Laser]
max_trail_length = 15
base_radius = 7.0
head_multiplier = 1.5
color_rgba = 255, 0, 0, 255
min_alpha = 25
```

**modes**
These are the modes the mode switch cycles through.
* SPOTLIGHT_HOLD: turns spotlight on and off on Norwii spotlight button press and release
* LASER: turns virtual laser on and off on on Norwii spotlight button press and release
* SPOTLIGHT_TOGGLE: turns spotlight on on Norwii spotlight button press and leaves it on until the button is pressed again (disabled by default)

**Spotlight**
* spot_radius: radius of the spotlight in pixels
* ring_thickness: thickness of the ring around the spotlight as fraction of the spot_radius
* background_alpha: controls how dark the area outside the spotlight will be; 255 = totally black, 0 = totally transparent
* ring_color_rgba: color of the ring in four number between 0 and 255 denoting the red, green, blue and alpha channels
 
 **Laser**
 * max_trail_length:  number of previous lasers positions to draw as a laser trail
 * base_radius: radius of a laser dot in pixels
 * head_multiplier: increase the radius of the head of the trail with this factor
 * color_rgba: color of the laser dot in four number between 0 and 255 denoting the red, green, blue and alpha channels
 * min_alpha: transparancy value of the oldest spot
 