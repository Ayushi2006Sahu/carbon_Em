from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
import traceback
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from emissions.models import Tenant, User, DataSource, RawIngestion, EmissionRecord, AuditLog
from emissions.serializers import EmissionRecordSerializer, AuditLogSerializer
from emissions.parsers.sap_parser import parse_sap_csv
from emissions.parsers.utility_parser import parse_utility_csv
from emissions.parsers.travel_parser import parse_travel_csv
from emissions.suspicion import evaluate_records_suspicion

def get_or_create_demo_tenant_user():
    """
    Utility helper to ensure a default tenant and user exist during demo runs.
    """
    tenant = Tenant.objects.filter(name="Acme Corporation").first()
    if not tenant:
        tenant = Tenant.objects.create(name="Acme Corporation")
        
    user = User.objects.filter(username="analyst_jane").first()
    if not user:
        user = User.objects.create(
            username="analyst_jane",
            email="jane@acme.com",
            role="analyst",
            tenant=tenant
        )
        user.set_password("breathe_esg_pass")
        user.save()
    return tenant, user

def create_audit_entry(record, action, user, before_state=None, after_state=None):
    """
    Helper to record historical ledger edits.
    """
    AuditLog.objects.create(
        record=record,
        action=action,
        changed_by=user,
        before_state=before_state,
        after_state=after_state
    )

