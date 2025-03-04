import os 
from openai import OpenAI
import json
import concurrent.futures
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
load_dotenv()
# Define max_retries at the module level
MAX_RETRIES = 3
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    raise ValueError("OPENAI_API_KEY is not set. Check your environment variables or .env file.")
def rephrase_summary(summary):
    client = OpenAI(api_key= openai_api_key)
    
    SYSTEM_PROMPT = """
    Provide legal judgment summaries that are strictly fact-based and concise. 
    Strip out all phrases like 'ruled', 'determined', 'held', 'found', or references to courts/benches. 
    Avoid procedural details unless crucial to the decision."""

    USER_PROMPT = f"""
    Summary: {summary}

    Convert this into a concise summary that:
    1. Uses direct statements without court references
    2. The summary should be concise and to the point.
    3. Do not provide any summary as a list.
    """

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=6),
        retry_error_callback=lambda retry_state: summary  # Return original summary if all retries fail
    )
    def make_openai_request():
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ],
        )
        return response.choices[0].message.content

    try:
        return make_openai_request()
    except Exception as e:
        print(f"Error in rephrasing after {MAX_RETRIES} retries: {e}")
        return summary

def get_summary(pdf_url):
    headers = {'Content-Type': 'application/json'}
    api_url = "https://askjunior23--judgement-summary-list.modal.run"

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda retry_state: {
            "summary": f"Error after {MAX_RETRIES} retries: {retry_state.outcome.exception()}",
            "new_summary": "",
            "id": "",
            "new_url": pdf_url
        }
    )
    def make_request():
        try:
            response = requests.post(
                api_url, 
                headers=headers, 
                json={"pdf_url": pdf_url},
                timeout=50
            )
            print(f"Status Code: {response.status_code}, Response: {response.text}")
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            raise

    try:
        summary_data = make_request()
        initial_summary = summary_data.get("summary", "No summary found")
        rephrased_summary = rephrase_summary(initial_summary) if initial_summary != "No summary found" else initial_summary
        
        return {
            "summary": initial_summary,
            "new_summary": rephrased_summary,
            "id": summary_data.get("id", "No ID found"),
            "new_url": summary_data.get("new_url", pdf_url) 
        }
        
    except Exception as e:
        print(f"Final error for {pdf_url}: {e}")
        return {
            "summary": f"Error: {str(e)}",
            "new_summary": "",
            "id": "",
            "new_url": pdf_url
        }
        
def update_json(data, pdf_url, result):
    for judgement in data:
        if judgement["pdf_link"] == pdf_url:
            judgement["summary"] = result["summary"]
            judgement["new_summary"] = result["new_summary"]
            if "new_url" in result:
                judgement["pdf_link"] = result["new_url"]
            if "id" in result:
                judgement["id"] = result["id"]

def process_summary(pdf_urls, cases):
    print(len(cases))
    print("Starting...")
    start_time = time.time()

    batch_size = 10
    max_calls = 2 

    total_batches = len(pdf_urls) // batch_size + (1 if len(pdf_urls) % batch_size > 0 else 0)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_calls) as executor:
        futures = {executor.submit(get_summary, pdf_url): pdf_url for pdf_url in pdf_urls}

        for future in concurrent.futures.as_completed(futures):
            pdf_url = futures[future]
            try:
                result = future.result()
                update_json(cases, pdf_url, result)
            except Exception as e:
                print(f"Error processing {pdf_url}: {e}")

            current_batch = (pdf_urls.index(pdf_url) // batch_size) + 1
            progress_percent = (current_batch / total_batches) * 100
            print(f"Progress: {progress_percent:.2f}%")

    end_time = time.time()
    total_time = end_time - start_time
    print(total_time)
    return cases

def get_url_and_data(cases):
    pdf_urls = []
    filtered_data = []

    for d in cases:
        if not isinstance(d, dict):
            print(f"Skipping invalid entry: {d}")
            continue
            
        pdf_url = d.get("pdf_link")
        if pdf_url and "N/A" not in pdf_url:
            pdf_urls.append(pdf_url)
            filtered_data.append(d)
    return pdf_urls , filtered_data

if __name__ == "__main__":
    with open(r"C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\finance-projects\financebench\final_madras.json", "r", encoding="utf-8") as file:
        records = json.load(file)

        
    pdf_urls , filtered_data = get_url_and_data(records)
    records = process_summary(pdf_urls , filtered_data)
    # Define output file path
    output_file = r"C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\finance-projects\financebench\Summarised_Madras.json"

    # Save the updated JSON data
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=4, ensure_ascii=False)

    print(f"Updated JSON file saved to: {output_file}")
