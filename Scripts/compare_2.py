import json
import re
from rapidfuzz import fuzz
import usaddress
import openai
import base64
from typing import List
import os
from datetime import date, datetime


def normalize_string(value):
    if not value:  
        return ""  
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r'[^a-zA-Z0-9]', '', value)  
    return value.lower().strip()


def search_key(data, target_key, default_value=''):
    target_key = normalize_string(target_key)
    stack = [data]

    while stack:
        current = stack.pop(0)

        if isinstance(current, dict):
            for key, value in current.items():
                if normalize_string(key) == target_key:
                    return value 
                stack.append(value)

        elif isinstance(current, list):
            stack.extend(current)

    return default_value  

def search_second_key(data, target_key, default_value=''):
    target_key = normalize_string(target_key)
    stack = [data]
    matches = []

    while stack:
        current = stack.pop(0)

        if isinstance(current, dict):
            for key, value in current.items():
                if normalize_string(key) == target_key:
                    matches.append(value)
                stack.append(value)

        elif isinstance(current, list):
            stack.extend(current)

    if len(matches) >= 2:
        return matches[1]
    elif len(matches) == 1:
        return matches[0]
    else:
        return default_value


priority_list = [
    "V",
    "VE", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20", "V21", "V22", "V23", "V24", "V25", "V26", "V27", "V28", "V29", "V30",
    "A",
    "AO",
    "AH",
    "AR",
    "AE", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18", "A19", "A20", "A21", "A22", "A23", "A24", "A25", "A26", "A27", "A28", "A29", "A30",
    "A99",
    "D",
    "B", "C", "X"
]

def get_priority(value):
    value = value.strip().upper()
    if not priority_list:
        print("Priority list not provided.\n")

    if value in priority_list:
        return priority_list.index(value)
    return float('inf')  



from dateutil import parser


def normalize_date_str(date_str):
    if not isinstance(date_str, str):
        raise TypeError("Expected a string as input")

    digits_only = re.sub(r'\D', '', date_str)

    if len(digits_only) != 8:
        raise ValueError("Invalid date format. Expected MMDDYYYY after cleanup.")

    dt = datetime.strptime(digits_only, "%m%d%Y")

    return dt.strftime("%m-%d-%Y")


def get_latest_date(date1, date2):
    d1 = parser.parse(normalize_date_str(date1), dayfirst=True)
    d2 = parser.parse(normalize_date_str(date2), dayfirst=True)
    return date1 if d1 > d2 else date2

def is_date_between(date_str, start_str, end_str):
    try:
        date_obj = parser.parse(date_str, dayfirst=True)
        start_obj = parser.parse(start_str, dayfirst=True)
        end_obj = parser.parse(end_str, dayfirst=True)
        return start_obj <= date_obj <= end_obj
    except Exception as e:
        print(f"⚠️ Date parsing error: {e}")
        return False


def find_date_after_certifier(data, unique_key="Certifier's Name", target_key="Date", max_depth=8):
    def search(obj, depth):
        if depth > max_depth:
            return None
        if isinstance(obj, dict):
            # Check if this dict contains the unique_key
            if any(normalize_string(unique_key) in normalize_string(k) for k in obj):
                # If found, look for the target_key in the same dict
                for k, v in obj.items():
                    if normalize_string(target_key) in normalize_string(k):
                        return v
            # Recursively search deeper
            for v in obj.values():
                result = search(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = search(item, depth + 1)
                if result:
                    return result
        return None

    return search(data, depth=1)


def normalize_diagram_number(s):
    return re.sub(r'\s+', ' ', s.strip()).lower()

def clean_value(value):
    keywords_to_remove = ["number", "no.", "num", "#"]
    pattern = r'\b(' + '|'.join(re.escape(kw) for kw in keywords_to_remove) + r')\b[\s:.#]*'
    return re.sub(pattern, '', value, flags=re.IGNORECASE).strip()

def diagram_number_pdf(data, key_variants):
    if isinstance(data, dict):
        for key, value in data.items():
            if normalize_diagram_number(key) in [normalize_diagram_number(k) for k in key_variants]:
                return clean_value(value) if isinstance(value, str) else value

            deeper_result = diagram_number_pdf(value, key_variants)
            if deeper_result is not None:
                return deeper_result

    elif isinstance(data, list):
        for item in data:
            deeper_result = diagram_number_pdf(item, key_variants)
            if deeper_result is not None:
                return deeper_result
    
    return None

def extract_float_value(value):
    if value is None or value == "":
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"-?\d+(\.\d+)?", str(value))
    return float(match.group()) if match else 0.0



def normalize_street_name(street_name, STREET_ABBREVIATIONS):
    words = street_name.split()
    return " ".join(STREET_ABBREVIATIONS.get(word, word) for word in words)

def normalize_state(state, STATE_ABBREVIATIONS):
    return STATE_ABBREVIATIONS.get(state, state)

def preprocess_address(address):
    address = re.sub(r'(\d+)([A-Za-z])', r'\1 \2', address)  # Space between numbers & letters
    address = re.sub(r'([A-Za-z])(\d+)', r'\1 \2', address)  # Space between letters & numbers
    address = re.sub(r'[-,]', ' ', address)  
    return address.strip()

def clean_address(address):
    return re.sub(r'[\s,-]', '', address).strip().lower()

def parse_address(address):
    address = preprocess_address(address)  
    try:
        parsed = usaddress.tag(address)[0]

        street_number = parsed.get("AddressNumber", "")
        street_name = parsed.get("StreetName", "") + " " + parsed.get("StreetNamePostType", "")
        city = parsed.get("PlaceName", "")
        state = normalize_state(parsed.get("StateName", ""))
        zipcode = parsed.get("ZipCode", "")

        if not city or not state or not zipcode:
            city_match = re.search(r'([A-Za-z]+)\s+([A-Z]{2})\s+(\d{5})$', address)
            if city_match:
                city, state, zipcode = city_match.groups()
                state = normalize_state(state)

        # Normalize street name
        street_name = normalize_street_name(street_name.strip())

        # Combine into final address
        full_address = f"{street_number} {street_name} {city} {state} {zipcode}".strip()
        return clean_address(full_address)
    except:
        return clean_address(address)  

def compare_addresses(address1, address2):
    norm1 = parse_address(address1)
    norm2 = parse_address(address2)

    match_score = fuzz.ratio(norm1, norm2)

    if match_score > 90:
        return "Addresses are Matched on EC and Application. ✅"
    elif match_score > 80:
        return "Addresses have High Similarity. Underwriting review required.❗"
    else:
        return "Property address on EC doesn't match application. Underwriting review required. ❌"


def get_value_by_normalized_key(data, target_keys):
    if not isinstance(data, dict):
        return 0.0
    
    normalized_data_keys = {normalize_string(k): k for k in data.keys()}
    
    for target in target_keys:
        norm_target = normalize_string(target)
        if norm_target in normalized_data_keys:
            return data[normalized_data_keys[norm_target]]
    
    return 0.0


def analyze_image( 
    image_path: List[str], 
    question: List[str], 
    model: str = "gpt-4o"
) -> str: 
    """
    Analyzes multiple images and answers questions about them using OpenAI's vision-capable model.
    
    :param image_paths: List of image file paths.
    :param questions: List of textual questions to ask.
    :param model: The vision-capable model to use.
    :return: String with concise answers.
    """
    encoded_images = []
    for path in image_path:
        with open(path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
            encoded_images.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                    "detail": "high" 
                }
            })

    question_block = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(question))
    openai.api_key = os.getenv("OPENAI_API_KEY") 
    user_message = [{"type": "text", "text": question_block}] + encoded_images
    response = openai.chat.completions.create(
        model=model,
        messages=[ 
            { 
                "role": "system",
                "content": (
                    "You are a smart assistant. Analyze all the provided images carefully, then answer the questions as 'True' or 'False' with highest accuracy possible."
                ) 
            },
            {
                "role": "user",
                "content": user_message 
            }
        ],
        max_tokens=800,
        temperature=0.0
    )

    return response.choices[0].message.content.strip()


