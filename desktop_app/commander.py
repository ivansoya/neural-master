from enum import Enum

from PyQt5.QtCore import Qt, QObject, QEvent, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget

from utility import EAnnotationStatus

class ECommanderStatus(Enum):
    LoadProject = 1
    DatasetView = 2
    Annotation = 3
    Statistics = 4
    LoadModel = 5

class UAnnotationSignalHolder(QWidget):
    added_new_annotation = pyqtSignal(int, object)
    deleted_annotation = pyqtSignal(int, int, object)
    updated_annotation = pyqtSignal(int, int, object, object)
    display_annotations = pyqtSignal(list)
    selected_annotation = pyqtSignal(int)

    selected_thumbnail = pyqtSignal(tuple, int)
    displayed_image = pyqtSignal(str)

    change_status_thumbnail = pyqtSignal(EAnnotationStatus, EAnnotationStatus)
    change_work_mode = pyqtSignal(int)
    changed_class_annotate = pyqtSignal(int)

    increase_annotated_counter = pyqtSignal()
    decrease_annotated_counter = pyqtSignal()

    def __init__(self):
        super().__init__()

class UGlobalSignalHolder(QObject):
    ctrl_pressed = pyqtSignal(int)
    ctrl_released = pyqtSignal(int)

    arrows_pressed = pyqtSignal(int)
    drop_pressed = pyqtSignal()
    delete_pressed = pyqtSignal(int)

    classes_updated = pyqtSignal()
    loaded_images_to_annotate = pyqtSignal(list)

    command_key_pressed = pyqtSignal(int)
    number_key_pressed = pyqtSignal(int)

    project_load_complete = pyqtSignal()
    project_updated_datasets = pyqtSignal()

    model_loaded = pyqtSignal()
    model_unloaded = pyqtSignal()

    go_to_page_annotation = pyqtSignal()
    go_to_page_datasets = pyqtSignal()

    # str - путь к папке, куда экспортируется
    # list - список датасетов, которые нужно экспортировать
    # object - словарь для рефактора классов, может быть None
    start_export = pyqtSignal(str, list, object)

    def __init__(self):
        super().__init__()

        self.status: ECommanderStatus = ECommanderStatus.LoadModel

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
        self.is_blocked = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if self.is_blocked is True:
                return super().eventFilter(obj, event)

            # Реализация обработки клавиш, в случае, если выбрана страница с разметкой
            if self.status.value == ECommanderStatus.Annotation.value:
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

                if  Qt.Key_0 <= event.key() <= Qt.Key_9:
                    self.number_key_pressed.emit(event.key())
                    return True

                if event.key() == Qt.Key_Space:
                    self.command_key_pressed.emit(Qt.Key_Space)
                    return True

                if event.key() == Qt.Key_N:
                    self.drop_pressed.emit()
                    self.arrows_pressed.emit(Qt.Key_Right)
                    self.delay_timer.start()
                    if self.freq_timer.isActive():
                        self.freq_timer.stop()
                    return True

                if event.key() == Qt.Key_Delete:
                    self.delete_pressed.emit(event.key())
                    return True

        elif event.type() == QEvent.KeyRelease:
            if self.is_blocked is True:
                return super().eventFilter(obj, event)

            if self.status.value == ECommanderStatus.Annotation.value:
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

    def set_block(self, block: float):
        self.is_blocked = block

    def set_status(self, status: ECommanderStatus):
        self.status = status

    def get_status(self):
        return self.status

    def on_freq(self):
        if (self.current_key == Qt.Key_Left or self.current_key == Qt.Key_Right or
            self.current_key == Qt.Key_A or self.current_key == Qt.Key_D):
            self.arrows_pressed.emit(self.current_key)
        elif self.current_key == Qt.Key_N:
            self.drop_pressed.emit()
            self.arrows_pressed.emit(Qt.Key_Right)