const { readConfig } = require('../utils/readConfig')
const { default: axios } = require("axios")
const { formatData } = require('../utils/formatData')

/**
 * Build Basic Auth headers for the upstream source API.
 * @param {Object} config
 * @returns {Object}
 */
function buildSourceHeaders(config) {
    const username = config?.authDetails?.username;
    const password = config?.authDetails?.password;
    const accessToken = Buffer.from(`${username || ''}:${password || ''}`).toString('base64');
    return {
        Authorization: `Basic ${accessToken}`,
        Accept: 'application/json',
        'Content-Type': 'application/json'
    };
}

/**
 * Formats a timestamp using a configured token pattern.
 * Supported tokens: YYYY, MM, DD, HH, mm, ss. Values are UTC.
 * Falls back to an ISO timestamp when no pattern is configured.
 * @param {string} lastSyncTime - ISO timestamp supplied by Findly.
 * @param {string} [dateFormat] - Token pattern, e.g. "YYYY-MM-DD HH:mm:ss".
 * @returns {string} Timestamp formatted for the source query.
 */
function formatSourceDate(lastSyncTime, dateFormat) {
    const parsedDate = new Date(lastSyncTime)
    if (Number.isNaN(parsedDate.getTime())) {
        throw new Error('Query parameter "lastSyncTime" must be a valid date.')
    }

    if (!dateFormat) {
        return parsedDate.toISOString()
    }

    const pad = (value) => String(value).padStart(2, '0')
    const tokens = {
        YYYY: parsedDate.getUTCFullYear(),
        MM: pad(parsedDate.getUTCMonth() + 1),
        DD: pad(parsedDate.getUTCDate()),
        HH: pad(parsedDate.getUTCHours()),
        mm: pad(parsedDate.getUTCMinutes()),
        ss: pad(parsedDate.getUTCSeconds())
    }
    return dateFormat.replace(/YYYY|MM|DD|HH|mm|ss/g, (token) => tokens[token])
}

/**
 * Renders a configured filter template, substituting the {date} placeholder.
 * The template holds all source-specific syntax, so no query dialect is
 * hard-coded here.
 * @param {Object} queryConfig - Filter configuration holding template/dateFormat.
 * @param {string} lastSyncTime - ISO timestamp supplied by Findly.
 * @returns {string} Rendered filter expression.
 */
function renderFilterTemplate(queryConfig, lastSyncTime) {
    const formattedDate = formatSourceDate(lastSyncTime, queryConfig?.dateFormat)
    return String(queryConfig.template).split('{date}').join(formattedDate)
}

/**
 * Adds the configured incremental filter to the upstream request parameters.
 * Without a configured template, isIncremental/lastSyncTime are forwarded as-is.
 * @param {Object} params - Existing upstream query parameters.
 * @param {Object} incrementalConfig - Incremental query configuration.
 * @param {string} lastSyncTime - ISO timestamp supplied by Findly.
 * @returns {Object} Query parameters containing the incremental filter.
 */
function addIncrementalQuery(params, incrementalConfig, lastSyncTime) {
    const queryParam = incrementalConfig?.queryParam
    if (!queryParam || !incrementalConfig?.template) {
        return {
            ...params,
            isIncremental: true,
            lastSyncTime
        }
    }

    const filter = renderFilterTemplate(incrementalConfig, lastSyncTime)
    const existingQuery = params[queryParam]
    const separator = existingQuery ? (incrementalConfig.separator || '') : ''
    return {
        ...params,
        [queryParam]: `${existingQuery || ''}${separator}${filter}`
    }
}

/**
 * Builds the upstream query params for the deleted-items request.
 * Without a configured template, lastSyncTime is forwarded as-is.
 * @param {Object} deletionQuery - Deletion query configuration.
 * @param {string} lastSyncTime - ISO timestamp supplied by Findly.
 * @param {string} limit - Page size.
 * @param {string} offset - Page offset.
 * @param {string} limitKey - Source page size param name.
 * @param {string} offsetKey - Source offset param name.
 * @returns {Object} Query params for the deletion request.
 */
function buildDeletionParams(deletionQuery, lastSyncTime, limit, offset, limitKey, offsetKey) {
    const params = {
        [limitKey]: limit,
        [offsetKey]: offset
    }

    const queryParam = deletionQuery?.queryParam
    if (!queryParam || !deletionQuery?.template) {
        params.lastSyncTime = lastSyncTime
        return params
    }

    params[queryParam] = renderFilterTemplate(deletionQuery, lastSyncTime)
    if (deletionQuery?.fieldsParam && deletionQuery?.idField) {
        params[deletionQuery.fieldsParam] = deletionQuery.idField
    }
    return params
}

/**
 * Extracts deleted document ids from the upstream response.
 * @param {Object} body - Upstream response body.
 * @param {Object} deletionQuery - Deletion query configuration.
 * @returns {string[]} Deleted document ids.
 */
