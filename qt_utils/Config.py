import sys
import math
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QVBoxLayout, QFormLayout, QPushButton, QMessageBox,
    QHBoxLayout, QSlider, QCheckBox, QRadioButton, QButtonGroup, QComboBox, QSizePolicy, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal, QRegExp
from PyQt5.QtGui import QFont, QColor, QPen, QPainter, QDoubleValidator, QIntValidator, QRegExpValidator

from configparser_crypt import ConfigParserCrypt
import json
from utils.system_limits import get_system_limits, SYSTEM_LIMITS, DEFAULT_LIMITS, HELP_TEXT

# from utils.LogHelper import CustomLogger

# logger = CustomLogger()

config = ConfigParserCrypt()
config.aes_key = b'\xfa\xc1\x1e\xdf6\xa9\xad\xc4h\xeb\xc2*\xd9l\xb0\xea \xc6?\x1bq\x85\xc4\x1c\x80\x1f\x05\x8b\xc3\xda\xdeB'
config.read_encrypted('config.ini')

class TabooVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pan_left = -90
        self.pan_right = 90
        self.current_position = 0
        self.taboo_enabled = True
        self.setFixedSize(140, 140)
        self.setToolTip("Green arc: Allowed movement range\nRed arc: Forbidden movement range\nRed line: Current position")

    def normalize(self, angle):
        return (angle + 360) % 360
        
    def clockwise_angle(self, a1, a2):
        a1_norm = self.normalize(a1)
        a2_norm = self.normalize(a2)
        return (a2_norm - a1_norm) % 360
        
    def is_between_cw(self, limit1, limit2, current):
        limit1 = self.normalize(limit1)
        limit2 = self.normalize(limit2)
        current = self.normalize(current)
        
        if limit1 < limit2:
            return limit1 <= current <= limit2
        else:
            return current >= limit1 or current <= limit2

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the circle
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(center_x, center_y) - 5

        # Draw outer circle with a bolder line
        pen = QPen(Qt.black, 3)  # Increased thickness from 2 to 3
        painter.setPen(pen)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # Create bold font for all text
        label_font = QFont()
        label_font.setPointSize(9)
        label_font.setBold(True)
        painter.setFont(label_font)
        
        # Draw cardinal direction markers with better alignment
        # North (0°)
        painter.setPen(QPen(Qt.black, 2))  # Make text darker/bolder
        painter.drawText(center_x - 7, center_y - radius + 15, "0°")
        
        # East (90°)
        painter.drawText(center_x + radius - 25, center_y + 5, "90°")
        
        # South (180°)
        painter.drawText(center_x - 12, center_y + radius - 5, "180°")
        
        # West (-90°)
        painter.drawText(center_x - radius + 5, center_y + 5, "-90°")

        # Check if current position is within the allowed range using your exact logic
        is_in_range = self.is_between_cw(self.pan_left, self.pan_right, self.current_position)
        
        # Set pen and brush colors based on if gun is in range
        # if self.taboo_enabled:
        if is_in_range:
            # Gun is in range - show green
            pen_color = QColor(0, 150, 0, 200)
            brush_color = QColor(0, 255, 0, 50)
        else:
            # Gun is out of range - show red
            pen_color = QColor(150, 0, 0, 200)
            brush_color = QColor(255, 0, 0, 50)
        # else:
        #     # Taboo disabled - use light green
        #     pen_color = QColor(0, 150, 0, 100)
        #     brush_color = QColor(0, 255, 0, 20)
            
        painter.setPen(QPen(pen_color, 3))  # Increased thickness from 2 to 3
        painter.setBrush(brush_color)
        
        # CORRECTED APPROACH: Draw the arc directly using angles in our system
        # Convert to Qt angles
        qt_left = (90 - self.pan_left) % 360   # Counterclockwise from 3 o'clock
        qt_right = (90 - self.pan_right) % 360 # Counterclockwise from 3 o'clock
        
        # Calculate span - always go counterclockwise in Qt from start to end
        start_angle = qt_right  # Start at right boundary in Qt
        end_angle = qt_left     # End at left boundary in Qt
        
        # Ensure we get the correct span (might need to add 360)
        if end_angle <= start_angle:
            end_angle += 360
        
        span_angle = end_angle - start_angle
        
        # QT uses 16th of a degree for angles
        start_angle_16 = int(start_angle * 16)
        span_angle_16 = int(span_angle * 16)
        
        # Draw arc
        rect = QRect(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawPie(rect, start_angle_16, span_angle_16)
        
        # Draw only the two boundary lines with increased thickness
        # Left boundary line
        angle_rad = math.radians(self.pan_left)
        # Convert to Qt coordinate system
        angle_rad = math.pi/2 - angle_rad
        x1 = center_x + int(radius * math.cos(angle_rad))
        y1 = center_y - int(radius * math.sin(angle_rad))
        painter.drawLine(center_x, center_y, x1, y1)
        
        # Left boundary label - with better positioning
        boundary_font = QFont()
        boundary_font.setPointSize(8)
        boundary_font.setBold(True)
        painter.setFont(boundary_font)
        
        # # Calculate offset for left boundary label based on angle
        # left_angle = math.degrees(angle_rad)
        # if 0 <= left_angle < 90:  # First quadrant
        #     left_offset_x = 5
        #     left_offset_y = -10
        # elif 90 <= left_angle < 180:  # Second quadrant
        #     left_offset_x = -30
        #     left_offset_y = -10
        # elif 180 <= left_angle < 270:  # Third quadrant
        #     left_offset_x = -30
        #     left_offset_y = 15
        # else:  # Fourth quadrant
        #     left_offset_x = 5
        #     left_offset_y = 15
            
        # painter.drawText(x1 + left_offset_x, y1 + left_offset_y, f"{self.pan_left}°")
        
        # Right boundary line
        angle_rad = math.radians(self.pan_right)
        # Convert to Qt coordinate system
        angle_rad = math.pi/2 - angle_rad
        x2 = center_x + int(radius * math.cos(angle_rad))
        y2 = center_y - int(radius * math.sin(angle_rad))
        painter.drawLine(center_x, center_y, x2, y2)
        
        # Right boundary label - with better positioning
        # right_angle = math.degrees(angle_rad)
        # if 0 <= right_angle < 90:  # First quadrant
        #     right_offset_x = 5
        #     right_offset_y = -10
        # elif 90 <= right_angle < 180:  # Second quadrant
        #     right_offset_x = -30
        #     right_offset_y = -10
        # elif 180 <= right_angle < 270:  # Third quadrant
        #     right_offset_x = -30
        #     right_offset_y = 15
        # else:  # Fourth quadrant
        #     right_offset_x = 5
        #     right_offset_y = 15
            
        # painter.drawText(x2 + right_offset_x, y2 + right_offset_y, f"{self.pan_right}°")
        
        # Draw current position line in red (always red regardless of in range or not)
        # with increased thickness
        painter.setPen(QPen(Qt.red, 3))  # Increased thickness from 2 to 3
        angle_rad = math.radians(self.current_position)
        # Convert to Qt coordinate system
        angle_rad = math.pi/2 - angle_rad
        x = center_x + int(radius * math.cos(angle_rad))
        y = center_y - int(radius * math.sin(angle_rad))
        painter.drawLine(center_x, center_y, x, y)
        
        # Current position label - with better positioning and bold text
        # curr_angle = math.degrees(angle_rad)
        # if 0 <= curr_angle < 90:  # First quadrant
        #     curr_offset_x = 5
        #     curr_offset_y = -10
        # elif 90 <= curr_angle < 180:  # Second quadrant
        #     curr_offset_x = -30
        #     curr_offset_y = -10
        # elif 180 <= curr_angle < 270:  # Third quadrant
        #     curr_offset_x = -30
        #     curr_offset_y = 15
        # else:  # Fourth quadrant
        #     curr_offset_x = 5
        #     curr_offset_y = 15
            
        # painter.drawText(x + curr_offset_x, y + curr_offset_y, f"{self.current_position}°")

    def update_values(self, pan_left, pan_right, current_position, taboo_enabled):
        """Update the visualization with new values"""
        self.pan_left = pan_left
        self.pan_right = pan_right
        self.current_position = current_position
        self.taboo_enabled = taboo_enabled
        self.update()

class WindDirectionClock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.direction = 0
        self.setFixedSize(300, 150)

        self.direction_text_box = QLineEdit(self)
        self.direction_text_box.setReadOnly(True)
        self.direction_text_box.setFixedSize(70, 35)
        self.direction_text_box.move(5, 58)

        font = QFont()
        font.setPointSize(12)
        self.direction_text_box.setFont(font)
        self.direction_text_box.setAlignment(Qt.AlignCenter)

        self.update_direction_text()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QPen(Qt.black, 3))
        painter.drawEllipse(80, 5, 140, 140)

        for i in range(12):
            angle = i * 30
            painter.save()
            painter.translate(150, 75)
            painter.rotate(angle)
            painter.drawLine(0, -68, 0, -60)
            painter.restore()

        painter.save()
        painter.translate(150, 75)
        painter.rotate(self.direction * 30)
        painter.setPen(QPen(Qt.red, 3))
        painter.drawLine(0, 0, 0, -62)
        painter.drawLine(0, -62, -6, -56)
        painter.drawLine(0, -62, 6, -56)
        painter.restore()

    def mousePressEvent(self, event):
        self.setDirectionFromMouse(event.pos())

    def mouseMoveEvent(self, event):
        self.setDirectionFromMouse(event.pos())

    def setDirectionFromMouse(self, pos):
        center = QPoint(150, 75)
        dx = pos.x() - center.x()
        dy = center.y() - pos.y()
        angle = math.atan2(dy, dx)
        angle = math.degrees(angle)
        angle = 360 - (angle - 90) % 360
        self.direction = int((angle + 15) / 30) % 12
        self.update_direction_text()
        self.update()

    def update_direction_text(self):
        direction_mapping = {
            0: "6-12", 1: "7-1", 2: "8-2", 3: "9-3",
            4: "10-4", 5: "11-5", 6: "12-6", 7: "1-7",
            8: "2-8", 9: "3-9", 10: "4-10", 11: "5-11"
        }
        direction_name = direction_mapping.get(self.direction, "Unknown")
        self.direction_text_box.setText(direction_name)

    def getDirection(self):
        return self.direction

    def setDirection(self, direction):
            self.direction = direction % 12
            self.update_direction_text()
            self.update()

