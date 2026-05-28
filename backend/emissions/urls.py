from django.urls import path
from emissions import views

urlpatterns = [
    # Data Ingestion
    path('ingest/sap/', views.ingest_sap_csv, name='ingest_sap'),
    path('ingest/utility/', views.ingest_utility_csv, name='ingest_utility'),
    path('ingest/travel/', views.ingest_travel_csv, name='ingest_travel'),
    
    # Emission Records Management
    path('records/', views.list_records, name='list_records'),
    path('records/<int:pk>/approve/', views.approve_record, name='approve_record'),
    path('records/<int:pk>/reject/', views.reject_record, name='reject_record'),
    path('records/<int:pk>/audit/', views.get_record_audit, name='record_audit'),
    
    # Business Intelligence Summary Dashboard
    path('dashboard/summary/', views.get_dashboard_summary, name='dashboard_summary'),
]
