import pyvisa as visa
import time
from pyvisa.constants import VI_ATTR_TMO_VALUE
import dearpygui.dearpygui as dpg
import inspect
import numpy as np

dpg_callback_queue = []


def msgbox(message, extra_button=False):

    def on_msgbox_btn_click(sender, data, user_data):
        nonlocal resp
        resp = dpg.get_item_label(sender)
        dpg.hide_item(popup)

    # print(dpg.last_item())
    with dpg.popup(parent=dpg.last_item(), modal=True) as popup:
        # print(dpg.get_item_parent(popup))
        dpg.add_text(message)
        if extra_button:
            with dpg.group(horizontal=True):
                dpg.add_button(label='Yes', callback=on_msgbox_btn_click)
                dpg.add_button(label='No', callback=on_msgbox_btn_click)
        else:
            dpg.add_button(label='OK', callback=on_msgbox_btn_click)
    dpg.show_item(popup)

    resp = None
    while not resp:
        handle_callbacks_and_render_one_frame()
    return resp


def show_wait(message) -> None:

    # print(dpg.last_item())
    with dpg.window(tag="wait_popup"):
        # print(dpg.get_item_parent(popup))
        dpg.add_text(message)


def hide_wait():
    dpg.hide_item("wait_popup")


def run_callbacks():
    global dpg_callback_queue
    while dpg_callback_queue:
        job = dpg_callback_queue.pop(0)
        if job[0] is None:
            continue
        sig = inspect.signature(job[0])
        args = []
        for i in range(len(sig.parameters)):
            args.append(job[i + 1])
        result = job[0](*args)


def handle_callbacks_and_render_one_frame():
    global dpg_callback_queue
    dpg_callback_queue += dpg.get_callback_queue() or []  # retrieves and clears queue
    run_callbacks()
    dpg.render_dearpygui_frame()


