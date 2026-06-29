import pygame
pygame.init()
import math
import sys
import ctypes
import time
import os
import json
import threading
from typing import Dict, List
from configparser_crypt import ConfigParserCrypt

from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QStackedWidget,
    QHBoxLayout,
    QSizePolicy,
    QLineEdit,
    QSpacerItem,
    QDialog,
    QPushButton,
    QMessageBox,
    QShortcut,
    QFrame, 
    QTableWidget, 
    QTableWidgetItem, 
    QHeaderView,
    QProgressBar,
    QRadioButton,
    QCheckBox, 
    QButtonGroup
)

if sys.platform == 'win32':
    os.add_dll_directory(r'C:\Program Files\VideoLAN\VLC')
elif sys.platform == 'linux':
    os.environ['LD_LIBRARY_PATH'] = '/usr/bin/vlc'

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QTimer, QPointF, QRectF, QThread, QEvent
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QKeySequence, QImage, QPalette, QKeyEvent, QPaintEvent, QFont, QBrush, QPainterPath
from PyQt5.QtWidgets import QPinchGesture
from qt_utils.LongPressButton import LongPressButton as LQPushButton
from qt_utils.login import LoginDialog
from qt_utils.SoundPlayer import SoundPlayer
from qt_utils.Config import ConfigScreen
from qt_utils.Diagnose import MainWidget as DiagnoseScreen, Parameter

from utils.Anemometer import RS485WindSpeedTransmitter
from utils.TinyFrameController import TinyFrameGunController
from utils.JoyStick import JoyStickThread4, JoyStickThread5, JoyStickThread0
from utils.Smoother import JoystickSmoother
from utils.UserManagement import ROLES
from utils.AutoPilotController import AutoPilotController
from utils.Ballistics import PolynomialPredictor
from utils.BallisticCorrection import ProjectileSolver
from utils.BallisticsNSVT import PolynomialPredictorNSVT
from utils.LogHelper import CustomLogger
from utils.system_limits import get_system_limits, SYSTEM_LIMITS, DEFAULT_LIMITS
from utils.Firedetection import CASTLEListener
from utils.DroneHardkill import HardkillDrone
from utils.ObjectTracker import ObjectDetector

import api.sdk.sdk as HvsSDK
from api.sdk.datdefs import *
from api.camera_communication import CameraCommunication
from pydash import throttle
import vlc
import numpy as np
import win32gui
import win32con
import win32api
import win32ui
import requests
import hashlib
import json
from collections import deque
import serial

logger = CustomLogger()

def rescale(val, in_min, in_max, out_min, out_max):
    return out_min + (val - in_min) * ((out_max - out_min) / (in_max - in_min))

def normalize(angle):
    return (angle + 360) % 360

def clockwise_angle(a1, a2):
    a1_norm = normalize(a1)
    a2_norm = normalize(a2)
    return (a2_norm - a1_norm) % 360

def is_between_cw(limit1, limit2, current):
    limit1 = normalize(limit1)
    limit2 = normalize(limit2)
    current = normalize(current)
    
    if limit1 < limit2:
        return limit1 <= current <= limit2
    else:
        return current >= limit1 or current <= limit2

def get_plane_normal(roll_deg, pitch_deg, yaw_deg=0):
    r, p, y = np.deg2rad([roll_deg, pitch_deg, yaw_deg])
    Rx = np.array([[1, 0, 0],
                   [0, np.cos(r), -np.sin(r)],
                   [0, np.sin(r),  np.cos(r)]])
    Ry = np.array([[np.cos(p), 0, np.sin(p)],
                   [0, 1, 0],
                   [-np.sin(p), 0, np.cos(p)]])
    Rz = np.array([[np.cos(y), -np.sin(y), 0],
                   [np.sin(y),  np.cos(y), 0],
                   [0, 0, 1]])
    normal = Rz @ Ry @ Rx @ np.array([0, 0, 1])
    return normal

def vector_on_plane(yaw_deg, normal):
    theta = np.deg2rad(yaw_deg)
    v_xy = np.array([np.cos(theta), np.sin(theta), 0])
    n_hat = normal / np.linalg.norm(normal)
    v_proj = v_xy - np.dot(v_xy, n_hat) * n_hat
    return v_proj / np.linalg.norm(v_proj)

def elevation_angle(v):
    return np.rad2deg(np.arctan2(v[2], np.linalg.norm(v[:2])))

curPath = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curPath)

IP = "10.1.0.180".encode()
PORT = 39020
USER = "admin".encode()
PWD = "Abc.12345".encode()
TIMEOUT = 30

def angle_format(angle):
    angle = angle + 360
    angle = angle % 360
    if angle > 180:
        angle = 360-angle
        angle = -angle
    return "{: >6.2f}".format(angle)

def get_resource_path(relative_path):
    """Get the absolute path to a resource, works for PyInstaller and development"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # If not running as PyInstaller executable, use current directory
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)

def get_asset_path(name):
    return os.path.join(curPath, "assets", name)

def angle_event(obj, angle_x, angle_y):
    this:VideoPlayer = ctypes.cast(obj, ctypes.py_object).value
    this.recv_angle_event.emit(angle_x, angle_y)

def laser_event(obj, distance):
    this:VideoPlayer = ctypes.cast(obj, ctypes.py_object).value
    print("LRF Distance",distance)
    this.received_laser(distance)

class NotificationOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
        self.parent_widget = parent
        self.notifications = []
        
        # Main layout centered in the overlay
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignCenter)  # Center notifications
        
        # Timer for position updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_position)
        self.update_timer.start(50)
        
        # Show the overlay
        self.show()
        
    def update_position(self):
        if not self.parent_widget.isVisible():
            self.hide()
            return
        
        # Update position to match parent
        parent_geo = self.parent_widget.frameGeometry()
        parent_pos = self.parent_widget.mapToGlobal(QPoint(0, 0))
        self.setGeometry(parent_pos.x(), parent_pos.y(), parent_geo.width(), parent_geo.height())
        
        if self.notifications:
            self.show()
            self.raise_()
        else:
            self.hide()
    
    def show_notification(self, message, title="Notification", buttons=None, callbacks=None):
        # Create notification widget
        notification_widget = QFrame(self)
        notification_widget.setObjectName("notificationDialog")
        notification_widget.setMinimumWidth(450)
        notification_widget.setMaximumWidth(500)
        
        # Apply style to match the screenshot
        notification_widget.setStyleSheet("""
            #notificationDialog {
                background-color: #c7c19f;
                border: 1px solid #a5a088;
                border-radius: 5px;
            }
            QLabel {
                color: #333333;
            }
            QPushButton {
                background-color: #3e4a2b;
                color: white;
                border: 1px solid #2c341f;
                border-radius: 3px;
                padding: 8px 15px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4c5936;
            }
            QPushButton:pressed {
                background-color: #333d23;
            }
        """)
        
        notification_layout = QVBoxLayout(notification_widget)
        notification_layout.setContentsMargins(0, 0, 0, 10)
        
        # Title bar
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #e0dbc3; border-top-left-radius: 5px; border-top-right-radius: 5px;")
        title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 0, 10, 0)
        
        # Title label
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: #333333;")
        
        # Close button
        close_button = QPushButton("✕")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666666;
                border: none;
                font-size: 14px;
                padding: 0;
                max-width: 20px;
            }
            QPushButton:hover {
                color: #333333;
            }
        """)
        
        # Create closure for close button
        def close_notification():
            self.layout.removeWidget(notification_widget)
            for i, n in enumerate(self.notifications):
                if n['widget'] == notification_widget:
                    self.notifications.pop(i)
                    break
            notification_widget.deleteLater()
        
        close_button.clicked.connect(close_notification)
        close_button.setFixedSize(20, 20)
        
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_button)
        
        notification_layout.addWidget(title_bar)
        
        # Message label - LEFT aligned
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 10)  # Adjust margins to match screenshot
        
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignLeft)  # LEFT alignment
        message_label.setStyleSheet("font-size: 14px;")
        content_layout.addWidget(message_label)
        
        notification_layout.addWidget(content_widget)
        
        # Buttons
        if buttons:
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            button_layout.setContentsMargins(10, 0, 10, 0)
            button_layout.setSpacing(10)
            
            button_layout.addStretch()  # Push buttons to the right
            
            for i, button_text in enumerate(buttons):
                button = QPushButton(button_text)
                
                # Create closure for button callback
                def create_callback(idx):
                    def on_click():
                        # Call the callback if provided
                        if callbacks and idx < len(callbacks) and callbacks[idx]:
                            callbacks[idx]()
                        # Close the notification
                        close_notification()
                    return on_click
                
                button.clicked.connect(create_callback(i))
                button_layout.addWidget(button)
            
            notification_layout.addWidget(button_widget)
        
        # Add to layout and track notification
        self.layout.addWidget(notification_widget)
        self.notifications.append({
            'widget': notification_widget
        })
        
        # Show and raise the notification
        notification_widget.show()
        self.show()
        self.raise_()
        
    # Convenience methods for different notification types
    def show_warning(self, message, title="Warning", buttons=None, callbacks=None):
        if buttons is None:
            buttons = ["OK"]
        self.show_notification(message, title, buttons, callbacks)
        
    def show_question(self, message, title="Question", buttons=None, callbacks=None):
        if buttons is None:
            buttons = ["YES", "NO", "CANCEL"]
        self.show_notification(message, title, buttons, callbacks)

class NativeOverlay(QWidget):
    def __init__(self, target_widget):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.target_widget = target_widget
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(self.windowFlags() |
                            Qt.Tool |
                            Qt.WindowTransparentForInput)

        self.setStyleSheet("background: transparent;")
        self.show()

        self.draw_rect = False
        self.az = None
        self.el = None
        self.h_fov = None
        self.v_fov = None

        # Sync position every 100 ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_overlay_position)
        self.timer.start(100)

    def toggle_rectangle(self, enabled, az, el, h_fov, v_fov, width, height):
        logger.warning(f"Inside toggle_rectangle, {enabled}")
        self.draw_rect = enabled
        self.az = az
        self.el = el
        self.h_fov = h_fov
        self.v_fov = v_fov
        self.img_width = width
        self.img_height = height

        self.update()

    def update_overlay_position(self):
        if not self.target_widget.isVisible():
            self.hide()
            return
        else:
            self.show()

        target_geo = self.target_widget.frameGeometry()
        target_pos = self.target_widget.mapToGlobal(target_geo.topLeft())
        self.setGeometry(target_pos.x(), target_pos.y(),
                         target_geo.width(), target_geo.height())
        self.raise_()

    # def paintEvent(self, event: QPaintEvent):
    #     if self.draw_rect:
    #         painter = QPainter(self)
    #         painter.setRenderHint(QPainter.Antialiasing)

    #         # Draw rectangle
    #         painter.setPen(QPen(QColor(255, 0, 0, 255), 3))

    #         # Size of the rectangle
    #         rect_width = 50
    #         rect_height = 50

    #         # Get widget center
    #         # center_x = self.width() // 2
    #         # center_y = self.height() // 2
    #         center_x = self.width() // 2
    #         center_y = self.height() // 2
    #         print(f"WIDTH: {self.width()}, HEIGHT: {self.height()}")
    #         # Offset from center based on azimuth and elevation
    #         # change_x = int((self.img_width * self.az) / self.h_fov) 
    #         # change_y = int((self.height() * self.el) / self.v_fov)
    #         change_x = int((self.width() * self.az) / self.h_fov)
    #         change_y = int((self.img_height * (self.el + 0.18)) / self.v_fov)
    #         # Center of the rectangle
    #         rect_center_x = center_x - change_x
    #         rect_center_y = center_y + change_y
           
    #         logger.warning(f"Rectangle centers: {rect_center_x}, {rect_center_y}")
    #         # rect_center_x = 70
    #         # rect_center_y = self.height()
    #         logger.warning(f"Width: {self.width()}, Height: {self.height()}")
    #         # Top-left corner of rectangle
    #         top_left_x = rect_center_x - rect_width // 2
    #         top_left_y = rect_center_y - rect_height // 2

    #         # Draw rectangle
    #         # painter.drawRect(top_left_x, top_left_y, rect_width, rect_height)
    #         # Draw horizontal line
    #         crosshair_len = 20
    #         painter.drawLine(rect_center_x - crosshair_len, rect_center_y,
    #                          rect_center_x + crosshair_len, rect_center_y)
    #         # Draw vertical line
    #         painter.drawLine(rect_center_x, rect_center_y - crosshair_len,
    #                          rect_center_x, rect_center_y + crosshair_len)
    #         # Draw center point as a small filled circle
    #         painter.setBrush(QBrush(QColor(0, 255, 0, 255)))  # Green dot
    #         dot_radius = 5
    #         painter.drawEllipse(rect_center_x - dot_radius,
    #                             rect_center_y - dot_radius,
    #                             dot_radius * 2,
    #                             dot_radius * 2)

    def paintEvent(self, event: QPaintEvent):
        if self.draw_rect:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
    
            # Set pen for crosshair and rings
            painter.setPen(QPen(QColor(255, 0, 0, 255), 3))  # Red color, 3px
    
            # Get widget center
            center_x = self.width() // 2
            center_y = self.height() // 2
            print(f"WIDTH: {self.width()}, HEIGHT: {self.height()}")
    
            # Offset from center based on azimuth and elevation
            change_x = int((self.width() * self.az) / self.h_fov)
            change_y = int((self.img_height * (self.el)) / self.v_fov)
    
            # Center of crosshair
            crosshair_x = center_x - change_x
            crosshair_y = center_y + change_y
        
            logger.warning(f"Rectangle centers: {crosshair_x}, {crosshair_y}")
            logger.warning(f"Width: {self.width()}, Height: {self.height()}")
    
            # Crosshair lines
            inner_radius = int((self.width() * 0.056) / self.h_fov)
            outer_radius = 2 * inner_radius
            crosshair_len = outer_radius

            painter.drawLine(crosshair_x - crosshair_len, crosshair_y,
                             crosshair_x + crosshair_len, crosshair_y)  # Horizontal
            painter.drawLine(crosshair_x, crosshair_y - crosshair_len,
                             crosshair_x, crosshair_y + crosshair_len)  # Vertical
    
            # Draw concentric rings
            painter.setBrush(Qt.NoBrush)  # Ensure only the outline is drawn
    
            # Outer circle
            painter.drawEllipse(crosshair_x - outer_radius,
                                crosshair_y - outer_radius,
                                outer_radius * 2,
                                outer_radius * 2)
    
            # Inner circle
            painter.drawEllipse(crosshair_x - inner_radius,
                                crosshair_y - inner_radius,
                                inner_radius * 2,
                                inner_radius * 2)
    
            # Center dot
            painter.setBrush(QBrush(QColor(0, 255, 0, 255)))  # Green center dot
            dot_radius = 5
            painter.drawEllipse(crosshair_x - dot_radius,
                                crosshair_y - dot_radius,
                                dot_radius * 2,
                                dot_radius * 2)


class NativeOverlayBalLine(QWidget):
    def __init__(self, target_widget):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.target_widget = target_widget
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(self.windowFlags() |
                            Qt.Tool |
                            Qt.WindowTransparentForInput)

        self.setStyleSheet("background: transparent;")
        self.show()

        self.draw_curve = False
        self.az_list = []
        self.el_list = []
        self.h_fov = None
        self.v_fov = None
        self.img_width = None
        self.img_height = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_overlay_position)
        self.timer.start(100)

    def toggle_curve(self, enabled, az_list, el_list, h_fov, v_fov, width, height):
        logger.warning(f"Inside toggle_curve, {enabled}")
        self.draw_curve = enabled
        self.az_list = az_list
        self.el_list = el_list
        self.h_fov = h_fov
        self.v_fov = v_fov
        self.img_width = width
        self.img_height = height

        self.update()

    def update_overlay_position(self):
        if not self.target_widget.isVisible():
            self.hide()
            return
        else:
            self.show()

        target_geo = self.target_widget.frameGeometry()
        target_pos = self.target_widget.mapToGlobal(target_geo.topLeft())
        self.setGeometry(target_pos.x(), target_pos.y(),
                         target_geo.width(), target_geo.height())
        self.raise_()

    def paintEvent(self, event: QPaintEvent):
        if self.draw_curve and self.az_list and self.el_list:
            if len(self.az_list) != len(self.el_list):
                logger.error("Azimuth and Elevation lists must be the same length")
                return

            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(255, 0, 0, 255), 2))

            center_x = self.width() // 2
            center_y = self.height() // 2

            points = []

            for az, el in zip(self.az_list, self.el_list):
                change_x = int((self.img_width * az) / self.h_fov)
                change_y = int((self.height() * el) / self.v_fov)
                point_x = center_x - change_x
                point_y = center_y + change_y
                points.append(QPointF(point_x, point_y))

            # Draw curve using QPainterPath
            path = QPainterPath()
            if points:
                path.moveTo(points[0])
                for point in points[1:]:
                    path.lineTo(point)

            painter.drawPath(path)


class NativeOverlayCompass(QWidget):
    def __init__(self, target_widget):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.target_widget = target_widget

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)

        self.setStyleSheet("background: transparent;")
        self.show()

        self.azimuth_angle = 0
        self.elevation_angle = 0
        self.visible_flag = True  # default is visible

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_overlay_position)
        self.timer.start(100)

    def update_overlay_position(self):
        if not self.target_widget.isVisible() or not self.visible_flag:
            self.hide()
            return
        else:
            self.show()

        target_geo = self.target_widget.frameGeometry()
        target_pos = self.target_widget.mapToGlobal(target_geo.topLeft())
        self.setGeometry(target_pos.x(), target_pos.y(),
                         target_geo.width(), target_geo.height())
        self.raise_()

    def update_angles(self, azimuth_deg, elevation_deg, visible=True):
        self.azimuth_angle = azimuth_deg
        self.elevation_angle = elevation_deg
        self.visible_flag = visible
        self.update_overlay_position()
        self.update()

    def paintEvent(self, event):
        if not self.visible_flag:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)

        radius = 50
        spacing = 40
        center_y = self.height() - radius - 20
        # center1_x = self.width() // 2 - radius - spacing // 2
        # center2_x = self.width() // 2 + radius + spacing // 2
        right_margin = 175  # Distance from the right edge
        total_width = 2 * radius + spacing
        start_x = self.width() - total_width - right_margin

        center1_x = start_x + radius
        center2_x = start_x + radius + spacing + 2 * radius


        # Draw circles
        for center_x in [center1_x, center2_x]:
            painter.drawEllipse(center_x - radius, center_y - radius, 2 * radius, 2 * radius)

        # Draw azimuth rod
        self.draw_rod(painter, center1_x, center_y, radius, self.azimuth_angle, "Az")

        # Draw elevation rod
        self.draw_rod(painter, center2_x, center_y, radius, self.elevation_angle, "El")

    def draw_rod(self, painter, cx, cy, radius, angle_deg, label):
        angle_rad = math.radians(angle_deg - 90)  # 0 deg = up
        x_end = cx + radius * math.cos(angle_rad)
        y_end = cy + radius * math.sin(angle_rad)

        # Rod
        painter.setPen(QPen(QColor(255, 0, 0), 3))
        painter.drawLine(cx, cy, int(x_end), int(y_end))

        # Label
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(cx - 15, cy + radius + 15, label)