def run_all_comparisons(data_pdf=None, data_app=None, image_paths=None):
    """Run all comparison rules and return consolidated results."""
    
    # Load data if not provided
    if data_pdf is None:
        try:
            with open(r"JSONs\EC.json") as f: 
                data_pdf = json.load(f)
        except FileNotFoundError:
            return {"error": "EC.json not found"}
    
    if data_app is None:
        try:
            with open(r"JSONs\application.json") as f: 
                data_app = json.load(f)
        except FileNotFoundError:
            return {"error": "application.json not found"}
    
    if image_paths is None:
        # Check for default image paths
        default_paths = [r"Images\1.png", r"uploads\1.png"]
        existing_paths = [path for path in default_paths if os.path.exists(path)]
        image_paths = existing_paths if existing_paths else []
    
    # Extract essential variables
    try:
        extracted_vars = extract_essential_variables(data_pdf, data_app)
    except Exception as e:
        return {"error": f"Failed to extract variables: {str(e)}"}
    
    # Initialize results dictionary
    results = {}
    
    # Rule 1: Address verification
    try:
        results["rule_1"] = verify_address(
            extracted_vars["address_pdf"],
            extracted_vars["address_app"],
            extracted_vars["street_name_pdf"],
            extracted_vars["street_number_app"]
        )
    except Exception as e:
        results["rule_1"] = {"rule": "Rule 1 - Address Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 2: Diagram number verification
    try:
        results["rule_2"] = verify_diagram_number(
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagram_number_app"],
            extracted_vars["top_of_bottom_floor_app"],
            extracted_vars["top_of_next_higher_floor_app"],
            extracted_vars["Section_C_LAG_app"]
        )
    except Exception as e:
        results["rule_2"] = {"rule": "Rule 2 - Diagram Number Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 3: Crawlspace details
    try:
        results["rule_3"] = verify_crawlSpace_details(
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagrams_for_crawlspace"],
            extracted_vars["total_square_footage"],
            extracted_vars["enclosure_Size"],
            extracted_vars["crawlspace_square_footage"],
            extracted_vars["garage_square_footage"]
        )
    except Exception as e:
        results["rule_3"] = {"rule": "Rule 3 - Crawlspace Details Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 4: CBRS/OPA details
    try:
        results["rule_4"] = verify_CBRS_OPA_details(
            extracted_vars["CBRS_OPA_app"],
            extracted_vars["CBRS"],
            extracted_vars["OPA"]
        )
    except Exception as e:
        results["rule_4"] = {"rule": "Rule 4 - CBRS/OPA Details Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 5: Construction status
    try:
        results["rule_5"] = verify_construction_status(
            extracted_vars["Construction_status_pdf"],
            extracted_vars["Construction_status_app"]
        )
    except Exception as e:
        results["rule_5"] = {"rule": "Rule 5 - Construction Status Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 6: Certifier verification
    try:
        results["rule_6"] = verify_certifier(
            extracted_vars["Elevation_Certificate_Section_Used"],
            extracted_vars["section_c_measurements_used"],
            extracted_vars["certifier_name_pdf"],
            extracted_vars["certifier_license_number"]
        )
    except Exception as e:
        results["rule_6"] = {"rule": "Rule 6 - Certifier Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 7: Section C measurements
    try:
        results["rule_7"] = verify_sectionC_measurements(
            extracted_vars["HAG_pdf"],
            extracted_vars["LAG_pdf"],
            extracted_vars["section_c_measurements_used"],
            extracted_vars["top_of_bottom_floor_pdf"],
            extracted_vars["top_of_bottom_floor_app"],
            extracted_vars["top_of_next_higher_floor_app"],
            extracted_vars["top_of_next_higher_floor_pdf"],
            extracted_vars["LAG_app"],
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagram_choices_1"],
            extracted_vars["diagram_choices_2"],
            extracted_vars["diagram_choices_3"],
            extracted_vars["diagram_choices_4"],
            extracted_vars["diagram_choices_5"]
        )
    except Exception as e:
        results["rule_7"] = {"rule": "Rule 7 - Section C Measurements Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 8: Section E measurements
    try:
        results["rule_8"] = verify_sectionE_measurements(
            extracted_vars["Elevation_Certificate_Section_Used"],
            extracted_vars["section_e_measurements_used"],
            extracted_vars["e1b"],
            extracted_vars["top_of_bottom_floor_app"],
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagram_choices_6"],
            extracted_vars["LAG_pdf"],
            extracted_vars["diagram_choices_7"],
            extracted_vars["diagram_choices_8"],
            extracted_vars["diagram_choices_9"],
            extracted_vars["diagram_choices_10"],
            extracted_vars["e2"],
            extracted_vars["e1a"]
        )
    except Exception as e:
        results["rule_8"] = {"rule": "Rule 8 - Section E Measurements Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 9: Section H measurements
    try:
        results["rule_9"] = verify_sectionH_measurements(
            extracted_vars["Elevation_Certificate_Section_Used"],
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagram_choices_11"],
            extracted_vars["h1a_top_of_bottom_floor"],
            extracted_vars["LAG_pdf"],
            extracted_vars["diagram_choices_12"],
            extracted_vars["diagram_choices_13"],
            extracted_vars["h1b_top_of_next_higher_floor"]
        )
    except Exception as e:
        results["rule_9"] = {"rule": "Rule 9 - Section H Measurements Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 10: Machinery logic 
    try:
        results["rule_10"] = verify_Machinery_logic(
            extracted_vars["machinery"],
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagram_choices_14"],
            extracted_vars["top_of_next_higher_floor_pdf"],
            extracted_vars["c2e_elevation_of_mahinery"],
            extracted_vars["top_of_bottom_floor_pdf"],
            extracted_vars["e4_top_of_platform"],
            extracted_vars["e1b"],
            extracted_vars["h2"],
            extracted_vars["diagram_choices_15"],
            extracted_vars["e2"]
        )
    except Exception as e:
        results["rule_10"] = {"rule": "Rule 10 - Machinery Logic Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rule 11: Vents details
    try:
        results["rule_11"] = verify_vents_details(
            extracted_vars["diagramNumber_pdf"],
            extracted_vars["diagram_choices_10"],
            extracted_vars["total_number_of_openings"],
            extracted_vars["number_of_flood_openings_app"],
            extracted_vars["total_area_of_openings"],
            extracted_vars["area_of_flood_openings_app"]
        )
    except Exception as e:
        results["rule_11"] = {"rule": "Rule 11 - Vents Details Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Rules 12-24: Photograph-based rules (only if images are available)
    if image_paths and all(os.path.exists(path) for path in image_paths):
        # Rule 12: Photograph requirement
        try:
            results["rule_12"] = verify_photograph_requirement(
                extracted_vars["Construction_status_app"]
            )
        except Exception as e:
            results["rule_12"] = {"rule": "Rule 12 - Photograph Requirement", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 13: Building eligibility
        try:
            results["rule_13"] = verify_building_eligibility(image_paths)
        except Exception as e:
            results["rule_13"] = {"rule": "Rule 13 - Building Eligibility", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 14: Occupancy verification
        try:
            results["rule_14"] = verify_occupancy(
                extracted_vars["occupancy_type_app"],
                extracted_vars["occupancy_type_ec"],
                image_paths
            )
        except Exception as e:
            results["rule_14"] = {"rule": "Rule 14 - Occupancy Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 15: Under water verification
        try:
            results["rule_15"] = verify_underWater(image_paths)
        except Exception as e:
            results["rule_15"] = {"rule": "Rule 15 - Under Water Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 16: Foundation eligibility
        try:
            results["rule_16"] = verify_foundation_eligibility(image_paths)
        except Exception as e:
            results["rule_16"] = {"rule": "Rule 16 - Foundation Eligibility", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 17: Foundation type verification
        try:
            results["rule_17"] = verify_foundation_type(
                extracted_vars["diagram_number_app"],
                image_paths
            )
        except Exception as e:
            results["rule_17"] = {"rule": "Rule 17 - Foundation Type Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 18: Number of floors verification
        try:
            results["rule_18"] = verify_number_of_floors(
                image_paths,
                extracted_vars["number_of_floors_app"]
            )
        except Exception as e:
            results["rule_18"] = {"rule": "Rule 18 - Number of Floors Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 19: Dormers verification
        try:
            results["rule_19"] = verify_dormers(image_paths)
        except Exception as e:
            results["rule_19"] = {"rule": "Rule 19 - Dormers Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 20: Construction type verification
        try:
            results["rule_20"] = verify_construction_type(
                extracted_vars["construction_type_app"],
                image_paths
            )
        except Exception as e:
            results["rule_20"] = {"rule": "Rule 20 - Construction Type Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 21: Additions verification
        try:
            results["rule_21"] = verify_additions(image_paths)
        except Exception as e:
            results["rule_21"] = {"rule": "Rule 21 - Additions Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 22: Diagram 5 verification
        try:
            results["rule_22"] = verify_diagram5(image_paths)
        except Exception as e:
            results["rule_22"] = {"rule": "Rule 22 - Diagram 5 Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 23: Diagram 6 verification
        try:
            results["rule_23"] = verify_diagram6(
                extracted_vars["diagram_number_app"],
                image_paths
            )
        except Exception as e:
            results["rule_23"] = {"rule": "Rule 23 - Diagram 6 Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
        
        # Rule 24: Machinery verification
        try:
            results["rule_24"] = verify_machinery(
                extracted_vars["appliances_on_first_floor"],
                extracted_vars["foundation_type_app"],
                image_paths
            )
        except Exception as e:
            results["rule_24"] = {"rule": "Rule 24 - Machinery Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    else:
        # Add placeholders for image-based rules when no images are available
        for rule_num in range(12, 25):
            results[f"rule_{rule_num}"] = {
                "rule": f"Rule {rule_num} - Image Analysis Required",
                "status": "⚠️",
                "details": ["No images provided or images not found. Rule skipped."]
            }
    
    # Additional validations
    try:
        results["additional_checks"] = verify_additional_things(
            extracted_vars["firm_date_app"],
            extracted_vars["firm_date_pdf"],
            extracted_vars["suffix_app"],
            extracted_vars["suffix_pdf"],
            extracted_vars["flood_zone_app"],
            extracted_vars["flood_zone_pdf"]
        )
    except Exception as e:
        results["additional_checks"] = {"rule": "Additional Things Verification", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    try:
        results["form_validation"] = form_validation(
            extracted_vars["EC_expiration"],
            extracted_vars["survey_date"]
        )
    except Exception as e:
        results["form_validation"] = {"rule": "Form Validation", "status": "❌", "details": [f"Error: {str(e)}"]}
    
    # Generate summary statistics
    total_rules = len([k for k in results.keys() if k.startswith('rule_')])
    passed_rules = len([k for k, v in results.items() if k.startswith('rule_') and v["status"] == "✅"])
    failed_rules = len([k for k, v in results.items() if k.startswith('rule_') and v["status"] == "❌"])
    warning_rules = len([k for k, v in results.items() if k.startswith('rule_') and v["status"] == "⚠️"])
    
    results["summary"] = {
        "total_rules": total_rules,
        "passed_rules": passed_rules,
        "failed_rules": failed_rules,
        "warning_rules": warning_rules,
        "images_processed": len(image_paths) if image_paths else 0,
        "overall_status": "✅" if failed_rules == 0 and warning_rules == 0 else ("⚠️" if failed_rules == 0 else "❌")
    }
    
    return results





# File paths
# -----------------------------------------
# with open(r"JSONs\EC.json") as f: 
#     data_pdf = json.load(f) 

# with open(r"JSONs\application.json") as f: 
#     data_app = json.load(f) 

# image_path = [r"Images\1.png"]  

#========================================================================
# All extracted variables
#========================================================================

def extract_essential_variables(data_pdf, data_app): 
    STREET_ABBREVIATIONS = {
            "Street": "St.", "Avenue": "Ave.", "Boulevard": "Blvd.", "Drive": "Dr.",
            "Court": "Ct.", "Road": "Rd.", "Lane": "Ln.", "Terrace": "Ter.",
            "Place": "Pl.", "Circle": "Cir.", "Highway": "Hwy.", "Parkway": "Pkwy."
        }

    STATE_ABBREVIATIONS = {
            "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
            "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
            "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
            "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
            "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
            "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
            "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
            "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
            "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
            "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
            "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"
        }

    street_number_pdf = extract_float_value(search_key(data_pdf, 'Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.'))
    street_name_pdf = normalize_string(search_key(data_pdf, "Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.") or search_key(data_pdf, "A2. Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.") or search_key(data_pdf, "A2")) 
    city_value_pdf = search_key(data_pdf, 'City') 
    state_value_pdf = search_key(data_pdf, 'State')
    zipcode_value_pdf = search_key(data_pdf, 'ZIPCode')
    address_pdf = "".join([
    str(street_number_pdf) if street_number_pdf else "",
    street_name_pdf or "",
    city_value_pdf or "",
    state_value_pdf or "",
    zipcode_value_pdf or ""
    ])
  

    street_number_app = extract_float_value(search_key(data_app, "Property Address"))
    address_app = search_key(data_app, "Property Address") 

    top_of_bottom_floor_app = extract_float_value(search_key(data_app, "Top of Bottom Floor")) 
    top_of_next_higher_floor_app = extract_float_value(search_key(data_app, 'Top of Next Higher Floor')) 

    key_variants = [
        "building_diagram_number",
        "BuildingDiagram",
        "bldg_diag_num",
        "buildingDiagramNo",
        "Diagram Number",
        "Building Diagram Number",
        "A7",
        "A7. Building Diagram Number",
        "A7 Building Diagram Number"
    ]

    try:
        Section_C_LAG_app = float(search_key(data_app, 'Lowest Adjacent Grade (LAG)') or search_key(data_app, "Lowest Adjacent Grade") or search_key(data_app, "LAG")) 
    except (ValueError, TypeError):
        Section_C_LAG_app = 0 

    try:
        diagramNumber_pdf = diagram_number_pdf(data_pdf, key_variants)
    except (ValueError, TypeError):
        diagramNumber_pdf = -1  

    try:
        diagram_number_app = diagram_number_pdf(data_app, key_variants) 
    except (ValueError, TypeError):
        diagram_number_app = -1 

    crawlspace_details = search_key(data_pdf, 'CrawlspaceDetails') or search_key(data_pdf, "Crawlspace") or search_key(data_pdf, "for a building with crawlspace or enclosure(s)")

    lookup_keys = ["SquareFootage", "square footage of crawlspace or enclosure(s)", "a) Square footage of crawlspace or enclosure(s)", "A8. For a building with a crawlspace or enclosure(s): a) Square footage of crawlspace or enclosure(s)"] 


    if isinstance(crawlspace_details, (int, float)):
        crawlspace_square_footage = extract_float_value(crawlspace_details)
    else:
        crawlspace_square_footage = (
            extract_float_value(get_value_by_normalized_key(crawlspace_details, lookup_keys)) or
                0.0
            )

    garage_details = search_key(data_pdf, 'GarageDetails') or search_key(data_pdf, "Garage") or search_key(data_pdf, "for a building with attached garage")
    garage_square_footage = extract_float_value(get_value_by_normalized_key(garage_details, lookup_keys) or 0.0)
    enclosure_Size = extract_float_value(search_key(data_app, "Enclosure/Crawlspace Size"))
    total_square_footage = crawlspace_square_footage + garage_square_footage
    diagrams_for_crawlspace = ['6', '7', '8', '9']  

    CBRS = search_key(data_pdf, 'CBRS') or search_key(data_pdf,"CBRSDesignation")
    OPA = search_key(data_pdf, 'OPA') or search_key(data_pdf, 'OPADesignation')  
    CBRS_OPA_app = search_key(data_app, 'Building Located In CBRS/OPA') 

    Construction_status_pdf = search_key(data_pdf, 'Building elevations are based on') or search_key(data_pdf, "Building Elevations Source") 
    Construction_status_app = search_key(data_app, 'Building in Course of Construction') # no / yes 
    certifier_name_pdf = search_key(data_pdf, "Certifier's Name") or search_key(data_pdf, "Certifier Name") or search_key(data_pdf, "CertificateName")
    certifier_license_number = search_key(data_pdf, "License Number") 
    try:
        Section_C_FirstFloor_Height_app = float(search_key(data_app, 'Elevation Certificate First Floor Height') or search_key(data_app, "First Floor Height"))
    except (ValueError, TypeError):
        Section_C_FirstFloor_Height_app = 0 
    try:
        Section_C_Lowest_Floor_Elevation_app = float(search_key(data_app, 'Lowest Floor Elevation') or search_key(data_app, "Elevation Certificate Lowest Floor Elevation") or search_key(data_app, "Lowest (Rating) Floor Elevation"))
    except (ValueError, TypeError):
        Section_C_Lowest_Floor_Elevation_app = 0
    section_c_measurements_used = False 
    Elevation_Certificate_Section_Used = search_key(data_app, "Elevation Certificate Section Used") 

    top_of_bottom_floor_pdf = extract_float_value(search_key(data_pdf, 'Top of Bottom Floor')) 
    top_of_bottom_floor_app = extract_float_value(search_key(data_app, "Top of Bottom Floor")) 
    top_of_next_higher_floor_pdf = extract_float_value(search_key(data_pdf, 'Top of Next Higher Floor')) 
    LAG_pdf = extract_float_value(search_key(data_pdf, 'Lowest Adjacent Grade (LAG) next to building')) 
    LAG_app = extract_float_value(search_key(data_app, 'Lowest Adjacent Grade (LAG)') or search_key(data_pdf, "Lowest adjacent (finished) grade next to building (LAG)") or search_key(data_pdf, "Lowest Adjacent Grade") or search_key(data_pdf, "LAG")) 
    HAG_pdf = extract_float_value(search_key(data_pdf, 'Highest Adjacent Grade') or search_key(data_pdf, "Highest Adjacent Grade (HAG)") or search_key(data_pdf, "HAG") or search_key(data_pdf, "Highest adjacent (finished) grade next to building (HAG)"))    
    diagram_choices_1 = ['1', '1a', '3', '6', '7', '8']
    diagram_choices_2 = '1b'
    diagram_choices_3 = ['2', '2a', '2b', '4', '9']
    diagram_choices_4 = '5' 
    diagram_choices_5 = ['2', '2a', '2b', '4', '6', '7', '8', '9']

    section_e_measurements_used = False 
    diagram_choices_6 = ["1", "1a", "3", "6", "7", "8"]
    diagram_choices_7 = "1b"
    diagram_choices_8 = "5" 
    diagram_choices_9 = ["2", "2a", "2b", "4", "9"]
    diagram_choices_10 = ["6", "7", "8", "9"] 
    e1a = extract_float_value(search_key(data_pdf, 'Top of Bottom Floor') or search_key(data_pdf, 'Top of Bottom Floor (including basement, crawlspace, or enclosure) is') or search_key(data_pdf, "e1a"))  
    e1b = extract_float_value(search_second_key(data_pdf, 'Top of Bottom Floor') or search_key(data_pdf, 'Top of Bottom Floor (including basement, crawlspace, or enclosure) is') or search_key(data_pdf, "e1b")) 
    e2 = extract_float_value(search_key(data_pdf, 'Top of Next Higher Floor')) or extract_float_value(search_key(data_pdf, 'Top of Next Higher Floor (elevation C2.b in the diagrams) of the building is') or search_key(data_pdf, "e2")) 

    bfe = search_key(data_app, "Current Base Flood Elevation(BFE)") or search_key(data_app, "Current Base Flood Elevation") or search_key(data_app, "BFE")  

    h1a_top_of_bottom_floor = extract_float_value(search_key(data_pdf, 'Top of Bottom Floor'))
    h1b_top_of_next_higher_floor = extract_float_value(search_key(data_pdf, 'Top of Next Higher Floor')) 
    diagram_choices_11 = ['1', '1a', '3', '6', '7','8']
    diagram_choices_12 = ['2', '2a', '2b', '4', '9']
    diagram_choices_13 = ['2', '2a', '2b', '4', '6', '7', '8', '9']

    machinery = search_key(data_app, 'Is all machinery and equipment servicing the building, located inside or outside the building, elevated above the first floor') or search_key(data_app, 'Machinery or Equipment Above') or search_key(data_app, "the building, located inside or outside the building, elevated above the first floor") or search_key(data_app, "building, elevated above the first floor")  or search_key(data_app, "Does the building contain machinery and equipment servicing the building?") or search_key(data_app, "equipment servicing the building") 
    c2e_elevation_of_mahinery = extract_float_value(search_key(data_pdf, 'Lowest elevation of Machinery and Equipment (M&E) servicing the building (describe type of M&E and location in section D comments area)') or search_key(data_pdf, "Lowest elevation of machinery or equipment servicing the building")) 
    e4_top_of_platform = extract_float_value(search_key(data_pdf, 'Top of platform of machinery and/or equipment servicing the building is') or search_key(data_pdf, 'Top of platform of machinery and/or equipment'))
    h2 = search_key(data_pdf, "Machinery and Equipment (M&E) servicing the building") or search_key(data_pdf, "Machinery and Equipment servicing the building") or search_key(data_pdf, "Does the building contain machinery and equipment servicing the building?") 
    e2 = extract_float_value(search_key(data_pdf, "for building diagrams 6-9 with permanent flood openings provided in section A items B and/or  9 (see pages 1-2 of instructions), the next higher floor (c2.b in applicable building diagram) of the building is") or search_key(data_pdf , "Next higher floor"))   
    diagram_choices_14 = ['1', '1a', '1b', '3']
    diagram_choices_15 = ['2', '2a', '2b', '4', '6', '7', '8', '9'] 

    A8_non_engineered_flood_openings_pdf = extract_float_value(search_key(data_pdf, 'Non-Engineered Flood Openings') or search_key(data_pdf, 'Non-Engineered'))
    A8_engineered_flood_openings_pdf = extract_float_value(search_key(data_pdf, 'Engineered Flood Openings') or search_key(data_pdf, "d) Engineered flood openings?") or search_key(data_pdf, 'Engineered')) 
    A8_flood_openings_pdf = extract_float_value(search_key(data_pdf, 'Number of permanent flood openings in the crawlspace') or search_key(data_pdf, 'Number of permanent flood openings in the crawlspace or enclosures within 1.0 foot above adjacent grade') or search_key(data_pdf, 'No. of permanent openings (flood vents) within 1 ft. above adjacent grade'))
    A8_flood_openings_pdf = ((A8_non_engineered_flood_openings_pdf) + (A8_engineered_flood_openings_pdf)) or A8_flood_openings_pdf 
    A8_total_area = extract_float_value(search_key(data_pdf, "c) Total net area of flood openings in A8.b") or search_key(data_pdf, "Total net area of flood openings in A8.b") or search_key(data_pdf, "Total area of all permanent openings (flood vents) in C3h") or search_key(data_pdf, "Total net open area of non-engineered flood openings"))   

    # A9 vents
    A9_non_engineered_flood_openings_pdf = extract_float_value(search_second_key(data_pdf, 'Non-Engineered Flood Openings') or search_second_key(data_pdf, 'Non-Engineered'))
    A9_engineered_flood_openings_pdf = extract_float_value(search_second_key(data_pdf, 'Engineered Flood Openings') or search_key(data_pdf, "Has Engineered Openings:") or search_second_key(data_pdf, 'Engineered'))  
    A9_flood_openings_pdf = extract_float_value(search_second_key(data_pdf, 'Number of permanent flood openings in the crawlspace') or search_second_key(data_pdf, 'Number of permanent flood openings in the crawlspace or enclosures within 1.0 foot above adjacent grade') or search_second_key(data_pdf, 'No. of permanent openings (flood vents) within 1 ft. above adjacent grade')) 
    A9_flood_openings_pdf = ((A9_non_engineered_flood_openings_pdf) + (A9_engineered_flood_openings_pdf)) or A9_flood_openings_pdf
    # Area of A9
    A9_total_area = extract_float_value(search_second_key(data_pdf, "Total net open area of non-engineered flood openings in A9.c") or search_second_key(data_pdf, "Total net area of flood openings in A9.b") or search_second_key(data_pdf, "Total area of all permanent openings (flood vents) in C3h") or search_second_key(data_pdf, "Total net open area of non-engineered flood openings"))
    # total number of opening -> A8_openings + A9_openings
    total_number_of_openings = A8_flood_openings_pdf + A9_flood_openings_pdf
    # total area of openings -> A8_area + A9_area
    total_area_of_openings =  A8_total_area + A9_total_area 
    # getting vents number and area from the application
    number_of_flood_openings_app = extract_float_value(search_key(data_app, 'Number of Openings')) 
    area_of_flood_openings_app = extract_float_value(search_key(data_app, "Area of Permanent Openings (Sq. In.)") or search_key(data_app, "Area of Permanent Openings"))

    occupancy_type_app = search_key(data_app, "Occupancy Type") 
    occupancy_type_ec = search_key(data_pdf, "Building Occupancy") 

    result = search_key(data_app, "Total # of floors in building") or search_key(data_app, "total number of floors in building") or search_key(data_app, "total no of floors in building")  
    number_of_floors_app = result if result != '' else "0" 

    construction_type_app = str(search_key(data_app, "Building Construction Type") or search_key(data_app, "Construction Type")).strip().lower()

    foundation_type_app = search_key(data_app, "foundation") 
    appliances_on_first_floor = search_key(data_app, "Are all appliances elevated above the first floor?") or search_key(data_app, "Appliances on First Floor") or search_key(data_app, "Are all appliances elevated above the first floor") # yes / no

    flood_zone_app = normalize_string(search_key(data_app, "Current Flood Zone") or search_key(data_app, "Flood Zone")) 
    flood_zone_pdf = normalize_string(search_key(data_pdf, "B8. Flood Zone(s)") or search_key(data_pdf, "flood zone") or search_key(data_pdf, "B8") or search_key(data_pdf, "flood zones"))
    suffix_app = normalize_string(search_key(data_app, "Map Panel Suffix") or search_key(data_app, "suffix") or search_key(data_app, "panel"))
    suffix_pdf = normalize_string(search_key(data_pdf, "B5. Suffix") or search_key(data_pdf, "suffix") or search_key(data_pdf, "B5"))  
    firm_date_app = normalize_string(search_key(data_app, "FIRM Date") or search_key(data_app, "firm"))
    firm_date_pdf = normalize_string(search_key(data_pdf, "B6") or search_key(data_pdf, "B6 Firm index date") or search_key(data_pdf, "firm index date") or search_key(data_pdf, "firm") or search_key(data_pdf, "firm index") or search_key(data_pdf, "firm date")) 

    EC_expiration = search_key(data_pdf, "Expiration Date") or search_key(data_pdf, "Expire") or search_key(data_pdf, "Expiration") 
    survey_date = find_date_after_certifier(data_pdf, "Certifier's Name", "Date", 8) 

    return {
    "street_number_pdf": street_number_pdf,
    "street_name_pdf": street_name_pdf,
    "city_value_pdf": city_value_pdf,
    "state_value_pdf": state_value_pdf,
    "zipcode_value_pdf": zipcode_value_pdf,
    "address_pdf": address_pdf,
    "street_number_app": street_number_app,
    "address_app": address_app,
    "top_of_bottom_floor_app": top_of_bottom_floor_app,
    "top_of_next_higher_floor_app": top_of_next_higher_floor_app,
    "Section_C_LAG_app": Section_C_LAG_app,
    "diagramNumber_pdf": diagramNumber_pdf,
    "diagram_number_app": diagram_number_app,
    "crawlspace_details": crawlspace_details,
    "crawlspace_square_footage": crawlspace_square_footage,
    "garage_details": garage_details,
    "garage_square_footage": garage_square_footage,
    "enclosure_Size": enclosure_Size,
    "total_square_footage": total_square_footage,
    "diagrams_for_crawlspace": diagrams_for_crawlspace,
    "CBRS": CBRS,
    "OPA": OPA,
    "CBRS_OPA_app": CBRS_OPA_app,
    "Construction_status_pdf": Construction_status_pdf,
    "Construction_status_app": Construction_status_app,
    "certifier_name_pdf": certifier_name_pdf,
    "certifier_license_number": certifier_license_number,
    "Section_C_FirstFloor_Height_app": Section_C_FirstFloor_Height_app,
    "Section_C_Lowest_Floor_Elevation_app": Section_C_Lowest_Floor_Elevation_app,
    "section_c_measurements_used": section_c_measurements_used,
    "Elevation_Certificate_Section_Used": Elevation_Certificate_Section_Used,
    "top_of_bottom_floor_pdf": top_of_bottom_floor_pdf,
    "top_of_next_higher_floor_pdf": top_of_next_higher_floor_pdf,
    "LAG_pdf": LAG_pdf,
    "LAG_app": LAG_app,
    "HAG_pdf": HAG_pdf,
    "diagram_choices_1": diagram_choices_1,
    "diagram_choices_2": diagram_choices_2,
    "diagram_choices_3": diagram_choices_3,
    "diagram_choices_4": diagram_choices_4,
    "diagram_choices_5": diagram_choices_5,
    "section_e_measurements_used": section_e_measurements_used,
    "diagram_choices_6": diagram_choices_6,
    "diagram_choices_7": diagram_choices_7,
    "diagram_choices_8": diagram_choices_8,
    "diagram_choices_9": diagram_choices_9,
    "diagram_choices_10": diagram_choices_10,
    "e1a": e1a,
    "e1b": e1b,
    "e2": e2,
    "h1a_top_of_bottom_floor": h1a_top_of_bottom_floor,
    "h1b_top_of_next_higher_floor": h1b_top_of_next_higher_floor,
    "diagram_choices_11": diagram_choices_11,
    "diagram_choices_12": diagram_choices_12,
    "diagram_choices_13": diagram_choices_13,
    "machinery": machinery,
    "c2e_elevation_of_mahinery": c2e_elevation_of_mahinery,
    "e4_top_of_platform": e4_top_of_platform,
    "h2": h2,
    "diagram_choices_14": diagram_choices_14,
    "diagram_choices_15": diagram_choices_15,
    "A8_non_engineered_flood_openings_pdf": A8_non_engineered_flood_openings_pdf,
    "A8_engineered_flood_openings_pdf": A8_engineered_flood_openings_pdf,
    "A8_flood_openings_pdf": A8_flood_openings_pdf,
    "A8_total_area": A8_total_area,
    "A9_non_engineered_flood_openings_pdf": A9_non_engineered_flood_openings_pdf,
    "A9_engineered_flood_openings_pdf": A9_engineered_flood_openings_pdf,
    "A9_flood_openings_pdf": A9_flood_openings_pdf,
    "A9_total_area": A9_total_area,
    "total_number_of_openings": total_number_of_openings,
    "total_area_of_openings": total_area_of_openings,
    "number_of_flood_openings_app": number_of_flood_openings_app,
    "area_of_flood_openings_app": area_of_flood_openings_app,
    "occupancy_type_app": occupancy_type_app,
    "occupancy_type_ec": occupancy_type_ec,
    "number_of_floors_app": number_of_floors_app,
    "construction_type_app": construction_type_app,
    "foundation_type_app": foundation_type_app,
    "appliances_on_first_floor": appliances_on_first_floor,
    "flood_zone_app": flood_zone_app,
    "flood_zone_pdf": flood_zone_pdf,
    "suffix_app": suffix_app,
    "suffix_pdf": suffix_pdf,
    "firm_date_app": firm_date_app,
    "firm_date_pdf": firm_date_pdf,
    "EC_expiration": EC_expiration,
    "survey_date": survey_date
}

# ========================================================================
# All extracted variables
# ========================================================================

print("Rule 1\n----------------------------------------------------")

def verify_address(address_pdf, address_app, street_name_pdf, street_number_app):
    results = []
    results.append(f"Address from PDF: {address_pdf}")
    results.append(f"Address from Application: {address_app}")

    if street_name_pdf == street_number_app:
        results.append("Street Number matched on EC and Application.")
    else:
        results.append("Street Number not matched on EC and Application.")

    comparison_result = compare_addresses(address_pdf, address_app)
    results.append(f"{comparison_result}")
    
    status = "✅" if "Matched" in comparison_result else ("❌" if "doesn't match" in comparison_result else "⚠️")
    
    return {
        "rule": "Rule 1 - Address Verification",
        "status": status,
        "details": results
    }

# Diagram Numbers 
print("Rule 2\n----------------------------------------------------")

def verify_diagram_number(diagramNumber_pdf, diagram_number_app=None, top_of_bottom_floor_app=None, top_of_next_higher_floor_app=None, Section_C_LAG_app=None):
    results = []
    results.append(f"PDF diagram number: {diagramNumber_pdf}")
    results.append(f"Application diagram number: {diagram_number_app}")
    
    status = "✅"
    
    # Logic for diagram reassignment
    if str(diagram_number_app) == "8" and top_of_bottom_floor_app is not None and top_of_next_higher_floor_app is not None:
        if abs(extract_float_value(top_of_bottom_floor_app) - extract_float_value(top_of_next_higher_floor_app)) > 5:
            results.append("Diagram number on application is 8, but there is more than 5 feet difference between 'Top of bottom floor' and 'Top of next higher floor'. Reassigning diagram number as 7")
            diagram_number_app = 7

    if str(diagram_number_app) == "9" and Section_C_LAG_app is not None and top_of_bottom_floor_app is not None:
        if (Section_C_LAG_app - top_of_bottom_floor_app) > 2:
            results.append("Diagram number on application is 9, but there is more than 2 feet difference between 'Top of bottom floor' and the 'LAG'. Reassigning diagram number as 2")
            diagram_number_app = 2
            
        if top_of_next_higher_floor_app is not None and (top_of_bottom_floor_app - top_of_next_higher_floor_app) > 5:
            results.append("Diagram number on application is 9, but there is more than 5 feet difference between 'Top of bottom floor' and the 'Top of next higher floor'. Reassigning diagram number as 2")
            diagram_number_app = 2

    if diagramNumber_pdf and diagram_number_app:
        if str(diagramNumber_pdf).lower().strip()[0] == str(diagram_number_app).lower().strip()[0]:
            results.append("✅ Diagram Numbers matched.")
        else:
            results.append("❌ The diagram numbers on the EC and application do not match. Underwriting review required.")
            status = "❌"
    else:
        results.append("⚠️ The diagram number on the EC is missing. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 2 - Diagram Number Verification",
        "status": status,
        "details": results
    }

# Crawlspace and Garage Square Footage details
print("\nRule 3\n----------------------------------------------------")

def verify_crawlSpace_details(diagramNumber_pdf, diagrams_for_crawlspace, total_square_footage, enclosure_Size, crawlspace_square_footage, garage_square_footage):
    results = []
    status = "✅"
    
    if diagramNumber_pdf in diagrams_for_crawlspace: 
        if total_square_footage == enclosure_Size:
            results.append(f"Diagram Number is among {', '.join(map(str, diagrams_for_crawlspace))}. and Crawlspace and Garage square footage '{crawlspace_square_footage + garage_square_footage}' is aligned with Total Enclosure size '{enclosure_Size}' in the application. ✅")
        else:
            results.append("The square footage of the enclosure(s) on the EC doesn't match the application. Underwriting review required ❌")
            status = "❌"
    else:
        results.append(f"Diagram Number is not among {', '.join(map(str, diagrams_for_crawlspace))}. so no comparison is required. ✅")
    
    return {
        "rule": "Rule 3 - Crawlspace Details Verification",
        "status": status,
        "details": results
    }

# Searching for CBRS/OPA details  cbrsSystemUnitOrOpa 
print("\nRule 4\n----------------------------------------------------")

def verify_CBRS_OPA_details(CBRS_OPA_app, CBRS, OPA):
    results = []
    status = "✅"
    
    if str(CBRS_OPA_app).lower() != str(CBRS).lower() or str(CBRS_OPA_app).lower().strip() != str(OPA).lower().strip():
        results.append("CBRS/OPA details do not match. ❌")
        status = "❌"
    else:
        results.append("CBRS/OPA details matched with the application. ✅")
    
    if str(CBRS).lower().strip() == "yes" or str(OPA).lower().strip() == "yes":
        results.append("Area in CBRS/OPA, Additional Documentation Required.")
    else:
        results.append("Area not in CBRS/OPA, Additional Documentation Not Required.")
    
    return {
        "rule": "Rule 4 - CBRS/OPA Details Verification",
        "status": status,
        "details": results
    }


# Rule 5
#----------------------------------------------------------------------------------
print("Rule 5\n----------------------------------------------------")
def verify_construction_status(Construction_status_pdf, Construction_status_app):
    results = []
    status = "✅"
    
    if normalize_string(Construction_status_pdf) == "finishedconstruction" and str(Construction_status_app).lower().strip() == "yes":
        results.append("Construction Status mismatched. Confirm the construction status of the building. ❌")
        status = "❌"
    elif normalize_string(Construction_status_pdf) == "finishedconstruction" and str(Construction_status_app).strip() == "no":
        results.append("Construction Status matched on EC and Application. ✅")
    elif normalize_string(Construction_status_pdf) == "buildingunderconstruction" and str(Construction_status_app).lower().strip() == "yes":
        results.append("Construction Status matched on EC and Application. ✅")

    if (normalize_string(Construction_status_pdf) in ["constructiondrawings", "buildingunderconstruction", "underconstruction"] 
        and str(Construction_status_app).lower().strip() == "yes"):
        results.append("A finished construction EC is required.")
        if status == "✅":
            status = "⚠️"
    
    return {
        "rule": "Rule 5 - Construction Status Verification",
        "status": status,
        "details": results
    }

# Rule 6 
#--------------------------------------------------------------------
print("Rule 6\n----------------------------------------------------")

def verify_certifier(Elevation_Certificate_Section_Used, section_c_measurements_used, certifier_name_pdf, certifier_license_number):
    results = []
    status = "✅"
    
    if "c" in str(Elevation_Certificate_Section_Used).lower().strip():
        section_c_measurements_used = True  
        results.append("Section C measurements are used in the application. ✅")
    else:
        results.append("Section C measurements are not used in the application. ❌")
        status = "❌"

    if section_c_measurements_used:
        if certifier_name_pdf:
            results.append(f"Certifier name: '{certifier_name_pdf}' is present on EC. ✅")
        else:
            results.append("Please review. Certifier name is not present on EC. ❌")
            status = "❌"
        
        if certifier_license_number:
            results.append(f"Certifier's License number: '{certifier_license_number}' is present on EC. ✅")
        else:
            results.append("Please Review. Certifier's License number is not present on EC. ❌")
            status = "❌"
    
    return {
        "rule": "Rule 6 - Certifier Verification",
        "status": status,
        "details": results
    }


# Rule 7 - Elevation Logic 
#----------------------------------------------------------------------------------
print("Rule 7\n----------------------------------------------------")

def verify_sectionC_measurements(HAG_pdf, LAG_pdf, section_c_measurements_used, top_of_bottom_floor_pdf, top_of_bottom_floor_app, top_of_next_higher_floor_app, top_of_next_higher_floor_pdf, LAG_app, diagramNumber_pdf, diagram_choices_1, diagram_choices_2, diagram_choices_3, diagram_choices_4, diagram_choices_5):
    results = []
    status = "✅"
    
    if HAG_pdf < LAG_pdf:
        results.append("The EC elevation of the HAG is lower than the LAG. Underwriting review required. ❌")
        status = "❌"
    else:
        results.append("The EC elevation of the HAG is higher than the LAG. ✅")

    if section_c_measurements_used:
        if top_of_bottom_floor_pdf == top_of_bottom_floor_app:
            results.append("Top of bottom floor is matched on EC and Application. ✅")
        else:
            results.append("Please review. Top of bottom floor is not matched on EC and Application. ❌")
            status = "❌"
        
        if top_of_next_higher_floor_app == top_of_next_higher_floor_pdf:
            results.append("Top of next higher floor is matched on EC and Application. ✅")
        else:
            results.append("Please review. Top of next higher floor is not matched on EC and Application. ❌")
            status = "❌"

        if LAG_app == LAG_pdf:
            results.append("Lowest Adjacent Grade (LAG) is matched on EC and Application. ✅")
        else:
            results.append("Please review. Lowest Adjacent Grade (LAG) is not matched on EC and Application. ❌")
            status = "❌"

        # Elevation Logic
        if str(diagramNumber_pdf).lower().strip() in diagram_choices_1:   
            if top_of_bottom_floor_pdf < LAG_pdf + 2: 
                results.append("Elevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅")
            else:
                results.append("Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")
                status = "❌"

            if top_of_bottom_floor_pdf >= LAG_pdf:
                results.append("Elevation Logic matched. Top of bottom floor is greater than LAG. ✅")
            else:
                results.append("Please review the foundation system as the top of bottom floor is less than the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() == diagram_choices_2:  
            if LAG_pdf <= top_of_bottom_floor_pdf < LAG_pdf + 6:
                results.append("Elevation Logic matched. The top of bottom floor is within 6 feet of the LAG. ✅")
            else:
                results.append("Please review stem-wall foundation system as the top of bottom floor is not within 6 feet of the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() in diagram_choices_3:
            if top_of_bottom_floor_pdf < LAG_pdf:
                results.append("Elevation Logic matched. The top of bottom floor is below the LAG. ✅")
            else:
                results.append("Please verify the building foundation as the top of bottom floor is not below the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() in diagram_choices_4:
            if LAG_pdf <= top_of_bottom_floor_pdf:
                results.append("Elevation Logic matched. The top of bottom floor elevation is above the LAG for this Diagram 5 building. ✅")
            else:
                results.append("Please verify foundation system. The top of bottom floor elevation is below the LAG for this Diagram 5 building. ❌")
                status = "❌"
            
            if top_of_bottom_floor_pdf <= (LAG_pdf + 20):
                results.append("Elevation Logic matched. Top of bottom floor is below 20 feet of LAG. ✅")
            else:
                results.append("Please review elevations and photographs as there is more than 20 foot difference between C2a and the LAG. ❌")
                status = "❌"

        if str(diagramNumber_pdf).lower().strip() in diagram_choices_5:
            if top_of_next_higher_floor_pdf and top_of_next_higher_floor_pdf > top_of_bottom_floor_pdf:
                results.append("Elevation Logic matched. The C2b elevation is not lower than the C2a elevation. ✅")
            else: 
                results.append("Underwriting review required. The C2b elevation is lower than the C2a elevation. ❌")
                status = "❌"
        
        # Additional checks
        if abs(LAG_pdf-top_of_bottom_floor_pdf) > 20: 
            results.append("There is more than a 20 foot difference between C2a and the LAG. Review of photographs required. ❌")
            status = "❌"
        else:
            results.append("LAG and C2a difference is smaller than 20. Passed -> No underwriter review required. ✅")

        if abs(LAG_pdf-top_of_next_higher_floor_pdf) > 20:
            results.append("Please review elevations and photographs as there is more than 20 foot difference between the LAG and Next Higher Floor. ❌")
            status = "❌"
        else:
            results.append("LAG and C2b difference is smaller than 20. Passed -> No underwriter review required. ✅")
    
    return {
        "rule": "Rule 7 - Section C Measurements Verification",
        "status": status,
        "details": results
    }


# Section E measurements used
print("\nRule 8\n----------------------------------------------------")
def verify_sectionE_measurements(Elevation_Certificate_Section_Used, section_e_measurements_used, e1b, top_of_bottom_floor_app, diagramNumber_pdf, diagram_choices_6, LAG_pdf, diagram_choices_7, diagram_choices_8, diagram_choices_9, diagram_choices_10, e2, e1a):
    results = []
    status = "✅"
    
    if "e" in str(Elevation_Certificate_Section_Used).lower().strip():
        section_e_measurements_used = True
        results.append("Section E measurements are used in the application. ✅")
    else:
        results.append("Section E measurements are not used in the application. ❌")
        return {
            "rule": "Rule 8 - Section E Measurements Verification",
            "status": "❌",
            "details": results
        }

    if section_e_measurements_used:
        if abs(e1b) == abs(top_of_bottom_floor_app): 
            results.append("EC Top of Bottom Floor matches with the Application. ✅")
        else:
            results.append("The Top of Bottom Floor elevation in Section E of the EC doesn't match the application. Underwriting review required. ❌")
            status = "❌"

        if str(diagramNumber_pdf).lower().strip() in diagram_choices_6:
            if e1b < LAG_pdf + 2:
                results.append("Elevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅")
            else:
                results.append("Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")
                status = "❌"

            if e1b >= LAG_pdf:
                results.append("Elevation Logic matched. The top of bottom floor is greater than the LAG. ✅")
            else:
                results.append("Please review foundation system as the top of bottom floor is less than the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() == diagram_choices_7:  
            if e1b <= LAG_pdf + 6:
                results.append("Elevation Logic matched. The elevation is within 6 feet of LAG. ✅")
            else:
                results.append("E1b: Please Review, The elevation is not be within 6 feet of LAG. ❌")
                status = "❌"

            if e1b >= LAG_pdf:
                results.append("Elevation Logic matched. The e1b elevation is greater than LAG. ✅")
            else:
                results.append("Please Review, the e1b elevation is lower than LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() in diagram_choices_8:
            if e1b <= (LAG_pdf + 20):
                results.append("Elevation Logic matched. e1b is lower than 20 feet of LAG. ✅")
            else: 
                results.append("Please review elevations and photographs as there is more than 20 foot difference between the E1b elevation and the LAG. ❌")
                status = "❌"

            if e1b >= LAG_pdf:
                results.append("Elevation Logic matched. The e1b elevation is greater than the LAG. ✅")
            else:
                results.append("The top of bottom floor elevation is below the LAG for this Diagram 5 building. Please verify foundation system. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() in diagram_choices_9:
            if e1b < LAG_pdf: 
                results.append("The top of bottom floor is above the LAG. Elevation Logic matched. ✅")
            else:
                results.append("Please review the foundation system as the top of bottom floor is not below the LAG. ❌")
                status = "❌"

        if str(diagramNumber_pdf).lower().strip() in diagram_choices_10:
            if not e2:
                results.append("Please review the elevation certificate as the E2 elevation is not present. ❌")
                status = "❌"

            if e2 > e1a: 
                results.append("E2 is higher than E1b. Elevation Logic matched. ✅")
            else:
                results.append("Please review the elevation certificate as E2 is less than E1b. ❌")
                status = "❌"

        if e1a > 20 or e1b > 20 or e2 > 20:  
            results.append("Please review elevations and photographs as there is more than 20 foot difference in Section E. ❌")
            status = "❌"
        else:
            results.append("E1a, E1b, and E2 are smaller than 20. Passed -> No underwriter review required. ✅")
    
    return {
        "rule": "Rule 8 - Section E Measurements Verification",
        "status": status,
        "details": results
    }

# Section H 
#------------------------------------------------------------------------------- 
print("Rule 9 - Section H\n----------------------------------------------------")

def verify_sectionH_measurements(Elevation_Certificate_Section_Used, diagramNumber_pdf, diagram_choices_11, h1a_top_of_bottom_floor, LAG_pdf, diagram_choices_12, diagram_choices_13, h1b_top_of_next_higher_floor):
    results = []
    status = "✅"
    
    if str(Elevation_Certificate_Section_Used).lower().strip() == "h":
        results.append("Section H measurements are used in the application. ✅")
        
        if str(diagramNumber_pdf).lower().strip() in diagram_choices_11:
            if h1a_top_of_bottom_floor <= LAG_pdf + 2:
                results.append("Elevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅")
            else:   
                results.append("Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")
                status = "❌"

            if h1a_top_of_bottom_floor >= LAG_pdf:
                results.append("Elevation Logic matched. The top of bottom floor is greater than the LAG. ✅")
            else:
                results.append("Please review foundation system as the top of bottom floor is less than the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() == '1b':
            if LAG_pdf <= h1a_top_of_bottom_floor:
                results.append("H1a: For diagram no. '1b' The elevation is above the LAG. Elevation Logic matched. ✅")
            else:
                results.append("Please review the foundation system as the top of bottom floor is below the LAG. ❌")
                status = "❌"

            if h1a_top_of_bottom_floor < LAG_pdf + 6:
                results.append("The top of bottom floor is within 6 feet of the LAG. ✅")
            else:
                results.append("Please review the foundation system as the top of bottom floor is not within 6 feet of the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() in diagram_choices_12:
            if LAG_pdf > h1a_top_of_bottom_floor:
                results.append("Top of bottom floor is below the LAG. Elevation Logic matched. ✅")
            else:
                results.append("Please review foundation system as the top of bottom floor is at or above the LAG. ❌")
                status = "❌"

        elif str(diagramNumber_pdf).lower().strip() == '5':
            if h1a_top_of_bottom_floor <= (LAG_pdf + 20):
                results.append("there is not more than a 20 foot difference between H1a and the LAG. Elevation Logic matched. ✅")
            else: 
                results.append("Please review elevations and photographs as there is more than a 20 foot difference between H1a and the LAG. ❌")
                status = "❌"

            if LAG_pdf <= h1a_top_of_bottom_floor:
                results.append("H1a elevation is above the LAG. Elevation Logic matched. ✅")
            else:
                results.append("Please review. The H1a elevation is below the LAG. ❌")
                status = "❌"

        if str(diagramNumber_pdf).lower().strip() in diagram_choices_13:
            if h1b_top_of_next_higher_floor: 
                results.append("H1b is present on EC. ✅")
            else:
                results.append("Underwriting review required as H1b is missing from the EC. ❌")
                status = "❌"

            if h1b_top_of_next_higher_floor > h1a_top_of_bottom_floor:
                results.append("H1b > H1a. Elevation Logic matched. ✅")
            else:
                results.append("Underwriting review required as H1b <= H1a. ❌")
                status = "❌"

            if h1a_top_of_bottom_floor > 20 or h1b_top_of_next_higher_floor > 20:
                results.append("Please review elevations and photographs as there is more than a 20 foot difference described in Section H. ❌")
                status = "❌"
            else:
                results.append("H1a and H1b are smaller than 20. Passed -> No underwriter review required. ✅")
    else:
        results.append("Section H measurements are not used in the application.")
    
    return {
        "rule": "Rule 9 - Section H Measurements Verification",
        "status": status,
        "details": results
    }

#----------------------------------------------------------------
print("\nRule 10\n----------------------------------------------------")

def verify_Machinery_logic(bfe, flood_zone_app, machinery, diagramNumber_pdf, diagram_choices_14, top_of_next_higher_floor_pdf, c2e_elevation_of_machinery, top_of_bottom_floor_pdf, e4_top_of_platform, e1b, h2, diagram_choices_15, e2):
    results = []
    status = "✅"
    SFHA = False

    if str(flood_zone_app).strip().upper() in ['X', 'B', 'C', 'A99']:
        results.append(f"✅ Flood Zone is among these 'X, B, C, A99'. BFE Logic is not applicable. Moving next...\n") 
        status = "✅"  

    SFHA_list = [
        "A", "AE",
        "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10",
        "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18", "A19", "A20",
        "A21", "A22", "A23", "A24", "A25", "A26", "A27", "A28", "A29", "A30",
        "AH", "AO", "A99", 
        "V", "VE",
        "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10",
        "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20",
        "V21", "V22", "V23", "V24", "V25", "V26", "V27", "V28", "V29", "V30"
    ]

    if str(flood_zone_app).strip().upper() in SFHA_list:
        SFHA = True

    if SFHA and bfe is not None:
        if c2e_elevation_of_machinery >= bfe:
            print("Property in SFHA, and BFE is present.\n") 
            results.append(f"✅ Machinery elevation {c2e_elevation_of_machinery} is at or above BFE {bfe}.\n")
            status = "✅"
        else:
            results.append(f"❌ Machinery elevation {c2e_elevation_of_machinery} is below BFE {bfe}. Continue to Steps 2–4.\n")
            status = "❌"
    else:
        results.append("⚠️ Property is not in SFHA or BFE not provided. Continue to Steps 2–4.\n") 
        status = "❌"

    if str(machinery).lower().strip() == "yes":
        results.append("Machinery or Equipment Above is present in the application. ✅")

        if str(diagramNumber_pdf).lower().strip() in diagram_choices_14: 
            if top_of_next_higher_floor_pdf is not None:
                if c2e_elevation_of_machinery >= top_of_next_higher_floor_pdf:
                    results.append("Elevation Logic matched. The M&E elevation on the EC support the M&E mitigation discount. ✅") 
                else:
                    results.append("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required. ❌")
                    status = "❌"
            
            elif not top_of_next_higher_floor_pdf:
                if c2e_elevation_of_machinery >= top_of_bottom_floor_pdf + 8:
                    results.append("Elevation of machinery is higher than 8 feet of top of bottom floor. Elevation Logic matched. ✅")
                else:
                    results.append("Elevation of machinery is not higher than 8 feet of top of bottom floor. The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.❌")
                    status = "❌"
            
            if e4_top_of_platform >= e1b + 8:
                results.append(f"For diagrams '{', '.join(map(str, diagram_choices_14))}' The top of platform of machinery and/or equipment servicing the building should be at least 8 feet higher than the top of bottom floor. Top of platform: {e4_top_of_platform}, Top of bottom floor: {e1b}. Elevation Logic matched. ✅")
            else:
                results.append("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required. ❌")
                status = "❌"

            if str(h2).lower().strip() == "yes":
                results.append("H2 is marked as 'Yes' in the EC")
            elif str(h2).lower().strip() == "no":
                results.append("Section H2 of the EC does not appear to support the M&E mitigation discount. Underwriting review required.")
                status = "❌"
            else:
                results.append("H2 is not marked in the EC")

        elif str(diagramNumber_pdf).lower() in diagram_choices_15:
            if c2e_elevation_of_machinery >= top_of_next_higher_floor_pdf:
                results.append("The elevation of machinery is higher than top of next higher floor. Elevation Logic matched. ✅")
            else:
                results.append("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.")
                status = "❌"
            
            if e4_top_of_platform >= e2:
                results.append("Top of platform of machinery is higher than E2. Elevation Logic matched. ✅")
            else:
                results.append("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.")
                status = "❌"

            if str(h2).strip().lower() == "yes":
                results.append("H2 is marked as 'Yes' in the EC")
            elif str(h2).strip().lower() == "no":
                results.append("H2 is marked as 'No' in the EC")
            else:
                results.append("H2 is not marked in the EC")

        elif str(diagramNumber_pdf).lower().strip() == '5':
            if c2e_elevation_of_machinery >= top_of_bottom_floor_pdf:
                results.append(f"For diagrams '5' The elevation of machinery and equipment should be equal or greater than the top of bottom floor. Elevation of machinery and equipment: {c2e_elevation_of_machinery}, Top of bottom floor: {top_of_bottom_floor_pdf}. Elevation Logic matched.")
            else:
                results.append("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.")
                status = "❌"
            
            if e4_top_of_platform >= e1b:
                results.append("Top of platform of machinery is higher than E1b. Elevation Logic matched. ✅")
            else:
                results.append("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.")
                status = "❌"

            if str(h2).strip().lower() == "yes":
                results.append("H2 is marked as 'Yes' in the EC.")
            elif str(h2).lower().strip() == "no":
                results.append("Section H2 of the EC does not appear to support the M&E mitigation discount. Underwriting review required.")
                status = "❌"
            else:
                results.append("H2 is marked as 'Yes' in the EC.")
    else:
        results.append("Machinery or Equipment Above is not present in the application.")
    
    return { 
        "rule": "Rule 10 - Machinery Logic Verification",
        "status": status,
        "details": results
    }
 

# Rule 11 ------------------------------------------------------------
print("\nRule 11\n----------------------------------------------------") 

def verify_vents_details(diagramNumber_pdf, diagram_choices_10, total_number_of_openings, number_of_flood_openings_app, total_area_of_openings, area_of_flood_openings_app):
    results = []
    status = "✅"
    
    if str(diagramNumber_pdf).lower().strip() in diagram_choices_10:
        results.append(f"Diagram Number is among '{', '.join(map(str, diagram_choices_10))}'.")
        
        if total_number_of_openings == number_of_flood_openings_app:
            results.append("Total number of vents on the EC (Sections A8 + A9) matches with the application.")
        else:
            results.append("Please Review. Total number of vents on the EC (Sections A8 + A9) does not match with the application.")
            status = "❌"
        
        if total_area_of_openings == area_of_flood_openings_app:
            results.append("Total area of vents on the EC (Sections A8 + A9) matches with the application.")
        else:
            results.append("Please Review. Total area of vents on the EC (Sections A8 + A9) does not match with the application.")
            status = "❌"
    else:
        results.append(f"Diagram Number is not among '{', '.join(map(str, diagram_choices_10))}'.")
    
    return {
        "rule": "Rule 11 - Vents Details Verification",
        "status": status,
        "details": results
    }



# ========================================================================================
# Rule # 12 - Photograph Rules start here 
# ========================================================================================
print("Rule 12\n----------------------------------------------------")

def verify_photograph_requirement(Construction_status_app):
    results = []
    status = "✅"
    
    if str(Construction_status_app).strip().lower() == "yes":
        results.append("Building underconstruction. Photographs are not required.")
    else:
        results.append("Building is not underconstruction. Photographs are required.")
    
    return {
        "rule": "Rule 12 - Photograph Requirement",
        "status": status,
        "details": results
    }


# ============================================================================================
# Rule # 13 
# ============================================================================================
print("Rule 13\n----------------------------------------------------") 

def verify_building_eligibility(image_path):
    results = []
    status = "✅"
    
    building_eligibility = analyze_image( 
        image_path=image_path,  
        question=["The building in the image(s) is affixed to a permanent site, and has two or more outside rigid walls with a fully secured roof? (True/False)"]
    )

    if str(building_eligibility).strip().lower() == "true":
        results.append("✅ The building is affixed to a permanent site, has two or more outside rigid walls, and a fully secured roof.")
    else:
        results.append("❌ The building is not affixed to a permanent site, does not have two or more outside rigid walls, or does not have a fully secured roof. Underwriting review required.")
        status = "❌"
    
    return {
        "rule": "Rule 13 - Building Eligibility",
        "status": status,
        "details": results
    }
# ===========================================================================================
# Rule # 14 
# ===========================================================================================
print("Rule 14\n----------------------------------------------------")

def verify_occupancy(occupancy_type_app, occupancy_type_ec, image_path):
    results = []
    status = "✅"
    
    if occupancy_type_app == occupancy_type_ec:
        results.append("✅ Occupancy Type matches on EC and Application.")
    else:
        results.append("❌ Please review. Occupancy Type does not match on EC and Application.")
        status = "❌"

    if str(occupancy_type_app).strip().lower() == "residential" or str(occupancy_type_ec).strip().lower() == "non-residential" or str(occupancy_type_ec).strip().lower() =="other residential" or str(occupancy_type_ec).strip().lower() == "residential condominium building" or str(occupancy_type_ec).strip().lower() == "two-four family":
        result = analyze_image(
            image_path=image_path,  
            question=["The building in the image(s) has multi-unit structures? (True/False)"]
        ) 

        if str(result).strip().lower() == "true": 
            results.append("✅ The building is a residential / non-residential unit, two-four family, Other Residential, or residential condominium building, and has a multi-unit structure.")
        elif str(result).lower() == "false":
            results.append("❌ The building is a residential / non-residential unit, two-four family, Other Residential, or residential condominium building, but does not have a multi-unit structure. Underwriting review required.")
            status = "❌"
        else:
            results.append("❌ AI provided an unexpected response. Underwriting review required.")
            status = "❌"
    else:
        results.append("⚠️ The occupancy type is not Residential, Non-Residential, Other Residential, or Residential Condominium Building, or Two-Four Family. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 14 - Occupancy Verification",
        "status": status,
        "details": results
    }
# ===========================================================================================
# Rule # 15
# ===========================================================================================
print("Rule 15\n----------------------------------------------------")

def verify_underWater(image_path):
    results = []
    status = "✅"
    
    under_water = analyze_image(
        image_path=image_path,  
        question=["Some part of the building or entire building in the image(s) is over water? (True/False)"]
    ) 

    if str(under_water).strip().lower() == "true":
        results.append("❌ The building is over water. Underwriting review required.")
        status = "❌"
    elif str(under_water).strip().lower() == "false":
        results.append("✅ The building is not over water.")
    else:
        results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 15 - Under Water Verification",
        "status": status,
        "details": results
    }


# ===========================================================================================
# Rule # 16
# ===========================================================================================
print("Rule 16\n----------------------------------------------------")
def verify_foundation_eligibility(image_path):
    results = []
    status = "✅"
    
    foundation_eligibility = analyze_image(
        image_path=image_path,  
        question=["Does the building in the image(s) show the 'front' and 'back' of the building, including the 'foundation system' and are the 'number of floors' visible clearly? (True/False)"] 
    )  

    if str(foundation_eligibility).strip().lower() == "true":
        results.append("✅ The building in the image(s) shows the 'front' or 'back' of the building, including the 'foundation system' and the 'number of floors' are visible clearly.")
    elif str(foundation_eligibility).strip().lower() == "false":
        results.append("❌ The building in the image(s) does not show one of the 'front' and 'back' of the building, or the 'foundation system' or the 'number of floors' are not visible clearly. Underwriting review required.")
        status = "❌"
    else:
        results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 16 - Foundation Eligibility",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Rule # 17
# ===========================================================================================
print("Rule 17\n----------------------------------------------------")

def verify_foundation_type(diagram_number_app, image_path):
    results = []
    status = "✅"
    
    foundation_type = ""
    choices_1 = ['1', '1a', '1b', '3']
    choices_2 = ['2', '2a', '4']
    choice_3 = "3b"
    choices_6 = ['8', '9'] 

    if normalize_string(str(diagram_number_app)) in choices_1:
        foundation_type = "slab on grade"  
    elif normalize_string(str(diagram_number_app)) in choices_2: 
        foundation_type = "basement" 
    elif normalize_string(str(diagram_number_app)) in choice_3:  
        foundation_type = "basement with exterior egress" 
    elif normalize_string(str(diagram_number_app)) == '5':
        foundation_type = "Elevated Without Enclosure on Posts" or "Elevated Without Enclosure on Piles" or "Elevated Without Enclosure on Piers"
    elif normalize_string(str(diagram_number_app)) in normalize_string('6'):
        foundation_type = "Elevated With Enclosure on Posts" or "Elevated With Enclosure on Piles" or "Elevated With Enclosure on Piers"
    elif normalize_string(str(diagram_number_app)) in normalize_string('7'):
        foundation_type = "Elevated With Enclosure Not On Posts" or "Elevated With Enclosure Not On Piles" or "Elevated With Enclosure Not On Piers" 
    elif normalize_string(str(diagram_number_app)) in choices_6:
        foundation_type = "Crawlspace"

    foundation_type_ai = analyze_image(
        image_path=image_path,  
        question=["Deeply analyze the given image, and tell what is the foundation type of the building in the image(s)? Select only one from give options:"
        "Slab on Grade"
        "Basement"
        "Elevated Without Enclosure on Posts"
        "Elevated Without Enclosure on Piles"
        "Elevated Without Enclosure on Piers"
        "Elevated With Enclosure on Posts"
        "Elevated With Enclosure on Piles"
        "Elevated With Enclosure on Piers"
        "Elevated With Enclosure Not On Posts"
        "Elevated With Enclosure Not On Piles"
        "Elevated With Enclosure Not On Piers"
        "Crawlspace"] 
    )

    results.append(f"Foundation type in the application: {foundation_type}")
    results.append(f"Foundation type in the image (by AI): {foundation_type_ai}")

    if str(foundation_type).strip().lower() == str(foundation_type_ai).strip().lower(): 
        results.append("✅ The foundation type in the application matches with the foundation type in the image.")
    else:
        results.append("❌ The foundation type in the application does not match with the foundation type in the image. Underwriting review required.")
        status = "❌"
    
    return {
        "rule": "Rule 17 - Foundation Type Verification",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Rule # 18
# ===========================================================================================
print("Rule 18\n----------------------------------------------------")

def verify_number_of_floors(image_path, number_of_floors_app): 
    results = []
    status = "✅"
    
    results.append(f"Number of floors in the application: {number_of_floors_app}")

    number_of_floor_openai = analyze_image(
        image_path=image_path,  
        question=["Count the number of floors in the building visible in the image(s). do not count mid-level entries, enclosures, basements, or crawlspaces (on grade or subgrade) as a floor. Respond with only a single integer like 1, 2, 3, etc., with no extra text or explanation. If you are unsure, make your best estimate."]  
    ) 
    results.append(f"Number of floors in the image: {extract_float_value(number_of_floor_openai)}")

    try:
        if extract_float_value(number_of_floors_app) == extract_float_value(number_of_floor_openai):
            results.append("✅ The number of floors in the application matches with the number of floors in the image.")
        else:
            results.append("❌ The number of floors in the application does not match with the number of floors in the image. Underwriting review required.")
            status = "❌"
    except ValueError:
        results.append("⚠️ Unable to compare the number of floors because one of the values could not be converted to an integer. Underwriting review required.")
        status = "⚠️"
    except TypeError:
        results.append("⚠️ One or both variables are None or not properly defined. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 18 - Number of Floors Verification",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Rule # 19
# ===========================================================================================
print("Rule 19\n----------------------------------------------------")

def verify_dormers(image_path):
    results = []
    status = "✅"
    
    dormers = analyze_image(
        image_path=image_path,  
        question=["Deeply analyze the image and tell does the building in the image(s) have dormers or indicate the presence of an additional floor? (True/False)"]
    )

    if str(dormers).lower().strip() == "true":
        results.append("❌ The building has dormers or indicates the presence of an additional floor. Underwriting review required.")
        status = "❌"
    elif str(dormers).lower().strip() == "false":
        results.append("✅ The building does not have dormers or indicate the presence of an additional floor.")
    else:
        results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 19 - Dormers Verification",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Rule # 20
# ===========================================================================================
print("Rule 20\n----------------------------------------------------")

def verify_construction_type(construction_type_app, image_path):
    results = []
    status = "✅"
    
    has_brick_or_masonry_walls = analyze_image(
        image_path=image_path,  
        question=["Analyze the image(s) deeply and tell does the building in the image(s) have brick or masonry walls? (True/False)"]
    ).strip().lower() 

    if construction_type_app in ('other', 'others'):
        results.append("✅ Construction Type is marked as 'Other' in the application")
    elif construction_type_app == "frame":
        if has_brick_or_masonry_walls == "true":
            results.append("❌ Construction Type is marked as 'Frame', but the building has brick or masonry walls. Underwriting review required.")
            status = "❌"
        elif has_brick_or_masonry_walls == "false":
            results.append("✅ Construction Type is marked as 'Frame', and the building does not have brick or masonry walls.")
        else:
            results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
            status = "⚠️"
    elif construction_type_app == "masonry":
        if has_brick_or_masonry_walls == "true":
            results.append("✅ Construction Type is marked as 'Masonry', and the building has brick or masonry walls.")
        elif has_brick_or_masonry_walls == "false":
            results.append("❌ Construction Type is marked as 'Masonry', but the building does not have brick or masonry walls. Underwriting review required.")
            status = "❌"
        else:
            results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
            status = "⚠️"
    else:
        results.append(f"⚠️ Unexpected Construction Type: '{construction_type_app}'. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 20 - Construction Type Verification",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Rule # 21
# ===========================================================================================
print("Rule 21\n----------------------------------------------------")

def verify_additions(image_path):
    results = []
    status = "✅"
    
    extra_structure = analyze_image( 
        image_path=image_path,
        question=['Return True, if there is any evidence that another building is attached to the building in image(s) by means of a roof, elevated walkway, rigid exterior wall, or stairway. Else return False.']
    )

    if str(extra_structure).lower().strip() == "true":
        results.append("❌ An extra structure is attached to the building structure. Underwriting review required.")
        status = "❌"
    elif str(extra_structure).lower().strip() == "false":
        results.append("✅ The building does not have any extra unit attached to it.")
    else: 
        results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 21 - Additions Verification",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Rule # 22
# ===========================================================================================
print("Rule 22\n----------------------------------------------------")

def verify_diagram5(image_path):
    results = []
    status = "✅"
    
    verify_diagram_ai = analyze_image(
        image_path=image_path,  
        question=["If a building has an elevated floor (like a house on stilts), and the space underneath is open with lattice or slats (not solid walls), then that open area does NOT count as an enclosed space. The building would still be classified as 'Diagram 5' (a type of structure where the lower area is not fully enclosed). Tell me if the building in the image(s) is a 'Diagram 5' structure? Answer only in True/False. (True/False)"]  
    ).strip().lower()   

    if verify_diagram_ai == "true":
        results.append("✅ AI says the building in the image(s) is a 'Diagram 5' structure. Assigning diagram number as '5'.")
    elif verify_diagram_ai == "false":
        results.append("❌ AI says the building in the image(s) is not a 'Diagram 5' structure.")
        status = "❌"
    else:
        results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
        status = "⚠️"
    
    return {
        "rule": "Rule 22 - Diagram 5 Verification",
        "status": status,
        "details": results
    }
# ===========================================================================================
# Rule # 23
# ===========================================================================================
print("Rule 23\n----------------------------------------------------")

def verify_diagram6(diagram_number_app, image_path):
    results = []
    status = "✅"
    
    if str(diagram_number_app).lower().strip() == "5":
        recheck_building_for_diagram = analyze_image(
            image_path=image_path,  
            question=["Analyze the given image(s) deeply and tell is there any evidence of an enclosed elevator shaft? (True/False)"] 
        ).strip().lower()

        if recheck_building_for_diagram == "true":
            results.append("❌ The diagram number is 5, and the building has an enclosed elevator shaft, Assigning diagram number as 6.")
            status = "❌"
        elif recheck_building_for_diagram == "false":
            results.append("✅ The diagram number is 5, and the building does not have an enclosed elevator shaft.")
        else:
            results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
            status = "⚠️"
    else:
        results.append("✅ Diagram number is not 5, rule doesn't apply here.")
    
    return {
        "rule": "Rule 23 - Diagram 6 Verification",
        "status": status,
        "details": results
    }
# ===========================================================================================
# Rule # 24
# ===========================================================================================
print("Rule 24\n----------------------------------------------------")

def verify_machinery(appliances_on_first_floor, foundation_type_app, image_path):
    results = []
    status = "✅"
    
    if str(appliances_on_first_floor).lower().strip() == "no":
        results.append("✅ No appliances are elevated above first floor.")
    elif str(appliances_on_first_floor).lower().strip() == "yes":
        results.append("⚠️ Appliances are elevated above the first floor.")

        appliances_eligibility = ""
        
        if str(foundation_type_app).lower().strip() == "slab on grade" or str(foundation_type_app).lower() == "Slab on Grade (non-elevated)":
            appliances_eligibility = analyze_image(
                image_path=image_path,
                question=["Return True if the given image(s) shows the presence of exterior machine and equipments like 'AC Condenser, Elevator, Generator' elevated atleat to the height of attic in case of single floor, or elevated to atleast within a foot of the height of second or higher floor in case of more than one floor.\n Return False if the given image(s) does not show any exterior machinery or machinery elevated as described above. "] 
            ) 
        elif str(foundation_type_app).lower().strip() == "basement (non-elevated)":
            appliances_eligibility = analyze_image(
                image_path=image_path,
                question=["Return True, if the building in the image(s) shows exterior machinery or equipment elevated to atleast within a foot of the height of the floor above the basement or higher, else return False."]
            )  
        elif str(foundation_type_app).lower().strip() in ["elevated without enclosure on posts", "elevated without enclosure on piles", "elevated without enclosure on piers"]:
            appliances_eligibility = analyze_image(
                image_path=image_path,
                question=["Return True, if the building the image(s) shows exterior machinery elevated elevated to atleast within a foot of the height of the lowest elevated floor or higher, else return False."]
            ) 
        elif str(foundation_type_app).lower().strip() in ["elevated with enclosure on posts", "elevated with enclosure on piles", "elevated with enclosure on piers"]: 
            appliances_eligibility = analyze_image(
                image_path=image_path,
                question=["Return True, if the building the image(s) shows exterior machinery like 'AC Condenser, Elevator, Generator' elevated to atleast within a foot of the height of lowest elevated floor or heigher, else return False."] 
            ).lower().strip()
        elif str(foundation_type_app).lower() in ["elevated with enclosure not posts", "elevated with enclosure not piles", "elevated with enclosure not piers"]:
            appliances_eligibility = analyze_image( 
                image_path=image_path,
                question=["Return True, if the building in the image(s) shows exterior machinery like 'AC Condenser, Elevator, Generator' elevated to atleast within a foot of the height of the lowest elevated floor or higher, else return False."] 
            ) 
        elif str(foundation_type_app).lower() in ["crawlspace", "crawlspace (elevated)", "crawlspace (non-elevated)", "crawlspace (subgrade)", "subgrade crawlspace"]:
            appliances_eligibility = analyze_image(
                image_path=image_path, 
                question=["Return True, if the building in the image(s) shows exterior machinery like 'AC Condenser, Elevator, Generator' elevated to atleast within a foot of the height of the floor above the crawlspace or higher, else return False."] 
            )  

        if str(appliances_eligibility).lower() == "true":
            results.append("✅ Machinery is elevated according to the Rule.")
        elif str(appliances_eligibility).lower() == "false":
            results.append("❌ Machinery is not elevated according to the Rule. Underwriting review required.")
            status = "❌"
        else:
            results.append("⚠️ AI provided an unexpected response. Underwriting review required.")
            status = "⚠️"
    elif not appliances_on_first_floor:
        results.append("⚠️ Appliances are elevated on the first floor field is not filled on the application.")
        status = "⚠️"
    
    return {
        "rule": "Rule 24 - Machinery Verification",
        "status": status,
        "details": results
    }

# ===========================================================================================
# Addtional Things to Consider
# ===========================================================================================
print("\n\nAddtional things to consider\n")

def verify_additional_things(firm_date_app, firm_date_pdf, suffix_app, suffix_pdf, flood_zone_app, flood_zone_pdf):
    results = []
    status = "✅"
    
    if firm_date_app == firm_date_pdf:
        results.append("✅ Firm date is same on both EC and Application.")

        if suffix_app == suffix_pdf:
            if flood_zone_app == flood_zone_pdf: 
                results.append("✅ Flood zones and Suffix are matched on EC and application.")
            elif flood_zone_pdf != flood_zone_app:
                results.append("❌ Suffix matched, but flood zones are different. Assigning the highest priority.")
                status = "⚠️"
                
                if get_priority(flood_zone_app) > get_priority(flood_zone_pdf):
                    results.append(f"Zone defined in application has higher priority (i.e {flood_zone_app} > {flood_zone_pdf})")
                elif get_priority(flood_zone_app) < get_priority(flood_zone_pdf):
                    results.append(f"Zone defined in the pdf has higher priority (i.e {flood_zone_pdf} > {flood_zone_app})")

        elif suffix_app != suffix_pdf:
            if flood_zone_app == flood_zone_pdf:
                results.append("⚠️ Flood Zones matched but Suffix does not match. Underwriting review required.")
                status = "⚠️"
            elif flood_zone_app != flood_zone_pdf:
                results.append("❌ Neither the flood zones matched, nor the suffix matched.")
                status = "❌"

    elif firm_date_app != firm_date_pdf:
        latest_date = get_latest_date(normalize_date_str(firm_date_app), normalize_date_str(firm_date_pdf)) 
        results.append(f"FIRM dates are not matched, reassigning the latest date {latest_date}")
        status = "⚠️"
    
    return {
        "rule": "Additional Things Verification",
        "status": status,
        "details": results
    }


# ===========================================================================================
# Form Validation
# ===========================================================================================
print("\nForm Validation\n")

def form_validation(EC_expiration, survey_date):
    results = []
    status = "✅"
    
    if not EC_expiration:
        results.append("❌ EC expiration date could not be found.")
        status = "❌"
    if not survey_date:
        results.append("❌ Survey date could not be found.")
        status = "❌"

    if EC_expiration and survey_date:
        validation_ranges = [
            ("06-01-1984", "06-30-1984", "09-30-1000", "09-30-2000"),
            ("02-01-1987", "02-28-1987", "09-30-1000", "09-30-2000"),
            ("06-01-1990", "06-30-1990", "09-30-1000", "09-30-2000"),
            ("05-01-1993", "05-31-1993", "09-30-1000", "09-30-2000"),
            ("05-01-1996", "05-31-1996", "09-30-1000", "09-30-2000"),
            ("07-01-1999", "07-31-1999", "09-30-1000", "09-30-2000"),
            ("07-01-2000", "07-31-2000", "08-01-1999", "12-31-2006"),
            ("12-01-2005", "12-31-2005", "01-01-2003", "12-31-2009"),
            ("02-01-2009", "02-28-2009", "02-01-2006", "03-31-2010"),
            ("03-31-2012", "04-01-2012", "04-01-2009", "07-31-2013"),
            ("07-31-2015", "08-01-2015", "08-01-2012", "12-31-2016"),
            ("11-30-2018", "12-01-2018", "01-01-2017", "02-21-2020"),
            ("11-30-2022", "12-01-2022", "02-01-2020", "06-29-2023"),
            ("30-06-2026", "01-07-2026", "01-06-2023", date.today().strftime("%d-%m-%Y")),
        ]

        valid = any(
            is_date_between(EC_expiration, ec_start, ec_end) and
            is_date_between(survey_date, sv_start, sv_end)
            for ec_start, ec_end, sv_start, sv_end in validation_ranges
        )

        if valid:
            results.append("✅ EC is signed on valid date.")
        else:
            results.append("⚠️ Seems like EC is signed on invalid date. Underwriting review required.")
            status = "⚠️"

        try:
            if parser.parse(EC_expiration, dayfirst=True).year < 2003:
                results.append("❌ EC expiration is earlier than 2003. Underwriting review required.")
                status = "❌"
        except Exception as e:
            results.append(f"⚠️ Could not parse EC_expiration for year check: {e}")
            status = "⚠️"

        try:
            if parser.parse(survey_date, dayfirst=True) < parser.parse("01/10/2000", dayfirst=True):
                results.append("❌ Survey date is earlier than 01/10/2000. Underwriting review required.")
                status = "❌"
        except Exception as e:
            results.append(f"⚠️ Could not parse survey_date for cutoff check: {e}")
            status = "⚠️"
    
    return {
        "rule": "Form Validation",
        "status": status,
        "details": results
    }


# CLI execution
if __name__ == "__main__":
    print("Running all comparison rules...")
    results = run_all_comparisons()
    
    if "error" in results:
        print(f"Error: {results['error']}")
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))