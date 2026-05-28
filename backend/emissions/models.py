from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    role = models.CharField(
        max_length=20, 
        choices=[('analyst', 'Analyst'), ('admin', 'Admin')], 
        default='analyst'
    )

    def __str__(self):
        return f"{self.username} ({self.role}) - {self.tenant.name if self.tenant else 'No Tenant'}"

class DataSource(models.Model):
    SOURCE_TYPES = [
        ('SAP', 'SAP Fuel & Procurement'),
        ('UTILITY', 'Utility Electricity'),
        ('TRAVEL', 'Corporate Travel'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_type} Source for {self.tenant.name}"

class RawIngestion(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
        ('done', 'Done'),
    ]
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='ingestions')
    raw_file = models.FileField(upload_to='raw_ingestions/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    ingested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ingestion {self.id} ({self.status}) for {self.source.source_type}"

class EmissionRecord(models.Model):
    SCOPE_CHOICES = [
        (1, 'Scope 1'),
        (2, 'Scope 2'),
        (3, 'Scope 3'),
    ]
    CATEGORY_CHOICES = [
        ('fuel', 'Fuel Combustion'),
        ('electricity', 'Grid Electricity'),
        ('flight', 'Air Travel'),
        ('hotel', 'Hotel Stays'),
        ('ground', 'Ground Transportation'),
    ]
    STATUS_CHOICES = [
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='emission_records')
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    
    activity_value = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit = models.CharField(max_length=20)
    normalized_value_kg_co2e = models.DecimalField(max_digits=18, decimal_places=4)
    emission_factor_used = models.DecimalField(max_digits=12, decimal_places=6)
    
    period_start = models.DateField()
    period_end = models.DateField()
    source_ref = models.CharField(max_length=255)  # E.g. raw row/expense number
    
    is_suspicious = models.BooleanField(default=False)
    suspicion_reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category.title()} (Scope {self.scope}) - {self.normalized_value_kg_co2e} kgCO2e"

class AuditLog(models.Model):
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50)  # E.g., 'ingested', 'approved', 'rejected'
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.action.upper()} on Record {self.record.id} by {self.changed_by.username if self.changed_by else 'System'}"
