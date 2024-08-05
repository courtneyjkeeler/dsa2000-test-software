import dearpygui.dearpygui as dpg
import usb.core
import usb.util
from pyftdi.i2c import I2cController, I2cIOError
from ftx_ctl.ftx import FTX
from ftx_ctl.frx import FRX
import time
from pna import PNA, handle_callbacks_and_render_one_frame
import binascii
import numpy as np


def add_text_to_console(msg) -> None:
    dpg.add_text(msg, parent="console_window")
    dpg.set_y_scroll("console_window", dpg.get_y_scroll_max("console_window"))


def is_pna_connected():
    # If connected is true, the disconnect button is enabled
    state = dpg.get_item_configuration("disconnect_button")
    return state.get("enabled")


def clear_graph():
    dpg.delete_item("y_axis", children_only=True, slot=1)
    dpg.delete_item("iip2 y_axis", children_only=True, slot=1)
    dpg.delete_item("oip2 y_axis", children_only=True, slot=1)
    dpg.delete_item("oip3 y_axis", children_only=True, slot=1)


class UserInterface:
    VID = 0x0403
    PID = 0x6048

    def __init__(self):
        self._console_window_id = 0
        self.i2c_transmit = None
        self.ftx = None
        self.i2c_receive = None
        self.frx = None
        self.pna = None
        self._lna_current_id = 0
        self._laserpd_mon_id = 0
        self._ftx_sn_id = 0
        self._ftx_rfmon_id = 0
        self._frx_rfmon_id = 0
        self._pd_current_id = 0
        self._frx_sn_id = 0
        self._temp_id = 0
        self.comments = ""
        self.opt_attn = "None"

    def run(self):
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
        ti = dpg.get_total_time()
        while dpg.is_dearpygui_running():
            tf = dpg.get_total_time()
            if (tf - ti) > 1:  # approx 1 second intervals
                ti = tf
                self._timer_callback()
            handle_callbacks_and_render_one_frame()
        dpg.destroy_context()

    def _timer_callback(self) -> None:
        """Timer callback that runs approx every 1 second.

        If the frx or ftx is connected, this will refresh the
        monitor data"""
        if self.frx is not None:
            self._update_mon_frx()

        if self.ftx is not None:
            self._update_mon_ftx()

    def connect_pna(self):
        #  Connect to the PNA
        if self.pna is None:
            self.pna = PNA()
        if self.pna.connect_to_pna() == 0:
            # Send *IDN? and read the response
            idn = self.pna.get_idn()
            dpg.add_text('Connection successful: %s' % idn.rstrip('\n'), parent=self._console_window_id)
            #  If no errors, show the disconnect button
            dpg.configure_item("connect_button", show=False, enabled=False)
            dpg.configure_item("disconnect_button", show=True, enabled=True)
            #  Enable calibration
            dpg.configure_item("start_cal_button", enabled=True)
            #  Enable starting a measurement
            dpg.configure_item("start_measure_button", enabled=True)
        else:
            dpg.add_text('Couldn\'t connect to \'%s\', exiting now...' % self.pna.VISA_ADDRESS,
                         parent=self._console_window_id)

    def disconnect_pna(self):
        #  Disconnect from the PNA
        self.pna.close_session()
        dpg.add_text('Disconnected from the PNA.', parent=self._console_window_id)
        #  If no errors, show the connect button
        dpg.configure_item("connect_button", show=True, enabled=True)
        dpg.configure_item("disconnect_button", show=False, enabled=False)
        #  Disable calibration
        dpg.configure_item("start_cal_button", enabled=False)
        #  Disable starting a measurement
        dpg.configure_item("start_measure_button", enabled=False)

    def start_calibration(self):
        dpg.add_text('Starting the calibration routine...', parent=self._console_window_id)
        self.pna.calibration(str(dpg.get_value("cal_input")))
        dpg.add_text('Finished receiver power calibration.', parent=self._console_window_id)

    def start_measurement(self):
        # TODO: what if we start a measurement from a pre-calibrated machine
        dpg.add_text("Starting two-tone measurement...", parent=self._console_window_id)
        self.pna.two_tone_test(dpg.get_value("cal_input"))
        if self.pna.x_axis is not None:
            dpg.configure_item("gain plot", show=True)
            dpg.add_line_series(self.pna.x_axis, self.pna.gain, parent="y_axis")
            dpg.configure_item("IIP2 plot", show=True)
            dpg.add_line_series(self.pna.x_axis, self.pna.IIp2, parent="iip2 y_axis")
            dpg.configure_item("OIP2 plot", show=True)
            dpg.add_line_series(self.pna.x_axis, self.pna.OIP2, parent="oip2 y_axis")
            dpg.configure_item("OIP3 plot", show=True)
            dpg.add_line_series(self.pna.x_axis, self.pna.OIP3, parent="oip3 y_axis")

    def _connect_frx(self, sender=None, data=None) -> None:
        """Callback for clicking the frx connect button.

        Calls the configure function on the I2C ports.
        """
        self.i2c_receive = I2cController()
        # dev = usb.core.find(idVendor=0x0403, idProduct=0x6048)
        dev = usb.core.find(idVendor=1027, idProduct=24592)  # Tigard
        if dev is None:
            add_text_to_console('USB Device not found!')
            return
        try:
            # self.i2c_receive.configure(dev, interface=1)
            self.i2c_receive.configure(dev, interface=2)
            self.frx = FRX(self.i2c_receive)
        except I2cIOError:
            # Log the error to the console
            add_text_to_console("Could not connect to FRX board, check connection and try again.")
            return

        add_text_to_console("Connected to the FRX board. Control fields are now enabled.")

        dpg.configure_item("frx_connect_button", show=False)
        dpg.configure_item("frx_disconnect_button", show=True)
        # Enable all the control inputs
        dpg.configure_item("frx_output_attn", enabled=True)

        # dpg.configure_item(self._frx_sn_id, color=(255, 255, 255))
        # dpg.configure_item(self._frx_rfmon_id, color=(255, 255, 255))
        # dpg.configure_item(self._pd_current_id, color=(255, 255, 255))
        # dpg.configure_item(self._temp_id, color=(255, 255, 255))

        self._update_all_frx()

    def _disconnect_frx(self, sender=None, data=None) -> None:
        """Callback for clicking the frx disconnect button.

        Calls the disconnect function on the SA to terminate the session.
        """
        dpg.configure_item("frx_connect_button", show=True)
        dpg.configure_item("frx_disconnect_button", show=False)
        self.i2c_receive.close()
        self.frx = None
        add_text_to_console("FRX board connection closed. OK to unplug.")
        # Disable all the settings inputs
        dpg.configure_item("frx_output_attn", enabled=False)
        # dpg.configure_item(self._frx_sn_id, color=(37, 37, 37))
        # dpg.configure_item(self._frx_rfmon_id, color=(37, 37, 37))
        # dpg.configure_item(self._pd_current_id, color=(37, 37, 37))
        # dpg.configure_item(self._temp_id, color=(37, 37, 37))

    def _update_frx_attn(self) -> None:
        new_value = dpg.get_value("frx_output_attn")
        self.frx.set_atten(int(new_value * 4))
        add_text_to_console("Setting output attenuation to " + str(new_value) + "...")
        time.sleep(0.1)
        set_value = self.frx.atten.read() / 4
        dpg.set_value("frx_output_attn", set_value)

        if new_value != set_value:
            add_text_to_console("**WARNING** Value input: " + str(round(new_value, 2)) + ", value set: " +
                                str(set_value) + ".")

    def _update_all_frx(self) -> None:
        """ Reads all the monitor data and updates the
            display accordingly
        """
        add_text_to_console("Reading FRX RF monitor...")
        # dpg.set_value(self._frx_rfmon_id, str(self.frx.get_rms_power()))
        add_text_to_console("Reading FRX PD current...")
        # dpg.set_value(self._pd_current_id, str(self.frx.get_pd_current()))
        add_text_to_console("Reading FRX UUID...")
        dpg.set_value(self._frx_sn_id, binascii.hexlify(self.frx.get_uuid()).decode('ascii'))
        add_text_to_console("Reading FRX temperature...")
        # dpg.set_value(self._temp_id, str(self.frx.get_temp()))
        add_text_to_console("Reading output attenuation value...")
        dpg.set_value("frx_output_attn", self.frx.atten.read() / 4)

    def _update_mon_frx(self) -> None:
        """ Reads all the monitor data and updates the
            display accordingly. Called every 1 second.
        """
        # dpg.set_value(self._frx_rfmon_id, str(self.frx.get_rms_power()))
        # dpg.set_value(self._pd_current_id, str(self.frx.get_pd_current()))
        dpg.set_value(self._frx_sn_id, binascii.hexlify(self.frx.get_uuid()).decode('ascii'))
        # dpg.set_value(self._temp_id, str(self.frx.get_temp()))
        # dpg.set_value("frx_output_attn", self.frx.atten.read() / 4)

    def _connect_ftx(self, sender=None, data=None) -> None:
        """Callback for clicking the connect button.

        Calls the configure function on the I2C ports.
        """

        # dev = usb.core.find(idVendor=0x0403, idProduct=0x6048)  # Custom
        dev = usb.core.find(idVendor=1027, idProduct=24592)  # Tigard
        if dev is None:
            add_text_to_console("Could not find the USB device, check connection and try again.")
            # dpg.add_text("Could not find the USB device, check connection and try again.",
            #              parent="console_window")
            return

        self.i2c_transmit = I2cController()
        try:
            self.i2c_transmit.configure(dev, interface=2)
            self.ftx = FTX(self.i2c_transmit)
        except I2cIOError:
            # Log the error to the console
            add_text_to_console("Could not connect to FTX board, check connection and try again.")
            # dpg.add_text("Could not connect to FTX board, check connection and try again.",
            #              parent="console_window")
            return

        add_text_to_console("Connected to the FTX board. Control fields are now enabled.")
        # dpg.add_text("Connected to the FTX board. Control fields are now enabled.",
        #              parent="console_window")
        dpg.configure_item("ftx_connect_button", show=False)
        dpg.configure_item("ftx_disconnect_button", show=True)
        # Enable all the control inputs
        dpg.configure_item("lna_bias_checkbox", enabled=True)
        dpg.configure_item("ftx_input_attn", enabled=True)
        dpg.configure_item("ftx_laser_current", enabled=True)

        # dpg.configure_item(self._ftx_sn_id, color=(255, 255, 255))
        # dpg.configure_item(self._ftx_rfmon_id, color=(255, 255, 255))
        # # dpg.configure_item(self._lna_current_id, color=(255, 255, 255))
        # # dpg.configure_item(self._laser_current_id, color=(255, 255, 255))
        # dpg.configure_item(self._laserpd_mon_id, color=(255, 255, 255))

        self._update_all_ftx()

    def _disconnect_ftx(self, sender=None, data=None) -> None:
        """Callback for clicking the disconnect button.

        Calls the disconnect function on the SA to terminate the session.
        """
        dpg.configure_item("ftx_connect_button", show=True)
        dpg.configure_item("ftx_disconnect_button", show=False)
        self.i2c_transmit.close()
        # dpg.add_text("FTX board connection closed. OK to unplug.",
        #              parent="console_window")
        add_text_to_console("FTX board connection closed. OK to unplug.")
        self.ftx = None
        # Disable all the settings inputs
        dpg.configure_item("lna_bias_checkbox", enabled=False)
        dpg.configure_item("ftx_input_attn", enabled=False)
        dpg.configure_item("ftx_laser_current", enabled=False)
        # dpg.configure_item(self._ftx_sn_id, color=(37, 37, 37))
        # dpg.configure_item(self._ftx_rfmon_id, color=(37, 37, 37))
        # dpg.configure_item(self._lna_current_id, color=(37, 37, 37))
        # # dpg.configure_item(self._laser_current_id, color=(37, 37, 37))
        # dpg.configure_item(self._laserpd_mon_id, color=(37, 37, 37))

    def _update_mon_ftx(self) -> None:
        """ Reads all the monitor data and updates the
            display accordingly
        """
        if dpg.get_value("lna_bias_checkbox"):
            dpg.set_value(self._lna_current_id, str(self.ftx.get_ld_current()))
        dpg.set_value(self._laserpd_mon_id, str(self.ftx.get_pd_current()))
        dpg.set_value(self._ftx_sn_id, binascii.hexlify(self.ftx.get_uuid()).decode('ascii'))
        dpg.set_value(self._ftx_rfmon_id, str(self.ftx.get_rms_power()))

    def _update_all_ftx(self) -> None:
        """ Reads all the monitor data and updates the
            display accordingly
        """
        if dpg.get_value("lna_bias_checkbox"):
            add_text_to_console("Reading FTX LNA current...")
            dpg.set_value(self._lna_current_id, str(self.ftx.get_ld_current()))
        add_text_to_console("Reading FTX laser current...")
        dpg.set_value("ftx_laser_current", self.ftx.get_ld_current())
        add_text_to_console("Reading FTX PD current...")
        dpg.set_value(self._laserpd_mon_id, str(self.ftx.get_pd_current()))
        add_text_to_console("Reading FTX UUID...")
        dpg.set_value(self._ftx_sn_id, binascii.hexlify(self.ftx.get_uuid()).decode('ascii'))
        add_text_to_console("Reading FTX RF monitor...")
        dpg.set_value(self._ftx_rfmon_id, str(self.ftx.get_rms_power()))
        add_text_to_console("Reading input attenuation value...")
        dpg.set_value("ftx_input_attn", self.ftx.atten.read() / 4)

    def _update_ftx_attn(self) -> None:
        new_value = dpg.get_value("ftx_input_attn")
        self.ftx.set_atten(int(new_value*4))
        add_text_to_console("Setting input attenuation to " + str(new_value) + "...")
        time.sleep(0.1)
        set_value = self.ftx.atten.read()/4
        dpg.set_value("ftx_input_attn", set_value)

        if new_value != set_value:
            add_text_to_console("**WARNING** Value input: "+str(round(new_value, 2))+", value set: "+str(set_value)+".")

    def _update_ftx_laser(self) -> None:
        new_value = dpg.get_value("ftx_laser_current")
        self.ftx.set_ld_current(int((new_value/50)*255))
        add_text_to_console("Setting laser current to " + str(new_value) + "...")
        time.sleep(0.1)
        set_value = self.ftx.get_ld_current()
        dpg.set_value("ftx_laser_current", set_value)

        if new_value != set_value:
            add_text_to_console("**WARNING** Value input: "+str(round(new_value, 2))+", value set: "+str(set_value)+".")

    def _lna_bias_checked(self, sender) -> None:
        """ Callback for when the lna bias enable checkbox is clicked.

        If turned on, sends the lna bias enable command
        If turned off, sends the lna bias disable command
        """
        value = dpg.get_value(sender)
        self.ftx.set_lna_power(value)
        if value:
            add_text_to_console("LNA bias enabled.")
            # dpg.add_text("LNA bias enabled.", parent="console_window")
            # dpg.configure_item(self._lna_current_id, color=(255, 255, 255))
            dpg.set_value(self._lna_current_id, str(self.ftx.get_ld_current()))
        else:
            add_text_to_console("LNA bias disabled.")
            # dpg.add_text("LNA bias disabled.", parent="console_window")
            # dpg.configure_item(self._lna_current_id, color=(37, 37, 37))

    def _show_popup_window(self, sender=None, data=None, user_data=None) -> None:
        """Callback for when certain buttons are clicked.

        Displays a small popup window with a message and button to indicate users are
        ready.
        """
        message = user_data.get("msg", None)
        if message is None:
            return
        if dpg.does_item_exist("blocking_popup"):
            dpg.configure_item("blocking_popup", width=250, height=100,
                               pos=((dpg.get_viewport_width() - 150) // 2, (dpg.get_viewport_height() - 50) // 2))
            dpg.configure_item("blocking_popup", show=True)
            dpg.set_value("blocking_popup_text", message)
            if message == "Add comments below:":
                if self.comments == "":
                    dpg.set_value('multiline_input', 'Fiber Length:\nBias T direct to laser\nLaser SN:\n'
                                  + 'Laser current:\nLaser wavelength:\nBias T direct to PD\nPD SN:\nPD current:')
                else:
                    dpg.set_value('multiline_input', self.comments)
            else:
                dpg.set_value('multiline_input', self.opt_attn)
            dpg.set_item_user_data("blocking_popup_button", user_data)
            return
        with dpg.window(tag="blocking_popup", width=150, height=50,
                        pos=((dpg.get_viewport_width() - 150) // 2, (dpg.get_viewport_height() - 50) // 2)):
            dpg.add_text(message, tag="blocking_popup_text")
            dpg.add_input_text(multiline=True, tag='multiline_input')
            if message == "Add comments below:":
                if self.comments == "":
                    dpg.set_value('multiline_input', 'Fiber Length:\nBias T direct to laser\nLaser SN:\n'
                                  + 'Laser current:\nLaser wavelength:\nBias T direct to PD\nPD SN:\nPD current:')
                else:
                    dpg.set_value('multiline_input', self.comments)
            else:
                dpg.set_value('multiline_input', self.opt_attn)
            dpg.add_button(label="OK", tag="blocking_popup_button", user_data=user_data,
                           callback=self._save_comments)

    def _save_comments(self, sender=None, data=None, user_data=None) -> None:
        message = user_data.get("msg", None)
        if message == "Add comments below:":
            self.comments = dpg.get_value('multiline_input')
        else:
            self.opt_attn = dpg.get_value('multiline_input')
        dpg.delete_item('blocking_popup')

    def _save_callback(self, sender, app_data) -> None:
        self.save_measurement(app_data.get('file_path_name'))

    def save_measurement(self, filepath):
        with open(filepath, 'w') as f:
            f.write('Two-Tone Test Report\n')
            f.write('Date,' + time.strftime("%m/%d/%Y", time.localtime()) + '\n')
            f.write('Time,' + time.strftime("%H:%M:%S", time.localtime()) + '\n')
            f.write('Optical Attenuation,' + self.opt_attn + '\n')
            f.write('Comments,' + self.comments + '\n')
            f.write('\n')
            if self.ftx is not None:
                f.write('FTX, Value, Units, Mon/Cmd\n')
                if dpg.get_value("lna_bias_checkbox"):
                    msg = 'ON'
                else:
                    msg = 'OFF'
                f.write('LNA Bias Enable,' + msg + ',,Cmd\n')
                if dpg.get_value("lna_bias_checkbox"):
                    f.write('LNA Current,' + dpg.get_value(self._lna_current_id) + ',mA,Mon\n')
                else:
                    f.write('LNA Current,N/A,mA,Mon\n')
                f.write('RF Monitor,' + dpg.get_value(self._ftx_rfmon_id) + ',dBm,Mon\n')
                f.write('Input Attenuation,' + str(dpg.get_value("ftx_input_attn")) + ',dB,Cmd\n')
                f.write('Laser Current,' + str(dpg.get_value("ftx_laser_current")) + ',mA,Cmd\n')
                f.write('PD Current,' + dpg.get_value(self._laserpd_mon_id) + ',mA,Mon\n')
                f.write('FTX SN,' + dpg.get_value(self._ftx_sn_id) + ',,Mon\n')
                f.write('\n')
            else:
                f.write('No FTX connected\n\n\n\n\n\n\n\n')
            if self.frx is not None:
                f.write('FRX, Value, Units, Mon/Cmd\n')
                f.write('PD Current,' + dpg.get_value(self._pd_current_id) + ',mA,Mon\n')
                f.write('RF Monitor,' + dpg.get_value(self._frx_rfmon_id) + ',dBm,Mon\n')
                f.write('Output Attenuation,' + str(dpg.get_value("frx_output_attn")) + ',dB,Cmd\n')
                f.write('Temperature,' + dpg.get_value(self._temp_id) + ',degC,Mon\n')
                f.write('FRX SN,' + dpg.get_value(self._frx_sn_id) + ',,Mon\n')
                f.write('\n')
            else:
                f.write('No FRX connected\n\n\n\n\n\n')
            f.write('PNA calibration power\n')
            f.write(str(dpg.get_value("cal_input")) + '\n')
            # TODO: update for multiple runs of data
            f.write(
                'Frequency (GHz),PL Log Mag(dBm),PH Log Mag(dBm),IM2 Log Mag(dBm),IM3L Log Mag(dBm),IM3H Log Mag(dBm),'
                'OIP2,OIP3,Gain,IIP2,IIP3\n')
            np.savetxt(f, np.array(list(zip(self.pna.x_axis, self.pna.primary_low, self.pna.primary_high,
                                            self.pna.second_intermod, self.pna.third_intermod_low,
                                            self.pna.third_intermod_high, self.pna.OIP2, self.pna.OIP3, self.pna.gain,
                                            self.pna.IIp2, self.pna.IIp3))), delimiter=',', fmt='%f')

    def _make_gui(self):
        with dpg.file_dialog(directory_selector=False, show=False, callback=self._save_callback,
                             tag="save_as_dialog_id", width=700, height=400):
            dpg.add_file_extension(".csv", color=(0, 255, 0, 255), custom_text="[CSV]")

        with dpg.window(label="Two Tone Test Program", tag="primary_window"):
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(label="Save Data", callback=lambda: dpg.show_item("save_as_dialog_id"))
                    with dpg.menu(label="Add..."):
                        dpg.add_menu_item(label="Optical Attn", callback=self._show_popup_window, check=True,
                                          user_data={'msg': "Enter the optical attenuation in dB:"})
                        dpg.add_menu_item(label="Comments", callback=self._show_popup_window,
                                          user_data={'msg': "Add comments below:"})
            with dpg.tab_bar(tag="tabs"):
                self._make_pna_tab()
                self._make_usb_tab()

    def _make_pna_tab(self):
        """Create the layout for the PNA tab."""
        with dpg.tab(label="PNA", tag="pna_tab"):
            with dpg.group(horizontal=True):
                with dpg.group(label="left side"):
                    with dpg.child_window(label="connection_window", height=100, width=200):
                        dpg.add_text("PNA Connection Control")
                        dpg.add_button(label="Connect", tag="connect_button", enabled=True, show=True,
                                       callback=self.connect_pna, indent=55, width=60)
                        dpg.add_button(label="Disconnect", tag="disconnect_button", enabled=False, show=False,
                                       callback=self.disconnect_pna, indent=35, width=100)
                    with dpg.child_window(label="calibration_window", height=150, width=200):
                        dpg.add_text("Re-Calibrate PNA")
                        dpg.add_spacer()
                        dpg.add_text("Source Power (dBm)")
                        dpg.add_input_float(tag="cal_input", step=0, on_enter=True,
                                            callback=lambda: print('Check if input is valid'), min_value=-50,
                                            min_clamped=True, max_value=10, max_clamped=True)
                        dpg.add_spacer(height=10)
                        dpg.add_button(label="Start", tag="start_cal_button", enabled=False,
                                       callback=self.start_calibration, indent=55, width=60)
                    with dpg.child_window(label="measurement_window", height=100, width=200):
                        dpg.add_button(label="Measure", tag="start_measure_button", enabled=False,
                                       callback=self.start_measurement, indent=55, width=60)
                        dpg.add_button(label="Clear", tag="clear_graph_button", enabled=True,
                                       callback=clear_graph, indent=55, width=60)
                with dpg.group(label='right side'):
                    with dpg.child_window(label="console_window", height=200, width=750) as self._console_window_id:
                        dpg.add_text("Welcome to the console for the two tone test program.")
                        dpg.add_text("Check here for status messages and important setup instructions.")
                        dpg.add_text("Begin by connecting to the PNA and (optionally) DUT.")
                    with dpg.child_window(tag="graph_window", width=750, height=400):
                        with dpg.plot(tag="gain plot", width=690, height=300, show=False):
                            dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (GHz)")
                            dpg.add_plot_axis(dpg.mvYAxis, label="Gain (dB)", tag="y_axis")
                        with dpg.plot(tag="IIP2 plot", width=690, height=300, show=False):
                            dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (GHz)")
                            dpg.add_plot_axis(dpg.mvYAxis, label="IIP2 (dBm)", tag="iip2 y_axis")
                        with dpg.plot(tag="OIP2 plot", width=690, height=300, show=False):
                            dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (GHz)")
                            dpg.add_plot_axis(dpg.mvYAxis, label="OIP2 (dBm)", tag="oip2 y_axis")
                        with dpg.plot(tag="OIP3 plot", width=690, height=300, show=False):
                            dpg.add_plot_axis(dpg.mvXAxis, label="Frequency (GHz)")
                            dpg.add_plot_axis(dpg.mvYAxis, label="OIP3 (dBm)", tag="oip3 y_axis")

    def _make_usb_tab(self):
        """Create the layout for the USB-I2C control tab."""
        with dpg.tab(label="USB-I2C", tag="usb_tab"):
            with dpg.group(label="overall", horizontal=True):
                with dpg.group(label="left_side"):
                    with dpg.child_window(tag="FTX", width=400, height=440):
                        with dpg.group(tag="ftx_settings_group"):
                            dpg.add_text("FTX", pos=[195, 5])
                            with dpg.group(tag="ftx_connect_buttons_group", horizontal=True):
                                dpg.add_button(label="Connect", tag="ftx_connect_button", callback=self._connect_ftx,
                                               pos=[180, 30])
                                dpg.add_button(label="Disconnect", tag="ftx_disconnect_button",
                                               callback=self._disconnect_ftx, show=False, pos=[180, 30])
                            dpg.add_text("LNA Bias Enable")#, color=(37, 37, 37))
                            dpg.add_checkbox(label="", tag="lna_bias_checkbox", enabled=False,
                                             callback=self._lna_bias_checked)
                            dpg.add_spacer()
                            dpg.add_text("LNA Current (mA)")#, color=(37, 37, 37))
                            self._lna_current_id = dpg.add_text("0.0", tag="ftx_lna_current")#, color=(69, 69, 69))
                            dpg.add_spacer()
                            dpg.add_text("RF Monitor (dBm)")#, color=(37, 37, 37))
                            self._ftx_rfmon_id = dpg.add_text("0.0", tag="ftx_rf_mon")#, color=(69, 69, 69))
                            dpg.add_spacer()
                            dpg.add_text("Input Attenuation (dB)")#, color=(37, 37, 37))
                            dpg.add_input_float(tag="ftx_input_attn", enabled=False, default_value=0, max_value=31.25,
                                                min_value=0, step=0.25, callback=self._update_ftx_attn, on_enter=True,
                                                min_clamped=True, max_clamped=True, format='%.2f')
                            dpg.add_spacer()
                            dpg.add_text("Laser Current (mA)")#, color=(37, 37, 37))
                            dpg.add_input_float(tag="ftx_laser_current", enabled=False, default_value=25, max_value=50,
                                                min_value=0, step=0.25, callback=self._update_ftx_laser, on_enter=True,
                                                min_clamped=True, max_clamped=True, format='%.2f')
                            dpg.add_spacer()
                            dpg.add_text("Photodiode Current (mA)")#, color=(37, 37, 37))
                            self._laserpd_mon_id = dpg.add_text("0.0", tag="ftx_laserpd_mon")#, color=(69, 69, 69))
                            dpg.add_spacer()
                            dpg.add_text("Serial Number")#, color=(37, 37, 37))
                            self._ftx_sn_id = dpg.add_text("0x0000", tag="ftx_sn")#, color=(69, 69, 69))
                            dpg.add_spacer()
                with dpg.group(label="right_side"):
                    with dpg.child_window(tag="FRX", width=400, height=440):
                        with dpg.group(tag="frx_settings_group"):
                            dpg.add_text("FRX", pos=[195, 5])
                            with dpg.group(tag="frx_connect_buttons_group", horizontal=True):
                                dpg.add_button(label="Connect", tag="frx_connect_button", callback=self._connect_frx,
                                               pos=[180, 30])
                                dpg.add_button(label="Disconnect", tag="frx_disconnect_button",
                                               callback=self._disconnect_frx, show=False, pos=[180, 30])
                            dpg.add_text("Photodiode Current (mA)")#, color=(37, 37, 37))
                            self._pd_current_id = dpg.add_text("0.0", tag="frx_pd_current")#, color=(69, 69, 69))
                            dpg.add_spacer()
                            dpg.add_text("RF Monitor (dBm)")#, color=(37, 37, 37))
                            self._frx_rfmon_id = dpg.add_text("0.0", tag="frx_rf_mon")#, color=(69, 69, 69))
                            dpg.add_spacer()
                            dpg.add_text("Output Attenuation (dB)")#, color=(37, 37, 37))
                            dpg.add_input_float(tag="frx_output_attn", enabled=False, default_value=0, max_value=31.25,
                                                min_value=0, step=0.25, on_enter=True, callback=self._update_frx_attn,
                                                min_clamped=True, max_clamped=True, format='%.2f')
                            dpg.add_spacer()
                            dpg.add_text("Temperature (C)")#, color=(37, 37, 37))
                            self._temp_id = dpg.add_text("0.0", tag="frx_temp")#, color=(69, 69, 69))
                            dpg.add_spacer()
                            dpg.add_text("Serial Number")#, color=(37, 37, 37))
                            self._frx_sn_id = dpg.add_text("0x0000", tag="frx_sn")#, color=(69, 69, 69))
                            dpg.add_spacer()
            with dpg.child_window(tag="console_window", width=810, height=110):
                dpg.add_text("Welcome to the console.")
                dpg.add_text("Connect to the RF over Fiber boards to begin.")

    def _exit_callback(self):
        if is_pna_connected():
            self.pna.close_session()
            dpg.add_text('Disconnecting from the PNA...', parent=self._console_window_id)

        if self.frx is not None:
            dpg.add_text("Disconnecting from FRX board...",
                         parent=self._console_window_id)
            self.i2c_receive.close()
            self.frx = None
        if self.ftx is not None:
            dpg.add_text("Disconnecting from FTX board...",
                         parent=self._console_window_id)
            self.i2c_transmit.close()
            self.ftx = None

