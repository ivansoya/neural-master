from PyQt5.QtCore import pyqtSignal, Qt, QObject
from PyQt5.QtWidgets import QGraphicsPixmapItem, QApplication, QGraphicsScene, QGraphicsView
from PyQt5.QtGui import QPixmap, QMouseEvent


class SignalEmitter(QObject):
    my_signal = pyqtSignal()  # Сигнал для обработки

    def __init__(self, parent=None):
        super().__init__(parent)

    def emit_signal(self):
        self.my_signal.emit()


class ClickablePixmapItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, signal_emitter, parent=None):
        super().__init__(pixmap, parent)
        self.signal_emitter = signal_emitter

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.signal_emitter.emit_signal()  # Генерируем сигнал через SignalEmitter
        super().mousePressEvent(event)


def on_item_clicked():
    print("Item clicked!")

app = QApplication([])

# Создаем сцену и виджет
scene = QGraphicsScene()
view = QGraphicsView(scene)

# Создаем картинку
pixmap = QPixmap(100, 100)  # Пример пустого изображения
pixmap.fill(Qt.red)  # Закрашиваем красным для примера

# Создаем объект для генерации сигнала
signal_emitter = SignalEmitter()

# Создаем элемент с картинкой и передаем ему объект signal_emitter
item = ClickablePixmapItem(pixmap, signal_emitter)

# Добавляем на сцену
scene.addItem(item)

# Подключаем сигнал my_signal к обработчику
signal_emitter.my_signal.connect(on_item_clicked)

# Отображаем
view.setScene(scene)
view.show()
app.exec_()
