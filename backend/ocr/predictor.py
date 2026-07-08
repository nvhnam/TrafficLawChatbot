from .detector_text.detector_text import TextDetector
from .ocr_text.ocr_predictor import OCRPredictor
import cv2 as cv


class OCRGeneralPredictor:
    def __init__(self):
        self.model_detector = TextDetector()
        self.model_ocr = OCRPredictor()


    def predict_ocr(self, image):
        lines_of_boxes = self.model_detector.predict(image)

        if not lines_of_boxes:
            return None

        list_texts_result = []
        for line in lines_of_boxes:
            line_text = ""

            for item in line:
                crop_img = item['crop']
                text = self.model_ocr.predict_crnn(crop_img)

                if text:
                    line_text += text + " "
            if line_text.strip():
                list_texts_result.append(line_text)

        return list_texts_result
#
# if __name__ == '__main__':
#     predictor = OCRGeneralPredictor()
#     image = "/home/manh/Pictures/Screenshots/Screenshot from 2026-05-01 13-38-21.png"
#     image = cv.imread(image)
#     list_texts_result = predictor.predict_ocr(image)
#     print(list_texts_result)