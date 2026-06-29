import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QScrollArea, QSizePolicy, QGroupBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtCore import pyqtSignal


class GROUP_PARAMS:
    ACTUAL_VALUES =      "Actual Values"
    ERROR_AND_STATE_CODES =      "Error and State Codes"
    ELECTRICAL_PARAMETERS =      "Electrical Parameters"
    POSITION_AND_SPEED_LIMITS =      "Position and Speed Limits"
    STRUCK_CONDITIONS =      "Struck Conditions"
    CONTROL_AND_FEEDBACK_GAINS =         "Control and Feedback Gains"
    TARGET_AND_PROFILE_PARAMETERS =      "Target and Profile Parameters"

class Parameter(QObject):
    broadcast = pyqtSignal()

    def __init__(self) -> None:
        self.params = {}
        self.groups = {}
        self.init_params()
        super().__init__()
    
    def add_param(self, group, name, unit):
        self.params[name] = {
            'group': group,
            'name': name,
            'unit': unit,
            'value': None,
            'value_degree': None,
            'unit_degree': None,
        }
        data = self.get_unit_value(unit, None)
        if data:
            self.params[name]['value_degree'] = data[0]
            self.params[name]['unit_degree'] = data[1]

        if group not in self.groups:
            self.groups[group] = []
        self.groups[group].append(self.params[name])

    def get_unit_value(self, unit, val):
        if 'count' in unit:
            if val is None:
                return None , 'degree' + unit[5:]
            return str(round(float(val) * 360 / (2**19), 3)) , 'degree' + unit[5:]
        return None

    def update_param(self, name, value):
        self.params[name]['value'] = str(value)
        data = self.get_unit_value(self.params[name]['unit'], value)
        if data:
            self.params[name]['value_degree'] = data[0]
            self.params[name]['unit_degree'] = data[1]

    def apply(self):
        self.broadcast.emit()

    def init_params(self):
        self.add_param(GROUP_PARAMS.ACTUAL_VALUES,"Actual Position", "count")
        self.add_param(GROUP_PARAMS.ACTUAL_VALUES,"Actual Speed", "count/s")
        self.add_param(GROUP_PARAMS.ACTUAL_VALUES,"Actual Motor Current", "mA")
        self.add_param(GROUP_PARAMS.ACTUAL_VALUES,"Actual Torque", "mNm")
        self.add_param(GROUP_PARAMS.ACTUAL_VALUES,"Enabled Motor", "—")
        self.add_param(GROUP_PARAMS.ERROR_AND_STATE_CODES,"Error Codes", "—")
        self.add_param(GROUP_PARAMS.ERROR_AND_STATE_CODES,"Operation State", "—")
        self.add_param(GROUP_PARAMS.ERROR_AND_STATE_CODES,"State of achieving the target", "—")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"DC Bus Voltage", "mV")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"Power Temperature", "°C")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"Continuous Current", "mA")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"Peak Current", "mA")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"Peak Current Duration", "ms")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"MAX Phase Current", "mA")
        self.add_param(GROUP_PARAMS.ELECTRICAL_PARAMETERS,"MAX Motor Current", "mA")
        self.add_param(GROUP_PARAMS.POSITION_AND_SPEED_LIMITS,"Position Limit (MIN)", "count")
        self.add_param(GROUP_PARAMS.POSITION_AND_SPEED_LIMITS,"Position Limit (MAX)", "count")
        self.add_param(GROUP_PARAMS.POSITION_AND_SPEED_LIMITS,"MAX Speed", "count/s")
        self.add_param(GROUP_PARAMS.POSITION_AND_SPEED_LIMITS,"Permissible MAX Position Error", "count")
        self.add_param(GROUP_PARAMS.POSITION_AND_SPEED_LIMITS,"Permissible MAX Speed Error", "count/s")
        self.add_param(GROUP_PARAMS.STRUCK_CONDITIONS,"Struck Current", "mA")
        self.add_param(GROUP_PARAMS.STRUCK_CONDITIONS,"Struck Speed", "count/s")
        self.add_param(GROUP_PARAMS.STRUCK_CONDITIONS,"Struck Time", "ms")
        self.add_param(GROUP_PARAMS.CONTROL_AND_FEEDBACK_GAINS,"Position Loop Gain", "—")
        self.add_param(GROUP_PARAMS.CONTROL_AND_FEEDBACK_GAINS,"Speed Loop Gain", "—")
        self.add_param(GROUP_PARAMS.CONTROL_AND_FEEDBACK_GAINS,"Speed Loop Integral", "—")
        self.add_param(GROUP_PARAMS.TARGET_AND_PROFILE_PARAMETERS,"Target Absolute Position", "count")
        self.add_param(GROUP_PARAMS.TARGET_AND_PROFILE_PARAMETERS,"Profile Acceleration", "count/s²")
        self.add_param(GROUP_PARAMS.TARGET_AND_PROFILE_PARAMETERS,"Profile Deceleration", "count/s²")
        self.add_param(GROUP_PARAMS.TARGET_AND_PROFILE_PARAMETERS,"Profile Speed", "count/s")
        self.add_param(GROUP_PARAMS.TARGET_AND_PROFILE_PARAMETERS,"Motion Mode", "—")
        self.add_param(GROUP_PARAMS.TARGET_AND_PROFILE_PARAMETERS,"Operation Mode", "—")

