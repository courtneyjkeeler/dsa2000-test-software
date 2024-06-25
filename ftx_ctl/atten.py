# Attenuator control
from pyftdi.i2c import I2cPort

# Registers
OUTPUT = 0x1
CONFIG = 0x3


# Not all the functionally, just enough to control the attenuator
class TCA6408A:
    def __init__(self, i2c: I2cPort):
        self.i2c = i2c
        # Set the control pins to output
        self.i2c.write([CONFIG, 0x0])

    def write(self, word: int):
        self.i2c.write([OUTPUT, word])

    def read(self) -> int:
        return self.i2c.read_from(OUTPUT, 1)[0]
