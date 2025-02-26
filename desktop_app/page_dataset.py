import os.path
from typing import Optional

from PyQt5.QtWidgets import QWidget, QStackedWidget, QListWidget, QFileDialog, QMessageBox

from commander import UGlobalSignalHolder
from design.dataset_page import Ui_page_dataset
from design.widget_dataset_item import Ui_widget_dataset_item
from loader import UOverlayLoader, UProjectAnnotationLoader, UDatasetCopyToProject
from project import UTrainProject
from utility import UMessageBox


class UPageDataset(QWidget, Ui_page_dataset):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject):
        super().__init__()
        self.setupUi(self)

        self.commander = commander
        self.project = project

        # Дополнительные виджеты
        self.overlay: Optional[UOverlayLoader] = None
        self.thread_load_annotations: Optional[UProjectAnnotationLoader] = None
        self.thread_copy: Optional[UDatasetCopyToProject] = None

        # Привязка к кнопкам
        self.button_to_annotation_scene.clicked.connect(self.get_to_annotation_page)
        self.button_add_dataset.clicked.connect(self.add_dataset)

    def get_to_annotation_page(self):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(2)

    def add_dataset(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку с датасетом", "")
        if not path:
            return
        dataset_name = os.path.basename(path)
        if dataset_name in self.project.datasets:
            UMessageBox.show_error(f"Данный датасет {dataset_name} уже есть в проекте!")
            return
        classes_path = os.path.join(path, "classes.txt").replace('\\', '/')
        if any(
            not os.path.exists(os.path.join(path, folder).replace('\\', '/'))
            for folder in ["images", "labels"]
        ) or not os.path.exists(classes_path) or not os.path.isfile(classes_path):
            UMessageBox.show_error(f"Выбранный датасет {dataset_name} не валидный!")
            return

        with open(classes_path, "r") as file:
            classes_list = [line.strip() for line in file]

        if classes_list != [cls.Name for cls in self.project.classes]:
            UMessageBox.show_error(f"Классы выбранного датасета не совпадают с классами проекта!")
            return

        if self.overlay or self.thread_load_annotations or self.thread_copy:
            return

        self.overlay = UOverlayLoader(self)
        self.overlay.show()

        self.thread_copy = UDatasetCopyToProject(path, self.project)

        self.thread_copy.signal_on_copy.connect(self.overlay.update_progress)
        self.thread_copy.signal_on_error.connect(UPageDataset.print_error)
        self.thread_copy.signal_on_ended.connect(self.load_annotations)

        self.thread_copy.run()

    def load_annotations(self, dataset_name: str):
        if self.thread_copy:
            self.thread_copy.deleteLater()
            self.thread_copy = None

        if self.overlay is None:
            UMessageBox.show_error("Не удается найти объект UOverlayLoader! Невозможно загрузить аннотации!")
            return

        self.thread_load_annotations = UProjectAnnotationLoader(self.project, [dataset_name])
        self.thread_load_annotations.signal_start_dataset.connect(self.overlay.update_label_dataset)
        self.thread_load_annotations.signal_loaded_label.connect(self.overlay.update_progress)
        self.thread_load_annotations.signal_end_load.connect(self.end_add_dataset)

        self.thread_load_annotations.signal_error.connect(UPageDataset.print_error)
        self.thread_load_annotations.signal_warning.connect(UPageDataset.print_warning)

        self.thread_load_annotations.run()

    def end_add_dataset(self):
        if self.thread_load_annotations:
            self.thread_load_annotations.deleteLater()
            self.thread_load_annotations = None

        UMessageBox.show_error("Датасет был успешно добавлен в проект и загружен!", "Успех!", QMessageBox.Ok)

        if self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None

    @staticmethod
    def print_error(error_str: str):
        UMessageBox.show_error(error_str)

    @staticmethod
    def print_warning(error_str: str):
        UMessageBox.show_error(str, "Предупреждение!", QMessageBox.Warning)


class UListDataset(QListWidget):
    def __init__(self, parent = None):
        super().__init__(parent)

class UItemDataset(QWidget, Ui_widget_dataset_item):
    def __init__(self, path: str, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.label_name.setText(os.path.basename(path))

