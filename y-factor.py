# -*- coding: utf-8 -*-
"""
Measure the y-factor noise using Siglent spectrum analyzer
"""

import datetime
import numpy as np
import pyvisa as visa
import math
import sys
import time


#########################################
# User Settings
#########################################
freq_start = 0
freq_stop = 1
preamp = False
attenuation = 0
reference_level = 0
video_bandwidth = 100
resolution_bandwidth = 100
#number_of_points = 201


# Connect to Siglent
rm = visa.ResourceManager()
rm.list_resources()
spectrum_analyzer = rm.open_resource('USB0::0xF4EC::0x1300::SSA3XLBC1R0061::INSTR')
print(spectrum_analyzer.query("*IDN?"))

spectrum_analyzer.read_termination = '\n'
spectrum_analyzer.query("*OPC?")
time.sleep(0.1)
spectrum_analyzer.write(':DISPlay:WINDow:TRACe:Y:RLEVel ' + str(reference_level) + ' DBM')
time.sleep(0.1)
spectrum_analyzer.write(':POWer:ATTenuation ' + str(attenuation))
time.sleep(0.1)
spectrum_analyzer.write(':POWer:GAIN ' + str(int(preamp)))
time.sleep(0.1)
spectrum_analyzer.write(':UNIT:POWer DBM')
time.sleep(0.1)
spectrum_analyzer.write(':DISPlay:WINDow:TRACe:Y:PDIVision 1 db')
time.sleep(0.1)
spectrum_analyzer.write(':SENSe:CORRection:OFF')
time.sleep(0.1)
spectrum_analyzer.write(':BWID: ' + str(resolution_bandwidth) + ' MHz')
time.sleep(0.1)
spectrum_analyzer.write(':BWIDth:VIDeo ' + str(video_bandwidth) + ' MHz')
time.sleep(0.1)
spectrum_analyzer.write(':TRAC1:MODE WRITE')
time.sleep(0.1)
spectrum_analyzer.write(':TRAC1:MODE AVERAGE')
time.sleep(0.1)
spectrum_analyzer.write(':DETector:TRAC1 AVERage')
time.sleep(0.1)
spectrum_analyzer.write(':AVERage:TRAC1:COUNt 16')
time.sleep(0.1)
spectrum_analyzer.write(':SWEep:MODE AUTO')
time.sleep(0.1)
spectrum_analyzer.write(':SWEep:TIME:AUTO ON')
time.sleep(0.1)
spectrum_analyzer.write(':SWEep:SPEed:ACCUracy')
time.sleep(0.1)
spectrum_analyzer.write(':AVERage:TYPE POWer')
time.sleep(0.1)

# Acquire Data
sweep_count = 1
freq_points = 16  # Total no of freq points to be avg'd when calculating SA data
spectrum_analyzer.write(':*WAI')
time.sleep(0.1)
spectrum_analyzer.write(':SENSE:FREQuency:STARt ' + str(freq_start) + ' MHz')
time.sleep(0.1)
spectrum_analyzer.write(':SENSE:FREQ:STOP ' + str(freq_stop) + ' MHz')
time.sleep(0.1)
spectrum_analyzer.write(':SWEep:COUNt ' + str(sweep_count))
time.sleep(0.1)

time.sleep(10)  # Check video BW to set the real number here
spectrum_analyzer.write('*WAI')
time.sleep(0.5)
data = spectrum_analyzer.query(':TRACe:DATA? 1')  # Returns current displayed data
time.sleep(0.5)

