import sys

from PyQt5.QtWidgets import QApplication, QMainWindow
from design.train_app import Ui_TrainApp
from commander import UGlobalSignalHolder
from page_annotation import UPageAnnotation
from page_classes import UPageClasses
from page_dataset import UPageDataset
from page_load_create import UPageLoader
from page_model import UPageModel
from project import UTrainProject

class TrainApp(QMainWindow, Ui_TrainApp):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.project = UTrainProject()

        self.global_signal_holder = UGlobalSignalHolder()
        QApplication.instance().installEventFilter(self.global_signal_holder)

        self.page_save_load = UPageLoader(self.global_signal_holder, self.project)
        self.page_dataset = UPageDataset(self.global_signal_holder, self.project)
        self.page_annotation = UPageAnnotation(self.global_signal_holder, self.project)
        self.page_classes = UPageClasses(self.global_signal_holder, self.project)
        self.page_model = UPageModel(self.global_signal_holder, self.project)

        self.stacked_page_loader.addWidget(self.page_save_load)
        self.stacked_page_loader.addWidget(self.page_dataset)
        self.stacked_page_loader.addWidget(self.page_annotation)
        self.stacked_page_loader.addWidget(self.page_classes)
        self.stacked_page_loader.addWidget(self.page_model)

        self.stacked_page_loader.setCurrentIndex(0)

        self.button_to_datasets_settings.clicked.connect(lambda: self.change_page(1))
        self.button_to_annotation_scene.clicked.connect(lambda: self.change_page(2))
        self.button_to_statistics.clicked.connect(lambda: self.change_page(3))
        self.button_to_model.clicked.connect(lambda: self.change_page(4))

        self.nav_bar.setVisible(False)
        self.nav_bar.setEnabled(False)

        self.global_signal_holder.project_load_complete.connect(self.handle_on_load_project)

    def change_page(self, page_index: int):
        self.stacked_page_loader.setCurrentIndex(page_index)

    def handle_on_load_project(self):
        self.nav_bar.setVisible(True)
        self.nav_bar.setEnabled(True)
        self.change_page(1)

def main():
    app = QApplication(sys.argv)
    window = TrainApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
