"""
OCR Service - reads request from stdin and returns OCR results
"""

import json
import sys
import os
import time

# Add parent dir to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

start_time = time.time()
import_start = time.time()
from ocr.extractor import extract_ocr
from config import OCR_CONFIDENCE_THRESHOLD
import_duration = time.time() - import_start


def process_ocr_request(request_data):
    """
    Process OCR request
    
    Expected input:
    {
        'imagePath': str,
        'documentType': 'passport' | 'visa' | ...
    }
    """
    try:
        image_path = request_data.get('imagePath')
        document_type = request_data.get('documentType', 'passport')
        
        if not image_path:
            return {
                'success': False,
                'error': 'imagePath is required',
                'documentType': document_type,
                'fields': {},
                'confidence': 0
            }
        
        # Extract OCR with timing
        ocr_start = time.time()
        result = extract_ocr(image_path, document_type)
        ocr_duration = time.time() - ocr_start
        
        # Add document type to result
        result['documentType'] = document_type
        result['success'] = result.get('status') in ['success', 'partial']
        result['timing'] = {
            'import_duration_sec': round(import_duration, 2),
            'ocr_duration_sec': round(ocr_duration, 2),
            'total_seconds': round(time.time() - start_time, 2)
        }
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'documentType': request_data.get('documentType', 'unknown'),
            'fields': {},
            'confidence': 0,
            'timing': {
                'import_duration_sec': round(import_duration, 2),
                'total_seconds': round(time.time() - start_time, 2)
            }
        }


if __name__ == '__main__':
    try:
        # Read request from stdin
        request_data = json.load(sys.stdin)
        result = process_ocr_request(request_data)
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'Invalid JSON: {str(e)}'}))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
