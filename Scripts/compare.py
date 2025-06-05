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

    return matches[1] if len(matches) > 1 else default_value  

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





# ------------------------------------------------------------------------------------
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
#---------------------------------------------------------------------------------------

def extract_float_value(value):
    if isinstance(value, (int, float)):  
        return float(value)
    
    match = re.search(r"-?\d+(\.\d+)?", str(value))
    return float(match.group()) if match else 0.0


def normalize_street_name(street_name):
    words = street_name.split()
    return " ".join(STREET_ABBREVIATIONS.get(word, word) for word in words)

# Normalize state names
def normalize_state(state):
    return STATE_ABBREVIATIONS.get(state, state)

# Ensure proper spacing in addresses before parsing
def preprocess_address(address):
    address = re.sub(r'(\d+)([A-Za-z])', r'\1 \2', address)  # Space between numbers & letters
    address = re.sub(r'([A-Za-z])(\d+)', r'\1 \2', address)  # Space between letters & numbers
    address = re.sub(r'[-,]', ' ', address)  # Replace dashes & commas with spaces
    return address.strip()

# Remove all spaces, commas, and dashes after normalization
def clean_address(address):
    return re.sub(r'[\s,-]', '', address).strip().lower()

# Parse and standardize an address
def parse_address(address):
    address = preprocess_address(address)  # Ensure proper spacing
    try:
        parsed = usaddress.tag(address)[0]

        street_number = parsed.get("AddressNumber", "")
        street_name = parsed.get("StreetName", "") + " " + parsed.get("StreetNamePostType", "")
        city = parsed.get("PlaceName", "")
        state = normalize_state(parsed.get("StateName", ""))
        zipcode = parsed.get("ZipCode", "")

        # If parsing fails to detect city/state/zip, extract them manually
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
        return clean_address(address)  # Fallback in case of parsing failure

# Compare two addresses using fuzzy matching
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
        max_tokens=600,
        temperature=0.0
    )

    return response.choices[0].message.content.strip()
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

# Files paths
#---------------------------------------------------------------------------------
with open(r"JSONs\EC.json") as f: 
    data_pdf = json.load(f) 

with open(r"JSONs\application.json") as f: 
    data_app = json.load(f) 
#----------------------------------------------------------------------------------    

street_number_pdf = extract_float_value(search_key(data_pdf, 'Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.'))
street_name_pdf = normalize_string(search_key(data_pdf, "Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.") or search_key(data_pdf, "A2. Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.") or search_key(data_pdf, "A2")) 
city_value_pdf = search_key(data_pdf, 'City') 
state_value_pdf = search_key(data_pdf, 'State')
zipcode_value_pdf = search_key(data_pdf, 'ZIPCode')
address_pdf = str(street_number_pdf) + street_name_pdf + city_value_pdf + state_value_pdf + zipcode_value_pdf  

street_number_app = extract_float_value(search_key(data_app, "Property Address"))
address_app = search_key(data_app, "Property Address") 


print("Rule 1\n----------------------------------------------------")
print(f"Address from PDF: {address_pdf}")
print(f"Address from Application: {address_app}") 

# Compare the normalized values
if street_name_pdf == street_number_app:
    print("Street Number matched on EC and Application.")
else:
    print("Street Number not matched on EC and Application.")

result = compare_addresses(address_pdf, address_app)
print(f"\n{result}\n")
# Diagram Numbers 
print("Rule 2\n----------------------------------------------------")

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

top_of_bottom_floor_app = extract_float_value(search_key(data_app, "Top of Bottom Floor")) 
top_of_next_higher_floor_app = extract_float_value(search_key(data_app, 'Top of Next Higher Floor')) 

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

print(f"PDF diagram number : {diagramNumber_pdf}\nApplication diagram number : {diagram_number_app}\n")

if str(diagram_number_app) == "8":
    if abs(extract_float_value(top_of_bottom_floor_app) - extract_float_value(top_of_next_higher_floor_app)) > 5:
        print("Diagram number on application is 8, but there is more than 5 feet difference between 'Top of bottom floor' and 'Top of next higher floor'.\n Reassigning diagram number as 7")
        diagram_number_app = 7 

if str(diagram_number_app) == "9":
    if (Section_C_LAG_app - top_of_bottom_floor_app) > 2:
        print("Diagram number on application is 9, but there is more than 2 feet difference between 'Top of bottom floor' and the 'LAG'.\n Reassigning diagram number as 2")
        diagram_number_app = 2 

if str(diagram_number_app) == "9":
    if (top_of_bottom_floor_app - top_of_next_higher_floor_app) > 5:
        print("Diagram number on application is 9, but there is more than 5 feet difference between 'Top of bottom floor' and the 'Top of next higher floor'.\n Reassigning diagram number as 2")
        diagram_number_app = 2 

if diagramNumber_pdf and diagram_number_app:
    if str(diagramNumber_pdf).strip()[0] == str(diagram_number_app).strip()[0]:
        print("✅ Diagram Numbers matched.")
    else:
        print("❌ The diagram numbers on the EC and application do not match. Underwriting review required.")
else:
    print("⚠️ The diagram number on the EC is missing. Underwriting review required.")  


# Crawlspace and Garage Square Footage details
print("\nRule 3\n----------------------------------------------------")

def get_value_by_normalized_key(data, target_keys):
    if not isinstance(data, dict):
        return 0.0
    
    normalized_data_keys = {normalize_string(k): k for k in data.keys()}
    
    for target in target_keys:
        norm_target = normalize_string(target)
        if norm_target in normalized_data_keys:
            return data[normalized_data_keys[norm_target]]
    
    return 0.0

crawlspace_details_v1 = search_key(data_pdf, 'CrawlspaceDetails') 
crawlspace_details_v2 = search_key(data_pdf, 'Crawlspace') 
crawlspace_details_v3 = search_key(data_pdf, 'for a building with crawlspace or enclosure(s)') 

lookup_keys = ["SquareFootage", "square footage of crawlspace or enclosure(s)", "a) Square footage of crawlspace or enclosure(s)", "A8. For a building with a crawlspace or enclosure(s): a) Square footage of crawlspace or enclosure(s)"] 

if isinstance(crawlspace_details_v1, (int, float)):
    crawlspace_square_footage = extract_float_value(crawlspace_details_v1)
elif isinstance(crawlspace_details_v2, (int, float)):
    crawlspace_square_footage = extract_float_value(crawlspace_details_v2)
elif isinstance(crawlspace_details_v3, (int, float)):
    crawlspace_square_footage = extract_float_value(crawlspace_details_v3)
else:
    crawlspace_square_footage = (
        extract_float_value(get_value_by_normalized_key(crawlspace_details_v1, lookup_keys)) or
        extract_float_value(get_value_by_normalized_key(crawlspace_details_v2, lookup_keys)) or
        extract_float_value(get_value_by_normalized_key(crawlspace_details_v3, lookup_keys)) or
        0.0
    )

