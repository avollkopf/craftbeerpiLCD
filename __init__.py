#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import socket
import fcntl
import struct
import warnings
import datetime
import threading
from time import gmtime, strftime
from modules import app, cbpi
from .i2c import CharLCD

# LCDVERSION = '4.0.00' The LCD-library and LCD-driver are taken from RPLCD Project version 1.0. The documentation:
# http://rplcd.readthedocs.io/en/stable/ very good and readable. Git is here: https://github.com/dbrgn/RPLCD.
# LCD_Address should be something like 0x27, 0x3f etc.
# See parameters in Craftbeerpi3.
# To determine address of LCD use command prompt in Raspi:
# sudo i2cdetect -y 1 or sudo i2cdetect -y 0
# Assembled by JamFfm
# 17.02.2018 add feature to change Multidisplay <-> Singledisplay without CBPI reboot
# 17.02.2018 add feature to change Kettle Id for Singledisplay without CBPI reboot
# 17.02.2018 add feature to change refresh rate for Multidisplay without CBPI reboot
# 17.02.2018 add feature to change refresh rate for Multidisplay in parameters with choose of value from 1-6s
# because more than 6s is too much delay in switching actors
# 18.02.2018 improve stability (no value of a temp sensor)
# 13.03.2018 display F or C depending on what is selected in parameters-unit
# 10.02.2020 Python 3 migration ready
# 12.03.2020 show start screen instead of blank screen after reboot and active step
# 12.03.2020 skip delays in Multi mode brewing
# 12.03.2020 selection of single-mode kettle id improved 15.03.2020 fixed blinking beerglass in single mode
# 15.03.2020 skip delays in  fermentation Multi mode
# 20.03.2020 added ÄÖÜß for A00 Charactermap, Charactermap is
# selectable in Parameter [A00, A02]. The Character maps are implemented into the LCD by factory. Changed cooling symbol

DEBUG = False  # turn True to show more debug info
BLINK = False  # start value for blinking the beerglass during heating only for single mode
# beerglass symbol
bierkrug = (
    0b11100,
    0b00000,
    0b11100,
    0b11111,
    0b11101,
    0b11101,
    0b11111,
    0b11100
)
# cooler symbol should look like icecubes
cool = (
    0b00100,
    0b10101,
    0b01110,
    0b11111,
    0b01110,
    0b10101,
    0b00100,
    0b00000
)
# Ä symbol because in A00 LCD there is no big Ä only small ä- If you use A02 LCD this is not necessary.
awithdots = (
    0b10001,
    0b01110,
    0b10001,
    0b10001,
    0b11111,
    0b10001,
    0b10001,
    0b00000
)
# Ö symbol because in A00 LCD there is no big Ö only small ö- If you use A02 LCD this is not necessary.
owithdots = (
    0b10001,
    0b01110,
    0b10001,
    0b10001,
    0b10001,
    0b10001,
    0b01110,
    0b00000
)
# Ü symbol because in A00 LCD there is no big Ü only small ü- If you use A02 LCD this is not necessary.
uwithdots = (
    0b01010,
    0b10001,
    0b10001,
    0b10001,
    0b10001,
    0b10001,
    0b01110,
    0b00000
)
# ß symbol because in A00 LCD there is no ß If you use A02 LCD this is not necessary.
esszett = (
    0b00000,
    0b00000,
    0b11100,
    0b10010,
    0b10100,
    0b10010,
    0b11100,
    0b10000
)


def lcd(LCDaddress, characters):
    try:
        lcd = CharLCD(i2c_expander='PCF8574', address=LCDaddress, port=1, cols=20, rows=4, dotsize=8,
                      charmap=characters,
                      auto_linebreaks=True, backlight_enabled=True)
        return lcd
    except:
        pass


def set_lcd_address():
    adr = cbpi.get_config_parameter('LCD_Address', None)
    if adr is None:
        cbpi.add_config_parameter('LCD_Address', '0x27', 'string', 'Address of the LCD, CBPi reboot required')
        adr = cbpi.get_config_parameter('LCD_Address', None)
        cbpi.app.logger.info("LCDDisplay  - set_lcd_address added: %s" % adr)
    return adr


