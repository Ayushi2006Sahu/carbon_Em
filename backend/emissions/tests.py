from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, date
from emissions.models import Tenant, DataSource, EmissionRecord
from emissions.utils import calculate_distance_km
from emissions.parsers.sap_parser import parse_sap_csv
from emissions.parsers.utility_parser import parse_utility_csv
from emissions.parsers.travel_parser import parse_travel_csv
from emissions.suspicion import evaluate_records_suspicion

class EmissionsCalculatorTests(TestCase):
    """
    Test suite for environmental calculations and parsers.
    """
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Acme Corporation Test")
        self.sap_source = DataSource.objects.create(tenant=self.tenant, source_type="SAP")
        self.util_source = DataSource.objects.create(tenant=self.tenant, source_type="UTILITY")
        self.travel_source = DataSource.objects.create(tenant=self.tenant, source_type="TRAVEL")

    def test_haversine_distance_calculation(self):
        """
        Verify geodesic distance calculations for top airports.
        """
        # Delhi (DEL) to London Heathrow (LHR) should be roughly 6,700-6,800 km
        dist = calculate_distance_km('DEL', 'LHR')
        self.assertTrue(6700 <= dist <= 6800)
        
        # New York (JFK) to Los Angeles (LAX) should be roughly 3,900-4,000 km
        dist_us = calculate_distance_km('JFK', 'LAX')
        self.assertTrue(3900 <= dist_us <= 4000)

        # Invalid code must raise ValueError
        with self.assertRaises(ValueError):
            calculate_distance_km('XYZ', 'LHR')

    def test_sap_parser_and_unit_conversions(self):
        """
        Verify SAP parser maps columns, normalizes units to KG, and identifies Scopes.
        """
        csv_data = (
            "MANDT,WERKS,MATNR,MEINS,MENGE,NETWR,WAERS,BLDAT\n"
            "100,1000,MAT-FUEL-DIESEL,L,100.00,250.00,EUR,15.05.2026\n"
            "100,1100,MAT-FUEL-PETROL,GAL,50.00,300.00,EUR,18.05.2026\n"
            "100,1200,MAT-PROC-STEEL,KG,1000.00,4000.00,EUR,20.05.2026\n"
            "100,1000,MAT-FUEL-DIESEL,BOX,10.00,100.00,EUR,22.05.2026\n"
        ).encode('utf-8')

        records = parse_sap_csv(csv_data, self.sap_source)
        self.assertEqual(len(records), 4)

        # Row 1: Diesel Liter (Scope 1, Category: fuel)
        r1 = records[0]
        self.assertEqual(r1.scope, 1)
        self.assertEqual(r1.category, 'fuel')
        self.assertEqual(r1.activity_value, Decimal('100.00'))
        self.assertEqual(r1.activity_unit, 'L')
        # CO2: 100 L * 2.68 = 268.0 kgCO2e
        self.assertEqual(r1.normalized_value_kg_co2e, Decimal('268.00'))
        self.assertFalse(r1.is_suspicious)

        # Row 2: Petrol Gallon (Scope 1, normalized)
        # 50 Gallons * 3.78541 = 189.27 Liters -> CO2: 189.27 * 2.31 = 437.2 kgCO2e
        r2 = records[1]
        self.assertEqual(r2.scope, 1)
        self.assertEqual(r2.activity_unit, 'GAL')
        self.assertAlmostEqual(float(r2.normalized_value_kg_co2e), 437.214, places=2)

        # Row 3: Steel KG (Scope 3, Category: fuel/catch-all)
        r3 = records[2]
        self.assertEqual(r3.scope, 3)
        self.assertEqual(r3.activity_unit, 'KG')
        # CO2: 1000 kg * 1.25 = 1250 kgCO2e
        self.assertEqual(r3.normalized_value_kg_co2e, Decimal('1250.00'))

        # Row 4: Bad Unit (triggers suspicion)
        r4 = records[3]
        self.assertTrue(r4.is_suspicious)
        self.assertIn("unit 'BOX' could not be normalized", r4.suspicion_reason)

    def test_utility_parser_electricity(self):
        """
        Verify Utility parser processes billing cycles, calculates grid factor, and flags anomalies.
        """
        csv_data = (
            "account_number,meter_id,service_address,billing_period_start,billing_period_end,kwh_consumed,peak_demand_kw,tariff_code,amount_billed\n"
            "ACCT-1,MTR-101,HQ,2025-01-01,2025-01-31,1000.00,10.0,IND,200.00\n"
            "ACCT-1,MTR-101,HQ,2025-03-01,2025-02-15,1000.00,10.0,IND,200.00\n" # Start >= End (Anomalous)
        ).encode('utf-8')

        records = parse_utility_csv(csv_data, self.util_source)
        self.assertEqual(len(records), 2)

        # Row 1: Valid Scope 2
        r1 = records[0]
        self.assertEqual(r1.scope, 2)
        self.assertEqual(r1.category, 'electricity')
        self.assertEqual(r1.activity_unit, 'kWh')
        # CO2: 1000 kWh * 0.82 = 820 kg
        self.assertEqual(r1.normalized_value_kg_co2e, Decimal('820.00'))
        self.assertFalse(r1.is_suspicious)

        # Row 2: Date Mismatch
        r2 = records[1]
        self.assertTrue(r2.is_suspicious)
        self.assertIn("Billing period start date is after or equal to the end date", r2.suspicion_reason)

    def test_travel_parser(self):
        """
        Verify Concur travel log parsing, including classes, nights, and Haversine distance computations.
        """
        csv_data = (
            "expense_id,traveler_name,travel_date,travel_type,origin,destination,distance_km,nights,travel_class,amount,currency\n"
            "EXP-1,Jane,2026-05-10,FLIGHT,DEL,LHR,,0,ECONOMY,800.00,USD\n"  # missing distance
            "EXP-2,Jane,2026-05-12,HOTEL,,,0,3,STANDARD,450.00,USD\n"
            "EXP-3,Jane,2026-05-15,GROUND,,HQ,25.00,0,DEFAULT,35.00,USD\n"
        ).encode('utf-8')

        records = parse_travel_csv(csv_data, self.travel_source)
        self.assertEqual(len(records), 3)

        # Flight DEL-LHR
        r1 = records[0]
        self.assertEqual(r1.scope, 3)
        self.assertEqual(r1.category, 'flight')
        self.assertEqual(r1.activity_unit, 'km')
        # Distance should be computed using Haversine (~6781 km)
        self.assertTrue(float(r1.activity_value) > 6700)
        # CO2: distance * 0.255
        self.assertAlmostEqual(float(r1.normalized_value_kg_co2e), float(r1.activity_value) * 0.255, places=2)

        # Hotel stay (3 nights)
        r2 = records[1]
        self.assertEqual(r2.category, 'hotel')
        self.assertEqual(r2.activity_value, Decimal('3'))
        self.assertEqual(r2.activity_unit, 'nights')
        # CO2: 3 * 31.2 = 93.6 kg
        self.assertEqual(r2.normalized_value_kg_co2e, Decimal('93.6'))

        # Ground transit
        r3 = records[2]
        self.assertEqual(r3.category, 'ground')
        self.assertEqual(r3.activity_value, Decimal('25.00'))
        # CO2: 25 * 0.21 = 5.25 kg
        self.assertEqual(r3.normalized_value_kg_co2e, Decimal('5.25'))

    def test_historical_outlier_suspicion(self):
        """
        Verify the suspicion engine flags records that are >3x historical category averages.
        """
        # Seed an approved historical baseline for the fuel category
        EmissionRecord.objects.create(
            tenant=self.tenant,
            source=self.sap_source,
            scope=1,
            category='fuel',
            activity_value=Decimal('100'),
            activity_unit='L',
            normalized_value_kg_co2e=Decimal('268.00'),  # 268 kgCO2e baseline avg
            emission_factor_used=Decimal('2.68'),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            source_ref="HIST-1",
            status="approved"
        )

        # Test records
        test_record = EmissionRecord(
            tenant=self.tenant,
            source=self.sap_source,
            scope=1,
            category='fuel',
            activity_value=Decimal('400'),
            activity_unit='L',
            normalized_value_kg_co2e=Decimal('1072.00'), # 1072 kgCO2e (>3x historical 268 avg!)
            emission_factor_used=Decimal('2.68'),
            period_start=date(2026, 5, 15),
            period_end=date(2026, 5, 15),
            source_ref="TEST-OUTLIER",
            status="pending_review"
        )

        records = [test_record]
        evaluate_records_suspicion(records)

        # Outlier check should trigger anomaly flag
        self.assertTrue(records[0].is_suspicious)
        self.assertIn("more than 3x historical average", records[0].suspicion_reason)
