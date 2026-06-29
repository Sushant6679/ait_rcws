from ctypes import *
from api.sdk.datdefs import *

# extern_data_event = CFUNCTYPE(None, c_void_p, ExternDevice_e, c_void_p, c_int)
extern_laser_event = CFUNCTYPE(None, c_void_p, c_double)


def laser_ranging(device, mode, event, this)->bool:
    """
    laser ranging
    :param device: 
    :param mode: 
    :param event: 
    :param this: 
    :return:
    """
    func = prefix + "SendRangingCmd"
    return eval(func)(device, mode, event, c_void_p(id(this)))
    # return eval(func)(device, mode, None, None)
