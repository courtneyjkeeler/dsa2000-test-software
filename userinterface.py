import dearpygui.dearpygui as dpg
import usb.core
import usb.util
from pyftdi.i2c import I2cController, I2cIOError
from ftx_ctl.ftx import FTX
from ftx_ctl.frx import FRX
import time
from pna import PNA, handle_callbacks_and_render_one_frame

# from threading import Thread
# from typing import List


class UserInterface:
    # _threads: List[Thread] = []

    def __init__(self):
        self.running = False
        self.paused = False
        self._connection_window_id = 0
        self._calibration_window_id = 0
        self._device_window_id = 0
        self._console_window_id = 0
        self._measure_window_id = 0
        self._last_cal = "No Cal"
        self.i2c_transmit = None
        self.ftx = None
        self.i2c_receive = None
        self.frx = None
        self.pna = None

    def run(self):
        self.running = True
        dpg.create_context()
        dpg.create_viewport(title='Two Tone Test Automated Program', width=1000, height=700)
        dpg.setup_dearpygui()
        dpg.set_exit_callback(self._exit_callback)
        self._make_gui()
        dpg.set_primary_window("primary_window", True)
        dpg.show_viewport()
        dpg.set_viewport_resizable(False)
        dpg.configure_app(manual_callback_management=True)
        # dpg.start_dearpygui()
        while dpg.is_dearpygui_running():
            handle_callbacks_and_render_one_frame()
        dpg.destroy_context()

    def connect_pna(self):
        #  Connect to the PNA
        if self.pna is None:
            self.pna = PNA()
        if self.pna.connect_to_pna() == 0:
            # Send *IDN? and read the response
            idn = self.pna.get_idn()
            dpg.add_text('Connection successful: %s' % idn.rstrip('\n'), parent=self._console_window_id)
            #  If no errors, show the disconnect button
            dpg.configure_item(dpg.get_item_children(self._connection_window_id, slot=1)[1], show=False, enabled=False)
            dpg.configure_item(dpg.get_item_children(self._connection_window_id, slot=1)[2], show=True, enabled=True)
            #  Enable calibration
            dpg.configure_item(dpg.get_item_children(self._calibration_window_id, slot=1)[5], enabled=True)
            #  Enable starting a measurement
            dpg.configure_item(dpg.get_item_children(self._measure_window_id, slot=1)[0], enabled=True)
        else:
            dpg.add_text('Couldn\'t connect to \'%s\', exiting now...' % self.pna.VISA_ADDRESS,
                         parent=self._console_window_id)

    def disconnect_pna(self):
        #  Disconnect from the PNA
        self.pna.close_session()
        dpg.add_text('Disconnected from the PNA.', parent=self._console_window_id)
        #  If no errors, show the connect button
        dpg.configure_item(dpg.get_item_children(self._connection_window_id, slot=1)[1], show=True, enabled=True)
        dpg.configure_item(dpg.get_item_children(self._connection_window_id, slot=1)[2], show=False, enabled=False)
        #  Disable calibration
        dpg.configure_item(dpg.get_item_children(self._calibration_window_id, slot=1)[5], enabled=False)
        #  Disable starting a measurement
        dpg.configure_item(dpg.get_item_children(self._measure_window_id, slot=1)[0], enabled=False)

    def is_pna_connected(self):
        # If connected is true, the disconnect button is enabled
        kid = dpg.get_item_children(self._connection_window_id, slot=1)[2]
        state = dpg.get_item_configuration(kid)
        return state.get("enabled")

    def connect_ftx(self) -> int:
        """Connects to the ftx and frx boards.
        """

        dev = usb.core.find(idVendor=0x0403, idProduct=0x6048)
        # dev = usb.core.find(idVendor=1027, idProduct=24592)
        if dev is None:
            dpg.add_text("Could not find the USB device, check connection and try again.",
                         parent=self._console_window_id)
            return 1

        self.i2c_transmit = I2cController()
        try:
            self.i2c_transmit.configure(dev, interface=2)
            self.ftx = FTX(self.i2c_transmit)
        except I2cIOError:
            # Log the error to the console
            dpg.add_text("Could not connect to FTX board, check connection and try again.",
                         parent=self._console_window_id)
            return 1

        self.i2c_receive = I2cController()
        try:
            self.i2c_receive.configure(dev, interface=1)
            self.frx = FRX(self.i2c_receive)
        except I2cIOError:
            # Log the error to the console
            dpg.add_text("Could not connect to FRX board, check connection and try again.",
                         parent=self._console_window_id)
            return 1
        return 0

    def start_calibration(self):
        dpg.add_text('Starting the calibration routine...', parent=self._console_window_id)
        self._last_cal = str(dpg.get_value(dpg.get_item_children(self._calibration_window_id, slot=1)[3]))
        self.pna.calibration(self._last_cal)
        dpg.add_text('Finished receiver power calibration.', parent=self._console_window_id)

    def no_dut_checked(self):
        #  Checked when the user wants to measure the noise floor of the PNA, for example
        if dpg.get_value(dpg.get_item_children(self._device_window_id, slot=1)[2]):
            #  Disable all the attenuator and serial number settings
            for kids in dpg.get_item_children(self._device_window_id, slot=1)[3:]:
                dpg.configure_item(kids, show=False)
            dpg.configure_item(self._device_window_id, height=100)
        else:
            #  Enable all the attenuator and serial number settings
            for kids in dpg.get_item_children(self._device_window_id, slot=1)[3:]:
                dpg.configure_item(kids, show=True)
            dpg.configure_item(self._device_window_id, height=300)

    def program_dut(self):
        #  Use the I2C connection to pass along the input values and read the SN

        err = 0
        if self.i2c_transmit is None or self.i2c_receive is None:
            err = self.connect_ftx()

        if err == 0:
            new_value = dpg.get_value(dpg.get_item_children(self._device_window_id, slot=1)[9])

            self.ftx.set_atten(int(new_value * 4))
            dpg.add_text("Setting input attenuation to " + str(new_value) + "...", parent=self._console_window_id)
            time.sleep(0.1)
            set_value = self.ftx.atten.read() / 4
            dpg.set_value(dpg.get_item_children(self._device_window_id, slot=1)[9], set_value)
            if new_value != set_value:
                dpg.add_text(
                    "**WARNING** Value input: " + str(round(new_value, 2)) + ", value set: " + str(set_value) + ".",
                    parent=self._console_window_id)

            new_value = dpg.get_value(dpg.get_item_children(self._device_window_id, slot=1)[5])

            self.frx.set_atten(int(new_value * 4))
            dpg.add_text("Setting output attenuation to " + str(new_value) + "...", parent=self._console_window_id)
            time.sleep(0.1)
            set_value = self.frx.atten.read() / 4
            dpg.set_value(dpg.get_item_children(self._device_window_id, slot=1)[5], set_value)
            if new_value != set_value:
                dpg.add_text(
                    "**WARNING** Value input: " + str(round(new_value, 2)) + ", value set: " + str(set_value) + ".",
                    parent=self._console_window_id)

            #  Re-read the SN in case we connected to a different board since the last read/write
            # FRX SN
            dpg.configure_item(dpg.get_item_children(self._device_window_id, slot=1)[6], label=self.frx.get_uuid())
            # FTX SN
            dpg.configure_item(dpg.get_item_children(self._device_window_id, slot=1)[11], label=self.ftx.get_uuid())

    def read_dut(self):
        #  Use I2C interface to read the attn values and SNs from FRX and FTX

        err = 0
        if self.i2c_transmit is None or self.i2c_receive is None:
            err = self.connect_ftx()

        if err == 0:
            dpg.set_value(dpg.get_item_children(self._device_window_id, slot=1)[5], str(self.frx.atten.read() / 4))
            dpg.set_value(dpg.get_item_children(self._device_window_id, slot=1)[9], str(self.ftx.atten.read() / 4))
            dpg.configure_item(dpg.get_item_children(self._device_window_id, slot=1)[6], label=self.frx.get_uuid())
            dpg.configure_item(dpg.get_item_children(self._device_window_id, slot=1)[11], label=self.ftx.get_uuid())

    def start_measurement(self):
        # TODO: what if we start a measurement from a pre-calibrated machine
        dpg.add_text("Starting two-tone measurement...", parent=self._console_window_id)
        self.pna.two_tone_test(self._last_cal)
        #  TODO: update the graphs here

    def save_measurement(self):
        frx_sn = None
        ftx_sn = None
        if self.frx is not None:
            frx_sn = self.frx.get_uuid()
        if self.ftx is not None:
            ftx_sn = self.ftx.get_uuid()

        self.pna.save_report(filepath="C:/Users/ckeeler/Documents/DSA2000/TestSoftware/", frx_sn=frx_sn, ftx_sn=ftx_sn)

    def _make_gui(self):
        with dpg.window(label="Two Tone Test Program", tag="primary_window"):
            with dpg.group(horizontal=True):
                with dpg.group(label="left side"):
                    self._connection_window_id = dpg.add_child_window(label="connection_window", height=100, width=200)
                    dpg.add_text("PNA Connection Control", parent=self._connection_window_id)
                    dpg.add_button(label="Connect", tag="connect_button", enabled=True, show=True,
                                   callback=self.connect_pna, indent=55, width=60, parent=self._connection_window_id)
                    dpg.add_button(label="Disconnect", tag="disconnect_button", enabled=False, show=False,
                                   callback=self.disconnect_pna, indent=35, width=100,
                                   parent=self._connection_window_id)
                    self._calibration_window_id = dpg.add_child_window(label="calibration_window", height=150,
                                                                       width=200)
                    dpg.add_text("Re-Calibrate PNA", parent=self._calibration_window_id)
                    dpg.add_spacer(parent=self._calibration_window_id)
                    dpg.add_text("Source Power (dBm)", parent=self._calibration_window_id)
                    dpg.add_input_float(tag="cal_input", step=0, on_enter=True, parent=self._calibration_window_id,
                                        callback=lambda: print('Check if input is valid'), min_value=-50,
                                        min_clamped=True, max_value=0, max_clamped=True)
                    dpg.add_spacer(parent=self._calibration_window_id, height=10)
                    dpg.add_button(label="Start", tag="start_cal_button", enabled=False,
                                   parent=self._calibration_window_id, callback=self.start_calibration, indent=55,
                                   width=60)
                    self._device_window_id = dpg.add_child_window(label="device_window", height=300, width=200)
                    dpg.add_text("Device Under Test Settings", parent=self._device_window_id)
                    dpg.add_spacer(parent=self._device_window_id)
                    dpg.add_checkbox(label="No DUT", parent=self._device_window_id, tag="no_dut_checkbox",
                                     callback=self.no_dut_checked)
                    dpg.add_spacer(parent=self._device_window_id)
                    dpg.add_text("Fiber Rx Attenuation", parent=self._device_window_id, tag="frt_text")
                    dpg.add_input_float(default_value=0, tag="frx_input", step=0, min_value=-50, min_clamped=True,
                                        max_value=0, max_clamped=True, parent=self._device_window_id)
                    dpg.add_text("FRX SN: ", parent=self._device_window_id, tag="frx_sn_text",
                                 show_label=True)
                    dpg.add_spacer(parent=self._device_window_id)
                    dpg.add_text("Fiber Tx Attenuation", parent=self._device_window_id)
                    dpg.add_input_float(default_value=0, tag="ftx_input", step=0, min_value=-50, min_clamped=True,
                                        max_value=0, max_clamped=True, parent=self._device_window_id)
                    dpg.add_spacer(parent=self._device_window_id)
                    dpg.add_text("FTX SN: ", tag="sn_text", parent=self._device_window_id,
                                 show_label=True)
                    dpg.add_spacer(parent=self._device_window_id, height=10)
                    dpg.add_button(label="Read", tag="read_dut_button", parent=self._device_window_id,
                                   callback=self.read_dut, indent=55, width=60)
                    dpg.add_button(label="Write", tag="program_dut_button", parent=self._device_window_id,
                                   callback=self.program_dut, indent=55, width=60)
                    self._measure_window_id = dpg.add_child_window(label="measurement_window", height=50, width=200)
                    dpg.add_button(label="Measure", tag="start_measure_button", enabled=False,
                                   parent=self._measure_window_id, callback=self.start_measurement, indent=55, width=60)
                    dpg.add_button(label="Save", tag="save_button", enabled=False, show=False,
                                   parent=self._measure_window_id, callback=self.save_measurement, indent=55, width=60)
                with dpg.group(label='right side'):
                    self._console_window_id = dpg.add_child_window(label="console_window", height=200, width=750)
                    dpg.add_text("Welcome to the console for the two tone test program.",
                                 parent=self._console_window_id)
                    dpg.add_text("Check here for status messages and important setup instructions.",
                                 parent=self._console_window_id)
                    dpg.add_text("Begin by connecting to the PNA and (optionally) DUT.",
                                 parent=self._console_window_id)
        # thread = Thread(target=self._listen_task)
        # thread.start()
        # self._threads.append(thread)

    def _exit_callback(self):
        self.running = False
        # for thread in self._threads:
        #     thread.join()
        # time.sleep(0.5)
        if self.is_pna_connected():
            self.pna.close_session()
            dpg.add_text('Disconnecting from the PNA...', parent=self._console_window_id)

        if self.frx is not None:
            dpg.add_text("Disconnecting from FRX board...",
                         parent=self._console_window_id)
            self.i2c_receive.close()
        if self.ftx is not None:
            dpg.add_text("Disconnecting from FTX board...",
                         parent=self._console_window_id)
            self.i2c_transmit.close()

