from ctypes import *
from api.sdk.datdefs import *

# Turntable control
def control_move(device, ptz_type, move, speed, speedV, video_type) -> c_bool:
    """
    :param device:      Device handle
    :param ptz_type:    Control type
    :param move:        Whether to rotate
    :param speed:       Value range: 1-63
    :param speedV:      Pitch speed: 1-63
    :param video_type:  VT_IRD: Thermal imaging  VT_LIGHT: Visible light (for single IP device use)
    :return:            Success or failure
    """
    func = prefix + "ControlMove"
    return eval(func)(device, ptz_type, move, speed, speedV, video_type)

# Camera control
def camera_move(device, camera_type, move, video_type) -> c_bool:
    """
    :param device:      Device handle
    :param camera_type: Control type
    :param move:        Whether to rotate
    :param video_type:  VT_IRD: Thermal imaging  VT_LIGHT: Visible light (for single IP device use)
    :return:            Success or failure
    """
    func = prefix + "CameraMove"
    return eval(func)(device, camera_type, move, video_type)
