import json
import os

from PyQt5.QtGui import QColor

from coco.coco_utility import UAnnotationClass
from utility import FAnnotationItem, FAnnotationClasses, EAnnotationStatus, FAnnotationData


def cfg_convert_to_coco(annotations_old_format: dict[str, list[FAnnotationItem]], classes: dict[int, FAnnotationClasses.FClassData]):
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


def make_dump_annotations_from_coco(path: str):
    if not (os.path.exists(path) and path.endswith(".json")):
        return -1, f"Не существует файла {path}!"

    ret = load_coco_json(path)
    if isinstance(ret, str):
        return -2, f"В сохраненном дампе разметки некорректный формат coco. Невозможно загрузить дамп!"

    _, _, annotations, images, classes = ret

    count_failed = 0
    images_dict: dict[int, FAnnotationItem] = {}
    for image in images:
        file_name = image["file_name"]
        if not (os.path.exists(file_name) and os.path.isfile(file_name)):
            print(f"Не удается найти файл {file_name}, возможно, он уже удален!")
            count_failed += 1
            continue

        status = EAnnotationStatus.NO_STATUS if "status" not in image else EAnnotationStatus(image["status"])
        image_id = image["id"]

        image_item = FAnnotationItem(
            [],
            image["file_name"],
            image_id,
            image["dataset"] if image["dataset"] != "None" else None,
            image["width"],
            image["height"]
        )

        image_item.set_annotation_status(status)
        if image_id not in images_dict:
            images_dict[image_id] = image_item

    if len(images_dict) == 0:
        return -3, "Не удалось найти ни один файл из дампа. Загрузка невозможна!"

    classes_dict: dict[int, tuple[str, str]] = {}
    for class_ann in classes:
        classes_dict[class_ann["id"]] = class_ann["name"], class_ann["color"]

    for annotation in annotations:
        image_id = annotation["image_id"]
        if image_id not in images_dict:
            continue

        class_id = annotation["category_id"]

        ann_data = FAnnotationData(
            annotation["id"],
            annotation["bbox"],
            annotation["segmentation"],
            class_id,
            "unresolved" if class_id not in classes_dict else classes_dict[class_id][0],
            QColor("#d3d3d3") if class_id not in classes_dict else QColor(classes_dict[class_id][1])
        )

        images_dict[image_id].add_annotation_data(ann_data)

    return 1, list(images_dict.values())


def make_coco_json(
        annotations: dict[str, list[FAnnotationItem]],
        classes: dict[int, UAnnotationClass],
        info: dict,
        licenses: list,
        is_dump: bool = False
):
    images, converted_annotations, categories = [], [], []

    for class_id, ann_class in classes.items():
        categories.append({
            "id": class_id,
            "name": ann_class.name,
            "supercategory": ann_class.super_category,
            "color": ann_class.color.name(),
        })

    for dataset, ann_list in annotations.items():
        for ann_item in ann_list:
            image_name = os.path.basename(ann_item.get_image_path()) if is_dump is False else ann_item.get_image_path()

            new_image = {
                "id": ann_item.get_image_id(),
                "file_name": image_name,
                "width": ann_item.get_width(),
                "height": ann_item.get_height(),
                "dataset": dataset if dataset else "None"
            }

            if is_dump:
                status = ann_item.get_annotation_status()
                new_image["status"] = EAnnotationStatus.NO_STATUS.value if status is EAnnotationStatus.PERFORMING_ANNOTATION else status.value

            images.append(new_image)

            data = ann_item.get_annotation_data()
            for ann_data in data:
                ann_data.clamp_cords()
                converted_annotations.append({
                    "id": ann_data.get_annotation_id(),
                    "image_id": ann_item.get_image_id(),
                    "category_id": ann_data.get_class_id(),
                    "bbox": ann_data.get_bbox(),
                    "segmentation": ann_data.get_segmentation(),
                    "area": ann_data.get_area(),
                    "iscrowd": 0
                })

    return build_coco_json(images, converted_annotations, categories, info, licenses)


def build_coco_json(images: list, annotations: list, categories: list, info: dict, licenses: list):
    coco = {
        "info": info,
        "licenses": licenses,
        "images": images,
        "annotations": annotations,
        "categories": categories
    }
    return coco


def save_coco_json(path, coco_dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(coco_dict, f, ensure_ascii=False, indent=2)


def load_coco_json(path):
    with open(path, "r", encoding="utf-8") as f:
        coco = json.load(f)

    try:
        validate_coco_structure(coco)
        return coco["info"], coco["licenses"], coco["annotations"], coco["images"], coco["categories"]
    except Exception as error:
        return str(error)

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