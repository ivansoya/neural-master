import os.path
import random

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog
from matplotlib.image import thumbnail

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

        self.annotation_data: list[FAnnItem] = list()

    def run(self):
        # Сначала создаем список размеченных данных
        for i in range(len(self.thumb_list)):
            if self.thumb_list[i].get_annotated_status().value == EAnnotationStatus.Annotated:
                self.annotation_data.append(
                    FAnnItem(self.thumb_list[i].annotation_data_list, self.thumb_list[i].image_path)
                )
            self.progress_bar_updated.emit(int(100 * i / len(self.thumb_list)))
        print(f"Всего {len(self.annotation_data)} размеченных картинок!")
        count_val = int(len(self.annotation_data) * (self.percentage / 100.0))

        list_for_val = random.sample(self.annotation_data, count_val)
        list_for_train = [ann for ann in self.annotation_data if ann not in list_for_val]

        # Непосредственная генерация датасета


    def generation(self, image_folder: str, label_folder: str, ann_data: list[FAnnItem]):
        image_folder_path = os.path.join(self.dataset_path, image_folder)
        label_folder_path = os.path.join(self.dataset_path, label_folder)

        file_name = f"Number_{self.counter:024b}_{self}"
        for i in range(len(ann_data)):

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

        # Обработка выбора пути к датасету
        self.radio_create_dataset.setChecked(True)
        self.button_choose_path_dataset.clicked.connect(self.on_button_choose_path_clicked)
        self.label_dataset_path.setText("Папка не выбрана")

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
            self.create_dataset_carcass(self.path_to_dataset)
            self.create_yaml_file(self.path_to_dataset)


        else:
            pass

        if self.path_to_dataset:  # Если папка была выбрана
            self.label_dataset_path.setText(f"{self.path_to_dataset}")
        else:
            self.label_dataset_path.setText("Папка не выбрана")

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

    def create_yaml_file(self, path):
        data_path = os.path.join(path, yaml_name)
        with open(data_path, 'w+') as data_file:
            name_class_list = []
            for class_item in self.class_list:
                name_class_list.append(class_item.Name)

            data_file.write("train: ../train/images\n"
                            "val: ../valid/images\n"
                            "test: ../test/images\n"
                            "\n"
                            f"nc: {len(name_class_list)}\n"
                            f"names: [{', '.join([f"'{item}'" for item in name_class_list])}]\n")
