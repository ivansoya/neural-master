from typing import Optional

from PyQt5.QtWidgets import QWidget, QStackedWidget

from commander import UGlobalSignalHolder
from design.dataset_page import Ui_page_dataset
from project import UTrainProject


class UPageDataset(QWidget, Ui_page_dataset):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.commander: Optional[UGlobalSignalHolder] = None
        self.project: Optional[UTrainProject] = None

    def initialize(self, commander: UGlobalSignalHolder, project: UTrainProject):
        self.commander = commander
        self.project = project

        self.button_to_annotation_scene.clicked.connect(self.get_to_annotation_page)

    def get_to_annotation_page(self):
        print("Я нажал, блдяь!")
        if isinstance(self.parent(), QStackedWidget):
            self.parent().setCurrentIndex(1)