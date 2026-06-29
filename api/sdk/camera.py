from ctypes import *
from api.sdk.datdefs import *

# Camera data feedback event
camera_event = CFUNCTYPE(None, c_void_p, CameraInfo, c_int)

# Focus positioning
def position_focus(device, focus, video_type):
    """
    :param device:      Device handle
    :param focus:       Focus value
    :param video_type:  VT_IRD: Infrared  VT_LIGHT: Visible light
    :return:            Success or failure
    """
    func = prefix + "PositionFocus"
    return eval(func)(device, focus, video_type)

# Zoom positioning
def position_zoom(device, zoom, video_type):
    """
    :param device:      Device handle
    :param zoom:        Zoom value
    :param video_type:  VT_IRD: Infrared  VT_LIGHT: Visible light
    :return:            Success or failure
    """
    func = prefix + "PositionZoom"
    return eval(func)(device, zoom, video_type)

def get_focus(device, video_type, focus):
    """
    :param device:      Device handle
    :param focus:       Focus value
    :param video_type:  VT_IRD: Infrared  VT_LIGHT: Visible light
    :return:            Success or failure
    """
    func = prefix + "GetFocusValue"
    return eval(func)(device, video_type, byref(focus))

def get_zoom(device, video_type, zoom):
    """
    :param device:      Device handle
    :param zoom:        Zoom value
    :param video_type:  VT_IRD: Infrared  VT_LIGHT: Visible light
    :return:            Success or failure
    """
    func = prefix + "GetZoomValue"
    return eval(func)(device, video_type, byref(zoom))

def trigger_auto_focus(device, video_type):
    func = prefix + "TriggerAutoFocus"
    return eval(func)(device, video_type)

def reg_camera_event(device, event, this):
    func = prefix + "RegCameraEvent"
    return eval(func)(device, event, c_void_p(id(this)))
