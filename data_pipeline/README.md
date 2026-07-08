# Pipeline Xu Ly Du Lieu Phap Luat Giao Thong

Pipeline tu dong chuyen doi van ban phap luat (Markdown) thanh du lieu co cau truc (JSONL),
phuc vu cho he thong Knowledge Graph va chatbot truy van luat giao thong Viet Nam.

Toan bo pipeline chay local, khong can goi API ben ngoai.

## Tong quan quy trinh

```
File Markdown (.md)
        |
        v
[Buoc 1] Chunking (step1_chunking.py)
  Tach van ban theo cau truc Dieu/Khoan/Diem
        |
        v
[Buoc 2] Entity Extraction (step2_extract_local.py)
  Trich xuat thuc the 3 tang bang regex (khong can API)
        |
        v
[Buoc 3] Data Cleaning (step3_clean_data.py)
  Chuan hoa, bo sung ngu canh, resolve tham chieu
        |
        v
[Buoc 4] Evaluate (evaluate.py)
  Danh gia chat luong trich xuat
        |
        v
File JSONL (san sang cho Neo4j)
```

## Cau truc thu muc

```
data_pipeline/
|-- config.py                  # Cau hinh chung (duong dan, prompt template)
|-- config.yaml                # Tham so model va database
|-- requirements.txt           # Thu vien can cai dat
|-- run_pipeline.py            # Script chay toan bo pipeline
|-- step1_chunking.py          # Buoc 1: Tach van ban thanh chunks
|-- step2_extract_local.py     # Buoc 2: Trich xuat thuc the bang regex
|-- step3_clean_data.py        # Buoc 3: Lam sach du lieu
|-- evaluate.py                # Danh gia chat luong ket qua
|-- input/                     # Thu muc chua file Markdown dau vao
|-- output/
|   |-- chunks/                # Ket qua buoc 1 (JSON)
|   |-- entities_raw/          # Ket qua buoc 2 (JSONL)
|   |-- entities_cleaned/      # Ket qua buoc 3 (JSONL) - ket qua cuoi cung
```

## Huong dan cai dat

### 1. Cai dat thu vien

```bash
pip install -r requirements.txt
```

Chi can 3 thu vien: python-dotenv, PyYAML, Unidecode. Khong can GPU, khong can API key.

### 2. Chuan bi du lieu dau vao

Copy file Markdown can xu ly vao thu muc `input/`:

```bash
cp /duong/dan/den/123-2021nd-cp.md input/
```

## Huong dan su dung

### Chay toan bo pipeline

```bash
# Xu ly tat ca file .md trong thu muc input/
python run_pipeline.py

# Xu ly mot file cu the
python run_pipeline.py 123-2021nd-cp.md
```

### Chay tung buoc rieng le

```bash
# Chi chay buoc 1 (chunking)
python step1_chunking.py

# Chi chay buoc 2 (entity extraction)
python step2_extract_local.py

# Chi chay buoc 3 (cleaning)
python step3_clean_data.py
```

### Danh gia ket qua

```bash
# Danh gia noi bo (coverage, phan bo nhan, thong ke muc phat)
python evaluate.py output/entities_cleaned/123-2021nd-cp.jsonl

# So sanh voi du lieu tham chieu (tu du an goc)
python evaluate.py output/entities_cleaned/123-2021nd-cp.jsonl \
  --ref ../data/data_called_entities_best/100.signed.jsonl
```

## Chi tiet tung buoc

### Buoc 1: Chunking (step1_chunking.py)

Tach van ban Markdown theo cau truc phan cap cua phap luat Viet Nam:

```
Phan > Chuong > Muc > Dieu > Khoan > Diem
```

Moi chunk dau ra chua:
- `content`: Noi dung van ban (co bom ngu canh Chuong/Muc vao dau)
- `metadata`: Vi tri chinh xac trong cay phan cap

**Dau vao**: File `.md` (trong `input/`)
**Dau ra**: File `.json` (trong `output/chunks/`)

### Buoc 2: Entity Extraction (step2_extract_local.py)

Trich xuat thuc the theo mo hinh 3 tang bang regex:

| Tang | Noi dung | Vi du |
|------|----------|-------|
| Level_3_Foundations | Chu the, tham chieu van ban | "Nguoi dieu khien xe o to" |
| Level_2_Rules_Actions | Hanh vi vi pham, bien phap khac phuc | "Vuot den do" |
| Attributes_Measures | Muc phat, thoi han | "400.000 - 600.000 dong" |

