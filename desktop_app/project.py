import configparser
import os.path
import shutil

from utility import FClassData, FAnnotationData, FAnnotationItem

TASKS = "tasks"
DATASETS = "datasets"
RESERVED = "reserved"

MAIN_SECTION = "main"
COUNTER = "counter"
CLASSES = "classes"
NAME = "name"

LABELS = "labels"
IMAGES = "images"

class UTrainProject:
    def __init__(self):
        # Неизменные данные в процессе работы программы
        # Список имен целей. Имена целей совпадают с названием каталога в проекте в папке tasks
        self.tasks: list[str] = list()

        # Список датасетов в проекте. Имя датасета совпадает с названием каталога в проекте в папке datasets
        self.datasets: list[str] = list()

        # Список зарезервированных аннотаций
        self.reserved: list[str] = list()

        self.classes: list[FClassData] = list()
        self.counter = 0
        self.name = ""
        self.path = ""

        # Изменяемые данные в процессе работы программы
        self.current_annotations: dict[str, list[FAnnotationItem]] = dict()


    def create(self, path: str, name:str, classes:list[str], counter:int = 0):
        try:
            config = configparser.ConfigParser()

            config.add_section(MAIN_SECTION)
            config[MAIN_SECTION][TASKS] = "[]"
            config[MAIN_SECTION][DATASETS] = "[]"
            config[MAIN_SECTION][RESERVED] = "[]"

            config[MAIN_SECTION][COUNTER] = str(counter)
            config[MAIN_SECTION][CLASSES] = "[" + ", ".join(classes) + "]"
            self.classes = [
                FClassData(index, classes[index], FClassData.get_save_color(index)) for index in range(len(classes))
            ]
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
            self.classes = [
                FClassData(index, class_strings[index], FClassData.get_save_color(index)) for index in range(len(class_strings))
            ]
            self.name = config.get(MAIN_SECTION, NAME)
            self.path = os.path.dirname(path_to_project)

            print(f"Загружен проект {self.name}!")
            print(f"Список строенных датасетов: {self.datasets}")
            print(f"Список задач для разметки: {self.tasks}")
            print(f"Список зарезервированных аннотаций: {self.reserved}")
            print(f"Список классов: {[class_name.Name for class_name in self.classes]}")
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
            config[MAIN_SECTION][CLASSES] = "[" + ", ".join([class_t.Name for class_t in self.classes]) + "]"
            config[MAIN_SECTION][NAME] = self.name

            for dataset in self.datasets:
                config.add_section(dataset)
                config[dataset][LABELS] = LABELS
                config[dataset][IMAGES] = IMAGES

            with open(os.path.join(self.path, self.name + ".cfg").replace('\\', '/'), "w") as file:
                config.write(file)

        except Exception as error:
            return str(error)

    def remove_dataset_folder(self, dataset: str):
        path_to_dataset = os.path.join(self.path, DATASETS, dataset).replace('\\', '/')
        if os.path.exists(path_to_dataset):
            shutil.rmtree(path_to_dataset)
            print(f"Из проекта {self.name} удалена папка датасета {dataset}, находящаяся по пути {path_to_dataset}!")
        else:
            print(f"Функция UTrainProject.remove_dataset_folder объекта {self.name}! На найдена папка датасета {dataset} по пути {path_to_dataset}!")

    def add_dataset(self, dataset: str):
        if dataset not in self.datasets:
            self.datasets.append(dataset)
            print(f"В проект {self.name} добавлен датасет {dataset}!")

    def remove_dataset(self, dataset: str):
        if dataset in self.datasets:
            self.datasets.remove(dataset)
            print(f"Из проекта {self.name} удален датасет {dataset}!")

    def remove_annotations_from_dataset(self, dataset):
        if self.current_annotations.get(dataset):
            del self.current_annotations[dataset]
            print(f"В проекте {self.name} из датасета {dataset} удалены все аннотации!")

    def add_annotation_to_dataset(self, dataset:str, ann_item:FAnnotationItem):
        if dataset in self.datasets:
            if dataset not in self.current_annotations:
                self.current_annotations[dataset] = list()
            self.current_annotations[dataset].append(ann_item)
            return
        else:
            return f"Ошибка в функции add_annotation_to_dataset! Не существует датасета {dataset}!"

    def get_datasets(self):
        return self.datasets

    def get_dataset_path(self, dataset_name: str):
        if dataset_name in self.datasets:
            return os.path.join(self.name, DATASETS, dataset_name).replace('\\', '/')

    def get_all_dataset_paths(self):
        paths = list()
        for dataset_name in self.datasets:
            paths.append(os.path.join(self.name, DATASETS, dataset_name).replace('\\', '/'))
        return paths

    def get_annotations_from_dataset(self, dataset_name: str):
        if dataset_name in self.current_annotations:
            return self.current_annotations[dataset_name]