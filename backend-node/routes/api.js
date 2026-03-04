const express = require('express');
const axios = require('axios');
const Document = require('../models/Document');
const Audit = require('../models/Audit');
const User = require('../models/User');
const { protect } = require('../middleware/auth');
const upload = require('../config/multer');

const router = express.Router();

// POST /api/upload
router.post('/upload', protect, upload.single('document'), async (req, res) => {
    const io = req.app.get('io');
    try {
        if (!req.file) return res.status(400).json({ success: false, message: 'No file uploaded.' });

        const { docType = 'other', region = 'national', country = 'IN', field = 'legal', industry = 'general', language = 'en' } = req.body;

        const document = await Document.create({
            user: req.user._id,
            filename: req.file.filename,
            originalName: req.file.originalname,
            mimeType: req.file.mimetype,
            size: req.file.size,
            docType, region, country, field, industry,
            storagePath: req.file.path,
            status: 'processing',
        });

        const audit = await Audit.create({ user: req.user._id, document: document._id, language, status: 'processing' });

        res.status(202).json({ success: true, message: 'Analysis started.', auditId: audit._id, documentId: document._id });

        const roomId = req.user._id.toString();
        io.to(roomId).emit('audit:start', { auditId: audit._id });

        processWithAI({ document, audit, language, country, region, io, roomId });
    } catch (err) {
        console.error('Upload error:', err);
        res.status(500).json({ success: false, message: 'Upload failed.' });
    }
});

async function processWithAI({ document, audit, language, country, region, io, roomId }) {
    const start = Date.now();
    try {
        io.to(roomId).emit('audit:progress', { auditId: audit._id, message: 'Extracting document text...' });
        io.to(roomId).emit('audit:progress', { auditId: audit._id, message: 'AI is reading your document...' });

        // Build FormData to send the actual file to Python
        const FormData = require('form-data');
        const fs = require('fs');
        const form = new FormData();

        form.append('file', fs.createReadStream(document.storagePath), document.originalName);
        if (language && language !== 'en') form.append('target_language', language);
        if (country) form.append('jurisdiction', country);
        if (document.docType) form.append('document_type', document.docType);

        const { data } = await axios.post(
            `${process.env.PYTHON_API_URL}/analyze`,
            form,
            { headers: form.getHeaders(), timeout: 120_000 }
        );

        let scoreLabel = 'HIGH_RISK';
        if (data.legalScore >= 71) scoreLabel = 'LOW_RISK';
        else if (data.legalScore >= 41) scoreLabel = 'MEDIUM_RISK';

        await Audit.findByIdAndUpdate(audit._id, {
            legalScore: data.legalScore, scoreLabel,
            clauses: data.clauses || [],
            summary: data.summary || [],
            summaryTranslated: data.summaryTranslated || {},
            jurisdictionFlags: data.jurisdiction_flags || [],
            processingTimeMs: Date.now() - start,
            status: 'complete',
        });

        await Document.findByIdAndUpdate(document._id, { status: 'analyzed' });
        await User.findByIdAndUpdate(document.user, { $inc: { auditCount: 1 } });

        io.to(roomId).emit('audit:complete', { auditId: audit._id, legalScore: data.legalScore, scoreLabel });
    } catch (err) {
        console.error('AI processing failed:', err.message);
        await Audit.findByIdAndUpdate(audit._id, { status: 'failed', errorMessage: err.message });
        await Document.findByIdAndUpdate(document._id, { status: 'failed' });
        io.to(roomId).emit('audit:error', { auditId: audit._id, message: 'Analysis failed. Please try again.' });
    }
}

// GET /api/audits
router.get('/audits', protect, async (req, res) => {
    try {
        const { page = 1, limit = 10 } = req.query;
        const skip = (page - 1) * limit;
        const [audits, total] = await Promise.all([
            Audit.find({ user: req.user._id })
                .populate('document', 'originalName docType region createdAt')
                .sort({ createdAt: -1 }).skip(skip).limit(parseInt(limit)),
            Audit.countDocuments({ user: req.user._id }),
        ]);
        res.json({ success: true, audits, pagination: { page: parseInt(page), limit: parseInt(limit), total } });
    } catch (err) {
        res.status(500).json({ success: false, message: 'Failed to fetch audits.' });
    }
});

// GET /api/audits/:id
router.get('/audits/:id', protect, async (req, res) => {
    try {
        const audit = await Audit.findOne({ _id: req.params.id, user: req.user._id }).populate('document');
        if (!audit) return res.status(404).json({ success: false, message: 'Audit not found.' });
        res.json({ success: true, audit });
    } catch (err) {
        res.status(500).json({ success: false, message: 'Failed to fetch audit.' });
    }
});

module.exports = router;