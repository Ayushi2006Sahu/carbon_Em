import csv
import io
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from django.db import models
from emissions.models import EmissionRecord, Tenant, DataSource

# Plant code lookup dictionary
WERKS_LOOKUP = {
    '1000': 'Berlin HQ Plant',
    '1100': 'Munich Assembly Facility',
    '1200': 'Hamburg Shipping Hub',
    '2000': 'Bangalore R&D Lab',
    '3000': 'New York Head Office',
}

# Standard fuel densities (kg/L or kg/m3) to support normalization to KG
FUEL_DENSITIES = {
    'DIESEL': Decimal('0.84'),
    'PETROL': Decimal('0.74'),
    'GAS': Decimal('0.80'),          # Natural Gas
    'NATURAL_GAS': Decimal('0.80'),
    'DEFAULT': Decimal('0.82'),
}

# German and case-insensitive column mappings
HEADER_MAP = {
    'mandt': 'MANDT', 'mandant': 'MANDT', 'client': 'MANDT',
    'werks': 'WERKS', 'werk': 'WERKS', 'plant': 'WERKS', 'plant_code': 'WERKS',
    'matnr': 'MATNR', 'material': 'MATNR', 'materialnummer': 'MATNR', 'item': 'MATNR',
    'meins': 'MEINS', 'einheit': 'MEINS', 'mengeneinheit': 'MEINS', 'unit': 'MEINS',
    'menge': 'MENGE', 'menge_qty': 'MENGE', 'quantity': 'MENGE', 'amount': 'MENGE',
    'netwr': 'NETWR', 'nettowert': 'NETWR', 'value': 'NETWR', 'cost': 'NETWR',
    'waers': 'WAERS', 'waehrung': 'WAERS', 'currency': 'WAERS',
    'bldat': 'BLDAT', 'belegdatum': 'BLDAT', 'date': 'BLDAT', 'datum': 'BLDAT', 'document_date': 'BLDAT'
}

