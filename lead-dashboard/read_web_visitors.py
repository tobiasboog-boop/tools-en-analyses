"""Extract Pipedrive Web Visitors data from Excel export."""
import pandas as pd
import json

# Read the Excel file
excel_path = r"C:\Users\tobia\Downloads\lijst.xlsx"

print("Reading Web Visitors Excel file...")
df = pd.read_excel(excel_path)

print(f"\nFound {len(df)} rows\n")
print("=" * 80)
print("COLUMN NAMES:")
print("=" * 80)
for i, col in enumerate(df.columns, 1):
    print(f"{i:2}. {col}")

print("\n" + "=" * 80)
print("FIRST 5 ROWS:")
print("=" * 80)
print(df.head(5).to_string())

print("\n" + "=" * 80)
print("DATA TYPES:")
print("=" * 80)
print(df.dtypes)

print("\n" + "=" * 80)
print("SAMPLE ROW (detailed):")
print("=" * 80)
if len(df) > 0:
    sample = df.iloc[0]
    for col in df.columns:
        value = sample[col]
        print(f"  {col:30} = {value} (type: {type(value).__name__})")

# Save as CSV for inspection
csv_path = r"C:\projects\tools_en_analyses\lead-dashboard\web_visitors_export.csv"
df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"\nExported to CSV: {csv_path}")

# Save column info as JSON
output = {
    'total_rows': len(df),
    'columns': list(df.columns),
    'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
    'sample_row': {col: str(val) for col, val in df.iloc[0].items()} if len(df) > 0 else {}
}

json_path = r"C:\projects\tools_en_analyses\lead-dashboard\web_visitors_info.json"
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"Column info saved: {json_path}")
