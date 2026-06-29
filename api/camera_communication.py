
""" camera_communication.py: File contains 
                            1. Camera Communication driver class code to perform various PTZ and 
                             Camera(Visible/Thermal) functions
                            """
""" Author: Mahesh C Deokule    """
""" Version: 1.0.0  """
""" Date: 13th Nov 2023  """
import ctypes
import json
import api.sdk.sdk as HvsSDK
from api.sdk.sdk import IPC_device
from api.sdk.datdefs import *
from api.defs import *

def angle_event(obj, angle_x, angle_y):
    this = ctypes.cast(obj, ctypes.py_object).value
    this.pan_tilt_position_event(angle_x, angle_y)


def camera_event(obj, camara_info, video_type):
    this = ctypes.cast(obj, ctypes.py_object).value
    this.received_fov(camara_info.view, video_type)


def track_aim_event(obj, aim_info, video_type):
    this = ctypes.cast(obj, ctypes.py_object).value
    this.received_track_aim_info(aim_info.contents, video_type)


def alarm_aim_info_event(obj, video_type, alarm_type, aim_info, count):
    this = ctypes.cast(obj, ctypes.py_object).value
    this.received_alarm_aim_info(video_type, alarm_type, aim_info, count)

# def extern_ranging_event(obj,distance)

""" Camera Communication class is used to connect to camera 
and perform various PTZ and Camera(Visible/Thermal) functions"""


