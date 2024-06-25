# -*- coding: utf-8 -*-
""" Calibrate the noise floor on the PNA """

import pyvisa as visa
import sys
import time
from pyvisa.constants import VI_ATTR_TMO_VALUE
import numpy as np
import datetime
import dearpygui.dearpygui as dpg
from openpyxl.utils.dataframe import dataframe_to_rows


def copy_channel(to_channel, name, offset, multiplier):
    # Copy channel 1 to new channel
    session.write(':SYSTem:MACRo:COPY:CHANnel:TO ' + str(to_channel))
    # Create an unratioed measurement and select it
    session.write(":CALCulate"+str(to_channel)+":PARameter:DEFine:EXTended '"+name+"','B, 1'")
    # Display measurement as trace
    session.write(":DISPlay:WINDow:TRACe"+str(to_channel+1)+":FEED '"+name+"'")
    # Delete the S11 measurement on trace 1
    session.write(":DISPlay:WINDow:TRACe1:DELete")
    session.write(":CALCulate"+str(to_channel)+":PARameter:SELect '"+name+"'")

    # Adjust freq offset params
    rec_num = session.query(":SENSe"+str(to_channel)+":FOM:RNUM? 'Receivers'")[:-1]
    session.write(':SENSe'+str(to_channel)+':FOM:RANGe' + str(int(rec_num)) + ':FREQuency:OFFSet '+str(offset))
    session.write(':SENSe'+str(to_channel)+':FOM:RANGe' + str(int(rec_num))+':FREQuency:MULTiplier '+str(multiplier))

    time.sleep(0.1)


def take_cal_sweep(port):
    calibrated = False
    while not calibrated:
        session.write('*CLS')
        time.sleep(0.1)
        # Take cal sweep on specified port
        session.write(
            "SOURce:POWer"+str(port)+":CORRection:COLLect:ACQuire PMETer,'ASENSOR',SYNChronous;*OPC")
        print('Starting cal sweep on port '+str(port)+'....')
        time.sleep(0.1)
        session.clear()

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
            session.write('SOURce:POWer:CORRection:COLLect:ITERation:NTOLerance ' + tolerance)
            number = input('Enter new interation count value: ')
            session.write('SOURce:POWer:CORRection:COLLect:ITERation:COUNt ' + number)
            # Restart cal sweep

    session.write('SOURce:POWer:CORRection:COLLect:SAVE')  # Applies the cal results to the channel
    return


def source_power_cal():
    # Query the address of the power meter, so we can control it over GPIB
    session.write('SYSTem:COMMunicate:GPIB:PMETer:ADDRess?')
    address = session.read()[:-1]  # Remove the /n char that is returned at the end

    # Open a GPIB pass-through session with the power meter
    # Long timeout, GPIB is slow while cal is running
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:OPEN 0, ' + address + ', 200000')
    # Get the handle ID number
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:OPEN?')
    handle = session.read()[:-1]  # str

    default_timeout = session.get_visa_attribute(VI_ATTR_TMO_VALUE)

    # Tell power meter to zero and calibrate sensor A
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*CLS'")  # Clear status register
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*ESE 1'")  # Enable OPC bit
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", 'CALibration1:ALL?'")

    session.set_visa_attribute(VI_ATTR_TMO_VALUE, 20000)  # Takes about 17 seconds
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*OPC?'")
    # Wait for it to finish
    session.query('SYSTem:COMMunicate:GPIB:RDEVice:READ? ' + handle)

    session.set_visa_attribute(VI_ATTR_TMO_VALUE, default_timeout)

    time.sleep(1)
    # TODO: The CAL query enters a number into the output buffer when the sequence is
    # complete. If the result is 0 the sequence was successful. If the result is 1
    # the sequence failed. Return that number and let outer function handle it?

    # Close the GPIB passthrough session
    session.write('SYSTem:COMMunicate:GPIB:RDEVice:CLOSE ' + handle)

    return 1


def two_tone_calibration(input_power):
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
    session.write('SOURce:POWer1:LEVel:IMMediate:AMPLitude ' + input_power)  # Port 1
    session.write('SOURce:POWer3:LEVel:IMMediate:AMPLitude ' + input_power)  # Port 3

    # Turn ports 2 and 4 OFF
    session.write('SOURce:POWer2:MODE OFF')
    session.write('SOURce:POWer4:MODE OFF')

    # Source power cal

    # Verify with the user that the power sensor is properly plugged in for calibration
    print('Please connect the power sensor to the Power Ref port of the power meter')
    dummy = input('Press the Enter key to continue')

    cal_results = source_power_cal()

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

    take_cal_sweep(1)
    time.sleep(0.1)
    take_cal_sweep(3)

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


