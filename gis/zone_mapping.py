"""Map between display names, slugs, and GeoJSON zone ids."""

ZONE_DISPLAY_TO_SLUG = {
    "North Delhi": "north-delhi",
    "South Delhi": "south-delhi",
    "East Delhi": "east-delhi",
    "West Delhi": "west-delhi",
    "Central Delhi": "central-delhi",
}

ZONE_SLUG_TO_DISPLAY = {v: k for k, v in ZONE_DISPLAY_TO_SLUG.items()}

ZONE_GEO_ID_TO_DISPLAY = {
    "north_delhi": "North Delhi",
    "south_delhi": "South Delhi",
    "east_delhi": "East Delhi",
    "west_delhi": "West Delhi",
    "central_delhi": "Central Delhi",
}
