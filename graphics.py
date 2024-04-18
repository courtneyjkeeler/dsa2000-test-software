import dearpygui.dearpygui as dpg
#from dearpygui_ext.logger import mvLogger

dpg.create_context()
dpg.create_viewport(title='PNA and SA Scripted Programs', width=600, height=300)


def start_calibration():
    dpg.delete_item("cal_window", children_only=True, slot=1)
    print("Cool")


def close():
    dpg.configure_item("yfac_button", enabled=True)
    dpg.configure_item("cal_button", enabled=True)


def button_callback(sender):
    dpg.configure_item("yfac_button", enabled=False)
    dpg.configure_item("cal_button", enabled=False)
    if sender == "cal_button":
        with dpg.window(label="Calibration", tag="cal_window", on_close=close):
            dpg.add_text("This is the two-tone calibration program.", parent="cal_window")
            dpg.add_text("Ensure USB connection between the computer and PNA, then click Start", parent="cal_window")
            dpg.add_button(label="START", callback=start_calibration, tag="start_cal", parent="cal_window")
    if sender == "yfac_button":
        with dpg.window(label="Y-Factor", tag="yfac_window"):
            dpg.add_text("This is the Y-factor measurement program")


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
