import dearpygui.dearpygui as dpg
import calibrationroutine as pna


dpg.create_context()
dpg.create_viewport(title='PNA Two-Tone Test', width=1000, height=600)


def start_session():
    if pna.connect_to_pna() == 1:
        dpg.set_value("start_text", "Could not connect to PNA, check USB connection and try again")
        # dpg.add_text('Error connecting to PNA', parent='console')
        return
    else:
        dpg.delete_item("cal_window")
        # dpg.configure_item("modal_id", show=True)
        with dpg.window(label="Menu", tag="menu_window", on_close=close):
            dpg.add_button(label="Noise Floor", callback=noise_floor, tag="noise_floor_button", parent="menu_window")
            dpg.add_button(label="Calibrate", callback=lambda: dpg.configure_item("modal_id", show=True),
                           tag="machine_cal_button", parent="menu_window")
            dpg.add_button(label="Measure", callback=lambda: dpg.configure_item("modal_dut", show=True),
                           tag="start_cycle_button", parent="menu_window")
            dpg.add_button(label="Cancel", callback=end_cycle, tag="end_cycle_button", parent="menu_window")


def close():
    dpg.configure_item("yfac_button", enabled=True)
    dpg.configure_item("cal_button", enabled=True)


def noise_floor(sender):
    dpg.configure_item("noise_floor_button", enabled=False)
    dpg.configure_item("machine_cal_button", enabled=False)
    dpg.configure_item("start_cycle_button", enabled=False)
    dpg.configure_item("end_cycle_button", enabled=False)
    dpg.add_text("Starting the PNA calibration at 0dB...", parent='console')
    pna.noise_floor_cal('C:\\Users\\ckeeler\\Documents\\DSA2000\\TestSoftware\\data\\')
    dpg.add_text("Finished the noise floor measurements.", parent='console')
    dpg.configure_item("noise_floor_button", enabled=True)
    dpg.configure_item("machine_cal_button", enabled=True)
    dpg.configure_item("start_cycle_button", enabled=True)
    dpg.configure_item("end_cycle_button", enabled=True)


def machine_cal(sender):
    power = dpg.get_value("power_level")
    dpg.configure_item("modal_id", show=False)
    dpg.configure_item("noise_floor_button", enabled=False)
    dpg.configure_item("machine_cal_button", enabled=False)
    dpg.configure_item("start_cycle_button", enabled=False)
    dpg.configure_item("end_cycle_button", enabled=False)
    dpg.add_text("Starting the PNA calibration at the user specified power level...", parent='console')
    pna.two_tone_calibration(power)
    dpg.add_text("Finished calibrating the PNA to the user specified level.", parent='console')
    dpg.configure_item("noise_floor_button", enabled=True)
    dpg.configure_item("machine_cal_button", enabled=True)
    dpg.configure_item("start_cycle_button", enabled=True)
    dpg.configure_item("end_cycle_button", enabled=True)


def start_cycle():
    device = dpg.get_value("serial_number")
    frx = dpg.get_value("frx_attenuation")
    ftx = dpg.get_value("ftx_attenuation")
    dpg.configure_item("modal_dut", show=False)
    dpg.configure_item("noise_floor_button", enabled=False)
    dpg.configure_item("machine_cal_button", enabled=False)
    dpg.configure_item("start_cycle_button", enabled=False)
    dpg.configure_item("end_cycle_button", enabled=False)
    # Ask the user for the serial number
    # Ask the user for the filepath
    # TODO: read SN from device
    # TODO: set atten values with i2c
    dpg.add_text("Starting the two-tone measurement for the current device...", parent='console')
    pna.device_measure('C:\\Users\\ckeeler\\Documents\\DSA2000\\TestSoftware\\data\\', device)
    dpg.add_text("Finished the two-tone measurement for the current device.", parent='console')
    dpg.configure_item("noise_floor_button", enabled=True)
    dpg.configure_item("machine_cal_button", enabled=True)
    dpg.configure_item("start_cycle_button", enabled=True)
    dpg.configure_item("end_cycle_button", enabled=True)


def end_cycle():
    # dpg.configure_item("modal_id3", show=False)
    pna.close_session()
    # Close the windows, reset GUI
    dpg.delete_item("menu_window")


cal_window = None

with dpg.window(label="Set Device Attenuation", modal=True, show=False, tag="modal_dut", no_title_bar=True):
    dpg.add_text("Enter the DUT serial number and attenuation:")
    dpg.add_separator()
    dpg.add_input_text(label="Serial Number", default_value='SN01', tag="serial_number")
    dpg.add_input_text(label="FTX Attenuation in dB", default_value='0', tag="ftx_attenuation")
    dpg.add_input_text(label="FRX Attenuation in dB", default_value='0', tag="frx_attenuation")
    dpg.add_button(label="Enter", width=75, callback=start_cycle)

with dpg.window(label="Set Calibration Power", modal=True, show=False, tag="modal_id", no_title_bar=True):
    dpg.add_text("Enter the power level for the calibration:")
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_input_text(label="Power level in dB", default_value='-50', tag="power_level")
        dpg.add_button(label="Enter", width=75, callback=machine_cal)

with dpg.window(label="Calibration", tag="cal_window", on_close=close):
    dpg.add_text("This is the two-tone calibration program.", parent="cal_window")
    dpg.add_text("Ensure USB connection between the computer and PNA, then click Start",
                 parent="cal_window", tag="start_text")
    dpg.add_button(label="START", callback=start_session, tag="start_session", parent="cal_window")

with dpg.window(label='Console', tag='console', width=1000, height=300, pos=[0, 300]):
    dpg.add_text('Welcome to the console', indent=40)

dpg.setup_dearpygui()
dpg.show_viewport()
# TODO: re-enable re-size and adjust the console settings in the callback
dpg.set_viewport_resizable(False)
dpg.set_primary_window("cal_window", True)
dpg.start_dearpygui()
dpg.destroy_context()
