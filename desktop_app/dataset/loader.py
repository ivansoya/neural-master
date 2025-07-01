import os
import shutil
import imageio.v3 as iio

from PyQt5.QtCore import QThread, pyqtSignal

from project import UTrainProject, DATASETS, RESERVED, LABELS_SEGM, LABELS, IMAGES
from supporting.functions import from_polygons_to_bbox
from utility import FAnnotationItem, FAnnotationData


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

        self.labels_count = 0
        self.current_labels = 0

    def run(self):
        is_run_reserved = False
        if self.input_datasets is None:
            self.input_datasets = self.project.get_datasets()
            is_run_reserved = True
        if len(self.input_datasets) == 0:
            if not (is_run_reserved and len(self.project.reserved) != 0):
                self.signal_warning.emit(f"Warning в UThreadDatasetLoadAnnotations.load_annotations!"
                                         f"В проекте нет датасетов!")
                self.signal_end_load.emit(self.input_datasets)
                return

        self.current_dataset = 1
        self.process_dataset_list(self.input_datasets, DATASETS)

        if is_run_reserved:
            self.process_dataset_list(self.project.get_reserved(), RESERVED)

        self.signal_end_load.emit(self.input_datasets)

    def process_dataset_list(self, dataset_list: list[str], type_dataset: str):
        count_datasets = len(dataset_list)
        for dataset in dataset_list:
            if not((dataset in self.project.datasets) or (dataset in self.project.reserved)):
                self.signal_warning.emit(f"Warning в UThreadDatasetLoadAnnotations.load_annotations!"
                                    f"Датасет отсутствует {dataset} в проекте!")
                continue

            # Получение списка файлов аннотаций
            image_path = str(os.path.join(self.project.path, type_dataset, dataset, IMAGES).replace('\\', '/'))
            label_types = [LABELS, LABELS_SEGM]
            label_files = []
            for label_type in label_types:
                label_path = str(os.path.join(self.project.path, type_dataset, dataset, label_type).replace('\\', '/'))
                if os.path.isdir(label_path):
                    label_files += [os.path.join(label_path, file).strip().replace('\\', '/')
                                    for file in os.listdir(label_path) if file.endswith(".txt")
                                    ]

            self.labels_count = len(label_files)
            if self.labels_count == 0:
                self.signal_warning.emit(f"Warning в UThreadDatasetLoadAnnotations.load_annotations!"
                                         f"В датасете {dataset} отсутствуют аннотации!")
                continue
            self.signal_start_dataset.emit(dataset, self.current_dataset, count_datasets)

            current_labels = 1
            for label in label_files:
                image_name = os.path.splitext(os.path.basename(label))[0]
                image_file = None

                for ext in self.project.image_extensions:
                    candidate = os.path.join(image_path, image_name + ext).strip().replace('\\', '/')
                    if os.path.exists(candidate):
                        image_file = candidate
                        break

                if image_file is None:
                    print(f"Не найдено изображение для {label}")
                    continue

                error = self.read_annotation(
                    dataset,
                    type_dataset,
                    label.strip().replace('\\', '/'),
                    image_file.strip().replace('\\', '/'),
                )
                if error:
                    self.signal_error.emit(dataset,
                                           f"Ошибка в UThreadDatasetLoadAnnotations.load_annotations! {error}")
                    return

                self.signal_loaded_label.emit(image_name, current_labels, self.labels_count)
                current_labels += 1

            self.current_dataset += 1

    def read_annotation(self, dataset: str, type_dataset: str, filename: str, image_path: str):
        try:
            image_data = iio.immeta(image_path)
            width_res, height_res = image_data["shape"]
            with open(filename, "r") as file:
                ann_list: list[FAnnotationData] = list()
                line_count = 1

                folder_name = os.path.basename(os.path.dirname(filename))
                if folder_name == LABELS:
                    for line in file:
                        values = line.strip().split()
                        if len(values) != 5:
                            continue

                        id_class = int(values[0])
                        x = max(0, min(int(float(values[1]) * width_res), width_res))
                        y = max(0, min(int(float(values[2]) * height_res), height_res))
                        width = int(float(values[3]) * width_res)
                        height = int(float(values[4]) * height_res)
                        color = self.project.classes.get_color(id_class)
                        class_name = self.project.classes.get_name(id_class)

                        ann_list.append(
                            FAnnotationData(
                                line_count,
                                [int(x - width // 2), int(y - height // 2), width, height],
                                [],
                                id_class,
                                class_name,
                                color,
                                width_res,
                                height_res
                            )
                        )
                        line_count += 1
                elif folder_name == LABELS_SEGM:
                    for line in file:
                        values = line.strip().split()
                        if len(values) < 7 or len(values) % 2 == 0:
                            continue

                        id_class = int(values[0])
                        color = self.project.classes.get_color(id_class)
                        class_name = self.project.classes.get_name(id_class)
                        point_list = [
                            float(values[i]) * width_res if i % 2 == 1 else float(values[i]) * height_res
                            for i in range(1, len(values))
                        ]

                        ann_list.append(
                            FAnnotationData(
                                line_count,
                                from_polygons_to_bbox([point_list]),
                                [point_list],
                                id_class,
                                class_name,
                                color,
                                width_res,
                                height_res
                        ))
                else:
                    return "Error"
                ann_item = FAnnotationItem(ann_list, image_path, dataset)
                error = self.project.add_annotation(dataset, ann_item, type_dataset)
                if error:
                    return error

        except Exception as error:
            if os.path.exists(image_path):
                error = self.project.add_annotation(
                    dataset,
                    FAnnotationItem([], image_path, 1, dataset),
                    type_dataset
                )
                if error:
                    return error
            else:
                return f"{str(error)}"