class ConfigScreen(QWidget):
    save_signal = pyqtSignal(str)
    config_saved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = ConfigParserCrypt()
        self.config.aes_key = b'\xfa\xc1\x1e\xdf6\xa9\xad\xc4h\xeb\xc2*\xd9l\xb0\xea \xc6?\x1bq\x85\xc4\x1c\x80\x1f\x05\x8b\xc3\xda\xdeB'
        self.gun_azimuth = 0  # Current position of gun
        self.system_type = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Configuration Screen')
        mainLayout = QVBoxLayout()

        # Initialize settings dictionary (same as before, but without Arc Type)
        self.settings = {
            'Taboo Zone': {
                'type': 'radio',
                'value': 'Off',  # Default value
                'options': ['On', 'Off'],
                'help': 'Enable or disable taboo zone (position limit). When off, default extreme position limits are used.'
            },
            'PAN Left taboo': {
                'type': 'input', 
                'value': 0, 
                'min': -180, 
                'max': 180, 
                'step': 1, 
                'help': 'Adjust the PAN left angle'
            },
            'PAN Right taboo': {
                'type': 'input', 
                'value': 0, 
                'min': -180, 
                'max': 180, 
                'step': 1, 
                'help': 'Adjust the PAN right angle'
            },
            'TILT Bottom taboo': {
                'type': 'input', 
                'value': 0, 
                'min': -50, 
                'max': 0, 
                'step': 1, 
                'help': 'Adjust the TILT bottom angle'
            },
            'TILT Top taboo': {
                'type': 'input', 
                'value': 0, 
                'min': 0, 
                'max': 50, 
                'step': 1, 
                'help': 'Adjust the TILT top angle'
            },
            'Velocity Speed': {
                'type': 'input',
                'value': 50,
                'min': 0,
                'max': 80,
                'step': 1,
                'help': 'Set velocity speed for joystick movement between 0 and 80 degrees per second.'
            },
            'Fire LRF': {
                'type': 'radio', 
                'value': 'Disable', 
                'options': ['Enable', 'Disable'], 
                'help': 'Enable or disable the firing of the LRF. Options are "Enable" and "Disable".'
            },
            'Firing Rate': {
                'type': 'input', 
                'value': 700, 
                'min': 650, 
                'max': 1000, 
                'step': 10, 
                'help': 'Set the firing rate between 650 and 1000 rounds per minute.'
            },
            'Number of Rounds': {
                'type': 'input', 
                'value': 0, 
                'min': 0, 
                'max': 100, 
                'step': 1, 
                'help': 'Set the number of rounds to fire (0-100). Zero means unlimited rounds.'
            },
            'Default LRF Distance considered (in case LRF is set off)': {
                'type': 'input', 
                'value': 1000, 
                'min': 500, 
                'max': 4000, 
                'step': 100, 
                'help': 'Set the default LRF distance between 1000 and 4000 when the LRF is off.'
            },
            'Wind Speed Mode': {
                'type': 'radio',
                'value': 'Manual',
                'options': ['Manual', 'Automatic'],
                'help': 'Select wind speed mode. Manual uses the value set below, Automatic uses the anemometer.'
            },
            'Wind Speed': {
                'type': 'input',
                'value': 0,
                'min': 0,
                'max': 100,
                'step': 1,
                'help': 'Set wind speed value between 0 and 100 km/h. 0 means no wind.'
            },
            'Wind Direction': {
                'type': 'radio',
                'value': '0',
                'options': ['0', '1', '2', '3', '4', '5', '7', '8', '9', '10', '11'],
                'help': 'Select wind direction based on clock positions. 0 means no wind, 3 is East, 9 is West, etc.'
            },
            'Track Mode': {
                'type': 'dropdown',
                'value': 'Manual ground tracking',
                'options': [
                    'Semi-auto air tracking',
                    'Manual ground tracking',
                    'Semi-auto ground tracking',
                    'Auto ground tracking'
                ],
                'help': 'Select tracking mode. Available modes: Semi-auto air, Manual ground, Semi-auto ground, Auto ground'
            },
            'Thermal Camera Power': {
                'type': 'radio',
                'value': 'Off',
                'options': ['On', 'Off'],
                'help': 'Control power to the thermal camera. On enables the thermal feed, Off disables it.'
            },
            'Fire on Move': {
                'type': 'radio',
                'value': 'Off',
                'options': ['On', 'Off'],
                'help': 'When On, the gun can be moved while armed and firing. When Off, movement is disabled when armed.'
            },
            'Mils': {
                'type': 'input',
                'value': 1,
                'min': 0.1,
                'max': 20,
                'step': 0.1,
                'help': 'Set the movement increment in mils (0.1-20). 1 mil = 0.001 radians. This controls the fine movement when using directional buttons.'
            },
            # ================================
            # PID tuning parameters
            # ================================
            'PID Kp': {
                'type': 'input',
                'value': 3.2,
                'min': 0.0,
                'max': 100.0,
                'step': 0.1,
                'help': 'Proportional gain (Kp) for PID tuning. Adjust to control the system response speed.'
            },
            'PID Ki': {
                'type': 'input',
                'value': 0.7,
                'min': 0.0,
                'max': 50.0,
                'step': 0.1,
                'help': 'Integral gain (Ki) for PID tuning. Adjust to reduce steady-state error.'
            },
            # 'PID Kd': {
            #     'type': 'input',
            #     'value': 0.0,
            #     'min': 0.0,
            #     'max': 50.0,
            #     'step': 0.1,
            #     'help': 'Derivative gain (Kd) for PID tuning. Adjust to reduce overshoot and oscillations.'
            # },
            'Radar IP': {
                'type': 'input',
                'value': '10.1.0.245',
                'help': 'Set the IP address for the radar connection (e.g., 10.1.0.250)'
            },
            'Radar Port': {
                'type': 'input',
                'value': 9010,
                'min': 1024,
                'max': 65535,
                'step': 1,
                'help': 'Set the port number for the radar connection (1024-65535)'
            },
            'Latitude': {
            'type': 'input',
            'value': 34.152300,
            'min': -90.000000,
            'max': 90.000000,
            'step': 0.000001,
            'help': 'Set the latitude coordinate of the system (-90.000000 to 90.000000). Supports up to 6 decimal places.'
            },
            'Longitude': {
                'type': 'input',
                'value': 77.577000,
                'min': -180.000000,
                'max': 180.000000,
                'step': 0.000001,
                'help': 'Set the longitude coordinate of the system (-180.000000 to 180.000000). Supports up to 6 decimal places.'
            },
            'Altitude': {
            'type': 'input',
            'value': 0.0,           # meters AMSL
            'min': -500.0,          # allow below sea level if needed
            'max': 10000.0,         # 10 km ceiling; change if you want
            'step': 0.01,            # spinner step if you add one later
            'help': 'Set site altitude in meters above mean sea level (-500.0 to 10000.0).'
            }
        }

        self.inputs = {}

        # Add title at the top (fixed, not scrollable)
        titleLabel = QLabel("Configuration")
        titleLabel.setAlignment(Qt.AlignCenter)
        titleLabel.setFont(QFont("Arial", 20, QFont.Bold))
        titleLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        titleLabel.setMaximumHeight(40)
        mainLayout.addWidget(titleLabel)
        
        mainLayout.addSpacing(10)
        
        # Create a scroll area
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create a widget to hold the form layout
        containerWidget = QWidget()
        
        # Use a grid layout with 2 columns
        gridLayout = QGridLayout(containerWidget)
        gridLayout.setHorizontalSpacing(20)
        gridLayout.setVerticalSpacing(15)
        
        screen_geo = QApplication.desktop().screenGeometry()
        screen_width = screen_geo.width()
        
        # Create the taboo visualizer
        self.taboo_visualizer = TabooVisualizer()
        
        # ================================================
        # ROW 1: Taboo Zone + Visualizer (special handling)
        # ================================================
        row = 0
        
        # Left column: Taboo Zone label and radio buttons
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        taboo_label = QLabel("Taboo Zone")
        taboo_label.setWordWrap(True)
        taboo_label.setMinimumWidth(int(screen_width * 0.15))
        self.settings['Taboo Zone']['label_element'] = taboo_label
        left_layout.addWidget(taboo_label)
        
        taboo_widget = QWidget()
        taboo_radio_layout = QHBoxLayout(taboo_widget)
        taboo_radio_layout.setContentsMargins(0, 0, 0, 0)
        taboo_group = QButtonGroup(taboo_widget)
        
        for option in self.settings['Taboo Zone']['options']:
            radioButton = QRadioButton(option)
            taboo_group.addButton(radioButton)
            if option == self.settings['Taboo Zone']['value']:
                radioButton.setChecked(True)
            radioButton.toggled.connect(self.update_taboo_visualizer)
            taboo_radio_layout.addWidget(radioButton)
        
        left_layout.addWidget(taboo_widget)
        
        # Add help button
        help_button = QPushButton('?')
        help_button.setFixedWidth(20)
        help_button.clicked.connect(lambda ch, s=self.settings['Taboo Zone']['help']: self.showHelp(s))
        left_layout.addWidget(help_button)
        
        # Add left widget to grid
        gridLayout.addWidget(left_widget, row, 0)
        
        # Right column: Taboo visualizer
        gridLayout.addWidget(self.taboo_visualizer, row, 1)
        
        self.inputs['Taboo Zone'] = taboo_widget
        
        # ================================================
        # ROW 2: PAN Left taboo + PAN Right taboo
        # ================================================
        row += 1
        
        # Left column: PAN Left taboo
        self.add_setting_to_grid(gridLayout, row, 0, 'PAN Left taboo')
        
        # Right column: PAN Right taboo
        self.add_setting_to_grid(gridLayout, row, 1, 'PAN Right taboo')
        
        # ================================================
        # ROW 3: TILT Bottom taboo + TILT Top taboo
        # ================================================
        row += 1
        
        # Left column: TILT Bottom taboo
        self.add_setting_to_grid(gridLayout, row, 0, 'TILT Bottom taboo')
        
        # Right column: TILT Top taboo
        self.add_setting_to_grid(gridLayout, row, 1, 'TILT Top taboo')
        
        # ================================================
        # Process the rest of the settings in left-right alternating pattern
        # ================================================
        remaining_settings = [key for key in self.settings.keys() 
                            if key not in ['Taboo Zone', 'PAN Left taboo', 'PAN Right taboo', 
                                        'TILT Bottom taboo', 'TILT Top taboo']]
        
        for i, key in enumerate(remaining_settings):
            row_pos = row + 1 + (i // 2)  # Integer division to get the row number
            col_pos = i % 2               # Modulo to alternate between columns 0 and 1
            
            self.add_setting_to_grid(gridLayout, row_pos, col_pos, key)
        
        # Set the container widget as the scroll area widget
        scrollArea.setWidget(containerWidget)
        
        # Add the scroll area to the main layout with stretch priority
        mainLayout.addWidget(scrollArea, 1)  # Give it stretch factor of 1
        
        # Button layout at the bottom (fixed, not scrollable)
        buttonLayout = QHBoxLayout()
        loadButton = QPushButton('Load Last Saved Config')
        loadButton.clicked.connect(lambda: self.loadConfig('config.ini'))
        resetConfig = QPushButton('Factory Reset Config')
        resetConfig.clicked.connect(lambda: self.loadConfig('default.ini'))
        saveButton = QPushButton('Save Config')
        saveButton.clicked.connect(self.saveConfig)
        
        buttonLayout.addWidget(loadButton)
        buttonLayout.addWidget(resetConfig)
        buttonLayout.addWidget(saveButton)
        
        mainLayout.addLayout(buttonLayout)
        
        self.setLayout(mainLayout)
        self.setStyleSheet("""
            * {
                text-transform: none;
                color: black;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QLineEdit, QComboBox {
                color: white;
                background-color: #2B2B2B;
            }
            QPushButton {
                color: white;
                background-color: #4C5D34;
            }
            QLabel {
                background-color: transparent;
            }
        """)
        
        self.loadConfig("default.ini", ignore_warning=True)
        self.setup_validators() 
        self.setup_specific_validators()
        self.setup_ip_validator()
        
        # Initial update of the taboo visualizer
        self.update_taboo_visualizer()

    def add_setting_to_grid(self, grid_layout, row, col, setting_key):
        """Add a setting to the grid layout at specified position with proper alignment"""
        setting = self.settings[setting_key]
        
        # Create the container widget for this setting
        setting_widget = QWidget()
        setting_layout = QHBoxLayout(setting_widget)
        setting_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add label
        label = QLabel(f"{setting_key}")
        label.setWordWrap(True)
        label.setFixedWidth(130)  # Fixed width for labels to ensure alignment
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        setting['label_element'] = label
        setting_layout.addWidget(label)
        
        # Create the appropriate widget based on setting type
        if setting_key == 'Wind Direction':
            widget = WindDirectionClock()
            widget.setDirection(int(setting['value']))
        elif setting_key == 'Track Mode' or setting.get('type') == 'dropdown':
            widget = QComboBox()
            widget.setFixedWidth(300)  # Fixed width for dropdown
            for option in setting['options']:
                widget.addItem(option)
            index = widget.findText(setting['value'])
            if index >= 0:
                widget.setCurrentIndex(index)
        elif setting['type'] == 'radio':
            widget = QWidget()
            radio_layout = QHBoxLayout(widget)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            radio_layout.setSpacing(20)  # Increased spacing between radio buttons
            radio_group = QButtonGroup(widget)
            for option in setting['options']:
                radioButton = QRadioButton(option)
                radio_group.addButton(radioButton)
                if option == setting['value']:
                    radioButton.setChecked(True)
                radio_layout.addWidget(radioButton)
            radio_layout.addStretch()  # Add stretch to keep radio buttons left-aligned
        else:
            widget = QLineEdit()
            widget.setFixedWidth(300)  # Fixed width for text inputs
            widget.setText(str(setting['value']))
            # Connect pan taboo input to update visualizer
            if setting_key in ['PAN Left taboo', 'PAN Right taboo']:
                widget.textChanged.connect(self.update_taboo_visualizer)
        
        # Add the widget to the layout with right alignment
        if setting['type'] == 'radio':
            setting_layout.addWidget(widget, 1)  # Give radio buttons widget a stretch factor
        else:
            # For other widgets, use a container with right alignment
            widget_container = QWidget()
            container_layout = QHBoxLayout(widget_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.addWidget(widget)
            container_layout.addStretch()  # Add stretch to keep widget right-aligned
            setting_layout.addWidget(widget_container, 1)  # Add stretch factor
        
        # Add help button
        help_button = QPushButton('?')
        help_button.setFixedWidth(20)
        help_button.setFixedHeight(20)
        help_button.clicked.connect(lambda ch, s=setting['help']: self.showHelp(s))
        setting_layout.addWidget(help_button)
        
        # Add to grid
        grid_layout.addWidget(setting_widget, row, col)
        
        # Store reference to widget
        self.inputs[setting_key] = widget

    def update_taboo_visualizer(self):
        """Update the taboo visualizer with current values from inputs"""
        # Get taboo enabled state
        taboo_enabled = False
        taboo_widget = self.inputs['Taboo Zone']
        for button in taboo_widget.findChildren(QRadioButton):
            if button.text() == 'On' and button.isChecked():
                taboo_enabled = True
        
        # Get pan left and right values
        try:
            pan_left = float(self.inputs['PAN Left taboo'].text())
        except (ValueError, AttributeError):
            pan_left = -90  # Default value
        
        try:
            pan_right = float(self.inputs['PAN Right taboo'].text())
        except (ValueError, AttributeError):
            pan_right = 90  # Default value
        
        # Update visualizer
        self.taboo_visualizer.update_values(
            pan_left=pan_left,
            pan_right=pan_right,
            current_position=self.gun_azimuth,
            taboo_enabled=taboo_enabled
        )

    def setup_specific_validators(self):
        """
        Set up validators for specific input fields:
        Velocity Speed, Default LRF Distance, Wind Speed, Firing Rate, and Number of Rounds
        """
        
        # Fields that need validators with their expected types
        specific_fields = [
            # Field name, validator type
            ('Velocity Speed', QIntValidator),
            ('Default LRF Distance considered (in case LRF is set off)', QIntValidator),
            ('Wind Speed', QDoubleValidator),
            ('Firing Rate', QIntValidator),
            ('Number of Rounds', QIntValidator),
            ('Radar Port', QIntValidator)
        ]
        
        for field_name, validator_type in specific_fields:
            if field_name in self.settings and field_name in self.inputs:
                setting = self.settings[field_name]
                widget = self.inputs[field_name]
                
                if isinstance(widget, QLineEdit) and 'min' in setting and 'max' in setting:
                    min_val = setting['min']
                    max_val = setting['max']
                    
                    # Create and set the validator
                    if validator_type == QIntValidator:
                        validator = QIntValidator(min_val, max_val)
                    else:  # QDoubleValidator
                        validator = QDoubleValidator(min_val, max_val, 1)  # 1 decimal place for wind speed
                    
                    widget.setValidator(validator)
                    
                    # Set tooltip showing the valid range
                    widget.setToolTip(f"Valid range: {min_val} to {max_val}")

    def loadConfig(self, config_name, ignore_warning=False):
        try:
            self.config.read_encrypted(config_name)
            
            # Ensure PAN taboo settings have full range for validators regardless of what's in config file
            if 'PAN Left taboo' in self.settings:
                self.settings['PAN Left taboo']['min'] = -180
                self.settings['PAN Left taboo']['max'] = 180
            
            if 'PAN Right taboo' in self.settings:
                self.settings['PAN Right taboo']['min'] = -180
                self.settings['PAN Right taboo']['max'] = 180
            
            for key, setting in self.settings.items():
                if setting['type'] == 'input' and key in ['PAN Left taboo', 'PAN Right taboo', 'TILT Bottom taboo', 'TILT Top taboo']:
                    widget = self.inputs[key]
                    if isinstance(widget, QLineEdit):
                        # Create a validator with proper range
                        min_val = setting['min']
                        max_val = setting['max']
                        validator = QDoubleValidator(min_val, max_val, 2)
                        widget.setValidator(validator)
                
                if key in self.config['DEFAULT']:
                    value = self.config['DEFAULT'][key]
                    if key == 'Wind Direction':
                        direction = int(value)
                        self.inputs[key].setDirection(direction)
                    elif key == 'Track Mode':
                        # Handle dropdown for Track Mode
                        combobox = self.inputs[key]
                        index = combobox.findText(value)
                        if index >= 0:
                            combobox.setCurrentIndex(index)
                    elif setting['type'] == 'radio':
                        for button in self.inputs[key].findChildren(QRadioButton):
                            if button.text() == value:
                                button.setChecked(True)
                                break
                    else:
                        # Force accept values within the valid range
                        try:
                            float_val = float(value)
                            if key in ['PAN Left taboo', 'PAN Right taboo'] and -180 <= float_val <= 180:
                                self.inputs[key].setText(value)
                            elif self.validateInput(value, setting['min'], setting['max']):
                                self.inputs[key].setText(value)
                        except:
                            pass
            
            # Update taboo visualizer after loading config
            self.update_taboo_visualizer()
            
            if not ignore_warning:
                QMessageBox.information(self, 'Success', 'Configuration loaded successfully.')
        except Exception as e:
            if not ignore_warning:
                QMessageBox.critical(self, 'Error', f'Failed to load configuration: {e}')

    def set_system_type(self, system_type):
        """
        Set the system type for taboo validation and update min/max limits
        """
        self.system_type = system_type
        
        # Get limits from the centralized system_limits module
        limits = get_system_limits(system_type)
        
        # Update settings with new limits and help text
        if hasattr(self, 'settings'):
            # Update PAN Left taboo
            if 'PAN Left taboo' in self.settings:
                self.settings['PAN Left taboo']['min'] = limits['PAN_LEFT_LIMIT']
                self.settings['PAN Left taboo']['max'] = 0 
                self.settings['PAN Left taboo']['help'] = HELP_TEXT['left']
            
            # Update PAN Right taboo
            if 'PAN Right taboo' in self.settings:
                self.settings['PAN Right taboo']['min'] = 0
                self.settings['PAN Right taboo']['max'] = limits['PAN_RIGHT_LIMIT']
                self.settings['PAN Right taboo']['help'] = HELP_TEXT['right']
            
            # Update TILT Top taboo
            if 'TILT Top taboo' in self.settings:
                self.settings['TILT Top taboo']['min'] = 0
                self.settings['TILT Top taboo']['max'] = limits['TILT_TOP_LIMIT']
                self.settings['TILT Top taboo']['help'] = HELP_TEXT['top']
            
            # Update TILT Bottom taboo
            if 'TILT Bottom taboo' in self.settings:
                self.settings['TILT Bottom taboo']['min'] = limits['TILT_BOTTOM_LIMIT']
                self.settings['TILT Bottom taboo']['max'] = 0
                self.settings['TILT Bottom taboo']['help'] = HELP_TEXT['bottom']
        
        # Update the UI to reflect the new limits
        self.update_limits_display()

    def setup_ip_validator(self):
        """Set up validator for IP address field"""
        if 'Radar IP' in self.inputs:
            widget = self.inputs['Radar IP']
            if isinstance(widget, QLineEdit):
                ip_regex = QRegExp(
                    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
                    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
                )
                ip_validator = QRegExpValidator(ip_regex)
                widget.setValidator(ip_validator)
                widget.setToolTip("Enter a valid IP address (e.g., 10.1.0.250)")

    def setup_validators(self):
        """
        Set up validators for all input fields to restrict input to valid ranges
        """
        for key, setting in self.settings.items():
            if setting['type'] == 'input' and 'min' in setting and 'max' in setting:
                widget = self.inputs.get(key)
                if widget and isinstance(widget, QLineEdit):
                    min_val = setting['min']
                    max_val = setting['max']
                    
                    # Force full range for PAN taboo fields
                    if key in ['PAN Left taboo', 'PAN Right taboo']:
                        min_val = -180
                        max_val = 180
                        
                        # Update the setting for consistency
                        setting['min'] = min_val
                        setting['max'] = max_val
                    
                    # Create an appropriate validator based on the data type
                    if isinstance(min_val, int) and isinstance(max_val, int):
                        # Use integer validator for integer settings
                        validator = QIntValidator(min_val, max_val)
                    else:
                        # Use double validator for float settings (with 2 decimal places)
                        # validator = QDoubleValidator(min_val, max_val, 2)
                        # Use higher precision for Latitude and Longitude
                        decimals = 6 if key in ['Latitude', 'Longitude'] else 2
                        validator = QDoubleValidator(min_val, max_val, decimals)

                    
                    widget.setValidator(validator)
                    
                    # Set tooltip showing the valid range
                    widget.setToolTip(f"Valid range: {min_val} to {max_val}")

    def update_limits_display(self):
        """
        Update the display of limits in the UI for all input fields
        """
        for key, setting in self.settings.items():
            if setting['type'] == 'input' and 'min' in setting and 'max' in setting:
                widget = self.inputs.get(key)
                if widget and isinstance(widget, QLineEdit):
                    min_val = setting['min']
                    max_val = setting['max']
                    
                    # Always use full range for PAN Left and PAN Right taboo fields
                    if key in ['PAN Left taboo', 'PAN Right taboo']:
                        min_val = -180
                        max_val = 180
                        
                        # Update the setting itself to ensure consistency
                        setting['min'] = min_val
                        setting['max'] = max_val
                    
                    # Get the current validator or create a new one based on data type
                    validator = widget.validator()
                    if not validator:
                        if isinstance(min_val, int) and isinstance(max_val, int):
                            validator = QIntValidator()
                            widget.setValidator(validator)
                        else:
                            validator = QDoubleValidator()
                            widget.setValidator(validator)
                    
                    # Update the validator range
                    if isinstance(validator, QIntValidator):
                        validator.setRange(min_val, max_val)
                    elif isinstance(validator, QDoubleValidator):
                        # validator.setRange(min_val, max_val, 2)  # 2 decimal places
                        decimals = 6 if key in ['Latitude', 'Longitude'] else 2
                        validator.setRange(min_val, max_val, decimals)
                    
                    # Update tooltip to show just the valid range
                    widget.setToolTip(f"Valid range: {min_val} to {max_val}")

    def set_gun_controller(self, gun_controller):
        """Set the gun controller for sending limit parameters to motors"""
        self.gun_controller = gun_controller

    def update_current_position(self, azimuth):
        """Update the current position marker in the visualizer"""
        self.gun_azimuth = azimuth
        self.update_taboo_visualizer()

    def saveConfig(self):
        try:
            result = {}
            for key, setting in self.settings.items():
                if key == 'Wind Direction':
                    value = self.inputs[key].getDirection()
                    self.config['DEFAULT'][key] = result[key] = str(value)
                elif key == 'Track Mode':
                    # Handle dropdown for Track Mode
                    value = self.inputs[key].currentText()
                    self.config['DEFAULT'][key] = result[key] = value
                elif setting['type'] == 'radio':
                    radio_layout = self.inputs[key].layout()
                    for i in range(radio_layout.count()):
                        button = radio_layout.itemAt(i).widget()
                        if isinstance(button, QRadioButton) and button.isChecked():
                            value = button.text()
                            self.config['DEFAULT'][key] = result[key] = value
                            break
                else:
                    value = self.inputs[key].text()
                    
                    # Special case for PAN Left and PAN Right taboo - allow full range
                    if key in ['PAN Left taboo', 'PAN Right taboo']:
                        try:
                            float_val = float(value)
                            if -180 <= float_val <= 180:
                                setting['label_element'].setStyleSheet("color:black")
                                self.config['DEFAULT'][key] = result[key] = str(value)
                            else:
                                setting['label_element'].setStyleSheet("color:red")
                                raise ValueError(f"Invalid value for {key}, must be between -180 and 180")
                        except ValueError as e:
                            if "must be between" in str(e):
                                raise e
                            setting['label_element'].setStyleSheet("color:red")
                            raise ValueError(f"Invalid value for {key}, must be a number")
# elif 'min' in setting and 'max' in setting and self.validateInput(value, setting['min'], setting['max']):
#     setting['label_element'].setStyleSheet("color:black")
#     self.config['DEFAULT'][key] = result[key] = str(value)
# else:
#     setting['label_element'].setStyleSheet("color:red")
#     raise ValueError(f"Invalid value for {key}")
                    # Normal validation for other fields
                    elif ('min' in setting and 'max' in setting and 
                        self.validateInput(value, setting['min'], setting['max'])) or \
                        ('min' not in setting and 'max' not in setting):
                        setting['label_element'].setStyleSheet("color:black")
                        self.config['DEFAULT'][key] = result[key] = str(value)
                    else:
                        setting['label_element'].setStyleSheet("color:red")
                        raise ValueError(f"Invalid value for {key}")
            
            # Validate taboo values against system type - but with full pan range
            if hasattr(self, 'system_type') and self.system_type:
                self.validate_taboo_values()
            
            with open('config.ini', 'wb') as configfile:
                self.config.write_encrypted(configfile)

            QMessageBox.information(self, 'Success', 'Configuration saved successfully!')
            
            # Emit save signal with the configuration data
            self.save_signal.emit(str(result))
            self.config_saved.emit()
            
        except ValueError as e:
            QMessageBox.critical(self, 'Error', f'Failed to save configuration: {str(e)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'An unexpected error occurred while saving the configuration: {str(e)}')

    def validate_taboo_values(self):
        """Validate taboo values against the system type"""
        try:
            pan_left = float(self.config['DEFAULT']['PAN Left taboo'])
            pan_right = float(self.config['DEFAULT']['PAN Right taboo'])
            tilt_bottom = float(self.config['DEFAULT']['TILT Bottom taboo'])
            tilt_top = float(self.config['DEFAULT']['TILT Top taboo'])
            
            # Get system-specific limits from the centralized module
            limits = get_system_limits(self.system_type)
            
            if pan_left < limits['PAN_LEFT_LIMIT'] or pan_left > limits['PAN_RIGHT_LIMIT']:
                raise ValueError(f"PAN Left taboo value {pan_left} is outside system limits for {self.system_type}")
            if pan_right < limits['PAN_LEFT_LIMIT'] or pan_right > limits['PAN_RIGHT_LIMIT']:
                raise ValueError(f"PAN Right taboo value {pan_right} is outside system limits for {self.system_type}")
            if tilt_bottom < limits['TILT_BOTTOM_LIMIT'] or tilt_bottom > 0:
                raise ValueError(f"TILT Bottom taboo value {tilt_bottom} is outside system limits for {self.system_type}")
            if tilt_top < 0 or tilt_top > limits['TILT_TOP_LIMIT']:
                raise ValueError(f"TILT Top taboo value {tilt_top} is outside system limits for {self.system_type}")
                
        except Exception as e:
            raise ValueError(f"Error validating taboo values: {str(e)}")
        
    def showHelp(self, helpText):
        QMessageBox.information(self, 'Help', helpText)

    def validateInput(self, value, min_value, max_value):
        try:
            value = float(value)
            if min_value == -180 and max_value == 180:
                return -180 <= value <= 180
            
            return min_value <= value <= max_value
        except ValueError:
            return False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ConfigScreen()
    ex.show()
    sys.exit(app.exec_())