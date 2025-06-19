from typing import List, Any

import numpy as np
import torch
import cv2
from PyQt5.QtCore import QObject, QPointF
from ultralytics import SAM


class USam2Net(QObject):
    def __init__(self, model_path: str, parent=None):
        super().__init__(parent)
        self.device = self._get_cuda_devices()
        self.model = SAM(model_path).to(self.device)

        self.predicting = False

    def is_predicting(self):
        return self.predicting

    def _get_cuda_devices(self):
        if torch.cuda.is_available():
            count = torch.cuda.device_count()
            if count == 1:
                return 0
            return [i for i in range(count)]
        return 'cpu'

    def _mask_to_polygons(self, mask: np.ndarray, epsilon: float = 1.0) -> list[list[QPointF]]:
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polygons = []
        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            polygon = [QPointF(float(pt[0][0]), float(pt[0][1])) for pt in approx]
            if len(polygon) >= 3:
                polygons.append(polygon)
        return polygons

    def segment_with_points(self, image: np.ndarray, points: list[tuple[int, int, int]]) -> list[list[QPointF]] | None:
        self.predicting = True

        xy = [[[p[0], p[1]] for p in points]]
        labels = [[p[2] for p in points]]
        print(xy, labels)
        results = self.model.predict(
            image,
            points=xy,
            labels=labels,
            device=self.device
        )

        polygons = []
        for mask in results[0].masks.data.cpu().numpy():
            polygons.extend(self._mask_to_polygons(mask))
        self.predicting = False
        return polygons

    def segment_with_box(self, image: np.ndarray, box: tuple[int, int, int, int]) -> list[list[tuple[Any]]] | None:
        self.predicting = True

        results = self.model.predict(
            image,
            bboxes=[list(box)],
            device=self.device
        )

        polygons = []
        for mask in results[0].masks.data.cpu().numpy():
            polygons.extend(self._mask_to_polygons(mask))
        self.predicting = False
        return polygons
