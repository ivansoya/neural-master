import os
from collections import Counter

# === 1. Чтение списка классов из txt ===
classes_txt = r"C:\Users\1\Documents\Проект Варан\Обучение\Датасеты\2025.09.24\classes.txt"

with open(classes_txt, "r", encoding="utf-8") as f:
    class_names = [line.strip() for line in f.readlines() if line.strip()]

num_classes = len(class_names)
print(f"Найдено {num_classes} классов")
for i, name in enumerate(class_names):
    print(f"{i}: {name}")

# === 2. Подсчёт классов в label-файлах ===
dataset_root = os.path.dirname(classes_txt)  # корень датасета (где лежит txt)
labels_dir = os.path.join(dataset_root, "labels")
counter = Counter()

for root, _, files in os.walk(labels_dir):
    for file in files:
        if file.endswith(".txt"):
            with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        cls_id = int(line.split()[0])  # первый элемент = id класса
                        counter[cls_id] += 1



# === 3. Вывод статистики ===
print("\nСтатистика по классам:")
print("id | class_name      | count")
print("-" * 40)
for cls_id, name in enumerate(class_names):
    print(f"{cls_id:<2} | {name:<14} | {counter[cls_id]}")
