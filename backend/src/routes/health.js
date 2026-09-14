const express = require('express');
const router = express.Router();

router.get('/', (req, res) => {
  res.json({ status: 'OK', message: 'Document Screening API is running' });
});

module.exports = router;
