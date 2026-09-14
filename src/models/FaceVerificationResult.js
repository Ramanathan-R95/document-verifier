const mongoose = require('mongoose');

const FaceVerificationResultSchema = new mongoose.Schema(
  {
    screeningCaseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ScreeningCase',
      required: true,
    },
    faceDetectedInDocument: Boolean,
    faceDetectedInPerson: Boolean,
    matchStatus: {
      type: String,
      enum: ['match', 'no_match', 'inconclusive', 'not_verified'],
      default: 'not_verified',
    },
    similarity: Number, // 0-1
    confidence: Number,
    details: mongoose.Schema.Types.Mixed,
    status: {
      type: String,
      enum: ['success', 'incomplete', 'failed'],
      default: 'success',
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('FaceVerificationResult', FaceVerificationResultSchema);
