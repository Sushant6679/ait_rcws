from ctypes import *
from api.sdk.datdefs import *

alarm_aim_event = CFUNCTYPE(None, c_void_p, c_int, c_int, POINTER(AlarmAimInfo), c_int)


def register_alarm_aim_info_event(device, event, this):
    """
    :param device:
    :param event:
    :param this:
    :return:
    """
    func = prefix + "RegAimAlarmEvent  "
    return eval(func)(device, event,  c_void_p(id(this)))
