import os.path
import random
import shutil
from typing import Optional

import yaml
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
import yaml

from carousel import UAnnotationThumbnail
from dataset_window import Ui_Dialog
from utility import FClassData, FAnnotationData, EAnnotationStatus

import configparser

config_name = "config.cfg"

save_section_name = "save"
counter_save_option_name = "counter"
yaml_name = "data.yaml"


class FAnnItem:
    def __init__(self, ann_list: list[FAnnotationData], image_path: str):
        self.annotation_list = ann_list
        self.image_path = image_path

    def get_item_data(self):
        return self.annotation_list, self.image_path

class UDatasetCreator(QThread):
    progress_bar_updated = pyqtSignal(int)
    creation_ended = pyqtSignal(int)

    def __init__(self, thumb_list: list[UAnnotationThumbnail], percentage: int, counter: int, path: str, parent=None):
        super().__init__(parent)
        self.thumb_list = thumb_list
        self.percentage = percentage
        self.counter = counter
        self.dataset_path = path

        self.len_data = 0
        self.progress_counter = 0

        self.annotation_data: list[FAnnItem] = list()

    def run(self):
        print(f"Общее количество картинок: {len(self.thumb_list)}")
        # Сначала создаем список размеченных данных
        for i in range(len(self.thumb_list)):
            if self.thumb_list[i].get_annotated_status().value == EAnnotationStatus.Annotated.value:
                self.annotation_data.append(
                    FAnnItem(self.thumb_list[i].annotation_data_list, self.thumb_list[i].image_path)
                )
            self.progress_bar_updated.emit(int(100 * i / len(self.thumb_list)))
        self.len_data = len(self.annotation_data)
        print(f"Размечено картинок: {len(self.annotation_data)}")
        if self.len_data <= 0:
            self.creation_ended.emit(-1)
            return

        count_val = int(len(self.annotation_data) * (1.0 - self.percentage / 100.0))

        try:
            list_for_val = random.sample(self.annotation_data, count_val)
        except Exception:
            list_for_val = []
        list_for_train = [ann for ann in self.annotation_data if ann not in list_for_val]

        # Непосредственная генерация датасета
        train_image_folder = os.path.join(self.dataset_path, "train/images")
        train_labels_folder = os.path.join(self.dataset_path, "train/labels")
        self.generation(train_image_folder, train_labels_folder, list_for_train)

        valid_image_folder = os.path.join(self.dataset_path, "valid/images")
        valid_labels_folder = os.path.join(self.dataset_path, "valid/labels")
        self.generation(valid_image_folder, valid_labels_folder, list_for_val)

        self.creation_ended.emit(self.counter)

    def generation(self, image_folder: str, label_folder: str, ann_data: list[FAnnItem]):
        for i in range(len(ann_data)):
            image_name_img = f"Number_{self.counter:024b}_{os.path.basename(ann_data[i].image_path)}"
            self.counter += 1
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
            except Exception:
                self.progress_bar_updated.emit(0)