Cac nhan ho tro: VIOLATION, MONEY_AMOUNT, PENALTY_MEASURE, SUBJECT,
DOCUMENT_RECORD, TIME_DURATION, PROCEDURE_ACTION, LEGAL_CONCEPT,
OBJECT_EQUIPMENT.

**Dau vao**: File `.json` (tu buoc 1)
**Dau ra**: File `.jsonl` (trong `output/entities_raw/`)

### Buoc 3: Data Cleaning (step3_clean_data.py)

5 cong doan lam sach:

1. **Chuan hoa ten van ban**: "Nghi dinh nay" -> "Nghi dinh so 100/2019/ND-CP"
2. **Bo sung ngu canh sua doi**: Gan context khi ND 123 sua doi ND 100
3. **Tinh chinh schema**: Gan the loai phuong tien, doi nhan giay to vat ly
4. **Trich xuat cay phan cap**: Document -> Article -> Clause -> Point
5. **Noi dao co lap**: Resolve "diem a khoan 2 Dieu 5" thanh noi dung that

**Dau vao**: File `.jsonl` (tu buoc 2)
**Dau ra**: File `.jsonl` (trong `output/entities_cleaned/`) - ket qua cuoi cung

### Buoc 4: Danh gia (evaluate.py)

Hai che do danh gia:

**Danh gia noi bo** (intrinsic): Khong can du lieu tham chieu
- Do bao phu (coverage): Ty le chunk co entity
- Phan bo nhan (label distribution)
- Thong ke muc phat (min, max)
- Mat do do thi (relationship/entity ratio)

**So sanh voi tham chieu** (extrinsic): Can file JSONL tu du an goc
- So sanh tong so entity, relationship
- So sanh phan bo nhan giua 2 he thong
- So sanh trung binh entity/chunk va mat do do thi

## Cau truc du lieu dau ra (JSONL)

Moi dong trong file JSONL cuoi cung la mot JSON object:

```json
{
  "Level_3_Foundations": [
    {
      "id": "abc123_e1",
      "label": "SUBJECT",
      "name": "Nguoi dieu khien xe o to",
      "value": "nguoi dieu khien xe o to, cac loai xe tuong tu"
    }
  ],
  "Level_2_Rules_Actions": [
    {
      "id": "abc123_e2",
      "label": "VIOLATION",
      "name": "Vuot den do",
      "value": "khong chap hanh hieu lenh den tin hieu giao thong"
    }
  ],
  "Attributes_Measures": [
    {
      "id": "abc123_e3",
      "label": "MONEY_AMOUNT",
      "name": "Tu 4.000.000 den 6.000.000 dong",
      "value": "phat tien tu 4.000.000 dong den 6.000.000 dong",
      "min": 4000000,
      "max": 6000000
    }
  ],
  "Relationships": [
    {"source": "abc123_e1", "type": "COMMITS", "target": "abc123_e2"},
    {"source": "abc123_e2", "type": "HAS_MONEY_AMOUNT", "target": "abc123_e3"}
  ],
  "metadata": {
    "document": "123-2021nd-cp",
    "dieu": "5",
    "khoan": "1",
    "diem": "a",
    "type": "LEGAL_RULE",
    "chunk_uuid": "abc123..."
  },
  "original_content": "..."
}
```

## Ket qua danh gia (ND 123/2021)

```
Tong chunks:              255
Tong thuc the:            513
Tong quan he:             228
Do bao phu:               100% (255/255 chunks co entity)

Phan bo nhan:
  VIOLATION:              186 (36.3%)
  MONEY_AMOUNT:           159 (31.0%)
  DOCUMENT_RECORD:         52 (10.1%)
  PENALTY_MEASURE:         41 ( 8.0%)
  LEGAL_CONCEPT:           35 ( 6.8%)
  TIME_DURATION:           18 ( 3.5%)
  SUBJECT:                 13 ( 2.5%)
  PROCEDURE_ACTION:         8 ( 1.6%)

Muc phat:
  Nho nhat:               100,000 VND
  Lon nhat:           120,000,000 VND
```

## Cac van ban dau vao can xu ly

| Van ban | File Markdown | Trang thai |
|---------|---------------|------------|
| Nghi dinh 100/2019/ND-CP | 100.signed.md | Da co JSONL (du an goc) |
| Nghi dinh 123/2021/ND-CP | 123-2021nd-cp.md | Da xu ly |
| Nghi dinh 168/2024/ND-CP | 168-nd-cp.signed.md | Da co JSONL (du an goc) |

## Luu y

- Toan bo pipeline chay offline, khong can internet
- Thoi gian xu ly 1 file: duoi 1 giay
- File `step2_extract_entities.py` (Gemini API) van duoc giu lai de tham khao
