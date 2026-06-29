import ctypes
from ctypes import *

from api.sdk.datdefs import *

class PresetInfo_t(ctypes.Structure):
    _fields_ = [
        ("preset", ctypes.c_int),  # Preset number
        ("name", ctypes.c_char * 100)  # Preset name
    ]

# Set preset
def set_preset(device, preset, name, speed) -> c_bool:
    """
    :param device:  Device handle
    :param preset:  Preset number
    :param name:    Preset name
    :param speed:   Preset speed
    :return:        Success or failure
    """
    func = prefix + "SetPreset"
    return eval(func)(device, preset, c_char_p(name), speed)

# Call preset
def call_preset(device, preset) -> c_bool:
    """
    :param device:   Device handle
    :param preset:   Preset number
    :return:         Success or failure
    """
    func = prefix + "CallPreset"
    return eval(func)(device, preset)

# Clear preset
def clear_preset(device, preset) -> c_bool:
    """
    :param device:   Device handle
    :param preset:   Preset number
    :return:         Success or failure
    """
    func = prefix + "ClearPreset"
    return eval(func)(device, preset)

# Clear all presets
def clear_all_preset(device) -> c_bool:
    """
    :param device:   Device handle
    :return:         Success or failure
    """
    func = prefix + "ClearAllPreset"
    return eval(func)(device)

# Get all presets
def get_presets(device, info, count) -> c_bool:
    """
    :param device:  Device handle
    :param info:    Preset information list
    :param count:   Number of presets
    :return:        Success or failure
    """
    func = prefix + "GetPresets"
    return eval(func)(device, byref(info), byref(count))

# Free acquired preset information
def free_presets(device, info, count) -> c_bool:
    """
    :param device:  Device handle
    :param info:    Preset information list
    :param count:   Number of presets
    :return:        Success or failure
    """
    func = prefix + "FreePresets"
    return eval(func)(device, byref(info), count)
