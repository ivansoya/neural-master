import os
import shutil
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

from project import UTrainProject
from utility import FAnnotationItem, FAnnotationData

class UOverlayLoader(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.label_dataset = QLabel("Загрузка данных...", self)
        self.label_dataset.setStyleSheet("color: white; font-size: 16px;")

        self.label_annotation = QLabel("Пожалуйста, подождите", self)
        self.label_annotation.setStyleSheet("color: white; font-size: 14px;")

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                text-align: center;
            }
            """
        )

        layout.addWidget(self.label_dataset)
        layout.addWidget(self.label_annotation)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def update_label_dataset(self, text: str, current: int, count: int):
        self.label_dataset.setText(f"Загрузка датасета {text}: {current} из {count}")

    def update_label_annotation(self, text: str):
        self.label_annotation.setText(text)

    def update_progress(self, label: str, current: int, count: int):
        self.label_annotation.setText(label)
        self.progress_bar.setValue(int(float(current) / count * 100))

class UDatasetCopyToProject(QThread):
    signal_on_copy = pyqtSignal(str, int, int)
    signal_on_ended = pyqtSignal(str)
    signal_on_error = pyqtSignal(str)

    def __init__(self, path_to_dataset, project: UTrainProject):
        super().__init__()

        self.project = project
        self.path_to_dataset = path_to_dataset

    def copy(self):
        try:
            path_to_images = os.path.join(self.path_to_dataset, "images").replace('\\', '/')
            path_to_labels = os.path.join(self.path_to_dataset, "labels").replace('\\', '/')

            dataset_path_new = os.path.join(self.project.path, os.path.basename(self.path_to_dataset)).replace('\\','/')
            images_path_new = os.path.join(str(dataset_path_new), "images").replace('\\', '/')
            labels_path_new = os.path.join(str(dataset_path_new), "labels").replace('\\', '/')

            os.makedirs(dataset_path_new, exist_ok=False)
            os.makedirs(images_path_new, exist_ok=False)
            os.makedirs(labels_path_new, exist_ok=False)

            current = 1
            labels_to_copy = [file for file in os.listdir(path_to_labels) if file.endswith(".txt")]
            for label in labels_to_copy:
                shutil.copy(
                    os.path.join(path_to_labels, label).replace('\\', '/'),
                    labels_path_new
                )
                self.signal_on_copy.emit(label, current, len(labels_to_copy))
                current += 1

            current = 1
            images_to_copy = [file for file in os.listdir(path_to_images) if file.endswith((".png", ".jpg", ".jpeg"))]
            for image in images_to_copy:
                shutil.copy(
                    os.path.join(path_to_images, image).replace('\\', '/'),
                    images_path_new
                )
                self.signal_on_copy.emit(image, current, len(images_to_copy))
                current += 1

            self.project.datasets.append(os.path.basename(self.path_to_dataset))
            self.signal_on_ended.emit(os.path.basename(self.path_to_dataset))

        except Exception as error:
            self.signal_on_error.emit(str(error))
            return

class UProjectAnnotationLoader(QThread):
    signal_start_dataset = pyqtSignal(str, int, int)
    signal_loaded_label = pyqtSignal(str, int, int)
    signal_end_load = pyqtSignal()
    signal_error = pyqtSignal(str)
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
            self.signal_warning.emit(f"Warning в UProjectAnnotationLoader.load_annotations!"
                                     f"В проекте нет датасетов!")
            self.signal_end_load.emit()
            return
        self.current_dataset = 1
        for dataset in self.input_datasets:
            if dataset not in self.project.datasets:
                self.signal_warning(f"Warning в UProjectAnnotationLoader.load_annotations!"
                                    f"Датасет отсутствует {dataset} в проекте!")
                continue
            image_path = os.path.join(self.project.path, dataset, "images").replace('\\', '/')
            label_path = os.path.join(self.project.path, dataset, "labels").replace('\\', '/')
            labels = [file for file in os.listdir(label_path) if file.endswith(".txt")]
            images = [image for image in os.listdir(image_path) if image.endswith((".png", ".jpg", ".jpeg"))]
            self.count_labels = len(labels)
            if self.count_labels == 0:
                self.signal_warning.emit(f"Warning в UProjectAnnotationLoader.load_annotations!"
                                         f"В датасете {dataset} отсутствуют аннотации!")
                continue
            self.current_labels = 1
            self.signal_start_dataset.emit(dataset, self.current_dataset, self.count_datasets)
            for label in labels:
                for image in images:
                    if image.split('.')[0] == label.split('.')[0]:
                        error = self.read_annotation(
                            dataset,
                            os.path.join(label_path, label).strip().replace('\\', '/'),
                            os.path.join(image_path, image).strip().replace('\\', '/'),
                        )
                        if error:
                            self.signal_error.emit(f"Ошибка в UProjectAnnotationLoader.load_annotations! {error}")
                            self.signal_end_load.emit()
                            return
                        self.signal_loaded_label(label, self.current_labels, self.count_labels)
                        images.remove(image)
                        continue
                self.current_labels += 1
            self.current_dataset += 1
        self.signal_end_load.emit()

    def read_annotation(self, dataset: str, filename: str, image_path: str, iio=None):
        try:
            image_data = iio.immeta(image_path)
            width_res, height_res = image_data["size"]
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
                    width = int(values[3])
                    height = int(values[4])

                    ann_list.append(
                        FAnnotationData(x, y, width, height, id_class, width_res, height_res)
                    )
                ann_item = FAnnotationItem(ann_list, image_path)
            if ann_item:
                error = self.project.add_annotation_to_dataset(dataset, ann_item)
                if error:
                    return error
                return
        except Exception as error:
            return f"{str(error)}"