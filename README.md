# Big Data UMKM Shopee Indonesia

# Pastikan sudah terinstall:
- Python / Anaconda
- XAMPP (untuk MySQL)
- MongoDB Community Server + Compass
- Java JDK 11+

---

## Langkah 1 — Siapkan File

Letakkan semua file dalam satu folder:
```
folder-proyek/
├── bidat.ipynb
├── dashboard.py
└── all_months.csv
```

---

## Langkah 2 — Install Library

Buka Anaconda Prompt / Terminal:
```bash
pip install pyspark pymysql sqlalchemy pymongo pandas numpy matplotlib seaborn plotly streamlit
```

---

## Langkah 3 — Jalankan MySQL (XAMPP)

1. Buka **XAMPP Control Panel**
2. Klik **Start** pada **Apache** dan **MySQL**
3. Pastikan keduanya **hijau** (Running)
4. Verifikasi: buka `http://localhost/phpmyadmin`

>  Port MySQL XAMPP default adalah **3307**, bukan 3306.

---

## Langkah 4 — Jalankan MongoDB

Buka CMD sebagai **Administrator**:
```bash
net start MongoDB
```

Verifikasi: buka **MongoDB Compass** → connect ke `mongodb://localhost:27017`

---

## Langkah 5 — Jalankan Notebook

1. Buka Anaconda Prompt → masuk ke folder proyek:
```bash
cd path/ke/folder-proyek
jupyter notebook
```
2. Buka `bidat.ipynb`
3. Jalankan semua cell dari atas ke bawah:
```
Menu: Kernel → Restart & Run All
```

> XAMPP dan MongoDB **wajib aktif** sebelum menjalankan notebook.

---

## Langkah 6 — Jalankan Dashboard

Setelah notebook selesai dijalankan minimal sampai Cell 11:
```bash
streamlit run dashboard.py
```
Buka browser: `http://localhost:8501`

---

## Konfigurasi 

Di **Cell 7** notebook dan **dashboard.py**, sesuaikan:
```python
MYSQL_PORT     = 3307   # ganti jika port XAMPP berbeda
MYSQL_PASSWORD = ""
MONGO_URI = "mongodb://localhost:27017/"
```

---