def set_charmap():
    charmap = cbpi.get_config_parameter('LCD_Charactermap', None)
    if charmap is None:
        cbpi.add_config_parameter('LCD_Charactermap', 'A00', 'select',
                                  'if characters look strange try to change this parameter. CBPi reboot required '
                                  , ['A00', 'A02'])
        charmap = cbpi.get_config_parameter('LCD_Charactermap', None)
        cbpi.app.logger.info("LCDDisplay  - LCD_Charactermap added: %s" % charmap)
    return charmap


def set_parameter_refresh():
    ref = cbpi.get_config_parameter('LCD_Refresh', None)
    if ref is None:
        cbpi.add_config_parameter('LCD_Refresh', 3, 'select',
                                  'Time to remain till next display in sec, NO! CBPi reboot '
                                  'required', [1, 2, 3, 4, 5, 6])
        ref = cbpi.get_config_parameter('LCD_Refresh', None)
        cbpi.app.logger.info("LCDDisplay  - set_parameter_refresh added: %s" % ref)
    return ref


def set_parameter_multidisplay():
    multi = cbpi.get_config_parameter('LCD_Multidisplay', None)
    if multi is None:
        cbpi.add_config_parameter('LCD_Multidisplay', 'on', 'select', 'Toggle between all Kettles or show only one '
                                                                      'Kette constantly, NO! CBPi reboot required',
                                  ['on', 'off'])
        multi = cbpi.get_config_parameter('LCD_Multidisplay', None)
        cbpi.app.logger.info("LCDDisplay  - set_parameter_multidisplay added: %s" % multi)
    return multi


def set_parameter_id1():
    kettleid = cbpi.get_config_parameter("LCD_Singledisplay", None)
    if kettleid is None:
        kettleid = 1
        cbpi.add_config_parameter("LCD_Singledisplay", 1, "kettle", "Select Kettle (Number), NO! CBPi reboot required")
        cbpi.app.logger.info("LCDDisplay  - set_parameter_id1 added: %s" % kettleid)
    return kettleid


def set_ip():
    if get_ip('wlan0') != 'Not connected':
        ip = get_ip('wlan0')
    elif get_ip('eth0') != 'Not connected':
        ip = get_ip('eth0')
    elif get_ip('enxb827eb488a6e') != 'Not connected':
        ip = get_ip('enxb827eb488a6e')
    else:
        ip = 'Not connected'
    pass
    return ip


def get_ip(interface):
    ip_addr = "Not Connected"
    so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ip_addr = socket.inet_ntoa(fcntl.ioctl(so.fileno(), 0x8915, struct.pack('256s', bytes(interface.encode())[:15]))[20:24])
    finally:
        pass
    return ip_addr


def get_version_fo(path):
    version = ""
    try:
        if path is not "":
            fo = open(path, "r")
        else:
            fo = open("/home/pi/craftbeerpi3/config/version.yaml", "r")
        version = fo.read()
        fo.close()
    finally:
        return version

def get_next_hop_timer(hop1,hop2,hop3,hop4,hop5,time_left):
    hop_timers = []
    if hop1 != None:
        hop1_left = time_left - hop1
        if hop1_left > 0:
            hop_timers.append(hop1_left)
    if hop2 != None:
        hop2_left = time_left - hop2
        if hop2_left > 0:
            hop_timers.append(hop2_left)
    if hop3 != None:
        hop3_left = time_left - hop3
        if hop3_left > 0:
            hop_timers.append(hop3_left)
    if hop4 != None:
        hop4_left = time_left - hop4
        if hop4_left > 0:
            hop_timers.append(hop4_left)
    if hop5 != None:
        hop5_left = time_left - hop5
        if hop5_left > 0:
            hop_timers.append(hop5_left)
    if len(hop_timers) != 0:
        next_hop_timer = time.strftime("%H:%M:%S", time.gmtime(min(hop_timers)))
    else:
        next_hop_timer = None
#    print(next_hop_timer)
    return next_hop_timer
    pass


