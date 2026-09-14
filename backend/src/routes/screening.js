const express = require('express');
const ScreeningCase = require('../models/ScreeningCase');
const Document = require('../models/Document');
const { runScreeningPipeline } = require('../services/screeningService');

const router = express.Router();

const historyQuery = () => {
  let query = ScreeningCase.find({});
  if (query && typeof query.populate === 'function') {
    query = query.populate('documentId', 'filename documentType status createdAt');
    query = query.populate('riskAssessmentId', 'riskScore riskLevel requiresHumanReview factors recommendation');
  }
  return query;
};

/**
 * POST /api/screening/analyze
 * Start passport screening analysis including OCR, validation, tampering, face and risk scoring.
 *
 * Expected input:
 * {
 *   "documentId": "<MongoDB _id of uploaded passport>",
 *   "personPhotoId": "<MongoDB _id of optional person photo>"
 * }
 */
router.post('/analyze', async (req, res) => {
  try {
    const { documentId, personPhotoId } = req.body;

    if (!documentId) {
      return res.status(400).json({ error: 'documentId is required' });
    }

    const document = await Document.findById(documentId);
    if (!document) {
      return res.status(404).json({ error: 'Document not found' });
    }

    const supportedDocumentTypes = ['passport', 'visa', 'national_id', 'driving_license', 'permit'];
    if (!supportedDocumentTypes.includes(document.documentType)) {
      return res.status(400).json({
        error: `Document type "${document.documentType}" is not supported for screening. Supported types: ${supportedDocumentTypes.join(', ')}`,
      });
    }

    if (personPhotoId) {
      const personPhoto = await Document.findById(personPhotoId);
      if (!personPhoto || personPhoto.documentType !== 'person_photo') {
        return res.status(400).json({
          error: 'personPhotoId must reference a valid uploaded person photo',
        });
      }
    }

    const caseId = `CASE-${Date.now()}`;
    const screeningCase = new ScreeningCase({
      caseId,
      documentId,
      personPhotoId: personPhotoId || null,
      status: 'processing',
    });

    await screeningCase.save();

    try {
      const pipelineResult = await runScreeningPipeline(screeningCase._id, document, personPhotoId || null);
      res.status(200).json(pipelineResult);
    } catch (pipelineError) {
      res.status(500).json({
        success: false,
        screeningCaseId: screeningCase._id,
        caseId: screeningCase.caseId,
        error: pipelineError.message,
      });
    }
  } catch (error) {
    console.error('Error creating screening case:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/screening/history
 * List screening cases history
 */
router.get('/history', async (req, res) => {
  try {
    const query = historyQuery();

    let screeningCases;
    if (query && typeof query.sort === 'function') {
      const sortedQuery = query.sort({ createdAt: -1 });
      screeningCases = typeof sortedQuery.limit === 'function'
        ? await sortedQuery.limit(50)
        : await sortedQuery;
    } else {
      screeningCases = await query;
    }

    res.json(screeningCases || []);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/screening/:id
 * Retrieve screening results
 */
router.get('/:id', async (req, res) => {
  try {
    const screeningCase = await ScreeningCase.findById(req.params.id)
      .populate('documentId')
      .populate('ocrResultId')
      .populate('validationResultId')
      .populate('tamperingResultId')
      .populate('faceVerificationResultId')
      .populate('riskAssessmentId');

    if (!screeningCase) {
      return res.status(404).json({ error: 'Screening case not found' });
    }

    res.json(screeningCase);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/screening
 * List all screening cases
 */
router.get('/', async (req, res) => {
  try {
    const query = historyQuery();
    const screeningCases = typeof query.sort === 'function'
      ? await query.sort({ createdAt: -1 }).limit(50)
      : await query;
    res.json(screeningCases || []);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
