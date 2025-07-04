from collections import OrderedDict

from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QScrollArea, QWidget, QLabel, QHBoxLayout, QListWidget, \
    QListWidgetItem, QVBoxLayout, QComboBox, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal

from annotation.annotation_item import UAnnotationItem
from annotation.annotation_polygon import UAnnotationPolygon
from annotation.annotation_scene import UAnnotationBox, UAnnotationGraphicsView
from utility import FAnnotationData, FDetectAnnotationData, FPolygonAnnotationData


class UHorizontalScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Устанавливаем горизонтальную полосу прокрутки
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

    def wheelEvent(self, event):
        # Перенаправляем колесо мыши на горизонтальную прокрутку
        if event.angleDelta().y() != 0:  # Убедимся, что движение произошло
            scroll_amount = event.angleDelta().y()  # Извлекаем величину прокрутки
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - scroll_amount
            )
        else:
            super().wheelEvent(event)  # Передаем обработку другим компонентам, если нужно

class UColorLabel(QLabel):
    def __init__(self, color: QColor = None, parent=None):
        super().__init__(parent)
        self.color = color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color if self.color else QColor(Qt.lightGray))
        super().paintEvent(event)

    def update_color(self, color: QColor):
        self.color = QColor(color)
        self.update()

class UListAnnotationWidget(QListWidget):
    item_selected = pyqtSignal(int)

    def __init__(self, parent = None):
        super().__init__(parent)
        self.itemClicked.connect(self.on_item_clicked)

        self.setSelectionMode(QListWidget.ExtendedSelection)

        self.widgets: list[UListAnnotationItem] = list()

    def on_item_clicked(self, item: QListWidgetItem):
        widget = self.itemWidget(item)
        if isinstance(widget, UListAnnotationItem):
            self.item_selected.emit(self.widgets.index(widget))

    def add_item(self, annotation_data: FAnnotationData):
        item = UListAnnotationItem(self.count() + 1, annotation_data)
        list_item = QListWidgetItem()
        list_item.setSizeHint(item.sizeHint())
        self.addItem(list_item)
        self.setItemWidget(list_item, item)

        self.widgets.append(item)

    def clear_annotations(self):
        self.clear()
        self.widgets.clear()

    def select_item(self, index: int, to_select: bool):
        if not 0 <= index < len(self.widgets):
            return

        self.item(index).setSelected(to_select)

    def update_item(self, index: int, annotation_data: FAnnotationData):
        if not 0 <= index < len(self.widgets):
            return

        self.widgets[index].set_data(annotation_data)

    def remove_item(self, index: int):
        if not 0 <= index < len(self.widgets):
            return

        widget_to_remove = self.widgets[index]

        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if widget == widget_to_remove:
                self.takeItem(i)  # удаляет и сам виджет из списка
                break

        del self.widgets[index]
        self._recalculate_indexes()

    def _recalculate_indexes(self):
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if isinstance(widget, UListAnnotationItem):
                widget.set_index(i + 1)


class UListAnnotationItem(QWidget):
    def __init__(self, index: int, annotation_data: FAnnotationData):
        super().__init__()
        self.index = index

        self.index_label = QLabel(str(index))
        index_font = QFont()
        index_font.setPointSize(10)
        self.index_label.setFont(index_font)

        self.color_label = UColorLabel()
        self.color_label.setFixedSize(30, 12)

        self.name_label = QLabel()
        name_font = QFont()
        name_font.setPointSize(10)
        self.name_label.setFont(name_font)

        self.type_label = QLabel()
        self.type_label.setFont(name_font)

        self.set_data(annotation_data)

        layout = QHBoxLayout()
        layout.addWidget(self.index_label)
        layout.addWidget(self.color_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.type_label)
        layout.addStretch()
        layout.setContentsMargins(4, 2, 4, 2)
        self.setLayout(layout)

    def set_data(self, annotation: FAnnotationData):
        if isinstance(annotation, FDetectAnnotationData):
            self.type_label.setText('бокс')
        elif isinstance(annotation, FPolygonAnnotationData):
            self.type_label.setText('маска')
        else:
            self.type_label.setText('неизвестно')

        self.name_label.setText(annotation.get_class_name())
        self.color_label.update_color(QColor(annotation.get_color()))

    def set_index(self, index: int):
        self.index = index
        self.index_label.setText(str(self.index))

    def get_index(self):
        return self.index


class UListClassCounts(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.class_widgets: dict[int, UListItemClassCount] = {}

    def increase_class(self, class_id: int, class_name: str, color: QColor):
        if class_id in self.class_widgets:
            self.class_widgets[class_id].increment()
        else:
            widget = UListItemClassCount(class_id, class_name, color)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())

            insert_row = 0
            for existing_id in sorted(self.class_widgets.keys()):
                if existing_id > class_id:
                    break
                insert_row += 1

            self.insertItem(insert_row, item)
            self.setItemWidget(item, widget)
            self.class_widgets[class_id] = widget

    def decrease_class(self, class_id: int):
        if class_id in self.class_widgets:
            widget = self.class_widgets[class_id]
            if widget.decrement():
                for i in range(self.count()):
                    if self.itemWidget(self.item(i)) == widget:
                        self.takeItem(i)
                        break
                del self.class_widgets[class_id]

    def clear(self):
        self.class_widgets.clear()
        super().clear()


class UListItemClassCount(QWidget):
    def __init__(self, class_id: int, class_name: str, color: QColor):
        super().__init__()

        self.class_id = class_id
        self.class_name = class_name
        self.count = 1

        self.color_box = UColorLabel(QColor(color))
        self.color_box.setFixedSize(20, 20)

        self.label_name = QLabel(class_name)
        self.label_count = QLabel(f"x {self.count}")

        font = QFont()
        font.setPointSize(10)
        self.label_name.setFont(font)
        self.label_count.setFont(font)
        self.label_name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self.label_name, 1)
        info_layout.addWidget(self.label_count, 0)

        info_container = QWidget()
        info_container.setLayout(info_layout)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)
        layout.addWidget(self.color_box, 0)
        layout.addWidget(info_container, 1)  # тянется

    def increment(self):
        self.count += 1
        self.label_count.setText(f"x {self.count}")

    def decrement(self):
        self.count -= 1
        self.label_count.setText(f"x {self.count}")
        return self.count <= 0
