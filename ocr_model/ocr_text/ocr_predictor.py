import cv2
import torch
import numpy as np
import os
from PIL import Image
from torchvision import transforms

# ĐÃ SỬA: Import model mới
from ocr_text.model_ocr import CRNN_ResNet
from config import *
from ocr_model.ocr_text.utils import StrLabelConverter, VIETNAMESE_ALPHABET


class OCRPredictor(object):
    def __init__(self):
        # Đường dẫn weight (Nên trỏ tới file weight_ocr_text_v2.pth khi train xong)
        self.checkpoint_path = os.path.join(folder_weight, "weight_ocr_text/weight_ocr_text.pth")

        self.imgH = 32
        self.n_hidden = 256
        self.alphabets = VIETNAMESE_ALPHABET
        self.nclass = len(self.alphabets) + 1
        self.converter = StrLabelConverter(self.alphabets)

        # self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.device = "cpu"


        # ĐÃ SỬA: Gọi CRNN_ResNet và XÓA tham số imgH
        self.model = CRNN_ResNet(nc=1, nclass=self.nclass, nh=self.n_hidden)
        self.model.to(self.device)

        # Load Checkpoint
        self.checkpoint = torch.load(self.checkpoint_path, map_location=self.device)

        # Xử lý format dict của file checkpoint mới
        if isinstance(self.checkpoint, dict) and 'model' in self.checkpoint:
            self.state_dict = self.checkpoint['model']
        else:
            self.state_dict = self.checkpoint

        self.model.load_state_dict(self.state_dict)
        self.model.eval()  # Bắt buộc để tắt Dropout/BatchNorm khi infer

    def predict_crnn(self, image_input):
        if isinstance(image_input, np.ndarray):
            # Chuyển BGR (OpenCV) sang Grayscale (L) vì nc=1
            image = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB)).convert('L')
        else:
            raise ValueError("Hàm này trong pipeline nhận đầu vào là numpy array (crop từ cv2)")

        # Tiền xử lý ảnh
        image = self.transform_image(image)
        image = image.unsqueeze(0).to(self.device)  # Thêm batch_size = 1

        # Dự đoán
        with torch.no_grad():
            preds = self.model(image)

        # Giải mã kết quả
        _, preds_index = preds.max(2)
        preds_index = preds_index.transpose(1, 0).contiguous()

        pred_str = self.converter.decode(preds_index.view(-1), torch.IntTensor([preds_index.size(1)]), raw=False)

        # Đảm bảo pred_str là string (đề phòng converter trả về list 1 phần tử)
        if isinstance(pred_str, list):
            pred_str = pred_str[0]

        pred_str = pred_str.replace("#", "/")

        return pred_str if pred_str else ""

    def transform_image(self, img, interpolation=Image.BILINEAR):
        # 1. Lấy kích thước thật của ảnh crop
        w, h = img.size

        # 2. Tính toán chiều ngang mới (new_w) dựa trên tỷ lệ, giữ chiều cao = 32
        # Ép new_w tối thiểu phải bằng 64 để tránh lỗi model nếu ảnh quá ngắn
        new_w = max(64, int(w * (self.imgH / h)))

        # 3. Resize với tỷ lệ chuẩn, không làm méo chữ
        img = img.resize((new_w, self.imgH), interpolation)

        # Chuyển thành Tensor và Normalize về đoạn [-1, 1]
        img = transforms.ToTensor()(img)
        img = img.sub_(0.5).div_(0.5)  # Dùng inplace operation (_ ) cho nhanh

        return img