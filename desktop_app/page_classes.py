from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QStackedWidget

from class_chart import FCountColor
from commander import UGlobalSignalHolder
from design.classes_page import Ui_classes_page_design
from project import UTrainProject


class UPageClasses(QWidget, Ui_classes_page_design):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.commander = commander
        self.project = project

        self.button_to_datasets_settings.clicked.connect(lambda: self.go_to_another_page(1))
        self.button_to_annotation_scene.clicked.connect(lambda: self.go_to_another_page(2))
        self.button_to_statistics.clicked.connect(lambda: self.go_to_another_page(3))

        if self.commander:
            self.commander.project_load_complete.connect(self.update_chart_statistics)

    def go_to_another_page(self, page_index: int):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(page_index)

    def update_chart_statistics(self):
        dict_classes = self.project.get_current_annotations()
        count_classes: dict[str, FCountColor] = dict()
        if len(dict_classes) == 0:
            return

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

        self.chart_classes.draw_chart(count_classes)
