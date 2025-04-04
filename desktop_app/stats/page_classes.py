from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QAbstractItemView, QMessageBox

from stats.class_chart import FCountColor
from commander import UGlobalSignalHolder
from design.classes_page import Ui_classes_page_design
from project import UTrainProject
from utility import UMessageBox


class UPageClasses(QWidget, Ui_classes_page_design):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.commander = commander
        self.project = project

        self.list_classes.setSelectionMode(QAbstractItemView.NoSelection)

        self.button_add_class.clicked.connect(self.add_class_to_project)

        if self.commander:
            self.commander.project_load_complete.connect(self.update_chart_statistics)
            self.commander.project_load_complete.connect(self.update_classes)
            self.commander.project_updated_datasets.connect(self.update_chart_statistics)

    def add_class_to_project(self):
        class_name = self.lineedit_enter_class.text()
        if class_name and len(class_name) >= 3:
            error = self.project.classes.add_class_by_name(class_name)
            if error:
                UMessageBox.show_error(error)
                return
            else:
                self.commander.classes_updated.emit()
                self.update_classes()
                self.update_chart_statistics()
                self.project.save()
                UMessageBox.show_error(f"Добавлен новый класс {class_name} в проект!", "ОК", int(QMessageBox.Ok))

    def update_classes(self):
        self.list_classes.clear()
        for class_id in self.project.classes.get_all_ids():
            self.list_classes.add_class(
                class_id,
                self.project.classes.get_name(class_id),
                self.project.classes.get_color(class_id)
            )

    def update_chart_statistics(self):
        dict_classes = self.project.get_current_annotations()
        count_classes: dict[str, FCountColor] = dict()
        if len(dict_classes) == 0:
            return

        for key, value in self.project.classes.get_items():
            class_name = self.project.classes.get_name(key) or str(key)
            if class_name not in count_classes:
                count_classes[class_name] = FCountColor(
                    0,
                    self.project.classes.get_color(key) or QColor("LightGrey")
                )
        for key, value in dict_classes.items():
            for item in value:
                data, path = item.get_item_data()
                for class_t in data:
                    class_name = self.project.classes.get_name(class_t.ClassID) or str(class_t.ClassID)
                    if not class_name in count_classes:
                        count_classes[class_name] = FCountColor(
                            0,
                            self.project.classes.get_color(class_t.ClassID) or QColor("LightGrey")
                        )
                    count_classes[class_name].increment_count()

        #count_classes = dict(sorted(count_classes.items()))
        self.chart_classes.draw_chart(count_classes)
