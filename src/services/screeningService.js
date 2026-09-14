const { callPythonService } = require('./pythonBridge');
const OCRResult = require('../models/OCRResult');
const ValidationResult = require('../models/ValidationResult');
const TamperingResult = require('../models/TamperingResult');
const FaceVerificationResult = require('../models/FaceVerificationResult');
const RiskAssessment = require('../models/RiskAssessment');
const ScreeningCase = require('../models/ScreeningCase');

/**
 * Run the complete OCR, validation, tampering, face, and risk pipeline for a passport
 * @param {string} screeningCaseId - Screening case ID
 * @param {object} document - Document object with filePath
 * @param {string|null} personPhotoId - Optional person photo document ID
 * @returns {Promise<object>} - Pipeline result
 */
const runScreeningPipeline = async (screeningCaseId, document, personPhotoId = null) => {
  try {
    const screeningCase = await ScreeningCase.findById(screeningCaseId);
    if (!screeningCase) {
      throw new Error('Screening case not found');
    }

    if (document && document.save) {
      document.status = 'processing';
      await document.save();
    }

    if (personPhotoId) {
      screeningCase.personPhotoId = personPhotoId;
    }

    // Step 1: OCR
    console.log('Step 1: Running OCR...');
    const ocrInput = {
      imagePath: document.filePath,
      documentType: document.documentType || 'passport',
    };

    const ocrResult = await callPythonService('ocr', ocrInput);
    if (!ocrResult.success) {
      throw new Error(`OCR failed: ${ocrResult.error || 'Unknown error'}`);
    }

    const ocrRecord = new OCRResult({
      screeningCaseId,
      documentType: document.documentType,
      fields: ocrResult.fields,
      confidence: ocrResult.confidence,
      rawOutput: ocrResult.rawText,
      status: ocrResult.status,
      missingFields: ocrResult.missingFields || [],
      warnings: ocrResult.warnings || [],
      preprocessing: ocrResult.preprocessing || {},
    });

    await ocrRecord.save();
    screeningCase.ocrResultId = ocrRecord._id;

    // Step 2: Validation
    console.log('Step 2: Running validation...');
    const validationInput = {
      fields: ocrResult.fields,
      documentType: document.documentType || 'passport',
    };

    const validationData = await callPythonService('validation', validationInput);
    const validationRecord = new ValidationResult({
      screeningCaseId,
      violations: validationData.violations || [],
      isValid: validationData.isValid,
      validationDetails: validationData,
    });

    await validationRecord.save();
    screeningCase.validationResultId = validationRecord._id;

    // Step 3: Tampering detection
    console.log('Step 3: Running tampering analysis...');
    const tamperingResult = await callPythonService('tampering', {
      imagePath: document.filePath,
    });

    const tamperingRecord = new TamperingResult({
      screeningCaseId,
      tamperingDetected: tamperingResult.tamperingDetected || false,
      confidence: tamperingResult.confidence || 0,
      assessment: tamperingResult.assessment || 'inconclusive',
      findings: tamperingResult.findings || [],
      analysisDetails: tamperingResult,
      status: tamperingResult.success ? 'success' : 'failed',
    });

    await tamperingRecord.save();
    screeningCase.tamperingResultId = tamperingRecord._id;

    // Step 4: Face verification
    let faceResult = {
      success: true,
      faceDetectedInDocument: false,
      faceDetectedInPerson: false,
      matchStatus: 'not_verified',
      similarity: 0,
      confidence: 0,
    };

    if (personPhotoId) {
      const personDocument = await require('../models/Document').findById(personPhotoId);
      if (personDocument && personDocument.filePath) {
        console.log('Step 4: Running face verification...');
        faceResult = await callPythonService('face', {
          documentImagePath: document.filePath,
          personImagePath: personDocument.filePath,
        });
      }
    }

    const faceRecord = new FaceVerificationResult({
      screeningCaseId,
      faceDetectedInDocument: faceResult.faceDetectedInDocument || false,
      faceDetectedInPerson: faceResult.faceDetectedInPerson || false,
      matchStatus: faceResult.matchStatus || 'not_verified',
      similarity: faceResult.similarity || 0,
      confidence: faceResult.confidence || 0,
      details: faceResult,
      status: faceResult.success ? 'success' : 'failed',
    });

    await faceRecord.save();
    screeningCase.faceVerificationResultId = faceRecord._id;

    // Step 5: Risk scoring
    console.log('Step 5: Calculating risk score...');
    const riskInput = {
      ocr: {
        confidence: ocrResult.confidence || 0,
        fields: ocrResult.fields || {},
      },
      validation: {
        isValid: validationData.isValid,
        violations: validationData.violations || [],
      },
      tampering: {
        success: tamperingResult.success,
        tamperingDetected: tamperingResult.tamperingDetected || false,
        confidence: tamperingResult.confidence || 0,
        assessment: tamperingResult.assessment || 'inconclusive',
        findings: tamperingResult.findings || [],
      },
      face: {
        success: faceResult.success,
        faceDetectedInDocument: faceResult.faceDetectedInDocument || false,
        faceDetectedInPerson: faceResult.faceDetectedInPerson || false,
        matchStatus: faceResult.matchStatus || 'not_verified',
        similarity: faceResult.similarity || 0,
        confidence: faceResult.confidence || 0,
      },
    };

    const riskResult = await callPythonService('risk_calculator', riskInput);
    const riskRecord = new RiskAssessment({
      screeningCaseId,
      riskScore: riskResult.riskScore || 0,
      riskLevel: riskResult.riskLevel || 'LOW',
      requiresHumanReview: !!riskResult.requiresHumanReview,
      factors: riskResult.factors || [],
      recommendation: riskResult.recommendation || 'Manual review recommended.',
      calculatedBy: 'phase3-basic-risk-model',
    });

    await riskRecord.save();
    screeningCase.riskAssessmentId = riskRecord._id;

    screeningCase.status = 'completed';
    screeningCase.requiresHumanReview = !!riskResult.requiresHumanReview || !validationData.isValid;
    await screeningCase.save();
    if (document && document.save) {
      document.status = 'completed';
      await document.save();
    }

    return {
      success: true,
      screeningCaseId: screeningCase._id,
      caseId: screeningCase.caseId,
      documentType: document.documentType,
      ocr: {
        fields: ocrResult.fields,
        confidence: ocrResult.confidence,
        status: ocrResult.status,
        missingFields: ocrResult.missingFields || [],
        warnings: ocrResult.warnings || [],
      },
      validation: {
        status: validationData.isValid ? 'valid' : 'invalid',
        isValid: validationData.isValid,
        errors: (validationData.violations || []).filter((v) => v.severity === 'error'),
        warnings: (validationData.violations || []).filter((v) => v.severity === 'warning'),
      },
      tampering: {
        tamperingDetected: tamperingResult.tamperingDetected || false,
        confidence: tamperingResult.confidence || 0,
        findings: tamperingResult.findings || [],
      },
      face: {
        faceDetectedInDocument: faceResult.faceDetectedInDocument || false,
        faceDetectedInPerson: faceResult.faceDetectedInPerson || false,
        matchStatus: faceResult.matchStatus || 'not_verified',
        similarity: faceResult.similarity || 0,
        confidence: faceResult.confidence || 0,
      },
      risk: {
        riskScore: riskResult.riskScore || 0,
        riskLevel: riskResult.riskLevel || 'LOW',
        requiresHumanReview: !!riskResult.requiresHumanReview,
        factors: riskResult.factors || [],
        recommendation: riskResult.recommendation || 'Manual review recommended.',
      },
      requiresHumanReview: !!riskResult.requiresHumanReview || !validationData.isValid,
    };
  } catch (error) {
    console.error('Pipeline error:', error);

    try {
      const screeningCase = await ScreeningCase.findById(screeningCaseId);
      if (screeningCase) {
        screeningCase.status = 'error';
        await screeningCase.save();
      }
      if (document && document.save) {
        document.status = 'error';
        await document.save();
      }
    } catch (e) {
      console.error('Failed to update screening case error status:', e);
    }

    throw error;
  }
};

module.exports = {
  runScreeningPipeline,
};
