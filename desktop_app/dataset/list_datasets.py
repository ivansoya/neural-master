from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QListWidget, QListWidgetItem

from design.widget_dataset_item import Ui_widget_dataset_item
from utility import FAnnotationItem


class UItemDataset(QWidget, Ui_widget_dataset_item):
    def __init__(self, name: str, annotations: dict[str, list[FAnnotationItem]], parent = None):
        super().__init__(parent)
        self.setupUi(self)

        self.name = name
        self.count = sum(len(ann) for ann in annotations.values())
        self.label_name.setText(name)
        self.label_count.setText(f"Аннотаций: {self.count}")
        self.annotations = annotations

    def update(self):
        super().update()
        self.count = sum(len(ann) for ann in self.annotations.values())
        self.label_name.setText(self.name)
        self.label_count.setText(f"Аннотаций: {self.count}")

    def get_dataset_name(self):
        return self.name

    def get_annotations(self):
        return self.annotations


class UListDataset(QListWidget):
    signal_on_item_clicked = pyqtSignal(str, dict)

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
            self.signal_on_item_clicked.emit(widget.get_dataset_name(), widget.get_annotations())

    def update_all_items(self):
        for i in range(self.count()):
            widget = self.itemWidget(self.item(i))
            if widget and isinstance(widget, UListDataset):
                widget.update()

    def get_selected_item(self) -> tuple[int, str]:
        item = self.currentItem()
        if item:
            widget = self.itemWidget(item)
            if widget and isinstance(widget, UItemDataset):
                return self.row(item), widget.get_dataset_name()
        return -1, ""

    @staticmethod
    def get_item_widget(list_widget: 'UListDataset'):
        if list_widget is None:
            return
        item = list_widget.currentItem()
        if item:
            widget = list_widget.itemWidget(item)
            if widget and isinstance(widget, UItemDataset):
                return widget
        return