# -*- coding: utf-8 -*-
""" Test the USB connection to the PNA-X """

import pyvisa as visa
import sys

# Change this variable to the address of your instrument
VISA_ADDRESS = 'USB0::0x0957::0x0118::MY48420936::0::INSTR'

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
session.write('*IDN?')
idn = session.read()

print('Connection successful: %s' % idn.rstrip('\n'))

# Close the connection to the instrument
session.close()
resourceManager.close()

print('Done.')
