import math

# Top 30 global airports by passenger traffic or carbon ESG significance
AIRPORTS = {
    'ATL': (33.6407, -84.4277),
    'PEK': (40.0799, 116.5971),
    'LAX': (33.9416, -118.4085),
    'HND': (35.5494, 139.7798),
    'ORD': (41.9742, -87.9073),
    'LHR': (51.4700, -0.4543),
    'CDG': (49.0097, 2.5479),
    'DFW': (32.8998, -97.0403),
    'PVG': (31.1443, 121.8083),
    'DXB': (25.2532, 55.3657),
    'AMS': (52.3105, 4.7683),
    'DEL': (28.5562, 77.1000),
    'BOM': (19.0896, 72.8656),
    'SIN': (1.3644, 103.9915),
    'SYD': (-33.9461, 151.1772),
    'JFK': (40.6413, -73.7781),
    'SFO': (37.6213, -122.3790),
    'DEN': (39.8561, -104.6737),
    'ICN': (37.4602, 126.4407),
    'MAD': (40.4839, -3.5679),
    'FRA': (50.0379, 8.5622),
    'CAN': (23.3924, 113.2988),
    'CLT': (35.2140, -80.9431),
    'LAS': (36.0840, -115.1537),
    'PHX': (33.4352, -112.0101),
    'MCO': (28.4287, -81.3160),
    'SEA': (47.4502, -122.3088),
    'MIA': (25.7959, -80.2870),
    'EWR': (40.6895, -74.1745),
    'YYZ': (43.6777, -79.6248),
    'NRT': (35.7720, 140.3929),
    'MUC': (48.3538, 11.7861),
}

def calculate_distance_km(origin, destination):
    """
    Calculates the great-circle distance between two airports in kilometers
    using the Haversine formula.
    """
    orig = str(origin).strip().upper()
    dest = str(destination).strip().upper()

    if orig not in AIRPORTS:
        raise ValueError(f"Origin airport code '{orig}' not in local airport database.")
    if dest not in AIRPORTS:
        raise ValueError(f"Destination airport code '{dest}' not in local airport database.")

    lat1, lon1 = AIRPORTS[orig]
    lat2, lon2 = AIRPORTS[dest]

    # Earth radius in kilometers
    R = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * 
         math.sin(delta_lambda / 2.0) ** 2)
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = R * c

    return round(distance, 2)
