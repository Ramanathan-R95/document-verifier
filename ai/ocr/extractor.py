"""
Document OCR extraction for supported identity document types.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    pytesseract = None
    Image = None


EXPECTED_FIELDS = {
    'passport': ['name', 'passportNumber', 'nationality', 'dateOfBirth', 'gender', 'expiryDate'],
    'visa': ['visaNumber', 'visaType', 'entryValidity', 'stayDuration', 'issueDate', 'expiryDate'],
    'national_id': ['fullName', 'idNumber', 'dateOfBirth', 'issueDate', 'expiryDate'],
    'driving_license': ['fullName', 'licenseNumber', 'dateOfBirth', 'issueDate', 'expiryDate'],
    'permit': ['holderName', 'permitNumber', 'permitType', 'issueDate', 'expiryDate'],
}


def extract_ocr(image_path, document_type='passport'):
    """Extract fields from a document image for the requested document type."""
    document_type = (document_type or 'passport').lower()
    supported_types = {'passport', 'visa', 'national_id', 'driving_license', 'permit'}
    if document_type not in supported_types:
        return {
            'status': 'failed',
            'error': f'Unsupported document type: {document_type}',
            'fields': {},
            'confidence': 0,
            'documentType': document_type,
        }
    if not Path(image_path).exists():
        return {
            'status': 'failed',
            'error': f'Image file not found: {image_path}',
            'fields': {},
            'confidence': 0,
            'documentType': document_type,
        }

    if pytesseract is None or Image is None:
        return {
            'status': 'failed',
            'error': 'Tesseract or Pillow not installed',
            'fields': {},
            'confidence': 0,
            'documentType': document_type,
        }

    try:
        img = ImageOps.exif_transpose(Image.open(image_path))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        # OCR cost rises sharply with camera-image resolution, without improving
        # document-sized text. Keep enough pixels for small print but stay within
        # the backend service timeout.
        img.thumbnail((2200, 2200))

        raw_text, ocr_confidence, read_metadata = _read_document_text(img)
        fields = _parse_fields_for_document(raw_text, document_type)
        # Field coverage says how complete the extraction is; Tesseract's word
        # confidences say how trustworthy the underlying read was.  Combining
        # them prevents a few guessed fields from looking highly reliable.
        confidence = _calculate_confidence(fields, document_type, ocr_confidence)

        expected = EXPECTED_FIELDS[document_type]
        missing_fields = [field for field in expected if not fields.get(field)]
        warnings = _extraction_warnings(fields, expected, ocr_confidence)
        return {
            # A response with a few speculative values must not be represented as
            # a successful extraction.  Consumers can use `partial` to route it
            # to human review instead of displaying it as verified information.
            'status': 'success' if not missing_fields and confidence >= 0.55 else 'partial',
            'fields': fields,
            'confidence': confidence,
            'rawText': raw_text,
            'documentType': document_type,
            'missingFields': missing_fields,
            'warnings': warnings,
            'preprocessing': read_metadata,
        }
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'fields': {},
            'confidence': 0,
            'documentType': document_type,
        }


def _parse_fields_for_document(text, document_type):
    doc_type = (document_type or 'passport').lower()
    text_normalized = text.replace('\r', '\n')

    if doc_type == 'passport':
        return _extract_passport_fields(text_normalized)
    if doc_type == 'visa':
        return _extract_visa_fields(text_normalized)
    if doc_type == 'national_id':
        return _extract_national_id_fields(text_normalized)
    if doc_type == 'driving_license':
        return _extract_driving_license_fields(text_normalized)
    if doc_type == 'permit':
        return _extract_permit_fields(text_normalized)
    return _extract_passport_fields(text_normalized)


def _extract_passport_fields(text):
    mrz = _extract_passport_mrz(text)
    fields = {
        'name': _find_passport_name(text) or mrz.get('name') or _first_meaningful_name(text),
        'passportNumber': _find_labeled_value(text, ('passport no', 'passport number', 'document no', 'document number'), r'[A-Z0-9]{6,9}') or mrz.get('passportNumber') or _find_document_number(text, 6, 9),
        'nationality': _find_nationality(text) or mrz.get('nationality'),
        'dateOfBirth': _find_labeled_date(text, ('date of birth', 'birth date', 'dob')) or mrz.get('dateOfBirth') or _find_first_date(text),
        'gender': _find_gender(text),
        'expiryDate': _find_labeled_date(text, ('date of expiry', 'expiry date', 'expiration date', 'date of expiration', 'valid until')) or mrz.get('expiryDate') or _find_last_date(text),
    }
    return {k: v for k, v in fields.items() if v not in (None, '')}


def _extract_visa_fields(text):
    fields = {
        'visaNumber': _find_labeled_value(text, ('visa no', 'visa number', 'document no'), r'[A-Z0-9]{6,12}') or _find_document_number(text, 6, 12),
        'visaType': _find_value_from_keywords(text, ['WORK', 'BUSINESS', 'TOURIST', 'STUDENT', 'TEMPORARY', 'RESIDENT']),
        'entryValidity': _find_value_from_keywords(text, ['SINGLE', 'MULTIPLE', 'DOUBLE']),
        'stayDuration': _find_first_match(text, r'\b\d+\s*(days?|months?|years?)\b', prefer_uppercase=False),
        'issueDate': _find_labeled_date(text, ('issue date', 'date of issue', 'issued')) or _find_first_date(text),
        'expiryDate': _find_labeled_date(text, ('expiry date', 'date of expiry', 'valid until', 'until')) or _find_last_date(text),
    }
    return {k: v for k, v in fields.items() if v not in (None, '')}


def _extract_national_id_fields(text):
    fields = {
        'fullName': _find_labeled_name(text, ('full name', 'name')) or _first_meaningful_name(text),
        'idNumber': _find_labeled_value(text, ('id no', 'id number', 'identity number', 'card no'), r'[A-Z0-9]{6,20}') or _find_document_number(text, 6, 20),
        'dateOfBirth': _find_labeled_date(text, ('date of birth', 'birth date', 'dob')) or _find_first_date(text),
        'issueDate': _find_labeled_date(text, ('issue date', 'date of issue', 'issued')) or _find_first_date(text, offset=1),
        'expiryDate': _find_labeled_date(text, ('expiry date', 'date of expiry', 'valid until')) or _find_last_date(text),
    }
    return {k: v for k, v in fields.items() if v not in (None, '')}


def _extract_driving_license_fields(text):
    fields = {
        'fullName': _find_labeled_name(text, ('full name', 'name')) or _first_meaningful_name(text),
        'licenseNumber': _find_labeled_value(text, ('licence no', 'license no', 'licence number', 'license number')) or _find_document_number(text, 6, 20),
        'dateOfBirth': _find_labeled_date(text, ('date of birth', 'birth date', 'dob')) or _find_first_date(text),
        'issueDate': _find_labeled_date(text, ('issue date', 'date of issue', 'issued')) or _find_first_date(text, offset=1),
        'expiryDate': _find_labeled_date(text, ('expiry date', 'date of expiry', 'valid until')) or _find_last_date(text),
    }
    return {k: v for k, v in fields.items() if v not in (None, '')}


def _extract_permit_fields(text):
    fields = {
        'holderName': _find_labeled_name(text, ('holder name', 'full name', 'name')) or _first_meaningful_name(text),
        'permitNumber': _find_labeled_value(text, ('permit no', 'permit number')) or _find_document_number(text, 6, 20),
        'permitType': _find_value_from_keywords(text, ['WORK', 'BUSINESS', 'TEMPORARY', 'PERMANENT', 'RESIDENT']),
        'issueDate': _find_labeled_date(text, ('issue date', 'date of issue', 'issued')) or _find_first_date(text),
        'expiryDate': _find_labeled_date(text, ('expiry date', 'date of expiry', 'valid until')) or _find_last_date(text),
    }
    return {k: v for k, v in fields.items() if v not in (None, '')}


def _first_meaningful_name(text):
    """Extract a person's name from document text by finding valid name patterns."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Document-related keywords that indicate this line is not a name
    doc_keywords = {'PASSPORT', 'REPUBLIC', 'NATIONAL', 'DRIVING', 'LICENSE', 'LICENCE', 'IDENTITY', 
                   'DOCUMENT', 'VALID', 'AUTHORITY', 'PAGE', 'DATE', 'ISSUE', 'EXPIR', 
                   'SIGNATURE', 'PHOTO', 'BIRTH', 'SEX', 'GENDER', 'COUNTRY', 'NATIONALITY',
                   'ADDRESS', 'PLACE', 'ISSUED', 'OF', 'AND', 'THE', 'MR', 'MRS', 'MS'}
    
    for line in lines:
        compact = re.sub(r'\s+', ' ', line).strip(' -:')
        line_upper = compact.upper()
        
        # Skip pure document keywords or mostly keywords
        words = compact.split()
        keyword_count = sum(1 for w in words if w.upper() in doc_keywords)
        
        # If line is ALL keywords or 100% keywords, skip it
        if keyword_count == len(words) and len(words) > 0:
            continue
        
        # If it's a very short line that's mostly keywords, skip (like "DATE OF BIRTH")
        if len(words) <= 2 and re.search(r'\b(DATE|BIRTH|GENDER|SEX)\b', line_upper):
            continue
        
        # Try standard letter-only pattern first
        if re.fullmatch(r"[A-Z][A-Z .'-]{1,60}", compact):
            words_split = compact.split()
            if len(words_split) >= 2:
                return compact.upper()
        
        # Try with numbers (OCR artifacts)  
        if re.fullmatch(r"[A-Z0-9][A-Z0-9 .'-]{1,60}", compact):
            words_split = compact.split()
            if len(words_split) >= 2:
                # Try cleaning OCR mistakes
                cleaned = compact.replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B').replace('l', 'I')
                if re.fullmatch(r"[A-Z][A-Z .'-]{1,60}", cleaned) and len(cleaned.split()) >= 2:
                    return cleaned.upper()
                # Return as-is if still looks valid
                if len(cleaned) > 4:  
                    return cleaned.upper()
        
        # Last resort: extract any two+ word sequence with mostly letters
        word_groups = re.findall(r'\b[A-Za-z0-9][A-Za-z0-9\'-]*\b', compact)
        if len(word_groups) >= 2:
            # Filter out keywords and very short words
            filtered = [w for w in word_groups if w.upper() not in doc_keywords and len(w) > 1]
            if len(filtered) >= 2 and len(' '.join(filtered[:2])) > 4:
                return ' '.join(filtered[:2]).upper()
    
    return None


