from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QScrollArea, QSpacerItem, QSizePolicy


class UFilterItem(QWidget):
    signal_on_selected = pyqtSignal(int, bool)

    def __init__(self, color: QColor, class_id: int, name: str, parent = None):
        super().__init__(parent)

        self.color = QColor(color).darker(110)
        self.class_id = class_id
        self.name = name
        self.selected = True

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.color_indicator = QLabel(self)
        self.color_indicator.setMaximumWidth(10)

        # Label с названием
        self.label = QLabel(self.name, self)

        self._set_style_selected()

        # Добавляем элементы в layout
        self.layout.addWidget(self.color_indicator)
        self.layout.addWidget(self.label)

    def mousePressEvent(self, event):
        self.selected = not self.selected
        if self.selected:
            self._set_style_selected()
        else:
            self._set_style_not_selected()
        self.signal_on_selected.emit(self.class_id, self.selected)
        self.update()

    def get_class_id(self):
        return self.class_id

    def _set_style_selected(self):
        self.setStyleSheet(
            f"{self.__class__.__name__} {{"
            f"border: 2px solid rgb({self.color.red()}, {self.color.green()}, {self.color.blue()});"
            f"border-radius: 2px;"
            f"}}"
        )
        self.color_indicator.setStyleSheet(
            f"QLabel {{"
            f"background-color: rgb({self.color.red()}, {self.color.green()}, {self.color.blue()});"
            f"}}"
        )
        self.label.setStyleSheet(
            f"QLabel {{"
            f"background-color: rgba({self.color.red()}, {self.color.green()}, {self.color.blue()}, 100);"
            f"font-size: 12px;"
            f"padding: 2px 10px;"
            f"}}"
        )

    def _set_style_not_selected(self):
        self.setStyleSheet(
            f"{self.__class__.__name__} {{"
            f"border: 2px solid transparent;"
            f"border-radius: 2px;"
            f"}}"
        )
        self.color_indicator.setStyleSheet(
            f"QLabel {{"
            "background-color: rgb(150, 150, 150);"
            f"}}"
        )
        self.label.setStyleSheet(
            f"QLabel {{"
            f"background-color: rgba(112, 112, 112, 100);"
            f"font-size: 12px;"
            f"padding: 2px 10px;"
            f"}}"
        )


class UScrollFilter(QScrollArea):
    signal_on_item_clicked = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.container = QWidget()  # Контейнер для всех виджетов
        self.layout = QHBoxLayout(self.container)  # Горизонтальный лейаут
        self.layout.setContentsMargins(0, 5, 0, 5)
        self.layout.setSpacing(5)

        self.container.setLayout(self.layout)
        self.setWidget(self.container)
        self.setWidgetResizable(True)  # Позволяет контейнеру изменять размер
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Включаем горизонтальный скролл
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Отключаем вертикальный скролл


    def add_filter(self, color: QColor, class_id: int, class_name: str):
        item = UFilterItem(color, class_id, class_name)
        item.signal_on_selected.connect(
            lambda clicked_item_id, selected: self.signal_on_item_clicked.emit(clicked_item_id, selected)
        )
        self.layout.addWidget(item)
        self.container.adjustSize()

    def get_filter_list(self):
        class_indexes = list()
        for index in range(self.layout.count()):
            widget = self.layout.itemAt(index)
            if isinstance(widget, UFilterItem):
                class_indexes.append(widget.get_class_id())

        return class_indexes

    def wheelEvent(self, event):
        if event.angleDelta().y() != 0:  # Проверяем, крутим ли мы колесико
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - event.angleDelta().y() // 2
            )
            event.accept()