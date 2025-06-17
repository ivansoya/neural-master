from PyQt5.QtWidgets import QComboBox

from utility import EAnnotationType


class EnumComboBox(QComboBox):
    def __init__(self, parent=None, members: dict[str, list[EAnnotationType]] = None):
        super().__init__(parent)
        self.members = members
        if self.members:
            for member_key, member_value in self.members.items():
                self.addItem(member_key)

    def get_current_enum(self):
        text = self.currentText()
        return self.members.get(text, [])

    def set_members(self, members: dict[str, list[EAnnotationType]]):
        self.clear()
        self.members = members
        for member_key, member_value in self.members.items():
            self.addItem(member_key)