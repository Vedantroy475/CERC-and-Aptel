import json
import time
from datetime import datetime
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

# Constants
URL = "https://www.cercind.gov.in/recent_rops.html"
OUTPUT_FILE = "cerc_scraped_data.json"

# Setup Selenium WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run browser in headless mode (optional)
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920x1080")

# Initialize WebDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

try:
    # Open the target URL
    driver.get(URL)
    print("[INFO] Opened URL:", URL)

    # Wait for the table to load
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    
    # Extract page source and parse with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Find the main table
    table = soup.find("table", {"class": "table-bordered"})
    if not table:
        print("[ERROR] Table not found on the page.")
        driver.quit()
        exit()

    # Extract table rows (excluding the header)
    rows = table.find_all("tr")[1:]

    extracted_data = []
    
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:  # Ensure the row has enough columns
            continue

        s_no = cells[0].text.strip()
        petition_no = cells[1].text.strip()
        subject_link = cells[2].find("a")
        subject_text = subject_link.text.strip() if subject_link else cells[2].text.strip()
        subject_url = subject_link["href"] if subject_link else ""
        hearing_date = cells[3].text.strip()
        category = cells[5].text.strip()  # Skipping "Date of posting ROP on website"

        # Extract petitioner name from the subject field (inside <strong> tag)
        petitioner = ""
        strong_tag = cells[2].find("strong")
        if strong_tag:
            petitioner = strong_tag.text.strip()

        # Format the data
        case_data = {
            "s_no": s_no,
            "petition_no": petition_no,
            "subject": subject_text,
            "pdf_link": "https://www.cercind.gov.in" + subject_url if subject_url else "",
            "hearing_date": hearing_date,
            "category": category,
            "petitioner": petitioner
        }

        extracted_data.append(case_data)

    # Store data in JSON file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] Data successfully saved to {OUTPUT_FILE}")

except Exception as e:
    print("[ERROR] An error occurred:", e)

finally:
    driver.quit()
    print("[INFO] WebDriver closed.")
