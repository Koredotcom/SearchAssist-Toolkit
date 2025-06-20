const { Router } = require("express");
const router = Router({ strict: true });
const SearchService = require("../services/searchservice");

router.put("/onboard-users",SearchService.onboardUser);

module.exports = router;