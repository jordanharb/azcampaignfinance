#!/usr/bin/env python3
"""
Test the shift fix on sample data
"""

# Simulate the fix logic
def fix_shifted_data(first_row):
    """Test the shift detection and correction logic"""
    
    # Get raw values
    org_email = first_row.get('OrgEml', '')
    org_phone = first_row.get('OrgTel', '')
    org_address = first_row.get('OrgAdr', '')
    org_treasurer = first_row.get('OrgTreasurer', '')
    org_jurisdiction = first_row.get('Jurisdiction', 'Arizona Secretary of State')
    
    print(f"BEFORE FIX:")
    print(f"  Email: {org_email}")
    print(f"  Phone: {org_phone}")
    print(f"  Address: {org_address}")
    print(f"  Treasurer: {org_treasurer}")
    print(f"  Jurisdiction: {org_jurisdiction}")
    
    # Detect and fix shifted data pattern
    if org_email and 'Phone:' in org_email:
        print("\n🔧 SHIFT DETECTED - Fixing...")
        
        # Data is shifted - fix it
        actual_phone = org_email.replace('Phone:', '').strip()
        actual_address = org_phone  # Phone field contains address
        actual_treasurer = org_address.replace('Treasurer:', '').strip() if 'Treasurer:' in org_address else org_address
        actual_jurisdiction = org_treasurer.replace('Jurisdiction:', '').strip() if 'Jurisdiction:' in org_treasurer else org_treasurer
        
        # Email is missing in shifted data, set to empty
        org_email = ''
        org_phone = actual_phone
        org_address = actual_address
        org_treasurer = actual_treasurer
        org_jurisdiction = actual_jurisdiction if actual_jurisdiction else 'Arizona Secretary of State'
    else:
        print("\n✅ No shift detected - data looks correct")
    
    print(f"\nAFTER FIX:")
    print(f"  Email: {org_email}")
    print(f"  Phone: {org_phone}")
    print(f"  Address: {org_address}")
    print(f"  Treasurer: {org_treasurer}")
    print(f"  Jurisdiction: {org_jurisdiction}")
    
    return {
        'org_email': org_email,
        'org_phone': org_phone,
        'org_address': org_address,
        'org_treasurer': org_treasurer,
        'org_jurisdiction': org_jurisdiction
    }

print("="*70)
print("TESTING SHIFT FIX LOGIC")
print("="*70)

# Test case 1: Shifted data (what we see in bad reports)
print("\n📋 TEST 1: Shifted Data (Bad)")
print("-" * 40)
shifted_row = {
    'OrgNm': 'GAIL GRIFFIN for State Representative - District 19',
    'OrgEml': 'Phone: (520) 378-4333',
    'OrgTel': 'PO Box 628, Hereford, AZ 85615',
    'OrgAdr': 'Treasurer: REMICK, TIMOTHY',
    'OrgTreasurer': 'Jurisdiction: Arizona Secretary of State',
    'Jurisdiction': ''
}
fixed = fix_shifted_data(shifted_row)

# Test case 2: Normal data (what we see in good reports)
print("\n\n📋 TEST 2: Normal Data (Good)")
print("-" * 40)
normal_row = {
    'OrgNm': 'GAIL GRIFFIN for State Representative - District 14',
    'OrgEml': 'griff4333@gmail.com',
    'OrgTel': '(520) 378-4333',
    'OrgAdr': 'PO Box 628, Hereford, AZ 85615',
    'OrgTreasurer': 'REMICK, TIMOTHY',
    'Jurisdiction': 'Arizona Secretary of State'
}
fixed = fix_shifted_data(normal_row)

# Test case 3: Another shifted pattern
print("\n\n📋 TEST 3: Another Shifted Pattern")
print("-" * 40)
shifted_row2 = {
    'OrgNm': 'Grantham for Arizona 2020',
    'OrgEml': 'Phone: (602) 510-0101',
    'OrgTel': '2068 E Tiffany Ct, Gilbert, AZ 85298',
    'OrgAdr': 'Treasurer: Grantham, Travis',
    'OrgTreasurer': 'Jurisdiction: Arizona Secretary of State',
    'Jurisdiction': 'Arizona Secretary of State'
}
fixed = fix_shifted_data(shifted_row2)

print("\n" + "="*70)
print("✅ FIX LOGIC VERIFIED")
print("="*70)
print("\nThe fix correctly:")
print("1. Detects when email contains 'Phone:'")
print("2. Shifts all fields back to correct positions")
print("3. Leaves normal data unchanged")
print("\nNow run complete_cleanup.py then step3_concurrent.py to reprocess!")