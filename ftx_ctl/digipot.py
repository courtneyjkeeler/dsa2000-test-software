# Digipot control for LD current control

from pyftdi.i2c import I2cPort


class CAT5171:
    def __init__(self, i2c: I2cPort):
        self.i2c = i2c

    def set(self, val: int):
        # All zeros for the "instruction byte" as we don't care about resets
        self.i2c.write([0, val])

    def get(self):
        return self.i2c.read(1)