def _show_popup_window(message) -> None:
    """Displays a small popup window with a message to tell users to wait.
    """
    if message is None:
        return
    if dpg.does_item_exist("blocking_popup"):
        dpg.configure_item("blocking_popup", width=150, height=50,
                           pos=((dpg.get_viewport_width() - 150) // 2, (dpg.get_viewport_height() - 50) // 2))
        dpg.configure_item("blocking_popup", show=True)
        dpg.set_value("blocking_popup_text", message)
        # dpg.set_item_user_data("blocking_popup_button", user_data)
        return
    with dpg.window(tag="blocking_popup", width=150, height=50,
                    pos=((dpg.get_viewport_width() - 150) // 2, (dpg.get_viewport_height() - 50) // 2)):
        dpg.add_text(message, tag="blocking_popup_text")
        # dpg.add_input_text(multiline=True, tag='multiline_input')
        # dpg.add_button(label="OK", tag="blocking_popup_button", user_data=user_data,
        #                callback=self._save_comments)


def _hide_popup_window() -> None:
    dpg.delete_item('blocking_popup')


class PNA:

    def __init__(self):
        self._session = None
        self._resourceManager = None
        self._primaryNum = None
        self.primary_low = None
        self.primary_high = None
        self.second_intermod = None
        self.third_intermod_low = None
        self.third_intermod_high = None
        # Change this variable to the address of your instrument
        # self.VISA_ADDRESS = 'USB0::0x0957::0x0118::MY48420936::0::INSTR'
        self.VISA_ADDRESS = 'GPIB0::16::INSTR'
        self.popup = None
        self.input_pow = None
        self.x_axis = None
        self.gain = None
        self.OIP3 = None
        self.OIP2 = None
        self.IIp2 = None
        self.IIp3 = None

        with dpg.window(modal=True, show=False, tag="modal_id", no_title_bar=True):
            dpg.add_text("Please wait....")

    def connect_to_pna(self) -> int:
        try:
            # Create a connection (session) to the instrument
            self._resourceManager = visa.ResourceManager()
            self._session = self._resourceManager.open_resource(self.VISA_ADDRESS)
        except visa.Error as ex:
            # print('Couldn\'t connect to \'%s\', exiting now...' % self.VISA_ADDRESS)
            # sys.exit()
            return 1

        # For Serial and TCP/IP socket connections enable the read Termination Character, or read's will timeout
        if self._session.resource_name.startswith('ASRL') or self._session.resource_name.endswith('SOCKET'):
            self._session.read_termination = '\n'

        return 0

    def close_session(self):
        # Close the connection to the instrument
        self._session.close()
        self._resourceManager.close()

    def get_idn(self):
        return self._session.query('*IDN?')

    def source_power_cal(self):
        # Query the address of the power meter, so we can control it over GPIB
        self._session.write('SYSTem:COMMunicate:GPIB:PMETer:ADDRess?')
        address = self._session.read()[:-1]  # Remove the /n char that is returned at the end

        # Open a GPIB pass-through session with the power meter
        # Long timeout, GPIB is slow while cal is running
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:OPEN 0, ' + address + ', 200000')
        # Get the handle ID number
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:OPEN?')
        handle = self._session.read()[:-1]  # str

        default_timeout = self._session.get_visa_attribute(VI_ATTR_TMO_VALUE)

        # Tell power meter to zero and calibrate sensor A
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*CLS'")  # Clear status register
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*ESE 1'")  # Enable OPC bit
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", 'CALibration1:ALL?'")

        self._session.set_visa_attribute(VI_ATTR_TMO_VALUE, 20000)  # Takes about 17 seconds
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:WRITe ' + handle + ", '*OPC?'")
        # Wait for it to finish
        self._session.query('SYSTem:COMMunicate:GPIB:RDEVice:READ? ' + handle)

        self._session.set_visa_attribute(VI_ATTR_TMO_VALUE, default_timeout)

        time.sleep(1)
        # TODO: The CAL query enters a number into the output buffer when the sequence is
        # complete. If the result is 0 the sequence was successful. If the result is 1
        # the sequence failed. Return that number and let outer function handle it?

        # Close the GPIB passthrough session
        self._session.write('SYSTem:COMMunicate:GPIB:RDEVice:CLOSE ' + handle)

        # return 1

    def take_cal_sweep(self, port):
        calibrated = False
        while not calibrated:
            self._session.write('*CLS')
            time.sleep(0.1)
            # Take cal sweep on specified port
            self._session.write(
                "SOURce:POWer" + str(port) + ":CORRection:COLLect:ACQuire PMETer,'ASENSOR',SYNChronous;*OPC")
            # print('Starting cal sweep on port ' + str(port) + '....')
            time.sleep(1)
            self._session.clear()

            # Ask the user if they want to save or repeat
            resp = msgbox('WAIT FOR CAL SWEEP TO FINISH\nSave results?', extra_button=True)

            if resp == 'Yes':
                calibrated = True
            else:
                # # Adjust tol and num count
                # tolerance = input('Enter new iteration tolerance value: ')
                # session.write('SOURce:POWer:CORRection:COLLect:ITERation:NTOLerance ' + tolerance)
                # number = input('Enter new interation count value: ')
                # session.write('SOURce:POWer:CORRection:COLLect:ITERation:COUNt ' + number)
                # # Restart cal sweep
                #  TODO: add this capability back in
                calibrated = True

        self._session.write('SOURce:POWer:CORRection:COLLect:SAVE')  # Applies the cal results to the channel
        return

    def calibration(self, input_power):
        self.input_pow = input_power
        self._primaryNum = None
        # Delete all traces, measurements, and windows that might be open
        self._session.write(':SYSTem:PRESet')

        # Set up the frequency range
        self._session.write('SENSe:FREQuency:STARt 300000000')  # 300 MHz
        self._session.write('SENSe:FREQuency:STOP 4050000000')  # 4.05 GHz
        self._session.write('SENSe:SWEep:POINts 401')

        # Set the IF bandwidth
        self._session.write('SENSe:BANDwidth:RESolution 10')  # 100 Hz

        # Set calibration level
        # By default the ports are coupled but we'll write to each anyway
        self._session.write('SOURce:POWer1:LEVel:IMMediate:AMPLitude ' + self.input_pow)  # Port 1
        self._session.write('SOURce:POWer3:LEVel:IMMediate:AMPLitude ' + self.input_pow)  # Port 3

        # Turn ports 2 and 4 OFF
        self._session.write('SOURce:POWer2:MODE OFF')
        self._session.write('SOURce:POWer4:MODE OFF')

        # Source power cal

        # Verify with the user that the power sensor is properly plugged in for calibration
        resp = msgbox('Please connect the power sensor to the Power \nRef port of the power meter.'
                      + '\n' + 'Click OK to continue')
        if resp == 'OK':
            dpg.configure_item("modal_id", show=True)
            print("cool")

        self.source_power_cal()

        dpg.configure_item("modal_id", show=False)

        # Verify with the user that the power meter is plugged into the power combiner
        resp = msgbox('Sensor zeroing and calibration complete.'
                      + '\n' + 'Please connect the power sensor to the S port of the combiner.'
                      + '\n' + 'Click OK to continue')

        if resp == 'OK':
            print('We did it!')

        # Adjust the tolerance and number of reads if needed
        # session.write('SOURce:POWer:CORRection:COLLect:ITERation:NTOLerance 0.1')  # default: 0.1
        # session.write('SOURce:POWer:CORRection:COLLect:ITERation:COUNt 25')  # default: 25

        # Adjust the timeout value for commands to the PNA (can take 6 seconds while cal is running)
        self._session.set_visa_attribute(VI_ATTR_TMO_VALUE, -1)
        self._session.write('SOURce:POWer:CORRection:COLLect:DISPlay:STATe 1')  # default is ON

        time.sleep(0.1)
        self.take_cal_sweep(1)
        time.sleep(0.1)
        self.take_cal_sweep(3)

        # Done with power meter, tell the user to disconnect
        # self.popup = BlockingPopupWindow('Done with the power meter. Disconnect the sensor from the combiner.'
        #                                  + '\n' + 'Connect Port 2 to the S port of the combiner.'
        #                                  + '\n' + 'Click OK to continue')
        # self.popup.show_window()
        resp = msgbox('Done with the power meter. Disconnect the sensor from the combiner.'
                      + '\n' + 'Connect Port 2 to the S port of the combiner.'
                      + '\n' + 'Click OK to continue')

        if resp == 'Yes':
            print('We did it!')

        # Create a measurement and select it
        self._session.write(":CALCulate:PARameter:DEFine:EXTended 'PL','B, 1'")  # Unratioed measurement
        # Display measurement as trace 2
        self._session.write(":DISPlay:WINDow:TRACe2:FEED 'PL'")
        # Delete the S11 measurement on trace 1
        self._session.write(":DISPlay:WINDow:TRACe1:DELete")
        self._session.write(":CALCulate:PARameter:SELect 'PL'")

        # trace_number = session.query(':CALCulate:PARameter:TNUMber?')
        # Activate B receiver
        # session.write(":CALCulate:PARameter:MODify B,1")
        self._session.write(':SENSe:CORRection:COLLect:METHod RPOWer')
        # Sweep and wait for *OPC
        self._session.query(':SENSe:CORRection:COLLect:ACQuire POWer;*OPC?')
        # Apply
        self._session.write(':SENSe:CORRection:COLLect:SAVE')
        # Reset the timeout value to the default
        self._session.set_visa_attribute(VI_ATTR_TMO_VALUE, 4000)

        # Done with the power cal
        # print('Finished receiver power calibration.')
        resp = msgbox('Finished receiver power calibration.'
                      + '\n' + 'If applicable, place DUT between S port and port 2.'
                      + '\n' + 'Click OK to return to home screen')

        if resp == 'Yes':
            print('We did it!')

    def copy_channel(self, to_channel, name, offset, multiplier):
        # Copy channel 1 to new channel
        self._session.write(':SYSTem:MACRo:COPY:CHANnel:TO ' + str(to_channel))
        # Create an unratioed measurement and select it
        self._session.write(":CALCulate" + str(to_channel) + ":PARameter:DEFine:EXTended '" + name + "','B, 1'")
        # Display measurement as trace
        self._session.write(":DISPlay:WINDow:TRACe" + str(to_channel + 1) + ":FEED '" + name + "'")
        # adjust offset
        self._session.write("DISPlay:WINDow:TRACe" + str(to_channel + 1) + ":Y:SCALe:RLEVel -50")
        # Delete the S11 measurement on trace 1
        self._session.write(":DISPlay:WINDow:TRACe1:DELete")
        self._session.write(":CALCulate" + str(to_channel) + ":PARameter:SELect '" + name + "'")

        # Adjust freq offset params
        rec_num = self._session.query(":SENSe" + str(to_channel) + ":FOM:RNUM? 'Receivers'")[:-1]
        self._session.write(
            ':SENSe' + str(to_channel) + ':FOM:RANGe' + str(int(rec_num)) + ':FREQuency:OFFSet ' + str(offset))
        self._session.write(
            ':SENSe' + str(to_channel) + ':FOM:RANGe' + str(int(rec_num)) + ':FREQuency:MULTiplier ' + str(multiplier))

        time.sleep(0.1)

    def two_tone_test(self, input_power):
        # Start two-tone measurement
        if self.input_pow is None:
            print("uh-oh, the machine wasn't calibrated before running the tests")
            self.input_pow = input_power
        # print('Starting two-tone measurement....')

        # This stuff doesn't need to be redone for every DUT switch
        if self._primaryNum is None:
            # Find the range number for the primary range
            self._primaryNum = self._session.query(":SENSe:FOM:RNUM? 'Primary'")[:-1]
            # Use it to set primary freq range
            self._session.write(':SENSe:FOM:RANGe' + str(int(self._primaryNum)) + ':FREQuency:STARt 350000000')  # 350 MHz
            self._session.write(':SENSe:FOM:RANGe' + str(int(self._primaryNum)) + ':FREQuency:STOP 2000000000')  # 2 GHz

            # Find the range number for the source and source2 range
            source_num = self._session.query(":SENSe:FOM:RNUM? 'Source'")[:-1]
            source2_num = self._session.query(":SENSe:FOM:RNUM? 'Source2'")[:-1]
            receivers_num = self._session.query(":SENSe:FOM:RNUM? 'Receivers'")[:-1]

            # Couple them to the primary range and set the offset
            self._session.write(':SENSe:FOM:RANGe' + str(int(source_num)) + ':COUPled 1')
            self._session.write(':SENSe:FOM:RANGe' + str(int(source2_num)) + ':COUPled 1')
            self._session.write(':SENSe:FOM:RANGe' + str(int(receivers_num)) + ':COUPled 1')
            self._session.write(':SENSe:FOM:RANGe' + str(int(source_num)) + ':FREQuency:OFFSet -500000')  # -500 kHz
            self._session.write(':SENSe:FOM:RANGe' + str(int(source2_num)) + ':FREQuency:OFFSet 500000')  # 500 kHz
            self._session.write(':SENSe:FOM:RANGe' + str(int(receivers_num)) + ':FREQuency:OFFSet -500000')  # -500 kHz

            # Turn frequency offset ON
            self._session.write(':SENSe:FOM:STATe 1')

            # Turn on port 1 and port 3
            self._session.write(':SOURce:POWer1:MODE ON')
            self._session.write(':SOURce:POWer3:MODE ON')

            time.sleep(0.1)

            # Copy channel 1 to channel 2
            self.copy_channel(2, 'IM2', 0, 2)
            # Copy channel 1 to channel 3
            self.copy_channel(3, 'PH', 500000, 1)
            # Copy channel 1 to channel 4
            self.copy_channel(4, 'IM3L', -1500000, 1)
            # Copy channel 1 to channel 5
            self.copy_channel(5, 'IM3H', 1500000, 1)

        # Save data

        # # 'Turn continuous sweep off
        self._session.write("INITiate:CONTinuous OFF")

        # To trigger ONLY a specified channel:
        # Set ALL channels to Sens<ch>:Sweep:Mode HOLD
        self._session.write(":SENSe1:SWEep:MODE HOLD")
        self._session.write(":SENSe2:SWEep:MODE HOLD")
        self._session.write(":SENSe3:SWEep:MODE HOLD")
        self._session.write(":SENSe4:SWEep:MODE HOLD")
        self._session.write(":SENSe5:SWEep:MODE HOLD")
        # Send TRIG:SCOP CURRent
        self._session.write(":TRIGger:SEQuence:SCOPe CURRent")
        # Send Init<ch>:Imm where <ch> is the channel to be triggered
        self._session.write("INITiate1:IMMediate;*wai")

        # # Must select the measurement before we can read the data
        self._session.write("CALCulate1:PARameter:SELect 'PL'")

        self._session.write("FORM:DATA ASCII,0")  # Easy to implement but slow

        # # Ask for the data from the sweep, pick one of the locations to read
        # Reset timeout value since this takes longer
        self._session.set_visa_attribute(VI_ATTR_TMO_VALUE, -1)
        self.primary_low = self._session.query_ascii_values("CALC1:DATA? FDATA", container=np.array)

        # Get frequency values
        self.x_axis = (self._session.query_ascii_values("CALC1:X?", container=np.array))/1000000000

        self._session.write("INITiate3:IMMediate;*wai")
        self._session.write("CALCulate3:PARameter:SELect 'PH'")
        self.primary_high = self._session.query_ascii_values("CALC3:DATA? FDATA", container=np.array)

        self._session.write("INITiate2:IMMediate;*wai")
        self._session.write("CALCulate2:PARameter:SELect 'IM2'")
        self.second_intermod = self._session.query_ascii_values("CALC2:DATA? FDATA", container=np.array)

        self._session.write("INITiate4:IMMediate;*wai")
        self._session.write("CALCulate4:PARameter:SELect 'IM3L'")
        self.third_intermod_low = self._session.query_ascii_values("CALC4:DATA? FDATA", container=np.array)

        self._session.write("INITiate5:IMMediate;*wai")
        self._session.write("CALCulate5:PARameter:SELect 'IM3H'")
        self.third_intermod_high = self._session.query_ascii_values("CALC5:DATA? FDATA", container=np.array)

        # Reset the timeout
        self._session.set_visa_attribute(VI_ATTR_TMO_VALUE, 4000)

        # Do math on the signals

        # OIP2 = PL + PH - IM2
        self.OIP2 = self.primary_low + self.primary_high - self.second_intermod
        # OIP3 = max((2*PL+PH-IM3L)/2, (PL+2*PH-IM3H)/2)
        self.OIP3 = np.maximum((2 * self.primary_low + self.primary_high - self.third_intermod_low) / 2,
                               (self.primary_low + 2 * self.primary_high - self.third_intermod_high) / 2)
        # gain = PL - inputPow
        self.gain = self.primary_low - input_power
        self.IIp2 = self.OIP2 - self.gain
        self.IIp3 = self.OIP3 - self.gain

