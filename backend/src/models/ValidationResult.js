const mongoose = require('mongoose');

const ValidationResultSchema = new mongoose.Schema(
  {
    screeningCaseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ScreeningCase',
      required: true,
    },
    violations: [
      {
        field: String,
        rule: String,
        severity: {
          type: String,
          enum: ['error', 'warning', 'info'],
        },
        message: String,
      },
    ],
    isValid: Boolean,
    validationDetails: mongoose.Schema.Types.Mixed,
  },
  { timestamps: true }
);

module.exports = mongoose.model('ValidationResult', ValidationResultSchema);
