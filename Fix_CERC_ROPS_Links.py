import json

# Load the JSON data
with open("cerc_scraped_data.json", "r", encoding="utf-8") as file:
    data = json.load(file)

# Fix the PDF links
for entry in data:
    if "pdf_link" in entry and entry["pdf_link"].startswith("https://www.cercind.gov.in"):
        entry["pdf_link"] = entry["pdf_link"].replace("www.cercind.gov.in", "www.cercind.gov.in/")

# Save the corrected JSON
with open("cerc_scraped_data_fixed.json", "w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, ensure_ascii=False)

print("Fixed JSON file has been saved as cerc_scraped_data_fixed.json")
