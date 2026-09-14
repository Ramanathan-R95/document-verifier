/**
 * Middleware for request validation
 */

const validateFileUpload = (req, res, next) => {
  if (!req.body.documentType) {
    return res.status(400).json({ error: 'documentType is required' });
  }
  next();
};

module.exports = {
  validateFileUpload,
};
