"""
Tampering Detection
Detect potential signs of document manipulation using image analysis.
"""

import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image


def detect_tampering(image_path):
    """Return evidence-based anomaly findings for an image."""
    if not Path(image_path).exists():
        return {
            'status': 'failed',
            'error': f'Image file not found: {image_path}',
            'tamperingDetected': False,
            'confidence': 0,
            'findings': [],
            'evidence': [],
        }

    try:
        source = Image.open(image_path)
        image_format = (source.format or '').upper()
        metadata = dict(source.info or {})
        img = source.convert('RGB')
        array = np.asarray(img)
        gray = np.asarray(img.convert('L'))

        findings = []
        evidence = []

        brightness = float(gray.mean())
        contrast = float(gray.std())
        edge_density = _edge_density(gray)
        saturated_pixels = _saturated_pixel_ratio(array)
        color_inconsistency = _color_inconsistency(array)
        ela_metrics = _jpeg_ela_metrics(img) if image_format in {'JPG', 'JPEG'} else None

        # Metadata is supporting evidence only: many legitimate workflows
        # re-encode documents and preserve editing software tags.
        software = str(metadata.get('software') or metadata.get('Software') or '').strip()
        if software and any(token in software.lower() for token in ('photoshop', 'gimp', 'pixelmator', 'paint.net', 'editor')):
            findings.append({
                'type': 'metadata_anomaly',
                'description': 'Editing-software metadata is present; this is a potential manipulation indicator, not proof of alteration.',
                'confidence': 0.55,
            })
            evidence.append(f'Image metadata identifies editing software ({software[:80]}).')

        width, height = img.size
        low_resolution = min(width, height) < 800
        if low_resolution:
            evidence.append('Image resolution is low for reliable forensic analysis; results may be inconclusive.')

        # These are deliberately *review* signals, not individual forgery
        # decisions. Document borders, text, seals, white backgrounds and
        # normal JPEG re-encoding all produce them in genuine documents.
        if edge_density > 0.28:
            findings.append({
                'type': 'edge_anomaly',
                'description': 'Unusually dense edges require visual review; this can also be caused by text, seals, or compression.',
                'confidence': 0.45,
            })
            evidence.append('Edge density is unusually high for a standard document image.')

        if color_inconsistency > 0.42:
            findings.append({
                'type': 'color_inconsistency',
                'description': 'Color channel inconsistencies detected - possible image tampering or compositing.',
                'confidence': 0.45,
            })
            evidence.append('RGB channels show unusual variation patterns for the document image.')

        # Blank/white document backgrounds naturally contain clipped white
        # pixels; require meaningful contrast before treating clipping as a
        # local-adjustment signal.
        if saturated_pixels > 0.92 and contrast > 65:
            findings.append({
                'type': 'saturation_anomaly',
                'description': 'High saturation or clipped highlights detected - possible local image adjustment.',
                'confidence': 0.4,
            })
            evidence.append('The image contains an unusually high share of saturated pixels.')

        if contrast > 100 and brightness < 18:
            findings.append({
                'type': 'contrast_anomaly',
                'description': 'Extreme contrast pattern suggests manual retouching or image editing.',
                'confidence': 0.45,
            })
            evidence.append('The image has strong contrast and very dark overall brightness, which can indicate edits.')

        # Error-level analysis (ELA) highlights regions whose JPEG compression
        # behaviour differs markedly from the rest of the image. This is useful
        # for a pasted portrait or text block, which whole-image statistics can
        # miss. ELA is meaningful only for JPEG input, and remains a review cue:
        # resaves, screenshots and social-media uploads can produce the same cue.
        if ela_metrics and ela_metrics['hasLocalizedAnomaly']:
            findings.append({
                'type': 'localized_compression_anomaly',
                'description': 'A localized region has compression artifacts that differ from the surrounding document; inspect the highlighted area for pasted or retouched content.',
                'confidence': 0.65,
                'regions': ela_metrics['suspiciousRegions'],
            })
            evidence.append(
                'JPEG recompression analysis found localized error-level differences '
                f"in {len(ela_metrics['suspiciousRegions'])} image region(s)."
            )

        forensic_findings = [item for item in findings if item['type'] != 'metadata_anomaly']
        confidence = min(0.9, round(sum(item['confidence'] for item in forensic_findings) / max(1, len(forensic_findings)), 2))
        # A detection needs corroborating visual signals on an adequately sized
        # image. Metadata is never sufficient, and a single generic image
        # statistic is only an inconclusive lead for a human reviewer.
        # A strong localized ELA result is more specific than one global image
        # statistic, so it can independently require review. Other signals still
        # need corroboration to avoid flagging ordinary document texture.
        has_localized_compression_anomaly = bool(ela_metrics and ela_metrics['hasLocalizedAnomaly'])
        tampering_detected = not low_resolution and confidence >= 0.45 and (
            len(forensic_findings) >= 2 or has_localized_compression_anomaly
        )
        assessment = 'review' if tampering_detected else ('inconclusive' if low_resolution or findings else 'clear')

        return {
            'status': 'success',
            'tamperingDetected': bool(tampering_detected),
            'confidence': confidence,
            'assessment': assessment,
            'findings': findings,
            'evidence': evidence,
            'metrics': {
                'width': width,
                'height': height,
                'brightness': round(brightness, 2),
                'contrast': round(contrast, 2),
                'edgeDensity': round(edge_density, 4),
                'saturatedPixelRatio': round(saturated_pixels, 4),
                'colorInconsistency': round(color_inconsistency, 4),
                'errorLevelAnalysis': ela_metrics,
            },
            'disclaimer': 'Signals indicate potential anomalies and require human review; they do not establish forgery.',
        }

    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'tamperingDetected': False,
            'confidence': 0,
            'findings': [],
            'evidence': [],
        }