class TinyFrameComm(QThread):
    data_received = pyqtSignal(list)

    def __init__(self, parent, ser):
        super().__init__(parent)
        # Initialize serial connection
        self.ser = ser
        # self.VideoObj = videoPlayerObj
        # self.GunObj = gunControllerObj
        self.running = True
        self.responses = []
        self.got_response = False
        self.waiting_for = None

        self.zoom_in_flag = False
        self.zoom_out_flag = False
        self.focus_in_flag = False
        self.focus_out_flag = False
        self.day_night_flag = False
        self.stab_flag = False
        self.lay_flag = False
        self.zero_gun_flag = False
        self.bal_flag = False
        self.mode_flag = False
        self.track_flag = False
        self.black_hot_flag = False
        self.released = True
        self.scan_flag = False
        self.brake_enabled = False
        self._pressed_for = 0
        self.lay_start_time = 0
        self.thermal_start_time = 0
        self.counter = 0
        self.show_targets = False

        self.zoom_value = 0

        self.current_lay_index = 0
        # Load the DLL (TinyFrame.dll)
        if sys.platform == 'win32':
            self.tinyframe = ctypes.CDLL(os.path.abspath('./TinyFrame.dll'))
        elif sys.platform.startswith('linux'):
            self.tinyframe = ctypes.CDLL(os.path.abspath('./TinyFrame.so'))
        else:
            raise OSError(f"Unsupported operating system: {sys.platform}")

        # Define the structure for TF_Msg (based on TinyFrame.h)
        class TF_Msg(ctypes.Structure):
            _fields_ = [
                ("frame_id", ctypes.c_uint8),
                ("is_response", ctypes.c_bool),
                ("type", ctypes.c_uint8),
                ("data", ctypes.POINTER(ctypes.c_uint8)),
                ("len", ctypes.c_uint16),
                ("userdata", ctypes.c_void_p),
                ("userdata2", ctypes.c_void_p)
            ]

        # Define the function type for the callback (listener)
        self.ListenerCallbackType = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(TF_Msg))
       
        # Define the argument types and return type for TF_AddGenericListener
        self.tinyframe.TF_AddGenericListener.argtypes = [ctypes.POINTER(ctypes.c_void_p), self.ListenerCallbackType]
        self.tinyframe.TF_AddGenericListener.restype = ctypes.c_bool


    
        # Define the argument types and return type for TF_Send
        self.tinyframe.TF_Send.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(TF_Msg)]
        self.tinyframe.TF_Send.restype = ctypes.c_bool

        # Initialize TinyFrame instance (0 for TF_SLAVE or 1 for TF_MASTER)
        self.tinyframe.TF_Init.argtypes = [ctypes.c_int]
        self.tinyframe.TF_Init.restype = ctypes.POINTER(ctypes.c_void_p)

        self.tinyframe.TF_Accept.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32]


        self.TF_Msg = TF_Msg  # Store the class for later use
        

        # Initialize TinyFrame instance (TF_SLAVE)
        self.tf_instance = self.tinyframe.TF_Init(0)
        if not self.tf_instance:
            raise Exception("Failed to initialize TinyFrame!")
        
        print("TinyFrame initialized!")

        # Add the generic listener callback
        # self.type_listener_callback_c = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint8, ctypes.POINTER(self.TF_Msg))(self.type_listener_callback)
        self.listener_callback_c = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(self.TF_Msg))(self.listener_callback)
        self.tinyframe.TF_AddGenericListener(self.tf_instance, self.listener_callback_c)
        # self.tinyframe.TF_AddTypeListener(self.tf_instance, 1, self.type_listener_callback_c)
        # self.tinyframe.TF_Query(self.tf_instance, ctypes.byref(TF_Msg), self.id_listener_callback, None, 0)

        # self.thread = threading.Thread(target=self.read_data, daemon=True)
        # self.thread.start()

    def listener_callback(self, tf, msg):
        """
        Listener callback function that processes incoming data."""
        self.counter += 1
        data = ctypes.cast(msg.contents.data, ctypes.POINTER(ctypes.c_uint8 * msg.contents.len)).contents[:]
        self.data_received.emit(data)
        
        # camera_zoom_in, camera_zoom_out, camera_focus_in, camera_focus_out, camera_lrf, camera_day_therm, camera_black_white_hot, res0 = map(int, f"{int(data[0]):08b}"[::-1])
        # RCWS_mode, RCWS_trackStatus, RCWS_stab, RCWS_ballisticStatus, RCWS_zeroGun, RCWS_layOn, RCWS_drivePWR, res1 = map(int, f"{int(data[1]):08b}"[::-1])
        # Wind = int(data[2])
        # DriveSpeed = int(data[3])
        # E_stop = int(data[4])
        # DrivePWR = int(data[5])

        # # print(f"""Camera Zoom in: {camera_zoom_in}\nCamera Zoom out: {camera_zoom_out}\nCamera Focus in: {camera_focus_in}\n
        # #         Camera Focus out: {camera_focus_out}\nCamera LRF: {camera_lrf}\nCamera D/N: {camera_day_therm}\n
        # #         Camera B/W Hot: {camera_black_white_hot}\n\nRCWS Mode: {RCWS_mode}\nRCWS Track Status: {RCWS_trackStatus}\n
        # #         RCWS Stabilization: {RCWS_stab}\nRCWS Ballistics: {RCWS_ballisticStatus}\nRCWS Zero Gun: {RCWS_zeroGun}\n
        # #         RCWS Lay On: {RCWS_layOn}\nRCWS Arm: {RCWS_drivePWR}\n\nWind: {Wind}\nDriveSpeed: {DriveSpeed}\nE_Stop: {E_stop}\n
        # #         Drive Power: {DrivePWR}""")
        
        # """if self.counter == 20:
        #     self.counter = 0
        #     try:
        #         night_zoom = self.VideoObj.ipc_object.get_zoom(VideoType_e.VT_IRD).value
        #         day_zoom = self.VideoObj.ipc_object.get_zoom(VideoType_e.VT_LIGHT).value
        #         # print("Day Zoom: ", day_zoom)
        #         if self.VideoObj.stackedWidget.currentIndex() == 1:
        #             self.VideoObj.progress_bar_1.setValue(int(day_zoom * 1.22))
        #             # print(str(int(day_zoom * 1.22)))
        #             self.VideoObj.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))
        #         else:
        #             self.VideoObj.progress_bar_1.setValue(int(night_zoom * 1.22))
        #             self.VideoObj.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))

        #         night_focus = self.VideoObj.ipc_object.get_focus(VideoType_e.VT_IRD).value
        #         day_focus = self.VideoObj.ipc_object.get_focus(VideoType_e.VT_LIGHT).value
        #         # print("Day Focus: ", day_focus.value)
        #         if self.VideoObj.stackedWidget.currentIndex() == 1:
        #             self.VideoObj.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
        #             self.VideoObj.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
        #         else:
        #             self.VideoObj.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
        #             self.VideoObj.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
        #     except:
        #         print("Error in receiving Data from camera")"""
        # # night_fov = self.VideoObj.ipc_object.get_fov(VideoType_e.VT_IRD).value
        # # day_fov = self.VideoObj.ipc_object.get_fov(VideoType_e.VT_LIGHT).value
        # # if self.VideoObj.stackedWidget.currentIndex() == 1:
        # #     self.VideoObj.pan_tilt_widget.update_values(self.VideoObj.gunAzimuth.text(), day_fov)
        # # else:
        # #     self.VideoObj.pan_tilt_widget.update_values(self.VideoObj.gunAzimuth.text(), night_fov)

        # # self.VideoObj.pan_widget.update_values(float(self.VideoObj.gunAzimuth.text()), 60) 
        # # self.VideoObj.tilt_widget.update_values(float(self.VideoObj.gunElevation.text()), 60)       

        # if not camera_zoom_in and not self.zoom_in_flag:
        #     self.zoom_in_flag = True
        #     self.VideoObj.control_camera(CameraType_e.CCT_ZOOM_IN, True)
        # elif camera_zoom_in and self.zoom_in_flag:
        #     self.zoom_in_flag = False
        #     self.VideoObj.control_camera(CameraType_e.CCT_ZOOM_IN, False)
        
        # if not camera_zoom_out and not self.zoom_out_flag:
        #     self.zoom_out_flag = True
        #     self.VideoObj.control_camera(CameraType_e.CCT_ZOOM_OUT, True)
        # elif camera_zoom_out and self.zoom_out_flag:
        #     self.zoom_out_flag = False
        #     self.VideoObj.control_camera(CameraType_e.CCT_ZOOM_OUT, False)

        # if not camera_focus_in and not self.focus_in_flag:
        #     self.focus_in_flag = True
        #     self.VideoObj.control_camera(CameraType_e.CCT_FOCUS_FAR, True)
        # elif camera_focus_in and self.focus_in_flag:
        #     self.focus_in_flag = False
        #     self.VideoObj.control_camera(CameraType_e.CCT_FOCUS_FAR, False)
        
        # if not camera_focus_out and not self.focus_out_flag:
        #     self.focus_out_flag = True
        #     self.VideoObj.control_camera(CameraType_e.CCT_FOCUS_NEAR, True)
        # elif camera_focus_out and self.focus_out_flag:
        #     self.focus_out_flag = False
        #     self.VideoObj.control_camera(CameraType_e.CCT_FOCUS_NEAR, False)

        # # if camera_lrf:
        # #     self.VideoObj.fire_lrf()

        # if not camera_day_therm and not self.day_night_flag:
        #     self.thermal_start_time = time.time()
        #     self.day_night_flag = True
        #     self.VideoObj.switchClicked()
        #     self.VideoObj.day_button.setChecked(True if self.VideoObj.stackedWidget.currentIndex() == 1 else False)
        #     self.VideoObj.night_button.setChecked(False if self.VideoObj.stackedWidget.currentIndex() == 1 else True)
        # elif camera_day_therm:
        #     pressed_for = time.time() - self.thermal_start_time
        #     self.day_night_flag = False
        #     # if pressed_for > 2:
        #     #     self.VideoObj.ToggleThermalPower()
        #     # self.VideoObj.switchClicked()

        # if not camera_black_white_hot and not self.black_hot_flag and self.released:
        #     self.VideoObj.setBlackHot()
        #     self.black_hot_flag = True
        #     self.released = False
        # elif camera_black_white_hot:
        #     self.released = True
        # elif not camera_black_white_hot and self.black_hot_flag and self.released:
        #     self.VideoObj.setWhiteHot()
        #     self.black_hot_flag = False
        #     self.released = False

        # if not RCWS_mode and not self.mode_flag: # 0 for position and 1 for velocity mode
        #     self.mode_flag = True
        #     self.GunObj.mover_pan.set_mode(1, speed=self.VideoObj.gun_speed)
        #     self.GunObj.mover_tilt.set_mode(1, speed=self.VideoObj.gun_speed)
        #     self.VideoObj.mode_value_button1.setChecked(True)
        #     self.VideoObj.mode_value_button2.setChecked(False)
        # elif RCWS_mode and self.mode_flag:
        #     self.mode_flag = False
        #     self.GunObj.mover_pan.set_mode(2)
        #     self.GunObj.mover_tilt.set_mode(2)
        #     self.VideoObj.mode_value_button1.setChecked(False)
        #     self.VideoObj.mode_value_button2.setChecked(True)
        
        # if not RCWS_trackStatus and not self.track_flag:
        #     self.track_flag = True
        #     self.GunObj.tracking.start_track()
        #     self.VideoObj.track_value_button1.setChecked(True)
        #     self.VideoObj.track_value_button2.setChecked(False)   
        # elif RCWS_trackStatus and self.track_flag:
        #     self.track_flag = False
        #     self.GunObj.tracking.stop_track()
        #     self.VideoObj.track_value_button1.setChecked(False)
        #     self.VideoObj.track_value_button2.setChecked(True)

        # if not RCWS_stab and not self.stab_flag:
        #     self.stab_flag = True
        #     self.VideoObj.toggleStabilization()
        #     self.VideoObj.stab_value_button1.setChecked(True)
        #     self.VideoObj.stab_value_button2.setChecked(False)
        # elif RCWS_stab and self.stab_flag:
        #     self.stab_flag = False
        #     self.VideoObj.toggleStabilization()
        #     self.VideoObj.stab_value_button1.setChecked(False)
        #     self.VideoObj.stab_value_button2.setChecked(True)
        
        # if not RCWS_ballisticStatus and not self.bal_flag:
        #     self.bal_flag = True
        #     self.VideoObj.toggle_ballistics()
        #     self.VideoObj.bal_value_button1.setChecked(self.VideoObj.ballistics_active)
        #     self.VideoObj.bal_value_button2.setChecked(not self.VideoObj.ballistics_active)
        # elif RCWS_ballisticStatus and self.bal_flag:
        #     self.bal_flag = False
        
        # if not RCWS_zeroGun and not self.zero_gun_flag:
        #     self.zero_gun_flag = True
        #     self.VideoObj.position_gun(0, 0)
        # elif RCWS_zeroGun and self.zero_gun_flag:
        #     self.zero_gun_flag = False
        
        # if not RCWS_layOn and not self.lay_flag:
        #     self.lay_start_time = time.time()
        #     self.lay_flag = True
        #     self.VideoObj.x_in.setFocus()
        # elif RCWS_layOn and self.lay_flag:
        #     self._pressed_for = time.time() - self.lay_start_time
        #     self.current_lay_index += 1
        #     self.lay_flag = False       

        #     if self._pressed_for > 1:
        #         print("Laying Gun")
        #         self.VideoObj.make_move_gun()
        #         self._pressed_for = 0
        #         self.lay_start_time = 0

        # if not RCWS_drivePWR and not self.brake_enabled:
        #     self.brake_enabled = True
        #     self.GunObj.unbrake()
        # elif RCWS_drivePWR and self.brake_enabled:
        #     self.brake_enabled = False
        #     self.GunObj.brake()

        # # if Wind:
        # #     self.VideoObj.manual_wind_speed = Wind
        # #     self.VideoObj.wind_speed_value.setValue(int(Wind))
        # #     # print("Wind: ", Wind)
        
        # # if not res1 and not self.scan_flag:
        # #     self.scan_flag = True
        # #     self.VideoObj.selfCheck()
        # # elif res1 and self.scan_flag:
        # #     self.scan_flag = False

        # if DriveSpeed:
        #     self.VideoObj.setGunSpeed(int(DriveSpeed))
        #     print("Drive Speed: ", DriveSpeed)

        # # if E_stop:
        # #     pass

        # # if DrivePWR:
        # #     pass

        
        return 1  # Return TF_NEXT to keep listening


    def run(self):
        while self.running:
            data = self.ser.read()
            self.tinyframe.TF_Accept(self.tf_instance, ctypes.c_uint8(*data), 1)
    
    def stop(self):
        self.running = False

