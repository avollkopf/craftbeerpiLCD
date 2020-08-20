![](https://img.shields.io/badge/CBPi%203%20addin-functionable-green.svg)  ![](https://img.shields.io/github/license/JamFfm/craftbeerpiLCD.svg?style=flat) ![](https://img.shields.io/github/last-commit/JamFfm/craftbeerpiLCD.svg?style=flat) ![](https://img.shields.io/github/release-pre/JamFfm/craftbeerpiLCD.svg?style=flat)

# **LCD add-on for CraftBeerPi 3**

![](https://github.com/breiti78/craftbeerpiLCD/blob/master/LCDPhoto.jpg "LCDDisplay Default Display")

With this add-on you can display your Brewing steps temperatures on a 20x4 i2c LCD Display.
In addition you can display the target-temperatur and current-temperature of each fermenter.
This addon only works with I2C connected LCD Displays.

## Installation

**Wiring:**

Display|       PI
-------|--------------------
SDA    |  Pin 3 GPIO02(SDA1)
SCL    |  Pin 5 GPIO03(SDL1)
VCC    |  Pin 2 Power 5V
GND    |  Pin 6 GND

**I2C Configuration:**

Ensure to activate the E2C connection in Raspi configuration.

**Software installation:**

Download and install this plugin via the CraftBeerPi user interface. It is called LCDDisplay.

After that a reboot is necessary.

## Configuration

Update 2020-08-20
- Reverted some changes for python3 back as they were not required for python3 compatibility
- Version is now running under python2 and python3 based craftbeerpi3
- Another bugfix with respect to the gravity function

Update 2020-08-16
- Added support for hop addition countdown timers
- Boil step name has to be set to 'Boil'
- hop steps of the step have to be named hop_1 ... hop_5 which is standard for the default Boilstep
- 5 hop steps are currently possible

Update 2020-08-12
- Python 3 support
- Support for iSpindle Gravity data
- iSpindle Gravity sensor type needs to be configured and used as sensor2
- LCD disply will display current gravity in line 4 of LCD display
- It may take some time to display gravity vlaue until next reading from spindle is available

At least configure your i2c address in the parameters menu. Some other
parameters of the LCD can be changed in the 

    __init__.py

file in the /home/pi/craftbeerpi3/modules/plugins/LCDDisplay folder.


There are different modes:

**Default display**
--------------

If no brewing process is running the LCD Display will show

- CraftBeerPi-Version 
- Brewery-name
- Current IP adress 
- Current date/time

**Multidisplay mode**
-----------------

- The script will loop thou your kettles and display the target and current temperature. 
- If heater is on, a beerglas symbol will appear in the first row on the right side (not flashing).
- When target-temperature is reached it displays the remaining time of the step (rest) too.

**Single mode**
-----------

- Only displays one kettle but reacts a little bit faster on temperature changes. 
- It displays the remaining time of the step (rest) when target temperature is reached.
- When the heater is "on" a small beerglas is flashing on/off in the first row on the right side.

**Fermenter mode**
--------------
- Pretty much the same as multidisplay for all fermenter.
- Displays the brew-name, fermenter-name, target-temperature, current-temperature of each fermenter.
- If the heater or cooler of the fermenter is on it will show a symbol.
A beerglas detects heater is on, * means cooler in on.
- The remaining time for each fermenter is shown like in weeks, days, hours. 
- Fermenter mode starts when a fermenter-step of any of the fermenter is starting and no brewing step is running(most likely)

Parameter
---------

There are several parameter to change in the **CBPi-parameter** menu:


**LCD_Address:**    
This is the address of the LCD modul. You can detect it by 
using the following command in the commandbox of the Raspi:   
- sudo i2cdetect -y 1 
or 
- sudo i2cdetect -y 0.
Default is 0x27.


**LCD_Charactermap:**     
Changes value between A00 and A02. This is a character map build in by factory into the LCD. 
Most likely you get a LCD with A00 when you by it in China. A00 has got most of the European letters and a lot 
of Asia letters. For germans the ÄÖÜß is missing in A00. In A02 there are more European letters incl. ÄÖÜß.
Therefore the addon distinguish between the charmaps. 
In case A00 it substitutes ÄÜÖß with custom made symbols which represent these letters.
In case A02 the addon skips substitution. If you notice strange letters try to change this parameter.
Default is "A00".

 
**LCD_Multidisplay:**     
Changes between the 2 modes. "on" means the Multi-display mode is on. 
"off" means single-display mode is on. Default is "on". 


**LCD_Refresh:**		  
In Multidisplay mode this is the time to wait until switching to next displayed kettle. 
Default is 3 sec.
 

**LCD_Singledisplay:** 	  
Here you can change the kettle to be displayed in single mode. The number is the same as row number  of
kettles starting with 1. Default is kettle 1 (probably the first kettle which was defined in hardware).


## Hints

- Changing a LCD_xxxx parameter in the parameters menue or any
file in LCDDisplay folder usually requires a reboot.
- Whether you need a reboot have a look in the comments of the parameters.
- A new fermenter should have a target temperature and at least one step defined.
- It maybe necessary to restart craftbeerpi after adding a new fermenter. 

- If the LCD address (eg. 0x27) is right but you still can not see letters displayed:
  - try to adjust contrast by the screw on the back of the LCD Hardware (I2C Modul)
  - be shure to provide the LCD hardware with the right ammount of voltage (mostly 5V or 3.3V)
  - use a strong powersuppy. If you notice LCD fading a bit there is a lack of current.
  - use proper connections. Soldering the wires is best for connection. Bad connection can also result in fading the LCD.


## Known Problems
The LCD hardware does not like temperature below 0°C (32°F). 
It becomes slow and can be damaged like brightness is no more homogen throughout the hole LCD area.

Does not work with stretch: if you start a step LCD will stop running.


## Questions  
Questions can be posed in the Craftbeerpi user group in Facebook or in the repository.


## Fixed Issues
- Now the °C or F is displaed like in CBPi parameters
- If there is a missing Kettle or Fermenter no more faults are thrown.
- Sometimes it lastes a long time till the fermenterstep starts running. 
- When CBPi3 Mesh Steps are active and you restart CBPi3 the display will show nothing. 
It will at least show the startscreen. Stop and restart the Mesh steps is still nessesary tho show active step.
- Not displaying ÄÜÖß
