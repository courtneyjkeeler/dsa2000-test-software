from pyftdi.ftdi import Ftdi
from pyftdi.i2c import I2cController, I2cIOError
from ftx_ctl.ftx import FTX
from ftx_ctl.frx import FRX

#  Ftdi.show_devices()


VID = "0403"
PID = "6048"

i2c_receive = I2cController()
i2c_receive.configure("ftdi://ftdi:4232h/1", interface=1)

frx = FRX(i2c_receive)
frx.adc.calibrate()
frx.get_uuid()

i2c_transmit = I2cController()
i2c_transmit.configure("ftdi://ftdi:2232:TG110494/2", {"interface": 2})

ftx = FTX(i2c_transmit)
ftx.adc.calibrate()

ftx.get_temp()
ftx.get_rms_power()

ftx.set_atten(0)
ftx.atten.read()

ftx.set_lna_power(True)
ftx.get_lna_current()

ftx.set_ld_current(128)
ftx.get_ld_current()

ftx.get_uuid()
