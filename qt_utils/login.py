# import sys
# from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QFrame, QDialog, QDesktopWidget, QComboBox)
# from PyQt5.QtGui import QPalette, QBrush, QPixmap, QColor
# from PyQt5.QtCore import Qt
# from utils.UserManagement import UserManager

# class LoginDialog(QDialog):
#     def __init__(self, parent, icon):
#         super().__init__(parent=parent)
#         self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
#         self.user = None
#         self.system_type = None

#         # Set fixed size
#         self.setFixedSize(800, 450)  # Increased height to accommodate the new dropdown

#         # Center the dialog on the screen
#         self.center_on_screen()

#         # Set solid background color
#         self.setAutoFillBackground(True)
#         palette = self.palette()
#         palette.setColor(QPalette.Window, QColor("#aaa"))
#         self.setPalette(palette)

#         # Create main layout
#         main_layout = QHBoxLayout(self)

#         # Right side layout for logo
#         logo_layout = QVBoxLayout()
#         logo_layout.addStretch()
#         logo_label = QLabel()
#         logo_pixmap = QPixmap(icon).scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
#         logo_label.setPixmap(logo_pixmap)
#         logo_label.setAlignment(Qt.AlignCenter)
#         logo_label.setObjectName("iconIco")
#         logo_layout.addWidget(logo_label)
#         logo_layout.addStretch()

#         # Add logo layout to main layout
#         main_layout.addLayout(logo_layout)

#         # Left side layout for login form
#         login_layout = QVBoxLayout()

#         # Login form title
#         title_label = QLabel('Login')
#         title_label.setAlignment(Qt.AlignCenter)
#         title_label.setObjectName("login")
#         login_layout.addWidget(title_label)

#         # System Type dropdown
#         label_system_type = QLabel('System Type')
#         self.combo_system_type = QComboBox()
#         self.combo_system_type.addItems(['NSVT', 'BMG', 'RCWS'])
#         login_layout.addWidget(label_system_type)
#         login_layout.addWidget(self.combo_system_type)

#         # Username label and line edit
#         label_name = QLabel('Username')
#         self.lineEdit_username = QLineEdit()
#         self.lineEdit_username.setPlaceholderText('Username')
#         self.lineEdit_username.setText("ADMIN")
#         self.lineEdit_username.returnPressed.connect(self.check_password)
#         login_layout.addWidget(label_name)
#         login_layout.addWidget(self.lineEdit_username)

#         # Password label and line edit
#         label_password = QLabel('Password')
#         self.lineEdit_password = QLineEdit()
#         self.lineEdit_password.setPlaceholderText('Password')
#         self.lineEdit_password.setText("ADMIN")
#         self.lineEdit_password.setEchoMode(QLineEdit.Password)
#         self.lineEdit_password.returnPressed.connect(self.check_password)
#         login_layout.addWidget(label_password)
#         login_layout.addWidget(self.lineEdit_password)

#         # Error message label
#         self.error_label = QLabel('')
#         self.error_label.setStyleSheet('color: red;')
#         login_layout.addWidget(self.error_label)

#         # Login button
#         button_login = QPushButton('Login')
#         button_login.clicked.connect(self.check_password)
#         button_login.setObjectName("btnLogin")
#         login_layout.addWidget(button_login)

#         # Add login layout to main layout
#         main_layout.addLayout(login_layout)

#         # Apply CSS
#         self.setStyleSheet("""
#             #iconIco {
#                 padding: 20px;
#                 padding-right: 40px;
#             }
#             #login {
#                 font-weight: bold;
#                 color: black;
#                 font-size: 24px;
#             }
#             QLabel {
#                 color: black;
#                 font-size: 16px;
#             }
#             QLineEdit, QComboBox {
#                 background-color: #f0f0f0;
#                 border: 1px solid #ccc;
#                 border-radius: 4px;
#                 padding: 10px;
#                 font-size: 16px;
#                 color: black;
#             }
#             QLineEdit::placeholder {
#                 color: #888;
#             }
#             #btnLogin {
#                 background-color: red;
#                 border: 2px solid red;
#                 color: white;
#                 font-weight: bold;
#                 border-radius: 4px;
#                 padding: 15px 15px;
#                 text-align: center;
#                 font-size: 16px;
#                 margin: 0px 0;
#             }
#             #btnLogin:hover {
#                 background-color: #cc0000;
#                 border-color: #cc0000;
#             }
#         """)

#     def center_on_screen(self):
#         screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
#         center_point = QDesktopWidget().screenGeometry(screen).center()
#         frame_geometry = self.frameGeometry()
#         frame_geometry.moveCenter(center_point)
#         self.move(frame_geometry.topLeft())

