import dearpygui.dearpygui as dpg
import calibrationroutine as pna


dpg.create_context()
dpg.create_viewport(title='PNA and SA Scripted Programs', width=600, height=300)


def start_calibration():
    if pna.connect_to_pna() == 1:
        dpg.set_value("start_text", "Could not connect to PNA, check USB connection and try again")
        # print("Could not connect to PNA, try again")
        return
    else:
        dpg.delete_item("cal_window", children_only=True, slot=1)
        dpg.configure_item("modal_id", show=True)


def close():
    dpg.configure_item("yfac_button", enabled=True)
    dpg.configure_item("cal_button", enabled=True)


def button_callback(sender):
    dpg.configure_item("yfac_button", enabled=False)
    dpg.configure_item("cal_button", enabled=False)
    if sender == "cal_button":
        global cal_window
        if cal_window is not None:
            dpg.delete_item(cal_window)
            cal_window = None
        with dpg.window(label="Calibration", tag="cal_window", on_close=close) as cal_window:
            dpg.add_text("This is the two-tone calibration program.", parent="cal_window")
            dpg.add_text("Ensure USB connection between the computer and PNA, then click Start",
                         parent="cal_window", tag="start_text")
            dpg.add_button(label="START", callback=start_calibration, tag="start_cal", parent="cal_window")
    if sender == "yfac_button":
        with dpg.window(label="Y-Factor", tag="yfac_window"):
            dpg.add_text("This is the Y-factor measurement program")


def noise_floor(sender):
    dpg.configure_item("modal_id", show=False)
    pna.noise_floor_cal('C:\\Users\\ckeeler\\Documents\\DSA2000\\TestSoftware\\data\\')


def no_noise_floor(sender):
    dpg.configure_item("modal_id", show=False)
    dpg.configure_item("modal_id2", show=True)


def machine_cal(sender):
    dpg.configure_item("modal_id2", show=False)
    pna.two_tone_calibration("-50")
    dpg.configure_item("modal_id3", show=True)


def no_machine_cal(sender):
    dpg.configure_item("modal_id2", show=False)
    dpg.configure_item("modal_id3", show=True)


def start_cycle():
    device = dpg.get_value("serial_num")
    dpg.configure_item("modal_id3", show=False)
    # Ask the user for the serial number
    # Ask the user for the filepath
    pna.device_measure('C:\\Users\\ckeeler\\Documents\\DSA2000\\TestSoftware\\data\\', device)

    # Ask if there's another device
    # If yes, repeat the cycle
    # If no, close out the session


def end_cycle():
    dpg.configure_item("modal_id3", show=False)
    pna.close_session()
    # Close the windows, reset GUI
    dpg.delete_item("cal_window")


cal_window = None


with dpg.window(label="Select Calibration", modal=True, show=False, tag="modal_id3", no_title_bar=True):
    dpg.add_text("Enter the serial number of the DUT:")
    dpg.add_separator()
    dpg.add_input_text(label="Serial Number", default_value='SN01', tag="serial_num")
    with dpg.group(horizontal=True):
        dpg.add_button(label="Measure", width=75, callback=start_cycle)
        dpg.add_button(label="Cancel", width=75, callback=end_cycle)


with dpg.window(label="Select Calibration", modal=True, show=False, tag="modal_id2", no_title_bar=True):
    dpg.add_text("Would you like to calibrate the PNA?")
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_button(label="Yes", width=75, callback=machine_cal)
        dpg.add_button(label="No", width=75, callback=no_machine_cal)


with dpg.window(label="Select Calibration", modal=True, show=False, tag="modal_id", no_title_bar=True):
    dpg.add_text("Would you like to calibrate the noise floor of the PNA?")
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_button(label="Yes", width=75, callback=noise_floor)
        dpg.add_button(label="No", width=75, callback=no_noise_floor)

with dpg.window(label="Program Selection",tag="Primary Window"):
    dpg.add_text("Choose from the options below")
    dpg.add_button(label="Two Tone Calibration", callback=button_callback, tag="cal_button")
    dpg.add_button(label="Y-factor Measurement", callback=button_callback, tag="yfac_button")
    dpg.add_button(label="Dielectric Measurement")

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("Primary Window", True)
dpg.start_dearpygui()
dpg.destroy_context()