class ParameterGroupWidget(QWidget):
    def __init__(self, group_title, params, two_page_layout=False):
        super().__init__()
        self.params = params
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Set margins to 0
        layout.setSpacing(0)  # Set spacing to 0

        titleLabel = QLabel(group_title)
        titleLabel.setAlignment(Qt.AlignCenter)
        titleLabel.setFont(QFont("Arial", 12, QFont.Bold))
        titleLabel.setMaximumHeight(50)

        if two_page_layout:
            self.gridLayout = QGridLayout()
            for i, param in enumerate(params):
                paramLabel = QLabel(param['name'])
                paramLabel.setFont(QFont("Arial", 10, QFont.Bold))
                paramLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                self.gridLayout.addWidget(paramLabel, i // 2, (i % 2) * 5)

                if param['value_degree']:
                    valueLabel = QLabel(f"{param['value_degree']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i // 2, (i % 2) * 5 + 1)
                
                if param['unit_degree']:
                    valueLabel = QLabel(f"{param['unit_degree']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i // 2, (i % 2) * 5 + 2)

                if param['value']:
                    valueLabel = QLabel(f"{param['value']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i // 2, (i % 2) * 5 + 3)
                
                valueLabel = QLabel(f"{param['unit']}")
                valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                self.gridLayout.addWidget(valueLabel, i // 2, (i % 2) * 5 + 4)

            for col in range(0, 10, 5):
                self.gridLayout.setColumnStretch(col, 6)
                for j in range(1, 5):
                    self.gridLayout.setColumnStretch(col + j, 1)
        else:
            self.gridLayout = QGridLayout()
            for i, param in enumerate(params):
                paramLabel = QLabel(param['name'])
                # paramLabel.setFont(QFont("Arial", 10, QFont.Bold))
                paramLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                self.gridLayout.addWidget(paramLabel, i, 0)
                if param['value_degree'] is not None:
                    valueLabel = QLabel(f"{param['value_degree']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i, 1)
                if param['unit_degree'] is not None:
                    valueLabel = QLabel(f"{param['unit_degree']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i, 2)
                if param['value'] is not None:
                    valueLabel = QLabel(f"{param['value']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i, 3)

                valueLabel = QLabel(f"{param['unit']}")
                valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                self.gridLayout.addWidget(valueLabel, i, 4)

            self.gridLayout.setColumnStretch(0, 6)
            for j in range(1, 5):
                self.gridLayout.setColumnStretch(j, 1)

        layout.addLayout(self.gridLayout)
        self.setLayout(layout)

    def update_params(self, params):
        self.params = params
        for i, param in enumerate(params):
            if param['value_degree'] is not None:
                if self.gridLayout.itemAtPosition(i, 1) is None:
                    valueLabel = QLabel(f"{param['value_degree']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i, 1)
                else:
                    self.gridLayout.itemAtPosition(i, 1).widget().setText(param['value_degree'])
            if param['value'] is not None:
                if self.gridLayout.itemAtPosition(i, 3) is None:
                    valueLabel = QLabel(f"{param['value']}")
                    valueLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    self.gridLayout.addWidget(valueLabel, i, 3)
                else:
                    self.gridLayout.itemAtPosition(i, 3).widget().setText(param['value'])

class ParameterWidget(QWidget):
    def __init__(self, title, param_groups):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Set margins to 0
        layout.setSpacing(0)  # Set spacing to 0

        titleLabel = QLabel(title)
        titleLabel.setAlignment(Qt.AlignCenter)
        titleLabel.setFont(QFont("Arial", 16, QFont.Bold))
        titleLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        titleLabel.setMaximumHeight(40)
        layout.addWidget(titleLabel)

        self.groupWidgets = []
        for title, group in param_groups.groups.items():
            groupBox = QGroupBox()
            groupLayout = QVBoxLayout()
            groupTitle = QLabel(title)
            groupTitle.setFont(QFont("Arial", 14, QFont.Bold))
            groupTitle.setStyleSheet("""color: #2B411C;""")
            groupLayout.addWidget(groupTitle)
            groupWidget = ParameterGroupWidget(title, group, False)
            groupLayout.addWidget(groupWidget)
            groupBox.setLayout(groupLayout)
            layout.addWidget(groupBox)
            self.groupWidgets.append(groupWidget)

        self.setLayout(layout)

    def update_groups(self, param_groups):
        for i, group in enumerate(param_groups.groups.values()):
            self.groupWidgets[i].update_params(group)

class MainWidget(QWidget):
    def __init__(self, pan_params: Parameter, tilt_params: Parameter):
        super().__init__()

        layout = QHBoxLayout()

        self.pan_params = pan_params
        self.tilt_params = tilt_params

        self.pan_params.broadcast.connect(self.update_pan)
        self.tilt_params.broadcast.connect(self.update_tilt)

        self.panWidget = ParameterWidget("PAN PARAMETERS", pan_params)
        self.tiltWidget = ParameterWidget("TILT PARAMETERS", tilt_params)

        panScroll = QScrollArea()
        panScroll.setWidget(self.panWidget)
        panScroll.setWidgetResizable(True)

        tiltScroll = QScrollArea()
        tiltScroll.setWidget(self.tiltWidget)
        tiltScroll.setWidgetResizable(True)

        layout.addWidget(panScroll)
        layout.addWidget(tiltScroll)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            * {
                text-transform: none;
                color: black;
            }
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                border: 1px solid #2B411C;
                background: #A4AA88;
                width: 15px;
                margin: 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2B411C;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QGroupBox{
                border: 1px solid #2B411C;
                margin: 0;
            }
        """)

    def update_pan(self):
        self.panWidget.update_groups(self.pan_params)

    def update_tilt(self):
        self.tiltWidget.update_groups(self.tilt_params)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    p,t = Parameter(), Parameter()
    mainWidget = MainWidget( p, t)
    mainWidget.showMaximized()

    p.update_param("Actual Position", "100")
    p.update_param("Actual Speed", "200")
    p.update_param("Actual Motor Current", "300")
    p.update_param("Actual Torque", "400")
    p.update_param("Enabled Motor", "Yes")

    t.update_param("Actual Position", "500")
    t.update_param("Actual Speed", "600")
    t.update_param("Actual Motor Current", "700")
    t.update_param("Actual Torque", "800")
    t.update_param("Enabled Motor", "No")

    p.apply()
    t.apply()

    sys.exit(app.exec_())
