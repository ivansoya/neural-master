from PyQt5.QtCore import QPointF, QLineF


def clamp(value, min_, max_):
    return max(min_, min(value, max_))

def distance_to_line(point: QPointF, line: QLineF) -> float:
    x2x1 = line.p2().x() - line.p1().x()
    y2y1 = line.p2().y() - line.p1().y()
    y1p0 = line.p1().y() - point.y()
    x1p0 = line.p1().x() - point.x()

    return abs(x2x1 * y1p0 - y2y1 * x1p0) / ((x2x1 ** 2 + y2y1 ** 2) ** 0.5)