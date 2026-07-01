import cv2
import torch
import numpy as np
from PIL import Image
import torchvision.transforms as transforms
import os
from ultralytics import YOLO
from config import *

class TextDetector():
    def __init__(self):
        self.detector_text = YOLO(os.path.join(folder_weight, "weight_detect_text/weight_detect_text.pt"))
        self.imgsz = 1024
        self.conf = 0.15
        self.iou = 0.45
        self.max_det = 1000
        self.augment = True
        self.agnostic_nms = True
        # self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.device = "cpu"

        self.verbose = False

    def predict(self,image):
        image = self.load_image(image)
        img_h, img_w = image.shape[:2]

        if image is None :
            return None

        results = self.detector_text.predict(
            source=image,
            imgsz=self.imgsz,
            conf=self.conf ,
            iou= self.iou,
            max_det=self.max_det,
            augment=self.augment,
            agnostic_nms=self.agnostic_nms,
            device= self.device ,
            verbose=self.verbose
        )

        if results :
            boxes_data = []
            for r in results:
                for box in r.boxes:
                    coords = box.xyxy[0].cpu().numpy().astype(int)
                    score = float(box.conf[0].cpu().item())
                    x1, y1, x2, y2 = coords

                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(img_w, x2)
                    y2 = min(img_h, y2)

                    if x2 <= x1 or y2 <= y1:
                        continue

                    crop_img = image[y1:y2, x1:x2]

                    boxes_data.append({
                        'box': [x1, y1, x2, y2],
                        "score"  :score,
                        'crop': crop_img
                    })
            lines_of_boxes = self.sort_boxes_and_group_lines(boxes_data)
            if lines_of_boxes:
                return lines_of_boxes
        return None

    def sort_boxes_and_group_lines(self, boxes_data, line_threshold_ratio=0.25):

        if not boxes_data:
            return []

        for item in boxes_data:
            x1, y1, x2, y2 = item['box']
            item['cy'] = (y1 + y2) / 2.0
            item['h'] = y2 - y1

        boxes_data.sort(key=lambda x: x['cy'])

        lines = []
        current_line = [boxes_data[0]]

        for item in boxes_data[1:]:
            prev_item = current_line[-1]

            avg_h = (item['h'] + prev_item['h']) / 2.0

            if abs(item['cy'] - prev_item['cy']) < (avg_h * line_threshold_ratio):
                current_line.append(item)
            else:
                lines.append(current_line)
                current_line = [item]

        if current_line:
            lines.append(current_line)

        for line in lines:
            line.sort(key=lambda x: x['box'][0])

        return lines

    def load_image(self,image):
        if isinstance(image, str):
            if not os.path.exists(image):
                return None
            img = cv2.imread(image)
            if img is None:
                return None
            return img

        if isinstance(image, np.ndarray):
            if image.ndim in [2, 3]:
                return image

        if isinstance(image, Image.Image):
            img = np.array(image)
            if img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        return None
