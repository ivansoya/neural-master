from PyQt5.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget, QLabel, QHBoxLayout
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


class UClassListItemWidget(QWidget):
    def __init__(self, class_id: int, name: str, color: QColor, parent=None):
        super().__init__(parent)

        self.class_id = class_id
        self.name = name
        self.color = color

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        self.label_id = QLabel(str(class_id))
        self.label_id.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.label_name = QLabel(name)
        self.label_name.setAlignment(Qt.AlignCenter)
        self.label_name.setWordWrap(True)

        self.label_color = QLabel()
        self.label_color.setFixedSize(50, 20)
        self.label_color.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #333;")

        layout.addWidget(self.label_id)
        layout.addWidget(self.label_name, stretch=1)
        layout.addWidget(self.label_color)


class UClassListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.MultiSelection)

    def add_class_item(self, class_id: int, name: str, color: QColor):
        widget = UClassListItemWidget(class_id, name, color)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, class_id)

        self.addItem(item)
        self.setItemWidget(item, widget)

    def get_selected_class_ids(self) -> list:
        return [item.data(Qt.UserRole) for item in self.selectedItems()]
