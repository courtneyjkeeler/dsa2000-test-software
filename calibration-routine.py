# -*- coding: utf-8 -*-
""" Calibrate the noise floor on the PNA """

import pyvisa as visa
import sys
import time
from pyvisa.constants import VI_ATTR_TMO_VALUE
import numpy as np


def copy_channel(sesh, to_channel, name, offset, multiplier):
    # Copy channel 1 to new channel
    sesh.write(':SYSTem:MACRo:COPY:CHANnel:TO ' + str(to_channel))
    # Create an unratioed measurement and select it
    sesh.write(":CALCulate"+str(to_channel)+":PARameter:DEFine:EXTended '"+name+"','B, 1'")
    # Display measurement as trace
    sesh.write(":DISPlay:WINDow:TRACe"+str(to_channel+1)+":FEED '"+name+"'")
    # Delete the S11 measurement on trace 1
    sesh.write(":DISPlay:WINDow:TRACe1:DELete")
    sesh.write(":CALCulate"+str(to_channel)+":PARameter:SELect '"+name+"'")

    # Adjust freq offset params
    rec_num = session.query(":SENSe"+str(to_channel)+":FOM:RNUM? 'Receivers'")[:-1]
    sesh.write(':SENSe'+str(to_channel)+':FOM:RANGe' + str(int(rec_num)) + ':FREQuency:OFFSet '+str(offset))
    sesh.write(':SENSe'+str(to_channel)+':FOM:RANGe' + str(int(rec_num))+':FREQuency:MULTiplier '+str(multiplier))

    time.sleep(0.1)


def take_cal_sweep(sesh, port):
    calibrated = False
    while not calibrated:
        sesh.write('*CLS')
        time.sleep(0.1)
        # Take cal sweep on specified port
        sesh.write(
            "SOURce:POWer"+str(port)+":CORRection:COLLect:ACQuire PMETer,'ASENSOR',SYNChronous;*OPC")
        print('Starting cal sweep on port '+str(port)+'....')
        time.sleep(0.1)
        sesh.clear()

        # Ask the user if they want to save or repeat
        print('Cal Sweep finished. Save results and continue (y) or repeat sweep (n)?')
        while True:
            ans = input('Please enter y or n:')
            if (ans == 'y') or (ans == 'n') or (ans == 'Y') or (ans == 'N'):
                break
        if (ans == 'y') or (ans == 'Y'):
            calibrated = True
        else:
            # Adjust tol and num count
            tolerance = input('Enter new iteration tolerance value: ')
            sesh.write('SOURce:POWer:CORRection:COLLect:ITERation:NTOLerance ' + tolerance)
            number = input('Enter new interation count value: ')
            sesh.write('SOURce:POWer:CORRection:COLLect:ITERation:COUNt ' + number)
            # Restart cal sweep

    sesh.write('SOURce:POWer:CORRection:COLLect:SAVE')  # Applies the cal results to the channel
    return


def source_power_cal(sesh):
    # Query the address of the power meter, so we can control it over GPIB
    sesh.write('SYSTem:COMMunicate:GPIB:PMETer:ADDRess?')
    address = sesh.read()[:-1]  # Remove the /n char that is returned at the end

    # Open a GPIB pass-through session with the power meter
    # Long timeout, GPIB is slow while cal is running
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:OPEN 0, ' + address + ', 200000')
    # Get the handle ID number
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:OPEN?')
    handle = sesh.read()[:-1]  # str

    default_timeout = sesh.get_visa_attribute(VI_ATTR_TMO_VALUE)

    # Tell power meter to zero and calibrate sensor A
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*CLS'")  # Clear status register
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*ESE 1'")  # Enable OPC bit
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", 'CALibration1:ALL?'")

    sesh.set_visa_attribute(VI_ATTR_TMO_VALUE, 20000)  # Takes about 17 seconds
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*OPC?'")
    # Wait for it to finish
    sesh.query('SYSTem:COMMunicate:GPIB:RDEVice:READ? ' + handle)

    sesh.set_visa_attribute(VI_ATTR_TMO_VALUE, default_timeout)

    time.sleep(1)
    # TODO: The CAL query enters a number into the output buffer when the sequence is
    # complete. If the result is 0 the sequence was successful. If the result is 1
    # the sequence failed. Return that number and let outer function handle it?

    # Close the GPIB passthrough session
    sesh.write('SYSTem:COMMunicate:GPIB:RDEVice:CLOSE ' + handle)

    return 1


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

