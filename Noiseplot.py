import csv
import matplotlib.pyplot as plt
import numpy


def readGainData(pathToFile):
    f = open(pathToFile)
    csv_reader = csv.reader(f)

    freq = []
    S21 = []

    for line_no, line in enumerate(csv_reader, 1):
        if line_no > 8:
            if len(line) == 0:
                print('Empty line...')
            elif len(line) == 1:
                if line[0] == 'END':
                    print("end of file")
                else:
                    print('Channel Header...')
            else:
                freq.append(float(line[0])/1000000000)
                S21.append(float(line[1]))

    f.close()
    return [freq, S21]

def readNoiseData(pathToFile):
    f = open(pathToFile)
    csv_reader = csv.reader(f)

    freq = []
    TraceA = []  # dark current
    TraceB = []

    for line_no, line in enumerate(csv_reader, 1):
        if line_no > 40:
            if len(line) == 0:
                print('Empty line...')
            else:
                freq.append(float(line[0])/1000000000)  # GHz
                TraceA.append(float(line[1]))
                TraceB.append(float(line[2]))
    f.close()
    return [freq, TraceA, TraceB]


def computeNoise(data, gain):
    darkCurrent = numpy.array(data[1])
    traceB = numpy.array(data[2])
    actualgain = numpy.array(gain[1])

    # Convert from dB to linear
    linearDark = 10**(darkCurrent/10)
    linearB = 10**(traceB/10)
    linearGain = 10**(actualgain/10)

    # Divide by 1000 to convert to Watts
    linearDark /= 1000
    linearB /= 1000

    # Subtract dark current from trace B
    diff = linearB - linearDark

    # Divide by linear gain to get power at input of laser in Watts
    inputPow = diff / linearGain

    print(inputPow)

    kb = 1.380649e-23  # J/K

    # divide by boltzmanns constant * bandwidth (megahert, 1e6) to get noise temp
    noiseTemp = inputPow / (kb * 1e6)

    return noiseTemp

Shengshi = readNoiseData('C:\\Users\\ckeeler\\Desktop\\Shengshi_noise.csv')
shenGain = readGainData('C:\\Users\\ckeeler\\Desktop\\Shengshi_gain.csv')

shenNoise = computeNoise(Shengshi, shenGain)

AGX = readNoiseData('C:\\Users\\ckeeler\\Desktop\\agx_noise.csv')
AGXgain = readGainData('C:\\Users\\ckeeler\\Desktop\\agx_gain.csv')

AGxNoise = computeNoise(AGX, AGXgain)

fig, ax1 = plt.subplots(1, 1, layout='constrained', sharey=True)
ax1.plot(Shengshi[0], shenNoise, label='Shengshi')
ax1.plot(AGX[0], AGxNoise, label='AGx')
ax1.legend()
ax1.set_xlabel('Freq (GHz)')
ax1.set_ylabel('Noise, K')

fig.show()

print("All done")
