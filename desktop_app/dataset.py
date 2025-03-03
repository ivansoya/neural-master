import os.path
import random
import shutil
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox

from carousel import UAnnotationThumbnail
from design.dataset_window import Ui_Dialog
from utility import FAnnotationClasses, FAnnotationItem, EAnnotationStatus, FDatasetInfo, EDatasetType


class UDatasetCreator(QThread):
    progress_bar_updated = pyqtSignal(int)
    creation_ended = pyqtSignal(int)

    def __init__(self, thumb_list: list[UAnnotationThumbnail], percentage: int, dataset_info: FDatasetInfo, parent = None):
        super().__init__(parent)
        if dataset_info is None:
            print("Ошибка при передачи данных для создания датасета!")
            return
        self.thumb_list = thumb_list
        self.percentage = percentage
        self.dataset_info = dataset_info

        self.len_data = 0
        self.progress_counter = 0

        self.annotation_data: list[FAnnotationItem] = list()

    def run(self):
        print(f"Общее количество картинок: {len(self.thumb_list)}")
        # Сначала создаем список размеченных данных
        for i in range(len(self.thumb_list)):
            if self.thumb_list[i].get_annotated_status().value == EAnnotationStatus.Annotated.value:
                self.annotation_data.append(
                    FAnnotationItem(self.thumb_list[i].annotation_data_list, self.thumb_list[i].image_path)
                )
            self.progress_bar_updated.emit(int(100 * i / len(self.thumb_list)))
        self.len_data = len(self.annotation_data)
        print(f"Размечено картинок: {len(self.annotation_data)}")
        if self.len_data <= 0:
            self.creation_ended.emit(-1)
            return

        # Распредление для Yaml файла YOLO
        if self.dataset_info.dataset_type.value == EDatasetType.YamlYOLO.value:
            count_val = int(len(self.annotation_data) * (1.0 - self.percentage / 100.0))
            try:
                list_for_val = random.sample(self.annotation_data, count_val)
            except Exception:
                list_for_val = []
            list_for_train = [ann for ann in self.annotation_data if ann not in list_for_val]
            # Непосредственная генерация датасета
            try:
                self.generation(
                    self.dataset_info.paths["train_images"],
                    self.dataset_info.paths["train_labels"],
                    list_for_train,
                )
                self.generation(
                    self.dataset_info.paths["valid_images"],
                    self.dataset_info.paths["valid_labels"],
                    list_for_val)
            except Exception as e:
                print(str(e))

        # Генерация для txt файла YOLO
        elif self.dataset_info.dataset_type.value == EDatasetType.TxtYOLO.value:
            try:
                self.generation(
                    self.dataset_info.paths["images"],
                    self.dataset_info.paths["labels"],
                    self.annotation_data
                )
            except Exception as e:
                print(f"Ошибка: {str(e)}")

        self.creation_ended.emit(self.dataset_info.counter)

    def generation(self, image_folder: str, label_folder: str, ann_data: list[FAnnotationItem]):
        for i in range(len(ann_data)):
            image_name_img = f"Number_{self.dataset_info.counter:024b}_{os.path.basename(ann_data[i].image_path)}"
            self.dataset_info.counter += 1
            image_name_txt = os.path.splitext(image_name_img)[0] + ".txt"
            # Копирование картинки в датасет
            shutil.copy(
                ann_data[i].image_path,
                os.path.join(image_folder, image_name_img)
            )
            with open(os.path.join(label_folder, image_name_txt), 'w+') as label_file:
                for annotation in ann_data[i].annotation_list:
                    label_file.write(str(annotation) + '\n')
            self.progress_counter += 1
            try:
                self.progress_bar_updated.emit(int(float(self.progress_counter) / self.len_data * 100))
            except Exception as e:
                self.progress_bar_updated.emit(0)
                print(f"Ошибка: {str(e)}")