def show_multidisplay(refresh, charmap):
    s = cbpi.cache.get("active_step")
    for idx, value in cbpi.cache["kettle"].items():
        current_sensor_value = (cbpi.get_sensor_value(value.sensor))

        heater_of_kettle = int(cbpi.cache.get("kettle").get(value.id).heater)
        heater_status = int(cbpi.cache.get("actors").get(heater_of_kettle).state)

        line1 = (u'%s' % (cbidecode(s.name, charmap))[:20])

        next_hop_alert = None
        if s.name == 'Boil' and s.timer_end is not None:
            try:
                hop1 = int(getattr(s,'hop_1'))*60
            except:
                hop1 = None
            try:
                hop2 = int(getattr(s,'hop_2'))*60
            except:
                hop2 = None           
            try:
                hop3 = int(getattr(s,'hop_3'))*60
            except:
                hop3 = None
            try:
                hop4 = int(getattr(s,'hop_4'))*60
            except:
                hop4 = None
            try:
                hop5 = int(getattr(s,'hop_5'))*60
            except:
                hop5 = None           
            time_left = (s.timer_end - time.time())
            next_hop_alert = get_next_hop_timer(hop1,hop2,hop3,hop4,hop5,time_left)

        # line2 when steptimer is running show remaining time and kettlename
        try:
            if s.timer_end is not None:
                time_remaining = time.strftime(u"%H:%M:%S", time.gmtime(s.timer_end - time.time()))
                line2 = ((u"%s %s" % (cbidecode(value.name, charmap).ljust(12)[:11], time_remaining)).ljust(20)[:20])
            else:
                line2 = (u'%s' % cbidecode(value.name, charmap))[:20]
        except:
            line2 = u"no kettle name"
            pass

        # line3
        if s.name != 'Boil':
            line3 = (u"Targ. Temp:%6.2f%s%s" % (float(value.target_temp), u"°", lcd_unit))[:20]

            # line4 needs error handling because there may be temp value without
            # sensor dates and so it is none and than an error is thrown
            try:
                line4 = (u"Curr. Temp:%6.2f%s%s" % (float(current_sensor_value), u"°", lcd_unit))[:20]
            except:
                cbpi.app.logger.info("LCDDisplay  - current_sensor_value exception %s" % current_sensor_value)
                line4 = (u"Curr. Temp: %s" % "No Data")[:20]
        else:
            try:
                line3 = (u"Set/Act:%4.0f/%5.1f%s%s" % (float(value.target_temp), float(current_sensor_value),u"°",lcd_unit))[:20]
            except:
                cbpi.app.logger.info("LCDDisplay  - current_sensor_value exception %s" % current_sensor_value)
                line3 = (u"Set/Act:%4.0f/ N/A%s%s" % (float(value.target_temp), float(current_sensor_value),u"°",lcd_unit))[:20]
            if next_hop_alert is not None:
                line4 = (u"Add Hop in: %s" % next_hop_alert)[:20]
            else:
                line4 = (u"     ")[:20]

        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(line1)
        lcd.cursor_pos = (0, 19)
        if heater_status != 0:
            lcd.write_string(u"\x00")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(line2)
        lcd.cursor_pos = (2, 0)
        lcd.write_string(line3)
        lcd.cursor_pos = (3, 0)
        lcd.write_string(line4)
        time.sleep(refresh)
    pass


def show_singlemode(kettleid1, blink, charmap):
    s = cbpi.cache.get("active_step")

    # read the current temperature of kettle with kettleid1 from parameters
    current_sensor_value_id1 = (cbpi.get_sensor_value(int(cbpi.cache.get("kettle").get(kettleid1).sensor)))

    # get the state of the heater of the current kettle
    heater_of_kettle = int(cbpi.cache.get("kettle").get(kettleid1).heater)
    # cbpi.app.logger.info("LCDDisplay  - heater id %s" % (heater_of_kettle))

    heater_status = cbpi.cache.get("actors").get(heater_of_kettle).state
    # cbpi.app.logger.info("LCDDisplay  - heater status (0=off, 1=on) %s" % (heater_status))

    # line1 the stepname
    line1 = (u'%s' % (cbidecode(s.name, charmap)).ljust(20)[:20])

    # line2 when steptimer is running show remaining time and kettlename
    if s.timer_end is not None:
        time_remaining = time.strftime(u"%H:%M:%S", time.gmtime(s.timer_end - time.time()))
        line2 = ((u"%s %s" % (
            cbidecode(cbpi.cache.get("kettle")[kettleid1].name, charmap).ljust(12)[:11], time_remaining)).ljust(20)[
                 :20])
    else:
        line2 = ((u'%s' % (cbidecode(cbpi.cache.get("kettle")[kettleid1].name, charmap))).ljust(20)[:20])

    # line3
    line3 = (u"Targ. Temp:%6.2f%s%s" % (float(cbpi.cache.get("kettle")[kettleid1].target_temp), u"°", lcd_unit)).ljust(
        20)[:20]

    # line4 needs error handling because there may be temp value without
    # sensor dates and so it is none and than an error is thrown
    try:
        line4 = (u"Curr. Temp:%6.2f%s%s" % (float(current_sensor_value_id1), u"°", lcd_unit)).ljust(20)[:20]
    except:
        cbpi.app.logger.info(
            "LCDDisplay  - single mode current_sensor_value_id1 exception %s" % current_sensor_value_id1)
        line4 = (u"Curr. Temp: %s" % "No Data")[:20]

    lcd.cursor_pos = (0, 0)
    lcd.write_string(line1)
    lcd.cursor_pos = (0, 19)
    if blink is False and heater_status != 0:
        lcd.write_string(u"\x00")
    else:
        lcd.write_string(u" ")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(line2)
    lcd.cursor_pos = (2, 0)
    lcd.write_string(line3)
    lcd.cursor_pos = (3, 0)
    lcd.write_string(line4)


