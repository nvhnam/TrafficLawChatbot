import torch
import unicodedata



VIETNAMESE_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" \
                      "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ" \
                      "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ" \
                      " !\"#$%&'()*+,-./:;<=>?@[]^_`{|}~"

# Gán biến này để code train/test import được
alphabets = VIETNAMESE_ALPHABET


class StrLabelConverter(object):
    def __init__(self, alphabet, ignore_case=False):
        self._ignore_case = ignore_case
        if self._ignore_case:
            alphabet = alphabet.lower()

        # Thêm ký tự '-' làm blank token cho CTC
        self.alphabet = alphabet + '-'

        self.dict = {}
        for i, char in enumerate(alphabet):
            self.dict[char] = i + 1

    def encode(self, text):
        length = []
        result = []
        for item in text:
            if isinstance(item, bytes):
                item = item.decode('utf-8', 'strict')
            item = unicodedata.normalize('NFC', item)
            length.append(len(item))
            for char in item:
                if self._ignore_case:
                    char = char.lower()
                try:
                    result.append(self.dict[char])
                except KeyError:
                    # In ra để debug (nếu cần)
                    print(f"Warning: Ký tự '{char}' chưa có trong alphabets -> Bị bỏ qua!")
                    continue
        return (torch.LongTensor(result), torch.LongTensor(length))

    def decode(self, t, length, raw=False):
        if length.numel() == 1:
            length = length[0]
            assert t.numel() == length, "Độ dài text và khai báo không khớp"
            if raw:
                return ''.join([self.alphabet[i - 1] if i > 0 else '-' for i in t])
            else:
                char_list = []
                for i in range(length):
                    if t[i] != 0 and (not (i > 0 and t[i - 1] == t[i])):
                        char_list.append(self.alphabet[t[i] - 1])
                return ''.join(char_list)
        else:
            texts = []
            index = 0
            for i in range(length.numel()):
                l = length[i]
                texts.append(
                    self.decode(
                        t[index:index + l], torch.LongTensor([l]), raw=raw))
                index += l
            return texts