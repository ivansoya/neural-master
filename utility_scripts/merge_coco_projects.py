import json
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_categories(cats1, cats2):
    merged = []
    name_to_id = {}
    map_merged = {}
    next_id = 1



    # Добавляем категории второго проекта
    for c in cats2:
        name = c["name"]
        if name not in name_to_id:
            name_to_id[name] = next_id
            merged.append({"id": next_id, "name": name, "supercategory": c["supercategory"], "color": c["color"]})
            next_id += 1

    # Добавляем категории первого проекта
    for c in cats1:
        name = c["name"]
        if name not in name_to_id:
            name_to_id[name] = next_id
            merged.append({"id": next_id, "name": name, "supercategory": c["supercategory"], "color": c["color"]})
            next_id += 1
        map_merged[c["id"]] = name_to_id[name]

    return merged, map_merged


def remap_annotations(annotations, id_map):
    """Заменяет category_id по словарю id_map"""
    for ann in annotations:
        if ann["category_id"] in id_map:
            ann["category_id"] = id_map[ann["category_id"]]
    return annotations


def main():
    if len(sys.argv) != 3:
        print("Использование: python merge_coco_classes.py project1.json project2.json")
        sys.exit(1)

    path1, path2 = sys.argv[1], sys.argv[2]

    coco1 = load_json(path1)
    coco2 = load_json(path2)

    merged_categories, map_merged = merge_categories(coco1["categories"], coco2["categories"])

    print(map_merged)

    # Заменяем ID классов в аннотациях
    coco1["categories"] = merged_categories
    coco1["annotations"] = remap_annotations(coco1["annotations"], map_merged)

    save_json(coco1, path1)

    print(f"Готово! Слияние завершено!")


if __name__ == "__main__":
    main()
