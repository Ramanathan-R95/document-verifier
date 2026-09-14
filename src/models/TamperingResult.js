const mongoose = require('mongoose');

const TamperingResultSchema = new mongoose.Schema(
  {
    screeningCaseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ScreeningCase',
      required: true,
    },
    tamperingDetected: Boolean,
    confidence: Number,
    assessment: {
      type: String,
      enum: ['clear', 'inconclusive', 'review'],
      default: 'inconclusive',
    },
    findings: [
      {
        type: { type: String },
        description: { type: String },
        confidence: { type: Number },
      },
    ],
    analysisDetails: mongoose.Schema.Types.Mixed,
    status: {
      type: String,
      enum: ['success', 'incomplete', 'failed'],
      default: 'success',
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('TamperingResult', TamperingResultSchema);