def _edge_density(gray):
    """Estimate edge density without OpenCV."""
    gy, gx = np.gradient(gray.astype(np.float32))
    magnitude = np.hypot(gx, gy)
    # A percentile threshold always labels roughly the same share of pixels as
    # edges, so it cannot distinguish a clean scan from a manipulated image.
    # A fixed gradient threshold gives this metric meaningful variation.
    return float(np.mean(magnitude > 55.0))


def _saturated_pixel_ratio(array):
    """Estimate saturation/clipping in a color image."""
    r, g, b = array[:, :, 0], array[:, :, 1], array[:, :, 2]
    saturated = ((r > 245) | (g > 245) | (b > 245)).astype(np.uint8)
    return float(saturated.mean())


def _color_inconsistency(array):
    """Measure how uneven the RGB channels are."""
    if array.ndim != 3:
        return 0.0
    r = array[:, :, 0].astype(np.float32)
    g = array[:, :, 1].astype(np.float32)
    b = array[:, :, 2].astype(np.float32)
    diff = np.abs(r - g) + np.abs(r - b) + np.abs(g - b)
    return float(diff.mean() / 255.0)


def _jpeg_ela_metrics(image, grid_size=8):
    """Return localized JPEG recompression-error metrics and candidate regions.

    The image is resized before analysis to keep the detector quick on camera
    photos. Region coordinates are normalized (0--1), allowing the UI to draw
    them over the original upload without relying on a resized image size.
    """
    analysis_image = image.copy()
    analysis_image.thumbnail((1600, 1600))

    encoded = BytesIO()
    analysis_image.save(encoded, format='JPEG', quality=85, subsampling=0)
    encoded.seek(0)
    recompressed = Image.open(encoded).convert('RGB')
    original = np.asarray(analysis_image.convert('RGB'), dtype=np.float32)
    error = np.abs(original - np.asarray(recompressed, dtype=np.float32)).mean(axis=2)

    height, width = error.shape
    blocks = []
    for row_index, row in enumerate(np.array_split(error, grid_size, axis=0)):
        for column_index, block in enumerate(np.array_split(row, grid_size, axis=1)):
            blocks.append({
                'row': row_index,
                'column': column_index,
                'meanError': float(block.mean()),
            })

    values = np.asarray([block['meanError'] for block in blocks], dtype=np.float32)
    median_error = float(np.median(values))
    # An absolute floor prevents tiny, harmless quantization differences in a
    # clean high-quality JPEG from becoming an anomaly merely due to a ratio.
    # A pasted region can have either *more* artifacts (a low-quality source)
    # or *fewer* artifacts (a smoothed/retouched source). Look for meaningful
    # deviations in both directions rather than only unusually large errors.
    threshold = max(0.75, median_error * 0.45)
    suspicious = [
        block for block in blocks
        if abs(block['meanError'] - median_error) > threshold
    ]
    suspicious_fraction = len(suspicious) / len(blocks)
    max_deviation = float(np.max(np.abs(values - median_error)))

    # A small number of strong blocks is characteristic of localized editing;
    # an anomaly spanning most blocks is normally a global re-encode, not a
    # pasted region. Return no more than four regions to keep the result usable.
    has_localized_anomaly = (
        0.015 <= suspicious_fraction <= 0.35
        and max_deviation >= max(1.5, median_error * 0.6)
    )
    suspicious_regions = []
    if has_localized_anomaly:
        for block in sorted(suspicious, key=lambda item: item['meanError'], reverse=True)[:4]:
            suspicious_regions.append({
                'x': round(block['column'] / grid_size, 3),
                'y': round(block['row'] / grid_size, 3),
                'width': round(1 / grid_size, 3),
                'height': round(1 / grid_size, 3),
                'meanError': round(block['meanError'], 2),
            })

    return {
        'available': True,
        'meanError': round(float(error.mean()), 2),
        'medianRegionError': round(median_error, 2),
        'maxRegionError': round(float(values.max()), 2),
        'maxRegionDeviation': round(max_deviation, 2),
        'suspiciousRegionFraction': round(suspicious_fraction, 3),
        'hasLocalizedAnomaly': has_localized_anomaly,
        'suspiciousRegions': suspicious_regions,
    }


def detect_tampering_in_image(image_path):
    return detect_tampering(image_path)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        result = detect_tampering(sys.argv[1])
        print(json.dumps(result))
    else:
        print(json.dumps({'error': 'No image path provided'}))
