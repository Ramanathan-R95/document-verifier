const mongoose = require('mongoose');

const RiskAssessmentSchema = new mongoose.Schema(
  {
    screeningCaseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ScreeningCase',
      required: true,
    },
    riskScore: Number, // 0-100
    riskLevel: {
      type: String,
      enum: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
    },
    requiresHumanReview: Boolean,
    factors: [
      {
        category: String, // 'ocr', 'validation', 'tampering', 'face'
        finding: String,
        weight: Number,
        confidence: Number,
      },
    ],
    recommendation: String,
    calculatedBy: String, // version/method of scoring
  },
  { timestamps: true }
);

module.exports = mongoose.model('RiskAssessment', RiskAssessmentSchema);
