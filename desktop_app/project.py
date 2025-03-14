import configparser
import os.path
import shutil

from PyQt5.QtCore import QThread

from supporting.error_text import UErrorsText
from utility import FAnnotationClasses, FAnnotationData, FAnnotationItem

TASKS = "tasks"
DATASETS = "datasets"
RESERVED = "reserved"

MAIN_SECTION = "main"
COUNTER = "counter"
CLASSES = "classes"
NAME = "name"

LABELS = "labels"
IMAGES = "images"

class UMergeAnnotationThread(QThread):
    def __init__(self, project: "UTrainProject", source_dict: dict[str, list[FAnnotationItem]], type_d: str = DATASETS):
        super().__init__()

        self.project = project
        self.source_dict = source_dict
        self.type_d = type_d
        if type_d == DATASETS:
            self.target_dict = self.project.get_current_annotations()
        else:
            self.target_dict = self.project.get_reserved_annotations()

    def run(self):
        for dataset, ann_list in self.source_dict.items():
            if not dataset in self.target_dict:
                self.target_dict[dataset] = list()
                self.project.add_dataset(dataset, self.type_d)
            image_path_list = [a_t.get_image_path() for a_t in ann_list]
            for annotation in ann_list:
                if annotation.get_image_path() in image_path_list:
                    image_path_list.remove(annotation.get_image_path())