garage_details_v1 = search_key(data_pdf, 'GarageDetails')
garage_details_v2 = search_key(data_pdf, 'Garage')
garage_details_v3 = search_key(data_pdf, 'for a building with attached garage')

garage_square_footage = extract_float_value(get_value_by_normalized_key(garage_details_v1, lookup_keys ) or extract_float_value(get_value_by_normalized_key(garage_details_v2, lookup_keys )) or extract_float_value(get_value_by_normalized_key(garage_details_v3, lookup_keys )) or 0.0)


enclosure_Size = extract_float_value(search_key(data_app, "Enclosure/Crawlspace Size"))

total_square_footage = crawlspace_square_footage + garage_square_footage
diagram_no_choices = ['6', '7', '8', '9']  

if diagramNumber_pdf in diagram_no_choices: 

    if total_square_footage == enclosure_Size:
        print(f"Diagram Number is among {', '.join(map(str, diagram_no_choices))}. and Crawlspace and Garage square footage '{crawlspace_square_footage + garage_square_footage}' is aligned with Total Enclosure size '{enclosure_Size}' in the application. ✅")
    else:
        print("The square footage of the enclosure(s) on the EC doesn't match the application. Underwriting review required ❌") 
else:
    print(f"Diagram Number is not among {', '.join(map(str, diagram_no_choices))}. so no comparison is required. ✅")


# Searching for CBRS/OPA details  cbrsSystemUnitOrOpa 
print("\nRule 4\n----------------------------------------------------")
CBRS = search_key(data_pdf, 'CBRS') or search_key(data_pdf,"CBRSDesignation")
OPA = search_key(data_pdf, 'OPA') or search_key(data_pdf, 'OPADesignation')  
CBRS_OPA_app = search_key(data_app, 'Building Located In CBRS/OPA') 

if str(CBRS_OPA_app).lower() != str(CBRS).lower() or str(CBRS_OPA_app).lower() != str(OPA).lower():
    print("CBRS/OPA details do not match. ❌") 
else:
    print("CBRS/OPA details matched with the application. ✅") 

if str(CBRS).lower() == "yes" or str(OPA).lower() == "yes":
    print("Area in CBRS/OPA, Additional Documentation Required.")
else:
    print("Area not in CBRS/OPA, Additional Documentation Not Required.\n")

# Rule 5
#----------------------------------------------------------------------------------
print("Rule 5\n----------------------------------------------------")
Construction_status_pdf_V1 = search_key(data_pdf, 'Building elevations are based on') or search_key(data_pdf, "BuildingElevationsSource") 
Construction_status_app = search_key(data_app, 'Building in Course of Construction') # no / yes 

if normalize_string(Construction_status_pdf_V1) == "finishedconstruction" and Construction_status_app.lower() == "yes":
    print("Construction Status mismatched. Confirm the construction status of the building. ❌")  

elif normalize_string(Construction_status_pdf_V1) == "finishedconstruction" and Construction_status_app.lower() == "no":
    print("Construction Status matched on EC and Application. ✅") 

elif normalize_string(Construction_status_pdf_V1) == "buildingunderconstruction" and  Construction_status_app.lower() == "yes":
    print("Construction Status matched on EC and Application. ✅") 

if (normalize_string(Construction_status_pdf_V1) in ["constructiondrawings", "buildingunderconstruction", "underconstruction"] 
    and Construction_status_app.lower() == "yes"):
    print("A finished construction EC is required.")



# Rule 6 
#----------------------------------------------------------------------------------
print("Rule 6\n----------------------------------------------------")

certifier_name_pdf_v1 = search_key(data_pdf, "Certifier's Name") or search_key(data_pdf, "Certifier Name") or search_key(data_pdf, "CertificateName")
certifier_license_number = search_key(data_pdf, "License Number") 

try:
    Section_C_FirstFloor_Height_app = float(search_key(data_app, 'ecSectionCFirstFloorHeight'))
except (ValueError, TypeError):
    Section_C_FirstFloor_Height_app = 0 


try:
    Section_C_Lowest_Floor_Elevation_app = float(search_key(data_app, 'ecSectionCLowestFloorElevation'))
except (ValueError, TypeError):
    Section_C_Lowest_Floor_Elevation_app = 0

section_c_measurements_used = False 
Elevation_Certificate_Section_Used = search_key(data_app, "Elevation Certificate Section Used") 

if "c" in Elevation_Certificate_Section_Used.lower():
    section_c_measurements_used = True  
    print("Section C measurements are used in the application. ✅\n")
else:
    print("Section C measurements are not used in the application. ❌\n") 

if section_c_measurements_used:
    if certifier_name_pdf_v1:
        print(f"Certifier name: '{certifier_name_pdf_v1}' is present on EC. ✅ ")
    else:
        print("Please review. Certifier name is not present on EC. ❌") 
    
    if certifier_license_number:
        print(f"Certifier's License number: '{certifier_license_number}' is present on EC. ✅\n")
    else:
        print("Please Review. Certifier's License number is not present on EC. ❌\n") 


# Rule 7 - Elevation Logic 
#----------------------------------------------------------------------------------
print("Rule 7\n----------------------------------------------------")

section_C = search_key(data_pdf, 'Section C') 
top_of_bottom_floor_pdf = extract_float_value(search_key(section_C, 'Top of Bottom Floor')) 
top_of_bottom_floor_app = extract_float_value(search_key(data_app, "Top of Bottom Floor")) 
top_of_next_higher_floor_pdf = extract_float_value(search_key(section_C, 'Top of Next Higher Floor')) 
LAG_pdf = extract_float_value(search_key(section_C, 'Lowest Adjacent Grade (LAG) next to building')) 
LAG_app = extract_float_value(search_key(data_app, 'Lowest Adjacent Grade (LAG)')) 
HAG_pdf = extract_float_value(search_key(section_C, 'Highest Adjacent Grade') or search_key(section_C, "Highest Adjacent Grade (HAG)"))     

# New condition implemented: HAG >= LAG
if HAG_pdf < LAG_pdf:
    print("The EC elevation of the HAG is lower than the LAG. Underwriting review required. ❌")
else:
    print("The EC elevation of the HAG is higher than the LAG. ✅")

diagram_choices_1 = ['1', '1a', '3', '6', '7', '8']
diagram_choices_2 = '1b'
diagram_choices_3 = ['2', '2a', '2b', '4', '9']
diagram_choices_4 = '5' 
diagram_choices_5 = ['2', '2a', '2b', '4', '6', '7', '8', '9']

if section_c_measurements_used:
    if top_of_bottom_floor_pdf == top_of_bottom_floor_app:
        print("Top of bottom floor is matched on EC and Application. ✅")
    else:
        print("Please review. Top of bottom floor is not matched on EC and Application. ❌") 
    
    if top_of_next_higher_floor_app == top_of_next_higher_floor_pdf:
        print("Top of next higher floor is matched on EC and Application. ✅")
    else:
        print("Please review. Top of next higher floor is not matched on EC and Application. ❌") 

    if LAG_app == LAG_pdf:
        print("Lowest Adjacent Grade (LAG) is matched on EC and Application. ✅")
    else:
        print("Please review. Lowest Adjacent Grade (LAG) is not matched on EC and Application. ❌")

