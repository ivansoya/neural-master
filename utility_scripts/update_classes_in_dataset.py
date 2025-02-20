import os
import glob
import argparse
import shutil
from re import match


def update_file_with_map(file_path: str, map_conv: dict[int, int]):
    lines: list[str] = list()
    modified: list[str] = list()
    count_updated = 0
    print(f"Открываем файл {file_path}")
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()

        for line in lines:
            values = line.split()
            print(values)
            if not values:
                continue
            try:
                key = int(values[0])
                if key in map_conv.keys():
                    values[0] = str(map_conv[key])
                    print(f"Старый id класса {key} и новый id для класса: {map_conv[key]}")
                    count_updated += 1
                    modified.append(' '.join(values))
            except ValueError as val_error:
                print(f"Ошибка! Первый элемент в {file_path} не является индексом {values[0]}!")
                continue
        return count_updated, modified
    except Exception as error:
        print(f"Ошибка! {str(error)}")
        exit(1)

def create_new_dataset(
        path_to_dataset: str,
        path_to_new_dataset: str,
        new_classes: list[str],
        map_conv: dict[int, int]
):
    current_labels_path = os.path.join(path_to_dataset, "labels").strip().replace('\\', '/')
    current_images_path = os.path.join(path_to_dataset, "images").strip().replace('\\', '/')

    new_labels_path = os.path.join(path_to_new_dataset, "labels").strip().replace('\\', '/')
    new_images_path = os.path.join(path_to_new_dataset, "images").strip().replace('\\', '/')

    new_classes_path = os.path.join(path_to_new_dataset, "classes.txt").strip().replace('\\', '/')

    os.makedirs(path_to_new_dataset, exist_ok=True)
    os.makedirs(new_labels_path, exist_ok=True)
    os.makedirs(new_images_path, exist_ok=True)

    try:
        with open(new_classes_path, 'w') as new_classes_file:
            new_classes_file.writelines(line + '\n' for line in new_classes)
    except Exception as error:
        print(f"Ошибка! {str(error)}")
        exit(1)

    labels = [os.path.join(current_labels_path, f).replace('\\', '/') for f in os.listdir(current_labels_path) if f.endswith(".txt")]
    for label in labels:
        image_path = os.path.join(current_images_path, os.path.basename(label).replace(".txt", "")).replace('\\', '/') + ".*"
        matching_images = [f.replace('\\', '/') for f in glob.glob(image_path)]
        if not matching_images:
            continue

        count, lines = update_file_with_map(label, map_conv)
        if count > 0:
            with open(os.path.join(new_labels_path, os.path.basename(label)).replace('\\', '/'), "w") as file:
                file.writelines(line + '\n' for line in lines)
            shutil.copyfile(matching_images[0], os.path.join(new_images_path, os.path.basename(matching_images[0])).replace('\\', '/'))
        else:
            print(f"В файле {label} отсутствуют доступные классы!")
    pass

def create_map_conv(current_classes: list[str], new_classes: list[str], output_map_conv: dict[int, int]):
    for index in range(len(current_classes)):
        class_name = current_classes[index]
        if class_name in new_classes:
            output_map_conv[index] = new_classes.index(class_name)

    return output_map_conv

def parse_classes_txt(file_path: str, output_list: list[str]):
    try:
        with open(file_path, 'r') as classes_file:
            output_list = [line.strip() for line in classes_file.readlines()]
    except Exception as error:
        print(f"Ошибка: {str(error)}")
        exit(1)

    return output_list

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--path', type=str, help="Путь к датасету", required=True)
    parser.add_argument('-o', '--output', type=str, help="Измененный датасет", required=True)
    parser.add_argument('-c', '--classes', type=str, help="Новый набор классов", required=True)

    args = parser.parse_args()

    if os.path.exists(args.path) is False:
        print(f"Ошибка! Выбранного датасета {args.path} не существует!")
        exit(1)

    current_classes_path = os.path.join(args.path, "classes.txt").replace('\\', '/')

    if os.path.exists(current_classes_path) is False or current_classes_path.endswith("classes.txt") is False:
        print(f"Ошибка! {current_classes_path} не является файлом классов. Он должен носить название classes.txt!")
        exit(1)

    if os.path.exists(args.classes) is False or args.classes.endswith(".txt") is False:
        print(f"Ошибка! Набора классов {args.classes} не существует или не является .txt!")
        exit(1)

    current_classes: list[str] = list()
    new_classes: list[str] = list()
    map_conv: dict[int, int] = dict()

    current_classes = parse_classes_txt(
        os.path.join(args.path, "classes.txt").replace('\\', '/'),
        current_classes
    )

    new_classes = parse_classes_txt(args.classes, new_classes)
    map_conv = create_map_conv(current_classes, new_classes, map_conv)

    print(f"Список старых классов: {current_classes}\nПолучен список новых классов: {new_classes}\nПолучена матрица изменений: {map_conv}")

    create_new_dataset(
        args.path,
        args.output,
        new_classes,
        map_conv
    )

if __name__== "__main__":
    main()