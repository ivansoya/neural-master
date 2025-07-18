import ultralytics
from ultralytics import YOLO
from ultralytics.data.split import autosplit

ultralytics.checks()

autosplit(path="/home/voran/voran-ftp-sync/training/2025.07.16/",
          weights=(0.8, 0.2, 0.0),
          annotated_only=False,)


# Load a model
model = YOLO("/home/voran/voran-ftp-sync/training/yolo11/yolo11n.pt")  # build a new model from YAML
#model = YOLO("yolo11s.pt")  # load a pretrained model (recommended for training)
#model = YOLO("yolo11s.yaml").load("yolo11s.pt")  # build from YAML and transfer weights

# Train the model
results = model.train(
  data="/home/voran/voran-ftp-sync/training/data.yaml",
  epochs=200, 
  imgsz=640, 
  device=0,
  optimizer="AdamW"
  #lrf=0.2,
  #weight_decay=0.0001
)
