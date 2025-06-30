import json
import os

from utility import FAnnotationItem, FAnnotationClasses


def convert_to_coco(annotations_old_format: dict[str, list[FAnnotationItem]], classes: dict[int, FAnnotationClasses.FClassData]):
    images, annotations, categories = [], [], []
    image_id, annotation_id = 1, 1

    for class_id, ann_class in classes.items():
        categories.append({
            "id": class_id + 1,
            "name": ann_class.Name,
            "supercategory": "attachment",
            "color": ann_class.Color.name(),
        })

    for dataset, ann_list in annotations_old_format.items():
        for ann_item in ann_list:
            image_name = os.path.basename(ann_item.get_image_path())
            data = ann_item.get_annotation_data()
            if data is None or len(data) == 0:
                continue

            image_width, image_height = data[0].get_resolution()

            images.append({
                "id": image_id,
                "file_name": image_name,
                "width": image_width,
                "height": image_height,
                "dataset": dataset
            })

            for ann_data in data:
                ann_data.clamp_cords()
                annotations.append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": ann_data.get_id() + 1,
                    "bbox": ann_data.get_bbox(),
                    "segmentation": ann_data.get_segmentation(),
                    "iscrowd": 0
                })
                annotation_id += 1

            image_id += 1

    return images, annotations, categories

def build_coco_json(images: dict, annotations: dict, categories: dict):
    coco = {
        "info": {
            "name": "Varan-Master",
            "description": "Varan",
            "version": "0.1",
            "author": "Ivan",
            "year": 2025
        },
        "licenses": [],
        "images": images,
        "annotations": annotations,
        "categories": categories
    }
    return coco

def save_coco_json(path, coco_dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(coco_dict, f, ensure_ascii=False, indent=2)