from pyftdi.ftdi import Ftdi
from pyftdi.i2c import I2cController
#Ftdi.show_devices()

i2c = I2cController()
i2c.configure('ftdi://ftdi:2232:TG110494/2')
port = i2c.get_port(0x20)

port.write_to(0x03, b'\x00')

port.write_to(0x03, [(0x80 | 0xFF)])
