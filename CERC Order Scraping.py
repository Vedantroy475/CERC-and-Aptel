import json
import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# URL of the website to scrape
URL = "https://www.cercind.gov.in/recent_orders.html"

# Initialize WebDriver options
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")

# Create a Service object using webdriver_manager
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def scrape_cerc_orders():
    try:
        print("[INFO] Opening website...")
        driver.get(URL)
        
        # Wait for table to be visible
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tbsa tbody")))
        print("[INFO] Table loaded successfully.")
        
        # Locate all rows in the table
        rows = driver.find_elements(By.CSS_SELECTOR, "table.tbsa tbody tr")
        print(f"[INFO] Found {len(rows)} rows in the table.")
        
        results = []
        
        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 6:
                    continue  # Skip incomplete rows
                
                sno = cells[0].text.strip()
                petition_no = cells[1].text.strip()
                
                try:
                    link_element = cells[2].find_element(By.TAG_NAME, "a")
                    pdf_link = link_element.get_attribute("href")
                    subject = link_element.text.strip()
                except NoSuchElementException:
                    pdf_link = ""
                    subject = cells[2].text.strip()
                
                date_of_order = cells[3].text.strip()
                date_of_posting = cells[4].text.strip()
                category = cells[5].text.strip()
                
                results.append({
                    "serial_number": sno,
                    "petition_number": petition_no,
                    "subject": subject,
                    "pdf_link": pdf_link,
                    "date_of_order": date_of_order,
                    "date_of_posting": date_of_posting,
                    "category": category
                })
            except Exception as e:
                print(f"[ERROR] Skipping a row due to an error: {e}")
                continue
        
        # Write data to JSON file
        with open("central_regulatory_commission_orders.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] Stored {len(results)} orders in central_regulatory_commission_orders.json.")
    
    except TimeoutException:
        print("[ERROR] Timeout while loading the page or elements.")
    except WebDriverException as wde:
        print(f"[ERROR] WebDriver Exception: {wde}")
    finally:
        driver.quit()
        print("[INFO] WebDriver closed.")

# Run the scraper
scrape_cerc_orders()
