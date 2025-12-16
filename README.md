# 🛠️ Nregabot Tools

> **A comprehensive automation suite for NREGA administrative tasks, optimized for efficiency and data management.**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)
![License](https://img.shields.io/badge/License-MIT-orange.svg)

---

## 📖 Overview

**Nregabot Tools** is a web-based utility application designed to simplify complex workflows associated with NREGA (Mahatma Gandhi National Rural Employment Guarantee Act) documentation. It automates invoice generation, simplifies labour list management, and provides smart data extraction tools, significantly reducing manual data entry errors and processing time.

The project is built with **Python (Flask)** and uses a lightweight **SQLite** database, making it suitable for both local deployment and cloud hosting.

---

## ✨ Key Features

### ⚡ Smart Contractor List Builder (New)
A powerful utility to generate precise labour lists from a Master Job Card database.

- **Village Filtering:** Automatically detects and filters labourers by Village Code (e.g., `006`, `021`).
- **Bulk Selection:** Smart paste functionality. Paste mixed identifiers (e.g., `245`, `006/660`, `502`) directly from WhatsApp or Excel.
- **Smart Matching:** Intelligently handles suffix matching (e.g., selects `002/6` without confusing it with `002/16`).
- **Conflict Detection:** Highlights ambiguous or duplicate entries in **red** for manual review.
- **Editing Support:** Upload an existing list to add or remove labourers without starting from scratch.

### 📝 Vendor & Invoice Management

- **Persistent Database:** Stores vendor details (GSTIN, bank information) in a local SQLite database.
- **Auto-Calculation:** Automatically computes CGST, SGST, and grand totals.
- **Text Parsing:** Paste raw bill text to auto-extract item names, rates, and quantities.

### 🔍 Data Extraction Utilities

- **Applicant List Parser:** Extracts structured data (Name, Job Card Number) from raw HTML files.
- **Work Code Extractor:** Pulls unique NREGA Work Codes from unstructured text blocks.

### 📋 Muster Roll Generator

- Rapidly generates formatted Muster Roll data suitable for printing or further processing.

---

## 🚀 Installation & Setup

Follow the steps below to run the application locally on macOS, Windows, or Linux.

### Prerequisites

- Python **3.10+**
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/rajatpoddar/Nregabot-tools.git
cd Nregabot-tools
```

### 2. Create a Virtual Environment

Using a virtual environment is strongly recommended.

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python app.py
```

Or using Flask directly:

```bash
flask run
```

Open your browser and navigate to:

```
http://127.0.0.1:5000
```

---

## 💡 How to Use: Contractor List Builder

1. **Upload Master List**  
   Navigate to *Contractor List* and upload your Master Applicant CSV file.

2. **Filter (Optional)**  
   Select a specific village from the dropdown to narrow the dataset.

3. **Bulk Select**  
   - Click the ⚡ **Bulk Select** button.  
   - Paste numbers separated by spaces, commas, or new lines (e.g., `201`, `205`, `006/660`).  
   - Click **Auto Select**.

4. **Review**  
   Click **Preview Selected**. Review rows highlighted in red (duplicates or conflicts) and remove unwanted entries.

5. **Download**  
   Click **Download Updated CSV** to obtain the finalized list.

---

## 📂 Project Structure

```text
Nregabot-tools/
├── app.py                    # Main Flask application logic
├── requirements.txt          # Python dependencies
├── vendors.db                # Local SQLite database
├── templates/                # HTML templates
│   ├── contractor_list.html  # Smart List Builder UI
│   ├── base.html             # Base layout & navigation
│   └── ...
├── static/                   # CSS, JavaScript, images
│   ├── style.css             # Main stylesheet (dark/light mode)
│   └── ...
└── README.md                 # Project documentation
```

---

## 🤝 Contributing

Contributions are welcome and appreciated.

1. Fork the repository.
2. Create your feature branch:
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add AmazingFeature"
   ```
4. Push to the branch:
   ```bash
   git push origin feature/AmazingFeature
   ```
5. Open a Pull Request.

---

## 👤 Author

**Rajat Poddar**  
GitHub: [@rajatpoddar](https://github.com/rajatpoddar)

---

Built with dedication for **Digital India**.

