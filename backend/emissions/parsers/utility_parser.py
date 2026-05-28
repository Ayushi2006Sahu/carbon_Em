import csv
import io
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from emissions.models import EmissionRecord

HEADER_MAP = {
    'account_number': 'account_number', 'account': 'account_number', 'acct': 'account_number', 'acct_no': 'account_number',
    'meter_id': 'meter_id', 'meter': 'meter_id', 'meter_number': 'meter_id', 'meter_no': 'meter_id',
    'service_address': 'service_address', 'address': 'service_address', 'location': 'service_address',
    'billing_period_start': 'billing_period_start', 'start_date': 'billing_period_start', 'from_date': 'billing_period_start', 'period_start': 'billing_period_start',
    'billing_period_end': 'billing_period_end', 'end_date': 'billing_period_end', 'to_date': 'billing_period_end', 'period_end': 'billing_period_end',
    'kwh_consumed': 'kwh_consumed', 'kwh': 'kwh_consumed', 'energy': 'kwh_consumed', 'consumption': 'kwh_consumed', 'quantity': 'kwh_consumed',
    'peak_demand_kw': 'peak_demand_kw', 'demand_kw': 'peak_demand_kw', 'peak_kw': 'peak_demand_kw',
    'tariff_code': 'tariff_code', 'tariff': 'tariff_code', 'rate_class': 'tariff_code',
    'amount_billed': 'amount_billed', 'amount': 'amount_billed', 'cost': 'amount_billed', 'total_bill': 'amount_billed'
}

def parse_utility_csv(file_content, data_source, user=None):
    """
    Parses a Utility Electricity CSV file (Green Button / billing export).
    Normalizes consumption to kWh, calculates emissions, marks as Scope 2,
    and returns a list of EmissionRecord objects (unsaved).
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
        
        # Original identifier
        account_no = row_dict.get('account_number', '').strip()
        meter_id = row_dict.get('meter_id', '').strip()
        source_ref = f"UTIL-{account_no or 'ACCT'}-{meter_id or 'METER'}-ROW-{row_idx}"
        
        # Parse Dates
        start_str = row_dict.get('billing_period_start', '').strip()
        end_str = row_dict.get('billing_period_end', '').strip()
        
        period_start = None
        period_end = None
        date_parsing_failed = False
        
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d.%m.%Y'):
            try:
                if not period_start and start_str:
                    period_start = datetime.strptime(start_str, fmt).date()
                if not period_end and end_str:
                    period_end = datetime.strptime(end_str, fmt).date()
            except ValueError:
                continue
                
        if not period_start:
            period_start = timezone.now().date()
            date_parsing_failed = True
        if not period_end:
            period_end = timezone.now().date()
            date_parsing_failed = True
            
        # Parse energy consumption
        kwh_str = row_dict.get('kwh_consumed', '0').strip().replace(',', '')
        try:
            kwh = Decimal(kwh_str)
        except Exception:
            kwh = Decimal('0')
            
        # Apply Grid Factor: 0.82 kgCO2e/kWh
        ef_used = Decimal('0.82')
        co2_val = kwh * ef_used
        
        record = EmissionRecord(
            tenant=tenant,
            source=data_source,
            scope=2,
            category='electricity',
            activity_value=kwh,
            activity_unit='kWh',
            normalized_value_kg_co2e=co2_val,
            emission_factor_used=ef_used,
            period_start=period_start,
            period_end=period_end,
            source_ref=source_ref,
            is_suspicious=False,
            status='pending_review'
        )
        
        # Initial local checks for suspicion
        reasons = []
        if kwh <= 0:
            reasons.append("Electricity usage (kWh) is zero or negative.")
        if period_start > timezone.now().date() or period_end > timezone.now().date():
            reasons.append("Billing period date is in the future.")
        if (timezone.now().date() - period_start).days > 365 * 2:
            reasons.append("Billing start date is older than 2 years.")
        if period_start >= period_end:
            reasons.append("Billing period start date is after or equal to the end date.")
        if date_parsing_failed:
            reasons.append(f"Failed to parse billing dates: start='{start_str}', end='{end_str}'.")
            
        if reasons:
            record.is_suspicious = True
            record.suspicion_reason = "; ".join(reasons)
            
        records.append(record)
        
    return records
