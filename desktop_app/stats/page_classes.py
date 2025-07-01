from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QAbstractItemView, QMessageBox

from coco.coco_project import UCocoProject
from stats.class_chart import FCountColor
from commander import UGlobalSignalHolder
from design.classes_page import Ui_classes_page_design
from project import UTrainProject
from supporting.functions import get_distinct_color
from utility import UMessageBox, EAnnotationType, FAnnotationClasses


class UPageClasses(QWidget, Ui_classes_page_design):
    def __init__(self, commander: UGlobalSignalHolder, project: UCocoProject, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.commander = commander
        self.project = project

        self.list_classes.setSelectionMode(QAbstractItemView.NoSelection)

        self.button_add_class.clicked.connect(self.add_class_to_project)

        self.combo_type.currentIndexChanged.connect(self.handle_on_type_changed)
        self.combo_type.set_members({
            "Все аннотации": [EAnnotationType.BoundingBox, EAnnotationType.Segmentation],
            "Ограничительные рамки": [EAnnotationType.BoundingBox],
            "Маски": [EAnnotationType.Segmentation],
        })
        self.combo_type.setCurrentIndex(0)

        if self.commander:
            self.commander.project_load_complete.connect(self.update_chart_statistics)
            self.commander.project_load_complete.connect(self.update_classes)
            self.commander.project_updated_datasets.connect(self.update_chart_statistics)

    def add_class_to_project(self):
        class_name = self.lineedit_enter_class.text()
        if class_name and len(class_name) >= 3:
            self.project.add_class(
                class_name,
                "attachment",
                None
            )

            self.commander.classes_updated.emit()
            self.update_classes()
            self.update_chart_statistics()
            self.project.save()
            UMessageBox.show_ok(f"Добавлен новый класс {class_name} в проект!")

    def update_classes(self):
        self.list_classes.clear()
        classes = self.project.get_classes()
        for class_id in classes.keys():
            self.list_classes.add_class(
                class_id,
                classes[class_id].name,
                QColor(classes[class_id].color)
            )

    def update_chart_statistics(self):
        annotations_by_dataset = self.project.get_annotations()
        class_info_by_id = self.project.get_classes()

        if not annotations_by_dataset:
            return

        # Инициализируем словарь с подсчётом
        count_by_class: dict[str, FCountColor] = {
            class_data.name: FCountColor(0, QColor(class_data.color))
            for class_data in class_info_by_id.values()
        }

        allowed_types = self.combo_type.get_current_enum()

        for dataset_annotations in annotations_by_dataset.values():
            for annotation in dataset_annotations:
                for ann_data in annotation.get_annotation_data():
                    if ann_data.get_annotation_type() not in allowed_types:
                        continue

                    class_id = ann_data.get_class_id()
                    class_data = class_info_by_id.get(class_id)
                    if class_data is None:
                        continue

                    count_by_class[class_data.name].increment_count()

        # Передаём данные на график
        self.chart_classes.draw_chart(count_by_class)

    def handle_on_type_changed(self):
        self.update_chart_statistics()
