import ctypes
from ctypes import *

from api.sdk.datdefs import *

track_aim_event = CFUNCTYPE(None, c_void_p, POINTER(TrackAimInfo), c_int)

# Start tracking
def start_track(device, video_type) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :return:            Success or failure
    """
    func = prefix + "StartTrack"
    return eval(func)(device, video_type)

# Stop tracking
def stop_track(device, video_type) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :return:            Success or failure
    """
    func = prefix + "StopTrack"
    return eval(func)(device, video_type)

# Hardware selection box tracking
def select_rect_track(device, video_type, video_rect, select_rect) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :param video_rect:  Video window size
    :param select_rect: Target selection window size
    :return:            Success or failure
    """
    func = prefix + "SelectRectTrack"
    return eval(func)(device, video_type, video_rect, select_rect)

# Enable/disable tracking capability for the channel
def enable_track_ability(device, video_type, enable) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :param enable:      Whether to enable tracking feature
    :return:            Success or failure
    """
    func = prefix + "EnableTrackAbility"
    return eval(func)(device, video_type, enable)

# Get tracking capability status
def get_track_ability_state(device, video_type, enable) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :param enable:      State of tracking capability
    :return:            Success or failure
    """
    func = prefix + "GetTrackAbilityState"
    return eval(func)(device, video_type, enable)

# Get tracking mode
def get_track_mode(device, video_type, mode) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :param mode:        Tracking mode
    :return:            Success or failure
    """
    func = prefix + "GetTrackMode"
    return eval(func)(device, video_type, mode)

# Set tracking mode
def set_track_mode(device, video_type, mode) -> c_bool:
    """
    :param device:      Device handle
    :param video_type:  Video type
    :param mode:        Tracking mode
    :return:            Success or failure
    """
    func = prefix + "SetTrackMode"
    return eval(func)(device, video_type, mode)

def register_track_alarm_event(device, event, this):
    """
    :param device:  Device handle
    :param event:   Event callback function for tracking alarm
    :param this:    Context or object to pass to the callback
    :return:        None
    """
    func = prefix + "RegTrackAimEvent "
    return eval(func)(device, event,  c_void_p(id(this)))
