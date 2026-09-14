const mongoose = require('mongoose');

const DocumentSchema = new mongoose.Schema(
  {
    filename: {
      type: String,
      required: true,
    },
    documentType: {
      type: String,
      enum: ['passport', 'visa', 'national_id', 'driving_license', 'permit', 'person_photo'],
      required: true,
    },
    fileSize: Number,
    mimeType: String,
    uploadedBy: String,
    filePath: String, // temporary path
    status: {
      type: String,
      enum: ['uploaded', 'processing', 'completed', 'error'],
      default: 'uploaded',
    },
    associatedScreeningCase: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'ScreeningCase',
    },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Document', DocumentSchema);
