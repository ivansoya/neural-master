from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtCore import Qt

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
