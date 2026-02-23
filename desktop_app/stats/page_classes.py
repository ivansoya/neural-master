from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QAbstractItemView, QMessageBox, QDialog, QListWidget

from coco.coco_project import UCocoProject
from coco.coco_utility import UAnnotationClass
from stats.class_chart import FCountColor
from commander import UGlobalSignalHolder
from design.classes_page import Ui_classes_page_design
from project import UTrainProject
from stats.window_add_class import UWindowClass, EAddClassStrings
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
            "Все аннотации": [EAnnotationType.BoundingBox, EAnnotationType.Segmentation, EAnnotationType.Mask],
            "Ограничительные рамки": [EAnnotationType.BoundingBox],
            "Полигоны": [EAnnotationType.Segmentation],
            "Маски": [EAnnotationType.Mask],
        })
        self.combo_type.setCurrentIndex(0)

        self.list_datasets.setSelectionMode(QListWidget.MultiSelection)
        self.list_datasets.itemSelectionChanged.connect(self.update_chart_statistics)

        self.button_show_all.clicked.connect(self.handle_on_choose_all_clicked)
        self.button_clear_all.clicked.connect(self.handle_on_clear_all_clicked)

        if self.commander:
            self.commander.project_load_complete.connect(self.update_chart_statistics)
            self.commander.project_load_complete.connect(self.update_classes)
            self.commander.project_load_complete.connect(self.update_list_dataset)
            self.commander.project_updated.connect(self.update_chart_statistics)


    def update_list_dataset(self):
        self.list_datasets.addItems(self.project.get_annotations().keys())
        self.list_datasets.selectAll()

    def handle_on_clear_all_clicked(self):
        self.list_datasets.clearSelection()

    def handle_on_choose_all_clicked(self):
        self.list_datasets.selectAll()

    def add_class_to_project(self):
        if self.project.task_thread and self.project.task_thread.isRunning():
            UMessageBox.show_error("Не все рабочие задачи завершились, дождитесь их окончания!")
            return

        window_class = UWindowClass(self.project.get_current_class_id() + 1)
        self.commander.set_block(True)
        if window_class.exec_() == QDialog.Accepted:
            result = window_class.get_result()

            tasks = [
                (
                    self.project.add_class,
                    (result[EAddClassStrings.CLASS_NAME], result[EAddClassStrings.SUPERCATEGORY], result[EAddClassStrings.COLOR],),
                    {}
                ),
                (self.project.save, (), {})
            ]

            self.project.start_task_thread(tasks, [self.on_added_finished], [])

        self.commander.set_block(False)

    @pyqtSlot()
    def on_added_finished(self):
        self.commander.classes_updated.emit()
        self.update_classes()
        self.update_chart_statistics()
        UMessageBox.show_ok(f"Добавлен новый класс в проект!")

    def update_classes(self):
        self.list_classes.clear()
        classes = self.project.get_classes()
        for class_id in classes.keys():
            self.list_classes.add_class(
                class_id,
                classes[class_id].name,
                QColor(classes[class_id].color)
            )

        datasets = self.project.get_annotations().keys()

    def update_chart_statistics(self):
        annotations_by_dataset = self.project.get_annotations()
        background_class = UAnnotationClass(
            "background",
            QColor(Qt.gray),
            "background",
        )
        class_info_by_id = {-1: background_class}
        class_info_by_id.update(self.project.get_classes())

        if not annotations_by_dataset:
            return

        # Инициализируем словарь с подсчётом
        count_by_class: dict[str, FCountColor] = {
            class_data.name: FCountColor(0, QColor(class_data.color))
            for class_data in class_info_by_id.values()
        }

        allowed_types = self.combo_type.get_current_enum()
        allowed_datasets = [item.text() for item in self.list_datasets.selectedItems()]

        for dataset, annotations in annotations_by_dataset.items():
            if dataset not in allowed_datasets:
                continue
            for annotation in annotations:
                if not annotation.get_annotation_data():
                    count_by_class["background"].increment_count()
                    continue

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