#     def check_password(self):
#         success, user = UserManager.verify_user(self.lineEdit_username.text().upper(), self.lineEdit_password.text().upper())
#         if success:
#             self.user = user
#             self.system_type = self.combo_system_type.currentText()
#             self.accept()
#         else:
#             self.error_label.setText('Incorrect Password')


import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QFrame, QDialog, QDesktopWidget, QRadioButton, QButtonGroup)
from PyQt5.QtGui import QPalette, QBrush, QPixmap, QColor
from PyQt5.QtCore import Qt
from utils.UserManagement import UserManager

class LoginDialog(QDialog):
    def __init__(self, parent, icon):
        super().__init__(parent=parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.user = None
        self.system_type = None

        # Set fixed size
        self.setFixedSize(800, 500)  # Increased height to accommodate the radio buttons

        # Center the dialog on the screen
        self.center_on_screen()

        # Set solid background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#aaa"))
        self.setPalette(palette)

        # Create main layout
        main_layout = QHBoxLayout(self)

        # Right side layout for logo
        logo_layout = QVBoxLayout()
        logo_layout.addStretch()
        logo_label = QLabel()
        logo_pixmap = QPixmap(icon).scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setObjectName("iconIco")
        logo_layout.addWidget(logo_label)
        logo_layout.addStretch()

        # Add logo layout to main layout
        main_layout.addLayout(logo_layout)

        # Left side layout for login form
        login_layout = QVBoxLayout()

        # Login form title
        title_label = QLabel('Login')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("login")
        login_layout.addWidget(title_label)

        # Username label and line edit
        label_name = QLabel('Username')
        self.lineEdit_username = QLineEdit()
        self.lineEdit_username.setPlaceholderText('Username')
        self.lineEdit_username.setText("ADMIN")
        self.lineEdit_username.returnPressed.connect(self.check_password)
        login_layout.addWidget(label_name)
        login_layout.addWidget(self.lineEdit_username)

        # Password label and line edit
        label_password = QLabel('Password')
        self.lineEdit_password = QLineEdit()
        self.lineEdit_password.setPlaceholderText('Password')
        self.lineEdit_password.setText("ADMIN")
        self.lineEdit_password.setEchoMode(QLineEdit.Password)
        self.lineEdit_password.returnPressed.connect(self.check_password)
        login_layout.addWidget(label_password)
        login_layout.addWidget(self.lineEdit_password)

        # System Type radio buttons
        label_system_type = QLabel('System Type')
        login_layout.addWidget(label_system_type)

        self.radio_group = QButtonGroup(self)
        radio_layout = QHBoxLayout()

        for system in ['BMG', 'NSVT', 'RCWS']:
            radio_button = QRadioButton(system)
            self.radio_group.addButton(radio_button)
            radio_layout.addWidget(radio_button)

        login_layout.addLayout(radio_layout)

        # Set default selection
        self.radio_group.buttons()[0].setChecked(True)

        # Error message label
        self.error_label = QLabel('')
        self.error_label.setStyleSheet('color: red;')
        login_layout.addWidget(self.error_label)

        # Login button
        button_login = QPushButton('Login')
        button_login.clicked.connect(self.check_password)
        button_login.setObjectName("btnLogin")
        login_layout.addWidget(button_login)

        # Add login layout to main layout
        main_layout.addLayout(login_layout)

        # Apply CSS
        self.setStyleSheet("""
            #iconIco {
                padding: 20px;
                padding-right: 40px;
            }
            #login {
                font-weight: bold;
                color: black;
                font-size: 24px;
            }
            QLabel {
                color: black;
                font-size: 16px;
            }
            QLineEdit, QRadioButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px;
                font-size: 16px;
                color: black;
            }
            QLineEdit::placeholder {
                color: #888;
            }
            QRadioButton {
                background-color: transparent;
                border: none;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            QRadioButton::indicator:checked {
                background-color: red;
                border: 2px solid white;
            }
            #btnLogin {
                background-color: red;
                border: 2px solid red;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 15px 15px;
                text-align: center;
                font-size: 16px;
                margin: 0px 0;
            }
            #btnLogin:hover {
                background-color: #cc0000;
                border-color: #cc0000;
            }
        """)

    def center_on_screen(self):
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        center_point = QDesktopWidget().screenGeometry(screen).center()
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def check_password(self):
        success, user = UserManager.verify_user(self.lineEdit_username.text().upper(), self.lineEdit_password.text().upper())
        if success:
            self.user = user
            self.system_type = self.radio_group.checkedButton().text()
            self.accept()
        else:
            self.error_label.setText('Incorrect Password')