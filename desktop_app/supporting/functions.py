from PyQt5.QtCore import QPointF, QLineF
from PyQt5.QtWidgets import QGraphicsView


def clamp(value, min_, max_):
    return max(min_, min(value, max_))

def get_clamped_pos(scene: QGraphicsView, cursor_pos: QPointF, image) -> QPointF:
    cursor_pos_scene = scene.mapToScene(cursor_pos)
    cursor_pos_image = image.mapFromScene(cursor_pos_scene)
    cursor_pos_image.setX(clamp(cursor_pos_image.x(), 0, image.boundingRect().width()))
    cursor_pos_image.setY(clamp(cursor_pos_image.y(), 0, image.boundingRect().height()))
    return cursor_pos_image

def distance_to_line(point: QPointF, line: QLineF) -> float:
    x2x1 = line.p2().x() - line.p1().x()
    y2y1 = line.p2().y() - line.p1().y()
    y1p0 = line.p1().y() - point.y()
    x1p0 = line.p1().x() - point.x()

    return abs(x2x1 * y1p0 - y2y1 * x1p0) / ((x2x1 ** 2 + y2y1 ** 2) ** 0.5)

def distances_sum(point: QPointF, line: QLineF) -> float:
    point_l1 = ((line.x1() - point.x()) ** 2 + (line.y1() - point.y()) ** 2) ** 0.5
    point_l2 = ((line.x2() - point.x()) ** 2 + (line.y2() - point.y()) ** 2) ** 0.5

    return point_l1 + point_l2

def distance_to_center(point: QPointF, line: QLineF) -> float:
    center = QPointF((line.x1() + line.x2()) / 2, (line.y1() + line.y2()) / 2)

    return ((center.x() - point.x()) ** 2 + (center.y() - point.y()) ** 2) ** 0.5