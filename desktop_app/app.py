import sys
import cv2
import os
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Roulette with OpenCV")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: lightgray;")
        self.image_label.setMinimumHeight(600)
        self.main_layout.addWidget(self.image_label)


        # Button to load images
        self.load_images_button = QPushButton("Load Image Directory")
        self.load_images_button.clicked.connect(self.load_images)
        self.main_layout.addWidget(self.load_images_button)

        # Scroll area for the image roulette
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVisible(False)
        self.scroll_content = QWidget()
        self.scroll_layout = QHBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)

        # Button to toggle visibility of the image roulette
        self.toggle_roulette_button = QPushButton("Hide Image Roulette")
        self.toggle_roulette_button.setEnabled(False)
        self.toggle_roulette_button.setVisible(False)
        self.toggle_roulette_button.clicked.connect(self.toggle_roulette_visibility)
        self.main_layout.addWidget(self.toggle_roulette_button)

        self.image_paths = []
        self.image_thumbnails = []
        self.thumbnail_size = 200

        # Enable horizontal scrolling with mouse wheel
        self.scroll_area.installEventFilter(self)

    def load_images(self):
        # Открываем диалог для выбора нескольких изображений
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "",
                                                     "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_paths:
            # Присваиваем выбранные пути
            self.image_paths = file_paths

            # Очищаем предыдущие миниатюры
            for thumb in self.image_thumbnails:
                thumb.deleteLater()
            self.image_thumbnails.clear()

            # Настроим высоту области прокрутки для миниатюр
            self.scroll_area.setFixedHeight(self.thumbnail_size)

            # Показываем область прокрутки и активируем кнопку для переключения
            self.scroll_area.setVisible(True)
            self.toggle_roulette_button.setEnabled(True)
            self.toggle_roulette_button.setVisible(True)

            # Динамически загружаем миниатюры
            self.load_thumbnails()

    def load_thumbnails(self):
        if self.image_paths:
            image_path = self.image_paths.pop(0)

            thumb_label = QLabel()
            thumb_label.setStyleSheet("background-color: lightgray;")
            thumb_label.setAlignment(Qt.AlignCenter)

            # Load and display thumbnail
            pixmap = QPixmap(image_path)
            thumb_label.setPixmap(pixmap.scaledToHeight(
                self.scroll_area.height() - 20, Qt.SmoothTransformation
            ))
            thumb_label.setFixedHeight(self.scroll_area.height() - 20)
            thumb_label.setFixedWidth(self.scroll_area.height() - 20)  # Keep thumbnails square

            # Connect click event
            thumb_label.mousePressEvent = lambda event, path=image_path: self.display_image(path)

            self.scroll_layout.addWidget(thumb_label)
            self.image_thumbnails.append(thumb_label)

            # Schedule the next thumbnail loading
            QTimer.singleShot(50, self.load_thumbnails)

    def toggle_roulette_visibility(self):
        if self.scroll_area.isVisible():
            self.scroll_area.setVisible(False)
            self.toggle_roulette_button.setText("Show Image Roulette")
        else:
            self.scroll_area.setVisible(True)
            self.toggle_roulette_button.setText("Hide Image Roulette")

    def display_image(self, image_path):
        # Load the selected image with OpenCV
        print(image_path)
        image = cv2.imread(image_path)
        if image is not None:
            # Convert to RGB for displaying in QLabel
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width, channel = image.shape
            bytes_per_line = 3 * width
            qimg = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))

    def eventFilter(self, source, event):
        if source == self.scroll_area and event.type() == event.Wheel:
            delta = event.angleDelta().y()  # Используем только горизонтальное изменение (x)
            # Изменяем только горизонтальную прокрутку
            if delta != 0:
                self.scroll_area.horizontalScrollBar().setValue(
                    self.scroll_area.horizontalScrollBar().value() - delta
                )
            return True
        return super().eventFilter(source, event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
