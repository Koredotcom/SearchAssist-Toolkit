async function formatData(rawData, lookupFields) {
    try {
        if (!rawData || !lookupFields) throw new Error("rawData or Lookup fields are missing")
        const rootField = lookupFields?.rootField
        let raw_data = rawData[rootField] || []
        let formattedData = []

        for (let item of raw_data) {
            let data = {}
            data["id"] = item[lookupFields?.id] || ""
            data["title"] = item[lookupFields?.title] || ""
            data["content"] = item[lookupFields?.content] || ""
            data["url"] = item[lookupFields?.url] || ""
            data["type"] = item[lookupFields?.type] || ""
            data["doc_created_on"] = item[lookupFields?.doc_created_on] || ""
            data["doc_updated_on"] = item[lookupFields?.doc_updated_on] || ""
            data["rawData"] = item || {}
            data["sys_racl"] = item[lookupFields?.sys_racl] || ""
            data["sys_file_type"] = item[lookupFields?.sys_file_type] || "json"
            data["html"] = item[lookupFields?.html] || ""
            formattedData.push(data)
        }
        return { data: formattedData }
    } catch (err) {
        console.log("Error", err);
        throw new Error(err.message || "Error occured while formatting the raw data")
    }

}


module.exports = { formatData }