def show_fermentation_multidisplay(refresh, charmap):
    for idx, value in cbpi.cache["fermenter"].items():
        current_sensor_value = (cbpi.get_sensor_value(value.sensor))
        # INFO value = modules.fermenter.Fermenter
        # INFO FermenterId = modules.fermenter.Fermenter.id
        gravity_sensor = False
        try:
            sensor2_of_fermenter = int(cbpi.cache.get("fermenter").get(value.id).sensor2)
            sensor2_type = cbpi.cache.get("sensors").get(sensor2_of_fermenter).type
            print("Sensor Type %s" % sensor2_type)
            if (sensor2_type == "iSpindel"):
                sensor2_data_type = cbpi.cache.get("sensors").get(sensor2_of_fermenter).config["sensorType"]
                print("Sensor2 Data Type %s" % sensor2_data_type) 
                if (sensor2_data_type == "Gravity"):
                    sensor2_data_unit = cbpi.cache.get("sensors").get(sensor2_of_fermenter).config["unitsGravity"]
                    print("Sensor2 Units: %s" % sensor2_data_unit)
                    gravity_sensor=True
                    try:
                        current_gravity_value = (cbpi.get_sensor_value(value.sensor2))
                    except:
                        current_gravity_value = None
        except:
            current_gravity_value = None

        # get the state of the heater of the current fermenter, if there is none, except takes place
        try:
            heater_of_fermenter = int(cbpi.cache.get("fermenter").get(value.id).heater)
            # cbpi.app.logger.info("LCDDisplay  - fheater id %s" % (heater_of_fermenter))

            fheater_status = int(cbpi.cache.get("actors").get(heater_of_fermenter).state)
            # cbpi.app.logger.info("LCDDisplay  - fheater status (0=off, 1=on) %s" % (fheater_status))
        except:
            fheater_status = 0

        # get the state of the cooler of the current fermenter, if there is none, except takes place

        try:
            cooler_of_fermenter = int(cbpi.cache.get("fermenter").get(value.id).cooler)
            # cbpi.app.logger.info("LCDDisplay  - fcooler id %s" % (cooler_of_fermenter))

            fcooler_status = int(cbpi.cache.get("actors").get(cooler_of_fermenter).state)
            # cbpi.app.logger.info("LCDDisplay  - fcooler status (0=off, 1=on) %s" % (fcooler_status))
        except:
            fcooler_status = 0
        pass

        line1 = (u'%s' % (cbidecode(value.brewname, charmap))[:20])
        # line2
        z = 0
        # todo: line2 = u"no kettle name"
        for key, value1 in cbpi.cache["fermenter_task"].items():
            # INFO value1 = modules.fermenter.FermenterStep
            # cbpi.app.logger.info("LCDDisplay  - value1 %s" % (value1.fermenter_id))
            if value1.timer_start is not None and value1.fermenter_id == value.id:
                line2 = interval(cbidecode(value.name, charmap), (value1.timer_start - time.time()))
                z = 1
            elif z == 0:
                line2 = (u'%s' % (cbidecode(value.name, charmap))[:20])
            pass

        # line3
        if (gravity_sensor == True):
            try:
                line3 = (u"Set/Act:%5.1f/%4.1f%s%s" % (float(value.target_temp), float(current_sensor_value), u"°", lcd_unit))[:20]
            except:
                cbpi.app.logger.info("LCDDisplay  - fermentmode current_sensor_value exception %s" % current_sensor_value)
                line3 = (u"Set/Act:%5.1f/ N/A%s%s" % (float(value.target_temp), u"°", lcd_unit))[:20]
        else:        
            line3 = (u"Targ. Temp: %6.1f%s%s" % (float(value.target_temp), u"°", lcd_unit))[:20]

        # line4
        # needs errorhandling because there may be tempvalue without sensordates and
        # so it is none and than an error is thrown
        if (gravity_sensor == True):
            if current_gravity_value != None and current_gravity_value != 0:
                if sensor2_data_unit != "SG":
                    line4 = (u"Gravity:%4.1f%s" % (float(current_gravity_value), sensor2_data_unit))[:20]
                else:
                    line4 = (u"Gravity:%5.3f%s" % (float(current_gravity_value), sensor2_data_unit))[:20]
            else:
                line4=(u"             ")[:20]
        else:
            try:
                line4 = (u"Curr. Temp: %6.1f%s%s" % (float(current_sensor_value), u"°", lcd_unit))[:20]
            except:
                cbpi.app.logger.info("LCDDisplay  - fermentmode current_sensor_value exception %s" % current_sensor_value)
                line4 = (u"Curr. Temp: %s" % u"No Data")[:20]
        pass

        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(line1)
        lcd.cursor_pos = (0, 19)
        if fheater_status != 0:
            lcd.write_string(u"\x00")
        if fcooler_status != 0:
            lcd.write_string(u"\x01")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(line2)
        lcd.cursor_pos = (2, 0)
        lcd.write_string(line3)
        lcd.cursor_pos = (3, 0)
        lcd.write_string(line4)

        time.sleep(refresh)
    pass


