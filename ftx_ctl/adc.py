# Methods for interacting with the TLA2528 ADC

from pyftdi.i2c import I2cPort
from enum import Enum

# Opcodes
OPCODE_READ_REG = 0b00010000
OPCODE_WRITE_REG = 0b00001000
OPCODE_SET_BIT = 0b00011000
OPCODE_CLEAR_BIT = 0b00100000

# Registers
SYSTEM_STATUS = 0x0
GENERAL_CFG = 0x1
DATA_CFG = 0x2
OSR_CFG = 0x3
OPMODE_CFG = 0x4
PIN_CFG = 0x5
GPIO_CFG = 0x7
GPO_DRIVE_CFG = 0x9
GPO_VALUE = 0xB
GPI_VALUE = 0xD
SEQUENCE_CFG = 0x10
CHANNEL_SEL = 0x11
AUTO_SEQ_CH_SEL = 0x12


class PinMode(Enum):
    AnalogInput = 1
    DigitalInput = 2
    PushPullOutput = 3
    OpenDrainOutput = 4


class TLA2528:
    def __init__(self, i2c: I2cPort):
        self.i2c = i2c
        self.oversampling = False

    def _write_reg(self, reg: int, payload: int):
        self.i2c.write([OPCODE_WRITE_REG, reg, payload])

    def _set_bits_reg(self, reg: int, bits: int):
        self.i2c.write([OPCODE_SET_BIT, reg, bits])

    def _clear_bits_reg(self, reg: int, bits: int):
        self.i2c.write([OPCODE_CLEAR_BIT, reg, bits])

    def _read_reg(self, reg: int) -> int:
        return self.i2c.exchange([OPCODE_READ_REG, reg], 1)[0]

    def _change_bit(self, reg: int, bit: int, val: bool):
        if val:
            self._set_bits_reg(reg, 1 << bit)
        else:
            self._clear_bits_reg(reg, 1 << bit)

    def reset(self):
        self._write_reg(GENERAL_CFG, 0b00000001)

    def calibrate(self):
        self._write_reg(GENERAL_CFG, 0b00000010)
        while self._read_reg(GENERAL_CFG) & 0b00000010:
            pass

    def set_osr(self, osr: int):
        self._write_reg(OSR_CFG, osr)
        self.oversampling = osr != 0

    def configure_pin(self, pin: int, mode: PinMode):
        match mode:
            case PinMode.AnalogInput:
                self._change_bit(PIN_CFG, pin, False)
            case PinMode.DigitalInput:
                self._change_bit(PIN_CFG, pin, True)
                self._change_bit(GPIO_CFG, pin, False)
            case PinMode.PushPullOutput:
                self._change_bit(PIN_CFG, pin, True)
                self._change_bit(GPIO_CFG, pin, True)
                self._change_bit(GPO_DRIVE_CFG, pin, True)
            case PinMode.OpenDrainOutput:
                self._change_bit(PIN_CFG, pin, True)
                self._change_bit(GPIO_CFG, pin, True)
                self._change_bit(GPO_DRIVE_CFG, pin, False)

    # FIXME
    def analog_read(self, pin: int) -> float:
        self._write_reg(CHANNEL_SEL, pin)
        self._write_reg(OPMODE_CFG, 0b00000001)
        # Will always be two bytes
        data = self.i2c.read(2)
        # If we're not oversampling, shift by 4
        if not self.oversampling:
            return ((data[0] << 4) | (data[1] >> 4)) / 2**12
        else:
            return ((data[0] << 8) | data[1]) / 2**16

    def digital_read(self, pin: int) -> bool:
        data = self._read_reg(GPI_VALUE)
        return (data >> pin) & 1 == 1

    def digital_write(self, pin: int, val: bool):
        self._change_bit(GPO_VALUE, pin, val)