# LAG_pdf <= top_of_bottom_floor_pdf <= LAG_pdf + 2 
    if str(diagramNumber_pdf).lower() in diagram_choices_1:   
        if top_of_bottom_floor_pdf < LAG_pdf + 2: 
            print(f"\nElevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅") 
        else:
            print(f"Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")

        if top_of_bottom_floor_pdf >= LAG_pdf:
            print("Elevation Logic matched. Top of bottom floor is greater than LAG. ✅")
        else:
            print("Please review the foundation system as the top of bottom floor is less than the LAG. ❌")

    elif str(diagramNumber_pdf).lower() == diagram_choices_2:  
        if LAG_pdf <= top_of_bottom_floor_pdf < LAG_pdf + 6:
            print(f"Elevation Logic matched. The top of bottom floor is within 6 feet of the LAG. ✅") 
        else:
            print(f"Please review stem-wall foundation system as the top of bottom floor is not within 6 feet of the LAG. ❌")

    elif str(diagramNumber_pdf).lower() in diagram_choices_3:
        if top_of_bottom_floor_pdf < LAG_pdf:
            print(f"Elevation Logic matched. The top of bottom floor is below the LAG. ✅") 
        else:
            print(f"Please verify the building foundation as the top of bottom floor is not below the LAG. ❌\n") 

# <= (LAG_pdf + 20):
    elif str(diagramNumber_pdf).lower() in diagram_choices_4:
        if LAG_pdf <= top_of_bottom_floor_pdf:
            print(f"Elevation Logic matched. The top of bottom floor elevation is above the LAG for this Diagram 5 building. ✅")
        else:
            print(f"Please verify foundation system. The top of bottom floor elevation is below the LAG for this Diagram 5 building. ❌")
        
        if top_of_bottom_floor_pdf <= (LAG_pdf + 20):
            print("Elevation Logic matched. Top of bottom floor is below 20 feet of LAG. ✅") 
        else:
            print("Please review elevations and photographs as there is more than 20 foot difference between C2a and the LAG. ❌")

    if str(diagramNumber_pdf).lower() in diagram_choices_5:
        if top_of_next_higher_floor_pdf and top_of_next_higher_floor_pdf > top_of_bottom_floor_pdf:
            print(f"Elevation Logic matched. The C2b elevation is not lower than the C2a elevation. ✅")
        else: 
            print(f"Underwriting review required. The C2b elevation is lower than the C2a elevation. ❌") 
    
    # top of bottom floor = C2a || top of next higher floor = C2b
    if abs(LAG_pdf-top_of_bottom_floor_pdf) > 20: 
        print("There is more than a 20 foot difference between C2a and the LAG. Review of photographs required. ❌")
    else:
        print("E: LAG and C2a difference is smaller than 20\nPassed -> No underwriter review required. ✅")

    if abs(LAG_pdf-top_of_next_higher_floor_pdf) > 20:
        print("Please review elevations and photographs as there is more than 20 foot difference between the LAG and Next Higher Floor. ❌") 
    else:
        print("E: LAG and C2b difference is smaller than 20\nPassed -> No underwriter review required. ✅") 


# Section E measurements used
print("\nRule 8\n----------------------------------------------------")
section_e_measurements_used = False 

if "e" in Elevation_Certificate_Section_Used.lower():
    section_e_measurements_used = True
    print("Section E measurements are used in the application. ✅\n")
else:
    print("Section E measurements are not used in the application. ❌\n") 

section_E = search_key(data_pdf, 'Section E') 
e1a = extract_float_value(search_key(section_E, 'Top of Bottom Floor') or search_key(section_E, 'Top of Bottom Floor (including basement, crawlspace, or enclosure) is'))  
e1b = extract_float_value(search_second_key(section_E, 'Top of Bottom Floor') or search_key(section_E, 'Top of Bottom Floor (including basement, crawlspace, or enclosure) is')) 
e2 = extract_float_value(search_key(section_E, 'Top of Next Higher Floor')) or extract_float_value(search_key(section_E, 'Top of Next Higher Floor (elevation C2.b in the diagrams) of the building is')) 

diagram_choices_6 = ["1", "1a", "3", "6", "7", "8"]
diagram_choices_7 = "1b"
diagram_choices_8 = "5" 
diagram_choices_9 = ["2", "2a", "2b", "4", "9"]
diagram_choices_10 = ["6", "7", "8", "9"] 

if section_e_measurements_used:
    if abs(e1b) == abs(top_of_bottom_floor_app): 
        print("EC Top of Bottom Floor matches with the Application. ✅")
    else:
        print("The Top of Bottom Floor elevation in Section E of the EC doesn't match the application. Underwriting review required. ❌") 

    if diagramNumber_pdf.lower() in diagram_choices_6:
        if e1b < LAG_pdf + 2:
            print(f"Elevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅") 
        else:
            print(f"Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")  

        if e1b >= LAG_pdf:
            print("Elevation Logic matched. The top of bottom floor is greater than the LAG. ✅")
        else:
            print("Please review foundation system as the top of bottom floor is less than the LAG. ❌")

# LAG_pdf <= e1b <= LAG_pdf + 6
    elif diagramNumber_pdf.lower() == diagram_choices_7:  
        if e1b <= LAG_pdf + 6:
            print(f"\nElevation Logic matched. The elevation is within 6 feet of LAG. ✅")
        else:
            print(f"E1b: Please Review, The elevation is not be within 6 feet of LAG. ❌")

        if e1b >= LAG_pdf:
            print("Elevation Logic matched. The e1b elevation is greater than LAG. ✅")
        else:
            print("Please Review, the e1b elevation is lower than LAG. ❌")

# LAG_pdf <= e1b <= (LAG_pdf + 20)
    elif str(diagramNumber_pdf).lower() in diagram_choices_8:
        if e1b <= (LAG_pdf + 20):
            print(f"Elevation Logic matched. e1b is lower than 20 feet of LAG. ✅")
        else: 
            print(f"Please review elevations and photographs as there is more than 20 foot difference between the E1b elevation and the LAG. ❌")  

        if e1b >= LAG_pdf:
            print("Elevation Logic matched. The e1b elevation is greater than the LAG. ✅")
        else:
            print("The top of bottom floor elevation is below the LAG for this Diagram 5 building. Please verify foundation system. ❌") 

    elif str(diagramNumber_pdf).lower() in diagram_choices_9:
        if e1b < LAG_pdf: 
            print(f"The top of bottom floor is above the LAG. Elevation Logic matched. ✅") 
        else:
            print(f"Please review the foundation system as the top of bottom floor is not below the LAG. ❌") 

    if str(diagramNumber_pdf).lower() in diagram_choices_10:
        if not e2:
            print("Please review the elevation certificate as the E2 elevation is not present. ❌")

        if e2 > e1a: 
            print(f"E2 is higher than E1b. Elevation Logic matched. ✅")  
        else:
            print(f"Please review the elevation certificate as E2 is less than E1b. ❌")

    if e1a > 20 or e1b > 20 or e2 > 20:  
        print("Please review elevations and photographs as there is more than 20 foot difference in Section E. ❌")
    else:
        print("E: E1a, E1b, and E2 are smaller than 20\nPassed -> No underwriter review required. ✅")


