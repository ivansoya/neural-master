import sys

from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, \
    QWidget, QScrollArea, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView, QGraphicsRectItem
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QImage, QPixmap, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from design.train_app import Ui_TrainApp
from commander import UGlobalSignalHolder
from project import UTrainProject


class TrainApp(QMainWindow, Ui_TrainApp):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.project = UTrainProject()

        self.global_signal_holder = UGlobalSignalHolder()
        QApplication.instance().installEventFilter(self.global_signal_holder)

        self.page_annotation.initialize(self.global_signal_holder, self.project)
        self.page_save_load.initialize(self.global_signal_holder, self.project)
        self.page_dataset.initialize(self.global_signal_holder, self.project)

        self.stacked_page_loader.setCurrentIndex(0)


def main():
    app = QApplication(sys.argv)
    window = TrainApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