@api_view(['POST'])
def ingest_sap_csv(request):
    tenant, user = get_or_create_demo_tenant_user()
    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({"error": "No file uploaded. Use parameter name 'file'."}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve Data Source
    data_source, _ = DataSource.objects.get_or_create(tenant=tenant, source_type='SAP')
    
    # Save Ingestion Run Tracker
    raw_ingest = RawIngestion.objects.create(
        source=data_source,
        raw_file=file_obj,
        status='processing'
    )

    try:
        file_obj.seek(0)
        file_content = file_obj.read()
        records = parse_sap_csv(file_content, data_source, user)
        
        # Evaluate anomaly outlier detection
        evaluate_records_suspicion(records)

        # Write to Database with full auditing logs
        with transaction.atomic():
            for rec in records:
                rec.save()
                
                # Capture post-state payload
                after_data = EmissionRecordSerializer(rec).data
                create_audit_entry(
                    record=rec,
                    action='ingested',
                    user=user,
                    before_state=None,
                    after_state=after_data
                )
                
        raw_ingest.status = 'done'
        raw_ingest.save()
        
        return Response({
            "message": f"Successfully ingested SAP CSV.",
            "records_created": len(records)
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        traceback.print_exc()
        raw_ingest.status = 'failed'
        raw_ingest.save()
        return Response({"error": f"Failed to ingest SAP CSV: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def ingest_utility_csv(request):
    tenant, user = get_or_create_demo_tenant_user()
    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({"error": "No file uploaded. Use parameter name 'file'."}, status=status.HTTP_400_BAD_REQUEST)

    data_source, _ = DataSource.objects.get_or_create(tenant=tenant, source_type='UTILITY')
    
    raw_ingest = RawIngestion.objects.create(
        source=data_source,
        raw_file=file_obj,
        status='processing'
    )

    try:
        file_obj.seek(0)
        file_content = file_obj.read()
        records = parse_utility_csv(file_content, data_source, user)
        
        evaluate_records_suspicion(records)

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
                
        raw_ingest.status = 'done'
        raw_ingest.save()
        
        return Response({
            "message": "Successfully ingested Utility CSV.",
            "records_created": len(records)
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        traceback.print_exc()
        raw_ingest.status = 'failed'
        raw_ingest.save()
        return Response({"error": f"Failed to ingest Utility CSV: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def ingest_travel_csv(request):
    tenant, user = get_or_create_demo_tenant_user()
    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({"error": "No file uploaded. Use parameter name 'file'."}, status=status.HTTP_400_BAD_REQUEST)

    data_source, _ = DataSource.objects.get_or_create(tenant=tenant, source_type='TRAVEL')
    
    raw_ingest = RawIngestion.objects.create(
        source=data_source,
        raw_file=file_obj,
        status='processing'
    )

    try:
        file_obj.seek(0)
        file_content = file_obj.read()
        records = parse_travel_csv(file_content, data_source, user)
        
        evaluate_records_suspicion(records)

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
                
        raw_ingest.status = 'done'
        raw_ingest.save()
        
        return Response({
            "message": "Successfully ingested Corporate Travel CSV.",
            "records_created": len(records)
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        traceback.print_exc()
        raw_ingest.status = 'failed'
        raw_ingest.save()
        return Response({"error": f"Failed to ingest Travel CSV: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def list_records(request):
    """
    List all EmissionRecords with multi-tenant scopes and dynamic parameter filters.
    """
    tenant, _ = get_or_create_demo_tenant_user()
    
    # In a full production app, we would resolve tenant based on request.user.tenant
    # For this dashboard we scope globally but support a query filter
    queryset = EmissionRecord.objects.all().order_by('-created_at')
    
    # Query filters
    tenant_param = request.query_params.get('tenant')
    status_param = request.query_params.get('status')
    scope_param = request.query_params.get('scope')
    category_param = request.query_params.get('category')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    is_suspicious = request.query_params.get('is_suspicious')
    
    if tenant_param:
        queryset = queryset.filter(tenant_id=tenant_param)
    else:
        # Default to demo tenant to guarantee safety
        queryset = queryset.filter(tenant=tenant)
        
    if status_param:
        queryset = queryset.filter(status=status_param)
    if scope_param:
        queryset = queryset.filter(scope=scope_param)
    if category_param:
        queryset = queryset.filter(category=category_param)
    if start_date:
        queryset = queryset.filter(period_start__gte=start_date)
    if end_date:
        queryset = queryset.filter(period_end__lte=end_date)
    if is_suspicious:
        queryset = queryset.filter(is_suspicious=(is_suspicious.lower() == 'true'))

    serializer = EmissionRecordSerializer(queryset, many=True)
    return Response(serializer.data)

@api_view(['PATCH'])
def approve_record(request, pk):
    tenant, user = get_or_create_demo_tenant_user()
    record = get_object_or_404(EmissionRecord, pk=pk, tenant=tenant)
    
    if record.status == 'approved':
        return Response({"error": "This carbon record has already been approved and cannot be updated again."}, status=status.HTTP_400_BAD_REQUEST)
        
    before_state = EmissionRecordSerializer(record).data
    
    with transaction.atomic():
        record.status = 'approved'
        record.reviewed_by = user
        record.reviewed_at = timezone.now()
        record.save()
        
        after_state = EmissionRecordSerializer(record).data
        create_audit_entry(
            record=record,
            action='approved',
            user=user,
            before_state=before_state,
            after_state=after_state
        )
        
    return Response(after_state)

@api_view(['PATCH'])
def reject_record(request, pk):
    tenant, user = get_or_create_demo_tenant_user()
    record = get_object_or_404(EmissionRecord, pk=pk, tenant=tenant)
    
    reason = request.data.get('reason', '').strip()
    if not reason:
        return Response({"error": "A rejection reason must be provided."}, status=status.HTTP_400_BAD_REQUEST)
        
    before_state = EmissionRecordSerializer(record).data
    
    with transaction.atomic():
        record.status = 'rejected'
        record.reviewed_by = user
        record.reviewed_at = timezone.now()
        
        # Log the rejection details into the suspicion trail
        rejection_marker = f"Rejected by Analyst: {reason}"
        if record.suspicion_reason:
            record.suspicion_reason = f"{record.suspicion_reason}; {rejection_marker}"
        else:
            record.suspicion_reason = rejection_marker
        record.is_suspicious = True
        record.save()
        
        after_state = EmissionRecordSerializer(record).data
        create_audit_entry(
            record=record,
            action='rejected',
            user=user,
            before_state=before_state,
            after_state=after_state
        )
        
    return Response(after_state)

@api_view(['GET'])
def get_record_audit(request, pk):
    tenant, _ = get_or_create_demo_tenant_user()
    record = get_object_or_404(EmissionRecord, pk=pk, tenant=tenant)
    
    logs = AuditLog.objects.filter(record=record).order_by('-changed_at')
    serializer = AuditLogSerializer(logs, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_dashboard_summary(request):
    """
    Returns metrics aggregated over all records for the tenant.
    All carbon volumes are returned in kgCO2e.
    """
    tenant, _ = get_or_create_demo_tenant_user()
    tenant_records = EmissionRecord.objects.filter(tenant=tenant)
    
    # Counts
    total_records = tenant_records.count()
    pending_count = tenant_records.filter(status='pending_review').count()
    approved_count = tenant_records.filter(status='approved').count()
    rejected_count = tenant_records.filter(status='rejected').count()
    suspicious_count = tenant_records.filter(is_suspicious=True).count()
    
    # Sums (in kgCO2e)
    # Total footprint over all records vs approved records only
    total_footprint = tenant_records.aggregate(models.Sum('normalized_value_kg_co2e'))['normalized_value_kg_co2e__sum'] or Decimal('0')
    approved_footprint = tenant_records.filter(status='approved').aggregate(models.Sum('normalized_value_kg_co2e'))['normalized_value_kg_co2e__sum'] or Decimal('0')
    
    # Footprint breakdown by Scope
    scope1 = tenant_records.filter(scope=1).aggregate(models.Sum('normalized_value_kg_co2e'))['normalized_value_kg_co2e__sum'] or Decimal('0')
    scope2 = tenant_records.filter(scope=2).aggregate(models.Sum('normalized_value_kg_co2e'))['normalized_value_kg_co2e__sum'] or Decimal('0')
    scope3 = tenant_records.filter(scope=3).aggregate(models.Sum('normalized_value_kg_co2e'))['normalized_value_kg_co2e__sum'] or Decimal('0')
    
    return Response({
        "tenant_name": tenant.name,
        "total_records": total_records,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "suspicious_count": suspicious_count,
        "total_footprint_kg": float(total_footprint),
        "approved_footprint_kg": float(approved_footprint),
        "scope_breakdown_kg": {
            "scope1": float(scope1),
            "scope2": float(scope2),
            "scope3": float(scope3)
        }
    })
