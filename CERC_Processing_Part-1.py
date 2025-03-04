# Get the name of parties and Judges that will get appended in the data
import os
import io
import requests
from typing import List
import fitz
from tenacity import retry, stop_after_attempt, wait_fixed
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
from pydantic import BaseModel, Field
from litellm import completion
import json
from tqdm import tqdm
import json
import asyncio


# To handle cases of api calls getting failed 
@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def get_completion_with_retry(messages):
    return completion(
        model="openrouter/google/gemini-2.0-flash-001",
        messages=messages,
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY")
    )

async def extract_pdf_text(file_url: str) -> List[str]:
    """ Get the text of the pdf after getting url of the same """
    try:
        response = requests.get(file_url)
        pdf_content = response.content
        mem_stream = io.BytesIO(pdf_content)
            
        text_pages = []
        pdf_document = fitz.open(stream=mem_stream, filetype="pdf")
        
        def process_page(page):
            return page.get_text()
            
        total_pages = len(pdf_document)
        end_page = min(10, total_pages)  
        pages_to_process = [pdf_document[i] for i in range(0, end_page)]
        
        with ThreadPoolExecutor() as executor:
            text_pages = list(executor.map(process_page, pages_to_process))
        
        pdf_document.close()
        return text_pages
    
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return []

def extract_metadata_vertex(text):
    try:
        system_prompt = """
        You are a legal document analyzer. Your task is to accurately extract and format party names from legal case documents, ensuring compliance with standard legal citation formats.
        ### **Rules:**
        1. **Extract ALL primary petitioners and respondents** listed in the document.
        2. **Do NOT limit to the first named petitioner/respondent unless explicitly stated.**  
        3.  If the case mentions **"AND ORS."**, retain it to indicate additional parties.  
        4. Convert all extracted names to **UPPERCASE.**  
        5. Preserve **dots in initials** (e.g., "N.S." should stay as "N.S.").  
        6. Maintain **proper spacing and remove extra commas or redundant spaces.**  
        7. **Validate extracted case titles** against standard legal citation formats:  
        - Ensure **government entities and private parties** are correctly structured.  
        - Keep **acronyms and abbreviations intact.**  
        8. **Return "party_name": null** if no valid party names can be determined.  

        ### **Example Outputs:**
        ```json
        {"party_name": "NTPC LIMITED VS MADHYA PRADESH POWER MANAGEMENT COMPANY LIMITED"}
        {"party_name": "TATA POWER DELHI DISTRIBUTION LIMITED VS DELHI ELECTRICITY REGULATORY COMMISSION"}
        {"party_name": "M/S GREEN ENERGY ASSOCIATION VS JHARKHAND STATE ELECTRICITY REGULATORY COMMISSION & ORS."}
        {"party_name": null}
        
        Note: 
        - Keep all initials with their dots: N.S., B.J., M.R., etc.
        - Maintain proper spacing between initials and names
        - Remove any extra spaces
        - If input has commas between letters, remove them and format properly
        """

        user_prompt = f"""
        Extract **all primary petitioners and respondents** from the following legal text.  
        Follow the rules to ensure proper legal formatting:

        1. **Return all names in uppercase** and format as `"PETITIONER VS RESPONDENT"`.  
        2. If multiple petitioners or respondents exist, **list them all** unless "AND ORS." is explicitly stated.  
        3. **Do NOT modify acronyms or abbreviations** (e.g., "NTPC" must remain "NTPC").  
        4. Ensure **correct representation of government entities** (e.g., "STATE OF KARNATAKA" vs. "XYZ PRIVATE LTD").  
        5. **If no valid party names are found, return "party_name": null.**  

        **Text to analyze:**  
        {text}
        """
        
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = get_completion_with_retry(messages)
        
        if not response or not response.choices or not response.choices[0].message.content:
            raise ValueError("Invalid response received from API")

        
        content = response.choices[0].message.content
        
        
    
        cleaned_content = content.replace("json", "").replace("", "").replace("```" , "").strip()
        # print(cleaned_content)
        
        parsed_json = json.loads(cleaned_content)
        return parsed_json
    
        
    except Exception as e:
        print(f"Error in extract_metadata_vertex: {str(e)}")
        return (f"Error in extract_metadata_vertex")
    