# For Serial and TCP/IP socket connections enable the read Termination Character, or read's will timeout
if session.resource_name.startswith('ASRL') or session.resource_name.endswith('SOCKET'):
    session.read_termination = '\n'

# Send *IDN? and read the response
idn = session.query('*IDN?')

print('Connection successful: %s' % idn.rstrip('\n'))

# Delete all traces, measurements, and windows that might be open
session.write(':SYSTem:PRESet')

# Set up the frequency range
session.write('SENSe:FREQuency:STARt 300000000')  # 300 MHz
session.write('SENSe:FREQuency:STOP 4050000000')  # 4.05 GHz
session.write('SENSe:SWEep:POINts 401')

# Set the IF bandwidth
session.write('SENSe:BANDwidth:RESolution 100')  # 100 Hz

# Set the source power level for the DUT
# By default the ports are coupled but we'll write to each anyway
# First we'll omit the DUT and perform measurements to make sure it's 10dB better
session.write('SOURce:POWer1:LEVel:IMMediate:AMPLitude ' + POWER)  # Port 1
session.write('SOURce:POWer3:LEVel:IMMediate:AMPLitude ' + POWER)  # Port 3

# Turn ports 2 and 4 OFF
session.write('SOURce:POWer2:MODE OFF')
session.write('SOURce:POWer4:MODE OFF')

# Source power cal

# Verify with the user that the power sensor is properly plugged in for calibration
print('Please connect the power sensor to the Power Ref port of the power meter')
dummy = input('Press the Enter key to continue')

calResults = source_power_cal(session)

# Verify with the user that the power meter is plugged into the power combiner
print('Sensor zeroing and calibration complete')
print('Please connect the power sensor to the S port of the combiner')
input('Press the Enter key to continue')

# Adjust the tolerance and number of reads if needed
# session.write('SOURce:POWer:CORRection:COLLect:ITERation:NTOLerance 0.1')  # default: 0.1
# session.write('SOURce:POWer:CORRection:COLLect:ITERation:COUNt 25')  # default: 25

# Adjust the timeout value for commands to the PNA (can take 6 seconds while cal is running)
session.set_visa_attribute(VI_ATTR_TMO_VALUE, -1)
session.write('SOURce:POWer:CORRection:COLLect:DISPlay:STATe 1')  # default is ON

take_cal_sweep(session, 1)
time.sleep(0.1)
take_cal_sweep(session, 3)

# Reset the timeout value to the default
session.set_visa_attribute(VI_ATTR_TMO_VALUE, 4000)

# Done with power meter, tell the user to disconnect
print('Done with the power meter. Disconnect the sensor from the combiner.')
print('Connect Port 2 to the S port of the combiner.')
input('Press the Enter key to continue: ')

# Create a measurement and select it
session.write(":CALCulate:PARameter:DEFine:EXTended 'PL','B, 1'")  # Unratioed measurement
# Display measurement as trace 2
session.write(":DISPlay:WINDow:TRACe2:FEED 'PL'")
# Delete the S11 measurement on trace 1
session.write(":DISPlay:WINDow:TRACe1:DELete")
session.write(":CALCulate:PARameter:SELect 'PL'")

#trace_number = session.query(':CALCulate:PARameter:TNUMber?')
# Activate B receiver
#session.write(":CALCulate:PARameter:MODify B,1")
session.write(':SENSe:CORRection:COLLect:METHod RPOWer')
# Sweep and wait for *OPC
session.query(':SENSe:CORRection:COLLect:ACQuire POWer;*OPC?')
# Apply
session.write(':SENSe:CORRection:COLLect:SAVE')

#session.write(":CALCulate:PARameter:SELect 'PL'")

# Done with the power cal
print('Finished receiver power calibration.')

# Start two-tone measurement
print('Starting two-tone measurement....')

# Find the range number for the primary range
primaryNum = session.query(":SENSe:FOM:RNUM? 'Primary'")[:-1]
# Use it to set primary freq range
session.write(':SENSe:FOM:RANGe' + str(int(primaryNum)) + ':FREQuency:STARt 350000000')  # 350 MHz
session.write(':SENSe:FOM:RANGe' + str(int(primaryNum)) + ':FREQuency:STOP 2000000000')  # 2 GHz

