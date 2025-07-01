from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor, QPainter
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

class UOverlayLoader(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setParent(parent)
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.label_dataset = QLabel("Загрузка данных...", self)
        self.label_dataset.setAlignment(Qt.AlignCenter)
        self.label_dataset.setStyleSheet("color: white; font-size: 16px;")

        self.label_annotation = QLabel("Пожалуйста, подождите", self)
        self.label_annotation.setAlignment(Qt.AlignCenter)
        self.label_annotation.setStyleSheet("color: white; font-size: 14px;")

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("text-align: center;")

        layout.addWidget(self.label_dataset)
        layout.addWidget(self.label_annotation)
        layout.addWidget(self.progress_bar)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # Создаем QPixmap для overlay
        self.pixmap = QPixmap(self.size())
        self.pixmap.fill(QColor(0, 0, 0, 200))  # Заполняем прозрачным фоном

        self.setLayout(layout)
        self.raise_()
        self.show()
        self.update()

    def update_label_dataset(self, text: str, current: int, count: int):
        self.label_dataset.setText(f"Загрузка датасета {text}: {current} из {count}")

    def update_label_annotation(self, text: str):
        self.label_annotation.setText(text)

    def update_progress(self, label: str, current: int, count: int):
        self.label_annotation.setText(label)
        self.progress_bar.setValue(int(float(current) / count * 100))

    def resizeEvent(self, event):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self.update()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)
        painter.end()

    @staticmethod
    def delete_overlay(overlay: 'UOverlayLoader'):
        if overlay:
            overlay.hide()
            overlay.deleteLater()
            return None
        return overlay