# Section H 
#------------------------------------------------------------------------------- 
print("Rule 9 - Section H\n----------------------------------------------------")

if Elevation_Certificate_Section_Used.lower() == "h":
    print("Section H measurements are used in the application. ✅\n")

    section_H_in_pdf = search_key(data_pdf, 'Section H')
    h1a_top_of_bottom_floor = extract_float_value(search_key(section_H_in_pdf, 'Top of Bottom Floor'))
    h1b_top_of_next_higher_floor = extract_float_value(search_key(section_H_in_pdf, 'Top of Next Higher Floor')) 

    diagram_choices_11 = ['1', '1a', '3', '6', '7','8']
    diagram_choices_12 = ['2', '2a', '2b', '4', '9']
    diagram_choices_13 = ['2', '2a', '2b', '4', '6', '7', '8', '9']

    # LAG_pdf <= h1a_top_of_bottom_floor <= LAG_pdf + 2
    if diagramNumber_pdf.lower() in diagram_choices_11:
        if h1a_top_of_bottom_floor <= LAG_pdf + 2:
            print(f"Elevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅")
        else:   
            print("Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")

        if h1a_top_of_bottom_floor >= LAG_pdf:
            print("Elevation Logic matched. The top of bottom floor is greater than the LAG. ✅")
        else:
            print("Please review foundation system as the top of bottom floor is less than the LAG. ❌")

    elif diagramNumber_pdf.lower() == '1b':
        if LAG_pdf <= h1a_top_of_bottom_floor:
            print(f"H1a: For diagram no. '1b' The elevation is above the LAG. Elevation Logic matched. ✅")
        else:
            print(f"Please review the foundation system as the top of bottom floor is below the LAG. ❌")

        if h1a_top_of_bottom_floor < LAG_pdf + 6:
            print("The top of bottom floor is within 6 feet of the LAG. ✅")
        else:
            print("Please review the foundation system as the top of bottom floor is not within 6 feet of the LAG. ❌")

    elif diagramNumber_pdf.lower() in diagram_choices_12:
        if LAG_pdf > h1a_top_of_bottom_floor:
            print(f"Top of bottom floor is below the LAG. Elevation Logic matched. ✅")
        else:
            print(f"Please review foundation system as the top of bottom floor is at or above the LAG. ❌")

    elif diagramNumber_pdf.lower() == '5':
        if h1a_top_of_bottom_floor <= (LAG_pdf + 20):
            print(f"there is not more than a 20 foot difference between H1a and the LAG. Elevation Logic matched. ✅")  
        else: 
            print(f"Please review elevations and photographs as there is more than a 20 foot difference between H1a and the LAG. ❌")

        if LAG_pdf <= h1a_top_of_bottom_floor:
            print("H1a elevation is above the LAG. Elevation Logic matched. ✅")
        else:
            print("Please review. The H1a elevation is below the LAG. ❌") 

    if diagramNumber_pdf.lower() in diagram_choices_13:
        # the next higher floor should be present, and it should be greater than top of bottom floor 
        if h1b_top_of_next_higher_floor: 
            print(f"H1b is present on EC. ✅") 
        else:
            print(f"Underwriting review required as H1b is missing from the EC. ❌") 

        if h1b_top_of_next_higher_floor > h1a_top_of_bottom_floor:
            print("H1b > H1a. Elevation Logic matched. ✅") 
        else:
            print("Underwriting review required as H1b <= H1a. ❌")

        if h1a_top_of_bottom_floor > 20 or h1b_top_of_next_higher_floor > 20:
            print("Please review elevations and photographs as there is more than a 20 foot difference described in Section H. ❌")
        else:
            print("E: H1a and H1b are smaller than 20.\nPassed -> No underwriter review required. ✅") 


#----------------------------------------------------------------
print("\nRule 10\n----------------------------------------------------")

machinery = search_key(data_app, 'Is all machinery and equipment servicing the building, located inside or outside the building, elevated above the first floor') or search_key(data_app, 'Machinery or Equipment Above') or search_key(data_app, "the building, located inside or outside the building, elevated above the first floor") or search_key(data_app, "building, elevated above the first floor") 

c2e_elevation_of_mahinery = extract_float_value(search_key(data_pdf, 'Lowest elevation of Machinery and Equipment (M&E) servicing the building (describe type of M&E and location in section D comments area)'))
e4_top_of_platform = extract_float_value(search_key(data_pdf, 'Top of platform of machinery and/or equipment servicing the building is') or search_key(data_pdf, 'Top of platform of machinery and/or equipment'))

h2 = search_key(data_pdf, "Machinery and Equipment (M&E) servicing the building") or search_key(data_pdf, "Machinery and Equipment servicing the building") 

e2 = extract_float_value(search_key(data_pdf, "for building diagrams 6-9 with permanent flood openings provided in section A items B and/or  9 (see pages 1-2 of instructions), the next higher floor (c2.b in applicable building diagram) of the building is") or search_key(data_pdf , "Next higher floor"))   

diagram_choices_14 = ['1', '1a', '1b', '3']
diagram_choices_15 = ['2', '2a', '2b', '4', '6', '7', '8', '9'] 

