import os
os.environ["SDL_VIDEO_ALLOW_SCREENSAVER"] = "1"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
os.environ["SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR"] = "0"

import sys
import pygame
from pygame.locals import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

class JoyStick:
    def __init__(self, id):
        self.id = id
        self.joy = pygame.joystick.Joystick(id)
        self.name = self.joy.get_name()
        self.joy.init()
        self.numaxes = self.joy.get_numaxes()
        self.numballs = self.joy.get_numballs()
        self.numbuttons = self.joy.get_numbuttons()
        self.numhats = self.joy.get_numhats()

        self.axis = [0] * self.numaxes
        self.ball = [0] * self.numballs
        self.button = [0] * self.numbuttons
        self.hat = [0] * self.numhats

    def update(self):
        for i in range(self.numaxes):
            self.axis[i] = self.joy.get_axis(i)

class JoyStickThread4(QThread):
    error_signal = pyqtSignal(str)
    change_axis_signal = pyqtSignal(float, float, float, float)
    button_signal = pyqtSignal(str, int, int)

    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        pygame.init()
        pygame.event.set_blocked(
            (QUIT, ACTIVEEVENT, KEYDOWN, KEYUP, MOUSEMOTION, MOUSEBUTTONUP, MOUSEBUTTONDOWN,
             JOYBALLMOTION, JOYHATMOTION, VIDEORESIZE, VIDEOEXPOSE, USEREVENT)
        )
        self.joycount = pygame.joystick.get_count()
        if self.joycount == 0:
            pygame.quit()
            self.error_signal.emit("This program only works with at least one joystick plugged in. No joysticks were detected.")
            return
        self.joy = [JoyStick(i) for i in range(self.joycount)]

        # Set up a timer to emit axis values regularly
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.emit_axis_values)
        self.timer.start(16)  # Emit values every 50 ms

    def emit_axis_values(self):
        for joy in self.joy:
            joy.update()
            self.change_axis_signal.emit(*joy.axis)

    def run(self):
        if self.joycount == 0:
            self.error_signal.emit("This program only works with at least one joystick plugged in. No joysticks were detected.")
            return
        while self.running:
            for event in [pygame.event.wait()] + pygame.event.get():
                if event.type in (JOYBUTTONUP, JOYBUTTONDOWN):
                    joy_name = self.joy[event.joy].name
                    status = 1 if event.type == JOYBUTTONDOWN else 0
                    self.joy[event.joy].button[event.button] = status
                    self.button_signal.emit(joy_name, event.button, status)

# import os
# import sys
# import pygame
# from pygame.locals import *
# from PyQt5.QtCore import QThread, pyqtSignal, QTimer

# os.environ["SDL_VIDEO_ALLOW_SCREENSAVER"] = "1"
# os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
# os.environ["SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR"] = "0"

# class JoyStick:
#     def __init__(self, id):
#         self.id = id
#         self.joy = pygame.joystick.Joystick(id)
#         self.name = self.joy.get_name()
#         self.joy.init()
#         self.numaxes = self.joy.get_numaxes()
#         self.numballs = self.joy.get_numballs()
#         self.numbuttons = self.joy.get_numbuttons()
#         self.numhats = self.joy.get_numhats()

#         self.axis = [0] * max(5, self.numaxes)  # Ensure at least 5 axes
#         self.ball = [0] * self.numballs
#         self.button = [0] * self.numbuttons
#         self.hat = [0] * self.numhats

#     def update(self):
#         for i in range(self.numaxes):
#             self.axis[i] = self.joy.get_axis(i)

class JoyStickThread5(QThread):
    error_signal = pyqtSignal(str)
    change_axis_signal = pyqtSignal(float, float, float, float, float)  # 5 axis values
    button_signal = pyqtSignal(str, int, int)  # joy_name, button_id, status

    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        pygame.init()
        pygame.event.set_blocked(
            (QUIT, ACTIVEEVENT, KEYDOWN, KEYUP, MOUSEMOTION, MOUSEBUTTONUP, MOUSEBUTTONDOWN,
             JOYBALLMOTION, JOYHATMOTION, VIDEORESIZE, VIDEOEXPOSE, USEREVENT)
        )   
        self.joycount = pygame.joystick.get_count()
        if self.joycount == 0:
            pygame.quit()
            self.error_signal.emit("This program only works with at least one joystick plugged in. No joysticks were detected.")
            return
        self.joy = [JoyStick(i) for i in range(self.joycount)]

        # Set up a timer to emit axis values regularly
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.emit_axis_values)
        self.timer.start(16)  # Emit values every 50 ms

    def emit_axis_values(self):
        for joy in self.joy:
            joy.update()
            self.change_axis_signal.emit(*joy.axis[:5])  # Emit 5 axis values, padded with 0 if necessary

    def run(self):
        if self.joycount == 0:
            self.error_signal.emit("This program only works with at least one joystick plugged in. No joysticks were detected.")
            return
        while self.running:
            for event in [pygame.event.wait()] + pygame.event.get():
                if event.type == JOYAXISMOTION:
                    joy = self.joy[event.joy]
                    if event.axis < 5:  # Update for up to 5 axes
                        joy.axis[event.axis] = event.value
                        self.change_axis_signal.emit(*joy.axis[:5])
                elif event.type in (JOYBUTTONUP, JOYBUTTONDOWN):
                    joy_name = self.joy[event.joy].name
                    status = 1 if event.type == JOYBUTTONDOWN else 0
                    self.joy[event.joy].button[event.button] = status
                    self.button_signal.emit(joy_name, event.button, status)

    def get_joy(self):
        return self.joy

