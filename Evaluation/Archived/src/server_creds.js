const express = require("express");
const bodyParser = require("body-parser"); // for parsing JSON in request body
const fs = require("fs");
const csv = require("csv-parser");

const app = express();
const port = 3000; // Set your desired port
const jsonFilePath = "../config/creds.json";

app.use(bodyParser.json());

// Function to read and extract credentials from JSON file
function readCredentials(filePath) {
  try {
    const data = fs.readFileSync(filePath);
    const credentials = JSON.parse(data);

    if (!credentials) {
      console.log("No valid credentials found.");
      return null;
    }

    const {
      host,
      auth_token,
      stream_id,
      search_index_id,
      index_pipeline_id,
      query_pipeline_id,
      user_id,
      embedings_model,
      start_index
    } = credentials;

    return {
      host,
      auth_token,
      stream_id,
      search_index_id,
      index_pipeline_id,
      query_pipeline_id,
      user_id,
      embedings_model,
      start_index
    };
  } catch (error) {
    console.error(`Error reading JSON file ${filePath}: ${error.message}`);
    return null;
  }
}

// Function to read and parse CSV file
function readCSV(filePath, fieldsToAdd) {
  return new Promise((resolve, reject) => {
    const csvData = [];

    fs.createReadStream(filePath)
      .pipe(csv())
      .on("data", (row) => {
        // Append the specified fields to each row with empty strings
        fieldsToAdd.forEach((field) => {
          if (!row.hasOwnProperty(field)) {
            row[field] = "";
          }
        });

        csvData.push(row);
      })
      .on("end", () => {
        resolve(csvData);
      })
      .on("error", (error) => {
        reject(error);
      });
  });
}

// Example usage
// const filePath = "data/user_query.csv";
const fieldsToAdd = ["Expected_Title", "Expected_URL"]; // Replace with your desired field names

// readCSV(filePath, fieldsToAdd)
//   .then((csvData) => {
//    console.log("Processed CSV Data:", csvData);
//   })
//   .catch((error) => {
//     console.error(`Error reading CSV file ${filePath}: ${error.message}`);
//   });



app.post("/sendData", async (req, res) => {
  try {
    const { FilePath: csvFilePath } = req.body;

    try {
      var credentials = readCredentials(jsonFilePath);
    } catch (error) {
      console.error(`Error processing credentials: ${error.message}`);
    }

    try {
      var csv_data = await readCSV(csvFilePath, fieldsToAdd);
    } catch (error) {
      console.error(`Error reading CSV file ${csvFilePath}: ${error.message}`);
    }

    // console.log("Credentials:", credentials);
    // console.log("CSV Data:", csv_data);
    res.json({ credentials, csv_data });
  } catch (error) {
    console.error(`Error processing data: ${error.message}`);
    res.status(500).json({ error: error.message });
  }
});

app.listen(port, () => {
  const baseUrl = `http://localhost:${port}`;
  console.log(`Server is listening on port ${port}`);
  console.log(`Server URL: ${baseUrl}`);
});
