"""
Validation Service - reads request from stdin and returns validation results
"""

import json
import sys
import os

# Add parent dir to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.validator import validate_document


def process_validation_request(request_data):
    """
    Process validation request
    
    Expected input:
    {
        'fields': {
            'name': str,
            'passportNumber': str,
            'nationality': str,
            'dateOfBirth': str,
            'gender': str,
            'expiryDate': str
        },
        'documentType': 'passport' | 'visa' | ...
    }
    """
    try:
        fields = request_data.get('fields', {})
        document_type = request_data.get('documentType', 'passport')
        
        # Validate
        result = validate_document(fields, document_type)
        
        result['success'] = result.get('isValid', False)
        result['documentType'] = document_type
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'isValid': False,
            'violations': [],
            'documentType': request_data.get('documentType', 'unknown')
        }


if __name__ == '__main__':
    try:
        # Read request from stdin
        request_data = json.load(sys.stdin)
        result = process_validation_request(request_data)
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'Invalid JSON: {str(e)}'}))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
