from ctypes import *
import ctypes
import json
from api.sdk.datdefs import *

# Turntable control
def send_common_cmd(device, cmd, req):
    # resp = ctypes.create_string_buffer(1024)
    resp = (ctypes.c_char * 4096)()  # Create a char array of size 4096 for the response
    # resp = POINTER(c_char*4096)
    # resp = (POINTER(c_char) * 1024)()
    func = prefix + "SendCommonCmdS"  # Function name to send command
    eval(func)(device, cmd.encode(), json.dumps(req).encode(), resp, 4096)  # Execute the command

    return resp.value  # Return the response
