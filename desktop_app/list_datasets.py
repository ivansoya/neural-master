from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QListWidget, QListWidgetItem

from design.widget_dataset_item import Ui_widget_dataset_item
from utility import FAnnotationItem


class UItemDataset(QWidget, Ui_widget_dataset_item):
    def __init__(self, name: str, annotations: list[FAnnotationItem], count: int, parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.label_name.setText(name)
        self.label_count.setText(f"Аннотаций: {count}")
        self.annotations = annotations

    def get_annotations(self):
        return self.annotations

class UListDataset(QListWidget):
    signal_on_item_clicked = pyqtSignal(list)

    def __init__(self, parent = None):
        super().__init__(parent)
        self.itemClicked.connect(self.on_item_clicked)

    def add_dataset_item(self, item: UItemDataset):
        list_item = QListWidgetItem(self)
        list_item.setSizeHint(item.sizeHint())
        self.addItem(list_item)
        self.setItemWidget(list_item, item)

    def on_item_clicked(self, item: QListWidgetItem):
        widget = self.itemWidget(item)
        if isinstance(widget, UItemDataset):
            self.signal_on_item_clicked.emit(widget.get_annotations())