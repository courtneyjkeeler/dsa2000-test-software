import csv
import matplotlib.pyplot as plt
import numpy

def readData(pathToFile):
    f = open(pathToFile)
    csv_reader = csv.reader(f)

    currChan = 1
    freq = []
    PL = []
    PH = []
    IM2 = []
    IM3L = []
    IM3H = []

    for line_no, line in enumerate(csv_reader, 1):
        if line_no > 7:
            if len(line) == 0:
                print('Empty line...')
            elif len(line) == 1:
                if line[0] == 'END':
                    if currChan < 5:
                        currChan += 1
                else:
                    print('Channel Header...')
            elif not (line[0] == 'Freq(Hz)'):
                if currChan == 1:
                    freq.append(float(line[0])/1000000000)
                    PL.append(float(line[1]))
                elif currChan == 2:
                    IM2.append(float(line[1]))
                elif currChan == 3:
                    PH.append(float(line[1]))
                elif currChan == 4:
                    IM3L.append(float(line[1]))
                elif currChan == 5:
                    IM3H.append(float(line[1]))
                else:
                    print('Channel out of range!')
            else:
                print('More Header info...')
    f.close()
    return [freq, PL, PH, IM2, IM3L, IM3H]


def computeIntercepts(data, inputPow):
    freq = numpy.array(data[0])
    PL = numpy.array(data[1])
    PH = numpy.array(data[2])
    IM2 = numpy.array(data[3])
    IM3L = numpy.array(data[4])
    IM3H = numpy.array(data[5])
    OIP2 = PL + PH - IM2
    OIP3 = numpy.maximum((2*PL+PH-IM3L)/2, (PL+2*PH-IM3H)/2)
    gain = PL - inputPow
    IIp2 = OIP2 - gain

    # To compute IP2, use `pl+ph-im2`
    # To compute IP3, use `max((2pl+ph-im3l)/2, (pl+2ph-im3h)/2)`
    # IIp2 = OIP2 - gain

    return [OIP2, OIP3, gain, IIp2]


inputPow = 0  # dBm

#AGX = readData('C:\\Users\\david\\Desktop\\RFoF_upToPD_noAtten_AGx_20km.csv')
AGX20 = readData('C:\\Users\\ckeeler\\Desktop\\RFoF_fiberOnly_AGx_20km_30mA.csv')
Shengshi20 = readData('C:\\Users\\ckeeler\\Desktop\\RFoF_fiberOnly_Shengshi_20km_45mA.csv')

intercepts20 = computeIntercepts(Shengshi20, inputPow)
interceptsAGX = computeIntercepts(AGX20, inputPow)

#fig1, (ax1, ax2, ax3) = plt.subplots(1, 3, layout='constrained')
fig1, axs = plt.subplots(2, 2, layout='constrained')

axs[0, 0].plot(Shengshi20[0], intercepts20[2], label='Shengshi, 45 mA')  # gain vs freq
axs[0, 0].plot(AGX20[0], interceptsAGX[2], label='AGx, 30 mA')
#ax1.plot(AGX20[0], interceptsAGX[2], label='AGx')

#ax1.set_title('Gain')
axs[0, 0].set_xlabel('Frequency (GHz)')
axs[0, 0].set_ylabel('Gain (dB)')
axs[0, 0].legend()

axs[1, 0].plot(Shengshi20[0], intercepts20[0], label='Shengshi')  # OIP2 vs freq
axs[1, 0].plot(AGX20[0], interceptsAGX[0], label='AGx')
#ax2.plot(AGX20[0], interceptsAGX[0], label='AGx')

#ax2.set_title('No Attenuation')
axs[1, 0].set_xlabel('Frequency (GHz)')
axs[1, 0].set_ylabel('OIP2 (dBm)')
#ax2.legend()

axs[1, 1].plot(Shengshi20[0], intercepts20[1], label='Shengshi')
axs[1, 1].plot(AGX20[0], interceptsAGX[1], label='AGx')
#ax3.plot(AGX20[0], interceptsAGX[1], label='AGx')

#ax2.set_title('No Attenuation')
axs[1, 1].set_xlabel('Frequency (GHz)')
axs[1, 1].set_ylabel('OIP3 (dBm)')
#ax3.legend()

axs[0, 1].plot(Shengshi20[0], intercepts20[3], label='Shengshi')
axs[0, 1].plot(AGX20[0], interceptsAGX[3], label='AGx')
axs[0, 1].set_xlabel('Frequency (GHz)')
axs[0, 1].set_ylabel('IIP2 (dBm)')

fig1.suptitle('Linearity of Fiber over 20km, at manufacturer recommended input current', fontsize=16)

fig1.show()
#
# fig2, (x1, x2) = plt.subplots(1, 2, layout='constrained', sharey=True)
# x1.plot(withAtten[0], interceptsWithAtten[0], label='10dB Attenuation')
# x1.plot(upToPD[0], interceptsUpToPD[0], label='no Attenuation')
#
# x1.set_title('IP2')
# x1.set_xlabel('Frequency (GHz)')
# #x1.set_ylabel('LogM (dBm)')
# x1.legend()
#
# x2.plot(withAtten[0], interceptsWithAtten[1], label='10dB Attenuation')
# x2.plot(upToPD[0], interceptsUpToPD[1], label='no Attenuation')
#
# x2.set_title('IP3')
# x2.set_xlabel('Frequency (GHz)')
# #x1.set_ylabel('LogM (dBm)')
# x2.legend()
#
# fig2.show()

print('done.')
