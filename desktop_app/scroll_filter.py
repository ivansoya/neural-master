from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QScrollArea, QSpacerItem, QSizePolicy


class UFilterItem(QWidget):
    def __init__(self, color: QColor, class_id: int, name: str, parent = None):
        super().__init__(parent)

        self.color = color
        self.class_id = class_id
        self.name = name
        self.selected = True

        self.layout = QHBoxLayout(self)

        self.color_indicator = QLabel(self)
        self.color_indicator.setMaximumWidth(10)
        self.color_indicator.setStyleSheet(
            f"background-color: rgb({self.color.red()}, {self.color.green()}, {self.color.blue()});"
        )

        # Label с названием
        self.label = QLabel(self.name, self)
        self.label.setStyleSheet(
            f"background-color: rgba({self.color.red()}, {self.color.green()}, {self.color.blue()}, 100);"
            f"font-size: 12px;"
        )

        self.setStyleSheet(
            f"UFilterItem{{"
            f"border: }}"
        )

        # Добавляем элементы в layout
        self.layout.addWidget(self.color_indicator)
        self.layout.addWidget(self.label)

    def mousePressEvent(self, event):
        self.selected = not self.selected
        if self.selected:
            self.setStyleSheet(f"border: 2px solid rgb({self.color.red()}, {self.color.green()}, {self.color.blue()});")
        else:
            self.color_indicator.setStyleSheet("background-color: rgb(150, 150, 150);")
            self.label.setStyleSheet("background-color: rgba(112, 112, 112, 100);")
            self.setStyleSheet("border: none;")
        self.update()

    def get_class_id(self):
        return self.class_id


class UScrollFilter(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.container = QWidget()  # Контейнер для всех виджетов
        self.layout = QHBoxLayout(self.container)  # Горизонтальный лейаут
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        self.container.setLayout(self.layout)
        self.setWidget(self.container)
        self.setWidgetResizable(True)  # Позволяет контейнеру изменять размер
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Включаем горизонтальный скролл
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Отключаем вертикальный скролл


    def add_filter(self, color: QColor, class_id: int, class_name: str):
        item = UFilterItem(color, class_id, class_name)
        self.layout.addWidget(item)
        self.container.adjustSize()

    def get_filter_list(self):
        class_indexes = list()
        for index in range(self.layout.count()):
            widget = self.layout.itemAt(index)
            if isinstance(widget, UFilterItem):
                class_indexes.append(widget.get_class_id())

        return class_indexes