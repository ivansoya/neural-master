from enum import Enum

class EAnnotationMode(Enum):
    DragMode = 1
    AnnotateMode = 2

class FClassRectStruct:
    def __init__(self, name, class_id, color):
        self.Name = name
        self.Class_Id = class_id
        self.Color = color
