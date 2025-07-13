from typing import Optional

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDialog, QListWidget, QFileDialog

from coco.coco_project import UCocoProject
from coco.coco_utility import UAnnotationClass
from design.dialog_export import Ui_dialog_export
from utility import UMessageBox, FAnnotationItem, FAnnotationData


class UDialogExport(QDialog, Ui_dialog_export):
    def __init__(self, project: UCocoProject):
        super().__init__()
        self.setupUi(self)

        self.project = project

        self.chosen_classes_id: list[int] = list()
        self.chosen_datasets: list[str] = list()

        self.datasets = list(self.project.get_annotations().keys())
        self.classes: dict[int, UAnnotationClass] = self.project.get_classes()

        self.export_path: Optional[str] = None

        self.list_choose_classes.setSelectionMode(QListWidget.MultiSelection)
        self.list_choose_datasets.setSelectionMode(QListWidget.MultiSelection)

        self.list_choose_datasets.addItems(self.datasets)
        for class_id, class_data in self.classes.items():
            self.list_choose_classes.add_class_item(class_id, class_data.name, QColor(class_data.color))

        self._select_all(self.list_choose_datasets, True)
        self._select_all(self.list_choose_classes, True)

        self.button_choose_all.clicked.connect(lambda: self._select_all(self.list_choose_datasets, True))
        self.button_cancel_all.clicked.connect(lambda: self._select_all(self.list_choose_datasets, False))

        self.button_enable_datasets.clicked.connect(lambda: self.stack_export.setCurrentIndex(0))
        self.button_enable_classes.clicked.connect(lambda: self.stack_export.setCurrentIndex(1))

        self.button_choose_path.clicked.connect(self.handle_select_export_path)
        self.button_start_export.clicked.connect(self.handle_on_export_clicked)

    @pyqtSlot()
    def handle_select_export_path(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Выберите путь для экспорта")
        if folder_path:
            self.export_path = folder_path
            self.label_path.setText(folder_path)
        else:
            self.export_path = None

    @pyqtSlot()
    def handle_on_export_clicked(self):
        if not self.export_path:
            UMessageBox.show_error("Не указан путь для экспорта!")
            return

        self.chosen_classes_id = self.list_choose_classes.get_selected_class_ids()
        self.chosen_datasets = [self.list_choose_datasets.item(i).text() for i in range(self.list_choose_datasets.count()) if self.list_choose_datasets.item(i).isSelected()]

        if len(self.chosen_classes_id) == 0 or len(self.chosen_datasets) == 0:
            UMessageBox.show_error("Должен быть указан хотя бы один датасет или класс")
            return

        self.accept()

    def get_result(self):
        return self.export_path, self.chosen_classes_id, self.chosen_datasets

    @staticmethod
    def _select_all(list_widget: QListWidget, is_selected: bool):
        for i in range(list_widget.count()):
            list_widget.item(i).setSelected(is_selected)