if machinery:
    print("Machinery or Equipment Above is present in the application. ✅\n")  

    if str(diagramNumber_pdf).lower() in diagram_choices_14: 
        if top_of_next_higher_floor_pdf:
            if c2e_elevation_of_mahinery >= top_of_next_higher_floor_pdf:
                print("Elevation Logic matched. The M&E elevation on the EC support the M&E mitigation discount. ✅")
            else:
                print("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required. ❌") 
        
        elif not top_of_next_higher_floor_pdf:
            if c2e_elevation_of_mahinery >= top_of_bottom_floor_pdf + 8:
                print("Elevation of machinery is higher than 8 feet of top of bottom floor. Elevation Logic matched. ✅") 
            else:
                print("Elevation of machinery is not higher than 8 feet of top of bottom floor. The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.❌")
        
        if e4_top_of_platform >= e1b + 8:
            print(f"For diagrams '{', '.join(map(str, diagram_choices_14))}' The top of platform of machinery and/or equipment servicing the building should be at least 8 feet higher than the top of bottom floor.\nTop of platform: {e4_top_of_platform}\nTop of bottom floor: {e1b}\nElevation Logic matched. ✅")
        else:
            print("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required. ❌") 

        if h2.lower() == "yes":
            print("H2 is marked as 'Yes' in the EC\n")
        
        elif h2.lower() == "no":
            print("Section H2 of the EC does not appear to support the M&E mitigation discount. Underwriting review required.")

        else:
            print("H2 is not marked in the EC\n")

    elif str(diagramNumber_pdf).lower() in diagram_choices_15:

        if c2e_elevation_of_mahinery >= top_of_next_higher_floor_pdf:
            print("The elevation of machinery is higher than top of next higher floor. Elevation Logic matched. ✅") 
        else:
            print("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.") 
        
        if e4_top_of_platform >= e2:
            print(f"Top of platform of machinery is higher than E2. Elevation Logic matched. ✅") 
        else:
            print("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.") 

        if h2.lower() == "yes":
            print("H2 is marked as 'Yes' in the EC\n")
        
        elif h2.lower() == "no":
            print("H2 is marked as 'No' in the EC\n")

        else:
            print("H2 is not marked in the EC\n")

    elif str(diagramNumber_pdf).lower() == '5':
        if c2e_elevation_of_mahinery >= top_of_bottom_floor_pdf:
            print(f"For diagrams '5' The elevation of machinery and equipment should be equal or greater than the top of bottom floor.\nElevation of machinery and equipment: {c2e_elevation_of_mahinery}\nTop of bottom floor: {top_of_bottom_floor_pdf}\nElevation Logic matched.\n") 
        else:
            print("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.") 
        
        if e4_top_of_platform >= e1b:
            print("Top of platform of machinery is higher than E1b. Elevation Logic matched. ✅")
        else:
            print("The M&E elevation on the EC does not appear to support the M&E mitigation discount. Underwriting review required.") 

        if h2.lower() == "yes":
            print("H2 is marked as 'Yes' in the EC.\n")
        
        elif h2.lower() == "no":
            print("Section H2 of the EC does not appear to support the M&E mitigation discount.  Underwriting review required.\n")

        else:
            print("H2 is marked as 'Yes' in the EC.\n")

else:
    print("Machinery or Equipment Above is not present in the application.\n") 

# Rule 11 -------------------------------------------------------------------------------------------------------
print("\nRule 11\n----------------------------------------------------") 
# diagram_choices_10 = ["6", "7", "8", "9"] 

# A8 vents
A8_non_engineered_flood_openings_pdf_v1 = extract_float_value(search_key(data_pdf, 'Non-Engineered Flood Openings'))
A8_non_engineered_flood_openings_pdf_v2 = extract_float_value(search_key(data_pdf, 'Non-Engineered'))
A8_engineered_flood_openings_pdf_v1 = extract_float_value(search_key(data_pdf, 'Engineered Flood Openings') or search_key(data_pdf, "d) Engineered flood openings?"))  
A8_engineered_flood_openings_pdf_v2 = extract_float_value(search_key(data_pdf, 'Engineered'))
A8_flood_openings_pdf_v3 = extract_float_value(search_key(data_pdf, 'Number of permanent flood openings in the crawlspace'))
A8_old_flood_openings_pdf_v4 = extract_float_value(search_key(data_pdf, 'Number of permanent flood openings in the crawlspace or enclosures within 1.0 foot above adjacent grade'))
A8_much_older_flood_openings_pdf_v5 = extract_float_value(search_key(data_pdf, 'No. of permanent openings (flood vents) within 1 ft. above adjacent grade'))

A8_flood_openings_pdf = ((A8_non_engineered_flood_openings_pdf_v1 or A8_non_engineered_flood_openings_pdf_v2) + (A8_engineered_flood_openings_pdf_v1 or A8_engineered_flood_openings_pdf_v2)) or A8_flood_openings_pdf_v3 or A8_old_flood_openings_pdf_v4 or A8_much_older_flood_openings_pdf_v5

# Area of A8
A8_total_vents_area_pdf_v1 = extract_float_value(search_key(data_pdf, "Total net open area of non-engineered flood openings in A8.c"))
A8_total_vents_area_pdf_v2 = extract_float_value(search_key(data_pdf, "Total net area of flood openings in A8.b") or search_key(data_pdf, "c) Total net area of flood openings in A8.b"))  
A8_total_vents_area_pdf_v3 = extract_float_value(search_key(data_pdf, "Total area of all permanent openings (flood vents) in C3h"))  
A8_total_vents_area_pdf_v4 = extract_float_value(search_key(data_pdf, "Total net open area of non-engineered flood openings"))

A8_total_area = A8_total_vents_area_pdf_v1 or A8_total_vents_area_pdf_v2 or A8_total_vents_area_pdf_v3 or A8_total_vents_area_pdf_v4 

# A9 vents
A9_non_engineered_flood_openings_pdf_v1 = extract_float_value(search_second_key(data_pdf, 'Non-Engineered Flood Openings'))
A9_non_engineered_flood_openings_pdf_v2 = extract_float_value(search_second_key(data_pdf, 'Non-Engineered'))
A9_engineered_flood_openings_pdf_v1 = extract_float_value(search_second_key(data_pdf, 'Engineered Flood Openings') or search_key(data_pdf, "Has Engineered Openings:"))  
A9_engineered_flood_openings_pdf_v2 = extract_float_value(search_second_key(data_pdf, 'Engineered'))
A9_flood_openings_pdf_v3 = extract_float_value(search_second_key(data_pdf, 'Number of permanent flood openings in the crawlspace')) 
A9_old_flood_openings_pdf_v4 = extract_float_value(search_second_key(data_pdf, 'Number of permanent flood openings in the crawlspace or enclosures within 1.0 foot above adjacent grade'))
A9_much_older_flood_openings_pdf_v5 = extract_float_value(search_second_key(data_pdf, 'No. of permanent openings (flood vents) within 1 ft. above adjacent grade'))

A9_flood_openings_pdf = ((A9_non_engineered_flood_openings_pdf_v1 or A9_non_engineered_flood_openings_pdf_v2) + (A9_engineered_flood_openings_pdf_v1 or A9_engineered_flood_openings_pdf_v2)) or A9_flood_openings_pdf_v3 or A9_old_flood_openings_pdf_v4 or A9_much_older_flood_openings_pdf_v5

# Area of A9
A9_total_vents_area_pdf_v1 = extract_float_value(search_second_key(data_pdf, "Total net open area of non-engineered flood openings in A9.c"))
A9_total_vents_area_pdf_v2 = extract_float_value(search_second_key(data_pdf, "Total net area of flood openings in A9.b")) 
A9_total_vents_area_pdf_v3 = extract_float_value(search_second_key(data_pdf, "Total area of all permanent openings (flood vents) in C3h"))
A9_total_vents_area_pdf_v4 = extract_float_value(search_second_key(data_pdf, "Total net open area of non-engineered flood openings"))

A9_total_area = A9_total_vents_area_pdf_v1 or A9_total_vents_area_pdf_v2 or A9_total_vents_area_pdf_v3 or A9_total_vents_area_pdf_v4

# total number of opening -> A8_openings + A9_openings
total_number_of_openings = A8_flood_openings_pdf + A9_flood_openings_pdf

# total area of openings -> A8_area + A9_area
total_area_of_openings =  A8_total_area + A9_total_area 

