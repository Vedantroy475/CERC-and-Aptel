import os
from typing import List, Literal
from pydantic import BaseModel, Field
import instructor
from openai import AsyncOpenAI
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import warnings
import fitz
from PIL import Image
import base64
import io
import requests
from fastapi import FastAPI, HTTPException
import logging
import json

warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=DeprecationWarning)

def fetch_pdf_content(url: str, timeout: int = 30) -> bytes:
    """Fetch PDF content synchronously"""
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content

def convert_pdf_to_base64(pdf_content: bytes) -> str:
    """Convert PDF content to base64 string"""
    try:
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        base64_images = []
        
        def process_page(page):
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()
            
        with ThreadPoolExecutor() as executor:
            end_page = min(13, len(pdf_document))
            pages = [pdf_document[i] for i in range(end_page)]
            base64_images = list(executor.map(process_page, pages))
            
        pdf_document.close()
        return "".join(base64_images)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

class CaseClassification(BaseModel):
    type: str = Literal["Order", "Judgment", "Oral Judgment", "Null"]

async def process_single_judgment(base64_image: str) -> CaseClassification:
    """Process a single judgment"""
    system_prompt = """
    You are a legal document image classifier. Follow these EXACT rules when analyzing the document image:

    1. Classify as Order if ANY of these are found:
    - "COMMON ORDER" appears as header/title
    - Standalone "ORDER" header
    - "ORDER (ORAL)" header
    - Short document with clear procedural directions (like "Dispense with ordered")
    - Document primarily containing procedural instructions or directions
    - Single-page documents with brief directives from the court

    2. Only if no Order indicators, classify as Oral Judgment if:
    - Judge name has (ORAL) suffix
    - Has "ORAL JUDGMENT" header
    - Has "Judgment (Oral)" header

    3. If no Order or Oral Judgment indicators -> Judgment

    4. Return Null if document/image unclear
    """

    user_prompt = """
    Classify this document image following these strict rules:

    1. Must classify as Order if ANY of these found:
    - "COMMON ORDER" or "ORDER" headers
    - Short document with procedural directions
    - Brief court directives
    - Document containing primarily instructions/directions
    
    2. Only if no Order indicators, classify as Oral Judgment if:
    - Judge name has (ORAL) suffix
    - Has "ORAL JUDGMENT" header
    - Has "Judgment (Oral)" header

    3. If no Order or Oral Judgment indicators Judgment
    
    4. If has Judgment/Order that indicate -> Judgment

    4. Return Null if document/image unclear

    Provide only the classification type without explanation.
    """

    client = AsyncOpenAI(api_key= os.getenv("OPENAI_API_KEY"))
    client_with_instructor = instructor.patch(client)
    response = await client_with_instructor.chat.completions.create(
        model="gpt-4o-mini",
        response_model=CaseClassification,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        temperature=0.0,
        max_tokens=300)
    return response

def process_case_thread(case: dict) -> dict:
    """Process a single case in a thread"""
    try:
        if "pdf_link" not in case:
            return None
            
        # Fetch and convert PDF
        pdf_content = fetch_pdf_content(case["pdf_link"])
        case_data = convert_pdf_to_base64(pdf_content)
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async judgment processing
            result = loop.run_until_complete(process_single_judgment(case_data))
            
            if result:
                case["type"] = result.type
                print(result.type)
                return case
            return None
            
        finally:
            loop.close()
            
    except Exception as e:
        logging.error(f"Error processing case: {str(e)}")
        return None

def process_cases(data: List[dict], max_workers: int = 2) -> tuple:
    """Process all cases using ThreadPoolExecutor"""
    processed_cases = []
    error_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all cases to the thread pool
        future_to_case = {
            executor.submit(process_case_thread, case): i 
            for i, case in enumerate(data)
        }
        
        # Process results as they complete
        with tqdm(total=len(data), desc="Processing cases") as pbar:
            for future in as_completed(future_to_case):
                case_idx = future_to_case[future]
                try:
                    result = future.result()
                    if result:
                        processed_cases.append(result)
                    else:
                        error_count += 1
                except Exception as e:
                    logging.error(f"Case {case_idx} generated an exception: {str(e)}")
                    error_count += 1
                pbar.update(1)
    
    print(f"\nSuccessfully processed: {len(processed_cases)} cases")
    print(f"Errors: {error_count}")
    
    return data, processed_cases, error_count

# Removal all cases that is not judgment
def filter_judgments(cases):
    filtered_data = [item for item in cases if item.get("type").lower() == "judgment"]
    print(f"Out of {len(cases)} total, {len(filtered_data)} are judgments")
    
    return filtered_data

if __name__ == "__main__":
    with open("C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\finance-projects\financebench/processed_cases.json" , "r" , encoding= "utf-8") as file:
        cases = json.load(file)
    
    cases = cases[:40] 
    data, processed_cases, error_count = process_cases(cases)
    records = filter_judgments(data)
    
    with open("Classified_cases.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)