from decimal import Decimal
from django.db import models
from django.utils import timezone
from emissions.models import EmissionRecord

def evaluate_records_suspicion(records):
    """
    Evaluates a list of (unsaved) EmissionRecord objects for anomaly/suspicion detection.
    Updates the records' is_suspicious and suspicion_reason fields.
    
    Rules checked:
    1. activity_value is 0 or negative
    2. normalized_value_kg_co2e is more than 3x the tenant's historical average for that category
    3. period_start/period_end are in the future or more than 2 years old
    4. unit could not be confidently mapped (marked during ingestion)
    """
    # Group records by (tenant, category) to fetch historical averages efficiently
    tenant_categories = set((r.tenant, r.category) for r in records)
    
    averages = {}
    for tenant, category in tenant_categories:
        avg_val = EmissionRecord.objects.filter(
            tenant=tenant,
            category=category,
            status='approved'  # compare against high-quality verified data
        ).aggregate(models.Avg('normalized_value_kg_co2e'))['normalized_value_kg_co2e__avg']
        
        if avg_val is not None:
            averages[(tenant.id, category)] = Decimal(str(avg_val))
            
    for r in records:
        reasons = []
        
        # 1. Check existing reasons from the parser stage
        if r.is_suspicious and r.suspicion_reason:
            reasons = r.suspicion_reason.split("; ")
            
        # 2. Check historical average outlier spike (> 3x category average)
        key = (r.tenant.id, r.category)
        if key in averages:
            historical_avg = averages[key]
            # Only trigger if the historical average is meaningful (e.g. non-zero)
            if historical_avg > 0 and r.normalized_value_kg_co2e > (historical_avg * Decimal('3')):
                reasons.append(
                    f"Emissions value ({r.normalized_value_kg_co2e:.1f} kgCO2e) is more than 3x "
                    f"historical average ({historical_avg:.1f} kgCO2e) for category '{r.category}'."
                )
                
        # 3. Double-check date thresholds (standard fallback checks)
        today = timezone.now().date()
        if r.period_start > today or r.period_end > today:
            date_future_msg = "Transaction date is in the future."
            if date_future_msg not in reasons:
                reasons.append(date_future_msg)
                
        if (today - r.period_start).days > 365 * 2:
            date_old_msg = "Transaction date is older than 2 years."
            if date_old_msg not in reasons:
                reasons.append(date_old_msg)
                
        if r.activity_value <= 0:
            qty_msg = "Activity quantity is zero or negative."
            if qty_msg not in reasons:
                reasons.append(qty_msg)
                
        # 4. Finalize state
        if reasons:
            r.is_suspicious = True
            r.suspicion_reason = "; ".join(reasons)
        else:
            r.is_suspicious = False
            r.suspicion_reason = None
            
    return records
