import os.path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QStackedWidget, QFileDialog, QDialog, QMessageBox

from dataset.loader import UThreadDatasetLoadAnnotations, UOverlayLoader
from commander import UGlobalSignalHolder
from design.page_save_load import Ui_page_load_dataset
from design.window_create_project import Ui_window_create_project
from project import UTrainProject
from utility import UMessageBox


class UPageLoader(QWidget, Ui_page_load_dataset):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject):
        super().__init__()
        self.setupUi(self)

        self.commander = commander
        self.project = project

        self.thread_load: Optional[UThreadDatasetLoadAnnotations] = None
        self.overlay: Optional[UOverlayLoader] = None

        self.button_create_train_project.clicked.connect(self.create_project)
        self.button_load_train_project.clicked.connect(self.load_project)
        self.button_skip_creation.clicked.connect(lambda: self.go_to_another_page(2))

    def go_to_another_page(self, page_index = 1):
        if isinstance(self.parent(), QStackedWidget):
            if page_index >= self.parent().count():
                QDialogCreateProject.show_error(f"Невозможно перейти на страницу под номером {page_index}")
                return
            self.parent().setCurrentIndex(page_index)

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть существующий проект", "*.cfg", "Все файлы (*)")
        if not file_path:
            QDialogCreateProject.show_error("Ошибка! Невозможно открыть проект!")
            return

        error = self.project.load(file_path)
        if error:
            QDialogCreateProject.show_error(error)
            return
        else:
            if self.overlay or (self.thread_load and self.thread_load.isRunning()):
                QDialogCreateProject.show_error("Невозможно загрузить датасеты. Уже идет загрузка датасетов!")
                return

            self.overlay = UOverlayLoader(self)

            self.thread_load = UThreadDatasetLoadAnnotations(self.project)

            self.thread_load.signal_start_dataset.connect(self.overlay.update_label_dataset)
            self.thread_load.signal_loaded_label.connect(self.overlay.update_progress)
            self.thread_load.signal_end_load.connect(self.on_end_load)
            self.thread_load.signal_error.connect(self.on_error_load)
            self.thread_load.signal_warning.connect(
                lambda error_str:UMessageBox.show_warning(error_str)
            )

            self.thread_load.start()

    def on_error_load(self, dataset: str, error: str):
        self.project.remove_all_annotations_from_dataset(dataset)
        UMessageBox.show_error(error)

        self.overlay = UOverlayLoader.delete_overlay(self.overlay)

    def on_end_load(self, datasets: list[str]):
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.commander.project_load_complete.emit()
        UMessageBox.show_ok("Датасеты загружены!")

    def create_project(self):
        self.commander.set_block(True)
        dialog_create_project = QDialogCreateProject(self.project)
        dialog_create_project.on_end.connect(self.unlock_commander)

        dialog_create_project.exec()
        pass

    def unlock_commander(self):
        self.commander.set_block(False)
        self.commander.project_load_complete.emit()

class QDialogCreateProject(QDialog, Ui_window_create_project):
    on_end = pyqtSignal()

    def __init__(self, project : UTrainProject, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.project = project

        self.project_name: str = ""
        self.project_path: str = ""
        self.project_classes: list[str] = list()

        self.button_choose_project_path.clicked.connect(self.choose_file_path)
        self.button_add_class.clicked.connect(self.add_class)
        self.button_load_classes.clicked.connect(self.choose_classes)
        self.button_create_project.clicked.connect(self.create_project)

    def create_project(self):
        if not self.lineedit_project_name.text():
            QDialogCreateProject.show_error("Должно быть указано имя проекта!")
            return
        if len(self.lineedit_project_name.text()) < 6:
            QDialogCreateProject.show_error("Имя проекта должно быть не короче 6 символов!")
            return
        if not self.project_path or not os.path.exists(self.project_path):
            QDialogCreateProject.show_error("Укажите валидный путь к проекту!")
            return
        path_to_project_file = os.path.join(self.project_path, self.lineedit_project_name.text()).strip().replace('\\', '/') + ".cfg"
        if os.path.isfile(path_to_project_file):
            QDialogCreateProject.show_error("Данный проект уже существует!")
            return
        if len(self.project_classes) == 0:
            QDialogCreateProject.show_error("Укажите хотя бы один класс для создания проекта!")
            return

        error = self.project.create(
            self.project_path,
            self.lineedit_project_name.text(),
            self.project_classes
        )
        if error:
            QDialogCreateProject.show_error(error)

        self.close()

    def choose_file_path(self):
        folder_path = QFileDialog.getExistingDirectory(None, "Выберите папку для создания проекта!")
        if folder_path:
            self.project_path = folder_path.replace('\\', '/')
        else:
            QDialogCreateProject.show_error("Неверный путь к папке!")

    def choose_classes(self):
        file_classes, _ = QFileDialog.getOpenFileName(
            None, "Выберите файл со списком классов", "*.txt", "Все файлы (*)")
        if not file_classes or not os.path.isfile(file_classes):
            QDialogCreateProject.show_error("Файл с классами недействительный!")
            return

        current_classes: list[str] = list()
        try:
            with open(file_classes, "r") as opened_classes:
                for line in opened_classes.readlines():
                    if len(line) > 0:
                        current_classes.append(line.strip())
        except Exception as error:
            QDialogCreateProject.show_error(str(error))
            return

        self.project_classes = current_classes
        self.write_list_classes()

    def add_class(self):
        if not self.lineedit_add_class.text():
            QDialogCreateProject.show_error("Не указано название класса!")
            return
        if len(self.lineedit_add_class.text()) < 4:
            QDialogCreateProject.show_error("Длина названия класса не должна быть меньше 4 символов!")
            return
        if self.lineedit_add_class.text() in self.project_classes:
            QDialogCreateProject.show_error("Указанный класс уже есть в списке!")
            return
        self.project_classes.append(self.lineedit_add_class.text().strip().replace(' ', '-'))
        self.lineedit_add_class.clear()

        self.write_list_classes()

    def write_list_classes(self):
        self.browser_added_classes.clear()
        self.browser_added_classes.setPlainText(
            "\n".join(f"{i}: {item}" for i, item in enumerate(self.project_classes))
        )

    def close(self):
        self.on_end.emit()
        super().close()

    @staticmethod
    def show_error(text_error: str):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Ошибка!")
        msg.setText("Ошибка при создании проекта!")
        msg.setInformativeText(text_error)
        msg.setStandardButtons(QMessageBox.Ok)

        msg.exec()
