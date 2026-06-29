from PyQt5.QtCore import QThread, pyqtSignal
from api.sdk.datdefs import *
from api.camera_communication import CameraCommunication

class DroneTrack(QThread):
    def __init__(self, parent=None):
        self.running = True
        self.curr_state ='CHECK_AND_TRACK'
        self.track_status = None

    def run(self):
        while self.running and not self.isInterruptionRequested():
            if self.curr_state == 'CHECK_AND_TRACK':
                # self.camera.ipc.set_track_mode(VideoType_e.VT_IRD, TrackMode_e.TRACK_AIR_SEMIAUTO)
                max_box = None
                try:
                    target_data = self.video_player.detectionQueue.pop()
                    x = target_data.left
                    y = target_data.top
                    max_box = Rect(x, y, x+40, y+40)
                except:
                    pass

                if max_box:
                    self.video_player.start_track(tracking_mode=0)

            elif self.curr_state == 'CHECK_TRACK_STATUS':
                self.track_status = self.camera.get_track_status(VideoType_e.VT_IRD)
                if self.track_status:
                    track_fail_count = 0

                else:
                   self.curr_state = 'CHECK_AND_TRACK'