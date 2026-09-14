"""Fast, dependency-local regression tests for the AI service contracts.

Run with: ai/.venv/bin/python -m unittest discover -s ai/tests -v
"""

import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocr.extractor import extract_ocr, _parse_fields_for_document  # noqa: E402
from validation.validator import validate_document  # noqa: E402
from services.risk_calculator import calculate_risk_score  # noqa: E402
from tampering.detector import detect_tampering  # noqa: E402


class ServiceContractTests(unittest.TestCase):
    def test_ocr_contract_for_all_document_types(self):
        text = 'JOHN DOE\nA1234567\nIND\n15/03/1990\nM\n15/03/2030'
        for document_type in ('passport', 'visa', 'national_id', 'driving_license', 'permit'):
            fields = _parse_fields_for_document(text, document_type)
            self.assertTrue(fields)
            self.assertIsInstance(fields, dict)

    def test_ocr_rejects_unsupported_type_and_missing_file(self):
        self.assertEqual(extract_ocr('/tmp/missing.png', 'unknown')['status'], 'failed')
        self.assertEqual(extract_ocr('/tmp/missing.png', 'passport')['confidence'], 0)

    def test_ocr_does_not_turn_document_headings_into_a_person_name(self):
        fields = _parse_fields_for_document(
            'REPUBLIC OF EXAMPLE\nPASSPORT\nDocument number: A1234567\n'
            'Date of expiry: 15/03/2030', 'passport'
        )
        self.assertNotIn('name', fields)
        self.assertEqual(fields['passportNumber'], 'A1234567')

    def test_ocr_prefers_labelled_values_without_cross_field_capture(self):
        fields = _parse_fields_for_document(
            'Full Name: Jane Q. Citizen\nID Number: AB12345678\n'
            'Date of birth: 1990-03-15\nExpiry date: 2030-03-15', 'national_id'
        )
        self.assertEqual(fields['fullName'], 'JANE Q. CITIZEN')
        self.assertEqual(fields['idNumber'], 'AB12345678')
        self.assertEqual(fields['dateOfBirth'], '1990-03-15')

    def test_validation_statuses_and_iso_dates(self):
        valid = {
            'name': 'JOHN DOE', 'passportNumber': 'A1234567', 'nationality': 'IND',
            'dateOfBirth': '1990-03-15', 'gender': 'M', 'expiryDate': '2030-03-15',
        }
        self.assertEqual(validate_document(valid, 'passport')['status'], 'valid')
        expired = dict(valid, expiryDate='2020-01-01')
        self.assertEqual(validate_document(expired, 'passport')['status'], 'failed')
        self.assertEqual(validate_document({}, 'unsupported')['status'], 'failed')

    def test_risk_requires_review_for_uncertainty(self):
        result = calculate_risk_score(
            {'confidence': 0.8},
            {'isValid': True, 'violations': [{'field': 'nationality', 'severity': 'warning'}]},
            None,
            None,
        )
        self.assertTrue(result['requiresHumanReview'])
        self.assertGreaterEqual(result['riskScore'], 0)
        self.assertLessEqual(result['riskScore'], 100)

    def test_tampering_missing_file_has_stable_evidence(self):
        result = detect_tampering('/tmp/missing-document.png')
        self.assertEqual(result['status'], 'failed')
        self.assertIsInstance(result['evidence'], list)

    def test_tampering_reports_jpeg_ela_metrics(self):
        """JPEG analyses expose localized-forensics data for the review UI."""
        image = Image.fromarray(np.full((900, 1200, 3), 210, dtype=np.uint8))
        # Add document-like dark text lines, then save a real JPEG input.
        pixels = np.asarray(image).copy()
        pixels[200:205, 100:1100] = 35
        image = Image.fromarray(pixels)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as temp_file:
            image.save(temp_file.name, format='JPEG', quality=90)
            result = detect_tampering(temp_file.name)

        ela = result['metrics']['errorLevelAnalysis']
        self.assertTrue(ela['available'])
        self.assertIn('hasLocalizedAnomaly', ela)
        self.assertIsInstance(ela['suspiciousRegions'], list)

    def test_tampering_flags_localized_recompression_in_jpeg(self):
        """A separately compressed pasted block is returned as review evidence."""
        rng = np.random.default_rng(2)
        pixels = np.clip(210 + rng.normal(0, 8, (900, 1200, 3)), 0, 255).astype(np.uint8)
        for row in range(150, 750, 55):
            pixels[row:row + 3, 80:1120] = 35
        image = Image.fromarray(pixels)
        encoded = BytesIO()
        image.save(encoded, format='JPEG', quality=92)
        encoded.seek(0)
        image = Image.open(encoded).convert('RGB')

        patch = image.crop((450, 300, 800, 600))
        patch_bytes = BytesIO()
        patch.save(patch_bytes, format='JPEG', quality=10)
        patch_bytes.seek(0)
        image.paste(Image.open(patch_bytes).convert('RGB'), (450, 300))

        with tempfile.NamedTemporaryFile(suffix='.jpg') as temp_file:
            image.save(temp_file.name, format='JPEG', quality=92)
            result = detect_tampering(temp_file.name)

        self.assertTrue(result['tamperingDetected'])
        finding = next(item for item in result['findings'] if item['type'] == 'localized_compression_anomaly')
        self.assertTrue(finding['regions'])


if __name__ == '__main__':
    unittest.main()
