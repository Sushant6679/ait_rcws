from ctypes import *
from api.sdk.datdefs import *

# Asynchronous connection result callback
Connect_cb = CFUNCTYPE(None, c_void_p, c_int)

# Create device handle
def CreateDevice(device, length, error) -> c_void_p:
    """
    :param device:  Device type
    :param length:  Error message buffer size
    :param error:   Returns error message on failure
    :return:        Returns device handle
    """
    func = prefix + "CreateDevice"
    return eval(func)(device, length, error)

# Release device handle
def ReleaseDevice(handle) -> c_bool:
    """
    :param handle:  Device handle
    :return:        Returns true on success, false on failure
    """
    func = prefix + "ReleaseDevice"
    return eval(func)(byref(c_int(handle)))

# Synchronously connect to device
def connect(handle, ip, port, uid, pwd, timeout) -> c_bool:
    """
    :param handle:  Device handle
    :param ip:      Device IP
    :param port:    Device port
    :param uid:     Device account
    :param pwd:     Device password
    :param timeout: Connection timeout
    :return:        Returns true on success, false on failure
    """
    func = prefix + "Connect"
    return eval(func)(handle, ip, port, uid, pwd, timeout)

# Asynchronously connect to device
def connect_ex(handle, ip, port, uid, pwd, timeout, callback) -> c_bool:
    """
    :param handle:      Device handle
    :param ip:          Device IP
    :param port:        Device port
    :param uid:         Device account
    :param pwd:         Device password
    :param timeout:     Connection timeout
    :param callback:    Asynchronous result callback function
    :return:            Returns true on success, false on failure
    """
    func = prefix + "ConnectEx"
    return eval(func)(handle, ip, port, uid, pwd, timeout, callback, None)

# Disconnect
def disconnect(handle) -> c_bool:
    """
    :param handle:  Device handle
    :return:        Returns true on success, false on failure
    """
    func = prefix + "DisConnect"
    return eval(func)(handle)

# Check connection status
def is_connected(handle) -> c_bool:
    """
    :param handle:  Device handle
    :return:        Returns true if connected, false otherwise
    """
    func = prefix + "IsConnected"
    return eval(func)(handle)

# Get error message
def GetLastErrMsg(handle) -> c_char_p:
    """
    :param handle:  Device handle
    :return:        Error message
    """
    func = prefix + "GetLastErrMsg"
    return eval(func)(handle)

# Get error code
def PGetLastErrCode(handle) -> c_int:
    """
    :param handle:  Device handle
    :return:        Error ID
    """
    func = prefix + "PGetLastErrMsg"
    return eval(func)(handle)

# Set request timeout
def SetRequestTimeout(handle, timeout) -> c_bool:
    """
    :param handle:      Device handle
    :param timeout:     Timeout duration
    :return:            Returns true on success, false on failure
    """
    func = prefix + "SetRequestTimeout"
    return eval(func)(handle, timeout)
