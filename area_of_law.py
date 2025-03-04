import os
from typing import List, Literal
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm  # For progress tracking
import logging
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

class Reason(BaseModel):
    score: Literal["Very High", "High", "Moderate", "Low", "Very Low"]
    reasons: List[str] 
    area_of_law: str = Literal["Administrative Law", "Arbitration Law", "Business Law", "Civil Law", "Constitutional Law", "Contract Law", "Criminal Law", "Environmental Law", "Education Law", "Employment Law", "Family and Health Law", "Industrial Law", "Intellectual Property Law", "Marriage and Divorce Law", "Property Law", "Taxation Law"]

def process_single_case(case):
    if "summary" not in case:
        return case, False
        
    try:
        case_name = case['party_name']
        summary = case['summary']
        contents = case_name + "\n\n" + "\n\n" + summary
        
        client = instructor.from_openai(OpenAI(api_key= os.getenv("OPENAI_API_KEY")))
        user_prompt = """
    Given the legal judgment text below, analyze it using the following scoring framework:

    SCORING CRITERIA:
    1. Novel Legal Concepts (Weight: High)
    - Is the court exploring new interpretations of law?
    - Is it developing or modifying existing legal principles?

    2. Settlement Status (Weight: High)
    - Are these unsettled principles of law?
    - Is this a new variation or interpretation of existing law?

    3. Public Importance (Weight: Medium)
    - Does the decision have significant public law implications?
    - Will it affect a large section of society?

    4. Precedential Value (Weight: High)
    - Is this the first time these legal issues are being decided?
    - Does it establish new precedent?

    5. Bench Composition (Weight: Medium)
    - Number of judges on the bench
    - Give additional weight to benches with 3 or more judges

    SCORING LEVELS:
    - Very High: Groundbreaking decision with multiple novel interpretations, unsettled principles, high public importance
    - High: Significant new interpretation or unsettled principle with public importance
    - Moderate: Some novel elements or public importance, but partially based on settled principles
    - Low: Mostly applies settled principles with minor variations
    - Very Low: Entirely based on settled principles with no new interpretations

    REQUIRED OUTPUT FORMAT:
    {
        "score": [Very High/High/Moderate/Low/Very Low],
        "reasons": [
            "List specific reasons for the score",
            "Include key factors that influenced the rating",
            "Mention any novel interpretations or principles",
            "Note bench composition if relevant"
        ]
        "area_of_law": [Administrative Law/Arbitration Law/Business Law/Civil Law/Constitutional Law/Criminal Law/Environmental Law/Education Law/Employment Law/Family and Health Law/Industrial Law/Marriage and Divorce Law/Property Law/Taxation Law"]
    }

    Please analyze the judgment text and provide a score with detailed reasoning following the above format. Be specific about which aspects of the judgment influenced the score.
    """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=Reason, 
            messages=[
                {"role": "user", "content": user_prompt},
                {"role": "user", "content": contents}
            ],
            temperature=0.0,
        )
        
        try:
            case["score"] = str(response.score)
        except:
            case["score"] = ""
            
        case["reasons"] = "".join(response.reasons)
        
        try:
            case["area_of_law"] = str(response.area_of_law)
        except:
            case["area_of_law"] = ""
            
        # Check if the string contains "typing.Literal"
        if "typing.Literal" in case["area_of_law"]:
            case["area_of_law"] = ""
        if "typing.Literal" in case["score"]:
            case["score"] = ""
            
        return case, True
        
    except Exception as e:
        print(f"Error processing case: {str(e)}")
        return case, False

def process_imp_judgment_parallel(cases, max_workers=5, max_attempts=3):
    """
    Process cases in parallel using ThreadPoolExecutor
    
    Args:
        cases: List of case dictionaries
        max_workers: Maximum number of parallel workers
    """
    attempt = 1
    
    while attempt <= max_attempts:
        problematic_entries = []
        processed_cases = []
        error_count = 0
        
        # Determine which cases to process in this attempt
        cases_to_process = cases if attempt == 1 else problematic_entries
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_case = {executor.submit(process_single_case, case): i 
                            for i, case in enumerate(cases_to_process)}
            
            with tqdm(total=len(cases_to_process), 
                     desc=f"Processing cases (Attempt {attempt}/{max_attempts})") as pbar:
                for future in as_completed(future_to_case):
                    case_idx = future_to_case[future]
                    try:
                        processed_case, success = future.result()
                        
                        # Check for problematic area_of_law
                        if "area_of_law" in processed_case:
                            area_of_law = str(processed_case["area_of_law"])
                            if "typing.Literal" in area_of_law:
                                problematic_entries.append(processed_case)
                            else:
                                processed_cases.append(processed_case)
                        else:
                            processed_cases.append(processed_case)
                            
                        if not success:
                            error_count += 1
                            
                    except Exception as e:
                        logger.info(f"Case {case_idx} generated an exception: {str(e)}")
                        error_count += 1
                        problematic_entries.append(cases_to_process[case_idx])
                    
                    pbar.update(1)
        
        logger.info(f"Attempt {attempt}: Found {len(problematic_entries)} problematic entries")
        
        # If no problematic entries or reached max attempts, break
        if not problematic_entries or attempt == max_attempts:
            if problematic_entries:
                logger.info(f"Warning: Still found {len(problematic_entries)} problematic entries after {max_attempts} attempts")
                # Add remaining problematic entries to processed cases
                processed_cases.extend(problematic_entries)
            break
            
        attempt += 1
        logger.info(f"Retrying... Attempt {attempt} of {max_attempts}")
    
    # Sort processed cases back to original order
    processed_cases.sort(key=lambda x: cases.index(x))
    
    return cases, processed_cases, error_count

if __name__ == "__main__":
    
    with open(r"C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\finance-projects\financebench\Summarised_Madras.json" , "r" , encoding= "utf-8") as f:
        records = json.load(f)
        
    cases, processed_cases, error_count = process_imp_judgment_parallel(records)
    with open(r"C:\Users\ANT pc\Downloads\Internship at Ask Junior.ai\Projects\finance-projects\financebench\Final_Summarised_Madras.json", "w", encoding="utf-8") as f_out:
        json.dump(processed_cases, f_out, ensure_ascii=False, indent=4)