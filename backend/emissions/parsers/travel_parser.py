import csv
import io
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from emissions.models import EmissionRecord
from emissions.utils import calculate_distance_km

HEADER_MAP = {
    'expense_id': 'expense_id', 'id': 'expense_id', 'expense': 'expense_id',
    'traveler_name': 'traveler_name', 'traveler': 'traveler_name', 'name': 'traveler_name',
    'travel_date': 'travel_date', 'date': 'travel_date', 'expense_date': 'travel_date',
    'travel_type': 'travel_type', 'type': 'travel_type',
    'origin': 'origin', 'from': 'origin', 'start': 'origin',
    'destination': 'destination', 'to': 'destination', 'end': 'destination',
    'distance_km': 'distance_km', 'distance': 'distance_km', 'km': 'distance_km',
    'nights': 'nights', 'days': 'nights', 'duration': 'nights', 'hotel_nights': 'nights',
    'travel_class': 'travel_class', 'class': 'travel_class', 'cabin': 'travel_class',
    'amount': 'amount', 'cost': 'amount',
    'currency': 'currency', 'curr': 'currency'
}

# Emission factors (kgCO2e per unit)
EF_FLIGHT_ECONOMY = Decimal('0.255')
EF_FLIGHT_BUSINESS = Decimal('0.612')
EF_HOTEL_NIGHT = Decimal('31.2')
EF_GROUND_KM = Decimal('0.21')

def parse_travel_csv(file_content, data_source, user=None):
    """
    Parses a Corporate Travel CSV file (Concur-style export).
    Maps distance calculations via airport codes if needed, applies multipliers,
    marks as Scope 3, and returns a list of EmissionRecord objects (unsaved).
    """
    tenant = data_source.tenant
    records = []
    
    reader = csv.reader(io.StringIO(file_content.decode('utf-8-sig')))
    
    headers = next(reader, None)
    if not headers:
        raise ValueError("The uploaded CSV file is empty.")
        
    standardized_headers = []
    for h in headers:
        clean_h = h.strip().lower().replace(' ', '_')
        standardized_headers.append(HEADER_MAP.get(clean_h, h.strip()))

    for row_idx, row in enumerate(reader, start=2):
        if not row or all(val.strip() == '' for val in row):
            continue
            
        row_dict = dict(zip(standardized_headers, row))
        
        expense_id = row_dict.get('expense_id', '').strip()
        source_ref = f"TRAVEL-{expense_id or 'EXP'}-ROW-{row_idx}"
        
        # Parse travel type
        raw_type = row_dict.get('travel_type', '').strip().upper()
        
        # Parse Date
        date_str = row_dict.get('travel_date', '').strip()
        travel_date = None
        date_parsing_failed = False
        
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d.%m.%Y'):
            try:
                travel_date = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
                
        if not travel_date:
            travel_date = timezone.now().date()
            date_parsing_failed = True
            
        # Common parameters
        category = 'flight'
        activity_value = Decimal('0')
        activity_unit = 'km'
        ef_used = Decimal('0')
        co2_val = Decimal('0')
        
        reasons = []
        haversine_applied = False
        airport_lookup_failed = False
        
        if raw_type == 'FLIGHT':
            category = 'flight'
            activity_unit = 'km'
            travel_class = row_dict.get('travel_class', '').strip().upper()
            
            # Determine class factor
            if 'BUSINESS' in travel_class or 'FIRST' in travel_class:
                ef_used = EF_FLIGHT_BUSINESS
            else:
                ef_used = EF_FLIGHT_ECONOMY
                
            # Parse or compute distance
            dist_str = row_dict.get('distance_km', '').strip().replace(',', '')
            if dist_str:
                try:
                    activity_value = Decimal(dist_str)
                except Exception:
                    activity_value = Decimal('0')
            else:
                # Compute distance using origin/destination IATA codes
                orig = row_dict.get('origin', '').strip().upper()
                dest = row_dict.get('destination', '').strip().upper()
                if orig and dest:
                    try:
                        computed_dist = calculate_distance_km(orig, dest)
                        activity_value = Decimal(str(computed_dist))
                        haversine_applied = True
                    except ValueError as e:
                        activity_value = Decimal('0')
                        airport_lookup_failed = True
                        reasons.append(str(e))
                else:
                    reasons.append("Missing distance_km and could not compute because origin/destination are empty.")
            
            co2_val = activity_value * ef_used

        elif raw_type == 'HOTEL':
            category = 'hotel'
            activity_unit = 'nights'
            ef_used = EF_HOTEL_NIGHT
            
            nights_str = row_dict.get('nights', '0').strip().replace(',', '')
            try:
                activity_value = Decimal(nights_str)
            except Exception:
                activity_value = Decimal('0')
                
            co2_val = activity_value * ef_used

        elif raw_type == 'GROUND':
            category = 'ground'
            activity_unit = 'km'
            ef_used = EF_GROUND_KM
            
            dist_str = row_dict.get('distance_km', '0').strip().replace(',', '')
            try:
                activity_value = Decimal(dist_str)
            except Exception:
                activity_value = Decimal('0')
                
            co2_val = activity_value * ef_used
        else:
            reasons.append(f"Unknown travel_type: '{raw_type}'. Supported: FLIGHT/HOTEL/GROUND.")
            activity_unit = 'unmapped'
            
        record = EmissionRecord(
            tenant=tenant,
            source=data_source,
            scope=3,
            category=category,
            activity_value=activity_value,
            activity_unit=activity_unit,
            normalized_value_kg_co2e=co2_val,
            emission_factor_used=ef_used,
            period_start=travel_date,
            period_end=travel_date,
            source_ref=source_ref,
            is_suspicious=False,
            status='pending_review'
        )
        
        # Suspicion detection checks
        if activity_value <= 0:
            reasons.append("Activity value (distance/nights) is zero or negative.")
        if travel_date > timezone.now().date():
            reasons.append("Travel expense date is in the future.")
        if (timezone.now().date() - travel_date).days > 365 * 2:
            reasons.append("Travel date is older than 2 years.")
        if date_parsing_failed:
            reasons.append(f"Failed to parse travel date format: '{date_str}'.")
        if airport_lookup_failed:
            reasons.append("Could not calculate flight distance; airports not in local top-30 list.")
        if activity_unit == 'unmapped':
            reasons.append("Travel classification failed.")
            
        if reasons:
            record.is_suspicious = True
            record.suspicion_reason = "; ".join(reasons)
            
        records.append(record)
        
    return records