class UDatasetDialog(QDialog, Ui_Dialog):
    def __init__(self, classes: list[FClassData], annotations: list[UAnnotationThumbnail], parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.class_list = classes
        self.annotations = annotations

        self.train_percentage: int = 75
        self.is_creating_dataset: bool = True
        self.path_to_dataset: str = ""
        self.start_count: int = 1

        self.dataset_creator: Optional[UDatasetCreator] = None

        # Обработка выбора пути к датасету
        self.radio_create_dataset.setChecked(True)
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

    def on_radio_choose_dataset_mod(self):
        if self.radio_add_to_dataset.isChecked():
            self.is_creating_dataset = False
        elif self.radio_create_dataset.isChecked():
            self.is_creating_dataset = True

    def on_button_choose_path_clicked(self):
        if self.radio_add_to_dataset.isChecked():
            self.path_to_dataset, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите файл YAML",
                "",
                "YAML Files (*.yaml);;All Files (*)"
            )
            self.path_to_dataset = self.path_to_dataset.replace("/", "\\")
        elif self.radio_create_dataset.isChecked():
            self.path_to_dataset = QFileDialog.getExistingDirectory(self, "Выберите папку")
            self.path_to_dataset = self.path_to_dataset.replace("/", "\\")
        else:
            pass

        if self.path_to_dataset:  # Если папка была выбрана
            self.label_dataset_path.setText(f"{self.path_to_dataset}")
        else:
            self.label_dataset_path.setText("Папка не выбрана")

    def on_button_clicked_start_dataset_creation(self):
        if self.radio_create_dataset.isChecked():
            if os.path.exists(self.path_to_dataset) is False:
                print("Выбранного пути не существует!")
                return
            if self.dataset_creator is not None and self.dataset_creator.isRunning() is True:
                print("Уже запущен процесс создания датасета!")
                return

            self.create_dataset_carcass(self.path_to_dataset)
            self.create_yaml_file(os.path.join(self.path_to_dataset, yaml_name))

            self.dataset_creator = UDatasetCreator(
                self.annotations,
                self.train_percentage,
                self.start_count,
                self.path_to_dataset
            )
            self.dataset_creator.progress_bar_updated.connect(self.progress_load.setValue)
            self.dataset_creator.creation_ended.connect(self.on_ended_creation_dataset)
            self.dataset_creator.start()

        elif self.radio_add_to_dataset.isChecked():
            if os.path.exists(self.path_to_dataset) is False:
                print("Выбранного пути не существует!")
                return

            self.check_yaml_file(self.path_to_dataset)

    def set_data_from_config(self, path_to_config: str):
        try:
            config = configparser.ConfigParser()
            config.read('config.cfg')
        except Exception:
            return -2
        try:
            self.start_count = int(config.get(save_section_name, counter_save_option_name).strip().strip('"'))
            return 1
        except configparser.NoOptionError | configparser.NoSectionError:
            self.start_count = 1
            return -1

    def create_config_file(self, path_to_config: str):
        config = configparser.ConfigParser()

        config.add_section(save_section_name)
        config.set(save_section_name, counter_save_option_name, str(self.start_count))

        path = os.path.join(path_to_config, config_name)
        print(path)
        with open(path, 'w+') as config_file:
            config.write(config_file)

    def create_dataset_carcass(self, path: str):
        os.makedirs(os.path.join(path, "train/images"), exist_ok=True)
        os.makedirs(os.path.join(path, "train/labels"), exist_ok=True)
        os.makedirs(os.path.join(path, "valid/images"), exist_ok=True)
        os.makedirs(os.path.join(path, "valid/labels"), exist_ok=True)
        os.makedirs(os.path.join(path, "test/images"), exist_ok=True)
        os.makedirs(os.path.join(path, "test/labels"), exist_ok=True)

    def create_yaml_file(self, yaml_path):
        with open(yaml_path, 'w+') as data_file:
            name_class_list = []
            for class_item in self.class_list:
                name_class_list.append(class_item.Name)

            data_file.write("train: ../train/images\n"
                            "val: ../valid/images\n"
                            "test: ../test/images\n"
                            "\n"
                            f"nc: {len(name_class_list)}\n"
                            f"names: [{', '.join([f"'{item}'" for item in name_class_list])}]\n")

    def check_yaml_file(self, yaml_path):
        if os.path.exists(yaml_path) is False:
            return -1

        with open(yaml_path, "r") as data_yaml:
            try:
                data = yaml.safe_load(data_yaml)
                dataset_path = os.path.dirname(yaml_path)

                result = {
                    "train_images": os.path.join(dataset_path, data["train"].lstrip("./")).replace("\\", "/"),
                    "train_labels": os.path.join(dataset_path, data["train"].lstrip("./") + "/labels").replace("\\", "/"),
                    "val_images": os.path.join(dataset_path, data["val"].lstrip("./")).replace("\\", "/"),
                    "val_labels": os.path.join(dataset_path, data["val"].lstrip("./") + "/labels").replace("\\", "/"),
                    "test_images": os.path.join(dataset_path, data["test"].lstrip("./")).replace("\\", "/"),
                    "test_labels": os.path.join(dataset_path, data["test"].lstrip("./") + "/labels").replace("\\", "/"),

                    "nc": data["nc"],
                    "names": data["names"],
                }
                print(result)
                return result

            except yaml.YAMLError:
                return -2


    def on_ended_creation_dataset(self, key: int):
        if key == -1:
            print("Ошибка при создании датасета!")
            self.progress_load.setValue(0)
            return
        else:
            self.start_count = key
            self.progress_load.setValue(100)

            self.create_config_file(self.path_to_dataset)

            # Создание QMessageBox
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Information)  # Устанавливаем тип иконки
            msg_box.setWindowTitle("Успех")
            msg_box.setText("Датасет успешно создан!")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