# getting vents number and area from the application
number_of_flood_openings_app = extract_float_value(search_key(data_app, 'numberOfFloodOpenings'))
area_of_flood_openings_app = extract_float_value(search_key(data_app, "totalAreaFloodOpenings"))

if str(diagramNumber_pdf).lower() in diagram_choices_10:
    print(f"Diagram Number is among '{', '.join(map(str, diagram_choices_10))}'.\n")  
    if total_number_of_openings == number_of_flood_openings_app:
        print("Total number of vents on the EC (Sections A8 + A9) matches with the application.")
    else:
        print("Please Review. Total number of vents on the EC (Sections A8 + A9) does not match with the application.")
    
    if total_area_of_openings == area_of_flood_openings_app:
        print("Total area of vents on the EC (Sections A8 + A9) matches with the application.\n")
    else:
        print("Please Review. Total area of vents on the EC (Sections A8 + A9) does not match with the application.\n") 
else:
    print(f"Diagram Number is not among '{', '.join(map(str, diagram_choices_10))}'.\n")




# ========================================================================================
# Rule # 12
# ========================================================================================
print("Rule 12\n----------------------------------------------------")

image_path = [r"Images\1.png"]  

if Construction_status_app.lower() == "yes":
    print("Building underconstruction. Photographs are not required.\n")
else:
    print("Building is not underconstruction. Photographs are required.\n")


# ============================================================================================
# Rule # 13
# ============================================================================================
print("Rule 13\n----------------------------------------------------")
building_eligibility = analyze_image(
    image_path=image_path,  
    question=["The building in the image(s) is affixed to a permanent site, and has two or more outside rigid walls with a fully secured roof? (True/False)"]
)

if str(building_eligibility).lower() == "true":
    print("✅ The building is affixed to a permanent site, has two or more outside rigid walls, and a fully secured roof. \n")
else:
    print("❌ The building is not affixed to a permanent site, does not have two or more outside rigid walls, or does not have a fully secured roof. Underwriting review required.\n")


# ===========================================================================================
# Rule # 14 
# ===========================================================================================
print("Rule 14\n----------------------------------------------------")

occupancy_type_app = search_key(data_app, "Occupancy Type") 
print(f"Occupancy type in Application: {occupancy_type_app}")

occupancy_type_ec = search_key(data_pdf, "Building Occupancy") 
print(f"Occupancy type in EC: {occupancy_type_ec}\n") 

if occupancy_type_app == occupancy_type_ec:
    print(f"✅ Occupancy Type matches on EC and Application.\n")
else:
    print("❌ Please review. Occupancy Type does not match on EC and Application.\n") 


if occupancy_type_app.lower() == "residential" or occupancy_type_ec.lower() == "non-residential" or occupancy_type_ec.lower() =="other residential" or occupancy_type_ec.lower() == "residential condominium building" or occupancy_type_ec.lower() == "two-four family":
    result = analyze_image(
        image_path=image_path,  
        question=["The building in the image(s) has multi-unit structures? (True/False)"]
    ) 

    if str(result).lower() == "true": 
        print("✅ The building is a residential / non-residential unit, two-four family, Other Residential, or residential 	condominium building, and has a multi-unit structure. \n") 
    elif str(result).lower() == "false":
        print("❌ The building is a residential / non-residential unit, two-four family, Other Residential, or residential condominium building, but does not have a multi-unit structure. Underwriting review required.\n")
    else:
        print("❌ Ai provided an unexpected response. Underwriting review required.\n") 
else:
    print("⚠️ The occupancy type is not Residential, Non-Residential, Other Residential, or Residential Condominium Building, or Two-Four Family. Underwriting review required.\n")

# ===========================================================================================
# Rule # 15
# ===========================================================================================
print("Rule 15\n----------------------------------------------------")

image_path = [r"Images\2.png"]
under_water = analyze_image(
    image_path=image_path,  
    question=["Some part of the building or entire building in the image(s) is over water? (True/False)"]
) 

if str(under_water).lower() == "true":
    print("❌ The building is over water. Underwriting review required.\n") 
elif str(under_water).lower() == "false":
    print("✅ The building is not over water. \n")
else:
    print("⚠️ Ai provided an unexpected response. Underwriting review required.\n")


# ===========================================================================================
# Rule # 16
# ===========================================================================================
print("Rule 16\n----------------------------------------------------")

foundation_eligibility = analyze_image(
    image_path=image_path,  
    question=["Does the building in the image(s) show the 'front' and 'back' of the building, including the 'foundation system' and are the 'number of floors' visible clearly? (True/False)"] 
)  

if str(foundation_eligibility).lower() == "true":
    print("✅ The building in the image(s) shows the 'front' or 'back' of the building, including the 'foundation system' and the 'number of floors' are visible clearly. \n")
elif str(foundation_eligibility).lower() == "false":
    print("❌ The building in the image(s) does not show one of the 'front' and 'back' of the building, or the 'foundation system' or the 'number of floors' are not visible clearly. Underwriting review required.\n") 
else:
    print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 


# ===========================================================================================
# Rule # 17
# ===========================================================================================
print("Rule 17\n----------------------------------------------------")

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

print(f"Foundation type in the application: {foundation_type}")
print(f"Foundation type in the image (by Ai): {foundation_type_ai}\n")

if foundation_type.lower() == str(foundation_type_ai).strip().lower(): 
    print(f"✅ The foundation type in the application matches with the foundation type in the image.\n")
else:
    print(f"❌ The foundation type in the application does not match with the foundation type in the image. Underwriting review required.\n") 


# ===========================================================================================
# Rule # 18
# ===========================================================================================
print("Rule 18\n----------------------------------------------------")

result = search_key(data_app, "Total # of floors in building")
number_of_floors_app = result if result != '' else "0"

print(f"Number of floors in the application: {number_of_floors_app}")

number_of_floor_openai = analyze_image(
    image_path=image_path,  
    question=["Count the number of floors in the building visible in the image(s). do not count mid-level entries, enclosures, basements, or crawlspaces (on grade or subgrade) as a floor. Respond with only a single integer like 1, 2, 3, etc., with no extra text or explanation. If you are unsure, make your best estimate."]  
) 
print(f"Number of floors in the image: {extract_float_value(number_of_floor_openai)}\n") 

try:
    if extract_float_value(number_of_floors_app) == extract_float_value(number_of_floor_openai):
        print("✅ The number of floors in the application matches with the number of floors in the image.\n")
    else:
        print("❌ The number of floors in the application does not match with the number of floors in the image. Underwriting review required.\n")

except ValueError:
    print("⚠️ Unable to compare the number of floors because one of the values could not be converted to an integer. Underwriting review required.\n") 
    
except TypeError:
    print("⚠️ One or both variables are None or not properly defined. Underwriting review required.\n")


# ===========================================================================================
# Rule # 19
# ===========================================================================================
print("Rule 19\n----------------------------------------------------")

dormers = analyze_image(
    image_path=image_path,  
    question=["Deeply analyze the image and tell does the building in the image(s) have dormers or indicate the presence of an additional floor? (True/False)"]
)

