from ctypes import *

from api.sdk.datdefs import *

# Play live video
def play_video(device, window, video_type, stream, port, play_id) -> c_bool:
    """
    :param device:      Device handle
    :param window:      Video display window handle
    :param video_type:  Video type
    :param stream:      Video stream
    :param port:        Port number, 0 to use SDK for video playback, non-0 to use Hik component for video playback
    :param play_id:     Returns video playback ID, globally unique
    :return:            Returns true on success, false on failure
    """
    func = prefix + "PlayVideo"
    return eval(func)(device, window, video_type, stream, port, play_id)

def stop_video_play(device, play_id) -> c_bool:
    """
    :param device:   Device handle
    :param play_id:  Video playback ID
    :return:         Returns true on success, false on failure
    """
    func = prefix + "StopVideoPlay"
    return eval(func)(play_id)

def change_window_resolution(device, play_id, x, y, width, height):
    """
    Change window resolution
    :param device:   Device handle
    :param play_id:  Video playback ID
    :param x:        X position of the window
    :param y:        Y position of the window
    :param width:    New width of the window
    :param height:   New height of the window
    :return:         Returns true on success, false on failure
    """
    func = prefix + "ChangeWndResolution"
    return eval(func)(play_id, c_int(x), c_int(y), c_int(width), c_int(height))
