import os
import shutil
from typing import Optional
import imageio.v3 as iio

from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QPixmap
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

from project import UTrainProject, DATASETS
from utility import FAnnotationItem, FAnnotationData

class UOverlayLoader(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setParent(parent)
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.label_dataset = QLabel("Загрузка данных...", self)
        self.label_dataset.setAlignment(Qt.AlignCenter)
        self.label_dataset.setStyleSheet("color: white; font-size: 16px;")

        self.label_annotation = QLabel("Пожалуйста, подождите", self)
        self.label_annotation.setAlignment(Qt.AlignCenter)
        self.label_annotation.setStyleSheet("color: white; font-size: 14px;")

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("text-align: center;")

        layout.addWidget(self.label_dataset)
        layout.addWidget(self.label_annotation)
        layout.addWidget(self.progress_bar)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Создаем QPixmap для overlay
        self.pixmap = QPixmap(self.size())
        self.pixmap.fill(QColor(0, 0, 0, 200))  # Заполняем прозрачным фоном

        self.setLayout(layout)
        self.raise_()
        self.show()
        self.update()

    def update_label_dataset(self, text: str, current: int, count: int):
        self.label_dataset.setText(f"Загрузка датасета {text}: {current} из {count}")

    def update_label_annotation(self, text: str):
        self.label_annotation.setText(text)

    def update_progress(self, label: str, current: int, count: int):
        self.label_annotation.setText(label)
        self.progress_bar.setValue(int(float(current) / count * 100))

    def resizeEvent(self, event):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.update()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)
        painter.end()

    @staticmethod
    def delete_overlay(overlay: 'UOverlayLoader'):
        if overlay:
            overlay.hide()
            overlay.deleteLater()
            return None
        return overlay

class UThreadDatasetCopy(QThread):
    signal_on_copy = pyqtSignal(str, int, int)
    signal_on_ended = pyqtSignal(str)
    signal_on_error = pyqtSignal(str)

    def __init__(self, project: UTrainProject, source_dataset_path, target_copy_type: str = DATASETS):
        super().__init__()

        self.project = project
        self.source_dataset_path = source_dataset_path
        self.target_copy_type = target_copy_type

    def run(self):
        try:
            path_to_images = os.path.join(self.source_dataset_path, "images").replace('\\', '/')
            path_to_labels = os.path.join(self.source_dataset_path, "labels").replace('\\', '/')

            dataset_path_new = os.path.join(self.project.path, self.target_copy_type, os.path.basename(self.source_dataset_path)).replace('\\', '/')
            images_path_new = os.path.join(str(dataset_path_new), "images").replace('\\', '/')
            labels_path_new = os.path.join(str(dataset_path_new), "labels").replace('\\', '/')

            os.makedirs(dataset_path_new, exist_ok=False)
            os.makedirs(images_path_new, exist_ok=False)
            os.makedirs(labels_path_new, exist_ok=False)

            self.go_folder(path_to_labels, labels_path_new, ".txt")

            self.go_folder(path_to_images, images_path_new, (".png", ".jpg", ".jpeg"))

            self.signal_on_ended.emit(os.path.basename(self.source_dataset_path))

        except Exception as error:
            self.signal_on_error.emit(str(error))
            return

    def go_folder(self, path_to_folder: str, new_path: str, extensions: str | tuple[str, ...]):
        current, percentage = 1, 1
        folder_to_copy = [file for file in os.listdir(path_to_folder) if file.endswith(extensions)]
        for label in folder_to_copy:
            shutil.copy2(
                os.path.join(path_to_folder, label).replace('\\', '/'),
                new_path
            )
            t_p = int(float(current) / len(folder_to_copy) * 100)
            if t_p > percentage:
                self.signal_on_copy.emit(label, current, len(folder_to_copy))
                percentage = t_p
            current += 1

