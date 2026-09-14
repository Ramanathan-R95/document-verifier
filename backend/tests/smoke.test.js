const request = require('supertest');

jest.mock('../src/config/database', () => ({
  connectDB: jest.fn(),
}));

jest.mock('../src/models/Document', () => {
  function MockDocument(data = {}) {
    this._id = data._id || 'doc-123';
    this.filename = data.filename || 'passport.png';
    this.documentType = data.documentType || 'passport';
    this.fileSize = data.fileSize || 1024;
    this.mimeType = data.mimeType || 'image/png';
    this.filePath = data.filePath || '/tmp/passport.png';
    this.status = data.status || 'uploaded';
    this.save = jest.fn().mockResolvedValue(this);
  }

  MockDocument.findById = jest.fn();

  return MockDocument;
});

jest.mock('../src/models/ScreeningCase', () => {
  function MockScreeningCase(data = {}) {
    this._id = data._id || 'case-123';
    this.caseId = data.caseId || 'CASE-123';
    this.documentId = data.documentId || 'doc-123';
    this.personPhotoId = data.personPhotoId || null;
    this.status = data.status || 'processing';
    this.requiresHumanReview = data.requiresHumanReview || false;
    this.save = jest.fn().mockResolvedValue(this);
  }

  MockScreeningCase.findById = jest.fn();
  MockScreeningCase.find = jest.fn().mockReturnValue({
    sort: jest.fn().mockReturnValue({
      limit: jest.fn().mockResolvedValue([]),
    }),
  });

  return MockScreeningCase;
});

jest.mock('../src/services/screeningService', () => ({
  runScreeningPipeline: jest.fn(),
}));

const app = require('../src/app');
const Document = require('../src/models/Document');
const ScreeningCase = require('../src/models/ScreeningCase');
const { runScreeningPipeline } = require('../src/services/screeningService');

describe('document screening API smoke tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('health endpoint is available', async () => {
    const response = await request(app).get('/api/health');

    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe('OK');
  });

  it('accepts a valid uploaded document', async () => {
    const response = await request(app)
      .post('/api/documents/upload')
      .field('documentType', 'passport')
      .attach('file', Buffer.from('fake-image-content'), {
        filename: 'passport.png',
        contentType: 'image/png',
      });

    expect(response.statusCode).toBe(201);
    expect(response.body.success).toBe(true);
    expect(response.body.document).toBeDefined();
  });

  it('rejects invalid document types', async () => {
    const response = await request(app)
      .post('/api/documents/upload')
      .field('documentType', 'forged_type')
      .attach('file', Buffer.from('fake-image-content'), {
        filename: 'passport.png',
        contentType: 'image/png',
      });

    expect(response.statusCode).toBe(400);
    expect(response.body.error).toMatch(/invalid document type/i);
  });

  it('runs screening analysis for an uploaded passport', async () => {
    const document = {
      _id: 'doc-123',
      documentType: 'passport',
      filePath: '/tmp/test-passport.png',
    };

    Document.findById.mockResolvedValue(document);
    runScreeningPipeline.mockResolvedValue({
      success: true,
      screeningCaseId: 'case-123',
      caseId: 'CASE-123',
      requiresHumanReview: false,
    });

    const response = await request(app)
      .post('/api/screening/analyze')
      .send({ documentId: 'doc-123' });

    expect(response.statusCode).toBe(200);
    expect(response.body.success).toBe(true);
    expect(response.body.screeningCaseId).toBe('case-123');
    expect(runScreeningPipeline).toHaveBeenCalledWith('case-123', document, null);
    expect(ScreeningCase.findById).not.toHaveBeenCalled();
  });

  it('returns screening history via the history endpoint', async () => {
    const response = await request(app).get('/api/screening/history');

    expect(response.statusCode).toBe(200);
    expect(Array.isArray(response.body)).toBe(true);
  });

  it('accepts a valid person photo id during analysis', async () => {
    const document = {
      _id: 'doc-123',
      documentType: 'passport',
      filePath: '/tmp/test-passport.png',
    };

    const personPhoto = {
      _id: 'photo-456',
      documentType: 'person_photo',
      filePath: '/tmp/person.png',
    };

    Document.findById.mockImplementation((id) => {
      if (id === 'doc-123') return Promise.resolve(document);
      if (id === 'photo-456') return Promise.resolve(personPhoto);
      return Promise.resolve(null);
    });

    runScreeningPipeline.mockResolvedValue({
      success: true,
      screeningCaseId: 'case-123',
      caseId: 'CASE-123',
      requiresHumanReview: false,
    });

    const response = await request(app)
      .post('/api/screening/analyze')
      .send({ documentId: 'doc-123', personPhotoId: 'photo-456' });

    expect(response.statusCode).toBe(200);
    expect(response.body.success).toBe(true);
    expect(runScreeningPipeline).toHaveBeenCalledWith('case-123', document, 'photo-456');
  });
});
