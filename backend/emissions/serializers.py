from rest_framework import serializers
from emissions.models import Tenant, User, DataSource, RawIngestion, EmissionRecord, AuditLog

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'tenant']

class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ['id', 'tenant', 'source_type', 'created_at']

class RawIngestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawIngestion
        fields = ['id', 'source', 'raw_file', 'status', 'ingested_at']

class AuditLogSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)
    changed_by_role = serializers.CharField(source='changed_by.role', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'record', 'action', 'changed_by', 'changed_by_username', 
            'changed_by_role', 'changed_at', 'before_state', 'after_state'
        ]

class EmissionRecordSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source='source.source_type', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'tenant', 'tenant_name', 'source', 'source_type', 'scope', 'category',
            'activity_value', 'activity_unit', 'normalized_value_kg_co2e',
            'emission_factor_used', 'period_start', 'period_end', 'source_ref',
            'is_suspicious', 'suspicion_reason', 'status', 'reviewed_by',
            'reviewed_by_username', 'reviewed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['normalized_value_kg_co2e', 'is_suspicious', 'suspicion_reason']
