const { readConfig } = require('../utils/readConfig')
const { default: axios } = require("axios")
const fs = require('fs');
const path = require('path')

const get_content_controller = async (req, res) => {
    try {
        if (!req?.query?.limit || !req?.query?.offset) return res.status(400).json({ error: 'The request parameters is missing.' })

        const limit = req?.query?.limit
        const offset = req?.query?.offset

        const config = await readConfig()


        const apiUrl = config?.configuration?.api?.contentUrl
        const method = config?.configuration?.api?.method

        const credentials = {
            username: config?.authDetails?.username,
            password: config?.authDetails?.password
        };

        const accessToken = Buffer.from(`${credentials.username}:${credentials.password}`).toString('base64');

        const headers = {
            "Authorization": `Basic ${accessToken}`,
            "Accept": "application/json",
            "Content-Type": "application/json"
        };

        const limitKey = config?.configuration?.pagination?.limit
        const offsetKey = config?.configuration?.pagination?.offset

        let params = {}
        params[limitKey] = limit
        params[offsetKey] = offset

        const reqOptions = {
            url: apiUrl,
            method: method,
            headers: headers,
            params: params
        }

        /**
         *  Uncomment this as per requirement
         * 
         *  const response = await axios(reqOptions)
            let data=response?.data
            const hasMoreKey=config?.configuration?.hasMore
            //this check is only for service now api
            const headerLinkData=response?.headers?.link
            const isContentAvailable=!headerLinkData?JSON.stringify(data).includes(hasMoreKey):JSON.stringify(data).includes(hasMoreKey) || headerLinkData.includes(hasMoreKey)
            data['isContentAvailable']=isContentAvailable
            return res.json(data)
         */

        // For testing purposes: Read from a sample file
        const filePath = limit === "1"
            ? path.join(__dirname, '../sampleDoc.txt')
            : path.join(__dirname, '../sampleDocs.txt');
        fs.readFile(filePath, 'utf8', (err, data) => {
            if (err) {
                return res.status(500).json({ error: 'Failed to read the file.' });
            }
            try {
                const jsonData = JSON.parse(data);
                return res.json(jsonData);
            } catch (parseError) {
                // Handle JSON parse errors
                return res.status(500).json({ error: 'Failed to parse the file content.' });
            }
        });

    } catch (error) {
        console.error('Error fetching data ', error.message)
        return res.status(500).send('Failed to fetch data')

    }

}

module.exports = { get_content_controller }