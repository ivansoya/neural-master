import os
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtGui import QColor

from coco_project.coco_json import load_coco_json
from utility import FAnnotationItem, FAnnotationData


@dataclass
class UProjectInfo:
    name: str
    description: str
    author: str
    year: int
    licenses: list

@dataclass
class UAnnotationClass:
    name: str
    color: QColor
    super_category: str


class UCocoProject:
    def __init__(self):

        self.annotations: dict[str, list[FAnnotationItem]] = {}
        self.annotation_classes: dict[int, UAnnotationClass] = {}

        self.last_image_id, self.last_annotation_id, self.last_class_id = 1, 1, 1

        self.project_info: Optional[UProjectInfo] = None

    def load_from_json(self, json_file: str):
        result = load_coco_json(json_file)
        if result is False:
            return

        info, licenses, annotations, images, categories = result

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
            image_path = (os.path.join(os.path.dirname(json_file), "images" if dataset == "no_dataset" else dataset, image['file_name'])
                         .strip().replace('\\', '/'))
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
                    dataset
                )
            )

        print(self.annotation_classes)
        print(f"Общее количество аннотаций: {sum([len(annotations) for annotations in self.annotations.values()])}")



