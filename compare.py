import json
import re
from rapidfuzz import fuzz
import usaddress

def normalize_string(value):
    if not value:  
        return ""  
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r'[^a-zA-Z]', '', value) 
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


# Files paths
# --------------------------------------------------------------------------------------------------------------------------------------
with open(r"EC.json") as f: 
    data_pdf = json.load(f) 

with open(r"application.json") as f:
    data_app = json.load(f) 
#---------------------------------------------------------------------------------------------------------------------------------
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
street_name_pdf = search_key(data_pdf, "Building Street Address (including Apt., Unit, Suite, and/or Bldg. No.) or P.O. Route and Box No.")
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
]

try:
    diagramNumber_pdf = diagram_number_pdf(data_pdf, key_variants)
except (ValueError, TypeError):
    diagramNumber_pdf = -1  

try:
    diagram_number_app = diagram_number_pdf(data_app, key_variants) 
except (ValueError, TypeError):
    diagram_number_app = -1 

print(f"PDF diagram number : {diagramNumber_pdf}\nApplication diagram number : {diagram_number_app}\n")

if diagramNumber_pdf and diagram_number_app:
    if str(diagramNumber_pdf).strip()[0] == str(diagram_number_app).strip()[0]:
        print("Diagram Numbers matched. ✅")
    else:
        print("The diagram numbers on the EC and application do not match. Underwriting review required. ❌")
else:
    print("The diagram number on the EC is missing. Underwriting review required.❗")  


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

lookup_keys = ["SquareFootage", "square footage of crawlspace or enclosure(s)"]

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
    Section_C_LAG_app = float(search_key(data_app, 'ecSectionCLowestAdjacentGrade'))
except (ValueError, TypeError):
    Section_C_LAG_app = 0

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
top_of_next_higher_floor_app = extract_float_value(search_key(data_app, 'Top of Next Higher Floor')) 
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
    if diagramNumber_pdf.lower() in diagram_choices_1:   
        if top_of_bottom_floor_pdf < LAG_pdf + 2:
            print(f"\nElevation Logic matched. The top of bottom floor is within 2 feet of the LAG. ✅") 
        else:
            print(f"Please review foundation system as the top of bottom floor is not within 2 feet of the LAG. ❌")

        if top_of_bottom_floor_pdf >= LAG_pdf:
            print("Elevation Logic matched. Top of bottom floor is greater than LAG. ✅")
        else:
            print("Please review the foundation system as the top of bottom floor is less than the LAG. ❌")

    elif diagramNumber_pdf.lower() == diagram_choices_2:  
        if LAG_pdf <= top_of_bottom_floor_pdf < LAG_pdf + 6:
            print(f"Elevation Logic matched. The top of bottom floor is within 6 feet of the LAG. ✅") 
        else:
            print(f"Please review stem-wall foundation system as the top of bottom floor is not within 6 feet of the LAG. ❌")

    elif diagramNumber_pdf.lower() in diagram_choices_3:
        if top_of_bottom_floor_pdf < LAG_pdf:
            print(f"Elevation Logic matched. The top of bottom floor is below the LAG. ✅") 
        else:
            print(f"Please verify the building foundation as the top of bottom floor is not below the LAG. ❌\n") 

# <= (LAG_pdf + 20):
    elif diagramNumber_pdf.lower() in diagram_choices_4:
        if LAG_pdf <= top_of_bottom_floor_pdf:
            print(f"Elevation Logic matched. The top of bottom floor elevation is above the LAG for this Diagram 5 building. ✅")
        else:
            print(f"Please verify foundation system. The top of bottom floor elevation is below the LAG for this Diagram 5 building. ❌")
        
        if top_of_bottom_floor_pdf <= (LAG_pdf + 20):
            print("Elevation Logic matched. Top of bottom floor is below 20 feet of LAG. ✅") 
        else:
            print("Please review elevations and photographs as there is more than 20 foot difference between C2a and the LAG. ❌")

    if diagramNumber_pdf.lower() in diagram_choices_5:
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
    elif diagramNumber_pdf.lower() in diagram_choices_8:
        if e1b <= (LAG_pdf + 20):
            print(f"Elevation Logic matched. e1b is lower than 20 feet of LAG. ✅")
        else: 
            print(f"Please review elevations and photographs as there is more than 20 foot difference between the E1b elevation and the LAG. ❌")  

        if e1b >= LAG_pdf:
            print("Elevation Logic matched. The e1b elevation is greater than the LAG. ✅")
        else:
            print("The top of bottom floor elevation is below the LAG for this Diagram 5 building. Please verify foundation system. ❌") 

    elif diagramNumber_pdf.lower() in diagram_choices_9:
        if e1b < LAG_pdf: 
            print(f"The top of bottom floor is above the LAG. Elevation Logic matched. ✅") 
        else:
            print(f"Please review the foundation system as the top of bottom floor is not below the LAG. ❌") 

    if diagramNumber_pdf.lower() in diagram_choices_10:
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

    if diagramNumber_pdf.lower() in diagram_choices_14: 
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

    
    elif diagramNumber_pdf.lower() in diagram_choices_15:

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

    elif diagramNumber_pdf.lower() == '5':
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
A8_engineered_flood_openings_pdf_v1 = extract_float_value(search_key(data_pdf, 'Engineered Flood Openings')) 
A8_engineered_flood_openings_pdf_v2 = extract_float_value(search_key(data_pdf, 'Engineered'))
A8_flood_openings_pdf_v3 = extract_float_value(search_key(data_pdf, 'Number of permanent flood openings in the crawlspace'))
A8_old_flood_openings_pdf_v4 = extract_float_value(search_key(data_pdf, 'Number of permanent flood openings in the crawlspace or enclosures within 1.0 foot above adjacent grade'))
A8_much_older_flood_openings_pdf_v5 = extract_float_value(search_key(data_pdf, 'No. of permanent openings (flood vents) within 1 ft. above adjacent grade'))

A8_flood_openings_pdf = ((A8_non_engineered_flood_openings_pdf_v1 or A8_non_engineered_flood_openings_pdf_v2) + (A8_engineered_flood_openings_pdf_v1 or A8_engineered_flood_openings_pdf_v2)) or A8_flood_openings_pdf_v3 or A8_old_flood_openings_pdf_v4 or A8_much_older_flood_openings_pdf_v5

# Area of A8
A8_total_vents_area_pdf_v1 = extract_float_value(search_key(data_pdf, "Total net open area of non-engineered flood openings in A8.c"))
A8_total_vents_area_pdf_v2 = extract_float_value(search_key(data_pdf, "Total net area of flood openings in A8.b")) 
A8_total_vents_area_pdf_v3 = extract_float_value(search_key(data_pdf, "Total area of all permanent openings (flood vents) in C3h"))  
A8_total_vents_area_pdf_v4 = extract_float_value(search_key(data_pdf, "Total net open area of non-engineered flood openings"))

A8_total_area = A8_total_vents_area_pdf_v1 or A8_total_vents_area_pdf_v2 or A8_total_vents_area_pdf_v3 or A8_total_vents_area_pdf_v4 

# A9 vents
A9_non_engineered_flood_openings_pdf_v1 = extract_float_value(search_second_key(data_pdf, 'Non-Engineered Flood Openings'))
A9_non_engineered_flood_openings_pdf_v2 = extract_float_value(search_second_key(data_pdf, 'Non-Engineered'))
A9_engineered_flood_openings_pdf_v1 = extract_float_value(search_second_key(data_pdf, 'Engineered Flood Openings')) 
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

if diagramNumber_pdf.lower() in diagram_choices_10:
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











































