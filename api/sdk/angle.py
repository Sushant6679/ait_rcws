from ctypes import *
from api.sdk.datdefs import *

# Angular Callback Event
angle_event = CFUNCTYPE(None, c_void_p, c_double, c_double)


# Hor Angle Positioning
def position_x(device, angle, speed) -> c_bool:
    """
    :param device: device handle
    :param angle: horizontal angle
    :param speed: angle positioning speed, speed range: 0~63
    :return: success or failure
    """
    func = prefix + "PositionX"
    return eval(func)(device, angle, speed)


# Pitch Angle Positioning
def position_y(device, angle, speed) -> c_bool:
    """
    :param device: device handle
    :param angle: pitch angle
    :param speed: angle positioning speed, speed range: 0~63
    :return: success or failure
    """
    func = prefix + "PositionY"
    return eval(func)(device, angle, speed)


# Horizontal pitch angle positioning
def position_xy(device, angle_x, angle_y, speed) -> c_bool:
    """
    :param device: device handle
    :param angle_x: horizontal angle
    :param angle_y: pitch angle
    :param speed: angle positioning speed, speed range: 0~63
    :return: success or failure
    """
    func = prefix + "PositionXY"
    return eval(func)(device, c_double(angle_x), c_double(angle_y), speed)


# Get horizontal angle
def get_angle_x(device, angle) -> c_bool:
    """
    :param device: device handle
    :param angle: horizontal angle
    :return: success or failure
    """
    func = prefix + "GetAngleX"
    return eval(func)(device, byref(angle))


# Get horizontal angle
def get_angle_y(device, angle) -> c_bool:
    """
    :param device: device handle
    :param angle: pitch angle
    :return: success or failure
    """
    func = prefix + "GetAngleY"
    return eval(func)(device, byref(angle))


# Angle Callback
def reg_angle_event(device, event, this) -> c_bool:
    """
    :param this:
    :param device: device handle
    :param event: Angular return event
    :return: success or failure
    """
    func = prefix + "RegAngleEvent"
    return eval(func)(device, event, c_void_p(id(this)))
