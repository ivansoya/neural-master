from PyQt5.QtWidgets import QWidget, QFileDialog

from commander import UGlobalSignalHolder
from design.model_page import Ui_page_model
from project import UTrainProject
from utility import UMessageBox


class UPageModel(QWidget, Ui_page_model):
    def __init__(self, commander: UGlobalSignalHolder, project: UTrainProject):
        super().__init__()
        self.setupUi(self)

        self.project = project
        self.commander = commander

        self.button_load_local.clicked.connect(self.load_model)
        self.commander.model_loaded.connect(self.handle_on_load_model)

    def load_model(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите модель .pt", "", "Model Files (*.pt);;All Files (*)")
        if file_path:
            error = self.project.load_local_yolo(file_path)
            if error:
                UMessageBox.show_error(error)
            else:
                self.commander.model_loaded.emit()

    def handle_on_load_model(self):
        self.label_status.setText("Загружена!")
        self._set_status_loaded()


    def _set_status_loaded(self):
        self.label_status.setText("Загружена!")
        self.label_status.setStyleSheet("QLabel {color: green;}")

    def _set_status_unloaded(self):
        self.label_status.setText("Не загружена!")
        self.label_status.setStyleSheet("QLabel {color: red;}")
