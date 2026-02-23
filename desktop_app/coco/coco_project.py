import os
import random
import shutil
from collections import defaultdict
from typing import Optional

import numpy as np
import yaml
from PyQt5.QtCore import QThread, QObject, pyqtSlot
from PyQt5.QtGui import QColor

from SAM2.sam2_net import USam2Net
from coco.coco_json import load_coco_json, make_coco_json, save_coco_json, make_annotation_dict_from_coco
from coco.coco_utility import UProjectInfo, UAnnotationClass, ECocoFileNames, EDefaultTrainName, IMAGES_DIR
from neural_model import URemoteNeuralNet, UBaseNeuralNet, ULocalDetectYOLO
from supporting.functions import rstrip, get_distinct_color
from supporting.task_runner import UTaskRunner
from utility import FAnnotationItem, FAnnotationData, UMessageBox


class UCocoProject:
    def __init__(self):

        self.annotations: dict[str, list[FAnnotationItem]] = {}
        self.annotation_classes: dict[int, UAnnotationClass] = {}

        self.project_info: Optional[UProjectInfo] = None
        self.project_path: Optional[str] = None

        self.current_image_id = 1
        self.current_annotation_id = 1
        self.current_class_id = 1

        # Поток обработки нейросети
        self.model_thread: Optional[QThread] = None
        self.model_worker: Optional[UBaseNeuralNet] = None

        # Поток SAM2
        self.sam2_thread: Optional[QThread] = None
        self.sam2_worker: Optional[USam2Net] = None

        self.load_sam2('SAM2/sam2.1_b.pt')

        self.image_extensions = [".jpg", ".jpeg", ".png"]

        # Дополнительный поток обработки
        self.task_runner: Optional[UTaskRunner] = None
        self.task_thread: Optional[QThread] = None

    def get_annotations(self):
        return self.annotations

    def get_classes(self):
        return self.annotation_classes

    def get_current_class_id(self):
        return self.current_class_id

    def get_project_name(self):
        return self.project_info.name if self.project_info is not None else "noname"

    def get_image_id(self):
        return self.current_image_id

    def get_image_id_with_increment(self):
        self.current_image_id = self.current_image_id + 1
        return self.current_image_id

    def get_annotation_id(self):
        return self.current_annotation_id

    def get_annotation_id_with_increment(self):
        self.current_annotation_id = self.current_annotation_id + 1
        return self.current_annotation_id

    def get_project_ann_dump_path(self):
        path = rstrip(os.path.join(self.project_path, "saved/dump.json"))
        return path

    def is_classes_equal(self, other_classes: dict[int, UAnnotationClass]):
        for class_id, class_info in other_classes.items():
            if class_id not in self.annotation_classes:
                return False
            if self.annotation_classes[class_id].name != class_info.name:
                return False
        return True

    def load_from_json(self, json_file: str):
        result = load_coco_json(json_file)
        if isinstance(result, str):
            return result

        info, licenses, annotations, images, categories = result
        self.project_path = rstrip(os.path.dirname(json_file))

        self.annotations, self.annotation_classes = make_annotation_dict_from_coco(
            images,
            annotations,
            categories,
            self.project_path
        )

        self.project_info = UProjectInfo(
            name=info['name'],
            description=info['description'],
            author=info['author'],
            year=info['year'],
            licenses=licenses,
        )

        print(
            f"Общее количество изображений: {len(images), sum([len(ann_list) for ann_list in self.annotations.values()])}")
        print(f"Количество аннотаций в проекте: {len(annotations)}")

        self.current_image_id = max([img["id"] for img in images], default=1)
        self.current_annotation_id = max([ann["id"] for ann in annotations], default=1)

        return

    def save(self):
        if self.project_path is None:
            print(f"Ошибка! Невозможно сохранить проект! Поврежден путь к проекту!")
            return

        json_file = rstrip(os.path.join(self.project_path, self.project_info.name + ".json"))
        print(json_file)
        if os.path.exists(json_file) is False:
            print("Невозможно сохранить проект! Поврежден путь к файлу!")
            return

        coco = make_coco_json(
            self.annotations,
            self.annotation_classes,
            {
                'name': self.project_info.name,
                'description': self.project_info.description,
                'author': self.project_info.author,
                'year': self.project_info.year,
            },
            self.project_info.licenses
        )

        save_coco_json(json_file, coco)

    def import_annotated_images(self, annotated_images: list[FAnnotationItem], new_dataset: str):
        image_path = rstrip(os.path.join(self.project_path, IMAGES_DIR))
        file_names = {f for f in os.listdir(image_path) if os.path.isfile(rstrip(os.path.join(image_path, f)))}

        for annotated_image in annotated_images:
            image_name = os.path.basename(annotated_image.get_image_path())
            if os.path.basename(annotated_image.get_image_path()) in file_names:
                print(f"Изображение с именем {image_name} уже существует в проекте!")
                continue

            # Создание папки и копирование изображения
            self.copy_image_to_project(annotated_image)

            annotated_image.set_image_id(self.get_image_id_with_increment())

            for annotation in annotated_image.get_annotation_data():
                annotation.set_annotation_id(self.get_annotation_id_with_increment())

            if new_dataset not in self.annotations:
                self.annotations[new_dataset] = []

            self.annotations[new_dataset].append(annotated_image)

    def update_annotations(self, update_annotations: list[FAnnotationItem], new_dataset: str = "noname_dataset"):
        usable_image_ids: set[int] = {item.get_image_id() for item_list in self.annotations.values() for item in
                                      item_list}
        usable_ann_ids: set[int] = {ann_data.get_annotation_id() for item_list in self.annotations.values() for item in
                                    item_list for ann_data in item.get_annotation_data()}

        for annotation in update_annotations:
            dataset = annotation.get_dataset_name()
            if dataset is None:
                if new_dataset not in self.annotations:
                    self.annotations[new_dataset] = list()
                self.add_annotation(annotation, new_dataset, usable_image_ids, usable_ann_ids)
                continue
            else:
                if dataset not in self.annotations:
                    self.annotations[dataset] = list()

                found_annotation = None
                for ann in self.annotations[dataset]:
                    if ann == annotation:
                        found_annotation = ann
                        break

                if found_annotation is None:
                    self.add_annotation(annotation, dataset, usable_image_ids, usable_ann_ids)
                else:
                    found_ids = {item.get_annotation_id() for item in found_annotation.get_annotation_data()}
                    new_data = annotation.get_annotation_data()

                    for item in new_data:
                        if item.get_annotation_id() not in found_ids:
                            item.set_annotation_id(self.get_annotation_id_with_increment())

                    found_annotation.update_annotation_data(new_data)

    def add_annotation(self, annotation: FAnnotationItem, dataset: str, image_ids: set[int], ann_ids: set[int]):
        if os.path.isfile(annotation.get_image_path()) is False:
            return
        else:
            image_name = os.path.basename(annotation.get_image_path())
            new_path_image = rstrip(os.path.join(self.project_path, IMAGES_DIR, image_name))

            os.makedirs(os.path.dirname(new_path_image), exist_ok=True)

            shutil.copy2(annotation.get_image_path(), new_path_image)
            annotation.set_image_path(new_path_image)

        # Изменяем ID элементов, если такие значения были найдены в проекте
        image_id = annotation.get_image_id()
        if image_id in image_ids:
            new_image_id = self.get_image_id_with_increment()
            annotation.set_image_id(new_image_id)
            image_ids.add(new_image_id)
        elif self.current_image_id < image_id:
            self.current_image_id = image_id

        for ann_object in annotation.get_annotation_data():
            ann_object_id = ann_object.get_annotation_id()
            if ann_object_id in ann_ids:
                new_annotation_id = self.get_annotation_id_with_increment()
                ann_object.set_annotation_id(new_annotation_id)
                ann_ids.add(new_annotation_id)
            elif self.current_annotation_id < ann_object_id:
                self.current_annotation_id = ann_object_id

        self.annotations[dataset].append(annotation)

    def remove_dataset(self, dataset: str):
        if dataset not in self.annotations:
            return

        for annotation in self.annotations[dataset][:]:
            self.remove_annotation(annotation, dataset)

        if len(self.annotations[dataset]) == 0:
            self.annotations.pop(dataset)

        #deleted_dataset_dir = rstrip(os.path.join(self.project_path, 'datasets', dataset))
        #if os.path.isdir(deleted_dataset_dir):
        #    shutil.rmtree(deleted_dataset_dir)

    def rename_dataset(self, dataset: str, new_dataset_name: str):
        if dataset not in self.annotations or dataset == new_dataset_name:
            return

        if new_dataset_name not in self.annotations:
            self.annotations[new_dataset_name] = []

        for annotation in self.annotations[dataset]:
            annotation.set_dataset_name(new_dataset_name)
            self.annotations[new_dataset_name].append(annotation)

        self.annotations.pop(dataset)

    def rename_dataset_annotations(self, annotations: list[FAnnotationItem], new_dataset_name: str):
        if new_dataset_name not in self.annotations:
            self.annotations[new_dataset_name] = list()

        for annotation in annotations:
            ann_dataset = annotation.get_dataset_name()
            try:
                self.annotations[ann_dataset].remove(annotation)
            except ValueError:
                print(str(ValueError) + str(annotation))
                pass
            annotation.set_dataset_name(new_dataset_name)
            self.annotations[new_dataset_name].append(annotation)
            if len(self.annotations[ann_dataset]) == 0:
                self.annotations.pop(ann_dataset)

    def remove_list_of_annotations(self, removing_annotations: list[FAnnotationItem]):
        for annotation in removing_annotations[:]:
            dataset = annotation.get_dataset_name()
            if dataset not in self.annotations:
                print(f"У аннотации под ID {annotation.get_image_id()} нет датасета, удаление невозможно!")
                continue

            self.remove_annotation(annotation, dataset)

    def remove_annotation(self, annotation: FAnnotationItem, dataset: str):
        if annotation not in self.annotations[dataset]:
            return
        self.annotations[dataset].remove(annotation)

        if len(self.annotations[dataset]) == 0:
            self.annotations.pop(dataset)

        image_path = annotation.get_image_path()
        if os.path.isfile(image_path):
            try:
                os.remove(image_path)
            except Exception as error:
                print(f"Возникла непредвиденная ошибка при удалении {image_path}!\nЛог ошибки: {str(error)}")

    def add_class(self, name: str, super_category: str, color: QColor | None = None):
        new_class_id = max([class_id for class_id in self.annotation_classes.keys()], default=1) + 1

        self.annotation_classes[new_class_id] = UAnnotationClass(
            name=name,
            color=QColor(color) if color is not None else get_distinct_color(new_class_id),
            super_category=super_category
        )

    """
    -------------- EXPORT ---------------
    """

    @staticmethod
    def write_files(image_dir_path: str, label_dir_path: str, annotation: FAnnotationItem):
        image_name = os.path.basename(annotation.get_image_path())
        image_path = rstrip(os.path.join(image_dir_path, image_name))
        try:
            shutil.copy2(annotation.get_image_path(), image_path)
        except Exception as error:
            print(f"{str(error)}: связано с файлом {annotation.get_image_path()} и копированием его в {image_path}")

        label_name = os.path.splitext(image_name)[0] + ".txt"
        label_path = rstrip(os.path.join(label_dir_path, label_name))
        with open(label_path, "w", encoding="utf-8") as label_file:
            label_file.write(annotation.get_bbox_strings())

    def simple_export_with_refactor(self, export_path: str, chosen_datasets: list[str], chosen_classes_id: list[int]):
        os.makedirs(export_path, exist_ok=True)

        refactored_data_dict = self._get_refactor_data(chosen_datasets, chosen_classes_id)
        refactored_classes = self._get_refactored_classes(chosen_classes_id)

        self._copy_images(export_path, refactored_data_dict)

        export_coco = make_coco_json(
            refactored_data_dict,
            refactored_classes,
            {
                'name': self.project_info.name,
                'description': self.project_info.description,
                'author': self.project_info.author,
                'year': self.project_info.year,
            },
            self.project_info.licenses,
        )

        save_coco_json(rstrip(os.path.join(export_path, os.path.basename(export_path) + ".json")), export_coco)

    def simple_txt_export_with_refactor(self, export_path: str, chosen_datasets: list[str],
                                        chosen_classes_id: list[int], train_percentage: float = 0.8):
        dirs = [
            export_path,
            rstrip(os.path.join(export_path, EDefaultTrainName.VAL_IMAGES)),
            rstrip(os.path.join(export_path, EDefaultTrainName.VAL_LABELS)),
            rstrip(os.path.join(export_path, EDefaultTrainName.TRAIN_IMAGES)),
            rstrip(os.path.join(export_path, EDefaultTrainName.TRAIN_LABELS))
        ]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)

        refactored_data_dict = self._get_refactor_data(chosen_datasets, chosen_classes_id)
        refactored_classes = self._get_refactored_classes(chosen_classes_id)

        print(f"Оригинальное количество картинок: {sum(len(ann_data) for ann_data in self.annotations.values())}"
              f"\nПосле рефакторинга: {sum(len(ann_data) for ann_data in refactored_data_dict.values())}")

        images_by_classes = defaultdict(list)  # key - tuple
        for ann_list in refactored_data_dict.values():
            for ann_item in ann_list:
                classes = [data.get_class_id() for data in ann_item.get_annotation_data()]

                if classes:
                    images_by_classes[tuple(sorted(classes))].append(ann_item)
                else:
                    images_by_classes[()].append(ann_item)

        for key, value in images_by_classes.items():
            train_count: int = np.ceil(len(value) * train_percentage).astype(int)

            train_selected = random.sample(value, train_count)
            val_selected = [item for item in value if item not in train_selected]

            print("Из набора классов", key, "общего количества", len(value), "выбрано", len(train_selected),
                  "обучающих и", len(val_selected), "валидационных изображений!")

            for train_item in train_selected:
                UCocoProject.write_files(
                    rstrip(os.path.join(export_path, EDefaultTrainName.TRAIN_IMAGES)),
                    rstrip(os.path.join(export_path, EDefaultTrainName.TRAIN_LABELS)),
                    train_item
                )

            for val_item in val_selected:
                UCocoProject.write_files(
                    rstrip(os.path.join(export_path, EDefaultTrainName.VAL_IMAGES)),
                    rstrip(os.path.join(export_path, EDefaultTrainName.VAL_LABELS)),
                    val_item
                )

        dataset_yaml = {
            "path": export_path,
            "train": EDefaultTrainName.TRAIN_IMAGES.value,
            "val": EDefaultTrainName.VAL_IMAGES.value,
            "names": {i - 1: class_obj.name for i, class_obj in refactored_classes.items()},
            "nc": len(refactored_classes),
        }

        yaml_path = os.path.join(export_path, EDefaultTrainName.YAML)
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(dataset_yaml, f, allow_unicode=True, sort_keys=False)

    def train_export_with_refactor(
            self,
            export_path: str,
            chosen_datasets: list[str],
            chosen_classes_id: list[int],
            train_percentage: float
    ):
        dirs = [
            export_path,
            rstrip(os.path.join(export_path, ECocoFileNames.TRAIN_DIR)),
            rstrip(os.path.join(export_path, ECocoFileNames.VAL_DIR)),
            rstrip(os.path.join(export_path, ECocoFileNames.ANNOTATION_DIR))
        ]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)

        refactored_data_dict = self._get_refactor_data(chosen_datasets, chosen_classes_id)
        refactored_classes = self._get_refactored_classes(chosen_classes_id)

        train_dicts = self._get_train_val_dicts(refactored_data_dict, train_percentage)
        save_json_names = (
            rstrip(os.path.join(export_path, ECocoFileNames.ANNOTATION_DIR, ECocoFileNames.TRAIN_JSON)),
            rstrip(os.path.join(export_path, ECocoFileNames.ANNOTATION_DIR, ECocoFileNames.VAL_JSON))
        )

        # Сохранение

    def _get_refactored_classes(self, chosen_classes_id: list[int]):
        refactored_classes: dict[int, UAnnotationClass] = dict()

        keys = list(self.annotation_classes.keys())
        for index in range(len(chosen_classes_id)):
            if chosen_classes_id[index] not in keys:
                continue

            refactored_classes[index + 1] = self.annotation_classes.get(chosen_classes_id[index])

        return refactored_classes

    def _get_refactor_data(self, chosen_datasets: list[str], chosen_classes_id: list[int]):
        needed_dataset_items: list[FAnnotationItem] = [item for dataset in chosen_datasets for item in
                                                       self.annotations.get(dataset, [])]
        refactored_annotations: dict[str, list[FAnnotationItem]] = dict()

        for item in needed_dataset_items:
            annotation_list: list[FAnnotationData] = list()

            data_list = item.get_annotation_data()
            for annotation in data_list:
                class_id = annotation.get_class_id()
                if class_id in chosen_classes_id:
                    copy_annotation = annotation.copy()
                    copy_annotation.set_class_id(chosen_classes_id.index(class_id) + 1)

                    annotation_list.append(copy_annotation)
                else:
                    continue

            # if len(annotation_list) == 0:
            #    continue

            copy_item = item.copy()
            copy_item.update_annotation_data(annotation_list)

            dataset = item.get_dataset_name()
            if dataset not in refactored_annotations:
                refactored_annotations[dataset] = list()
            refactored_annotations[dataset].append(copy_item)

        return refactored_annotations

    def _get_train_val_dicts(self, refactored_data_dict: dict[str, list[FAnnotationItem]], train_percentage: float):
        class_group_dict: dict[int, list[tuple[FAnnotationData, FAnnotationItem]]] = defaultdict(list)

        # Группировка по классу
        for dataset, ann_list in refactored_data_dict.items():
            for ann_item in ann_list:
                for ann_data in ann_item.get_annotation_data():
                    class_group_dict[ann_data.get_class_id()].append((ann_data, ann_item))

        images_train: dict[int, FAnnotationItem] = dict()
        images_val: dict[int, FAnnotationItem] = dict()

        for class_id, group_list in class_group_dict.items():
            count = len(group_list)
            if count == 0:
                continue

            train_indexes = set(random.sample(range(count), int(train_percentage * count)))
            for group_index in range(len(group_list)):
                if group_index in train_indexes:
                    to_add_dict = images_train
                else:
                    to_add_dict = images_val

                ann_data, ann_item = group_list[group_index]
                if ann_item.get_image_id() not in to_add_dict:
                    temp_item = ann_item.copy()
                    temp_item.update_annotation_data([])
                    to_add_dict[ann_item.get_image_id()] = temp_item

                to_add_dict[ann_item.get_image_id()].add_annotation_data(ann_data)

        train_result: dict[str, list[FAnnotationItem]] = defaultdict(list)
        for item in images_train.values():
            train_result[item.get_dataset_name()].append(item)

        val_result: dict[str, list[FAnnotationItem]] = defaultdict(list)
        for item in images_val.values():
            val_result[item.get_dataset_name()].append(item)

        return train_result, val_result

    def _copy_images(self, source_path: str, data_list: dict[str, list[FAnnotationItem]]):
        for dataset, item_list in data_list.items():
            for item in item_list:
                new_image_path = rstrip(os.path.join(source_path, IMAGES_DIR, os.path.basename(item.get_image_path())))
                os.makedirs(os.path.dirname(new_image_path), exist_ok=True)

                shutil.copy2(item.get_image_path(), new_image_path)

    def _delete_dataset_dir(self, dataset_name: str):
        deleted_dataset_dir = rstrip(os.path.join(self.project_path, 'datasets', dataset_name))
        if os.path.isdir(deleted_dataset_dir):
            shutil.rmtree(deleted_dataset_dir)

    def _create_dataset_dir(self, dataset_name: str):
        dataset_dir = rstrip(os.path.join(self.project_path, 'datasets', dataset_name))
        os.makedirs(dataset_dir, exist_ok=True)

    def copy_image_to_project(self, annotated_image: FAnnotationItem):
        image_path = annotated_image.get_image_path()
        if not os.path.isfile(image_path):
            return False

        new_image_path = rstrip(os.path.join(self.project_path, IMAGES_DIR, os.path.basename(image_path)))
        shutil.copy2(image_path, new_image_path)
        annotated_image.set_image_path(new_image_path)

        return True

    """
    ----------------------------
    """

    def _start_model_worker(self, worker: QObject):
        try:
            self.model_thread = QThread()
            self.model_worker = worker

            self.model_worker.moveToThread(self.model_thread)

            self.model_thread.started.connect(self.model_worker.start_work)
            self.model_thread.finished.connect(self.model_worker.deleteLater)
            self.model_thread.finished.connect(self.model_thread.deleteLater)

            self.model_thread.start()
            return None  # успех
        except Exception as error:
            return str(error)

    def load_local_yolo(self, path: str):
        worker = ULocalDetectYOLO(path, self.annotation_classes)
        return self._start_model_worker(worker)

    def load_remote_yolo(self, ip_address: str, port: int):
        worker = URemoteNeuralNet(self.annotation_classes, ip_address, port)
        try:
            worker.connect_to_server()
        except Exception as error:
            return f"Ошибка подключения к удалённому серверу: {error}"

        return self._start_model_worker(worker)

    def load_sam2(self, path: str):
        try:
            self.sam2_thread = QThread()
            self.sam2_worker = USam2Net(path)

            self.sam2_worker.moveToThread(self.sam2_thread)
            self.sam2_thread.finished.connect(self.sam2_worker.deleteLater)

            self.sam2_thread.start()
        except Exception as error:
            return str(error)

    """
    ----------------------------
    """

    def start_task_thread(
            self,
            tasks: list[tuple[callable, tuple, dict]],
            on_finished_list: list[callable],
            on_error_list: list[callable],
    ):
        if self.task_thread and self.task_thread.isRunning():
            return False

        self.task_runner = UTaskRunner(tasks)

        self.task_thread = QThread()
        self.task_runner.moveToThread(self.task_thread)

        self.task_thread.started.connect(self.task_runner.run)

        self.task_runner.finished.connect(self.task_thread.quit)
        self.task_runner.finished.connect(self.on_task_runner_finished)

        self.task_runner.error.connect(self.on_task_runner_error)

        for func in on_finished_list:
            self.task_runner.finished.connect(func)

        for func in on_error_list:
            self.task_runner.error.connect(func)

        self.task_thread.start()

        return True

    def on_task_runner_finished(self):
        self.task_runner = None

    def on_task_runner_error(self, error: str):
        self.task_thread.quit()
        self.task_runner = None
