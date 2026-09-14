"""
Python AI/ML services configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Service settings
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'pdf']

# OCR settings
OCR_CONFIDENCE_THRESHOLD = 0.5

# Face verification settings
FACE_SIMILARITY_THRESHOLD = 0.6
MIN_FACE_DETECTION_CONFIDENCE = 0.5

# Tampering detection settings
TAMPERING_CONFIDENCE_THRESHOLD = 0.5

# Document rules
DOCUMENT_RULES = {
    'passport': {
        'requiredFields': ['name', 'passportNumber', 'nationality', 'dateOfBirth', 'gender', 'expiryDate'],
        'idNumberPattern': r'^[A-Z0-9]{6,9}$',
    },
    'visa': {
        'requiredFields': ['visaNumber', 'visaType', 'entryValidity', 'stayDuration', 'issueDate', 'expiryDate'],
        'idNumberPattern': r'^[A-Z0-9]{6,12}$',
    },
    'national_id': {
        'requiredFields': ['fullName', 'idNumber', 'dateOfBirth', 'issueDate', 'expiryDate'],
        'idNumberPattern': r'^[A-Z0-9]{6,20}$',
    },
    'driving_license': {
        'requiredFields': ['fullName', 'licenseNumber', 'dateOfBirth', 'issueDate', 'expiryDate'],
        'idNumberPattern': r'^[A-Z0-9]{6,20}$',
    },
    'permit': {
        'requiredFields': ['holderName', 'permitNumber', 'permitType', 'issueDate', 'expiryDate'],
        'idNumberPattern': r'^[A-Z0-9]{6,20}$',
    },
}