def is_fermenter_step_running():
    for key, value2 in cbpi.cache["fermenter_task"].items():
        if value2.state == "A":
            return "active"
        else:
            pass


def show_standby(ipdet, cbpi_version, charmap):
    lcd.cursor_pos = (0, 0)
    lcd.write_string((u"CraftBeerPi %s" % cbpi_version).ljust(20))
    lcd.cursor_pos = (1, 0)
    lcd.write_string(
        (u"%s" % (cbidecode(cbpi.get_config_parameter("brewery_name", "No Brewery"), charmap))).ljust(20)[:20])
    lcd.cursor_pos = (2, 0)
    lcd.write_string((u"IP: %s" % ipdet).ljust(20)[:20])
    lcd.cursor_pos = (3, 0)
    lcd.write_string((strftime(u"%Y-%m-%d %H:%M:%S", time.localtime())).ljust(20))
    pass


def cbidecode(string, charmap="A00"):  # Changes some german Letters to be displayed
    # todo:  check if A00 is used and skip changes if A02 ist used
    if charmap == "A00":
        if DEBUG: cbpi.app.logger.info('LCDDisplay  - string: %s' % string)
        replaced_text = string.replace(u"Ä", u"\x02").replace(u"Ö", u"\x03").replace(u"Ü", u"\x04").replace(u"ß",
                                                                                                            u"\x05")
        if DEBUG: cbpi.app.logger.info('LCDDisplay  - replaced_text: %s' % replaced_text)
        return replaced_text
    else:
        return string
    pass


def interval(fermentername, seconds):
    """
    gives back intervall as tuppel
    @return: (weeks, days, hours, minutes, seconds)
    formats string for line 2
    returns the formatted string for line 2 of fermenter multiview
    """
    WEEK = 60 * 60 * 24 * 7
    DAY = 60 * 60 * 24
    HOUR = 60 * 60
    MINUTE = 60

    weeks = seconds // WEEK
    seconds = seconds % WEEK
    days = seconds // DAY
    seconds = seconds % DAY
    hours = seconds // HOUR
    seconds = seconds % HOUR
    minutes = seconds // MINUTE
    seconds = seconds % MINUTE

    if weeks >= 1:
        remaining_time = (u"W%d D%d %02d:%02d" % (int(weeks), int(days), int(hours), int(minutes)))
        return (u"%s %s" % (fermentername.ljust(8)[:7], remaining_time))[:20]
    elif weeks == 0 and days >= 1:
        remaining_time = (u"D%d %02d:%02d:%02d" % (int(days), int(hours), int(minutes), int(seconds)))
        return (u"%s %s" % (fermentername.ljust(8)[:7], remaining_time))[:20]
    elif weeks == 0 and days == 0:
        remaining_time = (u"%02d:%02d:%02d" % (int(hours), int(minutes), int(seconds)))
        return (u"%s %s" % (fermentername.ljust(11)[:10], remaining_time))[:20]
    else:
        pass
    pass


