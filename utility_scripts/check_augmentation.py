import sys
import cv2
import numpy as np
import albumentations as A
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QFileDialog
from PyQt5.QtGui import QPixmap, QImage


def load_cv_image(file_path: str):
    data = np.fromfile(file_path, dtype=np.uint8)  # читаем как байты
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)  # декодируем как картинку
    return img

class AugmentationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Albumentations Demo")
        self.resize(800, 600)

        # UI элементы
        self.image_label = QLabel("Загрузите изображение", self)
        self.image_label.setScaledContents(True)
        self.btn_load = QPushButton("Загрузить изображение", self)
        self.btn_aug = QPushButton("Аугментировать", self)
        self.btn_aug.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.btn_load)
        layout.addWidget(self.btn_aug)
        self.setLayout(layout)

        # Сигналы
        self.btn_load.clicked.connect(self.load_image)
        self.btn_aug.clicked.connect(self.apply_augmentation)

        # Переменные
        self.original_image = None

        # 2. Ночные аугментации (низкая яркость, контраст)
        self.transform = A.Compose([
            A.RandomSunFlare(flare_roi=(0, 0, 1, 0.5), p=0.2),
            A.GaussNoise(std_range=(0.1, 0.2), p=0.75),
            A.MotionBlur(blur_limit=(14, 22), angle_range=(0, 90), direction_range=(-0.5, 0.5), p=0.4),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=0.5),
            A.Sharpen(alpha=(0.2, 0.5), lightness=(0.5, 1), kernel_size=5, sigma=1, p=1),
            A.Defocus(radius=(3, 10), alias_blur=(0.1, 0.5), p=0.25)
        ])

        self.transform = A.Compose([
            A.CLAHE(p=0.3),
            A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=1),
            A.Erasing(scale=(0.02, 0.3), ratio=(0.3, 3.3), p=0.3),
            A.BBoxSafeRandomCrop(erosion_rate=0.1, p=0.3),
            A.SafeRotate(limit=(-90, 90), p=0.2),
        ], bbox_params=A.BboxParams(format='pascal_voc'))

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать изображение", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.original_image = load_cv_image(file_path)
            self.show_image(self.original_image)
            self.btn_aug.setEnabled(True)

    def apply_augmentation(self):
        if self.original_image is None:
            return
        h, w = self.original_image.shape[:2]
        dummy_bbox = [0, 0, w, h]
        augmented = self.transform(image=self.original_image, bboxes=[dummy_bbox])["image"]
        self.show_image(augmented)

    def show_image(self, img):
        """Преобразует OpenCV-изображение в QPixmap и показывает"""
        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(min(800, w), min(600, h))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AugmentationApp()
    win.show()
    sys.exit(app.exec_())
