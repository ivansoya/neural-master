import os.path
import shutil
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import QWidget, QStackedWidget, QListWidget, QFileDialog, QMessageBox, QListWidgetItem

from commander import UGlobalSignalHolder
from design.dataset_page import Ui_page_dataset
from image_gallery import UAnnotationImage
from list_datasets import UItemDataset, UListDataset
from loader import UOverlayLoader, UThreadDatasetLoadAnnotations, UThreadDatasetCopy
from project import UTrainProject, RESERVED, DATASETS
from utility import UMessageBox, FAnnotationItem, FAnnotationClasses


class UThreadDisplayDataset(QThread):
    signal_on_image_loaded = pyqtSignal(object)
    signal_on_progress_changed = pyqtSignal(str, int, int)
    signal_on_ended = pyqtSignal()
    signal_on_error = pyqtSignal(str)

    def __init__(self,
                 classes: FAnnotationClasses,
                 annotations: dict[str, list[FAnnotationItem]],
                 image_size: int = 200
    ):
        super().__init__()

        self.annotations = annotations
        self.size = image_size
        self.ann_len = sum(len(ann) for ann in self.annotations.values())
        self.classes = classes

    def run(self):
        indicator = 1
        for dataset, annotation_data in self.annotations.items():
            for index in range(len(annotation_data)):
                data, image_path = self.annotations[dataset][index].get_item_data()
                annotation_list = list()
                for annotation in data:
                    color, error = self.classes.get_color(annotation.ClassID)
                    annotation_list.append((annotation.X, annotation.Y, annotation.Width, annotation.Height, color))
                image_temp: UAnnotationImage = UAnnotationImage(image_path, dataset, annotation_list, self.size)
                self.signal_on_image_loaded.emit(image_temp)
                indicator += 1
                self.signal_on_progress_changed.emit(image_path, indicator, self.ann_len)
        self.signal_on_ended.emit()

