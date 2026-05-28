import os
import sys
import django
import traceback

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathe_esg.settings')
sys.path.append('backend')
django.setup()

from emissions.models import RawIngestion
from emissions.parsers.sap_parser import parse_sap_csv
from emissions.parsers.utility_parser import parse_utility_csv
from emissions.parsers.travel_parser import parse_travel_csv
from emissions.suspicion import evaluate_records_suspicion
from emissions.serializers import EmissionRecordSerializer
from emissions.views import get_or_create_demo_tenant_user, create_audit_entry
from django.db import transaction

def test_parse_run(r, user):
    r.raw_file.open('rb')
    content = r.raw_file.read()
    r.raw_file.close()
    
    source_type = r.source.source_type
    print(f"\n--- Dry-running Ingestion ID {r.id} ({source_type}) ---")
    print("File name:", r.raw_file.name)
    print("Content length:", len(content))
    
    if source_type == 'SAP':
        records = parse_sap_csv(content, r.source, user)
    elif source_type == 'UTILITY':
        records = parse_utility_csv(content, r.source, user)
    elif source_type == 'TRAVEL':
        records = parse_travel_csv(content, r.source, user)
    else:
        raise ValueError(f"Unknown source type: {source_type}")
        
    print("Parsed records count:", len(records))
    
    evaluate_records_suspicion(records)
    print("Suspicion evaluation complete.")
    
    # Run in transaction rollback to test saving without mutating database
    with transaction.atomic():
        for rec in records:
            rec.save()
            after_data = EmissionRecordSerializer(rec).data
            create_audit_entry(
                record=rec,
                action='ingested',
                user=user,
                before_state=None,
                after_state=after_data
            )
        transaction.set_rollback(True)
    print("Database dry-run save successful (rolled back)!")

def main():
    try:
        tenant, user = get_or_create_demo_tenant_user()
        runs = list(RawIngestion.objects.all().order_by('id'))
        print(f"Total Raw Ingestion Runs: {len(runs)}")
        for r in runs:
            print(f"ID: {r.id} | Status: {r.status} | File: {r.raw_file.name if r.raw_file else 'None'} | Time: {r.ingested_at}")
            
        for r in runs:
            if r.status == 'failed':
                try:
                    test_parse_run(r, user)
                except Exception as e:
                    print(f"CRASH DETECTED ON RUN {r.id}:", str(e))
                    traceback.print_exc()
    except Exception as e:
        print("DIAGNOSTIC CRASH:", str(e))
        traceback.print_exc()

if __name__ == '__main__':
    main()
