from PyQt5.QtCore import Qt, QObject, QEvent, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget

from utility import EWorkMode


class UGlobalSignalHolder(QObject):
    ctrl_pressed = pyqtSignal(int)
    ctrl_released = pyqtSignal(int)

    arrows_pressed = pyqtSignal(int)
    drop_pressed = pyqtSignal(int)
    delete_pressed = pyqtSignal(int)

    added_new_annotation = pyqtSignal(object)
    updated_annotation = pyqtSignal(int, object)
    deleted_annotation = pyqtSignal(int)

    change_work_mode = pyqtSignal(int)
    changed_class_annotate = pyqtSignal(int)

    command_key_pressed = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        # Частотный таймер, который отправляет событие о нажатии кнопки, при ее удержании
        self.freq_timer = QTimer(self)
        self.freq_timer.setInterval(100)
        self.freq_timer.timeout.connect(self.on_end_delay)

        # Таймер, который запускает частотный таймер
        self.delay_timer = QTimer(self)
        self.delay_timer.setInterval(500)
        self.delay_timer.setSingleShot(True)
        self.delay_timer.timeout.connect(self.on_freq)

        self.current_key = -1

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Control:
                self.ctrl_pressed.emit(event.key())
                return True

            if (event.key() == Qt.Key_Left or event.key() == Qt.Key_Right or
                event.key() == Qt.Key_A or event.key() == Qt.Key_D):
                self.current_key = event.key()
                self.arrows_pressed.emit(event.key())
                self.delay_timer.start()
                if self.freq_timer.isActive():
                    self.freq_timer.stop()
                return True

            if event.key() == Qt.Key_1:
                self.change_work_mode.emit(EWorkMode.DragMode.value)
                return True

            if event.key() == Qt.Key_2:
                self.change_work_mode.emit(EWorkMode.AnnotateMode.value)
                return True

            if event.key() == Qt.Key_Space:
                self.command_key_pressed.emit(Qt.Key_Space)
                return True

            if event.key() == Qt.Key_N:
                self.drop_pressed.emit(event.key())
                self.arrows_pressed.emit(Qt.Key_Right)
                self.delay_timer.start()
                if self.freq_timer.isActive():
                    self.freq_timer.stop()
                return True

            if event.key() == Qt.Key_Delete:
                self.delete_pressed.emit(event.key())
                return True

        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Control:
                self.ctrl_released.emit(event.key())
                return True

            if (event.key() == Qt.Key_Left or event.key() == Qt.Key_Right or
                event.key() == Qt.Key_A or event.key() == Qt.Key_D):
                self.freq_timer.stop()
                self.delay_timer.stop()
                self.current_key = -1
                return True

            if event.key() == Qt.Key_N:
                self.freq_timer.stop()
                self.delay_timer.stop()
                return True

        return super().eventFilter(obj, event)

    def on_end_delay(self):
        self.freq_timer.start()

    def on_freq(self):
        if (self.current_key == Qt.Key_Left or self.current_key == Qt.Key_Right or
            self.current_key == Qt.Key_A or self.current_key == Qt.Key_D):
            self.arrows_pressed.emit(self.current_key)
        elif self.current_key == Qt.Key_N:
            self.drop_pressed.emit(self.current_key)
            self.arrows_pressed.emit(Qt.Key_Right)