class UPageDataset(QWidget, Ui_page_dataset):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject):
        super().__init__()
        self.setupUi(self)

        self.commander = commander
        self.project = project

        # Дополнительные параметры

        # Дополнительные виджеты
        self.overlay: Optional[UOverlayLoader] = None
        self.thread_load_annotations: Optional[UThreadDatasetLoadAnnotations] = None
        self.thread_copy: Optional[UThreadDatasetCopy] = None
        self.thread_display: Optional[UThreadDisplayDataset] = None

        # Привязка к кнопкам
        self.button_to_annotation_scene.clicked.connect(self.get_to_annotation_page)
        self.button_add_dataset.clicked.connect(self.add_dataset)

        self.list_datasets.signal_on_item_clicked.connect(self.start_thread_display_at_gallery)
        self.list_reserved.signal_on_item_clicked.connect(self.start_thread_display_at_gallery)

        self.button_move_dataset_to_reserved.clicked.connect(self.move_dataset_to_reserved)

        # Привязка к событиям
        if self.commander:
            self.commander.project_load_complete.connect(self.create_list_dataset)

    def get_to_annotation_page(self):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(2)

    def start_thread_display_at_gallery(self, annotations: dict[str, list[FAnnotationItem]]):
        if self.overlay or (self.thread_display and self.thread_display.isRunning()):
            UMessageBox.show_error(
                "Невозможно запустить процесс отображения изображений! В текущее время он уже работает!"
            )
            return

        self.overlay = UOverlayLoader(self.dataset_display)

        try:
            self.view_gallery.clear_scene()
        except Exception as error:
            self.overlay = UOverlayLoader.delete_overlay(self.overlay)
            UMessageBox.show_error(str(error))
            return

        self.thread_display = UThreadDisplayDataset(self.project.classes, annotations, self.view_gallery.get_cell_size())
        self.thread_display.signal_on_image_loaded.connect(self.display_image_at_gallery)
        self.thread_display.signal_on_progress_changed.connect(self.overlay.update_progress)
        self.thread_display.signal_on_ended.connect(self.on_ended_thread_display)
        self.thread_display.signal_on_error.connect(self.on_error_thread_display)

        self.thread_display.run()

    def display_image_at_gallery(self, gallery_item):
        if isinstance(gallery_item, UAnnotationImage):
            self.view_gallery.add_item(gallery_item)

    def on_ended_thread_display(self):
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)
        self.view_gallery.update_visibility(force=True)

    def on_error_thread_display(self, error_msg: str):
        UMessageBox.show_error(error_msg)
        self.overlay = UOverlayLoader.detete_overlay(self.overlay)

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

        if classes_list != [cls.Name for cls in self.project.classes.get_all_classes()]:
            UMessageBox.show_error(f"Классы выбранного датасета не совпадают с классами проекта!")
            return

        if (self.overlay or
            (self.thread_copy and self.thread_copy.isRunning()) or
            (self.thread_load_annotations and self.thread_load_annotations.isRunning())
        ):
            return

        self.overlay = UOverlayLoader(self.dataset_display)

        self.thread_copy = UThreadDatasetCopy(self.project, path)

        self.thread_copy.signal_on_copy.connect(self.overlay.update_progress)
        self.thread_copy.signal_on_error.connect(self.make_error_with_copy)
        self.thread_copy.signal_on_ended.connect(self.load_annotations)

        self.thread_copy.start()

    def load_annotations(self, dataset_name: str):
        if self.thread_copy:
            self.thread_copy.deleteLater()
            self.thread_copy = None

        if self.overlay is None:
            UMessageBox.show_error("Не удается найти объект UOverlayLoader! Невозможно загрузить аннотации!")
            return

        self.project.add_dataset(dataset_name)

        self.thread_load_annotations = UThreadDatasetLoadAnnotations(self.project, [dataset_name])
        self.thread_load_annotations.signal_start_dataset.connect(self.overlay.update_label_dataset)
        self.thread_load_annotations.signal_loaded_label.connect(self.overlay.update_progress)
        self.thread_load_annotations.signal_end_load.connect(self.end_add_dataset)

        self.thread_load_annotations.signal_error.connect(self.make_error_with_load_annotations)
        self.thread_load_annotations.signal_warning.connect(UPageDataset.print_warning)

        self.thread_load_annotations.start()

    def end_add_dataset(self, datasets: list[str]):
        error = self.project.save()
        if error:
            UMessageBox.show_error(error)
        else:
            UMessageBox.show_error("Датасет был успешно добавлен в проект и загружен!", "Успех!", int(QMessageBox.Ok))
        # Обновление списка датасетов
        self.list_datasets.clear()
        self.create_list_dataset()
        self.close_overlay()

    def make_error_with_load_annotations(self, dataset: str, error_str: str):
        UMessageBox.show_error(error_str)

        self.project.remove_dataset(dataset)
        self.project.remove_all_annotations_from_dataset(dataset)
        self.project.remove_project_folder(dataset)

        self.close_overlay()

    def move_dataset_to_reserved(self):
        if self.overlay or (self.thread_copy and self.thread_copy.isRunning()):
            return

        dataset_item = UListDataset.get_item_widget(self.list_reserved)
        if not dataset_item or not dataset_item.name in self.project.datasets:
            return
        path_to_dataset_target = os.path.join(self.project.path, DATASETS, dataset_item.name).replace('\\', '/')

        self.overlay = UOverlayLoader(self.dataset_display)

        self.thread_copy = UThreadDatasetCopy(self.project, path_to_dataset_target, RESERVED)

        self.thread_copy.signal_on_copy.connect(self.overlay.update_progress)
        self.thread_copy.signal_on_error.connect(self.make_error_with_copy)
        self.thread_copy.signal_on_ended.connect(self.end_moving_dataset_to_reserved)

        self.thread_copy.start()

    def end_moving_dataset_to_reserved(self, dataset_name: str):
        self.overlay = UOverlayLoader.delete_overlay(self.overlay)

        self.create_list_reserved()
        self.create_list_dataset()

        self.project.remove_project_folder(dataset_name, RESERVED)

    def create_list_reserved(self):
        for dataset in self.project.reserved:
            try:
                reserved_temp = {dataset: self.project.get_reserved_annotations()[dataset]}
                self.list_reserved.add_dataset_item(
                    UItemDataset(
                        dataset,
                        reserved_temp
                    )
                )
            except Exception as error:
                return str(error)

    def create_list_dataset(self):
        # Создание общего предмета
        sum_len = sum(len(ann_list) for ann_list in self.project.current_annotations.values())
        if sum_len == 0:
            return
        all_item = UItemDataset(
            "All annotations",
            self.project.current_annotations
        )
        self.list_datasets.add_dataset_item(all_item)

        # Создание отдельных датасетов
        for dataset in self.project.datasets:
            try:
                annotation_temp = {dataset: self.project.get_current_annotations()[dataset]}
                self.list_datasets.add_dataset_item(
                    UItemDataset(
                        dataset,
                        annotation_temp
                    )
                )
            except Exception as error:
                return str(error)

    def make_error_with_copy(self, error_str: str):
        UMessageBox.show_error(error_str)
        self.close_overlay()

    @staticmethod
    def print_warning(error_str: str):
        UMessageBox.show_error(error_str, "Предупреждение!", QMessageBox.Warning)

    def close_overlay(self):
        if self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None