def _read_document_text(image):
    """Use several safe OCR reads and select by word confidence, not text length."""
    enhanced = ImageOps.autocontrast(image)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.5)
    enhanced = enhanced.filter(ImageFilter.SHARPEN)
    candidates = []
    # Phone photos are commonly rotated. PSM 6 handles form-like documents while
    # PSM 11 is much better for sparse card layouts.
    for angle in (0, 90, 180, 270):
        for variant_name, source in (('original', image), ('enhanced', enhanced)):
            candidate = source.rotate(angle, expand=True) if angle else source
            for psm in (6, 11):
                data = pytesseract.image_to_data(candidate, config=f'--psm {psm}', output_type=pytesseract.Output.DICT)
                words, values = [], []
                for word, value in zip(data.get('text', []), data.get('conf', [])):
                    word = (word or '').strip()
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = -1
                    if word:
                        words.append(word)
                    if word and value >= 0:
                        values.append(value)
                # Keep line breaks for label-aware extraction. Joining all tokens
                # lets one field consume a value from the following field.
                text = _text_from_ocr_data(data)
                confidence = (sum(values) / len(values) / 100) if values else 0.0
                # Favor reads with several confident words; a long low-confidence
                # garbage string is never preferred merely because it is longer.
                score = confidence + min(len(words), 30) / 300
                candidates.append((score, text, confidence, {'rotation': angle, 'variant': variant_name, 'psm': psm, 'wordCount': len(words)}))
    _, text, confidence, metadata = max(candidates, key=lambda item: item[0])
    return text, round(confidence, 2), metadata