class UTrainProject:
    def __init__(self):
        # Неизменные данные в процессе работы программы
        # Список имен целей. Имена целей совпадают с названием каталога в проекте в папке tasks
        self.tasks: list[str] = list()

        # Список датасетов в проекте. Имя датасета совпадает с названием каталога в проекте в папке datasets
        self.datasets: list[str] = list()

        # Список зарезервированных аннотаций
        self.reserved: list[str] = list()

        self.classes = FAnnotationClasses()
        self.counter = 0
        self.name = ""
        self.path = ""

        # Изменяемые данные в процессе работы программы
        self.current_annotations: dict[str, list[FAnnotationItem]] = dict()
        self.reserved_annotations: dict[str, list[FAnnotationItem]] = dict()


    def create(self, path: str, name:str, classes:list[str], counter:int = 0):
        try:
            config = configparser.ConfigParser()

            config.add_section(MAIN_SECTION)
            config[MAIN_SECTION][TASKS] = "[]"
            config[MAIN_SECTION][DATASETS] = "[]"
            config[MAIN_SECTION][RESERVED] = "[]"

            config[MAIN_SECTION][COUNTER] = str(counter)
            config[MAIN_SECTION][CLASSES] = "[" + ", ".join(classes) + "]"
            self.classes.add_classes_from_strings(classes)
            self.name = name
            self.path = path
            config[MAIN_SECTION][NAME] = self.name

            os.makedirs(os.path.join(path, TASKS).strip().replace('\\', '/'), exist_ok=False)
            os.makedirs(os.path.join(path, DATASETS).strip().replace('\\', '/'), exist_ok=False)
            os.makedirs(os.path.join(path, RESERVED).strip().replace('\\', '/'), exist_ok=False)

            with open(os.path.join(path, name).strip().replace('\\', '/') + ".cfg", "w") as configfile:
                config.write(configfile)

            return

        except Exception as error:
            return str(error)

    def load(self, path_to_project: str):
        try:
            config = configparser.ConfigParser()
            config.read(path_to_project)

            self.tasks = [str_t for str_t in config.get(MAIN_SECTION, TASKS).strip("[]").strip().split(", ") if str_t]
            self.datasets = [str_t for str_t in config.get(MAIN_SECTION, DATASETS).strip("[]").strip().split(", ") if str_t]
            self.reserved = [str_t for str_t in config.get(MAIN_SECTION, RESERVED).strip("[]").strip().split(", ") if str_t]

            self.counter = config.getint(MAIN_SECTION, COUNTER)
            class_strings = [class_t for class_t in config.get(MAIN_SECTION, CLASSES).strip("[]").split(", ") if class_t]
            self.classes.add_classes_from_strings(class_strings)
            self.name = config.get(MAIN_SECTION, NAME)
            self.path = os.path.dirname(path_to_project)

            self._init_dicts()

            print(f"Загружен проект {self.name}!")
            print(f"Список строенных датасетов: {self.datasets}")
            print(f"Список задач для разметки: {self.tasks}")
            print(f"Список зарезервированных аннотаций: {self.reserved}")
            print(f"Список классов: {[class_value.Name for class_value in self.classes.get_all_classes()]}")
            print(f"Счетчик: {self.counter}")

        except Exception as error:
            return str(error)

    def save(self):
        try:
            config = configparser.ConfigParser()

            config.add_section(MAIN_SECTION)
            config[MAIN_SECTION][TASKS] = "[" + ", ".join(self.tasks) + "]"
            config[MAIN_SECTION][DATASETS] = "[" + ", ".join(self.datasets) + "]"
            config[MAIN_SECTION][RESERVED] = "[" + ", ".join(self.reserved) + "]"

            config[MAIN_SECTION][COUNTER] = str(self.counter)
            config[MAIN_SECTION][CLASSES] = "[" + ", ".join([class_t.Name for class_t in self.classes.get_all_classes()]) + "]"
            config[MAIN_SECTION][NAME] = self.name

            #for dataset in self.datasets:
            #    config.add_section(dataset)
            #    config[dataset][LABELS] = LABELS
            #    config[dataset][IMAGES] = IMAGES

            with open(os.path.join(self.path, self.name + ".cfg").replace('\\', '/'), "w") as file:
                config.write(file)

        except Exception as error:
            return str(error)

    def remove_project_folder(self, dataset_name: str, type_dataset: str = DATASETS):
        path_to_dataset = os.path.join(self.path, type_dataset, dataset_name).replace('\\', '/')
        if os.path.exists(path_to_dataset):
            shutil.rmtree(path_to_dataset)
            print(f"Из проекта {self.name} удалена папка датасета {dataset_name}, находящаяся по пути {path_to_dataset}!")
        else:
            print(f"Функция UTrainProject.remove_dataset_folder объекта {self.name}! На найдена папка датасета {dataset_name} по пути {path_to_dataset}!")

    def add_dataset(self, dataset: str, type_dataset: str = DATASETS):
        ref_dataset_list = self._get_ref_to_list(type_dataset)
        if ref_dataset_list is None:
            return UErrorsText.not_existing_type_dataset("UTrainProject.add_dataset", type_dataset)

        if dataset not in ref_dataset_list:
            ref_dataset_list.append(dataset)
            print(f"В проект {self.name} добавлен датасет {dataset}!")

    def remove_dataset(self, dataset: str, type_dataset: str = DATASETS):
        dict_dataset = self._get_ref_to_list(type_dataset)
        if not dict_dataset:
            return UErrorsText.not_existing_type_dataset("UTrainProject.remove_dataset", type_dataset)

        if dataset in dict_dataset:
            dict_dataset.remove(dataset)
            print(f"Из проекта {self.name} удален датасет {dataset}!")
        else:
            return UErrorsText.not_existing_dataset_in_project("UTrainProject.remove_dataset", dataset)

    def delete_dataset_from_project(self, dataset: str, type_dataset: str = DATASETS):
        path_dataset_folder = os.path.join(self.path, type_dataset, dataset).replace('\\', '/')
        if not os.path.exists(path_dataset_folder):
            return UErrorsText.not_existing_path_to_dataset("UTrainProject.delete_dataset", path_dataset_folder)

        self.remove_dataset(dataset)
        self.remove_all_annotations_from_dataset(dataset, type_dataset)
        shutil.rmtree(path_dataset_folder)

    def swap_annotations(self, dataset_name: str, type_source: str, type_target: str):
        if type_source == type_target:
            return UErrorsText.type_swap_is_equal("UTrainProject.swap_annotations")
        source_ann_dict = self._get_ref_to_annotation_dict(type_source)
        target_ann_dict = self._get_ref_to_annotation_dict(type_target)
        if target_ann_dict is None or source_ann_dict is None:
            return UErrorsText.not_existing_type_dataset("UTrainProject.swap_annotations", "")

        if not dataset_name in source_ann_dict:
            return UErrorsText.not_existing_annotations("UTrainProject.swap_annotations", dataset_name)
        if dataset_name in target_ann_dict and len(target_ann_dict[dataset_name]) > 0:
            return UErrorsText.annotations_already_exist("UTrainProject.swap_annotations", dataset_name)

        ann_list = source_ann_dict.pop(dataset_name)
        for ann_data in ann_list:
            ann_data.image_path = ann_data.image_path.replace('/' + type_source + '/', '/' + type_target + '/')
        target_ann_dict[dataset_name] = ann_list

    def remove_all_annotations_from_dataset(self, dataset, type_dataset: str = DATASETS):
        ref_annotation_dict = self._get_ref_to_annotation_dict(type_dataset)
        if not ref_annotation_dict:
            return UErrorsText.not_existing_type_dataset("UTrainProject.remove_annotations", type_dataset)

        if ref_annotation_dict.get(dataset):
            del ref_annotation_dict[dataset]
            print(f"В проекте {self.name} из датасета {dataset} удалены все аннотации!")

    def add_annotation(self, dataset:str, ann_item:FAnnotationItem, type_dataset: str = DATASETS):
        ref_dataset_dict = self._get_ref_to_list(type_dataset)
        ref_annotations_dict = self._get_ref_to_annotation_dict(type_dataset)
        if not ref_dataset_dict or not ref_annotations_dict:
            return UErrorsText.not_existing_type_dataset("UTrainProject.add_annotation", type_dataset)

        if dataset in ref_dataset_dict:
            if dataset not in ref_annotations_dict:
                ref_annotations_dict[dataset] = list()
            ref_annotations_dict[dataset].append(ann_item)
            return
        else:
            return UErrorsText.not_existing_dataset_in_project("UTrainProject.add_annotation", dataset)

    def delete_annotation(self, dataset: str, ann_item: FAnnotationItem, type_dataset: str = DATASETS):
        ref_dataset_list = self._get_ref_to_list(type_dataset)
        ref_annotations_dict = self._get_ref_to_annotation_dict(type_dataset)
        if not ref_dataset_list or not ref_annotations_dict:
            return UErrorsText.not_existing_type_dataset("UTrainProject.delete_annotation", type_dataset)

        if dataset not in ref_dataset_list:
            return UErrorsText.not_existing_dataset_in_project("UTrainProject.delete_annotation", dataset)
        if dataset not in ref_annotations_dict:
            return UErrorsText.not_existing_annotations("UTrainProject.delete_annotation", dataset)

        try:
            ref_annotations_dict[dataset].remove(ann_item)
        except ValueError:
            return UErrorsText.not_existing_annotation_in_dataset("UTrainProject.delete_annotation", dataset)

    def get_datasets(self):
        return self.datasets

    def get_current_annotations(self):
        return self.current_annotations

    def get_reserved(self):
        return self.reserved

    def get_reserved_annotations(self):
        return self.reserved_annotations

    def get_dataset_path(self, dataset_name: str):
        if dataset_name in self.datasets:
            return os.path.join(self.name, DATASETS, dataset_name).replace('\\', '/')

    def get_reserved_path(self, reserved_name: str):
        if reserved_name in self.reserved:
            return os.path.join(self.name, RESERVED, reserved_name).replace('\\', '/')

    def get_all_dataset_paths(self, type_dataset: str = DATASETS):
        dict_ref = self._get_ref_to_list(type_dataset)
        if not dict_ref:
            UErrorsText.not_existing_type_dataset("UTrainProject.get_all_dataset_paths", type_dataset)

        paths = list()
        for dataset_name in dict_ref:
            paths.append(os.path.join(self.name, type_dataset, dataset_name).replace('\\', '/'))
        return paths

    def get_annotations_from_dataset(self, dataset_name: str):
        if dataset_name in self.current_annotations:
            return self.current_annotations[dataset_name]

    def get_annotations_from_reserved(self, reserved_name: str):
        if reserved_name in self.reserved_annotations:
            return self.reserved_annotations[reserved_name]

    def _get_ref_to_list(self, type_dataset: str):
        if type_dataset == DATASETS:
            return self.datasets
        elif type_dataset == RESERVED:
            return self.reserved
        else:
            return None

    def _get_ref_to_annotation_dict(self, type_dataset:str):
        if type_dataset == DATASETS:
            return self.current_annotations
        elif type_dataset == RESERVED:
            return self.reserved_annotations
        else:
            return None

    def _init_dicts(self):
        for dataset_name in self.datasets:
            self.current_annotations[dataset_name] = list()
        for reserved_name in self.reserved:
            self.reserved_annotations[reserved_name] = list()