if dormers.lower() == "true":
    print("❌ The building has dormers or indicates the presence of an additional floor. Underwriting review required.\n")
elif dormers.lower() == "false":
    print("✅ The building does not have dormers or indicate the presence of an additional floor. \n")
else:
    print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 


# ===========================================================================================
# Rule # 20
# ===========================================================================================
print("Rule 20\n----------------------------------------------------")

construction_type_app = str(search_key(data_app, "Building Construction Type") or search_key(data_app, "Construction Type")).strip().lower()
has_brick_or_masonry_walls = analyze_image(
    image_path=image_path,  
    question=["Analyze the image(s) deeply and tell does the building in the image(s) have brick or masonry walls? (True/False)"]
).strip().lower() 

if construction_type_app in ('other', 'others'):
    print("✅ Construction Type is marked as 'Other' in the application\n")

elif construction_type_app == "frame":
    if has_brick_or_masonry_walls == "true":
        print("❌ Construction Type is marked as 'Frame', but the building has brick or masonry walls. Underwriting review required.\n") 

    elif has_brick_or_masonry_walls == "false":
        print("✅ Construction Type is marked as 'Frame', and the building does not have brick or masonry walls. \n") 

    else:
        print("⚠️ AI provided an unexpected response. Underwriting review required.\n")

elif construction_type_app == "masonry":

    if has_brick_or_masonry_walls == "true":
        print("✅ Construction Type is marked as 'Masonry', and the building has brick or masonry walls. \n") 

    elif has_brick_or_masonry_walls == "false":
        print("❌ Construction Type is marked as 'Masonry', but the building does not have brick or masonry walls. Underwriting review required.\n") 

    else:
        print("⚠️ AI provided an unexpected response. Underwriting review required.\n")

else:
    print(f"⚠️ Unexpected Construction Type: '{construction_type_app}'. Underwriting review required.\n")

# ===========================================================================================
# Rule # 21
# ===========================================================================================
print("Rule 21\n----------------------------------------------------")

extra_structure = analyze_image(
    image_path=image_path,
    question=['Return True, if there is any evidence that another building is attached to the building in image(s) by means of a roof, elevated walkway, rigid exterior wall, or stairway. Else return False.']
)

if str(extra_structure).lower() == "true":
    print("❌ An extra structure is attached to the building structure. Underwriting review required.\n")
elif str(extra_structure).lower() == "false":
    print("✅ The building does not have any extra unit attached to it.\n")
else: 
    print("⚠️ AI provided an unexpected response. Underwriting review required.\n")


# ===========================================================================================
# Rule # 22
# ===========================================================================================
print("Rule 22\n----------------------------------------------------")

verify_diagram_ai = analyze_image(
    image_path=image_path,  
    question=["If a building has an elevated floor (like a house on stilts), and the space underneath is open with lattice or slats (not solid walls), then that open area does NOT count as an enclosed space. The building would still be classified as 'Diagram 5' (a type of structure where the lower area is not fully enclosed). Tell me if the building in the image(s) is a 'Diagram 5' structure? Answer only in True/False. (True/False)"]  
).strip().lower()   

if verify_diagram_ai == "true":
    print("✅ Ai says the building in the image(s) is a 'Diagram 5' structure. Assigning diagram number as '5'. \n")
    diagram_number_app = "5"

elif verify_diagram_ai == "false":
    print("❌ Ai says the building in the image(s) is not a 'Diagram 5' structure.\n") 

else:
    print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 


# ===========================================================================================
# Rule # 23
# ===========================================================================================
print("Rule 23\n----------------------------------------------------")

if diagram_number_app.lower() == "5":
    recheck_building_for_diagram = analyze_image(
        image_path=image_path,  
        question=["Analyze the given image(s) deeply and tell is there any evidence of an enclosed elevator shaft? (True/False)"] 
    ).strip().lower()

    if recheck_building_for_diagram == "true":
        print("❌ The diagram number is 5, and the building has an enclosed elevator shaft, Assigning diagram number as 6.\n")
        diagram_number_app = "6" 
    
    elif recheck_building_for_diagram == "false":
        print("✅ The diagram number is 5, and the building does not have an enclosed elevator shaft.\n")
    
    else:
        print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 
else:
    print("✅ Diagram number is not 5, rule doesn't apply here.\n")
    
# ===========================================================================================
# Rule # 24
# ===========================================================================================
print("Rule 24\n----------------------------------------------------")

foundation_type_app = search_key(data_app, "foundation") 
appliances_eligibility = ""

appliances_on_first_floor = search_key(data_app, "Are all appliances elevated above the first floor?") or search_key(data_app, "Appliances on First Floor") or search_key(data_app, "Are all appliances elevated above the first floor") # yes / no

if str(appliances_on_first_floor).lower() == "no":
    print("✅ No appliances are elevated above first floor.\n") 

