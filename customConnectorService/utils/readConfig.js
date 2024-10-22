// const fs = require('fs');
const fs = require('fs/promises');
const path = require('path'); 
 
 async function  readConfig(){
    const filePath = path.join(__dirname, '..','config/config.json');
    console.log('in read config',filePath)
    try {
    const data = await fs.readFile(filePath, 'utf8')
    const jsonData = JSON.parse(data);
    console.log(jsonData)
    return jsonData;
    } catch (error) {
    // JSON parse error
    if (error.code === 'ENOENT') {
      // File not found
      console.log('File not found')
      throw new Error("File not found'")
    } else {
      // Other errors
      console.log('Other errors', error)
      throw  new Error("An error occurred while reading the file")

    }
  }
}

module.exports = { readConfig }