function extractDeletedIds(body, deletionQuery) {
    const rootField = deletionQuery?.rootField
    const idField = deletionQuery?.idField

    // Source already returns the Findly contract.
    if (Array.isArray(body?.ids)) {
        return body.ids.map((id) => String(id).trim()).filter(Boolean)
    }

    if (!rootField || !idField) {
        return []
    }

    const rows = Array.isArray(body?.[rootField]) ? body[rootField] : []
    return rows
        .map((row) => row?.[idField])
        .map((id) => (id === undefined || id === null ? '' : String(id).trim()))
        .filter(Boolean)
}

/**
 * GET /getContent — list/map content for Search Assist.
 * Findly may pass isIncremental + lastSyncTime; the configured source filter is applied.
 */
const get_content_controller = async (req, res) => {
    try {
        if (!req?.query?.limit || !req?.query?.offset) return res.status(400).json({ error: 'The request parameters is missing.' })

        const limit = req?.query?.limit
        const offset = req?.query?.offset
        const isIncremental = req?.query?.isIncremental === true || req?.query?.isIncremental === 'true'
        const lastSyncTime = req?.query?.lastSyncTime

        const config = await readConfig()

        const apiUrl = config?.configuration?.api?.contentUrl
        const method = config?.configuration?.api?.method || 'GET'
        const headers = buildSourceHeaders(config)

        const limitKey = config?.configuration?.pagination?.limit
        const offsetKey = config?.configuration?.pagination?.offset

        let params = {
            ...(config?.configuration?.api?.queryParams || {})
        }
        params[limitKey] = limit
        params[offsetKey] = offset

        // Convert Findly's incremental timestamp into the source API's configured query.
        if (isIncremental && lastSyncTime) {
            console.log("Incremental Sync is enabled")
            params = addIncrementalQuery(
                params,
                config?.configuration?.api?.incrementalQuery,
                lastSyncTime
            )
        }
        console.log("Params for the Content API", params)
        const response = await axios({
            url: apiUrl,
            method,
            headers,
            params
        })
        console.log("Response from the Content API", response?.data)
        let data = await formatData(response?.data, config?.configuration?.lookupFields)
        const hasMoreKey = config?.configuration?.hasMore
        const headerLinkData = response?.headers?.link
        data['isContentAvailable'] = (headerLinkData && headerLinkData.includes(hasMoreKey)) ?? JSON.stringify(data).includes(hasMoreKey);
        return res.json(data)

    } catch (error) {
        console.error('Error fetching data ', error.message)
        return res.status(500).json({ error: error.message || "Failed to fetch data" })
    }
}

/**
 * GET /getDeletedItems?lastSyncTime=&limit=&offset=
 *
 * Queries configuration.deletionUrl for documents deleted since lastSyncTime,
 * then returns { ids, isContentAvailable } for Findly.
 */
const get_deleted_items_controller = async (req, res) => {
    try {
        const lastSyncTime = req?.query?.lastSyncTime
        if (!lastSyncTime) {
            return res.status(400).json({ error: 'Query parameter "lastSyncTime" is required.' })
        }

        const limit = req?.query?.limit || '30'
        const offset = req?.query?.offset || '0'
        const config = await readConfig()
        const deletionUrl = config?.configuration?.deletionUrl

        if (!deletionUrl) {
            return res.json({ ids: [], isContentAvailable: false })
        }

        const headers = buildSourceHeaders(config)
        const limitKey = config?.configuration?.pagination?.limit || 'limit'
        const offsetKey = config?.configuration?.pagination?.offset || 'offset'
        const deletionQuery = config?.configuration?.deletionQuery

        const params = buildDeletionParams(
            deletionQuery,
            lastSyncTime,
            limit,
            offset,
            limitKey,
            offsetKey
        )

        const response = await axios({
            url: deletionUrl,
            method: 'GET',
            headers,
            params
        })

        const body = response?.data || {}
        const ids = extractDeletedIds(body, deletionQuery)

        // Sources returning raw rows have no hasMore flag, so infer it from page fullness.
        const rows = Array.isArray(body?.[deletionQuery?.rootField])
            ? body[deletionQuery.rootField]
            : null
        const isContentAvailable = rows
            ? rows.length >= parseInt(String(limit), 10)
            : body.isContentAvailable === true

        console.log(`Deleted items since ${lastSyncTime}: ${ids.length} id(s), more=${isContentAvailable}`)
        return res.json({ ids, isContentAvailable })
    } catch (error) {
        console.error('Error fetching deleted items ', error.message)
        const status = error?.response?.status || 500
        return res.status(status).json({
            error: error.message || 'Failed to fetch deleted items'
        })
    }
}

module.exports = { get_content_controller, get_deleted_items_controller }
