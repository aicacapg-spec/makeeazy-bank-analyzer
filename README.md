# MakeEazy Bank Statement Analyzer

> Bank Statements Decoded. CA Workflows Accelerated.

Zero-cost, self-hosted bank statement analysis platform for CA firms. Supports **40+ Indian banks**, PDF/Excel/CSV formats, with **25 analysis modules** including cash flow, salary detection, EMI tracking, AML signals, and fraud detection.

## 🚀 Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

## 📊 Features

- **Multi-Format Upload** — PDF, Excel (.xlsx/.xls), CSV, TXT
- **Password-Protected PDF** support
- **40+ Indian Banks** — HDFC, SBI, ICICI, Axis, Kotak, PNB, and more
- **50+ Transaction Categories** — UPI, NEFT, RTGS, IMPS sub-categories
- **25 Analysis Modules** — Health Score, Cash Flow, Salary, EMI, AML, Fraud
- **7-Tab Dashboard** — Overview, Transactions, Salary, EMI, Suspicious, Top Txns, Bank Charges
- **Mobile Responsive** — Works on any device
- **JSON Export** — Download full analysis data

## 🏗️ Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Backend | Python + FastAPI | Free |
| Frontend | React + Vite + TypeScript | Free |
| Database | SQLite (swappable to PostgreSQL) | Free |
| PDF Parsing | pdfplumber | Free |
| Charts | Recharts | Free |
| Icons | Lucide React | Free |
| Deployment | Render.com | Free Tier |

**Total Cost: ₹0**

## 🏦 Supported Banks

HDFC, SBI, ICICI, Axis, Kotak, PNB, Bank of Baroda, Canara, Union Bank, IDBI, Yes Bank, IndusInd, Federal, Bandhan, IDFC First, RBL, AU SFB, Equitas, Ujjivan, Paytm, Standard Chartered, HSBC, Citi, DBS, and more.

## 📦 Deployment

### Render.com (Recommended — Free)
1. Push to GitHub
2. Connect repo on render.com
3. It auto-detects `render.yaml`
4. Deploy!

## 📄 License

Private — Built for CA firms by MakeEazy.
