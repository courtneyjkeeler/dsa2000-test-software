import pyvisa as visa
import time
from pyvisa.constants import VI_ATTR_TMO_VALUE
import dearpygui.dearpygui as dpg
import inspect
import numpy as np
from RsInstrument import *

dpg_callback_queue = []

# This file is modified for the Rohde & Schwarz ZVL VNA


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


def input_box():

    def on_inputbox_btn_click(sender, data, user_data):
        nonlocal resp
        # resp = dpg.get_item_label(sender)
        resp = dpg.get_value('new_tolerance')
        dpg.hide_item(popup)

    # print(dpg.last_item())
    with dpg.popup(parent=dpg.last_item(), modal=True) as popup:
        # print(dpg.get_item_parent(popup))
        dpg.add_text("New iteration tolerance:")
        dpg.add_input_float(tag='new_tolerance', default_value=0.1, min_value=0, max_value=5)
        dpg.add_text("New iteration count:")
        dpg.add_input_int(tag='new_count', default_value=25, min_value=1, max_value=100)
        dpg.add_button(label='OK', callback=on_inputbox_btn_click)
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
        self._zvl = None
        self.popup = None
        self.input_pow = None
        self.x_axis = None

        with dpg.window(modal=True, show=False, tag="modal_id", no_title_bar=True):
            dpg.add_text("Please wait....")

    def connect_to_pna(self) -> int:
        try:
            # Create a connection (session) to the instrument over LAN
            self._zvl = RsInstrument('TCPIP::192.168.1.50::INSTR', reset=True, id_query=True)
            self._zvl.write_str_with_opc('*RST')
            self._zvl.visa_timeout = 3000
            # opc_timeout default value is 10000 ms
            self._zvl.opc_timeout = 20000
            # Keep the spectrum analyzer synchronized by waiting for OPC after each command
            self._zvl.opc_query_after_write = True
        except ResourceError as ex:
            print(ex.args[0])
            # sys.exit()
            return 1

        return 0

    def close_session(self):
        # Close the connection to the instrument
        self._zvl.close()

    def get_idn(self):
        return self._zvl.query('*IDN?')

    def calibration(self, input_power):
        """
        Initializes the PNA settings to prepare for a two-tone test
        :param input_power:
        :return:
        """

        # Activate single sweep mode, minimum sweep points
        self._zvl.write('*RST')
        self._zvl.write('INITiate1:CONTinuous OFF')
        self._zvl.write('SWEep:POINts 101')  # minimum
        self._zvl.write('SENSe1:SWEep:TIME:AUTO ON')
        self._zvl.write('TRIGger1:SEQuence:SOURce IMMediate')

        # Single sweep performed on active channel only
        # self._zvl.write('INIT:SCOP SING')

        # Set the frequency span to 50kHz
        # self._zvl.write('FREQ:SPAN 50000')
        self._zvl.write('SENSe1:BANDwidth:RESolution 1kHz')

        self.input_pow = input_power

    def two_tone_test(self, primary_low):
        """
        Function to read the peak values for a fixed frequency two-tone test, and calculate OIP and IIP values.
        :param primary_low: in MHz, the frequency of the lower of the two tones
        :return array: floats [gain, PL, PH, IM2, IM3L, IM3H, OIP2, OIP3, IIP2, IIP3]
        """
        # Start two-tone measurement
        # Machine was initialized to be on single sweep mode, not continuous
        # Machine was initialized to be on auto RBW, auto VBW, auto sweep time

        # Reset the no of points
        self._zvl.write('SENSe1:SWEep:POINts 1001')

        self._zvl.write('FREQ:SPAN 50000')
        # Set center freq to tone of interest
        self._zvl.write('FREQuency:CENTer ' + str(primary_low) + 'MHz')

        # Set averaging
        self._zvl.write('AVER ON')
        self._zvl.write('AVER:COUN 5')

        # Start a sweep
        self._zvl.write('INITiate:IMMediate; *WAI')

        # Turn on the marker
        self._zvl.write('CALC:MARK ON')
        # format = self._zvl.write('CALCulate1:MARKer1:FORMat DEFault')
        self._zvl.write('CALC:MARK:X ' + str(primary_low) + 'MHz')

        # Read the marker value and save it
        PL = float(self._zvl.query('CALC:MARK:Y?'))

        # Repeat for all measurements
        self._zvl.write('FREQuency:CENTer ' + str(primary_low + 1) + 'MHz')
        self._zvl.write('INITiate:IMMediate; *WAI')
        self._zvl.write('CALC:MARK:X ' + str(primary_low + 1) + 'MHz')
        PH = float(self._zvl.query('CALC:MARK:Y?'))

        self._zvl.write('FREQuency:CENTer ' + str((primary_low + .5)*2) + 'MHz')
        self._zvl.write('INITiate:IMMediate; *WAI')
        self._zvl.write('CALC:MARK:X ' + str((primary_low + .5)*2) + 'MHz')
        IM2 = float(self._zvl.query('CALC:MARK:Y?'))

        self._zvl.write('FREQuency:CENTer ' + str(primary_low - 1) + 'MHz')
        self._zvl.write('INITiate:IMMediate; *WAI')
        self._zvl.write('CALC:MARK:X ' + str(primary_low - 1) + 'MHz')
        IM3L = float(self._zvl.query('CALC:MARK:Y?'))

        self._zvl.write('FREQuency:CENTer ' + str(primary_low + 2) + 'MHz')
        self._zvl.write('INITiate:IMMediate; *WAI')
        self._zvl.write('CALC:MARK:X ' + str(primary_low + 2) + 'MHz')
        IM3H = float(self._zvl.query('CALC:MARK:Y?'))

        self._zvl.write('FREQuency:CENTer ' + str(primary_low * 2) + 'MHz')
        self._zvl.write('INITiate:IMMediate; *WAI')
        self._zvl.write('CALC:MARK:X ' + str(primary_low * 2) + 'MHz')
        nyquist = float(self._zvl.query('CALC:MARK:Y?'))

        self._zvl.write('SENSe1:SWEep:POINts 101')

        # Do math on the signals

        OIP2 = PL + PH - IM2
        OIP3 = max((2*PL+PH-IM3L)/2, (PL+2*PH-IM3H)/2)
        gain = PL - self.input_pow

        IIP2 = OIP2 - gain
        IIP3 = OIP3 - gain

        # Return the results
        return [gain, PL, PH, IM2, IM3L, IM3H, OIP2, OIP3, IIP2, IIP3, nyquist]

