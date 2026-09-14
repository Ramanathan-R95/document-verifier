const mongoose = require('mongoose');

const OCRResultSchema = new mongoose.Schema(
  {
    screeningCaseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ScreeningCase',
      required: true,
    },
    documentType: String,
    fields: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },
    confidence: Number,
    rawOutput: String, // raw OCR text
    missingFields: {
      type: [String],
      default: [],
    },
    warnings: {
      type: [String],
      default: [],
    },
    preprocessing: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },
    status: {
      type: String,
      enum: ['success', 'partial', 'failed'],
      default: 'success',
    },
    error: String,
  },
  { timestamps: true }
);

module.exports = mongoose.model('OCRResult', OCRResultSchema);
