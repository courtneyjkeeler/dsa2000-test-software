def bit_set(value: int, bit: int, val: bool) -> int:
    return (value & ~(1 << bit)) | (val << bit)


def raw_to_current(raw: float, gain: float, sense_r: float, vref: float) -> float:
    return (raw * vref) / (gain * sense_r)
