const { Router } = require('express');
const router = Router({ strict: true });
const services = require('../services/services');

router.post('/webhook', services.getAnswer);
router.post('/one-week-threads', services.pushOneWeekThreads);

module.exports = router;