def parse_sap_csv(file_content, data_source, user=None):
    """
    Parses a SAP CSV file containing fuel and procurement records.
    Normalizes volumes to weight (KG), applies emission factors, detects Scope,
    and returns a list of EmissionRecord objects (unsaved).
    """
    tenant = data_source.tenant
    records = []
    
    # Read the file content as CSV
    reader = csv.reader(io.StringIO(file_content.decode('utf-8-sig')))
    
    headers = next(reader, None)
    if not headers:
        raise ValueError("The uploaded CSV file is empty.")
    
    # Standardize headers using the map
    standardized_headers = []
    for h in headers:
        clean_h = h.strip().lower()
        standardized_headers.append(HEADER_MAP.get(clean_h, h.strip()))

    for row_idx, row in enumerate(reader, start=2):
        if not row or all(val.strip() == '' for val in row):
            continue
            
        row_dict = dict(zip(standardized_headers, row))
        
        # Original identifier
        source_ref = f"SAP-ROW-{row_idx}-{row_dict.get('MATNR', 'UNKNOWN')}"
        
        # Parse plant code
        werks = row_dict.get('WERKS', '').strip()
        location_name = WERKS_LOOKUP.get(werks, f"Plant Code: {werks or 'Unknown'}")
        
        # Parse material
        matnr = row_dict.get('MATNR', '').strip().upper()
        
        # Parse date (DD.MM.YYYY)
        bldat_str = row_dict.get('BLDAT', '').strip()
        period_date = None
        date_parsing_failed = False
        
        for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y'):
            try:
                period_date = datetime.strptime(bldat_str, fmt).date()
                break
            except ValueError:
                continue
        
        if not period_date:
            period_date = timezone.now().date()
            date_parsing_failed = True
            
        # Parse quantity and value
        try:
            quantity = Decimal(row_dict.get('MENGE', '0').strip().replace(',', ''))
        except Exception:
            quantity = Decimal('0')
            
        unit = row_dict.get('MEINS', '').strip().upper()
        
        # Process and normalize unit to KG
        normalized_qty = quantity
        unit_normalization_failed = False
        
        # Determine fuel density based on material
        fuel_key = 'DEFAULT'
        if 'DIESEL' in matnr:
            fuel_key = 'DIESEL'
        elif 'PETROL' in matnr or 'GASOLINE' in matnr:
            fuel_key = 'PETROL'
        elif 'NATURAL_GAS' in matnr or 'GAS' in matnr:
            fuel_key = 'GAS'
            
        density = FUEL_DENSITIES[fuel_key]
        
        if unit == 'KG':
            normalized_qty = quantity
        elif unit == 'L' or unit == 'LTR':
            # Volume to mass: Liter * density
            normalized_qty = quantity * density
        elif unit == 'GAL' or unit == 'GALLON':
            # Gallon to liter then density
            liters = quantity * Decimal('3.78541')
            normalized_qty = liters * density
        elif unit == 'M3':
            # Cubic meters to mass (mostly for natural gas)
            normalized_qty = quantity * density
        else:
            # Unmapped unit. Default to quantity and set error flag
            unit_normalization_failed = True
            
        # Calculate carbon emissions
        # Factors: diesel = 2.68 kgCO2e/L, petrol = 2.31 kgCO2e/L, natural_gas = 2.04 kgCO2e/m3
        # If input was in KG, we back-calculate volume to apply the factor, or apply mass-equivalent factor
        co2_val = Decimal('0')
        ef_used = Decimal('0')
        scope = 3
        category = 'fuel'
        
        is_fuel = any(k in matnr for k in ['DIESEL', 'PETROL', 'GASOLINE', 'NATURAL_GAS', 'GAS'])
        
        if is_fuel:
            scope = 1
            category = 'fuel'
            if 'DIESEL' in matnr:
                ef_used = Decimal('2.68')  # kgCO2e/L
                # Convert quantity to L for emission factor
                vol_l = quantity
                if unit == 'KG':
                    vol_l = quantity / density
                elif unit == 'GAL':
                    vol_l = quantity * Decimal('3.78541')
                elif unit == 'M3':
                    vol_l = quantity * Decimal('1000') # 1 m3 = 1000 L
                co2_val = vol_l * ef_used
            elif 'PETROL' in matnr or 'GASOLINE' in matnr:
                ef_used = Decimal('2.31')  # kgCO2e/L
                vol_l = quantity
                if unit == 'KG':
                    vol_l = quantity / density
                elif unit == 'GAL':
                    vol_l = quantity * Decimal('3.78541')
                elif unit == 'M3':
                    vol_l = quantity * Decimal('1000')
                co2_val = vol_l * ef_used
            elif 'NATURAL_GAS' in matnr or 'GAS' in matnr:
                ef_used = Decimal('2.04')  # kgCO2e/m3
                vol_m3 = quantity
                if unit == 'KG':
                    vol_m3 = quantity / density
                elif unit == 'L' or unit == 'LTR':
                    vol_m3 = quantity / Decimal('1000')
                elif unit == 'GAL':
                    vol_m3 = (quantity * Decimal('3.78541')) / Decimal('1000')
                co2_val = vol_m3 * ef_used
        else:
            # General procurement material -> Scope 3 (Category 1: Purchased Goods and Services)
            # Default factor: 1.25 kgCO2e per kg of generic goods
            scope = 3
            category = 'fuel' # As defined in models: choices include fuel/electricity/flight/hotel/ground
            # Since SAP is Fuel & Procurement, we categorize general procurement under 'fuel' or a catch-all category.
            # In EmissionRecord model, the choices are fuel/electricity/flight/hotel/ground. Fuel is the most appropriate.
            ef_used = Decimal('1.250000')  # kgCO2e/kg
            # Net weight in KG
            co2_val = normalized_qty * ef_used
            
        # Create record
        record = EmissionRecord(
            tenant=tenant,
            source=data_source,
            scope=scope,
            category=category,
            activity_value=quantity,
            activity_unit=unit or 'KG',
            normalized_value_kg_co2e=co2_val,
            emission_factor_used=ef_used,
            period_start=period_date,
            period_end=period_date,
            source_ref=source_ref,
            is_suspicious=False,
            status='pending_review'
        )
        
        # Initial local checks for suspicion
        reasons = []
        if quantity <= 0:
            reasons.append("Activity quantity is zero or negative.")
        if period_date > timezone.now().date():
            reasons.append("Document date is in the future.")
        if (timezone.now().date() - period_date).days > 365 * 2:
            reasons.append("Document date is older than 2 years.")
        if date_parsing_failed:
            reasons.append(f"Failed to parse document date format: '{bldat_str}'.")
        if unit_normalization_failed:
            reasons.append(f"Activity unit '{unit}' could not be normalized confidently.")
            
        if reasons:
            record.is_suspicious = True
            record.suspicion_reason = "; ".join(reasons)
            
        records.append(record)
        
    return records
