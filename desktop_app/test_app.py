import sys
import cv2
import os
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, \
    QWidget, QScrollArea, QGraphicsScene, QGraphicsPixmapItem, QGraphicsView
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer

from design import Ui_TrainApp
from annotable import ResizableRect, ImageAnnotationScene, UAnnotableGraphicsView
from custom_widgets import UHorizontalScrollArea

class ExampleApp(QMainWindow, Ui_TrainApp):
    def __init__(self):
        # Это здесь нужно для доступа к переменным, методам
        # и т.д. в файле design.py
        super().__init__()
        self.setupUi(self)  # Это нужно для инициализации нашего дизайна

        self.image_paths = []
        self.image_thumbnails = []
        self.image_on_scene = None
        self.thumbnail_size = 150
        self.selected_size = 200
        self.selected_thumbnail = None

        self.graphics_scene = ImageAnnotationScene()
        self.image_view.setScene(self.graphics_scene)

        self.toggle_round_images.setVisible(False)
        self.round_images.setVisible(False)

        self.load_images_button.clicked.connect(self.load_images)

        self.toggle_round_images.clicked.connect(self.toggle_roulette_visibility)

    def load_images(self):
        # Открываем диалог для выбора нескольких изображений
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "",
                                                     "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_paths:
            self.image_paths = file_paths

            # Очистка старого контента
            for thumb in self.image_thumbnails:
                thumb.deleteLater()
            self.image_thumbnails.clear()

            # Убедитесь, что scroll_content имеет компоновщик
            layout = self.scroll_content.layout()
            if layout is None:
                layout = QHBoxLayout(self.scroll_content)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(10)
            else:
                # Удаляем предыдущие виджеты из компоновщика
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

            # Показываем область прокрутки
            self.round_images.setVisible(True)
            self.toggle_round_images.setEnabled(True)
            self.toggle_round_images.setVisible(True)

            # Динамическая загрузка миниатюр
            self.load_thumbnails(layout)

    def load_thumbnails(self, layout):
        if self.image_paths:
            image_path = self.image_paths.pop(0)

            # Создаем QLabel для миниатюры
            thumb_label = QLabel()
            thumb_label.setStyleSheet("background-color: lightgray;")
            thumb_label.setAlignment(Qt.AlignCenter)

            # Загружаем и показываем миниатюру
            pixmap = QPixmap(image_path)
            thumb_label.setPixmap(pixmap.scaledToHeight(
                self.thumbnail_size, Qt.SmoothTransformation
            ))
            thumb_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)

            # Привязываем событие клика
            thumb_label.mousePressEvent = lambda event, path=image_path: self.thumbLambdaBody(thumb_label, path)

            # Добавляем миниатюру в компоновщик
            layout.addWidget(thumb_label)
            self.image_thumbnails.append(thumb_label)

            # Если первый раз, то показываем изображение и выбираем миниатюру
            if layout.count() == 1:
                self.thumbLambdaBody(thumb_label, image_path)
                #self.fit_image_to_view()

            # Переход к следующей миниатюре
            QTimer.singleShot(50, lambda: self.load_thumbnails(layout))

    def selectActiveThumbnail(self, thumbnail):
        if self.selected_thumbnail is not None:
            self.selected_thumbnail.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        if thumbnail is not None:
            thumbnail.setFixedSize(self.selected_size, self.selected_size)
            self.selected_thumbnail = thumbnail

            # Прокручиваем область, чтобы выбранная миниатюра была в центре
            scroll_area_width = self.round_images.width()
            scroll_content_width = self.scroll_content.layout().count() * (self.thumbnail_size + 10)
            selected_index = self.image_thumbnails.index(thumbnail)
            scroll_position = max(0, selected_index * (self.thumbnail_size + 10) - scroll_area_width // 2 + self.thumbnail_size // 2)
            self.round_images.horizontalScrollBar().setValue(scroll_position)

    def displayImage(self, image_path):
        # Загрузка
        image = cv2.imread(image_path)
        if image is not None:
            # Convert to RGB for displaying in QLabel
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width, channel = image.shape
            bytes_per_line = 3 * width
            qimg = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.image_on_scene = QGraphicsPixmapItem(pixmap)
            self.graphics_scene.clear()
            self.graphics_scene.addItem(self.image_on_scene)
            self.image_on_scene.setPos(16000 - self.image_on_scene.boundingRect().width() // 2,
                                       16000 - self.image_on_scene.boundingRect().height() // 2)


    def toggle_roulette_visibility(self):
        if self.round_images.isVisible():
            self.round_images.setVisible(False)
            self.toggle_round_images.setText("Показать карусель")
        else:
            self.round_images.setVisible(True)
            self.toggle_round_images.setText("Скрыть карусель")

    def fit_image_to_view(self):
        if self.image_on_scene:
            rect = self.image_on_scene.boundingRect()
            self.image_view.fitInView(rect, Qt.KeepAspectRatio)

    def thumbLambdaBody(self, thumbnail, image_path):
        self.selectActiveThumbnail(thumbnail)
        self.displayImage(image_path)

def main():
    app = QApplication(sys.argv)
    window = ExampleApp()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
