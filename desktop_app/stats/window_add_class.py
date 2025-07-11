from enum import Enum

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDialog, QColorDialog, QMessageBox

from design.dialog_add_class import Ui_dialog_add_class
from supporting.functions import get_distinct_color

class EAddClassStrings(Enum):
    CLASS_ID = "class_id",
    CLASS_NAME = "class_name",
    SUPERCATEGORY = "supercategory",
    COLOR = "color"

class UWindowClass(QDialog, Ui_dialog_add_class):
    def __init__(self, class_id: int, data: tuple[str, str, QColor] | None = None, parent=None):
        super().__init__(parent)

        self.setupUi(self)

        self.class_id = class_id

        self.result_data = {
            EAddClassStrings.CLASS_ID: class_id,
            EAddClassStrings.CLASS_NAME: data[0] if data else None,
            EAddClassStrings.SUPERCATEGORY: data[1] if data else None,
            EAddClassStrings.COLOR: QColor(data[2]) if data else get_distinct_color(self.class_id),
        }

        self.update_background_label_color()

        self.button_choose_color.clicked.connect(self.choose_color)
        self.button_add_class.clicked.connect(self.accept_if_valid)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.result_data[EAddClassStrings.COLOR] = color

        self.update_background_label_color()

    def accept_if_valid(self):
        class_name = self.lineedit_class_name.text().strip()
        supercategory = self.lineedit_supercategory.text().strip()

        if not class_name or not supercategory:
            QMessageBox.warning(self, "Ошибка", "Оба поля должны быть заполнены.")
            return

        self.result_data[EAddClassStrings.CLASS_NAME] = class_name
        self.result_data[EAddClassStrings.SUPERCATEGORY] = supercategory

        self.accept()

    def update_background_label_color(self):
        import re
        style = self.label_class_color.styleSheet()

        style = re.sub(r'background-color\s*:\s*[^;]+;', '', style)
        style = style.strip()
        if style and not style.endswith(';'):
            style += ';'

        style += f' background-color: {self.result_data[EAddClassStrings.COLOR].name()};'
        self.label_class_color.setStyleSheet(style)

    def get_result(self):
        return self.result_data