"""
Face Verification Service - reads request from stdin and returns face matching results
"""

import json
import sys
import os

# Add parent dir to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from face.verifier import verify_face


def process_face_verification_request(request_data):
    """
    Process face verification request
    
    Expected input:
    {
        'documentImagePath': str,
        'personImagePath': str,
        'threshold': float (optional, default 0.6)
    }
    """
    try:
        document_path = request_data.get('documentImagePath')
        person_path = request_data.get('personImagePath')
        threshold = float(request_data.get('threshold', 0.6))
        if not 0.4 <= threshold <= 0.9:
            return {
                'success': False, 'error': 'threshold must be between 0.4 and 0.9',
                'faceDetectedInDocument': False, 'faceDetectedInPerson': False,
                'matchStatus': 'not_verified', 'similarity': 0, 'confidence': 0,
            }
        
        if not document_path or not person_path:
            return {
                'success': False,
                'error': 'documentImagePath and personImagePath are required',
                'faceDetectedInDocument': False,
                'faceDetectedInPerson': False,
                'matchStatus': 'not_verified',
                'similarity': 0,
                'confidence': 0
            }
        
        # Verify face match
        result = verify_face(document_path, person_path, threshold)
        result['success'] = result.get('status') == 'success'
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'faceDetectedInDocument': False,
            'faceDetectedInPerson': False,
            'matchStatus': 'not_verified',
            'similarity': 0,
            'confidence': 0
        }


if __name__ == '__main__':
    try:
        # Read request from stdin
        request_data = json.load(sys.stdin)
        result = process_face_verification_request(request_data)
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'Invalid JSON: {str(e)}'}))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
