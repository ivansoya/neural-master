from jinja2.optimizer import optimize
from sympy import simplify
from ultralytics import YOLO


# Load a model
model = YOLO("../trained_models/PyTorch/varan_s.pt")

model.export(format='rknn', dynamic=False)
