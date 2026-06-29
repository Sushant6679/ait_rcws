from ctypes import *
from api.sdk.datdefs import *


# 电源控制
def power_ctrl(device, power_type, power_state) -> c_bool:
    """
    :param device:      设备句柄
    :param power_type:      PT_LIGHT = 0    # 可见光电源
                            PT_IRD = 1      # 热像电源
                            PT_LASER = 2    # 激光电源
    :param power_state:     POWER_ON = 0     # 电源开
                            POWER_OFF = 1    # 电源关
                            POWER_AUTO = 2   # 电源自动
    :return:            成功或失败
    """
    func = prefix + "Power"
    return eval(func)(device, power_type, power_state)

