const { callPythonService } = require('./pythonBridge');
const ScreeningCase = require('../models/ScreeningCase');
const TamperingResult = require('../models/TamperingResult');
const FaceVerificationResult = require('../models/FaceVerificationResult');
const RiskAssessment = require('../models/RiskAssessment');

/**
 * Run Phase 3 analysis for a screening case
 * This uses the uploaded document and optional person image.
 */
const runPhase3Analysis = async (screeningCase, document, personImagePath) => {
  try {
    const documentPath = document.filePath;

    // 1. Tampering detection
    let tamperingResult = {
      success: true,
      tamperingDetected: false,
      confidence: 0,
      findings: [],
    };

    if (documentPath) {
      const tamperingResponse = await callPythonService('tampering', {
        imagePath: documentPath,
      });

      tamperingResult = {
        success: tamperingResponse.success,
        tamperingDetected: tamperingResponse.tamperingDetected || false,
        confidence: tamperingResponse.confidence || 0,
        findings: tamperingResponse.findings || [],
      };
    }

    // 2. Face verification
    let faceResult = {
      success: true,
      faceDetectedInDocument: false,
      faceDetectedInPerson: false,
      matchStatus: 'not_verified',
      similarity: 0,
      confidence: 0,
    };

    if (personImagePath) {
      const faceResponse = await callPythonService('face', {
        documentImagePath: documentPath,
        personImagePath,
      });

      faceResult = {
        success: faceResponse.success,
        faceDetectedInDocument: faceResponse.faceDetectedInDocument || false,
        faceDetectedInPerson: faceResponse.faceDetectedInPerson || false,
        matchStatus: faceResponse.matchStatus || 'not_verified',
        similarity: faceResponse.similarity || 0,
        confidence: faceResponse.confidence || 0,
      };
    }

    // 3. Risk scoring
    const ocrResult = screeningCase.ocrResultId ? await screeningCase.populate('ocrResultId') : null;
    const validationResult = screeningCase.validationResultId ? await screeningCase.populate('validationResultId') : null;

    const ocrData = ocrResult && ocrResult.ocrResultId ? ocrResult.ocrResultId.toObject() : { confidence: 0, fields: {} };
    const validationData = validationResult && validationResult.validationResultId ? validationResult.validationResultId.toObject() : { isValid: true, violations: [] };

    const riskResponse = await callPythonService('risk_calculator', {
      ocr: {
        confidence: ocrData.confidence || 0,
        fields: ocrData.fields || {},
      },
      validation: {
        isValid: validationData.isValid !== false,
        violations: validationData.violations || [],
      },
      tampering: tamperingResult,
      face: faceResult,
    });

    // Save tampering result
    const tamperingRecord = new TamperingResult({
      screeningCaseId: screeningCase._id,
      tamperingDetected: tamperingResult.tamperingDetected,
      confidence: tamperingResult.confidence,
      findings: tamperingResult.findings,
      analysisDetails: tamperingResult,
      status: 'success',
    });
    await tamperingRecord.save();
    screeningCase.tamperingResultId = tamperingRecord._id;

    // Save face verification result
    const faceRecord = new FaceVerificationResult({
      screeningCaseId: screeningCase._id,
      faceDetectedInDocument: faceResult.faceDetectedInDocument,
      faceDetectedInPerson: faceResult.faceDetectedInPerson,
      matchStatus: faceResult.matchStatus,
      similarity: faceResult.similarity,
      confidence: faceResult.confidence,
      details: faceResult,
      status: 'success',
    });
    await faceRecord.save();
    screeningCase.faceVerificationResultId = faceRecord._id;

    // Save risk assessment
    const riskRecord = new RiskAssessment({
      screeningCaseId: screeningCase._id,
      riskScore: riskResponse.riskScore,
      riskLevel: riskResponse.riskLevel,
      requiresHumanReview: riskResponse.requiresHumanReview,
      factors: riskResponse.factors,
      recommendation: riskResponse.recommendation,
      calculatedBy: 'phase3-basic-risk-model',
    });
    await riskRecord.save();
    screeningCase.riskAssessmentId = riskRecord._id;

    screeningCase.requiresHumanReview = riskResponse.requiresHumanReview;
    screeningCase.status = 'completed';
    await screeningCase.save();

    return {
      tampering: {
        tamperingDetected: tamperingResult.tamperingDetected,
        confidence: tamperingResult.confidence,
        findings: tamperingResult.findings,
      },
      face: {
        faceDetectedInDocument: faceResult.faceDetectedInDocument,
        faceDetectedInPerson: faceResult.faceDetectedInPerson,
        matchStatus: faceResult.matchStatus,
        similarity: faceResult.similarity,
        confidence: faceResult.confidence,
      },
      risk: {
        riskScore: riskResponse.riskScore,
        riskLevel: riskResponse.riskLevel,
        requiresHumanReview: riskResponse.requiresHumanReview,
        factors: riskResponse.factors,
        recommendation: riskResponse.recommendation,
      },
    };
  } catch (error) {
    console.error('Phase 3 pipeline failed:', error);
    throw error;
  }
};

module.exports = {
  runPhase3Analysis,
};
