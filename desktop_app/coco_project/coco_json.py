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
                    "category_id": ann_data.get_class_id() + 1,
                    "bbox": ann_data.get_bbox(),
                    "segmentation": ann_data.get_segmentation(),
                    "area": ann_data.get_area(),
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

def load_coco_json(path):
    with open(path, "r", encoding="utf-8") as f:
        coco = json.load(f)

    try:
        validate_coco_structure(coco)
        return coco["info"], coco["licenses"], coco["annotations"], coco["images"], coco["categories"]
    except Exception as error:
        print(error)
        return False

def validate_coco_structure(coco: dict):
    check_required_keys(coco, ["info", "licenses", "images", "annotations", "categories"], "COCO JSON")

    # Проверка изображений
    for i, image in enumerate(coco["images"]):
        check_required_keys(
            image,
            ["id", "file_name", "dataset", "width", "height"],
            f"images[{i}]"
        )

    # Проверка аннотаций
    for i, ann in enumerate(coco["annotations"]):
        check_required_keys(
            ann,
            ["id", "image_id", "category_id", "bbox", "area", "iscrowd", "segmentation"],
            f"annotations[{i}]"
        )

        # Дополнительная проверка формата разметок
        if not isinstance(ann["bbox"], list) or len(ann["bbox"]) != 4:
            raise ValueError(f"annotations[{i}]['bbox'] должен быть списком из 4 чисел")

        if not isinstance(ann["segmentation"], list):
            raise ValueError(f"annotations[{i}]['segmentation'] должен быть списком списков")

    # Проверка классов
    for i, cat in enumerate(coco["categories"]):
        check_required_keys(
            cat,
            ["id", "name", "supercategory", "color"],
            f"categories[{i}]"
        )

def check_required_keys(obj, required_keys, context=""):
    for key in required_keys:
        if key not in obj:
            raise ValueError(f"В {context} нет ключа '{key}'")