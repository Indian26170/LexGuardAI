const express = require('express');
const router = express.Router();
const multer = require('multer');
const upload = multer({ dest: 'uploads/' });

// Placeholder API endpoint
router.get('/', (req, res) => {
    res.json({ message: 'API works' });
});

// File upload placeholder
router.post('/upload', upload.single('file'), (req, res) => {
    res.json({ message: 'File uploaded' });
});

module.exports = router;
