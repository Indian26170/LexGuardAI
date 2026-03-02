const express = require('express');
const router = express.Router();

// Placeholder for Login
router.post('/login', (req, res) => {
    res.json({ message: 'Login endpoint' });
});

// Placeholder for Register
router.post('/register', (req, res) => {
    res.json({ message: 'Register endpoint' });
});

module.exports = router;