def two_tone_test(file_path, input_power, serial_number):
    # Start two-tone measurement
    print('Starting two-tone measurement....')

    # TODO: this stuff doesn't need to be redone for every DUT switch
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
    copy_channel(2, 'IM2', 0, 2)
    # Copy channel 1 to channel 3
    copy_channel(3, 'PH', 500000, 1)
    # Copy channel 1 to channel 4
    copy_channel(4, 'IM3L', -1500000, 1)
    # Copy channel 1 to channel 5
    copy_channel(5, 'IM3H', 1500000, 1)

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

    # Do math on the signals

    # OIP2 = PL + PH - IM2
    OIP2 = primary_low + primary_high - second_intermod
    # OIP3 = max((2*PL+PH-IM3L)/2, (PL+2*PH-IM3H)/2)
    OIP3 = np.maximum((2*primary_low+primary_high-third_intermod_low)/2,
                      (primary_low+2*primary_high-third_intermod_high)/2)
    # gain = PL - inputPow
    gain = primary_low - input_power
    IIp2 = OIP2 - gain

    # Read Date and Time from PC clock
    date_time_string = time.strftime('%m%d%Y %H:%M:%S')
    # Format Time
    t = datetime.datetime.strptime(date_time_string, "%m%d%Y %H:%M:%S")
    # TODO: revise the saving routine here

    with open(file_path+serial_number, 'w') as f:
        f.write('Data from Two-Tone Test\n')
        f.write(str(t)+'\n')
        f.write(serial_number+'\n')
        f.write(input_power+'\n')
        f.write('Frequency (Hz),PL Log Mag(dBm),PH Log Mag(dBm),IM2 Log Mag(dBm),IM3L Log Mag(dBm),IM3H Log Mag(dBm),'
                'OIP2,OIP3,Gain,IIP2\n')
        np.savetxt(f, zip(x_axis, primary_low, primary_high, second_intermod, third_intermod_low, third_intermod_high,
                          OIP2, OIP3, gain, IIp2), delimiter=',', fmt='%f')

    # Plot and save the results


def connect_to_pna():
    global session
    global resourceManager
    # Change this variable to the address of your instrument
    VISA_ADDRESS = 'USB0::0x0957::0x0118::MY48420936::0::INSTR'

    try:
        # Create a connection (session) to the instrument
        resourceManager = visa.ResourceManager()
        session = resourceManager.open_resource(VISA_ADDRESS)
    except visa.Error as ex:
        print('Couldn\'t connect to \'%s\', exiting now...' % VISA_ADDRESS)
        dpg.add_text('Couldn\'t connect to instrument, exiting now...', parent='console')
        # sys.exit()
        return 1

    # For Serial and TCP/IP socket connections enable the read Termination Character, or read's will timeout
    if session.resource_name.startswith('ASRL') or session.resource_name.endswith('SOCKET'):
        session.read_termination = '\n'

    # Send *IDN? and read the response
    idn = session.query('*IDN?')

    dpg.add_text('Successful connection to PNA', parent='console')
    print('Connection successful: %s' % idn.rstrip('\n'))
    return 0


def noise_floor_cal(file_path):
    # PATH = 'C:\\Users\\ckeeler\\Documents\\DSA2000\\TestSoftware\\data\\'

    # Setup workbook to save data
    # TODO: revise save routine here

    # First calibrate to 0db power with no DUT to see the noise floor of the PNA
    two_tone_calibration('0')
    two_tone_test(file_path, '0', 'PNA')


def device_measure(file_path, device):
    # Cal to -50db
    # two_tone_calibration('-50')
    # Insert DUT
    # print("Insert DUT between S port of the power combiner and PNA Port 2")
    # device = input("Please enter the serial number of the DUT:")
    # measure

    print("Starting two tone test on " + device + "...")
    two_tone_test(file_path, '-50', device)
    print("Saving two tone test data for " + device + "...")
    # TODO: revise the saving here


def close_session():
    # Close the connection to the instrument
    session.close()
    resourceManager.close()

    print('Done.')


session = None
resourceManager = None

