import json
import argparse
from pathlib import Path

def renumber_annotation_ids(input_path: str, output_path: str):
    # Загрузка COCO JSON
    with open(input_path, 'r', encoding='utf-8') as f:
        coco_data = json.load(f)

    # Проверка на наличие аннотаций
    if 'annotations' not in coco_data:
        print("Файл не содержит поля 'annotations'")
        return

    # Перенумерация аннотаций
    for new_id, annotation in enumerate(coco_data['annotations'], start=1):
        annotation['id'] = new_id

    # Сохранение нового JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(coco_data, f, ensure_ascii=False, indent=2)

    print(f"Файл сохранён: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Перенумерация annotation_id в COCO JSON.")
    parser.add_argument("input", help="Путь к исходному COCO JSON файлу.")
    parser.add_argument("output", help="Путь для сохранения выходного JSON.")

    args = parser.parse_args()

    renumber_annotation_ids(args.input, args.output)