def _text_from_ocr_data(data):
    """Rebuild line breaks from image_to_data so each OCR candidate needs one pass."""
    lines = {}
    for index, word in enumerate(data.get('text', [])):
        word = (word or '').strip()
        if not word:
            continue
        key = tuple(
            data.get(name, [0] * len(data.get('text', [])))[index]
            for name in ('block_num', 'par_num', 'line_num')
        )
        lines.setdefault(key, []).append(word)
    return '\n'.join(' '.join(words) for words in lines.values())


def _find_labeled_value(text, labels, pattern=r'[A-Z0-9][A-Z0-9 -]{3,30}'):
    """Extract labelled values, handling same-line and multi-line formats."""
    label_pattern = '|'.join(re.escape(label) for label in labels)
    lines = text.splitlines()
    
    for i, line in enumerate(lines):
        # Try same-line match first (label: value format)
        match = re.search(rf'\b(?:{label_pattern})\b\s*[:#-]?\s*({pattern})\s*$', line.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()
        
        # Try next-line match if label found (label on this line, value on next)
        if re.search(rf'\b(?:{label_pattern})\b\s*[:#-]?\s*$', line.strip(), re.IGNORECASE) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            match = re.match(rf'^({pattern})\s*$', next_line, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
    return None


def _find_labeled_name(text, labels, allow_single=False):
    """Read a labelled human name, handling multi-line and malformed input."""
    # First try strict pattern ([A-Z] [A-Z .'-])
    value = _find_labeled_value(text, labels, r"[A-Z][A-Z .'-]{2,60}")
    if not value:
        # Fallback to more lenient pattern that accepts numbers and common OCR errors
        value = _find_labeled_value(text, labels, r"[A-Za-z0-9][A-Za-z0-9 .'-]{2,60}")
    
    # If still no match, try fuzzy label matching (e.g., "Nsme" for "Name")
    if not value:
        value = _find_labeled_value_fuzzy(text, labels, r"[A-Za-z0-9][A-Za-z0-9 .'-]{2,60}")
    
    if not value:
        return None
    
    # Clean up: normalize spaces, remove leading/trailing punctuation
    value = re.sub(r'\s+', ' ', value).strip()
    value = value.strip(' -:').strip()
    
    # Remove numbers if they're OCR artifacts (e.g., "J0hn" -> "John")
    # But keep names with numbers like "3PO" or "K2"
    if re.search(r'[A-Z]', value) and re.search(r'\d', value):
        # Try replacing common OCR mistakes: 0->O, 1->I, 5->S, 8->B
        cleaned = value.replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B')
        if re.fullmatch(r"[A-Z][A-Z .'-]{1,60}", cleaned):
            value = cleaned
    
    # For name fields, allow single words (like "SMITH" for surname or "JOHN" for given name)
    # unless specifically requiring multiple words
    if allow_single:
        return value
    
    # For full names, check if we really have a multi-word name
    word_count = len(value.split())
    
    # Single capital letter (initial) or very short - need at least one more word
    if word_count == 1 and len(value) <= 2:
        return None
    
    # If it's a single word but looks like a proper name, return it
    # This handles cases like "surname: SMITH" or "given names: JOHN"
    if word_count == 1 and len(value) > 2:
        # Return single-word names if they don't look like document keywords
        if not re.search(r'\b(PASSPORT|NATIONAL|DOCUMENT|NUMBER|DATE|BANK|PAGE|SECTION|BLOCK|FIELD|AUTHORITY)\b', value):
            return value
    
    # Multi-word names
    return value if word_count >= 2 else None


def _find_labeled_value_fuzzy(text, labels, pattern=r'[A-Z0-9][A-Z0-9 -]{3,30}'):
    """Extract labelled values using fuzzy label matching for OCR errors."""
    lines = text.splitlines()
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Try fuzzy label matching
        for label in labels:
            label_lower = label.lower()
            label_words = label_lower.split()
            
            # Check for fuzzy match in this line
            if _fuzzy_label_match(line_lower, label_lower):
                # Found fuzzy match, extract value after the label
                # For simple cases like "Nsme John Smith" -> extract "John Smith"
                line_words = line.split()
                
                # Identify which words in the line correspond to label words
                matched_indices = []
                temp_words = line_words.copy()
                
                for label_word in label_words:
                    for idx, line_word in enumerate(temp_words):
                        if _fuzzy_match_word(line_word.lower(), label_word):
                            matched_indices.append(line_words.index(line_word))
                            temp_words.pop(idx)
                            break
                
                # Get remaining words after label (value)
                if matched_indices:
                    max_label_idx = max(matched_indices)
                    remaining_words = line_words[max_label_idx + 1:]
                    
                    if remaining_words:
                        remaining = ' '.join(remaining_words)
                        # Clean separators
                        remaining = re.sub(r'^[:#-]\s*', '', remaining).strip()
                        # Extract value pattern
                        match = re.search(rf'\b({pattern})', remaining, re.IGNORECASE)
                        if match:
                            return match.group(1).strip().upper()
                
                # Try next line if no value found on current line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    match = re.match(rf'^({pattern})', next_line, re.IGNORECASE)
                    if match:
                        return match.group(1).strip().upper()
    
    return None


def _fuzzy_label_match(text, label):
    """Check if a label appears in text with minor OCR errors."""
    # Split text into words for better matching
    text_words = text.split()
    label_words = label.split()
    
    # For two-word labels like "full name", try to match each word
    if len(label_words) > 1:
        matched_words = 0
        for lw in label_words:
            for tw in text_words:
                if _fuzzy_match_word(tw, lw):
                    matched_words += 1
                    break
        # Match if we found at least most of the label words
        return matched_words >= len(label_words) - 1
    
    # For single-word labels, try to find one matching word
    for word in text_words:
        if _fuzzy_match_word(word, label):
            return True
    return False


def _fuzzy_match_word(word, label):
    """Check if a word matches a label with minor OCR errors."""
    # Direct match
    if word == label:
        return True
    
    # Allow up to 1 character error for short labels, more for longer
    max_errors = max(1, len(label) // 4)
    
    if len(word) >= len(label) - 1 and len(word) <= len(label) + 1:
        errors = 0
        for i, (a, b) in enumerate(zip(word, label)):
            if a != b:
                errors += 1
        if errors <= max_errors:
            return True
    
    return False


def _find_passport_name(text):
    surname = _find_labeled_name(text, ('surname',), allow_single=True)
    given = _find_labeled_name(text, ('given names', 'given name', 'forenames'))
    if surname and given:
        return f'{given} {surname}'
    return _find_labeled_name(text, ('full name', 'name')) or surname or given


def _find_labeled_date(text, labels):
    """Extract dates that follow a label, handling same-line and multi-line formats."""
    label_pattern = '|'.join(re.escape(label) for label in labels)
    lines = text.splitlines()
    
    for i, line in enumerate(lines):
        # Try same-line format first
        match = re.search(rf'(?:{label_pattern})\s*[:#-]?\s*(\d{{1,4}}[./-]\d{{1,2}}[./-]\d{{2,4}})', line, re.IGNORECASE)
        if match:
            value = _normalise_date(match.group(1))
            return value if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) else None
        
        # Try next-line format if label found
        if re.search(rf'(?:{label_pattern})\s*[:#-]?\s*$', line, re.IGNORECASE) and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            match = re.match(r'^(\d{1,4}[./-]\d{1,2}[./-]\d{2,4})', next_line)
            if match:
                value = _normalise_date(match.group(1))
                return value if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) else None
    return None


def _find_document_number(text, minimum, maximum):
    """Avoid headings and date fragments when a field has no readable label."""
    candidates = re.findall(rf'\b(?=[A-Z0-9]{{{minimum},{maximum}}}\b)(?=[A-Z0-9]*\d)[A-Z0-9]+\b', text.upper())
    excluded = {'PASSPORT', 'NATIONAL', 'DOCUMENT', 'LICENSE', 'LICENCE', 'PERMIT', 'NUMBER'}
    candidates = [value for value in candidates if value not in excluded]
    # A document number normally contains both letters and digits. Reject pure
    # years, dates and other numeric noise when no label survived OCR.
    return next((value for value in candidates if re.search(r'[A-Z]', value) and re.search(r'\d', value)), None)


def _extract_passport_mrz(text):
    """Extract ICAO TD3 values when the two MRZ lines survived OCR."""
    lines = [re.sub(r'\s+', '', line.upper()) for line in text.splitlines()]
    lines = [line.replace('«', '<') for line in lines if line.count('<') >= 3]
    for index in range(len(lines) - 1):
        first, second = lines[index:index + 2]
        if not first.startswith('P<') or len(second) < 27:
            continue
        names = first[5:].replace('<', ' ').strip()
        values = {
            'name': ' '.join(names.split()),
            'passportNumber': second[0:9].replace('<', ''),
            'nationality': second[10:13].replace('<', ''),
            'dateOfBirth': _mrz_date(second[13:19]),
            'expiryDate': _mrz_date(second[21:27], expiry=True),
        }
        return {key: value for key, value in values.items() if value}
    return {}


def _mrz_date(value, expiry=False):
    if not re.fullmatch(r'\d{6}', value):
        return None
    year = int(value[:2])
    current_two_digit_year = datetime.now().year % 100
    year += (2000 if (expiry or year <= current_two_digit_year) else 1900)
    try:
        return datetime.strptime(f'{year}{value[2:]}', '%Y%m%d').date().isoformat()
    except ValueError:
        return None


def _find_gender(text):
    match = re.search(r'\b(M|F|Male|Female)\b', text, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(0).upper()
    return 'M' if value in ['M', 'MALE'] else 'F'


def _find_nationality(text):
    """Find a three-letter nationality code without treating a name as one."""
    known_codes = {
        'AFG', 'AUS', 'BGD', 'CAN', 'CHE', 'CHN', 'DEU', 'ESP', 'FRA',
        'GBR', 'IND', 'ITA', 'JPN', 'KOR', 'NPL', 'NZL', 'PAK', 'RUS',
        'SGP', 'USA', 'ZAF',
    }
    tokens = re.findall(r'\b[A-Z]{3}\b', text.upper())
    for token in tokens:
        if token in known_codes:
            return token
    # Prefer a token appearing after a nationality label when the issuing
    # country is not in the small built-in list.
    labelled = re.search(r'(?:NATIONALITY|CITIZENSHIP)\s*[:\-]?\s*([A-Z]{3})\b', text, re.IGNORECASE)
    return labelled.group(1).upper() if labelled else None


def _find_first_match(text, pattern, prefer_uppercase=False):
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    if not matches:
        return None
    value = matches[0]
    if prefer_uppercase:
        value = value.upper()
    return value


def _find_value_from_keywords(text, keywords):
    for keyword in keywords:
        if re.search(rf'\b{re.escape(keyword)}\b', text, flags=re.IGNORECASE):
            return keyword.title()
    return None


def _find_dates(text):
    matches = re.findall(r'(\d{1,4}[./-]\d{1,2}[./-]\d{2,4})', text)
    return [_normalise_date(value) for value in matches]


def _normalise_date(value):
    """Return dates in the ISO format consumed by validation rules."""
    value = value.replace('.', '/').replace('-', '/')
    for pattern in ('%d/%m/%Y', '%Y/%m/%d', '%d/%m/%y'):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return value


def _find_first_date(text, offset=0):
    values = _find_dates(text)
    if offset < len(values):
        return values[offset]
    return None


def _find_second_date(text):
    values = _find_dates(text)
    if len(values) >= 2:
        return values[1]
    return values[0] if values else None


def _find_last_date(text):
    values = _find_dates(text)
    return values[-1] if values else None


def _calculate_confidence(fields, document_type, ocr_confidence=0):
    expected = EXPECTED_FIELDS.get((document_type or 'passport').lower(), EXPECTED_FIELDS['passport'])
    found = sum(1 for key in expected if fields.get(key))
    coverage = found / len(expected)
    return round(min(1.0, (coverage * 0.7) + (max(0.0, min(1.0, ocr_confidence)) * 0.3)), 2)


def _extraction_warnings(fields, expected, ocr_confidence):
    warnings = []
    missing = [field for field in expected if not fields.get(field)]
    if missing:
        warnings.append(f"Could not reliably read: {', '.join(missing)}.")
    if ocr_confidence < 0.55:
        warnings.append('Image text quality is low; verify all extracted values against the original document.')
    return warnings


if __name__ == '__main__':
    if len(sys.argv) > 2:
        result = extract_ocr(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        result = extract_ocr(sys.argv[1])
    else:
        result = {'error': 'No image path provided'}
    print(json.dumps(result))