class OverlayWidget(QWidget):
    click_window = pyqtSignal(str)
    select_track = pyqtSignal(QPoint, QPoint)
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()

    def __init__(self, parent=None):
        super(OverlayWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.end = QPoint()
        self.start = QPoint()
        self.setMouseTracking(True)
        self.vdiff = 0
        self.hdiff = 0
        self.draw_b  = False
        self.distance = "--"
        self.predictions = {}

        # 🔥 IMPROVED TOUCH AND GESTURE SETUP
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setAttribute(Qt.WA_TouchPadAcceptSingleTouchEvents, True)

        # Grab gesture with specific flags
        gesture_id = self.grabGesture(Qt.PinchGesture)
        print(f"🎯 Pinch gesture grabbed with ID: {gesture_id}")

        # Pinch state tracking
        self.is_zooming = False
        self.zoom_direction = None
        self.ignore_mouse_during_pinch = False

    def mousePressEvent(self, event):
        if self.ignore_mouse_during_pinch:
            print("🚫 Ignoring mouse - pinch active")
            event.ignore()
            return

        self.click_window.emit(self.objectName())
        self.start = self.end = event.pos()

    def mouseMoveEvent(self, event):
        if self.ignore_mouse_during_pinch:
            event.ignore()
            return

        if event.buttons() & Qt.LeftButton:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.ignore_mouse_during_pinch:
            event.ignore()
            return

        self.select_track.emit(self.start, self.end)
        self.end = self.start = QPoint()
        self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in.emit()
        else:
            self.zoom_out.emit()

    def paintEngine(self):
        return None

    def paintEvent(self, event):
        self.draw_select()

    def get_painter(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        return painter

    def draw_select(self):
        if self.end.x() == 0 and self.end.y() == 0:
            self.draw_ballistic()
            return
        painter:QPainter = self.get_painter()
        pen = QPen()
        pen.setWidth(2)
        pen.setColor(QColor("#00ff00"))
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        temp_rect = QRect(self.start, self.end)
        painter.drawRect(temp_rect)
        mid_X= (self.start.x() + self.end.x())//2
        mid_T= (self.start.y() + self.end.y())//2
        temp_rect = QRect(mid_X-1, mid_T-1, 2, 2)
        pen.setColor(QColor("#ff0000"))
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        painter.drawRect(temp_rect)
        painter.drawLine(mid_X - 20, mid_T, mid_X + 20, mid_T)
        painter.drawLine(mid_X , mid_T - 20, mid_X , mid_T + 20)
        painter.end()
        self.draw_ballistic()

    def set_ballistic(self, vdiff, hdiff, distance, predictions):
        self.vdiff = vdiff
        self.hdiff = hdiff
        self.distance = distance
        self.predictions = predictions
        self.draw_b  = True
    
    def clear_ballistic(self):
        self.draw_b = False

    def draw_ballistic(self):
        if not self.draw_b:
            return
        vdiff, hdiff = self.vdiff, self.hdiff 
        painter:QPainter = self.get_painter()
        fov_h = math.degrees(0.120)
        fov_v = math.degrees(0.096)

        w = self.rect().width()
        h = self.rect().height()

        y = rescale(vdiff, 0, fov_v, 0, h)
        x = rescale(hdiff, 0, fov_h, 0, w)

        mx = w//2
        my = h//2


        max_w = 2
        for i in range(1,4):
            if mx + x * i > w:
                break
            max_w = x * i
            self.drawCrosshair(painter, mx + x * i, my, color=Qt.green, hlength=2, vlength= int(y*2 + 20))
            self.drawCrosshair(painter, mx - x * i, my, color=Qt.green, hlength=2, vlength= int(y*2 + 20))

        self.drawCrosshair(painter, mx, my - y, hlength= int(max_w * 2) ,color=Qt.yellow)
        self.drawCrosshair(painter, mx, my + y, hlength= int(max_w * 2) ,color=Qt.blue)
        # self.update()

        painter.setPen(Qt.white)
        painter.drawText(100, 100, "Range {} (mtrs)".format(self.distance))
        painter.drawText(100, 120,"Wind Direction <- {} (kmph / tick) ->".format("15"))

        painter.drawText(100, 140, "Ballistics:")
        painter.drawText(100, 160, "Elevation correction : {: >6.2f} degrees | {: >6.2f} mils".format(self.vdiff , math.radians(self.vdiff)*1000))
        painter.drawText(100, 180, "Wind correction : {: >6.2f} degrees | {: >6.2f} mils".format(self.hdiff, math.radians(self.hdiff)*1000))

        if self.predictions:
            painter.drawText(100, 200, "ToF : {: >6.2f} sec".format(self.predictions["TIME"]))
            painter.drawText(100, 220, "Burst width : {: >6.2f} mtrs".format(self.predictions["WIDTH"]))
        self.drawCrosshair(painter, mx, my, 10, 10)

    def drawCrosshair(self, painter:QPainter, x, y, hlength=100, vlength=100, color=Qt.red):
        painter.setPen(color)
        half_length_v = vlength // 2
        half_length_h = hlength // 2

        x, y = int(x), int(y)
        # Draw vertical line
        painter.drawLine(x, y - half_length_v, x, y + half_length_v)
        # Draw horizontal line
        painter.drawLine(x - half_length_h, y, x + half_length_h, y)

    def event(self, event):
        """Handle all events - gestures, touch, and others"""
        event_type = event.type()

        # Handle gestures FIRST and with highest priority
        if event_type == QEvent.Gesture:
            print(f"📱 GESTURE EVENT in OverlayWidget!")
            result = self.gestureEvent(event)
            if result:
                return True

        # Handle touch events
        elif event_type == QEvent.TouchBegin:
            print(f"👆 TOUCH BEGIN in OverlayWidget!")
            return self.touchEvent(event)
        elif event_type == QEvent.TouchUpdate:
            return self.touchEvent(event)
        elif event_type == QEvent.TouchEnd:
            print(f"🚫 TOUCH END in OverlayWidget!")
            # 🔥 IMMEDIATELY HANDLE TOUCH END - DON'T WAIT FOR touchEvent
            return self.handleTouchEnd(event)

        # Let parent handle other events
        return super().event(event)

    def handleTouchEnd(self, event):
        """Handle touch end immediately"""
        print("🔴 IMMEDIATE TOUCH END - stopping pinch")

        # Force stop pinch mode
        self.ignore_mouse_during_pinch = False
        print("❌ Touch ended - enabling mouse mode")

        # End manual pinch if it was active
        if hasattr(self, 'initial_pinch_distance'):
            print("🔴 Manual pinch ended - stopping zoom")
            self._stop_manual_zoom()
            del self.initial_pinch_distance
            del self.last_pinch_distance
        elif self.is_zooming:
            print("🔴 Force stopping zoom (failsafe)")
            self._stop_manual_zoom()

        event.accept()
        return True
    
    def touchEvent(self, event):
        """Handle touch events with manual pinch detection"""
        touch_points = event.touchPoints()
        print(f"🖐️ TOUCH: {len(touch_points)} points")

        if len(touch_points) == 2:
            # Two-finger touch - manual pinch detection
            self.ignore_mouse_during_pinch = True
            print("✅ Multi-touch detected - enabling pinch mode")

            # Calculate distance between fingers
            p1 = touch_points[0].pos()
            p2 = touch_points[1].pos()
            current_distance = ((p1.x() - p2.x())**2 + (p1.y() - p2.y())**2)**0.5

            if not hasattr(self, 'initial_pinch_distance'):
                # Start of pinch gesture
                self.initial_pinch_distance = current_distance
                self.last_pinch_distance = current_distance
                print("🟢 Manual pinch started")
            else:
                # Check for significant change (10% threshold to avoid jitter)
                distance_change = current_distance / self.last_pinch_distance

                if distance_change > 1.1:  # 10% increase
                    print(f"📈 Manual ZOOM IN detected - distance ratio: {distance_change:.3f}")
                    self._handle_manual_zoom('in')
                    self.last_pinch_distance = current_distance
                elif distance_change < 0.9:  # 10% decrease
                    print(f"📉 Manual ZOOM OUT detected - distance ratio: {distance_change:.3f}")
                    self._handle_manual_zoom('out')
                    self.last_pinch_distance = current_distance

        elif len(touch_points) <= 1:
            # 🔥 SAFETY CHECK - Only handle if TouchEnd wasn't already processed
            if hasattr(self, 'initial_pinch_distance'):
                print(f"📱 Touch points reduced to {len(touch_points)} - ending pinch (backup)")
                self.ignore_mouse_during_pinch = False
                print("❌ Single/no touch - enabling mouse mode (backup)")

                print("🔴 Manual pinch ended - stopping zoom (backup)")
                self._stop_manual_zoom()
                del self.initial_pinch_distance
                del self.last_pinch_distance

        event.accept()
        return True

    def _handle_manual_zoom(self, direction):
        """Handle manual zoom commands"""
        # Find the VideoPlayer parent - it might be several levels up
        parent_widget = self.parent()
        max_levels = 5  # Search up to 5 levels
        level = 0

        while parent_widget and level < max_levels:
            print(f"🔍 Level {level}: Checking parent {type(parent_widget).__name__}")

            if hasattr(parent_widget, 'camera_zoom_in_command'):
                print(f"✅ Found VideoPlayer at level {level}!")
                break
            
            parent_widget = parent_widget.parent()
            level += 1

        if not parent_widget or not hasattr(parent_widget, 'camera_zoom_in_command'):
            print("❌ No VideoPlayer found in parent hierarchy!")
            return

        if not self.is_zooming or self.zoom_direction != direction:
            # Stop current zoom if direction changed
            if self.is_zooming and self.zoom_direction != direction:
                print("🛑 Stopping previous manual zoom")
                parent_widget.camera_zoom_stop_command()

            # Start new zoom direction
            if direction == 'in':
                print("🔥 Starting manual ZOOM IN")
                parent_widget.camera_zoom_in_command()
            else:
                print("🔥 Starting manual ZOOM OUT")
                parent_widget.camera_zoom_out_command()

            self.is_zooming = True
            self.zoom_direction = direction

    def _stop_manual_zoom(self):
        """Stop manual zoom commands"""
        print("🔴 _stop_manual_zoom called")

        if self.is_zooming:
            print("🔍 Looking for VideoPlayer to stop zoom...")
            # Find the VideoPlayer parent
            parent_widget = self.parent()
            max_levels = 5
            level = 0

            while parent_widget and level < max_levels:
                if hasattr(parent_widget, 'camera_zoom_stop_command'):
                    break
                parent_widget = parent_widget.parent()
                level += 1

            if parent_widget and hasattr(parent_widget, 'camera_zoom_stop_command'):
                print("🔥 Stopping manual zoom")
                parent_widget.camera_zoom_stop_command()
            else:
                print("❌ Could not find VideoPlayer to stop zoom")

            self.is_zooming = False
            self.zoom_direction = None
            print("✅ Zoom state reset")
        else:
            print("ℹ️ Zoom already stopped")

    def gestureEvent(self, event):
        """Handle gesture events"""
        print(f"🎯 GESTURE EVENT RECEIVED - Type: {event.type()}")

        # Check all available gestures
        gestures = event.gestures()
        print(f"🎯 Found {len(gestures)} gestures")

        for gesture in gestures:
            print(f"🎯 Gesture type: {gesture.gestureType()}")

        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
            print(f"👌 PINCH GESTURE FOUND!")
            return self.handlePinchGesture(pinch)
        else:
            print("❌ No pinch gesture in event")

        return False
    
    def handlePinchGesture(self, pinch: QPinchGesture):
        """Handle pinch gesture to control camera zoom"""
        print(f"🎯 PINCH GESTURE: State={pinch.state()}, Scale={pinch.scaleFactor():.3f}")

        # Find the VideoPlayer parent
        parent_player = self.parent()
        while parent_player and not hasattr(parent_player, 'camera_zoom_in_command'):
            parent_player = parent_player.parent()

        if not parent_player:
            print("❌ No parent VideoPlayer found!")
            return False

        if pinch.state() == Qt.GestureStarted:
            print("🟢 Pinch gesture started")
            self.is_zooming = False
            self.zoom_direction = None
            self._initial_scale = pinch.scaleFactor()

        elif pinch.state() == Qt.GestureUpdated:
            current_scale = pinch.scaleFactor()

            # Determine zoom direction based on scale factor
            if current_scale > 1.0:  # Pinch out = Zoom in
                new_direction = 'in'
            else:  # Pinch in = Zoom out
                new_direction = 'out'

            # Only send command if direction changed or if we weren't zooming
            if not self.is_zooming or self.zoom_direction != new_direction:
                # Stop current zoom if direction changed
                if self.is_zooming and self.zoom_direction != new_direction:
                    print("🛑 Stopping previous zoom")
                    parent_player.camera_zoom_stop_command()

                # Start new zoom direction
                if new_direction == 'in':
                    print("📈 Starting ZOOM IN")
                    parent_player.camera_zoom_in_command()
                else:
                    print("📉 Starting ZOOM OUT")
                    parent_player.camera_zoom_out_command()

                self.is_zooming = True
                self.zoom_direction = new_direction

        elif pinch.state() == Qt.GestureFinished:
            print("🔴 Pinch gesture finished")
            # Stop zooming when gesture ends
            if self.is_zooming:
                print("🛑 Stopping zoom")
                parent_player.camera_zoom_stop_command()
                self.is_zooming = False
                self.zoom_direction = None

        return True

import cv2

class VideoPrompt(QLabel):
    def __init__(self, parent=None):
        super(VideoPrompt, self).__init__(parent)
        self.overlay_widget = OverlayWidget(self)
        # self.setStyleSheet("background-color: black;")

    def resizeEvent(self, event):
        self.overlay_widget.resize(self.size())
        
class TargetVisualization(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.targets = []
        self.setMinimumSize(300, 300)

    def set_targets(self, targets):
        self.targets = targets
        self.update()  # This will trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the circle
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2 - 10
        painter.setPen(QPen(Qt.black, 2))
        painter.drawEllipse(center, radius, radius)

        # Draw range circles
        ranges = [500, 1000, 1500]
        for range_value in ranges:
            range_radius = (range_value / 2000) * radius
            painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
            painter.drawEllipse(center, range_radius, range_radius)
            painter.drawText(int(center.x() + range_radius), int(center.y()), f"{range_value}m")

        # Draw the gun at the center
        gun_size = 20
        gun_rect = QRectF(center.x() - gun_size/2, center.y() - gun_size/2, gun_size, gun_size)
        painter.setBrush(QColor(100, 100, 100))
        painter.drawRect(gun_rect)

        # Draw the targets
        painter.setPen(QPen(Qt.red, 3))
        for target in self.targets:
            # 0 degrees is up, angle increases clockwise
            angle = math.radians(90 - target['azimuth'])
            distance = target.get('distance', 1000)  # Default to 1000 if distance is not present
            distance_ratio = min(distance / 2000, 1)  # Limit to 2000m
            x = center.x() + radius * distance_ratio * math.cos(angle)
            y = center.y() - radius * distance_ratio * math.sin(angle)
            painter.drawLine(int(x-5), int(y-5), int(x+5), int(y+5))
            painter.drawLine(int(x-5), int(y+5), int(x+5), int(y-5))
            painter.drawText(int(x+10), int(y), f"{distance:.0f}m")

        # Draw a line indicating 0 degrees (straight up)
        painter.setPen(QPen(Qt.blue, 2))
        painter.drawLine(int(center.x()), int(center.y()), int(center.x()), int(center.y() - radius))

class TargetRegistration:
    def __init__(self):
        self.targets: List[Dict[str, float]] = []
        self.current_index: int = -1
        self.active: bool = False
        self.file_path: str = "pre_registered_targets.json"

    def angle_format_target(self, angle: float) -> float:
        angle = angle + 360
        angle = angle % 360
        if angle > 180:
            angle = 360 - angle
            angle = -angle
        return angle

    def start(self):
        self.active = True
        self.load_targets()
        self.current_index = -1

    def stop(self):
        self.active = False
        self.save_targets()
        self.current_index = -1

    def is_active(self):
        return self.active

    def add_target(self, azimuth: float, elevation: float, distance: float):
        formatted_azimuth = self.angle_format_target(azimuth)
        formatted_elevation = self.angle_format_target(elevation)
        self.targets.append({'azimuth': formatted_azimuth, 'elevation': formatted_elevation, 'distance': distance})
        # self.sort_targets()
        self.save_targets()
        logger.info(f"Added and saved new target: Azimuth {formatted_azimuth}, Elevation {formatted_elevation}, Distance {distance}")

    def get_next_target(self) -> Dict[str, float]:
        if len(self.targets) == 0:
            return None
        self.current_index = (self.current_index + 1) % len(self.targets)
        return self.targets[self.current_index]

    def clear_targets(self):
        self.targets = []
        self.current_index = -1
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def save_targets(self):
        # self.sort_targets()
        with open(self.file_path, 'w') as f:
            json.dump(self.targets, f, indent=2)
        logger.info(f"Saved {len(self.targets)} sorted targets to {self.file_path}")

    def load_targets(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                content = f.read().strip()
                if content:
                    loaded_targets = json.loads(content)
                    # Ensure loaded targets are in the correct format
                    self.targets = [
                        {
                            'azimuth': self.angle_format_target(target['azimuth']),
                            'elevation': self.angle_format_target(target['elevation']),
                            'distance': target.get('distance', 0)  # Default to 0 if distance is not present
                        }
                        for target in loaded_targets
                    ]
                else:
                    self.targets = []
            # self.sort_targets()
            self.print_targets()
            logger.info(f"Loaded and sorted {len(self.targets)} targets from {self.file_path}")
        else:
            self.targets = []
            logger.info("No saved targets found")

    def sort_targets(self):
        self.targets.sort(key=lambda x: x['azimuth'])
        logger.info("Targets sorted in ascending order of azimuth")
    
    def print_targets(self):
        for target in self.targets:
            logger.info(f"Azimuth: {target['azimuth']}, Elevation: {target['elevation']}, Distance: {target['distance']}")

class TargetsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Pre-registered Targets")
        self.setMinimumSize(900, 600)
        
        self.file_path = "pre_registered_targets.json"  # Add this line
        
        layout = QHBoxLayout()
        
        # Left side: Table and buttons
        left_layout = QVBoxLayout()
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["S.No.", "Azimuth", "Elevation", "Distance"])
        
        # Set the horizontal header style
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #f0f0f0;
                color: black;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)
        
        left_layout.addWidget(self.table)
        
        # Create buttons
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.save_button = QPushButton("Save")
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.save_button)
        
        left_layout.addLayout(button_layout)
        
        # Right side: Target visualization
        self.visualization = TargetVisualization(self)
        
        # Add left and right layouts to main layout
        layout.addLayout(left_layout)
        layout.addWidget(self.visualization)
        
        self.setLayout(layout)
        
        # Connect buttons to functions
        self.add_button.clicked.connect(self.add_target)
        self.edit_button.clicked.connect(self.edit_target)
        self.delete_button.clicked.connect(self.delete_target)
        self.save_button.clicked.connect(self.save_targets)
        
        # Connect table item changed signal
        self.table.itemChanged.connect(self.on_item_changed)
        
        self.load_targets()
    
    def load_targets(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                content = f.read().strip()
                if content:
                    loaded_targets = json.loads(content)
                    self.parent.target_registration.targets = [
                        {
                            'azimuth': target['azimuth'],
                            'elevation': target['elevation'],
                            'distance': target.get('distance', 1000)  # Default to 1000 if distance is not present
                        }
                        for target in loaded_targets
                    ]
                else:
                    self.parent.target_registration.targets = []
            self.update_table()
            self.update_visualization()
            logger.info(f"Loaded {len(self.parent.target_registration.targets)} targets from {self.file_path}")
        else:
            self.parent.target_registration.targets = []
            logger.info("No saved targets found")
    
    def update_table(self):
        self.table.setRowCount(len(self.parent.target_registration.targets))
        for i, target in enumerate(self.parent.target_registration.targets):
            self.table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.table.setItem(i, 1, QTableWidgetItem(f"{target['azimuth']:.2f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{target['elevation']:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{target['distance']:.2f}"))
        self.update_serial_numbers()
    
    def add_target(self):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        self.table.setItem(row_count, 0, QTableWidgetItem(str(row_count+1)))
        self.table.setItem(row_count, 1, QTableWidgetItem("0.00"))
        self.table.setItem(row_count, 2, QTableWidgetItem("0.00"))
        self.table.setItem(row_count, 3, QTableWidgetItem("1000.00"))
        self.update_serial_numbers()
        self.update_visualization()
    
    def edit_target(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            for col in range(1, 4):
                item = self.table.item(current_row, col)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.table.editItem(self.table.item(current_row, 1))
    
    def delete_target(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.update_serial_numbers()
            self.update_visualization()
    
    def update_serial_numbers(self):
        for i in range(self.table.rowCount()):
            self.table.setItem(i, 0, QTableWidgetItem(str(i+1)))
    
    def update_visualization(self):
        targets = []
        for row in range(self.table.rowCount()):
            azimuth_item = self.table.item(row, 1)
            elevation_item = self.table.item(row, 2)
            distance_item = self.table.item(row, 3)
            if azimuth_item and elevation_item and distance_item:
                try:
                    azimuth = float(azimuth_item.text())
                    elevation = float(elevation_item.text())
                    distance = float(distance_item.text())
                    targets.append({"azimuth": azimuth, "elevation": elevation, "distance": distance})
                except ValueError:
                    print(f"Invalid value in row {row+1}. Skipping this target.")
        self.visualization.set_targets(targets)
    
    def on_item_changed(self, item):
        if item.column() in [1, 2, 3]:  # Update for changes in azimuth, elevation, or distance
            self.update_visualization()
    
    def save_targets(self):
        targets = []
        for row in range(self.table.rowCount()):
            azimuth_item = self.table.item(row, 1)
            elevation_item = self.table.item(row, 2)
            distance_item = self.table.item(row, 3)
            if azimuth_item and elevation_item and distance_item:
                try:
                    azimuth = float(azimuth_item.text())
                    elevation = float(elevation_item.text())
                    distance = float(distance_item.text())
                    targets.append({"azimuth": azimuth, "elevation": elevation, "distance": distance})
                except ValueError:
                    print(f"Invalid value in row {row+1}. Skipping this target.")
        
        self.parent.target_registration.targets = targets
        self.parent.target_registration.save_targets()
        logger.info(f"Saved {len(targets)} targets")
        self.close()

class CustomLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        # Check if the pressed key is the Delete key
        if event.key() == Qt.Key_Delete:
            # Clear the text in the input field
            self.clear()
        else:
            # Call the base class implementation for other keys
            super().keyPressEvent(event)

class VideoPlayer(QWidget):
    recv_angle_event = pyqtSignal(float, float)
    pAngleEvent = HvsSDK.angle.angle_event(angle_event)
    pLaserRangingEvent = HvsSDK.extern.extern_laser_event(laser_event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logged_in = False
        self.setWindowTitle("AITuring")
        self.showFullScreen()
        self.login_dialog = None
        self.system_type = None
        self.pan_params = Parameter()
        self.tilt_params = Parameter()
        self.config_screen = ConfigScreen()
        self.config_screen.config_saved.connect(self.reload_config)
        self.config_screen.save_signal.connect(self.update_config_variables)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_taboo_visualizer)
        self.update_timer.start(200)

        # Initialize CASTLE gunshot detection system (add after self.update_timer.start(200))
        self.castle_listener = CASTLEListener(
            video_player_instance=self,  # Pass self so it can call position_gun()
            debug=False  # Set to False in production
        )
        self.fire_detection_active = False

        # Start CASTLE listener in background
        # self.castle_listener.start_listening()

        # if hasattr(self, 'castle_listener') and self.castle_listener.logger:
        print(f"🔥 Fire Detection system initialized (logging will start when button is pressed)")
    

        self.diagnose_screen = DiagnoseScreen(self.pan_params, self.tilt_params)
        self.notification_overlay = NotificationOverlay(self)
        self.fine_speed = False
        self.stabilization_active = False
        self.scan_running = False
        self.track_started = False
        self.touch_to_aim_started = False
        self.head_tracking = False

        self.ballistics_v_diff = 0
        self.ballistics_h_diff = 0 

        # Console related variables
        self.zoom_in_flag = False
        self.zoom_out_flag = False
        self.focus_in_flag = False
        self.focus_out_flag = False
        self.day_night_flag = False
        self.stab_flag = False
        self.lay_flag = False
        self.zero_gun_flag = False
        self.bal_flag = False
        self.mode_flag = False
        self.track_flag = False
        self.black_hot_flag = False
        self.released = True
        self.scan_flag = False
        self.brake_enabled = False
        self.show_targets = False
        self._pressed_for = 0
        self.lay_start_time = 0
        self.thermal_start_time = 0
        self.bal_start_time = 0
        self.counter = 0

        self.zoom_value = 0
        self.current_lay_index = 0

        self.dir_map = {
            "0": "6-12", "1": "7-1", "2": "8-2", "3": "9-3",
            "4": "10-4", "5": "11-5", "6": "12-6", "7": "1-7",
            "8": "2-8", "9": "3-9", "10": "4-10", "11": "5-11"
        }

        # Initialize configuration
        self.config = ConfigParserCrypt()
        self.config.aes_key = b'\xfa\xc1\x1e\xdf6\xa9\xad\xc4h\xeb\xc2*\xd9l\xb0\xea \xc6?\x1bq\x85\xc4\x1c\x80\x1f\x05\x8b\xc3\xda\xdeB'
        # self.load_config()
        self.default_load_config()
        logger.info(f"Initial manual_wind_speed after loading config: {self.manual_wind_speed}")

        self.wind_speed_value = None
        self.wind_direction_value = None

        # Initialize buttons and layoutGs
        self.check_login_status()

        limits = get_system_limits(self.system_type)
        self.prev_pan_left_limit = limits['PAN_LEFT_LIMIT']
        self.prev_pan_right_limit = limits['PAN_RIGHT_LIMIT']
        self.prev_tilt_bottom_limit = limits['TILT_BOTTOM_LIMIT']
        self.prev_tilt_top_limit = limits['TILT_TOP_LIMIT']

        self.ipc_object = HvsSDK.IPC_device(DeviceType_e.DEVICE_HPWS)
        self.light_play_id = ctypes.c_int()
        self.ird_play_id = ctypes.c_int()
        self.connected = False
        self.currentindex = 0
        self.wind_correction_azimuth = 0.0
        self.wind_correction_elevation = 0.0
        self.apply_wind_correction = False
        self.default_distance = 1000
        self.velo_speed = 50 
        self.connect_device()
        self.connect_camera()
        self.recv_angle_event.connect(self.set_angle_cam)
        self.smoother = JoystickSmoother(dead_zone=0.1, exponent=3, alpha_slow=0.1, alpha_fast=0.2)
        self.ballistics = PolynomialPredictor('rangetable.csv')
        self.ballistics_nsvt = PolynomialPredictorNSVT('rangetableNSVT.csv')

        self.gun_controller = TinyFrameGunController(function=self.set_angle_gun, function_error=self.handle_error, parent=self, pan_params=self.pan_params, tilt_params=self.tilt_params, config_screen=self.config_screen, logout_function=self.logout, inclinometer_callback=self.set_inclinometer_data)

        # self.auto_pilot_controller = AutoPilotController()

        # self.auto_pilot_controller.stab_change.connect(self.handle_stab_change)
        # # self.auto_pilot_controller.start()

        self.auto_pilot_controller = AutoPilotController()
        self.stab_data_timer = QTimer(self)
        self.stab_data_timer.timeout.connect(self.check_stab_data)
        self.stab_data_timer.start(50)

        # virtual crosshair timer (double ring)
        self.double_ring_crosshair_timer_running = False
        self.received_inclinometer_data = False
        self.corr_el = None 
        self.corr_az = None

        self.double_ring_crosshair_timer = QTimer(self)
        self.double_ring_crosshair_timer.timeout.connect(self.update_double_ring_crosshair)
        
        # Radar related variables
        self.listening_radar = False
        self.tracking = False
        self.sending_offsets = False

        self.joystick_mappings = {
            "Saitek Pro Flight X-56 Rhino Stick": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 7,
                "left": 1,
                "up": 2,
                "down": 3,
                "half_adjustment": 4,
                "right": 5
            },
            "Mad Catz, Inc. 4-Port USB 2.0 Hub": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 7,
                "left": 1,
                "up": 2,
                "down": 3,
                "half_adjustment": 4,
                "right": 5
            },
            "3D Joystick Keyboard (4-axes)": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 7,
                "left": 1,
                "up": 2,
                "down": 3,
                "half_adjustment": 4,
                "right": 5
            },
            "Sony Corp. 4-Port USB 2.0 Hub (4-axes)": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 7,
                "left": 1,
                "up": 2,
                "down": 3,
                "half_adjustment": 4,
                "right": 5
            },
            "3D Joystick Keyboard (5-axes)": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 3,
                "left": 8,
                "up": 1,
                "down": 2,
                "half_adjustment": 10,
                "right": 9,
                "zoom+": 4,
                "zoom-": 5
            },
            "Sony Corp. 4-Port USB 2.0 Hub (5-axes)": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 4,
                "left": 8,
                "up": 1,
                "down": 2,
                "half_adjustment": 5,
                "right": 9
            },
            "China Longcctv 3D Joystick Keyboard": {
                "lrf": 0,
                "trigger": 6,
                "pre_register": 7,
                "left": 1,
                "up": 2,
                "down": 3,
                "half_adjustment": 4,
                "right": 5
            }
        }

        self.target_registration = TargetRegistration() 
        self.button_7_press_time = 0
        self.LONG_PRESS_DURATION = 1.0

        joystick_count = pygame.joystick.get_count()
        if joystick_count == 0:
            print("No Joysticks connected. Using ASWD from keyboard")
            self.program = JoyStickThread0(self)
        elif joystick_count == 1:
            joy = pygame.joystick.Joystick(0)
            name = joy.get_name()
            axes = joy.get_numaxes()
            keys = list(self.joystick_mappings)
            if sys.platform == "win32":
                if name.startswith("3D"):
                    if axes == 4:
                        print("Platform: ", sys.platform, "\nName: ", name, "\tAxes: ", axes, "\nSelected: 3D Joystick Keyboard (4-axes)")
                        self.program = JoyStickThread4(self)
                        self.mapping = self.joystick_mappings["3D Joystick Keyboard (4-axes)"]
                    elif axes == 5:
                        print("Platform: ", sys.platform, "\nName: ", name, "\tAxes: ", axes, "\nSelected: 3D Joystick Keyboard (5-axes)")
                        self.program = JoyStickThread5(self)
                        self.mapping = self.joystick_mappings["3D Joystick Keyboard (5-axes)"]
                elif name.startswith("Saitek"):
                    print("Platform: ", sys.platform, "\nName: ", name, "\tAxes: ", axes, "\nSelected: Saitek Pro Flight X-56 Rhino Stick")
                    self.program = JoyStickThread5(self)
                    self.mapping = self.joystick_mappings["Saitek Pro Flight X-56 Rhino Stick"]
                else:
                    logger.warning("Unknown Joystick")
            elif sys.platform.startwith("linux"):
                if name.startswith("Sony"):
                    if axes == 4:
                        self.program = JoyStickThread4(self)
                        self.mapping = self.joystick_mappings["Sony Corp. 4-Port USB 2.0 Hub (4-axes)"]
                    elif axes == 5:
                        self.program = JoyStickThread5(self)
                        self.mapping = self.joystick_mappings["Sony Corp. 4-Port USB 2.0 Hub (5-axes)"]
                elif name.startswith("Mad"):
                    self.program = JoyStickThread5(self)
                    self.mapping = self.joystick_mappings["Mad Catz, Inc. 4-Port USB 2.0 Hub"]
                else:
                    logger.warning("Unknown Joystick")

        # self.program = JoyStickThread(self)
        self.program.error_signal.connect(self.handle_error)
        self.last_axis_sent = None
        self.throttled_handle_change_axis_signal = throttle(self.handle_change_axis_signal, 16)
        self.program.change_axis_signal.connect(self.throttled_handle_change_axis_signal)
        self.program.button_signal.connect(self.handle_button_signal)
        self.program.start()

        self.timer_target = QTimer(self)
        self.targeted = False

        self.anemometer = RS485WindSpeedTransmitter()
        self.wind_speed_mode = 'Manual'
        self.manual_wind_speed = 0

        self.pan_left_limit = limits['PAN_LEFT_LIMIT']
        self.pan_right_limit = limits['PAN_RIGHT_LIMIT']
        self.tilt_bottom_limit = limits['TILT_BOTTOM_LIMIT']
        self.tilt_top_limit = limits['TILT_TOP_LIMIT']

        logger.critical(f"{self.pan_left_limit, self.pan_right_limit, self.tilt_bottom_limit, self.tilt_top_limit}")


        self._inclinometer_x = 0.0
        self._inclinometer_y = 0.0
        self._inclinometer_z = 0.0
        self._inclinometer_pitch = 0.0
        self._inclinometer_roll = 0.0

        self.looping_movement = False
        self.looping_thread = None

        self.canline_open = False
        # Add the new shortcut for looping movement
        # self.loop_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        # self.loop_shortcut.activated.connect(self.toggle_looping_movement)


        self.armed = False
        self.shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.shortcut.activated.connect(self.toggle_armed_state)

        self.shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        self.shortcut.activated.connect(self.toggle_head_tracking)

        self.radar_listener_shortcut = QShortcut(QKeySequence("Ctrl+U"), self)
        self.radar_listener_shortcut.activated.connect(self.toggle_radar_listener)

        self.tracking_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self.tracking_shortcut.activated.connect(self.toggle_object_tracking)

        self.stop_track_shortcut = QShortcut(QKeySequence("U"), self)
        self.stop_track_shortcut.activated.connect(self.stop_track_from_keyboard)

        self.object_tracking = False
        self.range_sending_active = False
        self.last_sent_range = -1
        self.throttled_position_gun_from_object_trcker = throttle(self.position_gun_from_object_tracker, 10)

        self.ball_value = 500
        self.ballistics_active = False
        self.create_ballistics_indicator()
        # self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+B"), self)
        # self.shortcut.activated.connect(self.toggle_ballistics)

        # self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+N"), self)
        # self.shortcut.activated.connect(self.increase_bal)

        # self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        # self.shortcut.activated.connect(self.decrease_bal)

        self.create_pre_registration_indicator()
        self.update_pre_registration_indicator()

        self.pre_register_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self)
        self.pre_register_shortcut.activated.connect(self.toggle_pre_registration_mode)

        self.wind_update_timer = QTimer(self)
        self.wind_update_timer.timeout.connect(self.update_wind_data)
        self.wind_update_timer.start(600) #Timer for updating Wind data 6000ms
        
        self.targets_dialog = None
        self.looping_movement = False
        self.looping_thread = None
        self.set_inclinometer_data = False
        self.plane_elevation = None
        self.range_table = {
            500: 0.28, 550:0.32, 600:0.37, 650:0.42, 700:0.478, 750:0.53,
            800:0.596, 850:0.66, 900:0.736, 950:0.815, 1000:0.9, 1050:0.99 ,
            1100:1.08, 1150:1.18, 1200:1.28, 1250:1.389, 1300:1.5, 1350:1.61, 1400:1.73
        }
        self.ballistic_table = {500: 0.28, 550: 0.32, 600: 0.36, 650: 0.4, 700: 0.45, 750: 0.5, 800: 0.55, 
                                850: 0.61, 900: 0.67, 950: 0.73, 1000: 0.8, 1050: 0.88, 1100: 0.96, 1150: 1.04, 
                                1200: 1.13, 1250: 1.23, 1300: 1.33, 1350: 1.45, 1400: 1.57, 1450: 1.7, 1500: 1.83, 
                                1550: 1.98, 1600: 2.14, 1650: 2.31, 1700: 2.5, 1750: 2.7, 1800: 2.91, 1850: 3.14}
        self.h_fov = 100
        self.v_fov = 100
        self.bal_indicator_running = False

        # ser = serial.Serial("COM9", 115200, timeout=1)
        # ports = serial.tools.list_ports.comports(include_links=False)
        # for port in ports:
        #     if "Arduino Mega" in port.description:
        #         ser = serial.Serial(port.device, 115200, timeout=1)
        
        # self.RCWS_drivePWR = 1
        # self.tf = TinyFrameComm(ser=ser, parent=self)
        # self.tf.data_received.connect(self.handle_arduino_data)
        # self.tf.start()
        # listener_thread = threading.Thread(target=self.tf.run)
        # listener_thread.start()

        # try:
        #     self.cgi_login()
        # except:
        #     logger.error("CGI Login Failed")

        self.mapping_indicator_timer = QTimer(self)
        self.mapping_indicator_timer.timeout.connect(self.update_mapping_indicators)
        self.mapping_indicator_timer.start()

        # self.bal_indicator = QTimer(self)
        # self.bal_indicator.timeout.connect(self.show_ballistics)

        # self.auto_gun_speed_timer = QTimer(self)
        # self.auto_gun_speed_timer.timeout.connect(self.auto_update_gun_speed)
        # self.auto_gun_speed_timer.start(1000)

        self.lrf_timer = QTimer(self)
        self.lrf_timer.timeout.connect(self.fire_lrf)

        self.range_sender = QTimer(self)
        self.range_sender.timeout.connect(self.send_range)
    
    # def send_range(self):
    #     self.gun_controller.send_range(self._lrf_dist_1)

    def wrap_pm180(self, a):
        # wrap to (-180, 180]
        a = (a + 180.0) % 360.0 - 180.0
        if a == -180.0:
            a = 180.0
        return a

    def geo_to_rcws_angles(self, az_geo_deg, el_geo_deg, rcws_at_north_deg=60.0):
        """Convert geographic az/el to RCWS frame.
           az_rcws in (-180..+180], el_rcws clamped to [-5..45]."""
        az_rcws = self.wrap_pm180(az_geo_deg + rcws_at_north_deg)
        el_rcws = max(-5.0, min(45.0, el_geo_deg))
        return az_rcws, el_rcws

    def get_az_el(self):
        """
        Compute azimuth (-180..+180) and elevation (-5..+45 clamped)
        from point1 -> point2 (lat/lon in degrees, alt in meters).
        """
        lat1 = 34.152300
        lon1 = 77.577000
        alt1 = 3500

        lat2 = self.latitude
        lon2 = self.longitude
        alt2 = self.altitude

        R = 6371000.0  # Earth radius (m)

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine ground distance
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        ground_dist = R * c

        # Azimuth (bearing from north, clockwise)
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
        az = math.degrees(math.atan2(y, x))

        # Wrap azimuth to −180..+180
        if az > 180:
            az -= 360
        elif az < -180:
            az += 360

        delta_alt = alt2 - alt1
        el = math.degrees(math.atan2(delta_alt, ground_dist))

        # Clamp elevation to −5..+45
        el = max(-5.0, min(45.0, el))

        return az, el

    def lay_on_gps(self):
        az, el = self.get_az_el()
        print(f"Required Az, el wrt North: {az, el}")
        az, el = self.geo_to_rcws_angles(az, el, 60)
        print(f"Required Az, El: {az, el}")
        self.position_gun(az, el)

    def send_track_offsets(self):
        if not self.sending_offsets:
            self.range_sender.start(100)
        else:
            self.range_sender.stop()
        self.sending_offsets = not self.sending_offsets
         # Update button appearance
        for button in self.findChildren(QPushButton):
            if button.text() == "Send Offsets":
                button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;" if self.sending_offsets else "")
                    
    def stop_track_from_keyboard(self):
        """Stop tracking when U key is pressed"""
        try:
            if self.tracking:  # Only stop if tracking is active
                self.stop_track()
                logger.info("Manual stop track requested via keyboard (U key)")
                # Optionally show a brief notification
                # QMessageBox.information(self, "Tracking", "Tracking stopped via keyboard")
        except Exception as e:
            logger.error(f"Error stopping track via keyboard: {e}")

    def toggle_object_tracking(self):
        print(f"[INFO Toggled Tracking]")
        if not self.object_tracking:
            self.object_tracker = ObjectDetector(parent=self, video_player=self)
            self.object_tracker.data_received.connect(self.throttled_position_gun_from_object_trcker)
            self.object_tracker.start()
        else:
            self.object_tracker.stop()
            del self.object_tracker
 
        self.object_tracking = not self.object_tracking
 
    def position_gun_from_object_tracker(self, offset_x, offset_y):
        print(f"[INFO] OffsetX: {offset_x}, OffsetY: {offset_y}")
        # self.position_gun(self._gun_azimuth + offset_x, self._gun_elevation + offset_y)
        self.gun_controller.vmove(offset_x, offset_y)
    
    def start_laptop_camera(self):
        # Open default camera (0 = laptop webcam)
        self.cap = cv2.VideoCapture(0)
    
        # Create a timer to grab frames periodically
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~30 FPS

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Optional: rotate 180° if your feed needs flipping
            frame = cv2.rotate(frame, cv2.ROTATE_180)

            # Convert frame to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            qimg = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.video_light.width(),
                self.video_light.height(),
                Qt.KeepAspectRatio,  # maintains aspect ratio
                Qt.SmoothTransformation
            )
            # Display on video_light
            self.video_light.setPixmap(pixmap)

     

    def handle_arduino_data(self, data):
        camera_zoom_in, camera_zoom_out, camera_focus_in, camera_focus_out, camera_lrf, camera_day_therm, camera_black_white_hot, res0 = map(int, f"{int(data[0]):08b}"[::-1])
        RCWS_mode, RCWS_trackStatus, RCWS_stab, RCWS_ballisticStatus, RCWS_zeroGun, RCWS_layOn, self.RCWS_drivePWR, res1 = map(int, f"{int(data[1]):08b}"[::-1])
        Wind = int(data[2])
        DriveSpeed = int(data[3])
        E_stop = int(data[4])
        DrivePWR = int(data[5])
        self.counter += 1
        # print(f"""Camera Zoom in: {camera_zoom_in}\nCamera Zoom out: {camera_zoom_out}\nCamera Focus in: {camera_focus_in}\n
        #         Camera Focus out: {camera_focus_out}\nCamera LRF: {camera_lrf}\nCamera D/N: {camera_day_therm}\n
        #         Camera B/W Hot: {camera_black_white_hot}\n\nRCWS Mode: {RCWS_mode}\nRCWS Track Status: {RCWS_trackStatus}\n
        #         RCWS Stabilization: {RCWS_stab}\nRCWS Ballistics: {RCWS_ballisticStatus}\nRCWS Zero Gun: {RCWS_zeroGun}\n
        #         RCWS Lay On: {RCWS_layOn}\nRCWS Arm: {RCWS_drivePWR}\n\nWind: {Wind}\nDriveSpeed: {DriveSpeed}\nE_Stop: {E_stop}\n
        #         Drive Power: {DrivePWR}""")
        
        # if self.counter == 5:
        #     self.counter = 0
        #     try:
        #         night_zoom = self.ipc_object.get_zoom(VideoType_e.VT_IRD).value
        #         day_zoom = self.ipc_object.get_zoom(VideoType_e.VT_LIGHT).value
        #         # print("Day Zoom: ", day_zoom)
        #         if self.stackedWidget.currentIndex() == 1:
        #             self.progress_bar_1.setValue(int(day_zoom * 1.22))
        #             # print(str(int(day_zoom * 1.22)))
        #             self.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))
        #         else:
        #             self.progress_bar_1.setValue(int(night_zoom * 1.22))
        #             self.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))

        #         night_focus = self.ipc_object.get_focus(VideoType_e.VT_IRD).value
        #         day_focus = self.ipc_object.get_focus(VideoType_e.VT_LIGHT).value
        #         # print("Day Focus: ", day_focus.value)
        #         if self.stackedWidget.currentIndex() == 1:
        #             self.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
        #             self.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
        #         else:
        #             self.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
        #             self.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
        #     except:
        #         print("Error in receiving Data from camera")
        # night_fov = self.VideoObj.ipc_object.get_fov(VideoType_e.VT_IRD).value
        # day_fov = self.VideoObj.ipc_object.get_fov(VideoType_e.VT_LIGHT).value
        # if self.VideoObj.stackedWidget.currentIndex() == 1:
        #     self.VideoObj.pan_tilt_widget.update_values(self.VideoObj.gunAzimuth.text(), day_fov)
        # else:
        #     self.VideoObj.pan_tilt_widget.update_values(self.VideoObj.gunAzimuth.text(), night_fov)

        # az = 90 - float(self.gunAzimuth.text())
        # if az < 0:
        #     az += 360
        # el = float(self.gunElevation.text()) - 90
        # if el < 0:
        #     el += 360
        # self.pan_widget.update_values(az, 60) 
        # self.tilt_widget.update_values(el, 60)       

        if not camera_zoom_in and not self.zoom_in_flag:
            self.zoom_in_flag = True
            self.control_camera(CameraType_e.CCT_ZOOM_IN, True)
        elif camera_zoom_in and self.zoom_in_flag:
            self.zoom_in_flag = False
            self.control_camera(CameraType_e.CCT_ZOOM_IN, False)
            # night_zoom = self.ipc_object.get_zoom(VideoType_e.VT_IRD).value
            # day_zoom = self.ipc_object.get_zoom(VideoType_e.VT_LIGHT).value
            # # print("Day Zoom: ", day_zoom)
            # if self.stackedWidget.currentIndex() == 1:
            #     self.progress_bar_1.setValue(int(day_zoom * 1.22))
            #     # print(str(int(day_zoom * 1.22)))
            #     self.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))
            # else:
            #     self.progress_bar_1.setValue(int(night_zoom * 1.22))
            #     self.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))
        
        if not camera_zoom_out and not self.zoom_out_flag:
            self.zoom_out_flag = True
            self.control_camera(CameraType_e.CCT_ZOOM_OUT, True)
        elif camera_zoom_out and self.zoom_out_flag:
            self.zoom_out_flag = False
            self.control_camera(CameraType_e.CCT_ZOOM_OUT, False)
            # night_zoom = self.ipc_object.get_zoom(VideoType_e.VT_IRD).value
            # day_zoom = self.ipc_object.get_zoom(VideoType_e.VT_LIGHT).value
            # # print("Day Zoom: ", day_zoom)
            # if self.stackedWidget.currentIndex() == 1:
            #     self.progress_bar_1.setValue(int(day_zoom * 1.22))
            #     # print(str(int(day_zoom * 1.22)))
            #     self.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))
            # else:
            #     self.progress_bar_1.setValue(int(night_zoom * 1.22))
            #     self.progress_bar_1_value.setText(str(int(day_zoom * 1.22)))

        if not camera_focus_in and not self.focus_in_flag:
            self.focus_in_flag = True
            self.control_camera(CameraType_e.CCT_FOCUS_FAR, True)
        elif camera_focus_in and self.focus_in_flag:
            self.focus_in_flag = False
            self.control_camera(CameraType_e.CCT_FOCUS_FAR, False)
            # night_focus = self.ipc_object.get_focus(VideoType_e.VT_IRD).value
            # day_focus = self.ipc_object.get_focus(VideoType_e.VT_LIGHT).value
            # # print("Day Focus: ", day_focus.value)
            # if self.stackedWidget.currentIndex() == 1:
            #     self.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
            #     self.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
            # else:
            #     self.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
            #     self.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
        
        if not camera_focus_out and not self.focus_out_flag:
            self.focus_out_flag = True
            self.control_camera(CameraType_e.CCT_FOCUS_NEAR, True)
        elif camera_focus_out and self.focus_out_flag:
            self.focus_out_flag = False
            self.control_camera(CameraType_e.CCT_FOCUS_NEAR, False)
            # night_focus = self.ipc_object.get_focus(VideoType_e.VT_IRD).value
            # day_focus = self.ipc_object.get_focus(VideoType_e.VT_LIGHT).value
            # # print("Day Focus: ", day_focus.value)
            # if self.stackedWidget.currentIndex() == 1:
            #     self.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
            #     self.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))
            # else:
            #     self.progress_bar_2.setValue(int(((day_focus - 35265)*100)/(36168-35265)))
            #     self.progress_bar_2_value.setText(str(int(((day_focus - 35265)*100)/(36168-35265))))

        # if camera_lrf:
        #     self.VideoObj.fire_lrf()

        if not camera_day_therm and not self.day_night_flag:
            self.thermal_start_time = time.time()
            self.day_night_flag = True
            self.switchClicked()
        elif camera_day_therm:
            pressed_for = time.time() - self.thermal_start_time
            self.day_night_flag = False
            # if pressed_for > 2:
            #     self.VideoObj.ToggleThermalPower()
            # self.VideoObj.switchClicked()

        if not camera_black_white_hot and not self.black_hot_flag and self.released:
            self.setBlackHot()
            self.black_hot_flag = True
            self.released = False
        elif camera_black_white_hot:
            self.released = True
        elif not camera_black_white_hot and self.black_hot_flag and self.released:
            self.setWhiteHot()
            self.black_hot_flag = False
            self.released = False

        if not RCWS_mode and not self.mode_flag: # Pre register mode ON/OFF
            self.mode_flag = True
            self.toggle_pre_registration_mode()
        elif RCWS_mode and self.mode_flag:
            self.mode_flag = False
            self.toggle_pre_registration_mode()
        
        if not RCWS_trackStatus and not self.track_flag:
            self.track_flag = True
            # self.gun_controller.start_track()
            self.toggle_track()
        elif RCWS_trackStatus and self.track_flag:
            self.track_flag = False
            # self.gun_controller.stop_track()
            self.toggle_track()

        if not RCWS_stab and not self.stab_flag:
            self.stab_flag = True
            self.toggleStabilization()
        elif RCWS_stab and self.stab_flag:
            self.stab_flag = False
            self.toggleStabilization()
        
        if not RCWS_ballisticStatus and not self.bal_flag:
            self.bal_flag = True
            # self.toggle_ballistics()
            if self.system_type == "NSVT":
                self.nsvt_ballistics()
            else:
                self.toggleBal()
        elif RCWS_ballisticStatus and self.bal_flag:
            self.bal_flag = False
            if self.system_type == "NSVT":
                self.nsvt_ballistics()
            else:
                self.toggleBal()

        # if not RCWS_ballisticStatus and not self.bal_flag:
        #     self.bal_flag = True
        #     self.bal_start_time = time.time()
        #     if self.bal_indicator_running:
        #         self.bal_indicator.stop()
        #         self.bal_indicator_running = False
        #         self.bal_overlay_ird.toggle_curve(False, [], [], None, None, None, None)
        #         self.bal_overlay_light.toggle_curve(False, [], [], None, None, None, None)
        #     else:
        #         self.bal_indicator.start(1000)
        #         self.bal_indicator_running = True
        # elif RCWS_ballisticStatus and self.bal_flag:
        #     press_time = time.time() - self.bal_start_time
        #     self.bal_flag = False
        #     if press_time > 1:
        #         self.toggleBal()
        #         self.bal_start_time = 0
        
        if not RCWS_zeroGun and not self.zero_gun_flag:
            self.zero_gun_flag = True
            self.position_gun(0, 0)
        elif RCWS_zeroGun and self.zero_gun_flag:
            self.zero_gun_flag = False

        if not camera_lrf and not self.show_targets:
            self.show_targets = True
            self.show_targets_dialog()
        elif RCWS_zeroGun and self.show_targets:
            self.show_targets = False
        
        if not RCWS_layOn and not self.lay_flag:
            self.lay_start_time = time.time()
            self.lay_flag = True
            self.x_in.setFocus()
        elif RCWS_layOn and self.lay_flag:
            self._pressed_for = time.time() - self.lay_start_time
            self.current_lay_index += 1
            self.lay_flag = False       

            if self._pressed_for > 1:
                print("Laying Gun")
                self.make_move_gun()
                self._pressed_for = 0
                self.lay_start_time = 0

        if not self.RCWS_drivePWR and not self.brake_enabled:
            self.brake_enabled = True
            if not self.armed:
                self.gun_controller.unbrake()
        elif self.RCWS_drivePWR and self.brake_enabled:
            self.brake_enabled = False
            self.gun_controller.brake()

        if Wind != self.manual_wind_speed:
            self.manual_wind_speed = Wind
            self.wind_speed_value.setValue(int(Wind))
            print("Wind: ", Wind)
        
        if not res1 and not self.scan_flag:
            print("selfcheck on")
            self.scan_flag = True
           #  self.selfCheck()
        elif res1 and self.scan_flag:
            print("SELFCHECK OFF")
            #self.scan_flag = False

        # if DriveSpeed != self.gun_speed:
        #     self.setGunSpeed(int(DriveSpeed))
        #     print("Drive Speed: ", DriveSpeed)

        # if E_stop:
        #     pass

        # if DrivePWR:
        #     pass

    # def toggle_radar_listener(self):
    #     if not self.listening_radar:
    #         self.radar_listener = HardkillDrone(
    #             video_player=self, 
    #             camera=self.camera, 
    #             server_ip=self.radar_ip,
    #             server_port=self.radar_port, 
    #             parent=self
    #         )
    #         self.radar_listener.start()
    #     else:
    #         self.radar_listener.stop()
    #     self.listening_radar = not self.listening_radar

    def toggle_range_sender(self):
        """Toggle range sending to gun controller from radar data"""
        if not self.listening_radar:
            logger.warning("Radar listener is not active. Cannot toggle range sender.")
            # QMessageBox.warning(self, "Warning", "Please enable Radar Listener first (Ctrl+U)")
            return
        
        self.range_sending_active = not self.range_sending_active
        
        if self.range_sending_active:
            logger.info("Range sender ACTIVATED - will send range from radar to gun controller")
            self.last_sent_range = -1  # Reset last sent range
            self.range_sender.start(100)  # Check every 100ms
            
            # Update button appearance
            for button in self.findChildren(QPushButton):
                if button.text() == "Bal-":
                    button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;")
        else:
            logger.info("Range sender DEACTIVATED")
            self.send_null_range()
            self.range_sender.stop()
            
            # Update button appearance
            for button in self.findChildren(QPushButton):
                if button.text() == "Bal-":
                    button.setStyleSheet("")
    
    def send_null_range(self):
        self.gun_controller.send_range(0)

    def send_range(self):
        """Send range to gun controller only when conditions are met"""
        if not hasattr(self, 'radar_listener') or not self.listening_radar:
            logger.debug("Radar listener not active, stopping range sender")
            self.range_sending_active = False
            self.range_sender.stop()
            return
        
        # Get range from radar listener
        current_range = self.radar_listener._range
        
        # Don't send if range is -1 (invalid)
        if current_range == -1:
            logger.debug(f"Range is -1 (invalid), not sending")
            return
        
        # Only send if range changed by 100m or more
        range_diff = abs(current_range - self.last_sent_range)
        
        if range_diff >= 100:
            logger.info(f"Range changed by {range_diff}m (from {self.last_sent_range}m to {current_range}m), sending to gun controller")
            self.gun_controller.send_range(current_range)
            self.last_sent_range = current_range
        else:
            logger.debug(f"Range difference {range_diff}m is less than 100m threshold, not sending")

    def toggle_radar_listener(self):
        if not self.listening_radar:
            self.radar_listener = HardkillDrone(
                video_player=self, 
                camera=self.camera, 
                server_ip=self.radar_ip,
                server_port=self.radar_port, 
                parent=self
            )
            self.radar_listener.start()
        else:
            # Stop range sender when radar listener stops
            if self.range_sending_active:
                logger.info("Stopping range sender because radar listener is being stopped")
                self.range_sending_active = False
                self.send_null_range()
                self.range_sender.stop()
                
                # Update button appearance
                for button in self.findChildren(QPushButton):
                    if button.text() == "Bal-":
                        button.setStyleSheet("")
            
            self.radar_listener.stop()
        
        self.listening_radar = not self.listening_radar
                
    def update_double_ring_crosshair(self):
        h_fov, v_fov = self.getFOV()
        if self.stackedWidget.currentIndex() == 0:
            self.overlay_ird.toggle_rectangle(True, self.corr_az, self.corr_el, h_fov, v_fov, width=1.25*512, height=512)
        else:
            self.overlay_light.toggle_rectangle(True, self.corr_az, self.corr_el, h_fov, v_fov, width=1092, height=614)

    def camera_zoom_in_command(self):
        """Send zoom in command to network camera"""
        print("🔥 ZOOM IN COMMAND EXECUTED!")
        if self.connected:
            self.control_camera(CameraType_e.CCT_ZOOM_IN, True)
        else:
            print("❌ Not connected to camera")

    def camera_zoom_out_command(self):
        """Send zoom out command to network camera"""
        print("🔥 ZOOM OUT COMMAND EXECUTED!")
        if self.connected:
            self.control_camera(CameraType_e.CCT_ZOOM_OUT, True)
        else:
            print("❌ Not connected to camera")

    def camera_zoom_stop_command(self):
        """Send zoom stop command to network camera"""
        print("🔥 ZOOM STOP COMMAND EXECUTED!")
        if self.connected:
            # Stop both zoom directions explicitly
            try:
                print("🛑 Stopping zoom IN")
                self.control_camera(CameraType_e.CCT_ZOOM_IN, False)
                print("🛑 Stopping zoom OUT") 
                self.control_camera(CameraType_e.CCT_ZOOM_OUT, False)
                print("✅ Both zoom directions stopped")
            except Exception as e:
                print(f"❌ Error stopping zoom: {e}")
        else:
            print("❌ Not connected to camera")

    def toggle_head_tracking(self):
        self.head_tracking = not self.head_tracking
        if self.head_tracking:
            print("Starting head tracking...")
            if hasattr(self, 'auto_pilot_controller') and self.auto_pilot_controller.isRunning():
                self.auto_pilot_controller.close()  # Close existing instance
                time.sleep(0.5)  # Wait a bit 
            
            # Create fresh instance
            self.auto_pilot_controller = AutoPilotController()
            self.auto_pilot_controller.start()
            print("Head tracking started")
        else:
            print("Stopping head tracking...")
            if hasattr(self, 'auto_pilot_controller'):
                self.auto_pilot_controller.close()
            print("Head tracking stopped")
    
    def auto_update_gun_speed(self):
        if not self.connected or self.stackedWidget.currentIndex() == 0:
            return
        hfov, vfov = self.getFOV()
        if abs(hfov - self.h_fov) < 0.2:
            return
        self.h_fov, self.v_fov = hfov, vfov
        self.velo_speed  =  int(1 + (self.v_fov - 0.51) * (49 / (36.5 - 0.51)))
        self.gunSpeed.setText(str(self.velo_speed))

    def show_ballistics(self):
        d = 0.25
        hfov, vfov = self.getFOV()
        if abs(hfov - self.h_fov) < 0.2:
            return
        self.h_fov, self.v_fov = hfov, vfov
        lrf_distances = range(500, 1900, 50)
        az_list, el_list = [], []
        for lrf in lrf_distances:
            wind_corr = self.set_ballistic(lrf)['AZIMUTH']
            corr_az = round(math.degrees(math.atan(d/lrf)) + wind_corr, 2)
            az_list.append(corr_az)
            el_list.append(self.ballistic_table[lrf])

        if self.stackedWidget.currentIndex() == 0:
            self.bal_overlay_ird.toggle_curve(True, az_list, el_list, self.h_fov, self.v_fov, 1.25*self.bal_overlay_ird.height(), self.overlay_ird.height())
        elif self.stackedWidget.currentIndex() == 1:
            self.bal_overlay_light.toggle_curve(True, az_list, el_list, self.h_fov, self.v_fov, (16/9)*self.bal_overlay_light.height(), self.overlay_light.height())


    
    def update_mapping_indicators(self):
        self.overlay_compass_ird.update_angles(azimuth_deg=self._gun_azimuth, elevation_deg=90 - self._gun_elevation, visible=True)
        self.overlay_compass_light.update_angles(azimuth_deg=self._gun_azimuth, elevation_deg=90 - self._gun_elevation, visible=True)
        
    def zoom_in(self, flag):
        logger.info(f"Zooming in: {flag}")
        self.control_camera(CameraType_e.CCT_ZOOM_IN, flag)
    def zoom_out(self, flag):
        logger.info(f"Zooming out {flag}")
        self.control_camera(CameraType_e.CCT_ZOOM_OUT, flag)
    def cgi_login(self):
        CAMERA_IP = "192.168.1.64"
        USERNAME = "admin"
        PASSWORD = "Abc.12345"  # plain password you use to log in
        URL = f"http://{CAMERA_IP}/cgi-bin/proc.cgi"
        headers = {"Content-Type": "application/json"}
        self.TOKEN = ""

        # Step 1: Get salt
        salt_payload = {
            "cmd": "userSaltGet",
            "param": {
                "username": USERNAME
            }
        }
        r = requests.post(URL, json=salt_payload)
        salt_response = r.json()
        salt = salt_response["param"]["salt"]
        loginEnc = salt_response["param"]["loginEnc"]
        
        # Step 2: Hash password
        if loginEnc == 0:
            hashed_password = hashlib.md5((PASSWORD + salt).encode()).hexdigest()
        else:
            raise NotImplementedError("Only MD5 (loginEnc = 0) supported in this example.")
        
        # Step 3: Login
        login_payload = {
            "cmd": "userLogin",
            "param": {
                "username": USERNAME,
                "password": hashed_password
            }
        }
        r = requests.post(URL, json=login_payload)
        login_response = r.json()
        
        if login_response["param"]["ackvalue"] == 100:
            self.TOKEN = login_response["param"]["token"]
            print(f"✅ Login successful. Token: {self.TOKEN}")
            return True
        else:
            print("❌ Login failed.")
            self.TOKEN = ""
            return False

    # def getFOV(self, width, height, video_type):
    #     # if self.TOKEN == "":
    #     #     logger.warning("Failed to get FOV")
    #     #     self.cgi_login()

    #     # if self.TOKEN != "":
    #     if self.cgi_login():
    #         CAMERA_IP = "192.168.1.64"
    #         URL = f"http://{CAMERA_IP}/cgi-bin/proc.cgi"
    #         headers = {"Content-Type": "application/json"}
    #         payload = {
    #             "cmd": video_type,
    #             "param": {
    #                 "token": self.TOKEN
    #             }
    #         }
    #         response = requests.post(URL, headers=headers, data=json.dumps(payload))
    #         data = response.json()

    #         if data["param"]["ackvalue"] == 100:
    #             fov = data["param"]["fov"] / 100
    #             fov_rad = math.radians(fov)
    #             aspect_ratio = width/height
    #             return fov, math.degrees(2 * math.atan(math.tan(fov_rad / 2) / math.sqrt(1 + aspect_ratio**2))), math.degrees(2 * math.atan(math.tan(fov_rad / 2) / math.sqrt(1 + (1 / aspect_ratio)**2)))
    #         else:
    #             logger.warning("Failed to get FOV")
    #             return None, None, None
    #     else:
    #         logger.warning("Failed to CGI login")
    #         return None, None, None
    
    def setFOV(self, fov, video_type):
        if self.cgi_login():
            CAMERA_IP = "192.168.1.64"
            URL = f"http://{CAMERA_IP}/cgi-bin/proc.cgi"
            headers = {"Content-Type": "application/json"}
            payload = {
                "cmd": video_type,
                "param": {
                    "token": self.TOKEN,
                    "fov": fov
                }
            }
            response = requests.post(URL, headers=headers, data=json.dumps(payload))
            data = response.json()

            if data["param"]["ackvalue"] == 100:
                return True
            else:
                return False


    def reload_config(self):
        logger.info("Reloading configuration...")
        self.load_config()
        self.update_application_state()
        
        # Send taboo values to motors
        self.send_taboo_values_to_motors()
        
        logger.info("Configuration reloaded, application state updated, and taboo values sent to motors.")

    def set_inclinometer_data(self, x, y, z):
        """
        Process inclinometer data for programmatic use
        
        Args:
            x: X-axis value
            y: Y-axis value
            z: Z-axis value
        """
        # Store the raw values
        self._inclinometer_x = x
        self._inclinometer_y = y
        self._inclinometer_z = z
        
        # Calculate pitch and roll angles
        # Pitch = rotation around X-axis, Roll = rotation around Y-axis
        pitch = math.degrees(math.atan2(y, math.sqrt(x*x + z*z)))
        roll = math.degrees(math.atan2(x, math.sqrt(y*y + z*z)))
        
        self._inclinometer_pitch = pitch
        self._inclinometer_roll = roll
        
        logger.debug(f"Inclinometer data updated - X: {x:.2f}, Y: {y:.2f}, Z: {z:.2f}, Pitch: {pitch:.2f}°, Roll: {roll:.2f}°")
        self.received_inclinometer_data = True


    def send_taboo_values_to_motors(self):
        """Send the taboo values (pan/tilt limits) to the motors accounting for multi-turn encoders"""
        if not hasattr(self, 'gun_controller') or not self.gun_controller.connected:
            logger.warning("Cannot send taboo values: Gun controller not connected")
            return False
        
        try:
            # Check if taboo zone is enabled in config
            taboo_enabled = self.config['DEFAULT'].get('Taboo Zone', 'Off') == 'On'

            # If taboo zone is disabled, send extreme values for pan and system-specific limits for tilt
            if not taboo_enabled:
                logger.info("Taboo zone is disabled, setting system-specific limits for tilt and extreme limits for pan")
                
                # For pan motor, still use extreme values to allow full rotation
                pan_params = {
                    'maxPositionLimit': 2147483647,  # Max positive 32-bit integer
                    'minPositionLimit': -2147483648,  # Min negative 32-bit integer
                    'arc': False
                }
                
                # For tilt motor, use system-specific limits
                COUNTS_PER_DEGREE = (2**19) / 360  # Base conversion factor
                
                # Get current tilt encoder position and angle
                current_tilt_encoder = self.gun_controller.read_tilt_encoder()
                current_tilt_angle = self._gun_elevation
                
                if current_tilt_encoder is None:
                    logger.error("Failed to read current tilt encoder position")
                    return False
                
                # Calculate the "zeroth" tilt encoder position (where angle would be 0)
                zeroth_tilt = current_tilt_encoder - (current_tilt_angle * COUNTS_PER_DEGREE)
                
                # Get system-specific tilt limits from our centralized system_limits module
                limits = get_system_limits(self.system_type)
                system_tilt_top = limits['TILT_TOP_LIMIT']
                system_tilt_bottom = limits['TILT_BOTTOM_LIMIT']
                
                # Calculate encoder counts for system-specific limits
                # Different calculation based on system type due to inverted tilt orientation
                if self.system_type in ['BMG', 'NSVT']:
                    # For NSVT/BMG systems, where as tilt angle increases, encoder count decreases
                    # We need to invert the angle difference direction
                    angle_diff_top = system_tilt_top - current_tilt_angle
                    angle_diff_bottom = system_tilt_bottom - current_tilt_angle
                    
                    # Calculate encoder values based on current position and angle differences
                    # The sign is flipped from the angle difference because of the inverse relationship
                    system_tilt_top_counts = int(current_tilt_encoder - (angle_diff_top * COUNTS_PER_DEGREE))
                    system_tilt_bottom_counts = int(current_tilt_encoder - (angle_diff_bottom * COUNTS_PER_DEGREE))
                    
                    logger.info(f"Using inverse relationship calculation for {self.system_type} system")
                    logger.info(f"System limits angle diffs: bottom={angle_diff_bottom}°, top={angle_diff_top}°")
                else:
                    # For RCWS, normal orientation
                    system_tilt_top_counts = int(zeroth_tilt + (system_tilt_top * COUNTS_PER_DEGREE))
                    system_tilt_bottom_counts = int(zeroth_tilt + (system_tilt_bottom * COUNTS_PER_DEGREE))
                
                # Ensure min is always less than max for the controller
                tilt_min_limit = min(system_tilt_top_counts, system_tilt_bottom_counts)
                tilt_max_limit = max(system_tilt_top_counts, system_tilt_bottom_counts)
                
                tilt_params = {
                    'maxPositionLimit': tilt_max_limit,
                    'minPositionLimit': tilt_min_limit,
                    'arc': 0  # Using 0 for tilt arc (default)
                }
                
                logger.info(f"Setting tilt limits to system defaults: [{system_tilt_bottom}°, {system_tilt_top}°] " +
                        f"(encoder counts: [{tilt_min_limit}, {tilt_max_limit}])")
                
                # Send the values to motors
                pan_result = self.gun_controller.write_pan_limit_params(pan_params)
                tilt_result = self.gun_controller.write_tilt_limit_params(tilt_params)
                
                if pan_result and tilt_result:
                    logger.info("Successfully set limits with taboo zone disabled")
                    return True
                else:
                    logger.warning("Failed to set limits with taboo zone disabled")
                    return False
            
            # If taboo zone is enabled, proceed with normal limit setting
            COUNTS_PER_DEGREE = (2**19) / 360  # Base conversion factor
            
            # Get taboo values from config
            pan_left = float(self.config['DEFAULT'].get('PAN Left taboo', self.pan_left_limit))
            pan_right = float(self.config['DEFAULT'].get('PAN Right taboo', self.pan_right_limit))
            tilt_bottom = float(self.config['DEFAULT'].get('TILT Bottom taboo', self.tilt_bottom_limit))
            tilt_top = float(self.config['DEFAULT'].get('TILT Top taboo', self.tilt_top_limit))
            
            logger.info(f"Target taboo values - Pan: [{pan_left}, {pan_right}], Tilt: [{tilt_bottom},{tilt_top}]")
            
            # For multi-turn motors, we need to get the current encoder positions first
            current_pan_encoder = self.gun_controller.read_pan_encoder()
            current_tilt_encoder = self.gun_controller.read_tilt_encoder()

            # Get current angles from the gun controller
            current_pan_angle = self._gun_azimuth
            current_tilt_angle = self._gun_elevation
            
            if is_between_cw(pan_left, pan_right, self._gun_azimuth):
                diff1 = clockwise_angle(pan_left, self._gun_azimuth)
                diff2 = clockwise_angle(self._gun_azimuth, pan_right)

                diff1 = diff1 * COUNTS_PER_DEGREE
                diff2 = diff2 * COUNTS_PER_DEGREE

                pan_left_counts = int(current_pan_encoder + diff1)
                pan_right_counts = int(current_pan_encoder - diff2)

                if current_pan_encoder is None or current_tilt_encoder is None:
                    logger.error("Failed to read current encoder positions")
                    return False

                logger.info(f"Current position - Pan: {current_pan_angle}° ({current_pan_encoder} counts), "
                        f"Tilt: {current_tilt_angle}° ({current_tilt_encoder} counts)")
                
                # Calculate zeroth tilt only if needed (for RCWS system)
                zeroth_tilt = None
                if self.system_type not in ['BMG', 'NSVT']:
                    zeroth_tilt = current_tilt_encoder - (self._gun_elevation*COUNTS_PER_DEGREE)
                    logger.info(f"Calculated zeroth tilt position: {zeroth_tilt}")

                # Calculate absolute encoder positions for limits with system type consideration
                if self.system_type in ['BMG', 'NSVT']:
                    # For NSVT/BMG, where as tilt angle increases, encoder count decreases
                    # We need to invert the angle difference direction
                    angle_diff_bottom = tilt_bottom - current_tilt_angle
                    angle_diff_top = tilt_top - current_tilt_angle
                    
                    # Calculate encoder values based on current position and angle differences
                    # The sign is flipped from the angle difference because of the inverse relationship
                    tilt_bottom_counts = int(current_tilt_encoder - (angle_diff_bottom * COUNTS_PER_DEGREE))
                    tilt_top_counts = int(current_tilt_encoder - (angle_diff_top * COUNTS_PER_DEGREE))
                    
                    logger.info(f"Using inverse relationship calculation for {self.system_type} system")
                    logger.info(f"Angle diffs: bottom={angle_diff_bottom}° ({tilt_bottom}°-{current_tilt_angle}°), " +
                            f"top={angle_diff_top}° ({tilt_top}°-{current_tilt_angle}°)")
                else:
                    # For RCWS, normal orientation
                    tilt_bottom_counts = int(zeroth_tilt + (tilt_bottom*COUNTS_PER_DEGREE))
                    tilt_top_counts = int(zeroth_tilt + (tilt_top*COUNTS_PER_DEGREE))
                    logger.info(f"Using standard tilt calculation for {self.system_type} system")
                
                # Since we're sending to a motor controller, ensure min is always less than max
                # regardless of which is physically "top" or "bottom"
                tilt_min_pos = min(tilt_bottom_counts, tilt_top_counts)
                tilt_max_pos = max(tilt_bottom_counts, tilt_top_counts)

                logger.info(f"Calculated absolute encoder positions for limits - "
                        f"Pan: [{pan_left_counts}, {pan_right_counts}], Tilt: [{tilt_min_pos}, {tilt_max_pos}]")
            else:
                logger.warning(f"Current position (Pan: {current_pan_angle}, Tilt: {current_tilt_angle}) is outside new taboo range!")
                
                self.pan_left_limit = self.prev_pan_left_limit
                self.pan_right_limit = self.prev_pan_right_limit
                self.tilt_bottom_limit = self.prev_tilt_bottom_limit
                self.tilt_top_limit = self.prev_tilt_top_limit

                if clockwise_angle(pan_left, pan_right) <= 180:
                    pan_range_desc = f"[{min(pan_left, pan_right):.2f}°, {max(pan_left, pan_right):.2f}°]"
                else:
                    # For Bigger arc, describe the two valid ranges
                    pan_range_desc = f"[-180.00° to {min(pan_left, pan_right):.2f}°] or [{max(pan_left, pan_right):.2f}° to 180.00°]"
                                
                QMessageBox.information(
                    self, 
                    "Operation Canceled: Position Outside Taboo Range",
                    f"Current gun position (Pan: {current_pan_angle:.2f}°, Tilt: {current_tilt_angle:.2f}°) is outside "
                    f"the taboo range (Pan: {pan_range_desc}, Tilt: [{tilt_bottom:.2f}°, {tilt_top:.2f}°]).\n\n"
                    "Cannot set these limits. Please move the gun to a valid position first."
                )
                logger.info("Position outside taboo range - operation canceled")
                return False
                
            # Prepare parameters for the controller
            pan_params = {
                'maxPositionLimit': pan_left_counts,
                'minPositionLimit': pan_right_counts,
                'arc': 1
            }
            
            tilt_params = {
                'maxPositionLimit': tilt_max_pos,
                'minPositionLimit': tilt_min_pos,
                'arc': 0  # Using 0 for tilt arc (default)
            }
            self.prev_pan_left_limit = self.pan_left_limit
            self.prev_pan_right_limit = self.pan_right_limit
            self.prev_tilt_bottom_limit = self.tilt_bottom_limit
            self.prev_tilt_top_limit = self.tilt_top_limit
            
            # Send to motors
            logger.info(f"Sending taboo values to motors - "
                    f"Pan: [{pan_left_counts}, {pan_right_counts}], Tilt: [{tilt_min_pos}, {tilt_max_pos}]")
        
            pan_result = self.gun_controller.write_pan_limit_params(pan_params)
            tilt_result = self.gun_controller.write_tilt_limit_params(tilt_params)
            
            if pan_result and tilt_result:
                logger.info("Successfully sent taboo values to motors")
                return True
            else:
                logger.warning("Failed to send taboo values to motors")
                return False
        except Exception as e:
            logger.error(f"Error sending taboo values to motors: {str(e)}", exc_info=True)
            return False
        
    def default_load_config(self):
        try:
            self.config.read_encrypted('default.ini')
            self.update_config_variables()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Load default values if config file doesn't exist or is corrupted
            self.set_default_config()
        # self.set_config_variables()

    def load_config(self):
        try:
            self.config.read_encrypted('config.ini')
            self.update_config_variables()
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Load default values if config file doesn't exist or is corrupted
            self.set_default_config()
        # self.set_config_variables()

    def update_application_state(self):
        # Update all relevant parts of the application
        self.update_ui_elements()
        self.update_wind_data()  # Force an immediate update of wind data
        # Update any other parts of the application that depend on configuration
        logger.info(f"Application state updated. Wind speed mode: {self.wind_speed_mode}, Manual wind speed: {self.manual_wind_speed}")

    def update_ui_elements(self):
        if hasattr(self, 'wind_speed_value') and hasattr(self, 'wind_direction_value'):
            self.wind_speed_value.setText(f"{self.manual_wind_speed:.1f}")
            self.wind_direction_value.setText(self.wind_direction)
            logger.info(f"UI updated - Wind speed: {self.wind_speed_value.text()}, Direction: {self.wind_direction_value.text()}")
        else:
            logger.warning("UI elements for wind data not yet initialized")

    def set_default_config(self):
        self.wind_speed_mode = 'Manual'
        self.manual_wind_speed = 0
        self.wind_direction = '0'
        self.lrf_firing_enabled = False
        self.default_distance = 1000
        self.track_mode = 'Manual ground tracking'
        self.velo_speed = 50
        self.thermal_camera_power = 'Off'
        self.firing_rate = 700
        self.num_rounds = 0
        self.mils_value = 1.0
        self.Kp = 4.2
        self.Ki = 1.9
        self.Kd = 0
        self.longitude = 77.577000
        self.latitude = 34.152300
        self.altitude = 0

    def toggle_thermal_camera(self):
        """Toggle the thermal camera power state"""
        current_power = self.thermal_camera_power == 'On'
        new_power = not current_power
        
        logger.info(f"Toggling thermal camera power from {self.thermal_camera_power} to {'On' if new_power else 'Off'}")
        
        success = self.set_thermal_camera_power(new_power)
        
        if success:
            # Update button appearance if there's a dedicated button
            for button in self.findChildren(QPushButton):
                if button.text() == "Thermal ON/OFF":
                    button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;" if new_power else "")
        
        return success

    def create_pre_registration_indicator(self):
        self.pre_registration_indicator = QLabel("PRE")
        self.pre_registration_indicator.setFixedSize(40, 20)
        self.pre_registration_indicator.setAlignment(Qt.AlignCenter)
        self.pre_registration_indicator.setStyleSheet("""
            background-color: #808080;
            color: white;
            border-radius: 10px;
            font-weight: bold;
        """)
        self.reportLayoutMain.addWidget(self.pre_registration_indicator)

    def update_pre_registration_indicator(self):
        if self.target_registration.is_active():
            self.pre_registration_indicator.setStyleSheet("""
                background-color: #00FF00;
                color: black;
                border-radius: 10px;
                font-weight: bold;
            """)
        else:
            self.pre_registration_indicator.setStyleSheet("""
                background-color: #808080;
                color: white;
                border-radius: 10px;
                font-weight: bold;
            """)
    

    def create_ballistics_indicator(self):
        self.ballistics_indicator = QLabel("BAL")
        self.ballistics_indicator.setFixedSize(40, 20)
        self.ballistics_indicator.setAlignment(Qt.AlignCenter)
        self.ballistics_indicator.setStyleSheet("""
            background-color: #808080;
            color: white;
            border-radius: 10px;
            font-weight: bold;
        """)
        self.reportLayoutMain.addWidget(self.ballistics_indicator)

    def update_ballistics_indicator(self):
        if self.ballistics_active:
            self.ballistics_indicator.setStyleSheet("""
                background-color: #00FF00;
                color: black;
                border-radius: 10px;
                font-weight: bold;
            """)
        else:
            self.ballistics_indicator.setStyleSheet("""
                background-color: #808080;
                color: white;
                border-radius: 10px;
                font-weight: bold;
            """)

    def toggle_ballistics(self):
        if self.target_registration.is_active():
            logger.warning("Cannot enable ballistics while pre-registered targets mode is active.")
            # QMessageBox.information(self, "Information", "Cannot enable ballistics while pre-registered targets mode is active.")
            return

        self.ballistics_active = not self.ballistics_active
        logger.critical(f"Ballistics toggled: {'active' if self.ballistics_active else 'inactive'}")
        self.update_ballistics_indicator()
        if self.ballistics_active:
            self.bal()
        else:
            self.clear_ballistics()

    def trigger_inclinometer_request(self):
        """
        Request inclinometer data from the ESP32 - sends request every time it's called
        """
        logger.info("Requesting inclinometer data from ESP32")
        if hasattr(self, 'gun_controller') and self.gun_controller.connected:
            result = self.gun_controller.request_inclinometer_data()
            if result:
                logger.critical("Inclinometer data request sent successfully")
            else:
                logger.error("Failed to send inclinometer data request")
        else:
            logger.warning("Cannot request inclinometer data: Gun controller not connected")


    def toggle_bal_line(self):
        pass
        # if self.bal_indicator_running:
        #     self.bal_indicator.stop()
        #     self.bal_indicator_running = False
        #     self.bal_overlay_ird.toggle_curve(False, [], [], None, None, None, None)
        #     self.bal_overlay_light.toggle_curve(False, [], [], None, None, None, None)
        # else:
        #     self.bal_indicator.start(1000)
        #     self.bal_indicator_running = True

    def nsvt_ballistics(self):
        self.ballistics_active = not self.ballistics_active
        logger.critical(f"Ballistics toggled: {'active' if self.ballistics_active else 'inactive'}")
        self.update_ballistics_indicator()
        if self.ballistics_active:
            self.fire_lrf()
            time.sleep(0.5)
            predictions = self.set_ballistic(distance=self._lrf_dist_1)
            corr_az = predictions['AZIMUTH']
            corr_el = predictions['ELEVATION']
            # corr_az = 0.1
            # corr_el = 0.2
            self.position_gun(self._gun_azimuth+corr_az, self._gun_elevation+corr_el)
            self.draw_virtual_crosshair(corr_az, corr_el)
        else:
            self.clear_ballistics()
            self.overlay_light.toggle_rectangle(False, None, None, None, None, 1392, 1080)
            self.overlay_ird.toggle_rectangle(False, None, None, None, None, 1.25*783, 512)

    def toggleBal(self):
        self.ballistics_active = not self.ballistics_active
        logger.critical(f"Ballistics toggled: {'active' if self.ballistics_active else 'inactive'}")
        self.update_ballistics_indicator()
        if self.ballistics_active:
            self.trigger_inclinometer_request()
            while not self.received_inclinometer_data:
                continue
            self.received_inclinometer_data = False
            plane_normal = get_plane_normal(roll_deg=self._inclinometer_x, pitch_deg=self._inclinometer_y, yaw_deg=self._inclinometer_z)
            vec_on_plane = vector_on_plane(self._gun_elevation, plane_normal)
            self.plane_elevation = elevation_angle(vec_on_plane)
            print("pLANE ELEVATION is: ", self.plane_elevation)
            # self.plane_elevation = 0
            global_gun_elevation = self.plane_elevation + self._gun_elevation

            # h_dist = 25
            # height = 1.5
            # lrf_dist = 1000
            # ele = 10  
            # x, y = lrf_dist * math.cos(ele), lrf_dist * math.sin(ele)
            self.fire_lrf()
            time.sleep(0.5)
            # self._lrf_dist_1 = 800
            if self._lrf_dist_1 < 100:
                self.plane_elevation = 0
                self.perform_ballistics(self._lrf_dist_1, self._gun_elevation)
                return
            if global_gun_elevation < 0:
                closest_key = min(self.range_table.keys(), key=lambda k: abs(k - self._lrf_dist_1))
                corr_el = self.range_table[closest_key]
                self.plane_elevation = 0
                self.perform_ballistics(self._lrf_dist_1, self._gun_elevation + corr_el)
                return 
            x, y, height0, h_dist = self._lrf_dist_1 * math.cos(math.radians(global_gun_elevation)), self._lrf_dist_1 * math.sin(math.radians(global_gun_elevation)), 2, 0.25
            
            self.ballistics_solver_thread = QThread()
            self.ballistics_solver = ProjectileSolver(target_x=x, target_y=y, height=0)
            self.ballistics_solver.moveToThread(self.ballistics_solver_thread)
            self.ballistics_solver_thread.started.connect(self.ballistics_solver.find_launch_angle)
            
            self.ballistics_solver.finished.connect(self.ballistics_solver_thread.quit)
            self.ballistics_solver.finished.connect(self.ballistics_solver.deleteLater)
            self.ballistics_solver_thread.finished.connect(self.ballistics_solver_thread.deleteLater)

            self.ballistics_solver.corr_el.connect(self.perform_ballistics)
            self.ballistics_solver_thread.start()
        else:
            self.corr_az = None
            self.corr_el = None
            self.double_ring_crosshair_timer.stop()
            self.clear_ballistics()
            self.overlay_ird.toggle_rectangle(False, None, None, None, None, 640, 512)
            self.overlay_light.toggle_rectangle(False, None, None, None, None, 1920, 1080)
        
        return True
    def perform_ballistics(self, x, global_req_angle):
        h_dist = 0.25
        logger.info(f"X value is {x}")

        wind_corr = self.set_ballistic(distance=x)['AZIMUTH']
        # self.corr_az = round(math.degrees(math.atan(h_dist/x)), 2) + wind_corr # + 0.06
        self.corr_az = wind_corr + math.degrees(1 * 0.001)
        self.corr_el = global_req_angle - self._gun_elevation - self.plane_elevation  + math.degrees(3 * 0.001) # the correction is based on the offset
        logger.warning(f"Corrected Azimuth: {self.corr_az}, Corrected Elevation: {self.corr_el}")
        # self.corr_az=0.2
        # self.corr_el = 0.3

        # The following correction based on error correction of ballistics
        if self._lrf_dist_1 > 850 and self._lrf_dist_1 <=1000:
            self.corr_el += 0.08
        if self._lrf_dist_1 > 1000 and self._lrf_dist_1 < 2000:
            self.corr_el += 0.15

        logger.warning(f"Corr Elevation: {self.corr_el}, Corr Azimuth: {self.corr_az}")
        final_gun_position = (round(self._gun_azimuth + self.corr_az, 2), round(self._gun_elevation + self.corr_el, 2))
        self.position_gun(final_gun_position[0], final_gun_position[1])
        # self.draw_virtual_crosshair(self.corr_az, self.corr_el)
        self.double_ring_crosshair_timer.start(1000)

    def draw_virtual_crosshair(self, corr_az, corr_el):
        self.corr_az, self.corr_el = corr_az, corr_el
        if self.stackedWidget.currentIndex() == 0:
            v_fov = json.loads(self.ipc_object.get_thermal_fov().decode('utf-8'))['fov'] / 100
            h_fov, v_fov = self.correct_fov(v_fov, 640/512)
            logger.info(f"HFOV: {h_fov}, VFOV: {v_fov}")
            if h_fov is not None and v_fov is not None:
                if self.corr_az > h_fov/2 or self.corr_el > v_fov/2:
                    self.ipc_object.set_thermal_fov(corr_el*3)
                    # h_fov, v_fov = h_fov*2, v_fov*2
                    h_fov, v_fov = self.correct_fov(corr_el*3, 1.25)
                # self.overlay_ird.toggle_rectangle(True, self.corr_az, self.corr_el, h_fov, v_fov, 1.25*783, 512)
                self.double_ring_crosshair_timer.start(1000)
            else:
                QMessageBox.critical(self, 'Error', "Could not get FOV")
        else:
            h_fov, v_fov = self.getFOV()
            logger.info(f"HFOV: {h_fov}, VFOV: {v_fov}")
            if h_fov is not None and v_fov is not None:
                if self.corr_az > h_fov/2 or self.corr_el > v_fov/2:
                    self.ipc_object.set_visible_fov(corr_el*3)
                    # h_fov, v_fov = h_fov*2, v_fov*2
                    h_fov, v_fov = self.correct_fov(corr_el*3, 16/9)
                # self.overlay_light.toggle_rectangle(True, self.corr_az, self.corr_el, h_fov, v_fov, 1392, 614)
                self.double_ring_crosshair_timer.start(1000)
            else:
                QMessageBox.critical(self, 'Error', "Could not get FOV")


    def update_wind_data(self):
        # logger.info(f"Current wind speed mode: {self.wind_speed_mode}")
        # logger.info(f"Current manual wind speed setting: {self.manual_wind_speed}")
        
        if self.wind_speed_mode == 'Automatic':
            wind_speed = self.anemometer.read_wind_speed(2)
            if wind_speed is None:
                logger.warning("Failed to read wind speed from anemometer. Falling back to manual value.")
                wind_speed = self.manual_wind_speed
            # logger.info(f"Anemometer reading: {wind_speed}")
        else:
            wind_speed = self.manual_wind_speed
            # logger.info(f"Using manual wind speed: {wind_speed}")

        # logger.info(f"Updated wind data - Speed: {wind_speed}, Direction: {self.wind_direction}")
        
        if hasattr(self, 'wind_speed_value') and hasattr(self, 'wind_direction_value'):
            self.wind_speed_value.setText(f"{wind_speed:.1f}")
            self.wind_direction_value.setText(self.wind_direction)
            # logger.info(f"UI updated - Wind speed: {self.wind_speed_value.text()}, Direction: {self.wind_direction_value.text()}")
        else:
            logger.warning("UI elements for wind data not yet initialized")

        # # Add this line to check the actual values of the UI elements after update
        # if hasattr(self, 'wind_speed_value'):
        #     logger.info(f"Wind speed UI value after update: {self.wind_speed_value.text()}")
        # if hasattr(self, 'wind_direction_value'):
        #     logger.info(f"Wind direction UI value after update: {self.wind_direction_value.text()}")

    def bal(self):
        #self.fire_lrf()
        t = self._lrf_dist_1
        if t > 2000:
            t = 2000
        logger.critical(f"Ballistic calculation triggered with distance: {t}")
        self.set_ballistic(t)

    def clear_ballistics(self):
        logger.critical("Clearing ballistics")
        self.video_light.overlay_widget.clear_ballistic()
        self.video_light.overlay_widget.update()
    
    def increase_bal(self):
        self.ball_value = self._lrf_dist_1
        self.ball_value += 50
        t = self.ball_value
        if t > 2000:
            t = 2000
        logger.log("Increased Ballsitic to "+str(t))
        self.set_ballistic(t)

    def decrease_bal(self):
        self.ball_value = self._lrf_dist_1
        self.ball_value -= 50
        t = self.ball_value
        if t < 50:
            t = 50
        logger.log("Increased Ballsitic to "+str(t))
        self.set_ballistic(t)

    def toggle_armed_state(self):
        if self.get_user_role() not in [ROLES.ADMIN, ROLES.PROGRAMMER]:
            return
        self.armed = not self.armed
        if self.armed:
            logger.critical("Status ARMED")
            self.armed_status.setText("Armed")
            
            # Only apply brakes if Fire on Move is Off
            fire_on_move = 'Off'  # Default value
            if hasattr(self, 'config') and 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
                fire_on_move = self.config['DEFAULT']['Fire on Move']
                
            if fire_on_move == 'Off':
                logger.info("Applying brake because Fire on Move is Off")
                self.gun_controller.brake()
            else:
                logger.info("Not applying brake because Fire on Move is On")
                # Ensure brake is released when Fire on Move is On
                self.gun_controller.unbrake()
                
            self.armed_status_widget.setStyleSheet(self.get_stylesheet_armed(True))
        else:
            logger.critical("Status UNARMED")
            self.armed_status.setText("Unarmed")
            logger.critical(f"Unarmed at Azimuth {self._gun_azimuth}, Elevation {self._gun_elevation}")
            self.gun_controller.unbrake()
            self.armed_status_widget.setStyleSheet(self.get_stylesheet_armed(False))

    def handle_error(self, error_msg):
        logger.error("[ ERROR ] " + error_msg)
        QMessageBox.critical(self, 'Error', error_msg)
        # self.close()

    def position_gun_head_tracking(self, x, y):
        """Position gun with fixed speeds for head tracking"""
        fire_on_move = 'Off'  # Default value
        if hasattr(self, 'config') and 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
            fire_on_move = self.config['DEFAULT']['Fire on Move']
            
        if hasattr(self, 'armed') and self.armed and fire_on_move == 'Off':
            logger.info(f"Gun movement command to ({x}, {y}) ignored: System is ARMED and Fire on Move is Off")
            return False
        
        # Same taboo zone checks as original position_gun method
        if not (self.config['DEFAULT'].get('Taboo Zone', 'Off') == 'On'):
            limits = get_system_limits(self.system_type)
            self.pan_left_limit = limits['PAN_LEFT_LIMIT']
            self.pan_right_limit = limits['PAN_RIGHT_LIMIT']
            self.tilt_bottom_limit = limits['TILT_BOTTOM_LIMIT']
            self.tilt_top_limit = limits['TILT_TOP_LIMIT']

        if not (self.pan_left_limit <= x <= self.pan_right_limit and self.tilt_bottom_limit <= y <= self.tilt_top_limit):
            logger.warning(f"Head tracking position command rejected: Az: {x}, El: {y} is outside limits")
            return False

        target_x = x
        
        # For NSVT/BMG systems, invert the tilt value before sending to the controller
        if self.system_type in ['BMG', 'NSVT']: 
            target_y = -y
        else:
            target_y = y
        
        # Fixed speeds for head tracking: Pan=100, Tilt=60
        pan_speed = 100
        tilt_speed = 60
        
        logger.info(f"Head tracking: Moving Gun to ({x}, {y}) with speeds (Pan: {pan_speed}, Tilt: {tilt_speed})")
        self.gun_controller.move(target_x, target_y, pan_speed, tilt_speed)
        return True

    def check_stab_data(self):
        if hasattr(self.auto_pilot_controller, 'latest_data'):
            data = None
            with self.auto_pilot_controller.data_lock:
                if self.auto_pilot_controller.latest_data['new_data']:
                    data = self.auto_pilot_controller.latest_data.copy()
                    self.auto_pilot_controller.latest_data['new_data'] = False
            
            if data is not None:
                self.handle_stab_change(
                    data['rollspeed'], data['pitchspeed'], data['yawspeed'],
                    data['roll'], data['pitch'], data['yaw']
                )

    def handle_stab_change(self, rs, ps, ys, r, p ,y):
        if p > self.tilt_top_limit-1:
            p = self.tilt_top_limit
        if p < self.tilt_bottom_limit+1:
            p = self.tilt_bottom_limit

        # rs = min(rs, 50)
        # ps = min(ps, 50)
        # ys = min(ys, 50)
        logger.critical(f"Pitch: {p}, Yaw: {y}")
        # self.gun_controller.vmove(ys, ps)
        # self.position_gun(y +90+90+150, -p)
        # self.position_gun(-y, p)
        self.position_gun_head_tracking(-y, p)
        # self.gun_controller.vmove(ys,ps)

    def toggle_fire_detection(self):
        """Toggle fire detection mode on/off with button-controlled logging"""
        self.fire_detection_active = not self.fire_detection_active
        
        # Enable/disable auto-targeting in CASTLE listener
        if self.fire_detection_active:
            # 🎯 NEW: START LOGGING AND LISTENING WHEN BUTTON IS PRESSED
            if not self.castle_listener.running:
                self.castle_listener.start_listening()
                print(f"🔥 Fire Detection ACTIVATED - Logging started")
                print(f"📄 Log file: {self.castle_listener.get_log_file_path()}")
            
            self.castle_listener.enable_auto_targeting()
            logger.critical("Fire Detection ACTIVATED - Auto-targeting ENABLED")
            
            # Log to fire detection system
            if hasattr(self.castle_listener, 'log_message'):
                self.castle_listener.log_message('critical', 
                    "FIRE DETECTION SYSTEM ACTIVATED FROM MAIN INTERFACE", {
                        'activated_by': 'user_interface_button',
                        'auto_targeting': True,
                        'system_armed': getattr(self, 'armed', False),
                        'fire_on_move': self.config['DEFAULT'].get('Fire on Move', 'Off') if hasattr(self, 'config') else 'Unknown',
                        'log_session_started': True
                    })
        else:
            # 🎯 NEW: STOP LOGGING AND LISTENING WHEN BUTTON IS PRESSED AGAIN
            self.castle_listener.disable_auto_targeting()
            
            # Log the deactivation before stopping
            if hasattr(self.castle_listener, 'log_message'):
                self.castle_listener.log_message('critical', 
                    "FIRE DETECTION SYSTEM DEACTIVATED FROM MAIN INTERFACE", {
                        'deactivated_by': 'user_interface_button',
                        'auto_targeting': False,
                        'log_session_ended': True
                    })
            
            # Stop the listener and logging
            if self.castle_listener.running:
                print(f"🔥 Fire Detection DEACTIVATED - Logging stopped")
                print(f"📄 Final log saved to: {self.castle_listener.get_log_file_path()}")
                self.castle_listener.stop()
            
            logger.critical("Fire Detection DEACTIVATED - Auto-targeting DISABLED")
        
        # Update button color
        for button in self.findChildren(QPushButton):
            if button.text() == "Fire Detection":
                if self.fire_detection_active:
                    button.setStyleSheet("background-color: rgb(0, 255, 0); color: black;")
                else:
                    button.setStyleSheet("")

    def handle_change_axis_signal(self, xx, yy, x, y, z=0):

        if not hasattr(self, 'gun_controller') or not self.gun_controller.connected:
            return
        
        fire_on_move = 'Off'  # Default value
        if hasattr(self, 'config') and 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
            fire_on_move = self.config['DEFAULT']['Fire on Move']
            
        if hasattr(self, 'armed') and self.armed and fire_on_move == 'Off':
            # logger.debug("Movement command ignored: System is ARMED and Fire on Move is Off")
            return
        yy, y = -yy, -y
        xx = -xx
        d_zone = 0.1
        if abs(x) <= d_zone and y > d_zone:
            to_on = PtzControlType_e.PCT_UP
        elif x > d_zone and abs(y) <= d_zone:
            to_on = PtzControlType_e.PCT_RIGHT
        elif x < -d_zone and abs(y) <= d_zone:
            to_on = PtzControlType_e.PCT_LEFT
        elif abs(x) <= d_zone and y < -d_zone:
            to_on = PtzControlType_e.PCT_DOWN
        elif x > d_zone and y > d_zone:
            to_on = PtzControlType_e.PCT_RIGHT_UP
        elif x < -d_zone and y > d_zone:
            to_on = PtzControlType_e.PCT_LEFT_UP
        elif x < -d_zone and y < -d_zone:
            to_on = PtzControlType_e.PCT_LEFT_DOWN
        elif x > d_zone and y < -d_zone:
            to_on = PtzControlType_e.PCT_RIGHT_DOWN
        else:
            to_on = None
        
        # Calculate pan speed with the algorithm
        if self.velo_speed == 0:
            pan_speed = 0
        elif self.velo_speed == 1:
            pan_speed = 0.03
        else:
            pan_speed = min(self.velo_speed, 80)
        
        # Calculate tilt speed with the algorithm
        if self.velo_speed == 0:
            tilt_speed = 0
        elif self.velo_speed == 1:
            tilt_speed = 0.03
        else:
            tilt_speed = min(self.velo_speed, 60)
        
        # Apply fine_speed if needed
        pan_speed = pan_speed * 0.1 if self.fine_speed else pan_speed
        tilt_speed = tilt_speed * 0.1 if self.fine_speed else tilt_speed
        
        # Use the updated get method with separate pan and tilt speeds
        xx, yy = self.smoother.get(xx, yy, pan_speed, tilt_speed)

        if not self.targeted:
            self.gun_controller.vmove(xx, yy * self.tilt_direction)

        if self.last_axis_sent == to_on:
            return
        self.last_axis_sent = to_on

        if to_on:
            self.control_ptz(to_on, True, abs(x), abs(y))
        else:
            self.control_ptz(PtzControlType_e.PCT_STATIC, False)

    def set_ballistic(self, distance):
        if self.wind_speed_mode == 'Automatic':
            wind_speed = self.anemometer.read_wind_speed(2)
            if wind_speed is None:
                logger.warning("Failed to read wind speed from anemometer. Falling back to manual value.")
                wind_speed = self.manual_wind_speed
        else:
            wind_speed = self.manual_wind_speed
        
        if self.wind_speed_value and self.wind_direction_value:
            self.wind_speed_value.setText(f"{wind_speed:.1f}")
            self.wind_direction_value.setText(self.wind_direction)
        
        logger.critical(f"Wind Speed Mode: {self.wind_speed_mode}")
        logger.critical(f"Wind Speed: {wind_speed}")
        logger.critical(f"Wind Direction: {self.wind_direction}")
        
        if self.system_type == 'RCWS':
            predictions = self.ballistics.predict(distance, wind_speed, self.wind_direction)
        elif self.system_type == 'NSVT':
            predictions = self.ballistics_nsvt.predict(distance, wind_speed, self.wind_direction)
        return predictions
        # self.update_predictions(predictions, distance)


    def update_predictions(self, predictions, distance):
        el, az = predictions['ELEVATION'], predictions['AZIMUTH']
        self.ballistics_v_diff = abs(el)
        self.ballistics_h_diff = abs(az)
        logger.critical(f"Ballistics calculations: Elevation {el}, Azimuth {az}")
        
        # Update wind correction values
        self.wind_correction_azimuth = az
        self.wind_correction_elevation = el
        self.update_wind_correction_display()
        
        if self.ballistics_active:
            logger.critical("Updating ballistics display")
            self.video_light.overlay_widget.set_ballistic(abs(el), abs(az), distance, predictions)
            self.video_light.overlay_widget.update()  # Force update of the overlay
        else:
            logger.critical("Ballistics inactive, not updating display")
        
        self.ball_value = distance

    def handle_button_signal(self, joy_name, btn_id, status):
        # if joy_name not in self.joystick_mappings:
        #     logger.warning(f"Unknown joystick: {joy_name}")
        #     return

        mapping = self.mapping
        # mapping = self.joystick_mappings[joy_name]
        
        if status == 1:
            self.handle_button_down_signal(joy_name, btn_id, mapping)
        else:
            self.handle_button_up_signal(joy_name, btn_id, mapping)

    def handle_button_down_signal(self, joy_name, btn_id, mapping):
        if btn_id == mapping["trigger"]:
            if self.armed_status.text() == "Armed":
                logger.critical(f"Trigger pressed at Azimuth {self._gun_azimuth}, Elevation {self._gun_elevation}")
                print("Num of rounds: ", self.num_rounds)
                self.gun_controller.trig(self.num_rounds)
        elif btn_id ==mapping["zoom+"]:
            self.control_camera(CameraType_e.CCT_ZOOM_IN, True)
        elif btn_id == mapping["zoom-"]:
            self.control_camera(CameraType_e.CCT_ZOOM_OUT, True)
        elif btn_id == mapping["pre_register"]:
            self.button_7_press_time = time.time()
            # self.toggle_head_tracking()
            # if self.ballistics_active:
                # self.apply_wind_correction = True
                # self.apply_wind_corrections()
        elif btn_id == mapping["lrf"]:
            if self.check_lrf_firing_enabled():
                logger.critical("LRF fired")
                self.fire_lrf()
            else:
                logger.warning("LRF firing is disabled in configuration")
        # elif btn_id == mapping["up"]:  # Assuming "up" is button 2
        #     self.toggle_looping_movement()
        elif btn_id in [mapping["left"], mapping["up"], mapping["down"], mapping["right"]]:
        # elif btn_id in [mapping["left"], mapping["down"], mapping["right"]]:
            # if self.ballistics_v_diff is not None and self.ballistics_h_diff is not None:
                #x, y = self.ballistics_h_diff, self.ballistics_v_diff
            #x = y = math.degrees(0.002)
            x = y = math.degrees(self.mils_value * 0.001)  # Convert mils to radians then to degrees

            if self.fine_speed:
                logger.info("Fine Speed pressed hence moving by half mils")
                x = y = math.degrees((self.mils_value * 0.5) * 0.001)  # Use half the configured value for fine speed
            elif btn_id == mapping["half_adjustment"]:
                x, y = x / 2, y / 2

            direction = {
                mapping["left"]: ("LEFT", -x, 0),
                mapping["up"]: ("UP", 0, self.tilt_direction*y),
                mapping["down"]: ("DOWN", 0, self.tilt_direction*-y),
                mapping["right"]: ("RIGHT", x, 0)
            }.get(btn_id)

            if direction:
                dir_name, adj_x, adj_y = direction
                logger.critical(f"Ballistic adjustment pressed {dir_name} with {adj_x} {adj_y}")
                self.position_gun_relative(adj_x, adj_y)
        else:
            logger.debug(f"Event btn_down for {btn_id} on {joy_name} is not available")

    def handle_button_up_signal(self, joy_name, btn_id, mapping):
        if btn_id == mapping["trigger"]:
            self.gun_controller.trigoff()
            logger.critical("Trigger released")
        elif btn_id ==mapping["zoom+"]:
            self.control_camera(CameraType_e.CCT_ZOOM_IN, False)
        elif btn_id == mapping["zoom-"]:
            self.control_camera(CameraType_e.CCT_ZOOM_OUT, False)
        elif btn_id == mapping["pre_register"]:
            press_duration = time.time() - self.button_7_press_time
            self.handle_button_7_action(press_duration)
            if self.ballistics_active:
                self.apply_wind_correction = False
        else:
            logger.debug(f"Event btn_up for {btn_id} on {joy_name} is not available")
    
    def toggle_looping_movement(self):
        if not self.looping_movement:
            self.looping_movement = True
            self.looping_thread = threading.Thread(target=self.looping_gun_movement)
            self.looping_thread.start()
            logger.info("Started looping gun movement")
        else:
            self.looping_movement = False
            if self.looping_thread:
                self.looping_thread.join()
            logger.info("Stopped looping gun movement")

    def looping_gun_movement(self):
        positions = [
            (-42, 0),
            (14, 0),
            (14, -20),
            (-42, -20)
        ]
        
        while self.looping_movement:
            for azimuth, elevation in positions:
                if not self.looping_movement:
                    break
                self.gun_speed = 25
                self.position_gun(azimuth, elevation)
                logger.info(f"Gun moved to position: Azimuth {azimuth}, Elevation {elevation}")
                time.sleep(4)  # 4-second delay at each position

    def handle_button_7_action(self, press_duration):
        if not self.target_registration.is_active():
            # logger.warning("Pre-registration mode is not active. Press Ctrl+Shift+T to activate.")
            return

        if press_duration >= self.LONG_PRESS_DURATION:
            # Long press: add current position to targets and save
            # self.fire_lrf()  # Fire LRF before adding target
            # Wait for LRF to update (you might need to implement a proper waiting mechanism)
            # time.sleep(0.5)  
            distance = self._lrf_dist_1 if self._lrf_dist_1 is not None else self.default_distance
            
            # Get current position as displayed in the UI (these are already in the correct orientation)
            azimuth = self._gun_azimuth
            elevation = self._gun_elevation
            
            logger.info(f"Saving target at current position: Azimuth {azimuth}, Elevation {elevation}")
            self.target_registration.add_target(azimuth, elevation, distance)
            logger.info("Target added and saved. You can add more targets or use short press to cycle through targets.")
        else:
            # Short press: cycle to the next target
            next_target = self.target_registration.get_next_target()
            if next_target:
                azimuth = next_target['azimuth']
                elevation = next_target['elevation']
                
                logger.info(f"Moving to target: Azimuth {azimuth}, Elevation {elevation}, Distance {next_target['distance']}")
                
                # The position_gun method now correctly handles system-specific adjustments
                self.position_gun(azimuth, elevation)
            else:
                logger.warning("No targets registered")

    def apply_wind_corrections(self):
        if self.apply_wind_correction and self.ballistics_active:
            # Apply wind corrections to gun position
            correction_pan = 90.0 -  (math.atan(self._lrf_dist_1/0.300)*(180/math.pi)) #0.345
            correction_tilt = 90.0 - (math.atan(self._lrf_dist_1/0.094)*(180/math.pi)) #0.119
            logger.info(f"Corrected Pan: {correction_pan}, Tilt: {correction_tilt}")
            corrected_azimuth = self._gun_azimuth + self.wind_correction_azimuth + correction_pan
            corrected_elevation = self._gun_elevation + self.tilt_direction*self.wind_correction_elevation + correction_tilt
            # corrected_azimuth = self._gun_azimuth + self.wind_correction_azimuth
            # corrected_elevation = self._gun_elevation + self.wind_correction_elevation
            self.position_gun(corrected_azimuth, corrected_elevation)
            logger.info(f"Applied wind corrections: Az {self.wind_correction_azimuth}, El {self.wind_correction_elevation}")

    def update_wind_correction_display(self):
        self.wind_correction_azimuth_value.setText(f"{self.wind_correction_azimuth:.2f}")
        self.wind_correction_elevation_value.setText(f"{self.wind_correction_elevation:.2f}")

    def toggle_pre_registration_mode(self):
        if self.ballistics_active:
            logger.warning("Cannot activate pre-registered targets mode while ballistics is active.")
            # QMessageBox.information(self, "Information", "Cannot activate pre-registered targets mode while ballistics is active.")
            return

        if self.target_registration.is_active():
            self.target_registration.stop()
            self.lrf_firing_enabled = False
            logger.info("Pre-registration mode deactivated. Targets saved. LRF firing disabled.")
        else:
            self.target_registration.start()
            # self.lrf_firing_enabled = True
            logger.info(f"Tilt direction set to {self.tilt_direction}")
            logger.info("Pre-registration mode activated. Loaded saved targets.")
            # QMessageBox.information(self, "Information", "Pre-registration mode activated.\nLRF is ENABLED.")
        self.update_pre_registration_indicator()

    def control_camera(self, camera_type, move):
        if not self.connected:
            return
        if self.currentindex:
            self.ipc_object.camera_move(camera_type, move, VideoType_e.VT_LIGHT)
        else:
            self.ipc_object.camera_move(camera_type, move, VideoType_e.VT_IRD)

    def connect_device(self, connect=True):
        # self.start_laptop_camera()
        if self.connected:
            res = self.ipc_object.disconnect()
            if res:
                self.video_light.overlay_widget.click_window.disconnect()
                self.video_ird.overlay_widget.click_window.disconnect()
                self.ipc_object.stop_video_play(self.light_play_id)
                self.ipc_object.stop_video_play(self.ird_play_id)
                self.connected = False
        elif connect:
            res = self.ipc_object.connect(IP, PORT, USER, PWD, TIMEOUT)
            if res:
                self.connected = True
                # self.__init_signals_slot__()
                # self.refresh_preset()
                # self.refresh_track()
                self.ipc_object.reg_angle_event(self.pAngleEvent, self)
                # self.ipc_object.play_video(
                #     ctypes.c_void_p(self.video_light.winId().__int__()),
                #     VideoType_e.VT_LIGHT,
                #     0,
                #     0,
                #     ctypes.byref(self.light_play_id),
                # )
                self.ipc_object.play_video(
                    int(self.video_light.winId()),
                    VideoType_e.VT_LIGHT,
                    0,
                    0,
                    ctypes.byref(self.light_play_id),
                )
                self.ipc_object.play_video(
                    int(self.video_ird.winId()),
                    VideoType_e.VT_IRD,
                    0,
                    0,
                    ctypes.byref(self.ird_play_id),
                )
                # self.ipc_object.play_video(
                #     ctypes.c_void_p(self.video_ird.winId().__int__()),
                #     VideoType_e.VT_IRD,
                #     0,
                #     0,
                #     ctypes.byref(self.ird_play_id),
                # )
                self.ipc_object.enable_track_ability(VideoType_e.VT_LIGHT, True)
                self.ipc_object.enable_track_ability(VideoType_e.VT_IRD, True)
                self.ipc_object.enable_track(False, tracking_mode=None)

    def connect_camera(self):
        self.detectionQueue = deque(maxlen=1)
        self.fovQueue = deque(maxlen=1)
        self.TEQueue = deque(maxlen=1)
        self.camera = CameraCommunication(self.detectionQueue, self.fovQueue, self.TEQueue)
        res = self.camera.connect('192.168.1.64'.encode(), 39020, 'admin'.encode(), 'Abc.12345'.encode())

    def check_login_status(self):
        if not self.logged_in:
            self.show_login_dialog()
        else:
            self.initializeUI()

    def show_login_dialog(self):
        self.login_dialog = LoginDialog(self, icon = get_asset_path("ico.png"))
        if self.login_dialog.exec_() == QDialog.Accepted:
            self.logged_in = True
            logger.info("Logged in")
            logger.set_username(self.login_dialog.user['role'])
            self.set_system_parameters(self.login_dialog.system_type)
            self.initializeUI()
        else:
            logger.info("Logged out")
            self.logout()

    def set_system_parameters(self, system_type):
        """
        Set system-specific parameters including tilt direction and taboo limits
        
        Args:
            system_type: Type of the system (BMG, NSVT, or RCWS)
        """
        # Set tilt direction based on system type
        if system_type in ['BMG', 'NSVT']:  # Added 'NSVT' with same tilt direction
            self.tilt_direction = 1
        elif system_type == 'RCWS':
            self.tilt_direction = -1
        else:
            logger.warning(f"Unknown system type: {system_type}. Using default tilt direction.")
            self.tilt_direction = 1
        
        logger.info(f"Tilt direction set to {self.tilt_direction} for system type {system_type}")
        
        # Store system type
        self.system_type = system_type
        
        # Get taboo limits from the centralized system_limits module
        limits = get_system_limits(self.system_type)
        self.pan_left_limit = limits['PAN_LEFT_LIMIT']
        self.pan_right_limit = limits['PAN_RIGHT_LIMIT']
        self.tilt_bottom_limit = limits['TILT_BOTTOM_LIMIT']
        self.tilt_top_limit = limits['TILT_TOP_LIMIT']
        
        # Update config file with new taboo values
        self.update_config_with_taboo_values()
        
        # Update config screen with system type
        if hasattr(self, 'config_screen'):
            self.config_screen.set_system_type(system_type)
        
        logger.info(f"System parameters set for {system_type}: " +
                    f"PAN limits [{self.pan_left_limit}, {self.pan_right_limit}], " +
                    f"TILT limits [{self.tilt_top_limit}, {self.tilt_bottom_limit}]")
        
    def update_config_with_taboo_values(self):
        """Update the configuration file with current taboo values"""
        try:
            # Make sure config exists
            if hasattr(self, 'config') and self.config:
                # Update the configuration with current taboo values - consistent naming
                self.config['DEFAULT']['PAN Left taboo'] = str(self.pan_left_limit)
                self.config['DEFAULT']['PAN Right taboo'] = str(self.pan_right_limit)
                self.config['DEFAULT']['TILT Top taboo'] = str(self.tilt_top_limit)
                self.config['DEFAULT']['TILT Bottom taboo'] = str(self.tilt_bottom_limit)
                
                # Save the config file
                with open('config.ini', 'wb') as configfile:
                    self.config.write_encrypted(configfile)
                    
                logger.info("Configuration file updated with new taboo values")
                
                # Reload config in config screen
                if hasattr(self, 'config_screen'):
                    self.config_screen.loadConfig("config.ini", ignore_warning=True)
            else:
                logger.warning("Cannot update config with taboo values: Config object not available")
        except Exception as e:
            logger.error(f"Error updating config with taboo values: {str(e)}")

    def logout(self):
        reply = QMessageBox.question(self, 'Logout Confirmation',
                                    "Do you want to zero the gun before logging out?",
                                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                                    QMessageBox.No)

        if reply == QMessageBox.Cancel:
            return  # User canceled the logout process
        elif reply == QMessageBox.Yes:
            self.position_gun(0, 0)  # Command to zero the gun
            
            # Wait for a moment to allow the gun to move
            time.sleep(0.5)
            
            # Check if the gun is at or very close to the zero position
            if abs(self._gun_azimuth) < 0.1 and abs(self._gun_elevation) < 0.1:
                logger.info("Gun successfully zeroed.")
            else:
                logger.warning(f"Gun not at zero position. Current position: Azimuth {self._gun_azimuth}, Elevation {self._gun_elevation}")
                QMessageBox.warning(self, 'Gun Not Zeroed', 
                                    f"The gun did not reach the zero position.\nCurrent position: Azimuth {self._gun_azimuth:.2f}, Elevation {self._gun_elevation:.2f}")

        # Proceed with logout after a 2-second delay
        time.sleep(1)

        if hasattr(self, 'program') and self.program:
            # Stop the timer
            if hasattr(self.program, 'timer'):
                self.program.timer.stop()
            
            # Set flag to stop thread
            self.program.running = False
        
        # Now disconnect and exit
        self.logged_in = False
        self.close()
        self.connect_device(False)
        self.gun_controller.exit()

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    stacked_widget = item.widget() and item.widget().property(
                        "stackedWidget"
                    )
                    if stacked_widget is not None:
                        self.clearStackedWidget(stacked_widget)
                    else:
                        self.clearLayout(item.layout())

    def clearStackedWidget(self, stacked_widget):
        if stacked_widget is not None:
            for index in range(stacked_widget.count()):
                page_widget = stacked_widget.widget(index)
                self.clearLayout(page_widget.layout())

    def reset_application(self):
        # Clear the current layout
        layout = self.layout()
        self.clearLayout(layout)
        self.close()

        # new_player = VideoPlayer()
        # new_player.show()
    def set_config_variables(self):
        self.wind_speed_mode = self.config['DEFAULT'].get('Wind Speed Mode', 'Manual')
        self.manual_wind_speed = float(self.config['DEFAULT'].get('Wind Speed', 0))
        self.wind_direction = self.config['DEFAULT'].get('Wind Direction', '0')
        self.lrf_firing_enabled = self.config['DEFAULT'].get('Fire LRF', 'Disable') == 'Enable'
        self.default_distance = int(self.config['DEFAULT'].get('Default LRF Distance considered (in case LRF is set off)', 1000))
        self.track_mode = self.config['DEFAULT'].get('Track Mode', 'Manual ground tracking')
        self.velo_speed = int(self.config['DEFAULT'].get('Velocity Speed',50))
        self.thermal_camera_power = self.config['DEFAULT'].get('Thermal Camera Power', 'Off')
        self.firing_rate = int(self.config['DEFAULT'].get('Firing Rate', 700))
        self.num_rounds = int(self.config['DEFAULT'].get('Number of Rounds', 0))
        self.Kp = float(self.config['DEFAULT'].get('PID Kp', 3.2))
        self.Ki = float(self.config['DEFAULT'].get('PID Ki', 0.7))
        self.Kd = float(self.config['DEFAULT'].get('PID Kd', 0))
        self.radar_ip = self.config['DEFAULT'].get('Radar IP', '10.1.0.245')
        self.radar_port = int(self.config['DEFAULT'].get('Radar Port', 9010))
        self.latitude = float(self.config['DEFAULT'].get('Latitude', 34.152300))
        self.longitude = float(self.config['DEFAULT'].get('Longitude', 77.577000))
        self.altitude = float(self.config['DEFAULT'].get('Altitude', 0))
        
        # Add Fire on Move setting
        self.fire_on_move = self.config['DEFAULT'].get('Fire on Move', 'Off')
        self.mils_value = float(self.config['DEFAULT'].get('Mils', 1.0))

        logger.info("Configuration loaded")
        logger.info(f"Wind Speed Mode: {self.wind_speed_mode}")
        logger.info(f"Manual Wind Speed set to: {self.manual_wind_speed}")
        logger.info(f"Wind Direction: {self.wind_direction}")
        logger.info(f"LRF Firing Enabled: {self.lrf_firing_enabled}")
        logger.info(f"Default LRF Distance: {self.default_distance}")
        logger.info(f"Track Mode: {self.track_mode}")
        logger.info(f"Velocity: {self.velo_speed}")
        logger.info(f"Thermal Camera Power: {self.thermal_camera_power}")
        logger.info(f"Firing Rate: {self.firing_rate}")
        logger.info(f"Number of Rounds: {self.num_rounds}")
        logger.info(f"Fire on Move: {self.fire_on_move}")
        logger.info(f"Mils Value: {self.mils_value}")
        logger.info(f"Tracking Kp: {self.Kp}")
        logger.info(f"Tracking Ki: {self.Ki}")
        logger.info(f"Tracking Kd: {self.Kd}")
        logger.info(f"Radar IP: {self.radar_ip}")
        logger.info(f"Radar Port: {self.radar_port}")
        logger.info(f"Latitude: {self.latitude}")
        logger.info(f"Longitude: {self.longitude}")
        logger.info(f"Altitude: {self.altitude}")

        if hasattr(self, 'connected') and self.connected and hasattr(self, 'ipc_object'):
            try:
                 
                mode_map = {
                    'Semi-auto air tracking': TrackMode_e.TRACK_AIR_SEMIAUTO,
                    'Manual ground tracking': TrackMode_e.TRACK_GROUND_MANUAL,
                    'Semi-auto ground tracking': TrackMode_e.TRACK_GROUND_SEMIAUTO,
                    'Auto ground tracking': TrackMode_e.TRACK_GROUND_AUTO
                }
                
                mode_enum = mode_map.get(self.track_mode)
                if mode_enum is not None:
                    # Set SDK track mode
                    self.ipc_object.set_track_mode(
                        VideoType_e.VT_LIGHT if self.currentindex else VideoType_e.VT_IRD, 
                        TrackMode_e(mode_enum.value)
                    )

                    # Set thermal mode
                    cmd = "imgSetCfg"
                    para = {
                        "Mode": mode_enum.value
                    }
                    self.ipc_object.send_common_cmd(cmd, para)
                    
                    logger.info(f"Successfully set track mode to {self.track_mode}")

                # Apply thermal camera power setting - we'll handle this in update_config_variables
                # This prevents setting the power twice during initialization

            except Exception as e:
                logger.error(f"Failed to set track mode: {str(e)}")

    def set_thermal_camera_power(self, power_on=True):
        """
        Set the thermal camera power using the manual control with timer

        Args:
            power_on (bool): True to power on, False to power off
        """
        try:
            # Always use 8:00 as the time setting
            hour = 8
            minute = 0

            # Use the manual parameter set command with timer
            cmd = "powerCoolIrManuParaSet"
            power_value = 1 if power_on else 0

            para = {
                "param": {
                    "power": power_value,
                    "sTimeHour": hour,
                    "sTimeMinute": minute
                }
            }

            logger.info(f"Setting thermal power to {power_value} with time {hour}:{minute}")
            response = self.ipc_object.send_common_cmd(cmd, para["param"])
            response_json = json.loads(response.decode('utf-8'))
            logger.debug(f"Power command response: {response_json}")

            # Check for success or interval too short error
            if response_json.get('ackvalue') == 100 or ('timestamp' in response_json and response_json.get('ackvalue') != 101):
                self.thermal_camera_power = 'On' if power_on else 'Off'
                logger.info(f"Successfully set thermal camera power to {self.thermal_camera_power}")

                # Update config
                self.config['DEFAULT']['Thermal Camera Power'] = self.thermal_camera_power
                with open('config.ini', 'wb') as configfile:
                    self.config.write_encrypted(configfile)

                return True
            elif response_json.get('ackvalue') == 101:
                logger.warning("Camera reported interval too short.")

                # Set the thermal camera power to 'Off' regardless of requested state
                self.thermal_camera_power = 'Off'
                self.config['DEFAULT']['Thermal Camera Power'] = self.thermal_camera_power

                # Save the config
                with open('config.ini', 'wb') as configfile:
                    self.config.write_encrypted(configfile)

                # Show a popup message about the interval being too short
                QMessageBox.warning(
                    self, 
                    "Thermal Camera Error", 
                    "The thermal camera reported 'interval too short'. Wait for a few minutes before trying to turn it on again."
                )

                # Update radio buttons in config screen if possible - WITHOUT USING QRadioButton directly
                try:
                    if hasattr(self, 'config_screen') and hasattr(self.config_screen, 'inputs'):
                        thermal_widget = self.config_screen.inputs.get('Thermal Camera Power')
                        if thermal_widget and thermal_widget.layout():
                            # Find all child widgets that might be radio buttons
                            for i in range(thermal_widget.layout().count()):
                                item = thermal_widget.layout().itemAt(i)
                                if item and item.widget():
                                    button = item.widget()
                                    # Check if it's a radio button by method instead of type
                                    if hasattr(button, 'isChecked') and hasattr(button, 'setChecked') and hasattr(button, 'text'):
                                        if button.text() == 'Off':
                                            button.setChecked(True)
                                            break
                except Exception as e:
                    logger.warning(f"Could not update radio buttons: {str(e)}")

                return False
            else:
                logger.warning(f"Failed to set thermal power. Response: {response_json}")
                QMessageBox.warning(
                    self, 
                    "Thermal Camera Error", 
                    f"Failed to set thermal camera power. Response code: {response_json.get('ackvalue')}"
                )
                return False

        except Exception as e:
            logger.error(f"Error setting thermal camera power: {str(e)}")
            QMessageBox.critical(
                self, 
                "Error", 
                f"An error occurred while controlling the thermal camera: {str(e)}"
            )
            return False
        

    def update_config_variables(self):
        previous_thermal_power = getattr(self, 'thermal_camera_power', 'Off')
        previous_firing_rate = getattr(self, 'firing_rate', 700)
        previous_num_rounds = getattr(self, 'num_rounds', 0)
        
        # Get previous Fire on Move setting correctly
        previous_fire_on_move = 'Off'  # Default value
        if hasattr(self, 'config') and hasattr(self.config, '__contains__') and 'DEFAULT' in self.config:
            try:
                previous_fire_on_move = self.config['DEFAULT'].get('Fire on Move', 'Off')
            except:
                # If any error, use default
                previous_fire_on_move = 'Off'
        
        self.set_config_variables()
        self.update_taboo_values_from_config()
        self.update_ui_elements()

        if previous_thermal_power != self.thermal_camera_power and hasattr(self, 'connected') and self.connected:
            logger.info(f"Thermal camera power changed from {previous_thermal_power} to {self.thermal_camera_power}")
            power_on = self.thermal_camera_power == 'On'
            self.set_thermal_camera_power(power_on)
        logger.info(f"Sending PID Values to ESP: {self.Kp, self.Ki, self.Kd}")
        # Handle firing rate and number of rounds changes
        if hasattr(self, 'gun_controller') and self.gun_controller.connected:
            # Check if firing rate has changed
            if previous_firing_rate != self.firing_rate:
                logger.info(f"Firing rate changed from {previous_firing_rate} to {self.firing_rate}")
                success = self.gun_controller.set_firing_rate(self.firing_rate)
                if success:
                    logger.info(f"Successfully updated firing rate to {self.firing_rate}")
                else:
                    logger.error(f"Failed to update firing rate to {self.firing_rate}")
            
            # Check if number of rounds has changed
            if previous_num_rounds != self.num_rounds:
                logger.info(f"Number of rounds changed from {previous_num_rounds} to {self.num_rounds}")
                success = self.gun_controller.set_rounds(self.num_rounds)
                if success:
                    logger.info(f"Successfully updated number of rounds to {self.num_rounds}")
                else:
                    logger.error(f"Failed to update number of rounds to {self.num_rounds}")
                    
            # Check if Fire on Move setting has changed
            current_fire_on_move = 'Off'  # Default value
            if 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
                current_fire_on_move = self.config['DEFAULT']['Fire on Move']
                
            if previous_fire_on_move != current_fire_on_move:
                logger.info(f"Fire on Move setting changed from {previous_fire_on_move} to {current_fire_on_move}")
                # Update the armed state and brake application
                if hasattr(self, 'update_armed_state'):
                    self.update_armed_state()

            # Send PID tuning Values
            logger.info(f"Sending PID Values to ESP: {self.Kp, self.Ki, self.Kd}")
            self.gun_controller.send_PID_values(self.Kp, self.Ki, self.Kd)

    def update_armed_state(self):
        """Update the armed state and brake application based on current settings"""
        if hasattr(self, 'armed') and self.armed:
            # If armed and Fire on Move is Off, ensure brake is applied
            fire_on_move = 'Off'  # Default value
            if hasattr(self, 'config') and 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
                fire_on_move = self.config['DEFAULT']['Fire on Move']
                
            if fire_on_move == 'Off':
                logger.info("Applying brake because Fire on Move is Off")
                self.gun_controller.brake()
            else:
                # If armed and Fire on Move is On, ensure brake is released
                logger.info("Releasing brake because Fire on Move is On")
                self.gun_controller.unbrake()

    def update_taboo_values_from_config(self):
        """Update the taboo limit values from the configuration file"""
        try:
            # First make sure the attributes exist, initialize if not
            if not hasattr(self, 'pan_left_limit'):
                # Set default values if not initialized yet
                self.pan_left_limit = -180
                self.pan_right_limit = 180
                self.tilt_bottom_limit = -5
                self.tilt_top_limit = 15
                logger.info("Initialized default taboo values")
            
            # Now update from configuration
            self.pan_left_limit = int(self.config['DEFAULT'].get('PAN Left taboo', self.pan_left_limit))
            self.pan_right_limit = int(self.config['DEFAULT'].get('PAN Right taboo', self.pan_right_limit))
            self.tilt_bottom_limit = int(self.config['DEFAULT'].get('TILT Bottom taboo', self.tilt_bottom_limit))
            self.tilt_top_limit = int(self.config['DEFAULT'].get('TILT Top taboo', self.tilt_top_limit))
            
            logger.info(f"Updated taboo values from config: Pan: [{self.pan_left_limit}, {self.pan_right_limit}], Tilt: [{self.tilt_bottom_limit}, {self.tilt_top_limit}]")
        except Exception as e:
            logger.error(f"Error updating taboo values from config: {str(e)}")

    def update_ui_elements(self):
        if hasattr(self, 'wind_speed_value') and hasattr(self, 'wind_direction_value'):
            self.wind_speed_value.setText(f"{self.manual_wind_speed:.1f}")
            self.wind_direction_value.setText(self.wind_direction)


    def on_stacked_widget_changed(self, index):
        """
        Handle stack widget index changes for diagnostics
        """
        # Start diagnostics timer if we're showing the diagnose screen (index 3)
        if index != 3:
            # If not on diagnose screen, ensure timer is stopped
            self.stop_diagnostics_timer()

        if index == 3:
            self.start_diagnostics_updates()
        else:
            # Stop the timer if we're not showing the diagnose screen
            if hasattr(self, 'diagnostics_timer') and self.diagnostics_timer.isActive():
                self.diagnostics_timer.stop()
                logger.info("Diagnostics timer stopped - navigated away from diagnostics")
                
    def initializeUI(self):
        screen_geo = QApplication.desktop().screenGeometry()
        screen_width = screen_geo.width()
        screen_height = screen_geo.height()

        # Calculate responsive sizing based on screen dimensions
        wh = int(screen_height * 0.035)  # Base height unit, ~3.5% of screen height
        font_size = int(wh * 0.6)        # Font size proportional to element height
        border_radius = wh // 2          # Border radius for rounded elements
        small_padding = int(screen_width * 0.005)  # Small padding size
        
        # Standard widget minimum widths based on screen percentage
        label_min_width = int(screen_width * 0.06)  # For text values (~90px on 1920 width)
        icon_width = int(screen_width * 0.02)       # For icons (~30px on 1920 width)

        self.video_light = VideoPrompt(self)
        self.video_light.setObjectName("video_light")
        self.video_ird = VideoPrompt(self)
        self.video_ird.setObjectName("video_ird")

        self.video_light.overlay_widget.click_window.connect(self.click_window_slot)
        self.video_ird.overlay_widget.click_window.connect(self.click_window_slot)
        self.video_light.overlay_widget.select_track.connect(self.select_track_slot)
        self.video_ird.overlay_widget.select_track.connect(self.select_track_slot)
        # self.video_ird.overlay_widget.zoom_in.connect(self.zoom_in)
        # self.video_ird.overlay_widget.zoom_out.connect(self.zoom_out)
        # self.video_light.overlay_widget.zoom_in.connect(self.zoom_in)
        # self.video_light.overlay_widget.zoom_out.connect(self.zoom_out)
        # self.video_rcws.overlay_widget.click_window.connect(self.click_window_slot)
        # self.video_rcws.overlay_widget.select_track.connect(self.select_track_slot_rcws)

        self.stackedWidget = QStackedWidget()
        self.stackedWidget.addWidget(self.video_ird)
        self.stackedWidget.addWidget(self.video_light)

        self.stackedWidget.addWidget(self.config_screen)
        self.stackedWidget.addWidget(self.diagnose_screen)

        self.overlay_light = NativeOverlay(self.video_light)
        self.overlay_ird = NativeOverlay(self.video_ird)
        self.overlay_compass_light = NativeOverlayCompass(self.video_light)
        self.overlay_compass_ird = NativeOverlayCompass(self.video_ird)

        self.bal_overlay_ird = NativeOverlayBalLine(self.video_ird)
        self.bal_overlay_light = NativeOverlayBalLine(self.video_ird)

        # self.stackedWidget.addWidget(self.video_rcws)
        self.stackedWidget.setMaximumWidth(int(screen_width * 0.8))
        self.stackedWidget.setMinimumWidth(int(screen_width * 0.8))
        self.stackedWidget.setProperty("stackedWidget", True)

        self.stackedWidget.currentChanged.connect(self.on_stacked_widget_changed)

        self.leftButtonsLayout1 = QVBoxLayout()
        self.rightButtonsLayout1 = QVBoxLayout()
        self.leftButtonsLayout2 = QVBoxLayout()
        self.rightButtonsLayout2 = QVBoxLayout()
        self.leftButtonsLayout3 = QVBoxLayout()  # New layout for CAM B/C menu
        self.rightButtonsLayout3 = QVBoxLayout()
        self.l1 = QWidget()
        self.l1.setLayout(self.leftButtonsLayout1)
        self.l2 = QWidget()
        self.l2.setLayout(self.leftButtonsLayout2)
        self.l3 = QWidget()  # New widget for CAM B/C menu
        self.l3.setLayout(self.leftButtonsLayout3)

        self.r1 = QWidget()
        self.r1.setLayout(self.rightButtonsLayout1)
        self.r2 = QWidget()
        self.r2.setLayout(self.rightButtonsLayout2)
        self.r3 = QWidget()  # New widget for CAM B/C menu
        self.r3.setLayout(self.rightButtonsLayout3)

        self.leftButtonsLayoutStack = QStackedWidget()
        self.leftButtonsLayoutStack.addWidget(self.l1)
        self.leftButtonsLayoutStack.addWidget(self.l2)
        self.leftButtonsLayoutStack.addWidget(self.l3) 

        self.rightButtonsLayoutStack = QStackedWidget()
        self.rightButtonsLayoutStack.addWidget(self.r1)
        self.rightButtonsLayoutStack.addWidget(self.r2)
        self.rightButtonsLayoutStack.addWidget(self.r3)

        self.buttonsLayout = QHBoxLayout()
        self.buttonsLayout.addWidget(self.leftButtonsLayoutStack)
        self.buttonsLayout.addWidget(self.stackedWidget)
        self.buttonsLayout.addWidget(self.rightButtonsLayoutStack)

        # Initialize status bar layout with responsive spacing
        self.reportLayoutMain = QHBoxLayout()
        self.reportLayoutMain.setSpacing(small_padding)
        self.reportLayoutMain.setContentsMargins(small_padding, small_padding, small_padding, small_padding)

        # Armed status widget
        self.armed_status_widget = QWidget(self)
        reportLayout = QHBoxLayout(self.armed_status_widget)
        reportLayout.setContentsMargins(small_padding, 0, small_padding, 0)

        self.armed_status = QLabel("Unarmed")
        self.armed_status.setMinimumHeight(wh)
        self.armed_status.setMinimumWidth(int(screen_width * 0.08))
        self.armed_status.setMaximumWidth(int(screen_width * 0.1))
        self.armed_status.setAlignment(Qt.AlignCenter)
        reportLayout.addWidget(self.armed_status)

        self.armed_status_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.armed_status_widget.setStyleSheet(self.get_stylesheet_armed(False))
        self.reportLayoutMain.addWidget(self.armed_status_widget)

        # Gun speed widget
        hbox2_widget = QWidget(self)
        reportLayout = QHBoxLayout(hbox2_widget)
        reportLayout.setContentsMargins(small_padding, 0, small_padding, 0)

        self.gun_speed = 50
        self.cam_speed = 50
        self.gunSpeed = QLabel(str(self.gun_speed))
        self.gunSpeed.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.gunSpeed.setStyleSheet(
            f"""
                font-size: {font_size}px;
                font-weight: bold;
                color: #2B411C;
                background-color: #A4AA88;
                padding: 2px;
                border-radius: {border_radius // 2}px;
                border: 2px solid #2B411C
            """
        )
        self.gunSpeed.setMinimumHeight(wh)
        self.gunSpeed.setMinimumWidth(int(screen_width * 0.03))
        reportLayout.addWidget(self.gunSpeed)

        # Wind data widget
        wind_widget = QWidget(self)
        wind_layout = QHBoxLayout(wind_widget)
        wind_layout.setContentsMargins(small_padding, 0, small_padding, 0)
        wind_layout.setSpacing(small_padding)

        # Wind Speed
        wind_speed_label = QLabel("Wind: Speed")
        wind_speed_label.setMinimumHeight(wh)
        wind_speed_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        wind_layout.addWidget(wind_speed_label)

        self.wind_speed_value = QLabel("0.0")
        self.wind_speed_value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wind_speed_value.setStyleSheet(
            f"""
                font-size: {font_size}px;
                font-weight: bold;
                color: white;
                background-color: black;
                padding: 2px;
                text-align: right;
                border-radius: {border_radius // 2}px;
            """
        )
        self.wind_speed_value.setMinimumHeight(wh)
        self.wind_speed_value.setMinimumWidth(label_min_width)
        wind_layout.addWidget(self.wind_speed_value)

        # Wind icon
        wind_icon_label = QLabel()
        wind_icon_label.setPixmap(
            QPixmap(get_asset_path("wind.png")).scaled(wh, wh, aspectRatioMode=Qt.KeepAspectRatio)
        )
        wind_icon_label.setMinimumHeight(wh)
        wind_icon_label.setMaximumWidth(icon_width)
        wind_layout.addWidget(wind_icon_label)

        # Wind Direction
        self.wind_direction_value = QLabel("N/A")
        self.wind_direction_value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wind_direction_value.setStyleSheet(
            f"""
                font-size: {font_size}px;
                font-weight: bold;
                color: white;
                background-color: black;
                padding: 2px;
                text-align: right;
                border-radius: {border_radius // 2}px;
            """
        )
        self.wind_direction_value.setMinimumHeight(wh)
        self.wind_direction_value.setMinimumWidth(label_min_width)
        wind_layout.addWidget(self.wind_direction_value)

        wind_direction_label = QLabel("Direction")
        wind_direction_label.setMinimumHeight(wh)
        wind_direction_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        wind_layout.addWidget(wind_direction_label)

        wind_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        wind_widget.setStyleSheet(
            f"""
                background-color:#4C5D34;
                border-radius:{border_radius}px;
                padding: 0;
            """
        )
        self.reportLayoutMain.addWidget(wind_widget)

        # Wind correction widget
        wind_correction_widget = QWidget(self)
        wind_correction_layout = QHBoxLayout(wind_correction_widget)
        wind_correction_layout.setContentsMargins(small_padding, 0, small_padding, 0)
        wind_correction_layout.setSpacing(small_padding)

        wind_correction_label = QLabel("Correction: Az")
        wind_correction_label.setMinimumHeight(wh)
        wind_correction_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        wind_correction_layout.addWidget(wind_correction_label)

        self.wind_correction_azimuth_value = QLabel("0.00")
        self.wind_correction_azimuth_value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wind_correction_azimuth_value.setStyleSheet(
            f"""
                font-size: {font_size}px;
                font-weight: bold;
                color: white;
                background-color: black;
                padding: 2px;
                text-align: right;
                border-radius: {border_radius // 2}px;
            """
        )
        self.wind_correction_azimuth_value.setMinimumHeight(wh)
        self.wind_correction_azimuth_value.setMinimumWidth(label_min_width)
        wind_correction_layout.addWidget(self.wind_correction_azimuth_value)

        self.wind_correction_elevation_value = QLabel("0.00")
        self.wind_correction_elevation_value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.wind_correction_elevation_value.setStyleSheet(
            f"""
                font-size: {font_size}px;
                font-weight: bold;
                color: white;
                background-color: black;
                padding: 2px;
                text-align: right;
                border-radius: {border_radius // 2}px;
            """
        )
        self.wind_correction_elevation_value.setMinimumHeight(wh)
        self.wind_correction_elevation_value.setMinimumWidth(label_min_width)
        wind_correction_layout.addWidget(self.wind_correction_elevation_value)

        wind_correction_layout.addWidget(QLabel("El"))

        wind_correction_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        wind_correction_widget.setStyleSheet(
            f"""
                background-color:#4C5D34;
                border-radius:{border_radius}px;
                padding: 0;
            """
        )
        self.reportLayoutMain.addWidget(wind_correction_widget)

        hbox2_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox2_widget.setStyleSheet(
            f"""
                background-color:#4C5D34;
                border-radius:{border_radius}px;
                padding: 0;
            """
        )
        self.reportLayoutMain.addWidget(hbox2_widget)
        
        # Add responsive spacer instead of fixed-width spacer
        self.reportLayoutMain.addSpacerItem(QSpacerItem(int(screen_width * 0.02), 0, QSizePolicy.Fixed, QSizePolicy.Fixed))

        # Gun status widget
        for i in ["gun"]:
            hbox2_widget = QWidget(self)
            reportLayout = QHBoxLayout(hbox2_widget)
            reportLayout.setContentsMargins(small_padding, 0, small_padding, 0)
            reportLayout.setSpacing(small_padding)

            value_label = QLabel("Az")
            value_label.setMinimumHeight(wh)
            value_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            reportLayout.addWidget(value_label)
            
            value_label = QLabel("-000.00")
            self.__setattr__(f"{i}Azimuth", value_label)
            value_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            value_label.setStyleSheet(
                f"""
                    font-size: {font_size}px;
                    font-weight: bold;
                    color: white;
                    background-color: black;
                    padding: 2px;
                    text-align: right;
                    border-radius: {border_radius // 2}px;
                """
            )
            value_label.setMinimumHeight(wh)
            value_label.setMinimumWidth(label_min_width)
            reportLayout.addWidget(value_label)

            icon1_label = QLabel()
            icon1_label.setPixmap(
                QPixmap(get_asset_path("{}.png".format(i))).scaled(
                    wh, wh, aspectRatioMode=0
                )
            )
            icon1_label.setMinimumHeight(wh)
            icon1_label.setMaximumWidth(icon_width)
            reportLayout.addWidget(icon1_label)

            value_label = QLabel("-000.00")
            self.__setattr__(f"{i}Elevation", value_label)
            value_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            value_label.setStyleSheet(
                f"""
                    font-size: {font_size}px;
                    font-weight: bold;
                    color: white;
                    background-color: black;
                    padding: 2px;
                    text-align: right;
                    border-radius: {border_radius // 2}px;
                """
            )
            value_label.setMinimumHeight(wh)
            value_label.setMinimumWidth(label_min_width)
            reportLayout.addWidget(value_label)

            value_label = QLabel("El")
            value_label.setMinimumHeight(wh)
            value_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            reportLayout.addWidget(value_label)
            
            hbox2_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            hbox2_widget.setStyleSheet(
                f"""
                    background-color:#4C5D34;
                    border-radius:{border_radius}px;
                    padding: 0;
                """
            )
            self.reportLayoutMain.addWidget(hbox2_widget)

        # Add stretch at the end to push elements to the left
        self.reportLayoutMain.addStretch(1)

        self.layoutCurrent = QVBoxLayout()
        self.layoutCurrent.addLayout(self.buttonsLayout)
        self.layoutCurrent.addLayout(self.reportLayoutMain)

        self.setLayout(self.layoutCurrent)

        # Set initial button states
        self.originalButtonsState(screen_width)
        self.newButtonsState(screen_width)
        self.camBCButtonsState(screen_width)

        self._gun_azimuth = 0
        self._gun_elevation = 0
        self._cam_azimuth = 0
        self._cam_elevation = 0
        self._delta_azimuth = 0
        self._delta_elevation = 0
        self._lrf_dist_1 = 500
        self._lrf_dist_2 = None
        self._lrf_dist_updated = None
        self.throttled = None
        self.update_ui_elements()
    
    # def getFOV(self):
    #     data = json.loads(self.ipc_object.get_magnification_data('visibleGetFocalInfo').decode('utf-8'))
    #     logger.warning(f"{data}")
    #     focal_length = data['camFocalCurFocal'] / 100
    #     # return hfov_deg, vfov_deg
    #     vfov_deg = data['camFocalCurView'] / 100
        
    #     return self.correct_fov(vfov_deg, 16/9)

    def getFOV(self):
        if self.stackedWidget.currentIndex() == 0:
            hfov_deg = json.loads(self.ipc_object.get_thermal_fov().decode('utf-8'))['fov'] / 100
            vfov_deg = math.degrees(2 * math.atan(math.tan(math.radians(hfov_deg) / 2) / 1.25))
            # return self.correct_fov(vfov_deg, 1.25)
            return hfov_deg, vfov_deg
        elif self.stackedWidget.currentIndex() == 1:
            data = json.loads(self.ipc_object.get_magnification_data('visibleGetFocalInfo').decode('utf-8'))
            hfov_deg = data['camFocalCurView'] / 100
            vfov_deg = math.degrees(2 * math.atan(math.tan(math.radians(hfov_deg) / 2) / 1.77))
            # return self.correct_fov(vfov_deg, 16/9)
            return hfov_deg, vfov_deg
    
    def correct_fov(self, vfov_deg, aspect_ratio):
        if vfov_deg > 2:
            vfov_deg = vfov_deg
        elif vfov_deg >= 1 and vfov_deg <= 2:
            vfov_deg += 0.2
        elif vfov_deg >= 0.8 and vfov_deg < 1:
            vfov_deg += 0.37
        elif vfov_deg >= 0.7 and vfov_deg < 0.8:
            vfov_deg += 0.4
        elif vfov_deg >= 0.5 and vfov_deg < 0.7:
            vfov_deg += 0.5
        elif vfov_deg < 0.5:
            vfov_deg += 0.68
        
        hfov_deg = math.degrees(2 * math.atan(math.tan(math.radians(vfov_deg/2)) * (aspect_ratio)))
        return hfov_deg, vfov_deg
        
    def setFOV(self, fov, video_type):
        if self.cgi_login():
            CAMERA_IP = "192.168.1.64"
            URL = f"http://{CAMERA_IP}/cgi-bin/proc.cgi"
            headers = {"Content-Type": "application/json"}
            payload = {
                "cmd": video_type,
                "param": {
                    "token": self.TOKEN,
                    "fov": fov
                }
            }
            response = requests.post(URL, headers=headers, data=json.dumps(payload))
            data = response.json()

            if data["param"]["ackvalue"] == 100:
                return True
            else:
                return False
            
    def throttle_function(self):
        c = time.time()
        if self.throttled is None or self.throttled + 5 < c:
            if self.connected:
                logger.critical("Laser Fired")
                self.ipc_object.laser_ranging(0, self.pLaserRangingEvent, self)
            self.throttled = c

    def check_lrf_firing_enabled(self):
        return self.lrf_firing_enabled
    
    def fire_lrf(self):
        if self.lrf_firing_enabled:
            if self.connected:
                logger.critical("Firing LRF")
                self.ipc_object.laser_ranging(0, self.pLaserRangingEvent, self)
            else:
                logger.warning("Cannot fire LRF: Not connected")
        else:
            logger.warning(f"LRF firing is disabled. Using default distance: {self.default_distance} meters")
            self.received_laser(self.default_distance)

    def get_stylesheet_armed(self, armed):
        if armed:
            return """
                background-color: #2B411C;
                border-radius: 20px;
                color: white;
                font-size: 20px;
                text-align: center;
                font-weight: bold;

            """
        else:
            return """
                background-color: #C8C8C8;
                border-radius: 20px;
                color: #2B411C;
                font-size: 20px;
                text-align: center;
                font-weight: bold;
            """

    def received_laser(self, distance):
        logger.critical("LRF Received {}".format(str(distance)))
        self.set_lrf(distance, distance)
    
    def select_track_slot_rcws(self, start, end):
        logger.critical("Selected adjustment for RCWS")
        x = (start.x() + end.x()) / 2
        y = (start.y() + end.y()) / 2
        h = self.video_rcws.height()
        w = self.video_rcws.width()
        y = h - y
        fov_h = math.degrees(0.120)
        fov_v = math.degrees(0.096)


        x = rescale(x, 0, w, 0, fov_h)
        y = rescale(y, 0, h, 0, fov_v)

        x= x - fov_h/2
        y= y - fov_v/2
        d = 750

        x = self.adjust(x, d, 0.108)
        y = self.adjust(y, d, 0.172)
        self.position_gun_relative(x, y)

    def adjust(self, theta, d, r):
        theta =  math.radians(theta)
        return math.degrees(math.atan2( d * math.tan(theta) - r + r * math.cos(theta), d - r * math.sin(theta)))

    def select_track_slot(self, start, end):
        if not self.connected:
            return
        logger.critical("Selected track for CAMERA")
        select_rect = HvsSDK.track.Rect()
        select_rect.top = start.y()
        select_rect.left = start.x()
        select_rect.bottom = end.y()
        select_rect.right = end.x()
        video_rect = HvsSDK.track.Rect()
        if self.currentindex:
            video_rect.top = self.video_light.x()
            video_rect.left = self.video_light.y()
            video_rect.bottom = self.video_light.y() + self.video_light.height()
            video_rect.right = self.video_light.x() + self.video_light.width()
            self.ipc_object.select_rect_track(
                VideoType_e.VT_LIGHT, video_rect, select_rect
            )
        else:
            video_rect.top = self.video_ird.x()
            video_rect.left = self.video_ird.y()
            video_rect.bottom = self.video_ird.y() + self.video_ird.height()
            video_rect.right = self.video_ird.x() + self.video_ird.width()
            self.ipc_object.select_rect_track(
                VideoType_e.VT_IRD, video_rect, select_rect
            )

    def control_ptz(self, ptz_type, move, vspeed=1, hspeed=1):
        vspeed = self.cam_speed * vspeed
        hspeed = self.cam_speed * hspeed
        self.ipc_object.control_move(ptz_type, move, int(vspeed), int(hspeed))

    def get_xy(self):
        try:
            pos_x = self.x_in.text()
            pos_y = self.y_in.text()
            if len(pos_x) == 0:
                x = float(0)
            else:
                x = float(pos_x)

            if len(pos_x) == 0:
                y = float(0)
            else:
                y = float(pos_y)
        except Exception as e:
            return None, None, False
        return x, y, True

    def make_move(self):
        x, y, valid = self.get_xy()
        if not valid:
            return
        self.position_cam(x, y)
        self.position_gun(x, y)

    def make_move_cam(self):
        x, y, valid = self.get_xy()
        if not valid:
            return
        self.position_cam(x, y)

    def make_move_gun(self):
        x, y, valid = self.get_xy()
        if not valid:
            return
        self.position_gun(x, y)

    def position_cam(self, x, y):
        if self.connected:
            logger.info("Moving Cam {} to {}".format(str(x), str(y)))
            self.ipc_object.position_xy(x, y, self.cam_speed)

    def position_gun_relative(self, x, y):
        # Check if system is ARMED and Fire on Move is Off
        fire_on_move = 'Off'  # Default value
        if hasattr(self, 'config') and 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
            fire_on_move = self.config['DEFAULT']['Fire on Move']
            
        if hasattr(self, 'armed') and self.armed and fire_on_move == 'Off':
            logger.info(f"Gun relative movement command by ({x}, {y}) ignored: System is ARMED and Fire on Move is Off")
            return False
            
        return self.position_gun(self._gun_azimuth + x, self._gun_elevation + y)

    def position_gun(self, x, y):
        fire_on_move = 'Off'  # Default value
        if hasattr(self, 'config') and 'DEFAULT' in self.config and 'Fire on Move' in self.config['DEFAULT']:
            fire_on_move = self.config['DEFAULT']['Fire on Move']
            
        if hasattr(self, 'armed') and self.armed and fire_on_move == 'Off':
            logger.info(f"Gun movement command to ({x}, {y}) ignored: System is ARMED and Fire on Move is Off")
            return False
        
        if not (self.config['DEFAULT'].get('Taboo Zone', 'Off') == 'On'):
            limits = get_system_limits(self.system_type)
            self.pan_left_limit = limits['PAN_LEFT_LIMIT']
            self.pan_right_limit = limits['PAN_RIGHT_LIMIT']
            self.tilt_bottom_limit = limits['TILT_BOTTOM_LIMIT']
            self.tilt_top_limit = limits['TILT_TOP_LIMIT']

        if not (self.pan_left_limit <= self._gun_azimuth <= self.pan_right_limit and self.tilt_bottom_limit <= self._gun_elevation <= self.tilt_top_limit):
            message = (f"Current position (Az: {self._gun_azimuth:.2f}, El: {self._gun_elevation:.2f}) is outside the allowed limits.\n\n"
                    f"Azimuth: between {self.pan_left_limit} and {self.pan_right_limit}\n"
                    f"Elevation: between {self.tilt_bottom_limit} and {self.tilt_top_limit}")
            
            # Show warning with "OK" button
            self.notification_overlay.show_warning(message, "Position Out of Limits", buttons=["OK"])
            logger.warning(f"Position command rejected: Az: {self._gun_azimuth}, El: {self._gun_elevation} is outside limits")
            return False
        
        if not (self.pan_left_limit <= x <= self.pan_right_limit and self.tilt_bottom_limit <= y <= self.tilt_top_limit):
            message = (f"Requested position (Az: {x:.2f}, El: {y:.2f}) is outside the allowed limits.\n\n"
                    f"Azimuth: between {self.pan_left_limit} and {self.pan_right_limit}\n"
                    f"Elevation: between {self.tilt_bottom_limit} and {self.tilt_top_limit}")
            
            # Show warning with "OK" button
            self.notification_overlay.show_warning(message, "Position Out of Limits", buttons=["OK"])
            logger.warning(f"Position command rejected: Az: {x}, El: {y} is outside limits")
            return False

        # logger.critical("_______________________________________________________________________________")
        # logger.critical(f"self.pan_left_limit:{self.pan_left_limit},self.pan_right_limit:{self.pan_right_limit},self.tilt_bottom_limit:{self.tilt_bottom_limit},self.tilt_top_limit:{self.tilt_top_limit}")
        target_x = x
    
        # For NSVT/BMG systems, we need to invert the tilt value before sending to the controller
        # because the controller already inverts it internally
        if self.system_type in ['BMG', 'NSVT']: 
            target_y = -y  # Invert for these system types
        else:
            target_y = y   # No inversion for RCWS
        
        pan_speed = self.getPanSpeed()
        tilt_speed = self.getTiltSpeed()
        logger.info(f"Moving Gun to ({x}, {y}) with speeds (Pan: {pan_speed}, Tilt: {tilt_speed})")
        logger.info(f"Sending adjusted values to controller: ({target_x}, {target_y})")
        self.gun_controller.move(target_x, target_y, pan_speed, tilt_speed)
        return True

    def click_window_slot(self, who_click):
        logger.debug(f"{who_click} window is clicked")

    def toggleStabilization(self):
        """
        Toggles the stabilization system on/off using only the gun controller.
        """
        try:
            self.stabilization_active = not self.stabilization_active
            
            if self.stabilization_active:
                # Start stabilization
                success = self.gun_controller.start_stab()
                if success:
                    logger.info("Stabilization activated")
                else:
                    self.stabilization_active = False
                    logger.error("Failed to activate stabilization")
            else:
                # Stop stabilization
                success = self.gun_controller.stop_stab()
                if success:
                    logger.info("Stabilization deactivated")
                else:
                    self.stabilization_active = True
                    logger.error("Failed to deactivate stabilization")
                    
            # Update button appearance
            for button in self.findChildren(QPushButton):
                if button.text() == "Stab ON/OFF":
                    button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;" if self.stabilization_active else "")
                    
        except Exception as e:
            logger.error(f"Error toggling stabilization: {str(e)}")
            self.stabilization_active = not self.stabilization_active  # Revert state
        
    def start_track(self, tracking_mode):
        if not self.connected:
            return
        self.ipc_object.enable_track(True, tracking_mode)
        if tracking_mode == 2:
            self.gun_controller.start_track(2)
        else:
            self.gun_controller.start_track(1)

        if self.currentindex:
            self.ipc_object.start_track(VideoType_e.VT_LIGHT)
        else:
            self.ipc_object.start_track(VideoType_e.VT_IRD)
        
        for button in self.findChildren(QPushButton):
            if button.text() == "Track ON/OFF":
                button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;")

    def stop_track(self):
        if not self.connected:
            return
        self.ipc_object.enable_track(False, tracking_mode=None)
        self.gun_controller.stop_track()
        if self.currentindex:
            self.ipc_object.stop_track(VideoType_e.VT_LIGHT)
        else:
            self.ipc_object.stop_track(VideoType_e.VT_IRD)
        
        for button in self.findChildren(QPushButton):
            if button.text() == "Track ON/OFF":
                button.setStyleSheet("")
    
    def toggle_track(self):
        if self.tracking:
            self.stop_track()
            # self.lrf_timer.stop()
        else:
            self.start_track(tracking_mode=0)
            # self.lrf_timer.start(2000)
        self.tracking = not self.tracking

        # # Update button appearance
        # for button in self.findChildren(QPushButton):
        #     if button.text() == "Track ON/OFF":
        #         button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;" if self.tracking else "")
                    
    
    def toggle_touch_to_aim(self):
        if self.touch_to_aim_started:
            self.stop_track()
        else:
            self.start_track(tracking_mode=2)
        self.touch_to_aim_started = not self.touch_to_aim_started
        # Update button appearance
        for button in self.findChildren(QPushButton):
            if button.text() == "Touch aim":
                button.setStyleSheet("background-color:rgb(120, 243, 38); color: white;" if self.touch_to_aim_started else "")
                    
        

    def update_taboo_visualizer(self):
        """Update the taboo visualizer with current gun position"""
        if hasattr(self, 'config_screen') and hasattr(self, '_gun_azimuth'):
            self.config_screen.update_current_position(self._gun_azimuth)

    def set_angle_gun(self, x=None, y=None):
        if x is not None and y is not None:
            if self.system_type in ['BMG', 'NSVT']:
                self._gun_azimuth = x
                self._gun_elevation = -y
            elif self.system_type == 'RCWS':
                self._gun_azimuth = x
                self._gun_elevation = y
            # logger.critical(f"Pan:{self._gun_azimuth}, Tilt:{self._gun_elevation}")
        # Set the text values with the updated data
        
        self.gunAzimuth.setText(angle_format(self._gun_azimuth))  # Ensure it stays within [0, 360)
        self.gunElevation.setText(angle_format(self._gun_elevation))

        self.update_taboo_visualizer()
        # self.set_angle_delta()

    def set_lrf(self, x=None, y=None):
        if x is not None and y is not None:
            self._lrf_dist_updated = time.time()
            self._lrf_dist_1 = x
            self._lrf_dist_2 = y
    
    # def selfCheck(self):
    #     return
    #     tilt = 90
    #     tilt_inc = -5
    #     self.position_gun(0, tilt)
    #     time.sleep(2)
    #     for pan in range(0, 360, 5):
    #         self.position_gun(pan, tilt)
    #         self.position_cam(pan, tilt)
    #         tilt += tilt_inc
    #         if tilt < -30:
    #             tilt_inc = 5
    #         if tilt > 90:
    #             tilt_inc = -5
    #         time.sleep(0.5)
    #     self.position_gun(0, 0)
    #     self.position_cam(0, 0)

    def selfCheck(self):
        self.scan_running = not self.scan_running
        if self.scan_running == True:
            self.scan_thread = threading.Thread(target=self.scan)
            self.scan_thread.start()

    def scan(self):
        loop_positions = [(0, 0), (-20, 0), (-20, -15), (20, -15), (20, 0)]
        self.gun_speed = 20
        while self.scan_running:
            for i in range(len(loop_positions)):
                self.position_gun(loop_positions[i][0], loop_positions[i][1])
                logger.info(f"Gun moved to position: Azimuth {loop_positions[i][0]}, Elevation {loop_positions[i][1]}")
                time.sleep(4)
                if not self.scan_running:
                    self.gun_speed = 50
                    break
        self.scan_thread.join()

    def set_angle_cam(self, x=None, y=None):
        if x is not None and y is not None:
            self._cam_azimuth = x
            self._cam_elevation = y
        # # Set the text values with the updated data
        # self.camAzimuth.setText(angle_format(self._cam_azimuth))  # Ensure it stays within [0, 360)
        # self.camElevation.setText(angle_format(self._cam_elevation))
        self.set_angle_delta()

    def set_angle_delta(self):
        self._delta_azimuth = self._cam_azimuth - self._gun_azimuth
        self._delta_elevation = self._cam_elevation - self._gun_elevation
        # self.deltaAzimuth.setText(angle_format(self._delta_azimuth))
        # self.deltaElevation.setText(angle_format(self._delta_elevation))

    def originalButtonsState(self, screen_width):
        left_buttons = {
            "Menu": self.toggleButtonsState,
            "D/N": self.switchClicked,
            "Black Hot": self.setBlackHot,
            "White Hot": self.setWhiteHot,
            "Stab ON/OFF": self.toggleStabilization,
            # "RCWS Vid": self.rcwsClicked,
            "Config": self.configClicked,
            "Diagnose": self.diagnoseClicked,
        }
        for i, f in left_buttons.items():
            if self.get_user_role() not in [ROLES.ADMIN, ROLES.PROGRAMMER]:
                if i in ['Config']:
                    continue
            left_button = (
                QPushButton(i) if i in ["Menu", "Config", "Diagnose"] or type(f) == tuple else LQPushButton(i)
            )
            left_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            # left_button.setMinimumWidth(int(screen_width * 0.1))
            left_button.setMaximumWidth(int(screen_width * 0.1))
            if f:
                if type(f) == tuple:
                    left_button.pressed.connect(f[0])
                    left_button.released.connect(f[1])
                else:
                    left_button.clicked.connect(f)
            self.leftButtonsLayout1.addWidget(left_button)

        right_buttons = {
            "Track ON/OFF": self.toggle_track,
            "Touch aim": self.toggle_touch_to_aim,
            # "Track Start": self.start_track,
            # "Track Stop": self.stop_track,
            "Zoom +": (
                lambda: self.control_camera(CameraType_e.CCT_ZOOM_IN, True),
                lambda: self.control_camera(CameraType_e.CCT_ZOOM_IN, False),
            ),
            "Zoom -": (
                lambda: self.control_camera(CameraType_e.CCT_ZOOM_OUT, True),
                lambda: self.control_camera(CameraType_e.CCT_ZOOM_OUT, False),
            ),
            "Focus +": (
                lambda: self.control_camera(CameraType_e.CCT_FOCUS_FAR, True),
                lambda: self.control_camera(CameraType_e.CCT_FOCUS_FAR, False),
            ),
            "Focus -": (
                lambda: self.control_camera(CameraType_e.CCT_FOCUS_NEAR, True),
                lambda: self.control_camera(CameraType_e.CCT_FOCUS_NEAR, False),
            ),
            "CAM B/C": self.toggleCamBCMenu,
            # "Iris +": (
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, True),
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, False),
            # ),
            # "Iris -": (
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, True),
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, False),
            # ),
        }

        for i, f in right_buttons.items():
            right_button = QPushButton(i)
            # right_button.setMinimumWidth(int(screen_width * 0.1))
            right_button.setMaximumWidth(int(screen_width * 0.1))
            right_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            if f:
                if type(f) == tuple:
                    right_button.pressed.connect(f[0])
                    right_button.released.connect(f[1])
                else:
                    right_button.clicked.connect(f)
            self.rightButtonsLayout1.addWidget(right_button)

    def newButtonsState(self, screen_width):
        left_buttons = {
            "Menu": self.toggleButtonsState,
            # "Bal Line": self.toggle_bal_line,
            # "Send Offsets": self.send_track_offsets,
            "Lay GPS": self.lay_on_gps,
            "Fire Detection": self.toggle_fire_detection,
            # "Bal": self.toggle_ballistics,
            "Bal": self.toggleBal if self.system_type == 'RCWS' else self.nsvt_ballistics,
            "Bal-": self.toggle_range_sender,
            # "Brightness +": (
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, True),
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, False),
            # ),
            # "Brightness -": (
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, True),
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, False),
            # ),
            # "Contrast +": (
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, True),
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, False),
            # ),
            # "Contrast -": (
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, True),
            #     lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, False),
            # ),
            "Zero Gun": lambda: self.position_gun(0, 0),
            # "Zero Cam": lambda: self.position_cam(0, 0),
        }
        for i, f in left_buttons.items():
            left_button = (
                QPushButton(i) if i == "Menu" or type(f) == tuple else LQPushButton(i)
            )
            left_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            # left_button.setMinimumWidth(int(screen_width * 0.1))
            left_button.setMaximumWidth(int(screen_width * 0.1))
            if f:
                if type(f) == tuple:
                    left_button.pressed.connect(f[0])
                    left_button.released.connect(f[1])
                else:
                    left_button.clicked.connect(f)
            self.leftButtonsLayout2.addWidget(left_button)

        right_buttons = {
            # "POS": self.make_move,
            # "CAM-POS": self.make_move_cam,
            "LAY": self.make_move_gun,
            "Pre-Targets": self.toggle_pre_registration_mode,
            "View Targets": self.show_targets_dialog,
            # "PTZ+": lambda: self.changeSpeedCam(1),
            # "PTZ-": lambda: self.changeSpeedCam(-1),
            "PTZG+": lambda: self.changeSpeedGun(1),
            "PTZG-": lambda: self.changeSpeedGun(-1),
            "LogOut": self.logout,
        }
        layout = QHBoxLayout()
        self.x_in = CustomLineEdit(self)
        self.y_in = CustomLineEdit(self)
        self.x_in.setStyleSheet("background-color: black;")
        self.y_in.setStyleSheet("background-color: black;")

        self.x_in.returnPressed.connect(self.toggle_focus)
        self.y_in.returnPressed.connect(self.toggle_focus)
        layout.addWidget(self.x_in)
        layout.addWidget(self.y_in)
        self.x_in.setMaximumWidth(int(screen_width * 0.035))
        self.y_in.setMaximumWidth(int(screen_width * 0.035))
        self.x_in.setMinimumHeight(40)
        self.y_in.setMinimumHeight(40)

        self.rightButtonsLayout2.addLayout(layout)
        for i, f in right_buttons.items():
            right_button = QPushButton(i) if i == "LogOut" else LQPushButton(i)
            # right_button.setMinimumWidth(int(screen_width * 0.1))
            right_button.setMaximumWidth(int(screen_width * 0.1))
            right_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            if f:
                if type(f) == tuple:
                    right_button.pressed.connect(f[0])
                    right_button.released.connect(f[1])
                else:
                    right_button.clicked.connect(f)
            self.rightButtonsLayout2.addWidget(right_button)
    
    def toggle_focus(self):
        if self.current_focus == 1:
            self.x_in.setFocus()
            self.current_focus = 2
        else:
            self.y_in.setFocus()
            self.current_focus = 1

    def show_targets_dialog(self):
        if not self.targets_dialog:
            self.targets_dialog = TargetsDialog(self)
        self.targets_dialog.load_targets()  # Reload targets each time dialog is shown
        self.targets_dialog.show()

    def toggleCamBCMenu(self):
        current_index = self.leftButtonsLayoutStack.currentIndex()
        if current_index != 2:  # If not already in CAM B/C menu
            self.leftButtonsLayoutStack.setCurrentIndex(2)
            self.rightButtonsLayoutStack.setCurrentIndex(2)
            print("Switched to CAM B/C menu")
        else:
            self.leftButtonsLayoutStack.setCurrentIndex(0)  # Go back to main menu
            self.rightButtonsLayoutStack.setCurrentIndex(0)
            print("Switched back to main menu")

    def camBCButtonsState(self, screen_width):
        left_buttons = {
            "Brightness +": (
                lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, True),
                lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, False),
            ),
            "Brightness -": (
                lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, True),
                lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, False),
            ),
            "CAM B/C": self.toggleCamBCMenu,  # Add CAM B/C button to left side
        }

        for i, f in left_buttons.items():
            left_button = LQPushButton(i)
            left_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            left_button.setMaximumWidth(int(screen_width * 0.1))
            if f:
                if isinstance(f, tuple):
                    left_button.pressed.connect(f[0])
                    left_button.released.connect(f[1])
                else:
                    left_button.clicked.connect(f)
            self.leftButtonsLayout3.addWidget(left_button)

        right_buttons = {
            "Contrast +": (
                lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, True),
                lambda: self.control_camera(CameraType_e.CCT_IRIS_OPEN, False),
            ),
            "Contrast -": (
                lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, True),
                lambda: self.control_camera(CameraType_e.CCT_IRIS_CLOSE, False),
            ),
            "CAM B/C": self.toggleCamBCMenu,  # Keep CAM B/C button on right side
        }

        for i, f in right_buttons.items():
            right_button = LQPushButton(i)
            right_button.setMaximumWidth(int(screen_width * 0.1))
            right_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            if f:
                if isinstance(f, tuple):
                    right_button.pressed.connect(f[0])
                    right_button.released.connect(f[1])
                else:
                    right_button.clicked.connect(f)
            self.rightButtonsLayout3.addWidget(right_button)

    def switchClicked(self):
        currentIndex = self.stackedWidget.currentIndex()
        currentIndex = 1 if currentIndex == 0 else 0
        self.currentindex = currentIndex
        self.stackedWidget.setCurrentIndex(currentIndex)
    
    def setWhiteHot(self):
        """Set thermal camera to white hot mode"""
        if self.connected:
            logger.info("Setting thermal camera to White Hot mode")
            self.ipc_object.set_thermal_mode(0, VideoType_e.VT_IRD)

    def setBlackHot(self):
        """Set thermal camera to black hot mode"""
        if self.connected:
            logger.info("Setting thermal camera to Black Hot mode")
            self.ipc_object.set_thermal_mode(1, VideoType_e.VT_IRD)

    def toggleButtonsState(self):
        """
        Handle menu toggle with diagnostics timer check
        """
        # Explicitly stop diagnostics timer when changing menu states
        self.stop_diagnostics_timer()
        
        currentIndex = self.leftButtonsLayoutStack.currentIndex()
        newIndex = 1 - currentIndex
        self.leftButtonsLayoutStack.setCurrentIndex(newIndex)
        self.rightButtonsLayoutStack.setCurrentIndex(newIndex)

    def switchClicked(self):
        self.stop_diagnostics_timer()
        currentIndex = self.stackedWidget.currentIndex()
        currentIndex = 1 if currentIndex == 0 else 0
        self.currentindex = currentIndex
        self.stackedWidget.setCurrentIndex(currentIndex)

    def get_user_role(self):
        return self.login_dialog and self.login_dialog.user and self.login_dialog.user['role'] 

    def settingsClicked(self):
        if self.get_user_role() in [ROLES.ADMIN, ROLES.PROGRAMMER]:
            currentIndex = self.stackedWidget.currentIndex()
            currentIndex = 3 if currentIndex == 2 else 2
        else:
            currentIndex = 3
        self.stackedWidget.setCurrentIndex(currentIndex)

    def configClicked(self):
        self.stop_diagnostics_timer()
        self.stackedWidget.setCurrentIndex(2)

    # def rcwsClicked(self):
    #     self.stackedWidget.setCurrentIndex(4)

    def diagnoseClicked(self):
        """
        Show the diagnose screen and initiate diagnostic data updates ONLY when the button is clicked
        """
        # First set the current index to show the diagnose screen
        self.stackedWidget.setCurrentIndex(3)
        
        # ONLY request diagnostics when button is explicitly clicked
        if hasattr(self, 'gun_controller') and self.gun_controller.connected:
            # Request initial diagnostics
            logger.info("Requesting initial diagnostics data after Diagnose button click")
            self.gun_controller.request_diagnostics()
            
            # Create timer if it doesn't exist yet
            if not hasattr(self, 'diagnostics_timer'):
                self.diagnostics_timer = QTimer(self)
                self.diagnostics_timer.timeout.connect(self.update_diagnostics)
            
            # Start the timer only if we're actually viewing diagnostics
            if not self.diagnostics_timer.isActive() and self.stackedWidget.currentIndex() == 3:
                self.diagnostics_timer.start(5000)  # Update every 5 seconds
                logger.info("Diagnostics timer started - updating every 5 seconds")
        else:
            logger.warning("Cannot request diagnostics: Gun controller not connected")

    def start_diagnostics_updates(self):
        """
        Request initial diagnostics data and start periodic updates
        """
        if hasattr(self, 'gun_controller') and self.gun_controller.connected:
            # Request initial diagnostics
            logger.info("Requesting initial diagnostics data")
            self.gun_controller.request_diagnostics()
            
            # Start the timer if not already running
            if not hasattr(self, 'diagnostics_timer'):
                self.diagnostics_timer = QTimer(self)
                self.diagnostics_timer.timeout.connect(self.update_diagnostics)
            
            if not self.diagnostics_timer.isActive():
                self.diagnostics_timer.start(5000)  # Update every 5 seconds
                logger.info("Diagnostics timer started - updating every 5 seconds")
        else:
            logger.warning("Cannot request diagnostics: Gun controller not connected")

    def update_diagnostics(self):
        """
        Request updated diagnostics data from the gun controller ONLY if still on diagnostics tab
        """
        current_index = self.stackedWidget.currentIndex()
        
        # ONLY update if we're actually on the diagnostics screen
        if current_index == 3 and hasattr(self, 'gun_controller') and self.gun_controller.connected:
            logger.info("Requesting updated diagnostics data (timer-based update)")
            self.gun_controller.request_diagnostics()
        else:
            # Stop the timer if we're not on the diagnostics screen
            if hasattr(self, 'diagnostics_timer') and self.diagnostics_timer.isActive():
                self.diagnostics_timer.stop()
                logger.info("Diagnostics timer stopped - not on diagnostics screen")

    def stop_diagnostics_timer(self):
        """Explicitly stop the diagnostics timer if it's running"""
        if hasattr(self, 'diagnostics_timer') and self.diagnostics_timer.isActive():
            self.diagnostics_timer.stop()
            logger.info("Diagnostics timer explicitly stopped")

    def changeSpeedGun(self, val):
        self.gun_speed = self.gun_speed + val
        self.gun_speed = max(0, min(self.gun_speed, 80))
        self.gunSpeed.setText(str(self.gun_speed))

    def getPanSpeed(self):
        if self.gun_speed == 0:
            return 0
        elif self.gun_speed == 1:
            return 0.03
        return min(self.gun_speed, 80)

    def getTiltSpeed(self):
        if self.gun_speed == 0:
            return 0
        elif self.gun_speed == 1:
            return 0.03
        return min(self.gun_speed, 60)

    def changeSpeedCam(self, val):
        self.cam_speed = self.cam_speed + val
        self.cam_speed = max(0, min(self.cam_speed, 60))
        self.camSpeed.setText(str(self.cam_speed))

    def closeEvent(self, event):
        """Handle proper shutdown when the window is closed"""
        # Stop all threads before shutdown
        if hasattr(self, 'castle_listener'):
            # Log shutdown if logging is active
            if self.castle_listener.running and hasattr(self.castle_listener, 'log_message'):
                self.castle_listener.log_message('critical', 
                    "APPLICATION SHUTDOWN - Stopping CASTLE listener", {
                        'shutdown_reason': 'application_close',
                        'fire_detection_was_active': self.fire_detection_active
                    })
            
            # Stop the listener
            self.castle_listener.stop()
            logger.info("CASTLE listener stopped")
        
        if hasattr(self, 'gunshot_monitor_timer'):
            self.gunshot_monitor_timer.stop()
        if hasattr(self, 'diagnostics_timer') and self.diagnostics_timer.isActive():
            self.diagnostics_timer.stop()
            logger.info("Diagnostics timer stopped during application close")
        
        if hasattr(self, 'program') and self.program:
            # Stop the timer first
            if hasattr(self.program, 'timer'):
                self.program.timer.stop()
            
            # Set a flag to stop the thread's main loop
            self.program.running = False
            
            # Wait for thread to finish (with timeout)
            if self.program.isRunning():
                self.program.wait(1000)  # Wait up to 1 second
                if self.program.isRunning():
                    self.program.terminate()
        
        # Now properly disconnect the controller
        if hasattr(self, 'gun_controller'):
            self.gun_controller.exit()
        
        # Accept the close event after cleanup
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    style_file = open(get_asset_path("styles.qss"), "r")
    style_content = style_file.read()
    app.setStyleSheet(style_content)

    # 🔥 ADD THESE LINES FOR TOUCH SUPPORT
    app.setAttribute(Qt.AA_SynthesizeTouchForUnhandledMouseEvents, False)
    app.setAttribute(Qt.AA_SynthesizeMouseForUnhandledTouchEvents, False)

    style_file.close()
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec_())