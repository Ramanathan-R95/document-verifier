const mongoose = require('mongoose');

const ScreeningCaseSchema = new mongoose.Schema(
  {
    caseId: {
      type: String,
      unique: true,
      required: true,
    },
    documentId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Document',
      required: true,
    },
    personPhotoId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Document',
    },
    status: {
      type: String,
      enum: ['pending', 'processing', 'completed', 'error'],
      default: 'pending',
    },
    ocrResultId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'OCRResult',
    },
    validationResultId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ValidationResult',
    },
    tamperingResultId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'TamperingResult',
    },
    faceVerificationResultId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'FaceVerificationResult',
    },
    riskAssessmentId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'RiskAssessment',
    },
    notes: String,
    reviewedBy: String,
    requiresHumanReview: {
      type: Boolean,
      default: false,
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('ScreeningCase', ScreeningCaseSchema);