elif str(appliances_on_first_floor).lower() == "yes":
    print("⚠️ Appliances are elevated above the first floor.\n")

    if str(foundation_type_app).lower() == "slab on grade" or str(foundation_type_app).lower() == "Slab on Grade (non-elevated)":
        appliances_eligibility = analyze_image(
            image_path=image_path,
            question=["Return True if the given image(s) shows the presence of exterior machine and equipments like 'AC Condenser, Elevator, Generator' elevated atleat to the height of attic in case of single floor, or elevated to the height of second or higher floor in case of more than one floor.\n Return False if the given image(s) does not show any exterior machinery or machinery elevated as described above. "] 
        ) 

        if str(appliances_eligibility).lower() == "true":
            print("✅ Machinery is elevated according to the Rule.\n")
        elif str(appliances_eligibility).lower() == "false":
            print("❌ Machinery is not elevated according to the Rule. Underwriting review required.\n")
        else:
            print("⚠️ Ai provided an unexpected response. Underwriting review required.\n")

    elif str(foundation_type_app).lower() == "basement (non-elevated)":
        appliances_eligibility = analyze_image(
            image_path=image_path,
            question=["Return True, if the building in the image(s) shows exterior machinery or equipment elevated to the height of the floor above the basement or higher, else return False."]
        )  

        if str(appliances_eligibility).lower() == "true":
            print("✅ Machinery is elevated according to the Rule.\n")
        elif str(appliances_eligibility).lower() == "false":
            print("❌ Machinery is not elevated according to the Rule. Underwriting review required.\n")
        else:
            print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 

    elif str(foundation_type_app).lower() == "elevated without enclosure on posts" or str(foundation_type_app).lower() == "elevated without enclosure on piles" or str(foundation_type_app).lower() == "elevated without enclosure on piers":
        appliances_eligibility = analyze_image(
            image_path=image_path,
            question=["Return True, if the building the image(s) shows exterior machinery elevated elevated to the height of the lowest elevated floor or higher, else return False."]
        ) 

        if str(appliances_eligibility).lower() == "true":
            print("✅ Machinery is elevated according to the Rule.\n")
        elif str(appliances_eligibility).lower() == "false":
            print("❌ Machinery is not elevated according to the Rule. Underwriting review required.\n")
        else:
            print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 

    elif str(foundation_type_app).lower() == "elevated with enclosure on posts" or str(foundation_type_app).lower() == "elevated with enclosure on piles" or str(foundation_type_app).lower() == "elevated with enclosure on piers":
        appliances_eligibility = analyze_image(
            image_path=image_path,
            question=["Return True, if the building the image(s) shows exterior machinery like 'AC Condenser, Elevator, Generator' elevated to the height of lowest elevated floor or heigher, else return False."]
        )

        if str(appliances_eligibility).lower() == "true":
            print("✅ Machinery is elevated according to the Rule.\n")
        elif str(appliances_eligibility).lower() == "false":
            print("❌ Machinery is not elevated according to the Rule. Underwriting review required.\n")
        else:
            print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 

    elif str(foundation_type_app).lower() == "elevated with enclosure not posts" or str(foundation_type_app).lower() == "elevated with enclosure not piles" or str(foundation_type_app).lower() == "elevated with enclosure not piers":
        appliances_eligibility = analyze_image(
            image_path=image_path,
            question=["Return True, if the building in the image(s) shows exterior machinery like 'AC Condenser, Elevator, Generator' elevated to the height of the lowest elevated floor or higher, else return False."]
        )

        if str(appliances_eligibility).lower() == "true":
            print("✅ Machinery is elevated according to the Rule.\n")
        elif str(appliances_eligibility).lower() == "false":
            print("❌ Machinery is not elevated according to the Rule. Underwriting review required.\n")
        else:
            print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 

    elif str(foundation_type_app).lower() == "crawlspace" or str(foundation_type_app).lower() == "crawlspace (elevated)" or str(foundation_type_app).lower() == "crawlspace (non-elevated)" or str(foundation_type_app).lower() == "crawlspace (subgrade)" or str(foundation_type_app).lower() == "subgrade crawlspace":
        appliances_eligibility = analyze_image(
            image_path=image_path,
            question=["Return True, if the building in the image(s) shows exterior machinery like 'AC Condenser, Elevator, Generator' elevated to the height of the floor above the crawlspace or higher, else return False."]
        )
        
        if str(appliances_eligibility).lower() == "true":
            print("✅ Machinery is elevated according to the Rule.\n")
        elif str(appliances_eligibility).lower() == "false":
            print("❌ Machinery is not elevated according to the Rule. Underwriting review required.\n")
        else:
            print("⚠️ Ai provided an unexpected response. Underwriting review required.\n") 


elif not appliances_on_first_floor:
    print("⚠️ Appliances are elevated on the first floor field is not filled on the application.\n")


# ===========================================================================================
# Addtional Things to Consider
# ===========================================================================================
print("\n\nAddtional things to consider\n")
flood_zone_app = normalize_string(search_key(data_app, "Current Flood Zone") or search_key(data_app, "Flood Zone")) 
flood_zone_pdf = normalize_string(search_key(data_pdf, "B8. Flood Zone(s)") or search_key(data_pdf, "flood zone") or search_key(data_pdf, "B8") or search_key(data_pdf, "flood zones"))

suffix_app = normalize_string(search_key(data_app, "Map Panel Suffix") or search_key(data_app, "suffix") or search_key(data_app, "panel"))

suffix_pdf = normalize_string(search_key(data_pdf, "B5. Suffix") or search_key(data_pdf, "suffix") or search_key(data_pdf, "B5"))  

firm_date_app = normalize_string(search_key(data_app, "FIRM Date") or search_key(data_app, "firm"))
firm_date_pdf = normalize_string(search_key(data_pdf, "B6") or search_key(data_pdf, "B6 Firm index date") or search_key(data_pdf, "firm index date") or search_key(data_pdf, "firm") or search_key(data_pdf, "firm index") or search_key(data_pdf, "firm date")) 

if firm_date_app == firm_date_pdf:
    print("✅ Firm date is same on both EC and Application.\n")

    if suffix_app == suffix_pdf:
        if flood_zone_app == flood_zone_pdf: 
            print("✅ Flood zones and Suffix are matched on EC and application.\n") 
        elif flood_zone_pdf != flood_zone_app:
            print("❌ Suffix matched, but flood zones are different. Assigning the highest priority.\n")
            
            if get_priority(flood_zone_app) > get_priority(flood_zone_pdf):
                print(f"Zone defined in application has higher priority (i.e {flood_zone_app} > {flood_zone_pdf})") 
                flood_zone_pdf = flood_zone_app 
            elif get_priority(flood_zone_app) < get_priority(flood_zone_pdf):
                print(f"Zone defined in the pdf has higher priority (i.e {flood_zone_pdf} > {flood_zone_app})")
                flood_zone_app = flood_zone_pdf

    elif suffix_app != suffix_pdf:
        if flood_zone_app == flood_zone_pdf:
            print("⚠️ Flood Zones matched but Suffix does not match. Underwriting review required.\n")
        elif flood_zone_app != flood_zone_pdf:
            print("❌ Nor the flood zones matched, neither the suffix matched.\n")  

elif firm_date_app != firm_date_pdf:
    print("FIRM dates are not matched, reassigning the latest date.\n")
    latest_date = get_latest_date(normalize_date_str(firm_date_app), normalize_date_str(firm_date_pdf)) 

    if latest_date == firm_date_app:
        firm_date_pdf = firm_date_app 
        suffix_pdf = suffix_app
        flood_zone_pdf = flood_zone_app

    elif latest_date == firm_date_pdf:
        firm_date_app = firm_date_pdf 
        suffix_app = suffix_pdf
        flood_zone_app = flood_zone_pdf 


# ===========================================================================================
# Form Validation
# ===========================================================================================
print("\nForm Validation\n")

EC_expiration = search_key(data_pdf, "Expiration Date") or search_key(data_pdf, "Expire") or search_key(data_pdf, "Expiration")
survey_date = find_date_after_certifier(data_pdf, "Certifier's Name", "Date", 8) 

def form_validation(EC_expiration, survey_date):
    if not EC_expiration:
        print("❌ EC expiration date could not be found.\n")
    if not survey_date:
        print("❌ Survey date could not be found.\n")

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
            print("✅ EC is signed on valid date.\n")
        else:
            print("⚠️ Seems like EC is signed on invalid date. Underwriting review required.\n")

        try:
            if parser.parse(EC_expiration, dayfirst=True).year < 2003:
                print("❌ EC expiration is earlier than 2003. Underwriting review required.\n")
        except Exception as e:
            print(f"⚠️ Could not parse EC_expiration for year check: {e}")

        try:
            if parser.parse(survey_date, dayfirst=True) < parser.parse("01/10/2000", dayfirst=True):
                print("❌ Survey date is earlier than 01/10/2000. Underwriting review required.\n")
        except Exception as e:
            print(f"⚠️ Could not parse survey_date for cutoff check: {e}")


