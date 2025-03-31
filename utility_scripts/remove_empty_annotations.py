import os


def clean_empty_labels(directory: str):
    labels_dir = os.path.join(directory, "labels").replace('\\', '/')
    images_dir = os.path.join(directory, "images").replace('\\', '/')

    if not os.path.exists(labels_dir) or not os.path.exists(images_dir):
        print("Одна из папок не существует")
        return

    for label_file in os.listdir(labels_dir):
        label_path = os.path.join(labels_dir, label_file)

        if os.path.isfile(label_path) and os.path.getsize(label_path) == 0:
            os.remove(label_path)
            print(f"Удален пустой файл разметки: {label_file}")

            base_name, _ = os.path.splitext(label_file)

            for image_file in os.listdir(images_dir):
                image_base, image_ext = os.path.splitext(image_file)
                if image_base == base_name:
                    image_path = os.path.join(images_dir, image_file)
                    os.remove(image_path)
                    print(f"Удалено изображение: {image_file}")
                    break

def main():
    directory = "E:\Varan-Master\datasets\dataset_19.02.2025"
    clean_empty_labels(directory)

if __name__ == "__main__":
    main()