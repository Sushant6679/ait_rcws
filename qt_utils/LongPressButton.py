import sys
from PyQt5.QtWidgets import QApplication, QPushButton
from PyQt5.QtCore import QTimer

class LongPressButton(QPushButton):
    def __init__(self, text, parent=None):
        super(LongPressButton, self).__init__(text, parent)
        self.setMouseTracking(True)
        self.timer = QTimer()
        self.timer.setInterval(500)  # Adjust this interval as needed
        self.timer.timeout.connect(self.emitClickFirst)

        self.timer2 = QTimer()
        self.timer2.setInterval(50)  # Adjust this interval as needed
        self.timer2.timeout.connect(self.emitClick)

        self.pressed_time = None

    def mousePressEvent(self, event):
        if event.button() == 1:  # Left mouse button
            self.pressed_time = event.timestamp()
            self.emitClick()
            self.timer.start()

    def mouseReleaseEvent(self, event):
        if event.button() == 1:  # Left mouse button
            self.timer.stop()
            self.timer2.stop()
            self.pressed_time = None

    def emitClickFirst(self):
        self.timer.stop()
        if self.pressed_time:
            self.timer2.start()

    # def mouseMoveEvent(self, event):
    #     if self.pressed_time is not None:
    #         if event.timestamp() - self.pressed_time >= self.timer.interval():
    #             self.emitClick()
    #             self.timer.start()

    def emitClick(self):
        self.clicked.emit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    button = LongPressButton("Long Press Me")
    button.clicked.connect(lambda: print("Button clicked!"))
    button.show()
    sys.exit(app.exec_())