# Find the range number for the source and source2 range
sourceNum = session.query(":SENSe:FOM:RNUM? 'Source'")[:-1]
source2Num = session.query(":SENSe:FOM:RNUM? 'Source2'")[:-1]
receiversNum = session.query(":SENSe:FOM:RNUM? 'Receivers'")[:-1]

# Couple them to the primary range and set the offset
session.write(':SENSe:FOM:RANGe' + str(int(sourceNum)) + ':COUPled 1')
session.write(':SENSe:FOM:RANGe' + str(int(source2Num)) + ':COUPled 1')
session.write(':SENSe:FOM:RANGe' + str(int(receiversNum)) + ':COUPled 1')
session.write(':SENSe:FOM:RANGe' + str(int(sourceNum)) + ':FREQuency:OFFSet -500000')  # -500 kHz
session.write(':SENSe:FOM:RANGe' + str(int(source2Num)) + ':FREQuency:OFFSet 500000')  # 500 kHz
session.write(':SENSe:FOM:RANGe' + str(int(receiversNum)) + ':FREQuency:OFFSet -500000')  # -500 kHz

# Turn frequency offset ON
session.write(':SENSe:FOM:STATe 1')

# Turn on port 1 and port 3
session.write(':SOURce:POWer1:MODE ON')
session.write(':SOURce:POWer3:MODE ON')

time.sleep(0.1)

# Copy channel 1 to channel 2
copy_channel(session, 2, 'IM2', 0, 2)
# Copy channel 1 to channel 3
copy_channel(session, 3, 'PH', 500000, 1)
# Copy channel 1 to channel 4
copy_channel(session, 4, 'IM3L', -1500000, 1)
# Copy channel 1 to channel 5
copy_channel(session, 5, 'IM3H', 1500000, 1)

# Save data

# # 'Turn continuous sweep off
session.write("INITiate:CONTinuous OFF")

# To trigger ONLY a specified channel:
# Set ALL channels to Sens<ch>:Sweep:Mode HOLD
session.write(":SENSe1:SWEep:MODE HOLD")
session.write(":SENSe2:SWEep:MODE HOLD")
session.write(":SENSe3:SWEep:MODE HOLD")
session.write(":SENSe4:SWEep:MODE HOLD")
session.write(":SENSe5:SWEep:MODE HOLD")
# Send TRIG:SCOP CURRent
session.write(":TRIGger:SEQuence:SCOPe CURRent")
# Send Init<ch>:Imm where <ch> is the channel to be triggered
session.write("INITiate1:IMMediate;*wai")

# # Must select the measurement before we can read the data
session.write("CALCulate1:PARameter:SELect 'PL'")

session.write("FORM:DATA ASCII,0")  # Easy to implement but slow

# # Ask for the data from the sweep, pick one of the locations to read
primary_low = session.query_ascii_values("CALC1:DATA? FDATA", container=np.array)

# Get frequency values
x_axis = session.query_ascii_values("CALC1:X?", container=np.array)

session.write("INITiate3:IMMediate;*wai")
session.write("CALCulate3:PARameter:SELect 'PH'")
primary_high = session.query_ascii_values("CALC3:DATA? FDATA", container=np.array)

session.write("INITiate2:IMMediate;*wai")
session.write("CALCulate2:PARameter:SELect 'IM2'")
second_intermod = session.query_ascii_values("CALC2:DATA? FDATA", container=np.array)

session.write("INITiate4:IMMediate;*wai")
session.write("CALCulate4:PARameter:SELect 'IM3L'")
third_intermod_low = session.query_ascii_values("CALC4:DATA? FDATA", container=np.array)

session.write("INITiate5:IMMediate;*wai")
session.write("CALCulate5:PARameter:SELect 'IM3H'")
third_intermod_high = session.query_ascii_values("CALC5:DATA? FDATA", container=np.array)

# Save the raw data


# Do math on the signals

# OIP2 = PL + PH - IM2
OIP2 = primary_low + primary_high - second_intermod
# OIP3 = max((2*PL+PH-IM3L)/2, (PL+2*PH-IM3H)/2)
OIP3 = np.maximum((2*primary_low+primary_high-third_intermod_low)/2,
                  (primary_low+2*primary_high-third_intermod_high)/2)
# gain = PL - inputPow
gain = primary_low - POWER
IIp2 = OIP2 - gain

# Plot and save the results

# Close the connection to the instrument
session.close()
resourceManager.close()

print('Done.')
