from ctypes import *

import api.sdk.ptz as ptz
import api.sdk.angle as angle
import api.sdk.track as track
import api.sdk.device as device
import api.sdk.preset as preset
import api.sdk.video as video
import api.sdk.cruise as cruise
import api.sdk.device_cfg as device_cfg
import api.sdk.camera as camera
import api.sdk.alarm as alarm
import api.sdk.extern as extern
import api.sdk.power as power


class IPC_device(object):
    __handle__ = None
    __error__ = None
    __length__ = None

    def __init__(self, dev):
        self.__length__ = 1024
        self.__handle__ = device.CreateDevice(dev.value, self.__length__, self.__error__)
        pass

    def __del__(self):
        if device.is_connected(self.__handle__):
            device.disconnect(self.__handle__)
        device.ReleaseDevice(self.__handle__)

    def connect(self, ip, port, uid, pwd, timeout) -> c_bool:
        return device.connect(self.__handle__, ip, port, uid, pwd, timeout)

    def connect_ex(self, ip, port, uid, pwd, timeout, cb) -> c_bool:
        return device.connect_ex(self.__handle__, ip, port, uid, pwd, timeout, cb)

    def get_angle_x1(self, x):
        return angle.get_angle_x(self.__handle__, x)

    def get_angle_x(self):
        angle_x = c_double()
        self.get_angle_x1(angle_x)
        return angle_x

    def get_angle_y1(self, y):
        return angle.get_angle_y(self.__handle__, y)

    def get_angle_y(self):
        angle_y = c_double()
        self.get_angle_y1(angle_y)
        return angle_y

    def disconnect(self):
        return device.disconnect(self.__handle__)

    def is_connected(self):
        return device.is_connected(self.__handle__)

    def control_move(self, ptz_type, move, speed, speed_v):
        return ptz.control_move(self.__handle__, ptz_type.value, move, speed, speed_v, None)

    def camera_move(self, camera_type, move, video_type):
        return ptz.camera_move(self.__handle__, camera_type.value, move, video_type.value)

    def position_xy(self, angle_x, angle_y, speed):
        return angle.position_xy(self.__handle__, angle_x, angle_y, speed)

    def reg_angle_event(self, event, this):
        return angle.reg_angle_event(self.__handle__, event, this)

    def reg_camera_event(self, event, this):
        return camera.reg_camera_event(self.__handle__, event, this)

    def set_focus(self, focus, video_type):
        return camera.position_focus(self.__handle__, focus, video_type.value)

    def set_zoom(self, zoom, video_type):
        return camera.position_zoom(self.__handle__, zoom, video_type.value)

    def get_focus(self, video_type):
        focus = c_double()
        camera.get_focus(self.__handle__, video_type.value, focus)
        return focus

    def get_zoom(self, video_type):
        zoom = c_double()
        camera.get_zoom(self.__handle__, video_type.value, zoom)
        return zoom

    def trigger_auto_focus(self, video_type):
        return camera.trigger_auto_focus(video_type.value)

    def start_track(self, video_type):
        return track.start_track(self.__handle__, video_type.value)

    def stop_track(self, video_type):
        return track.stop_track(self.__handle__, video_type.value)

    def select_rect_track(self, video_type, video_rect, select_rect) -> c_bool:
        return track.select_rect_track(self.__handle__, video_type.value, video_rect, select_rect)

    def get_track_mode(self, video_type, mode):
        return track.get_track_mode(self.__handle__, video_type.value, mode.value)

    def set_track_mode(self, video_type, mode):
        return track.set_track_mode(self.__handle__, video_type.value, mode.value)

    def get_track_ability_state(self, video_type, enable):
        return track.get_track_ability_state(self.__handle__, video_type.value, enable)

    def enable_track_ability(self, video_type, enable):
        return track.enable_track_ability(self.__handle__, video_type.value, enable)

    def get_presets(self, info, count):
        return preset.get_presets(self.__handle__, info, count)

    def free_presets(self, info, count):
        return preset.free_presets(self.__handle__, info, count)

    def set_preset(self, preset_number, name, speed):
        return preset.set_preset(self.__handle__, preset_number, name, speed)

    def call_preset(self, preset_number):
        return preset.call_preset(self.__handle__, preset_number)

    def clear_preset(self, preset_number):
        return preset.clear_preset(self.__handle__, preset_number)

    def clear_all_preset(self):
        return preset.clear_all_preset(self.__handle__)

    def play_video(self, window, video_type, stream, port, play_id):
        return video.play_video(self.__handle__, window, video_type.value, stream, port, play_id)

    def stop_video_play(self, play_id):
        return video.stop_video_play(self.__handle__, play_id)

    def change_window_resolution(self, play_id, x, y, width, height):
        return video.change_window_resolution(self.__handle__, play_id, x, y, width, height)

    def control_scan(self, scan_type, ctrl_type, path):
        return cruise.control_scan(self.__handle__, scan_type.value, ctrl_type.value, path)

    def send_common_cmd(self, cmd, req):
        return device_cfg.send_common_cmd(self.__handle__, cmd, req)

    def reg_track_aim_event(self, event, this):
        return track.register_track_alarm_event(self.__handle__, event, this)

    def reg_alarm_aim_info_event(self, event, this):
        return alarm.register_alarm_aim_info_event(self.__handle__, event, this)

    def laser_ranging(self, mode, event, this):
        return extern.laser_ranging(self.__handle__, mode, event, this)

    def power_ctrl(self, power_type, power_state):
        return power.power_ctrl(self.__handle__, power_type.value, power_state.value)

    def set_thermal_mode(self, mode, video_type):
        """
        Set thermal camera mode (white hot/black hot)
        :param mode: 0 for white hot, 1 for black hot
        :param video_type: VT_IRD or VT_LIGHT
        :return: Success or failure
        """
        cmd = "imgSetCfg"
        para = {
            "fakeColor": mode
        }
        return self.send_common_cmd(cmd, para)
    def get_thermal_fov(self):
        cmd =  "imgGetFov"
        para = {}
        return self.send_common_cmd(cmd, para)
    
    def get_magnification_data(self, cmd):
        cmd = cmd
        para = {}
        return self.send_common_cmd(cmd, para)
    
    def set_thermal_fov(self, fov):
        cmd = "imgSetFov"
        para = {
            "fov": fov * 100
        }
        return self.send_common_cmd(cmd, para)
    
    def set_visible_fov(self, fov):
        cmd = "ptzControl"
        para = {
            "channelid": 0,
            "actionid": 42,
            "locIrViewPos": fov * 100
        }
        return self.send_common_cmd(cmd, para)
    
    def enable_track(self, enable, tracking_mode):
        if enable:
            cmd = "ivpSet"
            para = {
                "type": 4,
                "channelid": 1,
                "enable": enable,
                "trackingMode": tracking_mode,
                "bObjectDetTracking": 0
            }
            return self.send_common_cmd(cmd, para)
        else:
            cmd = "ivpTrackingCtrl"
            para = {
                "bTracking": enable,
                "channelid": 1
            }
            result = self.send_common_cmd(cmd, para)
            cmd = "ivpSet"
            para = {
                "type": 4,
                "channelid": 0,
                "enable": enable,
                "trackingMode": 2,
                "bObjectDetTracking": 0
            }
            return self.send_common_cmd(cmd, para)