class CameraCommunication:
    pAngleEvent = HvsSDK.angle.angle_event(angle_event)
    pCameraEvent = HvsSDK.camera.camera_event(camera_event)
    pTrackAimEvent = HvsSDK.track.track_aim_event(track_aim_event)
    pAlarmAimEvent = HvsSDK.alarm.alarm_aim_event(alarm_aim_info_event)
    # pRangingEvent = HvsSDK.extern.reg_ranging_event(extern_ranging_event)
    def __init__(self, detectQ, fovQ, TEQ):
        """
        __init__ function creates socket object and initialises Camera class attributes like
        token_id, message_id and channel_id.

        :Param ip_address: ip_address of camera socket
        :Param port:port of camera socket
        :Param channel_id: default channel of camera
        :return: It returns None
        """
        self._angle_x_, self._angle_y_ = 0.0, 0.0
        self.ipc = IPC_device(DeviceType_e.DEVICE_HPWS)
        self.detectQ = detectQ
        self.fovQ = fovQ
        self.TEQ = TEQ
        

    def connect(self, ip_address, port, username, password):
        """
        connect function is to connect to camera using socket object and its parameters _ip_address and _port

        :It takes no parameter
        :return: It returns None
        """ 
        res = self.ipc.connect(ip_address, port, username, password, 30)
        if res:
            self.ipc.reg_angle_event(self.pAngleEvent, self)
            self.ipc.reg_camera_event(self.pCameraEvent, self)
            self.ipc.reg_track_aim_event(self.pTrackAimEvent, self)
            self.ipc.reg_alarm_aim_info_event(self.pAlarmAimEvent, self)
            # self.ipc.reg_ranging_event(self.pRangingEvent, self)
            # cmd = "timeGetWeb"
            # req = {}
            # response = self.ipc.send_common_cmd(cmd, req)
            # print(response)
        return res

    def disconnect(self):
        """
        disconnect function is to disconnect camera using socket object

        :It takes no parameter
        :return: It returns None
        """
        return self.ipc.disconnect()

    def open_video(self, window, stream, video_type):
        """
        preview the live video
        :param window: the window to show video, like winId() of QtWidgets, and cast to ctypes.c_void_p
        :param stream: main stream is 0 and second stream is 1
        :param video_type: day camera is 0 and thermal is 1
        :return: the id of player
        """
        play_id = ctypes.c_int()
        self.ipc.play_video(window, VideoType_e(video_type), stream, 0, ctypes.byref(play_id))
        return play_id

    def stop_video(self, play_id):
        """
        stop preview
        :param play_id:
        :return:
        """
        self.ipc.stop_video_play(play_id)

    def control_move(self, control_type, move, pan_speed, tilt_speed):
        """
        control_move function is to control the ptz of device
        :param control_type: the direction to control
                    PCT_STATIC     = 0
                    PCT_UP         = 1
                    PCT_DOWN       = 2
                    PCT_LEFT       = 3
                    PCT_RIGHT      = 4
                    PCT_LEFT_UP    = 5
                    PCT_RIGHT_UP   = 6
                    PCT_LEFT_DOWN  = 7
                    PCT_RIGHT_DOWN = 8
                    PCT_AUTO       = 9
        :param move: start or stop
        :param pan_speed:
        :param tilt_speed:
        :return:
        """
        return self.ipc.control_move(PtzControlType_e(control_type), move, pan_speed, tilt_speed)

    def camera_move(self, control_type, move, video_type):
        """
        camera_move function is to control the camera of device , like zoom in and zoom out
        :param control_type:
                        CCT_ZOOM_IN     = 1
                        CCT_ZOOM_OUT    = 2
                        CCT_FOCUS_NEAR  = 3
                        CCT_FOCUS_FAR   = 4
                        CCT_IRIS_OPEN   = 5
                        CCT_IRIS_CLOSE	= 6
        :param move: start or stop
        :param video_type: day camera is 0 and thermal is 1
        :return:
        """
        return self.ipc.camera_move(CameraType_e(control_type), move, VideoType_e(video_type))

    # Req 1.a.i
    def set_PTZ_pan_tilt_motor_pos(self, pan, tilt):
        """
        set_PTZ_pan_tilt_motor_pos function is to set Pan and Tilt motor position of PTZ.

        :Param locSpeed:     Not important
        :Param pan:          Pan angle of PTZ Motor
        :Param tilt:         Tilt angle of PTZ Motor 
        :return:             It returns None.
        """
        return self.ipc.position_xy(pan, tilt, 0)

    # Req 1.a.ii
    def set_PTZ_pan_tilt_motor_speed(self, panSpeed, tiltSpeed):
        """
        set_PTZ_pan_motor_speed function is to set Pan and Tilt motor speed of PTZ.

        :Param panSpeed:     Pan speed of PTZ Motor
        :Param tiltSpeed:    Tilt speed of PTZ Motor 
        :return:             It returns None.
        """
        self.set_PTZ_pan_motor_speed(panSpeed)
        self.set_PTZ_tilt_motor_speed(tiltSpeed)

    # Req 1.a.ii
    def set_PTZ_pan_motor_speed(self, panSpeed):
        """
        set_PTZ_pan_motor_speed function is to set Pan motor speed of PTZ.

        :Param panSpeed:     Pan speed of PTZ Motor
        :return:             It returns None.
        """
        cmd = "ptzWebSetPtzSpeedX"
        req = {
            "ptzspeedX": panSpeed
        }
        self.ipc.send_common_cmd(cmd, req)

    # Req 1.a.ii
    def set_PTZ_tilt_motor_speed(self, tiltSpeed):
        """
        set_PTZ_tilt_motor_speed function is to set Tilt motor speed of PTZ.

        :Param tiltSpeed:    Tilt speed of PTZ Motor
        :return:             It returns None.
        """
        cmd = "ptzWebSetPtzSpeedY"
        req = {
            "ptzspeedY": tiltSpeed
        }
        self.ipc.send_common_cmd(cmd, req)

    # Req 1.a.iii
    def get_PTZ_pan_tilt_motor_position(self):        
        """
        get_PTZ_pan_tilt_motor_position function is to get Pan Tilt motor position of PTZ.

        :Param None:    No Parameter
        :return:        It returns pan and tilt motor position of PTZ.
        """
        return self.ipc.get_angle_x(), self.ipc.get_angle_y()
    
    # Req 1.a.iv
    def get_PTZ_pan_tilt_motor_speed(self):
        """
        get_PTZ_pan_tilt_motor_speed function is to get Pan and Tilt motor speed of PTZ.

        :Param None:    No Parameter
        :return:        It returns Pan and Tilt motor speed of PTZ.
        """
        cmd = "ptzWebGetPtzCtrlPara"
        req = {
        }
        response = self.ipc.send_common_cmd(cmd, req)
        return json.loads(response.decode('utf-8')).get("ptzspeedX"), json.loads(response.decode('utf-8')).get("ptzspeedY")

    # Req 1.a.iv
    def get_PTZ_pan_motor_speed(self):
        """
        get_PTZ_pan_motor_speed function is to get Pan motor speed of PTZ.

        :Param None:    No Parameter
        :return:        It returns Pan motor speed of PTZ.
        """
        cmd = "ptzWebGetPtzCtrlPara"
        req = {
        }
        response = self.ipc.send_common_cmd(cmd, req)
        return json.loads(response.decode('utf-8')).get("ptzspeedX")

        # Req 1.a.iv
    def get_PTZ_tilt_motor_speed(self):
        """
        get_PTZ_tilt_motor_speed function is to get Tilt motor speed of PTZ.

        :Param None:    No Parameter
        :return:        It returns Tilt motor speed of PTZ.
        """
        cmd = "ptzWebGetPtzCtrlPara"
        req = {
        }
        response = self.ipc.send_common_cmd(cmd, req)
        return json.loads(response.decode('utf-8')).get("ptzspeedY")

    # Req 1.a.v
    def go_PTZ_home_position(self):
        """
        go_PTZ_home_position function is to bring camera to home position.

        :Param None:    No Parameter
        :return:        It returns None.
        """
        #Default home is Pan: 0, Tilt: 0.0
        self.set_PTZ_pan_tilt_motor_pos(0, 0)

    # Req 1.a.vi
    def pan_tilt_position_event(self, pan, tilt):
        """
        receive pan_tilt_position_event function, you can stream to external system here
        :return: It returns None.
        """
        # print("current pan is", pan)
        # print("current tilt is", tilt)
        return

    # Req 1.a.vii
    def set_north_alignment(self):
        """
        set_north_alignment function is to set true north alignment
        :return:
        """
        cmd = "ptzSetLimitMode"
        req = {
            "zeroSetFlag": 1
        }
        self.ipc.send_common_cmd(cmd, req)
        return

    # Req 1.a.viii    
    def get_GPS_lat_long(self):
        """
        get_GPS_lat_long function is to get latitude and longitude of gps device.

        :Param None:    No Parameter
        :return:        It returns Lat and Long of camera GPS.
        """
        cmd = "getGPSInfo"
        req = {
        }
        response = self.ipc.send_common_cmd(cmd, req)

        return json.loads(response.decode('utf-8')).get("longitude"), json.loads(response.decode('utf-8')).get("latitude")

    # Req 1.b.i
    def set_focus_motor_color_cam(self, focusPosition):
        """
        set_focus_motor_color_cam function is to set focus motor position of Color/Visible cam.

        :Param focusPosition:    Focus position of Color/Visible camera lens.
        :return:                 It returns None.
        """
        return self.ipc.set_focus(focusPosition, VideoType_e.VT_LIGHT)

    # Req 1.b.i
    def set_focus_motor_thermal_cam(self, focusPosition):
        """
        set_focus_motor_thermal_cam function is to set focus motor position of Thermal cam.

        :Param focusPosition:    Focus position of Thermal camera lens.
        :return:                 It returns None.
        """
        return self.ipc.set_focus(focusPosition, VideoType_e.VT_IRD)

    # Req 1.b.ii
    def get_focus_motor_curr_pos_color_cam(self):
        """
        get_focus_motor_curr_pos_color_cam function is to get focus motor position of Color/Visible cam.

        :Param None:    
        :return focusPosition:  It returns Focus position of Color/Visible cam.
        """
        return self.ipc.get_focus(VideoType_e.VT_LIGHT)

    # Req 1.b.ii
    def get_focus_motor_curr_pos_thermal_cam(self):
        """
        get_focus_motor_curr_pos_thermal_cam function is to get focus motor position of Thermal cam.

        :Param None:    
        :return focusPosition:  It returns Focus position of Thermal cam.
        """
        return self.ipc.get_focus(VideoType_e.VT_IRD)

    # Req 1.b.iii
    def set_zoom_motor_pos_color_cam(self, zoom_times):
        """
        set_zoom_motor_pos_color_cam function is to set zoom parameters like zoom times and speed
        of Visible/Color camera.

        :Param zoom_times:    No of times zoom
        :return focusPosition:  It returns None.
        """

        return self.ipc.set_zoom(zoom_times, VideoType_e.VT_LIGHT)

    # Req 1.b.iii
    def set_zoom_motor_pos_thermal_cam(self, zoom_times):
        """
        set_zoom_motor_pos_thermal_cam function is to set zoom parameters like zoom times and speed
        of Thermal camera.

        :Param zoom_times:    No of times zoom
        :return focusPosition:  It returns None.
        """
        return self.ipc.set_zoom(zoom_times, VideoType_e.VT_IRD)

    # Req 1.b.iv
    def get_zoom_motor_curr_pos_color_cam(self):
        """
        get_zoom_motor_curr_pos_color_cam function is to get zoom parameters like zoom times and speed
        of Visible/Color camera.

        :Param None:                No parameter
        :return digitalZoomTimes:   It returns digitalZoomTimes and digitalZoomSpeed.
        """
        return self.ipc.get_zoom(VideoType_e.VT_LIGHT)

    # Req 1.b.iv
    def get_zoom_motor_curr_pos_thermal_cam(self):
        """
        get_zoom_motor_curr_pos_thermal_cam function is to get zoom parameters like zoom times and speed
        of Thermal camera.

        :Param None:                No parameter
        :return digitalZoomTimes:   It returns digitalZoomTimes and digitalZoomSpeed.
        """
        return self.ipc.get_zoom(VideoType_e.VT_IRD)

    # Req 1.b.v
    def set_autofocus_both_cam(self):
        """
        set_autofocus_both_cam function is to set autofocus of Visible/Color and Thermal camera.

        :Param None:                No parameter
        :return:                    It returns None.
        """
        self.set_autofocus_color()
        self.set_autofocus_thermal()

    # Req 1.b.v
    def set_autofocus_color(self):
        """
        set_autofocus_both_cam function is to set autofocus of Visible/Color camera.

        :Param None:                No parameter
        :return:                    It returns None.
        """
        self.ipc.trigger_auto_focus(VideoType_e.VT_LIGHT)

    # Req 1.b.v
    def set_autofocus_thermal(self):
        """
        set_autofocus_both_cam function is to set autofocus of Thermal camera.

        :Param None:                No parameter
        :return:                    It returns None.
        """
        self.ipc.trigger_auto_focus(VideoType_e.VT_IRD)

    # Req 1.b.vi
    def received_fov(self, fov, video_type):
        # print("Video type : ", video_type, " , fov : ", fov)
        self.fovQ.append((fov, video_type))
        return

    # Req 1.b.vii
    def set_preset(self, preset_no, preset_name, speed):
        self.ipc.set_preset(preset_no, preset_name.encode('utf-8'), speed)

    def call_preset(self, preset_no):
        self.ipc.call_preset(preset_no)

    def del_preset(self, preset_no):
        self.ipc.clear_preset(preset_no)

    # Req 1.b.viii
    def set_camera_para_color(self, para):
        """
        :param para： thermal camera settings contains the dict below
        {
            "brightness": intValue,             //Brightness (0-100)
            "contrast": intValue,               //contrast (0-100)
            "sharpness": intValue,              //Sharpness (0-100)
            "saturation": intValue,             //saturation (0-100)
            "gamma": intValue,                  //gamma value (0-100) (external all-in-one machine)
            "dZoomSelect": intValue,            //Digital zoom selection (0: off; 1: on)
            "focusMode": intValue,              //focus mode (0: automatic; 1: manual: 2: semi-automatic)
            "focusSenLevel":intValue,           //Focus sensitivity (0: low; 1: medium: 2: high) (external all-in-one machine)
            "focusNearLimit": intValue,         //Minimum focus distance (0-7:0-7; 8: infinity)
            "dayNightMode": intValue,           //Day and night switching mode (0: day; 1: dark night; 2: automatic; 3: timing)
            "dayNightSen": intValue,            //Sensitivity in automatic day and night switching mode (0-7) (external all-in-one machine)
            "dayNightDayTmStart": intValue,     //day and night conversion start time, the number of seconds in the day (0-86399)
            "dayNightDayTmEnd": intValue,       //day and night conversion end time, the number of seconds in the day (0-86399)
            "backLightSelect": intValue,        //Backlight mode selection (0: off; 1: backlight compensation; 2: strong light suppression; 3 wide dynamic)
            "backLightAreaSelect": intValue,	//Backlight mode area selection (0: top, 1: bottom, 2: left, 3: right, 4: center)
            "highLightLevel": intValue,         //Strong light suppression level (0-100)
            "backLightLevel": intValue,         //Backlight compensation level (0-100) (self-developed all-in-one machine)
            "wBalanceSelect": intValue,         //White balance mode (0: automatic; 1: indoor; 2: outdoor; 3: manual; 4: incandescent lamp; 5:; 6: fluorescent lamp;)
            "wBRGainLevel": intValue,           //White balance R gain level (0-100)
            "wBBGainLevel": intValue,           //White balance B gain level (0-100)
            "defogSelect": intValue,            //Fog through mode (0: off; 1: on; 2: automatic)
            "defogLevel": intValue,             //Fog penetration level (0: high; 1: medium; 2: low;) (external all-in-one machine)
            "defogValue": intValue,             //Fog penetration level (0-100) (self-developed all-in-one machine)
            "wdrLevel": intValue,               //Wide dynamic level (0-100)
            "Nr2DMode": intValue,               //2D noise reduction mode mode (0: off; 1: on) (self-developed all-in-one machine)
            "Nr2DLevel": intValue,              //2D noise reduction level (0-100) (self-developed all-in-one machine)
            "Nr3DMode": intValue,               //3D noise reduction mode mode (0: off; 1: on) (self-developed all-in-one machine)
            "Nr3DLevel": intValue,              //3D noise reduction level (0-100)
            "mirrorSelect": intValue,           //Mirror mode (0: off; 1: flipped left and right; 2: flipped up and down; 3: flipped center;)
            "exposureSelect": intValue,         //Exposure mode (0: manual; 1: automatic; 2: aperture priority; 3: shutter priority;)
            "expGainLevel": intValue,           //Exposure gain (0-15)
            "apertureSelect": intValue,         //Aperture mode (see VISIBLE_APERTURE_MODE_E for definition)
            "shutterSelect": intValue,          //Shutter mode (see VISIBLE_SHUTTER_MODE_E for definition)
            "slowShutterMode": intValue,        //Slow shutter (0: manual; 1: automatic) (external all-in-one machine)
            "stabMode": intValue                //Anti-shake mode (0: off; 1: on) (external all-in-one machine)
            "stabLevel": intValue,		        //Anti-shake level（0：hith；1：middle；2：low）
            "bNetTrans": intValue		        //enable net transport
        }
        for example:
        param = {
            "brightness": 50,
            "contrast": 50,
            "sharpness": 50,
            "saturation": 50
        }
        :return: None
        """
        cmd = "visibleCfgSet"
        response = self.ipc.send_common_cmd(cmd, para)
        return

    # Req 1.b.ix
    def set_camera_para_thermal(self, para):
        """
        :param para： thermal camera settings contains the dict below
        {
            "brightness": intValue,         //Brightness (0-255) histogram is valid in manual mode
            "contrast": intValue,           //Contrast (0-255) histogram is valid in manual mode
            "brightness_auto": intValue,    //Brightness (0-255) histogram auto mode is valid
            "contrast_auto": intValue,      //Contrast (0-255) histogram is valid in manual mode
            "fakeColor": intValue,          //Palette (false color), 0-17 are hot white, hot black, dawn, iron red, rainbow 1, rainbow 2, rainbow 3, red hot, dark green, rainbow 4, gorgeous , The hottest, purple light, aurora, warm sun, azure, lava, gold
            "flip": intValue,               //Image flip, 0: None; 1: Up and down; 2: Left and right;
            "afMode": intValue,             //Auto focus trigger mode
            "histMode": intValue,           //Histogram mode, 1: manual mode; 2: automatic mode 1, default; 3: automatic mode 2; 4: automatic mode 3;
            "bAF": bool,                    //Whether turns on auto focus
            "elecZoom": bool,               //Whether turns on electronic zoom
            "elecZoomSpeed": intValue,      //Electronic zoom speed
            "elecZoomOsd": bool,            //Whether displays the electronic zoom OSD
            "elecZoomTimes": intValue,      //Electronic magnification, 10-80, which means 1.0-8.0 times
            "zoomReverse": bool,            //Whether zoom logic reverse
            "gammaCalib": intValue,         //Gamma correction parameters 0-30, 10
            "imgEnhance": bool,             //Whether turns on image enhancement
            "imgEnhanceCoef": intValue,     //Image enhancement coefficient 0-255, 80
            "antiSunshine": bool,           //Whether turns on anti-sunshine
            "antiSunshineThresh": intValue, //Image pixel threshold 0-255, 237
            "baffleTime": intValue,         //Baffle blocks the time 0-255, 24
            "pointThresh": intValue,        //point number threshold 0-255, 10
            "pip": intValue,                //Whether turn on picture-in-picture
            "bTargetTempShow": intValue,    //Whether displays the target temperature
            "transmission": intValue,       //Transmittance, 10-255, default 40
            "responsivity": intValue,       //response rate, 0-255 default 70
            "bGetFovFocalLength": bool,     //Whether actively query the thermal image field of view angle and focal length position
            "bNetTrans": bool,              //Whether turns on network backhaul
            "bPosAfEn": bool,               //Whether auto focus after positioning
            "cross": bool,                  //Whether turns on the cross cursor
            "crossH": intValue,             //The abscissa of the cross cursor 1-100, 50
            "crossV": intValue,             //the ordinate of the cross cursor
            "bAirFilter": bool,             //Whether turns on the air filter
            "bRawTimeFilter":bool,          //Whether turn on Raw time domain filtering
        }
        for example:
        param = {
            "brightness": 128,
            "contrast": 128
        }
        :return: None
        """
        cmd = "imgSetCfg"
        response = self.ipc.send_common_cmd(cmd, para)
        return

    # Req 1.b.x
    def set_track_channel(self, video_type):
        """
        set_track_channel function is to toggle camera (day / thermal) for tracking a target
        :param video_type: day camera is 0 and thermal is 1
        :return:
        """
        cmd = "ivpTrackingSwitchChannel"
        para = {
            "channelid": video_type
        }
        response = self.ipc.send_common_cmd(cmd, para)
        return

    # Req 1.b.xi
    def switch_fake_color(self, color):
        """
        switch_vice_versa function is to toggle between white hot to black hot vice versa.
        :param color: white hot is 0, black hot is 1
        :return: none
        """
        cmd = "imgSetCfg"
        para = {
            "fakeColor": color
        }
        response = self.ipc.send_common_cmd(cmd, para)
        return

    def start_track(self, video_type):
        """
        start track of the video_type channel
        :param video_type:
        :return:
        """
        self.ipc.start_track(VideoType_e(video_type))

    def stop_track(self, video_type):
        """
        stop track
        :param video_type:
        :return:
        """
        self.ipc.stop_track(VideoType_e(video_type))

    def select_to_track(self, video_type, video_rect, select_rect):
        """
        select a target in the video to trigger track
        :param video_type: day camera is 0 and thermal is 1
        :param video_rect: the rect of the video area
        :param select_rect: the rect of selected area
        rect structure is a dict of Rect like below
        {
            'left', c_long,
            'top', c_long,
            'right', c_long,
            'bottom', c_long
        }
        :return:
        """
        self.ipc.select_rect_track(VideoType_e(video_type), self.dict_to_rect(video_rect),
                                   self.dict_to_rect(select_rect))

    def dict_to_rect(self, _dict):
        _rect = Rect()
        for field, value in dict.items():
            setattr(_rect, field, value)
        return _rect

    def received_track_aim_info(self, aim_info, video_type):
        """
        received_track_aim_info function is to receive track aim info while tracking a target
        :param aim_info: see Structure "TrackAimInfo"
        :param video_type: day camera is 0 and thermal is 1
        :return:
        """
        # print("received tracking target info, video type is ", video_type,
        #       "target info is :", self.structure_to_dict(aim_info))
        # regex_patt = r'"rect":\s*("\{[^}]+\}")'



        # match = re.search(pattern, json_str)

        # if match:
        #     # Extract the matched rect value
        #     rect_str = match.group(1)
            
        #     # Convert the extracted string to a dictionary
        #     rect_dict = json.loads(rect_str)
        # rect = aim_info.rect
        # print(f"RectEx Left: {aim_info.rect.left}, Top: {aim_info.rect.top}, Width: {aim_info.rect.width}, Height: {aim_info.rect.height}")
        # self.detectionQ.put(rect)  # Put the dictionary into the queue

        return

    def received_alarm_aim_info(self, video_type, alarm_type, alarm_info, count):
        """
        received_alarm_aim_info function is to receive detect target details
        :param video_type: day camera is 0 and thermal is 1
        :param alarm_type: the type of alarm , the value is below
        {
            ALARM_INPUT_GPIO = 0, //IO input alarm
            ALARM_INPUT_MOVE_DET, //Motion detection alarm
            ALARM_INPUT_THREMAL_DET, //Thermal alarm
            ALARM_INPUT_SDCARD_FULL, //SD card full alarm
            ALARM_INPUT_IVP_INTRUSION, //area intrusion alarm
            ALARM_INPUT_IVP_TRIPWIRE, //Mixed line detection alarm
            ALARM_INPUT_IVP_LEFT_BENIND, //Left object detection alarm
            ALARM_INPUT_IVP_OBJECT_REMOVAL, //Object removal detection alarm
            ALARM_INPUT_IVP_TRACKING, //Target tracking alarm
            ALARM_INPUT_IVP_REGION_IN, //Enter zone detection alarm
            ALARM_INPUT_IVP_REGION_OUT, //Leave area detection alarm
            ALARM_INPUT_IVP_LINGER_DETECTION, //Wandering detection alarm
            ALARM_INPUT_IVP_CROWD_DETECTION, //Crowd gathering detection alarm
            ALARM_INPUT_IVP_QUICK_MOVE, //Quick movement alarm
            ALARM_INPUT_IVP_OBJECT_DET = 14, // object detect alarm
            ALARM_INPUT_VIDEO_LOST = 20, //Video loss alarm
            ALARM_INPUT_THERMAL_TIMEOUT, //The thermal imaging movement responds to abnormal alarms
            ALARM_INPUT_OD, //Video occlusion detection alarm
            ALARM_INPUT_NET_DISCONNECT, //Network cable disconnection alarm
            ALARM_INPUT_IP_CONFLICT, //IP conflict detection alarm
            ALARM_INPUT_ACCESS_VIOLATION, //Illegal access alarm
            ALARM_INPUT_NO_SDCARD, //No SD card alarm
            ALARM_INPUT_SDCARD_ERR, //SD card error alarm
            ALARM_INPUT_SDCARD_NO_SPACE, //Sd card insufficient space alarm
            ALARM_INPUT_HUMAN_TEMP, //High temperature target alarm
        }
        :param aim_info: pointer of targets list, see Structure "AlarmAimInfo" in datdefs.py
        :param count: count of targets
        :return:
        """
        # print(alarm_type)
        if alarm_type == 14:
            target_data_actual = None
            alarm = None
            max_height = 0
            max_width = 0
            for i in range(count):
                target_data = TargetDetails(alarm_info[i].rect.left, alarm_info[i].rect.top, alarm_info[i].rect.width, alarm_info[i].rect.height, alarm_info[i].targetType)
                if target_data.targetType is not None and (target_data.targetType == 0 or target_data.targetType == 26):
                    w = target_data.width
                    h = target_data.height
                    area = w * h
                    # print(f"Width: {w}, Height: {h}")
                    if w > max_width and h > max_height:
                        if area < 1000:
                            max_width = w
                            max_height = h
                            alarm = alarm_info[i]
                            target_data_actual = target_data
                            # print("Target Found, Boxed at {} size".format(str(area)))
                        else:
                            print("Target size mismatch skipping, {}".format(str(area)))
                else:
                    # print("Target type mismatch skipping {}".format(str(target_data.targetType)))
                    pass
            if alarm and target_data_actual:
                self.detectQ.append(target_data_actual)
                self.TEQ.append((alarm.offsetH,alarm.offsetV))
        return

    # structure_to_dict
    def structure_to_dict(self, structure):
        _dict = {}
        for field, _ in structure._fields_:
            value = getattr(structure, field)
            if isinstance(value, ctypes.Structure):
                value = self.structure_to_dict(value)
            _dict[field] = value
        return json.dumps(_dict)

    def get_intelligent_para(self, video_type, intelligent_type):
        """
        get_intelligent_para function is to get the parameter of intelligent
        :param video_type: day camera is 0 and thermal is 1
        :param intelligent_type: intelligent type : 0: Leftover detection; 1: Object removal detection;
                        2: Tripwire detection; 3: Intrusion detection; 4: Target tracking; 5: Entering the area;
                        6: Leaving the area; 7: Wandering detection; 8: Crowd gathering detection; 9: fast moving;
                        10: target classification
        :return: the json of intelligent parameter
                {
                    "ackvalue": 100,
                    "enable": true,
                    "delay": 10,
                    "bDraw": true,			//Whether mark target
                    "bAlarmOut": true,		//Whether linkage alarm output
                    "bAlarmEMail": true,	//Whether to send alarm email
                    "bAlarmFTP": true,		//Whether snapshot pictures upload FTP
                    "bAlarmClient": false,	//Whether send alarm message to the client
                    "bAlarmRecord": true,	//Whether to report to the police
                    "bAlarmSnapshot": true,//Whether to report to the police
                    "bAlarmTracking": true,	//Whether linkage target tracking
                    “bAlarmFlash”: intValue,			//Alarm flashing light
                    “bAlarmSound”: intValue,		//Alarm sound
                    "bIvpResPassBack": true,	//Whether send back analysis result
                    "passbackInt": true,	// Return frequency of intelligent analysis results, 0: real time; 1: 10 times/s; 2: 5 times/s; 3: 1 times/s; invalid in the regional temperature measurement mode of temperature measurement;
                    "bFollowPTZ": true,		//Whether PTZ follow up

                    // The following parameters are unique to target tracking
                    "trackingTime": 0,		// Target tracking duration, 0-3600, 0 means unlimited
                    "bLimit": 0,			// Target tracking While restricts the space range, only target tracking is supported
                    "bZoom": 0,			// Target tracking While automatically zooming in on the target, only target tracking is supported
                    "zoomCoef": 0,		// Target tracking target zoom factor, only supported by target tracking, 0-100
                    "trackingMode": 0,		// Target tracking mode, 0: semi-automatic to air; 1: automatic to air; 2: manual to ground; 3: semi-automatic to ground; 4: automatic to ground; only target tracking is available
                    "bShowOSD": 1,		// Whether to display target tracking miss information
                    "trackingRes": 1,		// Target tracking miss output type, 0: angle (x100); 1: milliradian (x100); 2: pixel;
                    "trackingCoef": 2,	// Missing target output coefficient, range 0.1-10, default 2；
                    "apec": 10000,	// Target response threshold of tracking library 1, range 8-32, default 16, only target tracking library 1 (see device capability set) is available
                    "searchRoiRatio": 2,	// Search range, range 1-10, default 2, only target tracking library 1 (see device capability set) is available
                    "interpFactor": 12,	// Learning rate, range 1-50, default 12, only target tracking library 1 (see device capability set) is available
                    "respThresh": 10000,	// Target response threshold of tracking library 3, range 0-50000, only target tracking library 3 (see device capability set) is available
                    "blendCoef": 10000,	// Mixing coefficient, range 0-32767, only target tracking library 3 (see device capability set) is available
                    "lamda": 10000,// Normalization coefficient, range 0-65535, only target tracking library 3 (see device capability set) is available
                    "trancAlpha": 10000,// Normalized threshold, range 0-4095, only target tracking library 3 (see device capability set) is available
                    "sigma": 10000,	// Gaussian core bandwidth, range 0-255, only target tracking library 3 (see device capability set) is available
                    "respThr": 10000,	// Response threshold, range 0-255, only target tracking library 3 (see device capability set) is available
                    "gradThr": 10000,	// Target detection threshold in air mode, range 0-255, only target tracking library 3 (see device capability set) is available
                    "bSwitchChnAuto": false,	// Whether to switch the channel to automatically lock the target, only target tracking library 3 (see device capability set) is available
                    // End of target tracking specific parameters

                    "timeThresh": 1,		// Duration threshold, range 1-300 seconds, only leftover detection, object removal detection, and wandering detection are available
                    "crowdThresh": 1,		// Congestion threshold, range 1-100, only crowd gathering detection is available
                    "speedThresh": 1,		// Speed threshold, range 1-100, only fast movement is available
                    "scenes": [			// Preset scenes, the 0th corresponds to the default scene, the 1-16th parameters correspond to the 1-16 presets
                        {
                            "sensitivity": 100,// Sensitivity
                            "enableTrajectory": 100,//Whether Enable trajectory analysis, only regional intrusion and cross-border detection are effective
                            "minTrajectoryDuration": 100,// Trajectory duration threshold (number of frames), 0-1000, only valid for area intrusion and cross-border detection
                            "nTrajectoryAlarmLen": 100,// Trajectory length threshold, 0-100, only valid for regional intrusion and cross-border detection
                            "maxPixelSpeed": 100,// The maximum pixel speed of the target, 0-100, only valid for area intrusion and cross-border detection
                            "sceneChangeThresh": 100,// Scene change threshold, 0-100, only valid for area intrusion and cross-border detection
                            "rectMax": {// Maximum target size, width range 0-639, height range 0-511；
                                "x": 0,
                                "y": 0,
                                "w": 640,
                                "h": 512
                            },
                            "rectMin": {// Minimum target size, width range 0-639, height range 0-511；
                                "x": 0,
                                "y": 0,
                                "w": 32,
                                "h": 32
                            },
                            "maxRegionNum": 8,// Maximum number of regions
                            "regions": [//region list
                                {
                                    "stPoints": [//Area coordinates, width range 0-639, height range 0-511；

                                    ],
                                    "stRules": [//Temperature measurement alarm rules, only the temperature measurement function is valid；
                                        {
                                                "indicator": int,// Temperature index, 0: highest temperature; 1: lowest temperature; 2: average temperature; 3: core temperature;
                                            "alarmMode": int, // Temperature measurement alarm mode, 0: greater than; 1: greater than or equal to; 2: equal to; 3: less than or equal to; 4: less than;
                                            "tempVal": float// Temperature value
                                        }
                                    ],
                                    "nIvpCheckMode":intValue //cross-border detect direction，0：A->B；1：B->A；2：double-sided；
                                }
                            ]
                        }
                    ],
                    "timePlan": [		// A total of 7 arrays, in order from Monday to Sunday, each array has a maximum of 4 time periods, and the time point is the number of seconds of the day	[
                        [
                            {
                                "sTime": 0,
                                "eTime": 86340
                            }
                        ]
                    ],
                    // The following parameters are only supported by the temperature measurement function
                    "tempMode": intValue,	// Temperature measurement mode, 0: target temperature measurement; 1: regional temperature measurement;
                    "tempInt": intValue,	// Time interval of temperature measurement in regional temperature measurement mode, in seconds
                    "minTemp": float,		// The lowest temperature, when the equipment capability is concentrated, when bTempIndustrySupport is FALSE, the range is 0-50 degrees Celsius, when TRUE, tempIndustryRange is 0 range 0-160 degrees Celsius, tempIndustryRange is 1 range 0-550 degrees Celsius, only valid in target temperature measurement mode
                    "maxTemp": float,		// The highest temperature, the range is the same as minTemp, only valid in the target temperature measurement mode
                    "tempThresh": float,	// Temperature alarm threshold, the range is the same as minTemp, only valid in target temperature measurement mode
                    "tempIndustryRange": intValue,// Industrial temperature measurement range selection, 0: 0-160 degrees Celsius; 1: 0-550 degrees Celsius;"xiuzheng_flag": bool,	//Whether turn on target correction
                    "heiti_ref_flag": bool,	//Whether turn on blackbody correction
                    "heiti_ref_temp": float,	// Black body reference temperature, -40-60; Celsius
                    "param_t_atm": float,	// Atmospheric temperature, -40-60 degrees Celsius
                    "param_tao": float,		// Transmittance 0-1
                    "param_e": float,		// Emissivity 0-1
                    "param_t_amb": float,	// Ambient temperature, -40-60 degrees Celsius
                    "param_renti_cewen_corr": float, // Target temperature coefficient，-12.7-12.8
                    "rectHeiti": {			// Black body coordinate area, under 640x512 coordinate system
                        "x": 0,
                        "y": 0,
                        "w": 32,
                        "h": 32
                    }

                    // The following parameters are only supported by the thermal alarm function
                    "hotAlarmThresh": intValue,		// Thermal alarm threshold, 0-100
                    "hotAlarmPtzAct": bool,			//Hot alarm whether linkage of PTZ
                    "hotAlarmPtzActime": intValue	//Hot alarm linkage of PTZ stop time，Unit second
                    }

        """
        cmd = "ivpGet"
        req = {
            "channelid": video_type,
            "type": intelligent_type
        }
        response = self.ipc.send_common_cmd(cmd, req)

        # print(response)
        return response

    def get_default_intelligent_para(self, video_type, intelligent_type):
        """
        get_default_intelligent_para function is to get the default parameter of intelligent
        :param video_type: day camera is 0 and thermal is 1
        :param intelligent_type: intelligent type : 0: Leftover detection; 1: Object removal detection;
                        2: Tripwire detection; 3: Intrusion detection; 4: Target tracking; 5: Entering the area;
                        6: Leaving the area; 7: Wandering detection; 8: Crowd gathering detection; 9: fast moving;
                        10: target classification
        :return: the json of intelligent parameter ,its the same as the get_intelligent_para function
        """
        cmd = "ivpGetDefault"
        req = {
            "channelid": video_type,
            "type": intelligent_type
        }
        response = self.ipc.send_common_cmd(cmd, req)

        return response

    def set_intelligent_para(self, parameter):
        """
        set_intelligent_para function is to set the parameter of intelligent
        :param parameter: like this
                        {
                            "channelid": 0, //ite video type
                            "type": 4, //its intelligent type
                            ...   // other parameter you want to set contains by the dict of parameter in get_intelligent_para function
                        }
        :return:
        """
        cmd = "ivpSet"
        response = self.ipc.send_common_cmd(cmd, parameter)

    def get_track_status(self, video_type):
        """
        to get the track status
        :param video_type:
        :return:
        """
        cmd = "ivpTrackingStatusGet"
        req = {
            "channelid": video_type.value
        }
        response = self.ipc.send_common_cmd(cmd, req)

        return json.loads(response.decode('utf-8')).get("bTracking")
    
    
    def set_fov(self, fov, video_type):
        """
        to get the track status
        :param video_type:
        :return:
        """
        cmd = "ptzControl"
        req = {
            "channelid": video_type.value,
            "actionid":42,
            "locIrViewPos": fov*100
        }
        response = self.ipc.send_common_cmd(cmd, req)

        return json.loads(response.decode('utf-8')).get("result")

    # def fire_lrf(self, mode):
    #     """
    #     set_lrf_ranging_mode function is to set Ranging mode of LRF.

    #     :Param mode:         0 - Single Measurement, 1 - Multiple Measurements(Continuous)
    #     :return:             It returns Cmd_SUCCESS or Cmd_FAILURE.
    #     """
    #     cmd = "laserRanging"
    #     req = {
    #         # "token": self._token_id,
    #         "action": mode
    #     }
    #     response = self.ipc.send_common_cmd(cmd, req)
    
    #     # response = self.ipc.send_common_cmd(cmd, req)
    #     # time.sleep(0.5)
    #     return json.loads(response.decode('utf-8')).get("laserRangingReport")



