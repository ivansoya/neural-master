from typing import Optional

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QDialog, QColorDialog

from add_class_window import Ui_dialog_add_class
from commander import UGlobalSignalHolder
from utility import FClassData


class UAddClassWindow(QDialog, Ui_dialog_add_class):

    def __init__(self, id_class: int, commander: UGlobalSignalHolder = None, parent = None):
        super().__init__(parent)
        self.setupUi(self)
        self.id_class = id_class
        self.class_name: str = ""
        self.selected_color: Optional[QColor] = None
        self.commander = commander

        self.button_choose_color.clicked.connect(self.choose_color)
        self.button_confirm.clicked.connect(self.confirm)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color

            palette = self.label_color.palette()
            palette.setColor(QPalette.Window, self.selected_color)
            self.label_color.setAutoFillBackground(True)
            self.label_color.setPalette(palette)

    def confirm(self):
        class_name = self.lineedit_name_class.text().strip()
        if not class_name:
            print("Не указано название класса!")
            return
        else:
            self.class_name = class_name
        if self.selected_color is None:
            self.selected_color = FClassData.get_save_color(self.id_class)

        class_data = FClassData(self.id_class, self.class_name, self.selected_color)

        if self.commander is not None:
            self.commander.added_new_class.emit(class_data)
            self.commander.set_block(False)

        self.close()

