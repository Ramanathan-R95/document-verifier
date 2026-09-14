"""
Tampering Service - reads request from stdin and returns tampering analysis results
"""

import json
import sys
import os

# Add parent dir to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tampering.detector import detect_tampering


def process_tampering_request(request_data):
    """
    Process tampering detection request
    
    Expected input:
    {
        'imagePath': str
    }
    """
    try:
        image_path = request_data.get('imagePath')
        
        if not image_path:
            return {
                'success': False,
                'error': 'imagePath is required',
                'tamperingDetected': False,
                'confidence': 0,
                'findings': [],
                'evidence': [],
            }
        
        # Detect tampering
        result = detect_tampering(image_path)
        result['success'] = result.get('status') == 'success'
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'tamperingDetected': False,
            'confidence': 0,
            'findings': [],
            'evidence': [],
        }


if __name__ == '__main__':
    try:
        # Read request from stdin
        request_data = json.load(sys.stdin)
        result = process_tampering_request(request_data)
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'Invalid JSON: {str(e)}'}))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
