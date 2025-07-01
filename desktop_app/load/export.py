from typing import Optional

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDialog, QListWidget, QFileDialog

from design.dialog_export import Ui_dialog_export
from utility import UMessageBox


class UDialogExport(QDialog, Ui_dialog_export):
    signal_done = pyqtSignal(str, list, object)

    def __init__(self, dataset_list: list[str], classes_list: list[str]):
        super().__init__()
        self.setupUi(self)

        self.classes_list = classes_list
        self.export_path: Optional[str] = None

        self.list_choose_classes.setSelectionMode(QListWidget.MultiSelection)
        self.list_choose_datasets.setSelectionMode(QListWidget.MultiSelection)

        self.list_choose_datasets.addItems(dataset_list)
        self.list_choose_classes.addItems(classes_list)

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

        chosen_classes_id = [i for i in range(self.list_choose_classes.count()) if self.list_choose_classes.item(i).isSelected()]
        chosen_datasets = [self.list_choose_datasets.item(i).text() for i in range(self.list_choose_datasets.count()) if self.list_choose_datasets.item(i).isSelected()]

        if len(chosen_classes_id) == 0 or len(chosen_datasets) == 0:
            UMessageBox.show_error("Должен быть указан хотя бы один датасет или класс")
            return

        refactor_dict_classes = {value: (index, self.classes_list[value]) for index, value in enumerate(chosen_classes_id)}
        self.signal_done.emit(
            self.export_path,
            chosen_datasets,
            refactor_dict_classes
        )
        self.accept()

    @staticmethod
    def _select_all(list_widget: QListWidget, is_selected: bool):
        for i in range(list_widget.count()):
            list_widget.item(i).setSelected(is_selected)
