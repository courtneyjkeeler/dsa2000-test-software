# Class for the entire FTX API
from pyftdi.i2c import I2cController
from ftx_ctl.adc import TLA2528, PinMode
from ftx_ctl.atten import TCA6408A
from ftx_ctl.digipot import CAT5171
from ftx_ctl.utils import raw_to_current

# FTX I2C Addresses
ADDR_DIGIPOT = 0x2C
ADDR_ATTEN = 0x20
ADDR_ADC = 0x10
ADDR_UUID = 0b1011000

# ADC Pinout
ADC_TEMP = 0
ADC_PD_IMON = 1
ADC_RF_MON = 2
ADC_LNA_IMON = 3
ADC_LD_IMON = 4
ADC_LNA_FAULT = 5
ADC_LNA_EN = 6

# Board constants
VREF = 5.0
SENSE_GAIN = 100
IPD_SENSE_R = 62
ILD_SENSE_R = 1
ILNA_SENSE_R = 0.5


class FTX:
    def _setup_adc(self):
        # Setup the ADC/GPIO
        self.adc.reset()
        self.adc.calibrate()
        self.adc.set_osr(3)
        # Pins 0-4 are analog inputs by default
        self.adc.configure_pin(ADC_LNA_FAULT, PinMode.DigitalInput)
        self.adc.configure_pin(ADC_LNA_EN, PinMode.PushPullOutput)

    def __init__(self, i2c: I2cController):
        self.i2c = i2c

        self.digipot = CAT5171(i2c.get_port(ADDR_DIGIPOT))
        self.atten = TCA6408A(i2c.get_port(ADDR_ATTEN))
        self.adc = TLA2528(i2c.get_port(ADDR_ADC))
        self.uuid = i2c.get_port(ADDR_UUID)

        # Perform initial setup
        self._setup_adc()

    def _read_current(self, pin: int, sense_r: float) -> float:
        return raw_to_current(self.adc.analog_read(pin), SENSE_GAIN, sense_r, VREF)

    def set_atten(self, word: int):
        self.atten.write(word)

    def set_ld_current(self, val: int):
        self.digipot.set(val)

    # In C
    def get_temp(self) -> float:
        tc = 19.5  # mV/C
        v0 = 400  # mV
        raw = self.adc.analog_read(ADC_TEMP)
        raw_mv = raw * 5000
        return (raw_mv - v0) / tc

    # In mA
    def get_ld_current(self) -> float:
        return self._read_current(ADC_LD_IMON, ILD_SENSE_R) * 1e3

    # In mA
    def get_lna_current(self) -> float:
        return self._read_current(ADC_LNA_IMON, ILNA_SENSE_R) * 1e3

    def set_lna_power(self, enabled: bool):
        self.adc.digital_write(ADC_LNA_EN, enabled)

    # Approximate, will need calibration
    def get_rms_power(self) -> float:
        raw = self.adc.analog_read(ADC_RF_MON)
        return 17.74 * (raw * 5) - 55

    # Returns true if the LNA is in a fault state
    def get_lna_fault(self) -> bool:
        return not self.adc.digital_read(ADC_LNA_FAULT)

    def get_uuid(self) -> bytes:
        return self.uuid.read_from(0b10000000, 16)

    # In mA
    def get_pd_current(self) -> float:
        return self._read_current(ADC_PD_IMON, IPD_SENSE_R) * 1e3
