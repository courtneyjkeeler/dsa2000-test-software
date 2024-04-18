# -*- coding: utf-8 -*-
""" Calibrate the noise floor on the PNA """

import pyvisa as visa
import sys
import time
from pyvisa.constants import VI_ATTR_TMO_VALUE
import numpy as np


# Change this variable to the address of your instrument
VISA_ADDRESS = 'USB0::0x0957::0x0118::MY48420936::0::INSTR'

POWER = '0'  # dB

try:
    # Create a connection (session) to the instrument
    resourceManager = visa.ResourceManager()
    session = resourceManager.open_resource(VISA_ADDRESS)
except visa.Error as ex:
    print('Couldn\'t connect to \'%s\', exiting now...' % VISA_ADDRESS)
    sys.exit()

# Reset the timeout value to the default
session.set_visa_attribute(VI_ATTR_TMO_VALUE, 4000)

# Create a measurement and select it
session.write(":CALCulate:PARameter:DEFine:EXTended 'PL','B, 1'")  # Unratioed measurement
# Display measurement as trace 2
session.write(":DISPlay:WINDow:TRACe2:FEED 'PL'")
# Delete the S11 measurement on trace 1
session.write(":DISPlay:WINDow:TRACe1:DELete")
session.write(":CALCulate:PARameter:SELect 'PL'")

# # Find the range number for the primary range
# primaryNum = session.query(":SENSe:FOM:RNUM? 'Primary'")[:-1]
# # Use it to set primary freq range
# session.write(':SENSe:FOM:RANGe' + str(int(primaryNum)) + ':FREQuency:STARt 350000000')  # 350 MHz
# session.write(':SENSe:FOM:RANGe' + str(int(primaryNum)) + ':FREQuency:STOP 2000000000')  # 2 GHz
#
# # Find the range number for the source and source2 range
# sourceNum = session.query(":SENSe:FOM:RNUM? 'Source'")[:-1]
# source2Num = session.query(":SENSe:FOM:RNUM? 'Source2'")[:-1]
# receiversNum = session.query(":SENSe:FOM:RNUM? 'Receivers'")[:-1]
#
# # Couple them to the primary range and set the offset
# session.write(':SENSe:FOM:RANGe' + str(int(sourceNum)) + ':COUPled 1')
# session.write(':SENSe:FOM:RANGe' + str(int(source2Num)) + ':COUPled 1')
# session.write(':SENSe:FOM:RANGe' + str(int(receiversNum)) + ':COUPled 1')
# session.write(':SENSe:FOM:RANGe' + str(int(sourceNum)) + ':FREQuency:OFFSet -500000')  # -500 kHz
# session.write(':SENSe:FOM:RANGe' + str(int(source2Num)) + ':FREQuency:OFFSet 500000')  # 500 kHz
# session.write(':SENSe:FOM:RANGe' + str(int(receiversNum)) + ':FREQuency:OFFSet -500000')  # -500 kHz
#
# # Turn frequency offset ON
# session.write(':SENSe:FOM:STATe 1')
#
# # Turn on port 1 and port 3
# session.write(':SOURce:POWer1:MODE ON')
# session.write(':SOURce:POWer3:MODE ON')

time.sleep(0.1)

# Save data

# To trigger ONLY a specified channel:
# Set ALL channels to Sens<ch>:Sweep:Mode HOLD
session.write(":SENSe1:SWEep:MODE HOLD")
# Send TRIG:SCOP CURRent
session.write(":TRIGger:SEQuence:SCOPe CURRent")
# Send Init<ch>:Imm where <ch> is the channel to be triggered

# # 'Turn continuous sweep off
session.write("INITiate:CONTinuous OFF")

# 'Take a sweep
session.write("INITiate1:IMMediate;*wai")

# # Must select the measurement before we can read the data
session.write("CALCulate1:PARameter:SELect 'PL'")

#session.write(":FORMat:DATA REAL")  # Real32, best for large data transfers
# Default Data Format is ASCII
session.write("FORM:DATA ASCII,0")  # Easy to implement but slow
# Tells the instrument to use the native endian type when sending binary data
#session.write("FORM:BORD SWAP")
#session.write("CALCulate1:DATA? FDATA")
# pl_data = session.read()

# # Ask for the data from the sweep, pick one of the locations to read
myMeas = session.query_ascii_values("CALC1:DATA? FDATA", container=np.array)

# Get frequency values
x_axis = session.query_ascii_values("CALC1:X?", container=np.array)

# Close the connection to the instrument
session.close()
resourceManager.close()

print('Done.')