from typing import Optional

from PyQt5.QtWidgets import QWidget, QStackedWidget, QFileDialog, QDialog

from commander import UGlobalSignalHolder
from design.page_save_load import Ui_page_load_dataset
from design.window_create_project import Ui_window_create_project
from project import UTrainProject


class UPageLoader(QWidget, Ui_page_load_dataset):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.commander: Optional[UGlobalSignalHolder] = None
        self.project: Optional[UTrainProject] = None

    def initialize(self, commander: UGlobalSignalHolder, project: UTrainProject):
        self.commander = commander
        self.project = project

        self.button_create_train_project.clicked.connect(self.create_project)
        self.button_skip_creation.clicked.connect(self.get_to_annotation_page)

    def get_to_annotation_page(self):
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(1)

    def create_project(self):

        pass


class QDialogCreateProject(QDialog, Ui_window_create_project):

    def __init__(self, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.project_name: str = ""
        self.project_path: str = ""

    def set_project_name(self):
        pass