# import os
# os.environ["SDL_VIDEO_ALLOW_SCREENSAVER"] = "1"
# os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
# os.environ["SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR"] = "0"

# import sys
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication

# from pygame.locals import *
# from PyQt5.QtCore import QThread, pyqtSignal, QTimer



class SimulatedJoyStick:
    def __init__(self):
        self.name = "Simulated Joystick"
        self.numaxes = 4
        self.numbuttons = 8
        self.axis = [0] * self.numaxes
        self.button = [0] * self.numbuttons

    def update(self):
        pass  # No need to update, as we'll set values directly

class JoyStickThread0(QThread):
    error_signal = pyqtSignal(str)
    change_axis_signal = pyqtSignal(float, float, float, float)
    button_signal = pyqtSignal(str, int, int)

    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        self.joy = SimulatedJoyStick()
        
        # Set up a timer to emit axis values regularly
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.emit_axis_values)
        self.timer.start(16)  # Emit values every 50 ms

        # Install event filter to capture key events
        QApplication.instance().installEventFilter(self)

    def emit_axis_values(self):
        self.change_axis_signal.emit(*self.joy.axis)

    def run(self):
        # This method is now mostly empty as we're not using pygame anymore
        while self.running:
            self.msleep(100)  # Sleep to prevent high CPU usage

    def eventFilter(self, obj, event):
        if isinstance(event, QKeyEvent):
            if event.type() == QKeyEvent.KeyPress:
                self.handle_key_press(event.key())
            elif event.type() == QKeyEvent.KeyRelease:
                self.handle_key_release(event.key())
        return False

    # def handle_key_press(self, key):
    #     # Map keys to joystick axes and buttons
    #     if key == Qt.Key_W:
    #         self.joy.axis[1] = -1  # Up
    #     elif key == Qt.Key_S:
    #         self.joy.axis[1] = 1   # Down
    #     elif key == Qt.Key_A:
    #         self.joy.axis[0] = -1  # Left
    #     elif key == Qt.Key_D:
    #         self.joy.axis[0] = 1   # Right
    #     elif key == Qt.Key_Space:
    #         self.joy.button[0] = 1  # Button 0 (e.g., trigger)
    #         self.button_signal.emit(self.joy.name, 0, 1)
    #     elif key == Qt.Key_B:
    #         self.joy.button[1] = 1  # Button 1
    #         self.button_signal.emit(self.joy.name, 1, 1)
    #     # Add more key mappings as needed

    # def handle_key_release(self, key):
    #     if key in [Qt.Key_W, Qt.Key_S]:
    #         self.joy.axis[1] = 0
    #     elif key in [Qt.Key_A, Qt.Key_D]:
    #         self.joy.axis[0] = 0
    #     elif key == Qt.Key_Space:
    #         self.joy.button[0] = 0
    #         self.button_signal.emit(self.joy.name, 0, 0)
    #     elif key == Qt.Key_B:
    #         self.joy.button[1] = 0
    #         self.button_signal.emit(self.joy.name, 1, 0)
    #     # Add more key release handlers as needed

    def handle_key_press(self, key):
        # Axis Up
        if key in [Qt.Key_W, Qt.Key_Up]:
            self.joy.axis[1] = -1
        # Axis Down
        elif key in [Qt.Key_S, Qt.Key_Down]:
            self.joy.axis[1] = 1
        # Axis Left
        elif key in [Qt.Key_A, Qt.Key_Period]:
            self.joy.axis[0] = -1
        # Axis Right
        elif key in [Qt.Key_D, Qt.Key_Minus]:
            self.joy.axis[0] = 1
        # Button 0
        elif key == Qt.Key_Space:
            self.joy.button[0] = 1
            self.button_signal.emit(self.joy.name, 0, 1)
        # Button 1
        elif key == Qt.Key_B:
            self.joy.button[1] = 1
            self.button_signal.emit(self.joy.name, 1, 1)
        # Add more mappings if needed
    
    def handle_key_release(self, key):
        if key in [Qt.Key_W, Qt.Key_S, Qt.Key_Up, Qt.Key_Down]:
            self.joy.axis[1] = 0
        elif key in [Qt.Key_A, Qt.Key_D, Qt.Key_Period, Qt.Key_Minus]:
            self.joy.axis[0] = 0
        elif key == Qt.Key_Space:
            self.joy.button[0] = 0
            self.button_signal.emit(self.joy.name, 0, 0)
        elif key == Qt.Key_B:
            self.joy.button[1] = 0
            self.button_signal.emit(self.joy.name, 1, 0)
