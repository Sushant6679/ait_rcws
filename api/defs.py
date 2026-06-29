import os
import platform
from enum import Enum
from ctypes import *
from api.sdk.datdefs import *

curPath = os.path.abspath(os.path.dirname(__file__))

class Cue(Structure):
    _fields_ = [
        ("Az", c_float),
        ("El", c_float),
        ("Range", c_float)
    ]

class TargetDetails(Structure):
    _fields_ = [
        ("left", c_long),
        ("top", c_long),
        ("width", c_long),
        ("height", c_long),
        ("targetType", c_long)
    ]