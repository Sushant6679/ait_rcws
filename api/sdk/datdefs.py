import os
import platform
from enum import Enum
from ctypes import *

curPath = os.path.abspath(os.path.dirname(__file__))

if platform.system() == 'Windows':
    lib_path = os.path.join(curPath, '..', 'lib', 'win64', 'HVideoSdk.dll')
    sdk = windll.LoadLibrary(lib_path)
    print("Loading Windows win64 Libraries")
else:
    if platform.machine() == 'aarch64':
        lib_path = os.path.join(curPath, '..', 'lib', 'linux_aarch', 'libHVideoSDK.so')
        print("Loading Linux aarch Libraries")
    else:
        lib_path = os.path.join(curPath, '..', 'lib', 'linux_x86', 'libHVideoSDK.so')
        print("Loading Linux x86 Libraries")

    sdk = cdll.LoadLibrary(lib_path)

prefix = "sdk.HVS_"


# Device types
class DeviceType_e(Enum):
    DEVICE_HIK  = 0     # Hikvision protocol
    DEVICE_DH   = 1     # Dahua protocol
    DEVICE_HPWS = 6     # Hope protocol
    DEVICE_GB   = 8     # National standard protocol


# Video types
class VideoType_e(Enum):
    VT_IRD   = 1    # Thermal imaging
    VT_LIGHT = 0    # Visible light

# PTZ (Pan-Tilt-Zoom) control types
class PtzControlType_e(Enum):
    PCT_STATIC     = 0    # PTZ stop
    PCT_UP         = 1    # PTZ tilt up
    PCT_DOWN       = 2    # PTZ tilt down
    PCT_LEFT       = 3    # PTZ pan left
    PCT_RIGHT      = 4    # PTZ pan right
    PCT_LEFT_UP    = 5    # PTZ pan left and tilt up
    PCT_RIGHT_UP   = 6    # PTZ pan right and tilt up
    PCT_LEFT_DOWN  = 7    # PTZ pan left and tilt down
    PCT_RIGHT_DOWN = 8    # PTZ pan right and tilt down
    PCT_AUTO       = 9    # PTZ auto-scan at speed SS


# Turntable motor types
class PtzType_t(Enum):
    PT_PtzV = 0  # Pitch motor
    PT_PtzH = 1  # Horizontal motor


# Camera lens control types
class CameraType_e(Enum):
    CCT_ZOOM_IN     = 1  # Zoom in at speed SS
    CCT_ZOOM_OUT    = 2  # Zoom out at speed SS
    CCT_FOCUS_NEAR  = 3  # Focus closer at speed SS
    CCT_FOCUS_FAR   = 4  # Focus farther at speed SS
    CCT_IRIS_OPEN   = 5  # Iris open at speed SS
    CCT_IRIS_CLOSE  = 6  # Iris close at speed SS


# Tracking modes
class TrackMode_e(Enum):
    TRACK_AIR_SEMIAUTO     = 0    # Semi-auto air tracking
    TRACK_AIR_AUTO         = 1    # Auto air tracking
    TRACK_GROUND_MANUAL    = 2    # Manual ground tracking
    TRACK_GROUND_SEMIAUTO  = 3    # Semi-auto ground tracking
    TRACK_GROUND_AUTO      = 4    # Auto ground tracking

# 电源控制类型
class PowerType_e(Enum):
    PT_LIGHT = 0    # 可见光电源
    PT_IRD = 1      # 热像电源
    PT_LASER = 2    # 激光电源


# 电源控制状态
class PowerState_e(Enum):
    POWER_ON = 0     # 电源开
    POWER_OFF = 1    # 电源关
    POWER_AUTO = 2   # 电源自动

# Scan types
class ScanType_e(Enum):
    SCAN_TYPE_NONE       = 0  # No scan
    SCAN_TYPE_PRESET     = 1  # Preset scan
    SCAN_TYPE_HORIZONTAL = 2  # Horizontal scan
    SCAN_TYPE_PANORAMA   = 3  # Panorama scan
    SCAN_TYPE_FAN        = 4  # Fan scan (apple peel scan)
    SCAN_TYPE_FRAME      = 5  # Frame scan
    SCAN_TYPE_PATTERN    = 6  # Pattern scan
    SCAN_TYPE_VERTICAL   = 7  # Vertical scan


# Scan control types
class ScanCtrlType_e(Enum):
    SCT_START     = 0  # Start
    SCT_STOP      = 1  # Stop
    SCT_PAUSE     = 2  # Pause
    SCT_CONTINUE  = 3  # Continue


# Peripheral device types
class ExternDevice_e(Enum):
    ED_COMPASS = 0       # Electronic compass
    ED_GPS = 1           # GPS
    ED_WEATHER = 2       # Weather device



class Rect(Structure):
    _fields_ = [
        ("left", c_long),
        ("top", c_long),
        ("right", c_long),
        ("bottom", c_long)
    ]


class RectEx(Structure):
    _fields_ = [
        ("left", c_long),
        ("top", c_long),
        ("width", c_long),
        ("height", c_long)
    ]


class TrackAimInfo(Structure):
    _fields_ = [
        ("angleX", c_double),
        ("angleY", c_double),
        ("offsetH", c_float),
        ("offsetV", c_float),
        ("rect", RectEx)
    ]


class CameraInfo(Structure):
    _fields_ = [
        ("zoom", c_double),
        ("view", c_double),
        ("focal", c_double)
    ]


class PointEx(Structure):
    _fields_ = [
        ("x", c_double),
        ("y", c_double)
    ]


class AlarmAimInfo(Structure):
    _fields_ = [
        ("id", c_int),
        ("targetType", c_int),
        ("confidence", c_double),
        ("distance", c_double),
        ("offsetH", c_double),
        ("offsetV", c_double),
        ("alarm", c_int),
        ("scene", c_int),
        ("gps", PointEx),
        ("alt", c_double),
        ("maxTemp", c_double),
        ("rect", RectEx),
    ]
