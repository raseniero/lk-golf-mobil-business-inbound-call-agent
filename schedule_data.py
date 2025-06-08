"""
Golf Club Repair Service - Schedule and Location Data

This module contains hardcoded schedule, location, and availability data
for the mobile golf club repair service POC in Oahu, Hawaii.
"""

from datetime import datetime, time
from typing import Dict, List, Optional

# Service Areas and Locations
SERVICE_AREAS = {
    "honolulu": {
        "name": "Honolulu Area",
        "locations": [
            "Ala Moana Golf Course",
            "Moanalua Golf Club"
        ]
    },
    "windward": {
        "name": "Windward Side", 
        "locations": [
            "Ko'olau Golf Club",
            "Pali Golf Course",
            "Bayview Golf Park"
        ]
    },
    "north_shore": {
        "name": "North Shore",
        "locations": [
            "Turtle Bay Golf (Palmer & Fazio Courses)",
            "Kahuku Golf Course"
        ]
    },
    "west_side": {
        "name": "West Side",
        "locations": [
            "Ko Olina Golf Club",
            "Kapolei Golf Club", 
            "Ewa Beach Golf Club"
        ]
    },
    "central_oahu": {
        "name": "Central Oahu",
        "locations": [
            "Mililani Golf Club",
            "Pearl Country Club",
            "Hawaii Country Club"
        ]
    },
    "east_side": {
        "name": "East Side",
        "locations": [
            "Hawaii Kai Golf Course",
            "Waialae Country Club"
        ]
    }
}

# July 2024 Schedule Matrix (mobile service location schedule)
JULY_SCHEDULE = {
    "Ala Moana Golf Course": [1],
    "Moanalua Golf Club": [2, 26],
    "Ko'olau Golf Club": [3, 25],
    "Pali Golf Course": [4, 24],
    "Bayview Golf Park": [5, 23],
    "Turtle Bay Golf": [6, 22],
    "Kahuku Golf Course": [7, 21],
    "Ko Olina Golf Club": [8, 20],
    "Kapolei Golf Club": [9, 19],
    "Ewa Beach Golf Club": [10, 18],
    "Mililani Golf Club": [11, 17],
    "Pearl Country Club": [12, 16],
    "Hawaii Country Club": [13, 15],
    "Hawaii Kai Golf Course": [14]
}

# Weekly Time Slot Availability
WEEKLY_SCHEDULE = {
    "monday": {
        "morning": {"time": "9AM-12PM", "available": True},
        "afternoon": {"time": "1PM-5PM", "available": True},
        "evening": {"time": "6PM-8PM", "available": False}
    },
    "tuesday": {
        "morning": {"time": "9AM-12PM", "available": True},
        "afternoon": {"time": "1PM-5PM", "available": False},
        "evening": {"time": "6PM-8PM", "available": True}
    },
    "wednesday": {
        "morning": {"time": "9AM-12PM", "available": False},
        "afternoon": {"time": "1PM-5PM", "available": True},
        "evening": {"time": "6PM-8PM", "available": True}
    },
    "thursday": {
        "morning": {"time": "9AM-12PM", "available": True},
        "afternoon": {"time": "1PM-5PM", "available": True},
        "evening": {"time": "6PM-8PM", "available": False}
    },
    "friday": {
        "morning": {"time": "9AM-12PM", "available": True},
        "afternoon": {"time": "1PM-5PM", "available": False},
        "evening": {"time": "6PM-8PM", "available": True}
    },
    "saturday": {
        "morning": {"time": "9AM-12PM", "available": False},
        "afternoon": {"time": "1PM-5PM", "available": True},
        "evening": {"time": "6PM-8PM", "available": True}
    },
    "sunday": {
        "morning": {"time": "9AM-12PM", "available": False},
        "afternoon": {"time": "1PM-5PM", "available": False},
        "evening": {"time": "6PM-8PM", "available": False}
    }
}

# Service Information with Duration Estimates
SERVICES = {
    "club_repair": {
        "name": "Club Repair",
        "description": "Fix broken club heads, shaft repairs",
        "price_range": "$25-75",
        "duration_minutes": (30, 60),
        "duration_display": "30-60 min"
    },
    "regripping": {
        "name": "Regripping", 
        "description": "Replace worn grips on clubs",
        "price_range": "$15-25 per grip",
        "duration_minutes": (15, 20),
        "duration_display": "15-20 min per club"
    },
    "shaft_replacement": {
        "name": "Shaft Replacement",
        "description": "Replace damaged or upgrade shafts", 
        "price_range": "$50-150",
        "duration_minutes": (45, 90),
        "duration_display": "45-90 min"
    },
    "loft_lie_adjustment": {
        "name": "Loft/Lie Adjustment",
        "description": "Adjust club angles for better fit",
        "price_range": "$20-30", 
        "duration_minutes": (15, 30),
        "duration_display": "15-30 min"
    },
    "cleaning_polish": {
        "name": "Club Cleaning & Polish",
        "description": "Professional cleaning and restoration",
        "price_range": "$10-20",
        "duration_minutes": (20, 30),
        "duration_display": "20-30 min"
    },
    "equipment_assessment": {
        "name": "Equipment Assessment",
        "description": "Evaluate club condition and recommendations", 
        "price_range": "Free with service",
        "duration_minutes": (15, 15),
        "duration_display": "15 min"
    }
}

# Helper Functions
def get_available_locations() -> List[str]:
    """Get all available service locations."""
    locations = []
    for area in SERVICE_AREAS.values():
        locations.extend(area["locations"])
    return locations

def get_locations_by_area(area_key: str) -> List[str]:
    """Get locations for a specific service area."""
    if area_key in SERVICE_AREAS:
        return SERVICE_AREAS[area_key]["locations"]
    return []

def is_location_available_on_date(location: str, day: int) -> bool:
    """Check if a location is available on a specific day in July."""
    if location in JULY_SCHEDULE:
        return day in JULY_SCHEDULE[location]
    return False

def get_available_time_slots(day_of_week: str) -> Dict[str, Dict]:
    """Get available time slots for a specific day of the week."""
    day = day_of_week.lower()
    if day in WEEKLY_SCHEDULE:
        return {
            slot: details for slot, details in WEEKLY_SCHEDULE[day].items() 
            if details["available"]
        }
    return {}

def get_service_duration(service_key: str) -> Optional[tuple]:
    """Get duration range for a specific service in minutes."""
    if service_key in SERVICES:
        return SERVICES[service_key]["duration_minutes"]
    return None

def get_all_services() -> Dict[str, Dict]:
    """Get all available services with their details."""
    return SERVICES

def find_location_area(location: str) -> Optional[str]:
    """Find which area a location belongs to."""
    for area_key, area_data in SERVICE_AREAS.items():
        if location in area_data["locations"]:
            return area_data["name"]
    return None