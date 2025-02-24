import configparser
import os.path

from utility import FClassData, FAnnotationData

TASKS = "tasks"
DATASETS = "datasets"
RESERVED = "reserved"

MAIN_SECTION = "main"
COUNTER = "counter"
CLASSES = "classes"
NAME = "name"

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

        # Изменяемые данные в процессе работы программы


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

            self.tasks = config.get(MAIN_SECTION, TASKS).strip("[]").split(", ")
            self.datasets = config.get(MAIN_SECTION, DATASETS).strip("[]").split(", ")
            self.reserved = config.get(MAIN_SECTION, RESERVED).strip("[]").split(", ")

            self.counter = config.getint(MAIN_SECTION, COUNTER)
            class_strings = config.get(MAIN_SECTION, CLASSES).strip("[]").split(", ")
            self.classes = [
                FClassData(index, class_strings[index], FClassData.get_save_color(index)) for index in range(len(class_strings))
            ]
            self.name = config.get(MAIN_SECTION, NAME)

            print(f"Загружен проект {self.name}!")
            print(f"Список строенных датасетов: {self.datasets}")
            print(f"Список задач для разметки: {self.tasks}")
            print(f"Список зарезервированных аннотаций: {self.reserved}")
            print(f"Список классов: {[class_name.Name for class_name in self.classes]}")
            print(f"Счетчик: {self.counter}")

        except Exception as error:
            return str(error)