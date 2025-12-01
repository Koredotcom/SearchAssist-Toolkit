

//verify the token 
const checkAuthorized = async function (req, res, next) {
    try {
        const configHeader = req.headers['x-header-config'];
        
        if (!configHeader) {
            // Fallback to old simple authorization check
            const authHeaders = req.headers.authorization || req.headers.Authorization;
            if (authHeaders === Buffer.from(process.env.Authorization).toString('base64')) {
                return next();
            }
            return res.status(403).json({ error: 'Forbidden: Invalid Authorization header' });
        }
        
        // New config-based validation
        const headerConfigs = JSON.parse(Buffer.from(configHeader, 'base64').toString('utf-8')).map(c => ({...c, encodingFormat: c.encodingFormat || 'base64'}));
        
        for (const config of headerConfigs) {
            const incomingValue = req.headers[config.key] || req.headers[config.key.toLowerCase()];
            const expectedValue = process.env[config.key];
            const decodedValue = config.encodingFormat === 'base64' ? Buffer.from(incomingValue, 'base64').toString('utf-8') : incomingValue;
            
            if (decodedValue !== expectedValue) {
                return res.status(403).json({ error: `Forbidden: Invalid ${config.key}` });
            }
        }
        
        next();
    } catch (err) {
        console.log(err);
        return res.status(403).json({ error: 'Forbidden: Authorization error' });
    }
}

module.exports = {
    checkAuthorized
}
