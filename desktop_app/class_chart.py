from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

class FCountColor:
    def __init__(self, count: int, color: QColor):
        self.count = count
        self.color = color

    def increment_count(self):
        self.count += 1

    def __str__(self):
        return f"{self.count}: {self.color}"

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)

class UWidgetChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout_v = QVBoxLayout(self)

        # Полотно для графика
        self.canvas = MplCanvas(self)
        self.layout_v.addWidget(self.canvas)

    def draw_chart(self, classes: dict[str, FCountColor]):
        self.canvas.ax.clear()

        class_names = list(classes.keys())
        print(class_names)
        counts = [item.count for item in classes.values()]
        print(classes.values())
        colors = [(item.color.redF(), item.color.greenF(), item.color.blueF()) for item in classes.values()]

        self.canvas.ax.bar(class_names, counts, color=colors)

        self.canvas.ax.set_title("Количество используемых классов")
        self.canvas.ax.set_ylabel("Количество")

        self.canvas.draw()