@cbpi.initalizer(order=3000)
def init(cbpi):
    global LCDaddress
    LCDaddress = int(set_lcd_address(), 16)
    cbpi.app.logger.info('LCDDisplay  - LCD_Address %s' % (set_lcd_address()))

    characters = str(set_charmap())
    cbpi.app.logger.info("LCDDisplay  - character map used %s" % characters)

    # This is just for the logfile at start
    refreshlog = float(set_parameter_refresh())
    cbpi.app.logger.info('LCDDisplay  - Refreshrate %s' % refreshlog)

    # This is just for the logfile at start
    multidisplaylog = str(set_parameter_multidisplay())
    cbpi.app.logger.info('LCDDisplay  - Multidisplay %s' % multidisplaylog)

    # This is just for the logfile at start
    id1log = int(set_parameter_id1())
    cbpi.app.logger.info("LCDDisplay  - Kettlenumber used %s" % id1log)

    global lcd
    try:
        lcd = lcd(LCDaddress, characters)
        lcd.create_char(0, bierkrug)                # u"\x00"  -->beerglass symbol
        lcd.create_char(1, cool)                    # u"\x01"  -->Ice symbol
        lcd.create_char(2, awithdots)               # u"\x02"  -->Ä
        lcd.create_char(3, owithdots)               # u"\x03"  -->Ö
        lcd.create_char(4, uwithdots)               # u"\x04"  -->Ü
        lcd.create_char(5, esszett)                 # u"\x05"  -->ß
    except:
        cbpi.notify('LCD Address is wrong', 'Change LCD Address in parameters, to detect comand promt in Raspi: sudo '
                                            'i2cdetect -y 1', type='danger', timeout=None)

    global lcd_unit
    try:
        lcd_unit = cbpi.get_config_parameter("unit", None)
        cbpi.app.logger.info("LCDDisplay  - unit used %s" % lcd_unit)
    except:
        pass

    # end of init

    @cbpi.backgroundtask(key="lcdjob", interval=0.7)
    def lcdjob(api):
        # YOUR CODE GOES HERE
        # This is the main job

        s = cbpi.cache.get("active_step")
        if s is None:
            stepname = None  # at active step and restart this assures to enter Standby screen where no s.xxx
            # methods are used an so there is no error and so there is no blank screen
        else:
            stepname = s.name
        pass

        refresh_time = float(set_parameter_refresh())

        multidisplay_status = str(set_parameter_multidisplay())

        ip = set_ip()

        character_map = characters

        if stepname is not None and multidisplay_status == "on":
            threadnames = str(threading.enumerate())
            if "<Thread(multidisplay," in threadnames:
                if DEBUG: cbpi.app.logger.info("NextionDisplay  - threads Thread multidisplay detected")
                pass
            else:
                t_multidisplay = threading.Thread(target=show_multidisplay, name='multidisplay',
                                                  args=(refresh_time, character_map))
                t_multidisplay.start()
                if DEBUG: cbpi.app.logger.info("NextionDisplay  - threads Thread multidisplay started")
            pass

        elif stepname is not None and multidisplay_status == "off":
            global BLINK
            if BLINK is False:
                show_singlemode(int(set_parameter_id1()), BLINK, character_map)
                BLINK = True
            else:
                show_singlemode(int(set_parameter_id1()), BLINK, character_map)
                BLINK = False
            pass

        elif is_fermenter_step_running() == "active":
            threadnames = str(threading.enumerate())
            if "<Thread(fermentation_multidisplay," in threadnames:
                if DEBUG: cbpi.app.logger.info("NextionDisplay  - threads Thread fermentation_multidisplay detected")
                pass
            else:
                t_ferm_multidisplay = threading.Thread(target=show_fermentation_multidisplay,
                                                       name='fermentation_multidisplay',
                                                       args=(refresh_time, character_map))
                t_ferm_multidisplay.start()
                if DEBUG: cbpi.app.logger.info("NextionDisplay  - threads Thread multidisplay started")
            pass

        else:
            cbpi_version = (get_version_fo(""))
            show_standby(ip, cbpi_version, character_map)
        pass
