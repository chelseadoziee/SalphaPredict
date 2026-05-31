# SalphaPredict

SalphaPredict is a web-based demand intelligence system for Salpha Energy. It helps the company analyse Excel-based sales data, understand product demand patterns, forecast future demand, and generate practical stock or inventory recommendations.

## Tech stack

- Python, Flask
- pandas, openpyxl, NumPy
- scikit-learn and Plotly (for later phases)
- HTML, CSS, JavaScript
- SQLite (planned for later phases)

## Project structure

```text
SalphaPredict/
├── app.py
├── config.py
├── requirements.txt
├── data/
├── uploads/
├── static/
├── templates/
├── logic/
├── models/
├── reports/
└── tests/
```

## Setup

1. Create and activate a virtual environment:

```bash
cd SalphaPredict
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. Run the app:

```bash
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Phase 1 features

- Branded homepage with project overview
- Upload page for Excel sales files (`.xlsx`, `.xls`)
- File saved to `uploads/`
- Basic preview showing filename, row count, and column names

## Mock data

A sample Excel file is available at `data/mock_data.xlsx`. It includes 12 months of Salpha product sales (2025) with these columns:

| Column | Description |
|--------|-------------|
| Date | Sale date |
| Product | Product name |
| Category | Product category (mock labels) |
| Quantity Sold | Units sold on that line |
| Unit Price | Selling price per unit (NGN) |
| Total Sales | Quantity Sold × Unit Price |
| Unit Cost | Estimated mock cost per unit (NGN) |
| Total Cost | Quantity Sold × Unit Cost |
| Profit | Total Sales − Total Cost |
| Profit Margin | (Profit ÷ Total Sales) × 100 |

**Important:** Unit Cost values in the mock file are **estimated prototype figures only** — they are **not** real Salpha Energy cost data. Do not use them for actual financial or procurement decisions.

To rebuild the Excel file from the cleaned CSV:

```bash
python scripts/build_mock_excel.py
```

Mock cost definitions live in `logic/mock_costs.py`. During upload, if **Profit** or **Profit Margin** are missing, the system calculates them from sales and cost data. If **Unit Cost** is also missing, prototype mock costs are used for known products (see disclaimer above).

## Testing upload

1. Start the app.
2. Go to `/upload`.
3. Choose a valid Excel file and submit the form (use `data/mock_data.xlsx` as a sample).
4. Confirm the file appears in `uploads/` and the preview card shows row count and columns.

If you upload an unsupported file type, the app shows an error message instead of crashing.

## Next steps

- Data cleaning and sales analysis
- Dashboard insights and charts
- Forecasting and inventory recommendations
- Report export and SQLite storage