def extract_judges_vertex(text):
    try:
        system_prompt = """
        You are a legal document analyzer. Your task is to **identify and extract judges' names** from legal case documents while preserving their **correct legal designations**.
        
        ### **Rules:**
        1. Extract **all judges' names** from the document.
        2. **Retain their official designations**, including:
        - "Justice" for Judicial Members  
        - "Technical Member" for Technical Experts  
        - "Chairperson" if explicitly mentioned  
        3. **Do not remove "Chief Justice"**, but extract and label their name separately.
        4. If multiple judges exist, **return them comma-separated** in the same order they appear in the document.
        5. Preserve **dots in initials** (e.g., "N.S." should remain "N.S.").
        6. Maintain **proper spacing** between names and avoid duplicate formatting.
        7. If judges’ names **cannot be determined**, return `"judges": null`.

        ### **Example Outputs:**
        ```json
        {"judges": "Justice Ramesh Ranganathan, Technical Member Seema Gupta"}
        {"judges": "Justice Sandesh Kumar Sharma, Justice Virender Bhat"}
        {"judges": "Chief Justice A. P. Shah, Justice P. S. Narasimha"}
        {"judges": null}
        """

        user_prompt = f"""
        Extract **all judges' names** from the following legal text, ensuring correct formatting:  

        1. **Include their correct legal designations**:  
        - "Justice" for Judicial Members  
        - "Chairperson" if explicitly mentioned  
        - "Technical Member" for Technical Experts  
        2. **DO NOT REMOVE "Chief Justice"**, but extract and label their name separately.  
        3. **Preserve initials and proper spacing** (e.g., "Justice N. S. Suhas").  
        4. **If multiple judges exist, return a comma-separated list** in the order they appear.  
        5. **Return only a clean JSON object** with the `"judges"` key.  
        6. **If judges' names cannot be determined, return `"judges": null"`.**  

        **Text to analyze:**  
        {text}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = get_completion_with_retry(messages)
        
        if not response or not response.choices or not response.choices[0].message.content:
            raise ValueError("Invalid response received from API")

        content = response.choices[0].message.content

        cleaned_content = content.replace("json", "").replace("```", "").strip()
        
        parsed_json = json.loads(cleaned_content)
        return parsed_json

    except Exception as e:
        print(f"Error in extract_judges_vertex: {str(e)}")
        return {"error": "Error in extract_judges_vertex"}

# This is the filter out dupicates data on the basis of party name
def remove_duplicate_party_names(cases):
    """Removes duplicate party names from a JSON file, keeping the first occurrence.

    Args:
        filepath: The JSON file of cases .
    """

    try:
        seen_party_names = set()  # Use a set to efficiently track seen names
        unique_cases = []

        for case in cases:
            party_name = case.get("party_name")  # Use .get() to handle missing keys

            if party_name is not None and party_name not in seen_party_names:
                unique_cases.append(case)
                seen_party_names.add(party_name)

        print(f"{((len(cases) - len(unique_cases)) /len(cases) )* 100} % duplicate party names removed sucessfully.....")
        return unique_cases

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format the input...")
    except Exception as e:  # Catch other potential errors
        print(f"An error occurred: {e}")

async def get_judge_party_name(records):
    for c in tqdm(records, desc="Processing cases"):
        url = c["pdf_link"]
        text = await extract_pdf_text(url)
        pdf_texts = "".join(text)
        judges_ext = extract_judges_vertex(pdf_texts)
        party_ext = extract_metadata_vertex(pdf_texts)

        if "judges" in judges_ext:
            judges_name = judges_ext["judges"]
            if judges_name:
                judges_name = judges_name.title()
            c["judges"] = judges_name

        if "party_name" in party_ext:
            party_name = party_ext["party_name"]
            c["party_name"] = party_name

        print(f"Party name: {c.get('party_name', -1)} , Judges name: {c.get('judges', -1)}")
     
    # returning the data after filtering for duplicates   
    try:
        return remove_duplicate_party_names(records)
    except:
        return records

# Main script execution
if __name__ == "__main__":
    input_file = r"C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\CERC and APTEL\central_regulatory_commission_orders - Copy.json"
    output_file = r"C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\CERC and APTEL\CERC_ROP_processed_cases.json"

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        # Run the async function properly in a script
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        processed_records = loop.run_until_complete(get_judge_party_name(records))

        # Save the processed data
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_records, f, indent=4, ensure_ascii=False)

        print(f"\n✅ Processed data saved to: {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")
