import socket, struct
from PyQt5.QtCore import pyqtSignal, QThread

class ObjectDetector(QThread):
    data_received = pyqtSignal(int, int)
    def __init__(self, parent=None, video_player=None):
        super().__init__(parent)
        self.UDP_IP = "0.0.0.0"
        self.UDP_PORT = 5005
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.UDP_PORT))
        self.running = True
        self.video_player_instance = video_player

    def run(self):
        print(f"Listening on {self.UDP_PORT}...")
        while self.running and not self.isInterruptionRequested():
            data, addr = self.sock.recvfrom(1024)
            print(f"{data}")
            offset_x, offset_y = struct.unpack("<hh", data)
            # print("Received offsets:", offset_x, offset_y)
            # self.data_received.emit(offset_x, offset_y)
            self.video_player_instance.gun_controller.csvmove(offset_x, offset_y)

    def stop(self):
        print(f"[INFO] Closing Socket")
        self.running = False
        if self.isRunning():
            self.requestInterruption()
            self.wait(2000)
            if self.isRunning():
                self.terminate()
                self.wait(1000)