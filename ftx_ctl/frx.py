# Class for the entire FRX API
from pyftdi.i2c import I2cController
from ftx_ctl.atten import TCA6408A
from ftx_ctl.adc import TLA2528, PinMode
from ftx_ctl.utils import raw_to_current

# FRX I2C Addresses
ADDR_ATTEN = 0x20
ADDR_ADC = 0x10
ADDR_UUID = 0b1011000

# ADC Pinout
ADC_TEMP = 0
ADC_PD_IMON = 1
ADC_RF_MON = 2

# Board constants
VREF = 5.0
SENSE_GAIN = 100
IPD_SENSE_R = 62


class FRX:
    def _setup_adc(self):
        # Setup the ADC/GPIO
        self.adc.reset()
        self.adc.calibrate()
        self.adc.set_osr(3)
        # Pins 0-4 are analog inputs by default

    def __init__(self, i2c: I2cController):
        self.i2c = i2c

        self.atten = TCA6408A(i2c.get_port(ADDR_ATTEN))
        self.adc = TLA2528(i2c.get_port(ADDR_ADC))
        self.uuid = i2c.get_port(ADDR_UUID)

        # Perform initial setup
        self._setup_adc()

    def _read_current(self, pin: int, sense_r: float) -> float:
        return raw_to_current(self.adc.analog_read(pin), SENSE_GAIN, sense_r, VREF)

    def set_atten(self, word: int):
        self.atten.write(word)

    # In C
    def get_temp(self) -> float:
        tc = 19.5  # mV/C
        v0 = 400  # mV
        raw = self.adc.analog_read(ADC_TEMP)
        raw_mv = raw * 5000
        return (raw_mv - v0) / tc

    # Approximate, will need calibration
    def get_rms_power(self) -> float:
        raw = self.adc.analog_read(ADC_RF_MON)
        return 17.74 * (raw * 5) - 55

    def get_uuid(self) -> bytes:
        return self.uuid.read_from(0b10000000, 16)

    # In mA
    def get_pd_current(self) -> float:
        return self._read_current(ADC_PD_IMON, IPD_SENSE_R) * 1e3
