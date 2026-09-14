"""
Face Verification
Compare faces from document and person photos
"""

import json
import sys
from pathlib import Path
import numpy as np

try:
    import face_recognition
except ImportError:
    face_recognition = None

try:
    from PIL import Image
except ImportError:
    Image = None


def verify_face_match(document_image_path, person_image_path, threshold=0.6):
    """
    Verify if the face in document matches the person photo
    
    Args:
        document_image_path: Path to document image
        person_image_path: Path to person's photo
        threshold: Similarity threshold (default 0.6)
    
    Returns:
        dict: {
            'faceDetectedInDocument': bool,
            'faceDetectedInPerson': bool,
            'matchStatus': 'match' | 'no_match' | 'inconclusive' | 'not_verified',
            'similarity': 0-1,
            'confidence': 0-1,
            'status': 'success' | 'failed'
        }
    """
    
    if face_recognition is None or Image is None:
        return {
            'status': 'failed',
            'error': 'face_recognition library not installed',
            'faceDetectedInDocument': False,
            'faceDetectedInPerson': False,
            'matchStatus': 'not_verified',
            'similarity': 0,
            'confidence': 0
        }
    
    # Validate paths
    if not Path(document_image_path).exists():
        return {
            'status': 'failed',
            'error': f'Document image not found: {document_image_path}',
            'faceDetectedInDocument': False,
            'faceDetectedInPerson': False,
            'matchStatus': 'not_verified',
            'similarity': 0,
            'confidence': 0
        }
    
    if not Path(person_image_path).exists():
        return {
            'status': 'failed',
            'error': f'Person image not found: {person_image_path}',
            'faceDetectedInDocument': False,
            'faceDetectedInPerson': False,
            'matchStatus': 'not_verified',
            'similarity': 0,
            'confidence': 0
        }
    
    try:
        quality_warning = _quality_warning(document_image_path)
        person_quality_warning = _quality_warning(person_image_path)
        if quality_warning or person_quality_warning:
            warnings = [item for item in (quality_warning, person_quality_warning) if item]
            return {
                'status': 'success', 'faceDetectedInDocument': False,
                'faceDetectedInPerson': False, 'matchStatus': 'inconclusive',
                'similarity': 0, 'confidence': 0.2,
                'warning': '; '.join(warnings), 'qualityGate': 'failed'
            }

        # Load document image
        doc_image = face_recognition.load_image_file(document_image_path)
        doc_face_locations = face_recognition.face_locations(doc_image)
        doc_face_encodings = face_recognition.face_encodings(doc_image)
        
        # Load person image
        person_image = face_recognition.load_image_file(person_image_path)
        person_face_locations = face_recognition.face_locations(person_image)
        person_face_encodings = face_recognition.face_encodings(person_image)
        
        # Check if faces detected
        face_detected_in_doc = len(doc_face_encodings) > 0
        face_detected_in_person = len(person_face_encodings) > 0
        
        # Handle cases where face not detected
        if not face_detected_in_doc or not face_detected_in_person:
            return {
                'status': 'success',
                'faceDetectedInDocument': face_detected_in_doc,
                'faceDetectedInPerson': face_detected_in_person,
                'matchStatus': 'not_verified',
                'similarity': 0,
                'confidence': 0.1,
                'warning': 'A single clear face was not detected in both images.',
                'qualityGate': 'passed'
            }
        
        # Handle multiple faces
        if len(doc_face_encodings) > 1:
            return {
                'status': 'success',
                'faceDetectedInDocument': True,
                'faceDetectedInPerson': face_detected_in_person,
                'matchStatus': 'inconclusive',
                'similarity': 0,
                'confidence': 0.7,
                'warning': f'Multiple faces detected in document ({len(doc_face_encodings)}); manual selection is required.',
                'qualityGate': 'passed'
            }
        
        if len(person_face_encodings) > 1:
            return {
                'status': 'success',
                'faceDetectedInDocument': face_detected_in_doc,
                'faceDetectedInPerson': True,
                'matchStatus': 'inconclusive',
                'similarity': 0,
                'confidence': 0.7,
                'warning': f'Multiple faces detected in person photo ({len(person_face_encodings)}); manual selection is required.',
                'qualityGate': 'passed'
            }
        
        # Compare face encodings
        doc_face_encoding = doc_face_encodings[0]
        person_face_encoding = person_face_encodings[0]
        
        # Calculate face distance
        face_distance = face_recognition.face_distance([doc_face_encoding], person_face_encoding)[0]
        
        # Convert distance to similarity (0-1, where 1 is perfect match)
        # face_distance is typically 0-0.6 for matches, 0.6-1.0+ for non-matches
        similarity = 1 - face_distance
        similarity = max(0, min(1, similarity))
        
        # Determine match status
        if similarity >= threshold:
            match_status = 'match'
            confidence = 0.85 + (similarity - threshold) * 0.1
        elif similarity >= threshold - 0.1:
            match_status = 'inconclusive'
            confidence = 0.6
        else:
            match_status = 'no_match'
            confidence = 0.9
        
        return {
            'status': 'success',
            'faceDetectedInDocument': face_detected_in_doc,
            'faceDetectedInPerson': face_detected_in_person,
            'matchStatus': match_status,
            'similarity': round(similarity, 3),
            'confidence': round(min(confidence, 1.0), 2),
            'details': {
                'faceDistanceScore': round(float(face_distance), 3),
                'threshold': threshold,
                'face_locations_doc': len(doc_face_locations),
                'face_locations_person': len(person_face_locations)
            },
            'qualityGate': 'passed',
            'disclaimer': 'Face similarity is assistive and should be reviewed with the source images.'
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'faceDetectedInDocument': False,
            'faceDetectedInPerson': False,
            'matchStatus': 'not_verified',
            'similarity': 0,
            'confidence': 0
        }


def verify_face(document_image_path, person_image_path, threshold=0.6):
    """Main entry point for face verification"""
    return verify_face_match(document_image_path, person_image_path, threshold)


def _quality_warning(image_path):
    """Reject obviously unusable inputs before embedding comparison."""
    try:
        with Image.open(image_path) as image:
            width, height = image.size
            if min(width, height) < 160:
                return f'Image resolution is too low ({width}x{height}).'
            grayscale = np.asarray(image.convert('L'))
            if float(grayscale.std()) < 8:
                return 'Image has insufficient contrast for reliable face verification.'
    except Exception:
        return 'Image could not be read for quality assessment.'
    return None


if __name__ == '__main__':
    if len(sys.argv) > 2:
        result = verify_face(sys.argv[1], sys.argv[2])
        print(json.dumps(result))
    else:
        print(json.dumps({'error': 'Two image paths required: document_image person_image'}))
