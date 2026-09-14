const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
const Document = require('../models/Document');
const { validateFileUpload } = require('../middleware/validation');

const router = express.Router();

// Configure multer for file uploads
const uploadDir = path.join(__dirname, '../../uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const timestamp = Date.now();
    const extension = path.extname(file.originalname || '').toLowerCase();
    cb(null, `${timestamp}-${Math.random().toString(36).slice(2, 10)}${extension}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
  fileFilter: (req, file, cb) => {
    const allowedMimes = ['image/jpeg', 'image/png', 'application/pdf'];
    if (allowedMimes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type. Only JPEG, PNG, and PDF are allowed.'));
    }
  },
});

/**
 * POST /api/documents/upload
 * Upload a document (passport, visa, etc.) or a person's photo
 */
router.post('/upload', upload.single('file'), validateFileUpload, async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file provided' });
    }

    const { documentType } = req.body;

    // Validate documentType
    const validTypes = ['passport', 'visa', 'national_id', 'driving_license', 'permit', 'person_photo'];
    if (!validTypes.includes(documentType)) {
      if (fs.existsSync(req.file.path)) fs.unlinkSync(req.file.path);
      return res.status(400).json({ error: 'Invalid document type' });
    }

    // Save document metadata to database
    const document = new Document({
      filename: path.basename(req.file.originalname),
      documentType,
      fileSize: req.file.size,
      mimeType: req.file.mimetype,
      filePath: req.file.path,
      status: 'uploaded',
    });

    await document.save();

    res.status(201).json({
      success: true,
      documentId: document._id,
      message: 'Document uploaded successfully',
      document: {
        id: document._id,
        filename: document.filename,
        documentType: document.documentType,
        status: document.status,
      },
    });
  } catch (error) {
    if (req.file) {
      if (fs.existsSync(req.file.path)) fs.unlinkSync(req.file.path);
    }
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/documents/:id
 * Retrieve document metadata
 */
router.get('/:id', async (req, res) => {
  try {
    const document = await Document.findById(req.params.id);
    if (!document) {
      return res.status(404).json({ error: 'Document not found' });
    }
    res.json(document);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
