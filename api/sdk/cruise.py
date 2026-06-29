from ctypes import *

from api.sdk.datdefs import *

# Scan control
def control_scan(device, scan_type, ctrl_type, path) -> c_bool:
    """
    :param device:      Device handle
    :param scan_type:   Scan type
    :param ctrl_type:   Control type
    :param path:        The x-th scan line
    :return:            Success or failure
    """
    func = prefix + "ControlScan"
    return eval(func)(device, scan_type, ctrl_type, path)

# Get scan status
def get_scan_state(device, state) -> c_bool:
    """
    :param device:      Device handle
    :param state:       Scan status
    :return:            Success or failure
    """
    func = prefix + "GetScanState"
    return eval(func)(device, state)

# Set cruise path preset information
def set_cruise_path(device, path, presets, count) -> c_bool:
    """
    :param device:      Device handle
    :param path:        The x-th scan line
    :param presets:     Cruise path preset information
    :param count:       Number of cruise path presets
    :return:            Success or failure
    """
    func = prefix + "SetCruisePath"
    return eval(func)(device, path, presets, count)
