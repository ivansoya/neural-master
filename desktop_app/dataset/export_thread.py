import os
import shutil

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from utility import FAnnotationItem


class UExportWorker(QObject):
    signal_process = pyqtSignal(float)
    signal_error = pyqtSignal(str)
    signal_done = pyqtSignal()

    def __init__(
            self,
            image_data: dict[str, list[FAnnotationItem]],
            dataset_path: str,
            dataset_list: list[str],
            class_refactor: dict[int, (int, str | None)] = None
    ):
        super().__init__()

        self.image_data = image_data
        self.dataset_list = dataset_list
        self.class_refactor = class_refactor
        self.dataset_path = dataset_path

    @pyqtSlot()
    def run(self):
        if not os.path.exists(self.dataset_path):
            self.signal_error.emit(f"Не существует пути для экспорта {self.dataset_path}!")
            return

        try:
            with open(os.path.join(self.dataset_path, 'classes.txt').replace('\\', '/'), 'w') as file:
                if self.class_refactor:
                    file.writelines([class_name + '\n' for key, (value, class_name) in self.class_refactor.items()])
        except Exception as error:
            self.signal_error.emit(str(error))
            return

        image_dir = os.path.join(self.dataset_path, 'images').replace('\\', '/')
        labels_dir = os.path.join(self.dataset_path, 'labels').replace('\\', '/')

        os.makedirs(image_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)

        images_count = sum([len(item_list) for dataset, item_list in self.image_data.items() if dataset in self.dataset_list])
        current = 1
        for dataset in self.dataset_list:
            if dataset not in self.image_data:
                continue

            for image in self.image_data[dataset]:
                class_strings = list()
                for annotation in image.get_annotation_data():
                    if self.class_refactor and annotation.get_id() in self.class_refactor:
                        class_id, _ = self.class_refactor[annotation.get_id()]
                        if class_id is not None:
                            class_strings.append(annotation.refactored_string(class_id) + '\n')

                if len(class_strings) > 0:
                    try:
                        shutil.copy2(image.get_image_path(), image_dir)
                        image_name = os.path.splitext(os.path.basename(image.get_image_path()))[0]
                        label_path = os.path.join(labels_dir, image_name + ".txt").replace('\\', '/')
                        with open(label_path, 'w') as file:
                            file.writelines(class_strings)
                    except Exception as error:
                        self.signal_error.emit(str(error))
                        return
                else:
                    continue

                self.signal_process.emit(current / float(images_count))
                if current < images_count:
                    current += 1

        self.signal_done.emit()
        return


