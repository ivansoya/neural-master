from ultralytics import YOLO

IMGSZ = 640
BATCH = 8

# Load a model
model = YOLO("../trained_models/PyTorch/yolov8s.pt")

# Train the model
train_results = model.train(
    data="E:/neural_networks/Обучение Варана/dataset_start/data.yaml",  # path to dataset YAML
    epochs=100,  # number of training epochs
    imgsz=IMGSZ,  # training image size
    device="cpu",  # device to run on, i.e. device=0 or device=0,1,2,3 or device=cpu
    batch = BATCH,
)

# Evaluate model performance on the validation set
metrics = model.val(imgsz=IMGSZ, batch=BATCH)

#results = model("test_data/images/img.png")
#results[0].show()

#model.export(format="onnx", batch=BATCH, imgsz=IMGSZ, dynamic=False)