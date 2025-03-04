import json
import time
import sys
import calendar
from collections import defaultdict
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Base URL for prepending relative links
BASE_URL = "https://www.aptel.gov.in"

# Prompt for the year if not provided as a command-line argument
if len(sys.argv) > 1:
    YEAR_TO_SELECT = sys.argv[1]
else:
    YEAR_TO_SELECT = input("Enter the year to scrape (e.g., 2025): ").strip()

print(f"Scraping PDF links for year: {YEAR_TO_SELECT}")

# Target URL
URL = "https://www.aptel.gov.in/en/old-judgement-data"

# Initialize WebDriver options
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")

# Create a Service object using webdriver_manager
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

try:
    # Open the target URL
    driver.get(URL)

    # Wait for the page to load and locate the year dropdown
    wait = WebDriverWait(driver, 15)
    year_select_element = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#edit-field-judge-year-value"))
    )

    # Create a Select object for the year dropdown
    select = Select(year_select_element)
    try:
        select.select_by_visible_text(YEAR_TO_SELECT)
    except Exception as e:
        print(f"select_by_visible_text failed with error: {e}. Trying select_by_value...")
        try:
            select.select_by_value(YEAR_TO_SELECT)
        except Exception as inner_e:
            print(f"select_by_value also failed: {inner_e}")
            driver.quit()
            raise

    # Click the Apply button to trigger the search/filter
    apply_button = driver.find_element(By.CSS_SELECTOR, "#edit-submit-judgements-orders")
    apply_button.click()

    # Wait until the table rows are loaded
    table_selector = "div.table-responsive table tbody tr"
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, table_selector)))
    time.sleep(3)  # Extra wait if necessary

    # Locate all table rows
    rows = driver.find_elements(By.CSS_SELECTOR, table_selector)

    # Dictionary to hold data grouped by month
    results_by_month = defaultdict(list)
    skipped_rows = []  # Track skipped rows

    for index, row in enumerate(rows[1:], start=2):
        try:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 5:
                continue  # Not a valid data row

            sno = cells[0].text.strip()
            case_name = cells[1].text.strip()

            try:
                link_element = cells[1].find_element(By.TAG_NAME, "a")
                pdf_link = link_element.get_attribute("href")
                if not pdf_link:
                    raise ValueError("Empty href")
                if pdf_link.startswith("/"):
                    pdf_link = BASE_URL + pdf_link
            except Exception:
                skipped_rows.append(sno)
                continue

            # Extract cause title (party names) from the third column
            try:
                party_name = cells[2].text.strip()
            except Exception:
                party_name = "N/A"

            # Extract judges from the fourth column
            try:
                judges = cells[3].text.strip()
            except Exception:
                judges = "N/A"

            # Extract and format date
            try:
                date_of_decision = cells[4].find_element(By.XPATH, ".//h6/strong").text.strip()
                parsed_date = datetime.strptime(date_of_decision, "%d.%m.%Y")
                month_number = parsed_date.month
                month_name = calendar.month_name[month_number]
                month_key = f"{month_name} {parsed_date.year}"
            except Exception:
                skipped_rows.append(sno)
                continue

            # Store the extracted information under the correct month
            results_by_month[month_key].append({
                "date": date_of_decision,
                "case_name": case_name,
                "pdf_link": pdf_link,
                "party_name": party_name,
                "judges": judges
            })
        
        except Exception:
            skipped_rows.append(sno)
            continue

    # Sort months in ascending order (earliest first)
    sorted_results_by_month = dict(sorted(results_by_month.items(), key=lambda x: datetime.strptime(x[0], "%B %Y")))

    # Write the output to a JSON file
    output_file = "output_by_month.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sorted_results_by_month, f, ensure_ascii=False, indent=2)

    # Summary output
    print(f"Total months processed: {len(sorted_results_by_month)}")
    for month, records in sorted_results_by_month.items():
        print(f"{month}: {len(records)} entries")
    print(f"Number of incomplete or skipped entries: {len(skipped_rows)}")
    if skipped_rows:
        print(f"S. NO. of skipped entries: {skipped_rows}")

except TimeoutException as te:
    print("Timeout while waiting for page elements:", te)
except WebDriverException as wde:
    print("WebDriver exception occurred:", wde)
finally:
    driver.quit()
