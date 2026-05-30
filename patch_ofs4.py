import re

with open('ofs.py', 'r') as f:
    content = f.read()

# Replace all occurrences of pd.read_excel to just return an empty DataFrame 
# with the necessary columns so the legacy auto-bidding code doesn't crash when calculating length or checking columns.
content = re.sub(
    r"pd\.read_excel\([^)]*\)", 
    "pd.DataFrame(columns=['BID ID', 'TradingCode', 'Quantity'])", 
    content
)

# Replace dataframe saving to avoid FileNotFoundError if the directory doesn't exist
content = re.sub(r"Csv_dataDf\.to_csv\([^)]*\)", "pass", content)
content = re.sub(r"file\.save\(excel_filepath\)", "pass", content)

with open('ofs.py', 'w') as f:
    f.write(content)

print("Removed Auto Bidding Excel file dependencies.")