class UDatasetDialog(QDialog, Ui_Dialog):
    def __init__(
            self,
            classes: FAnnotationClasses,
            annotations: list[UAnnotationThumbnail],
            dataset: FDatasetInfo = None,
            parent=None
    ):
        super().__init__(parent)
        self.setupUi(self)

        self.class_list = classes
        self.annotations = annotations

        self.train_percentage: int = 75
        self.dataset_info = dataset

        self.dataset_creator: Optional[UDatasetCreator] = None

        # Обработка выбора пути к датасету
        self.button_choose_path_dataset.clicked.connect(self.on_button_choose_path_clicked)
        self.label_dataset_path.setText("Папка не выбрана")

        # Назначение на кнопку создания датасета
        self.button_create.clicked.connect(self.on_button_clicked_start_dataset_creation)

        # Какой процент изображений пойдет в train категорию, какой в val категорию
        self.slider_train_val.setValue(self.train_percentage)
        self.slider_train_val.valueChanged.connect(self.on_slider_value_changed)
        self.label_train_percentage.setText(str(self.train_percentage))
        self.label_val_percentage.setText(str(100 - self.train_percentage))

    def on_slider_value_changed(self, value):
        self.train_percentage = value
        self.label_train_percentage.setText(str(self.train_percentage))
        self.label_val_percentage.setText(str(100 - self.train_percentage))

    def on_button_choose_path_clicked(self):
        path_to_dataset = QFileDialog.getExistingDirectory(self, "Выберите папку").replace("/", "\\")
        try:
            self.dataset_info = FDatasetInfo(path_to_dataset, EDatasetType(self.combo_dataset_type.currentIndex() + 1))
            self.label_dataset_path.setText(f"{self.dataset_info.path_general}")
        except Exception as e:
            print(f"Ошибка: {str(e)}")
            self.dataset_info = None

    def on_button_clicked_start_dataset_creation(self):
        if self.dataset_creator is not None and self.dataset_creator.isRunning() is True:
            print("Уже запущен процесс создания датасета!")
            return
        if self.dataset_info is None:
            print("Не выбран путь, куда создавать датасет!")
        else:
            try:
                self.dataset_info.create_dataset_carcass()
                if self.dataset_info.dataset_type.value == EDatasetType.YamlYOLO.value:
                    self.create_yaml_file()
                elif self.dataset_info.dataset_type.value == EDatasetType.TxtYOLO.value:
                    self.dataset_info.create_txt_yolo_file([name.Name for name in self.class_list.get_all_classes()])
            except Exception as e:
                print(f"Ошибка: {str(e)}")
                return
            self.dataset_creator = UDatasetCreator(
                self.annotations,
                self.train_percentage,
                self.dataset_info,
            )
            self.dataset_creator.progress_bar_updated.connect(self.progress_load.setValue)
            self.dataset_creator.creation_ended.connect(self.on_ended_creation_dataset)
            self.dataset_creator.start()

    def create_yaml_file(self):
        with open(self.dataset_info.datafile_path, 'w+') as data_file:
            name_class_list = []
            for class_item in self.class_list.get_all_classes():
                name_class_list.append(class_item.Name)

            data_file.write(f"train: ../{os.path.join(*os.path.normpath(self.dataset_info.paths["train_images"]).split(os.sep)[-2:]).replace('\\', '/')}\n"
                            f"val: ../{os.path.join(*os.path.normpath(self.dataset_info.paths["valid_images"]).split(os.sep)[-2:]).replace('\\', '/')}\n"
                            f"test: ../{os.path.join(*os.path.normpath(self.dataset_info.paths["test_images"]).split(os.sep)[-2:]).replace('\\', '/')}\n"
                            "\n"
                            f"nc: {len(name_class_list)}\n"
                            f"names: [{', '.join([f"'{item}'" for item in name_class_list])}]\n")

    def on_ended_creation_dataset(self, key: int):
        if key == -1:
            print("Ошибка при создании датасета!")
            self.progress_load.setValue(0)
            return
        else:
            self.dataset_info.counter = key
            self.progress_load.setValue(100)

            self.dataset_info.create_config_file()

            # Создание QMessageBox
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)  # Устанавливаем тип иконки
            msg_box.setWindowTitle("Успех")
            msg_box.setText("Датасет успешно создан!")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