class UThreadDatasetLoadAnnotations(QThread):
    signal_start_dataset = pyqtSignal(str, int, int)
    signal_loaded_label = pyqtSignal(str, int, int)
    signal_end_load = pyqtSignal(list)
    signal_error = pyqtSignal(str, str)
    signal_warning = pyqtSignal(str)

    def __init__(self, project: UTrainProject, input_datasets: list[str] = None):
        super().__init__()

        self.project = project
        self.input_datasets = input_datasets

        self.count_datasets = 0
        self.current_dataset = 0

        self.count_labels = 0
        self.current_labels = 0

    def run(self):
        if self.input_datasets is None:
            self.input_datasets = self.project.datasets
        self.count_datasets = len(self.input_datasets)
        if self.count_datasets == 0:
            self.signal_warning.emit(f"Warning в UThreadDatasetLoadAnnotations.load_annotations!"
                                     f"В проекте нет датасетов!")
            self.signal_end_load.emit()
            return
        self.current_dataset = 1
        for dataset in self.input_datasets:
            if dataset not in self.project.datasets:
                self.signal_warning.emit(f"Warning в UThreadDatasetLoadAnnotations.load_annotations!"
                                    f"Датасет отсутствует {dataset} в проекте!")
                continue
            try:
                image_path = str(os.path.join(self.project.path, DATASETS, dataset, "images").replace('\\', '/'))
                label_path = str(os.path.join(self.project.path, DATASETS, dataset, "labels").replace('\\', '/'))
            except Exception as error:
                self.signal_error.emit(dataset, str(error))
                return
            labels = [file for file in os.listdir(label_path) if file.endswith(".txt")]
            images = [image for image in os.listdir(image_path) if image.endswith((".png", ".jpg", ".jpeg"))]
            self.count_labels = len(labels)
            if self.count_labels == 0:
                self.signal_warning.emit(f"Warning в UThreadDatasetLoadAnnotations.load_annotations!"
                                         f"В датасете {dataset} отсутствуют аннотации!")
                continue
            self.current_labels = 1
            self.signal_start_dataset.emit(dataset, self.current_dataset, self.count_datasets)
            percentage = 1
            for label in labels:
                for image in images:
                    if image.split('.')[0] == label.split('.')[0]:
                        error = self.read_annotation(
                            dataset,
                            os.path.join(label_path, label).strip().replace('\\', '/'),
                            os.path.join(image_path, image).strip().replace('\\', '/'),
                        )
                        if error:
                            self.signal_error.emit(dataset, f"Ошибка в UThreadDatasetLoadAnnotations.load_annotations! {error}")
                            return
                        images.remove(image)
                        t_p = int(float(self.current_labels) / self.count_labels * 100)
                        if t_p > percentage:
                            self.signal_loaded_label.emit(label, self.current_labels, self.count_labels)
                            percentage = t_p
                        continue
                self.current_labels += 1
            self.current_dataset += 1
        self.signal_end_load.emit(self.input_datasets)

    def read_annotation(self, dataset: str, filename: str, image_path: str):
        try:
            image_data = iio.immeta(image_path)
            width_res, height_res = image_data["shape"]
            ann_item: Optional[FAnnotationItem] = None
            with open(filename, "r") as file:
                ann_list: list[FAnnotationData] = list()
                for line in file:
                    values = line.strip().split()
                    if len(values) != 5:
                        continue
                    id_class = int(values[0])
                    x = max(0, min(int(float(values[1]) * width_res), width_res))
                    y = max(0, min(int(float(values[2]) * height_res), height_res))
                    width = int(float(values[3]) * width_res)
                    height = int(float(values[4]) * height_res)

                    ann_list.append(
                        FAnnotationData(x, y, width, height, id_class, width_res, height_res)
                    )
                ann_item = FAnnotationItem(ann_list, image_path)
            if ann_item:
                error = self.project.add_annotation(dataset, ann_item)
                if error:
                    return error
                return
        except Exception as error:
            return f"{str(error)}"