import os
import random
import shutil
from typing import Optional

from PyQt5.QtCore import QThread, QObject
from PyQt5.QtGui import QColor

from SAM2.sam2_net import USam2Net
from coco.coco_json import load_coco_json, make_coco_json, save_coco_json
from coco.coco_utility import UProjectInfo, UAnnotationClass
from neural_model import URemoteNeuralNet, UBaseNeuralNet, ULocalDetectYOLO
from supporting.functions import rstrip, get_distinct_color
from utility import FAnnotationItem, FAnnotationData, UMessageBox

class UCocoProject:
    def __init__(self):

        self.annotations: dict[str, list[FAnnotationItem]] = {}
        self.annotation_classes: dict[int, UAnnotationClass] = {}

        self.last_image_id, self.last_annotation_id, self.last_class_id = 1, 1, 1

        self.project_info: Optional[UProjectInfo] = None
        self.project_path: Optional[str] = None

        self.current_image_id = 1
        self.current_annotation_id = 1

        # Поток обработки нейросети
        self.model_thread: Optional[QThread] = None
        self.model_worker: Optional[UBaseNeuralNet] = None

        # Поток SAM2
        self.sam2_thread: Optional[QThread] = None
        self.sam2_worker: Optional[USam2Net] = None

        self.load_sam2('SAM2/sam2.1_b.pt')

        self.image_extensions = [".jpg", ".jpeg", ".png"]

    def get_annotations(self):
        return self.annotations

    def get_classes(self):
        return self.annotation_classes

    def get_project_name(self):
        return self.project_info.name if self.project_info is not None else "noname"

    def get_image_id_with_increment(self):
        self.current_image_id += 1
        return self.current_image_id

    def get_annotation_id_with_increment(self):
        self.current_annotation_id += 1
        return self.current_annotation_id

    def load_from_json(self, json_file: str):
        result = load_coco_json(json_file)
        if isinstance(result, str):
            return result

        info, licenses, annotations, images, categories = result
        self.project_path = rstrip(os.path.dirname(json_file))

        for class_item in categories:
            self.annotation_classes[class_item['id']] = UAnnotationClass(
                class_item['name'],
                QColor(class_item['color']),
                class_item['supercategory']
            )

        dict_annotations: dict[int, list[dict]] = {}
        for annotation in annotations:
            image_id = annotation['image_id']
            if image_id not in dict_annotations:
                dict_annotations[image_id] = []
            dict_annotations[image_id].append({
                'id' : annotation['id'],
                'category_id' : annotation['category_id'],
                'bbox' : annotation['bbox'],
                'segmentation' : annotation['segmentation'],
                'iscrowd' : annotation['iscrowd'],
            })

        self.project_info = UProjectInfo(
            name=info['name'],
            description=info['description'],
            author=info['author'],
            year=info['year'],
            licenses=licenses,
        )

        for image in images:
            dataset = image['dataset'] if 'dataset' in image else "no_dataset"
            image_path = (os.path.join(os.path.dirname(json_file), "images" if dataset == "noname" else 'datasets/' + dataset, image['file_name'])
                         .strip().replace('\\', '/'))
            if os.path.isfile(image_path) is False:
                print(f"Не существует изображения по пути {image_path}!")
                continue
            if dataset not in self.annotations:
                self.annotations[dataset] = list()
            self.annotations[dataset].append(
                FAnnotationItem(
                    [FAnnotationData(
                        annotation['id'],
                        annotation['bbox'],
                        annotation['segmentation'],
                        annotation['category_id'],
                        self.annotation_classes[annotation['category_id']].name,
                        QColor(self.annotation_classes[annotation['category_id']].color),
                        image['width'],
                        image['height']
                    )
                     for annotation in dict_annotations[image["id"]]],
                    image_path,
                    image['id'],
                    dataset
                )
            )

        print(f"Общее количество изображений: {len(images), sum([len(ann_list) for ann_list in self.annotations.values()])}")
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

    def update_annotations(self, update_annotations: list[FAnnotationItem], new_dataset: str = "noname"):
        for annotation in update_annotations:
            dataset = annotation.get_dataset_name()
            if dataset is None:
                if new_dataset not in self.annotations:
                    self.annotations[new_dataset] = list()
                self.add_annotation(annotation, new_dataset)
                continue
            else:
                if dataset not in self.annotations:
                    self.annotations[dataset] = list()

                found_annotation = next((ann for ann in self.annotations[dataset] if ann == annotation), None)
                if found_annotation is None:
                    self.add_annotation(annotation, dataset)
                else:
                    found_annotation.update_annotation_data(annotation.get_annotation_data())

    def add_annotation(self, annotation: FAnnotationItem, dataset: str):
        if os.path.isfile(annotation.get_image_path()) is False:
            return
        else:
            image_name = os.path.basename(annotation.get_image_path())
            new_path_image = rstrip(os.path.join(self.project_path, 'datasets', dataset, image_name))

            os.makedirs(os.path.dirname(new_path_image), exist_ok=True)

            shutil.copy2(annotation.get_image_path(), new_path_image)
            annotation.set_image_path(new_path_image)

        annotation.set_image_id(self.get_image_id_with_increment())
        for ann_object in annotation.get_annotation_data():
            ann_object.set_class_id(self.get_annotation_id_with_increment())

        self.annotations[dataset].append(annotation)

    def remove_dataset(self, dataset: str):
        if dataset not in self.annotations:
            return

        for annotation in self.annotations[dataset][:]:
            self.remove_annotation(annotation, dataset)

        if len(self.annotations[dataset]) == 0:
            self.annotations.pop(dataset)

    def remove_list_of_annotations(self, removing_annotations: list[FAnnotationItem]):
        for annotation in removing_annotations:
            dataset = annotation.get_dataset_name()
            if dataset not in self.annotations:
                print(f"У аннотации под ID {annotation.get_image_id()} нет датасета, удаление невозможно!")
                continue

            self.remove_annotation(annotation, dataset)

    def remove_annotation(self, annotation: FAnnotationItem, dataset: str):
        if annotation not in self.annotations[dataset]:
            return
        self.annotations[dataset].remove(annotation)

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