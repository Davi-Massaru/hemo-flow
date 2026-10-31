"""Supported inventory identities; no transfusion compatibility or substitutions."""
from .common import COMPONENT, BLOOD, require

BLOOD_TYPES=('O-','O+','A-','A+','B-','B+','AB-','AB+')

def validate_product(blood_type=BLOOD,component=COMPONENT):
    require(component==COMPONENT and blood_type in BLOOD_TYPES,'Unsupported blood component or blood type')
    return blood_type

def matches(row,blood_type):
    return row.get('blood_type',BLOOD)==blood_type
