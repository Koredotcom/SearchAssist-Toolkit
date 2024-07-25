const express = require("express");
const bodyParser = require("body-parser"); // for parsing JSON in request body

const app = express();
const fs = require("fs");
const port = 3000; // Set your desired port
const axios = require("axios");
const { serialize } = require("v8");
const fuzzball = require("fuzzball");
const path = require("path");
const similarity = require('compute-cosine-similarity');
const { constrainedMemory } = require("process");

const CSV_file_path = "../data/user_query.csv";
const output_file_path = "../output/output.csv";
const jsonFilePath = "../config/creds.json";

app.use(bodyParser.json());

let headers;

let payload = {
  query: "Upgrade Quick Reference?",
  maxNumOfResults: 5,
  streamId: "st-123",
  lang: "en",
  isDev: true,
  customize: false,
  answerSearch: true,
  includeChunksInResponse:true,
  userId: "u-123",
  indexPipelineId: "fip-123",
  queryPipelineId: "fqp-123",
  messagePayload: {
    clientMessageId: 1703526077652,
    message: {
      body: "How are Horizon Air operated flights (series 2000-2999) treated, and are there any exceptions?",
    },
    resourceId: "/bot.message",
    timeDateDay: "25/12/2023, 23:11:17",
    currentPage: "https://searchassist-app.kore.ai/home/",
    meta: {
      timezone: "Asia/Calcutta",
      locale: "en-US",
    },
    location: "Hyderabad",
    country: "India",
    client: "botbuilder",
    botInfo: {
      chatBot: "automate_testing",
      taskBotId: "st-123",
      customData: {
        userContext: {},
      },
    },
  },
  pageNumber: 0,
};

//server 1 code
const embedings_headers = {
  "Content-Type": "application/json",
};

const embeddings_apiUrl = "http://127.0.0.1:5000/process_string/embed";

async function generate_embeddings(sentence) {
  try {
    const postData = {
      inputs: sentence,
    };
    const response = await axios.post(embeddings_apiUrl, postData, {
      embedings_headers,
    });
    return response.data;
  } catch (error) {
    console.error("Error:", error.message);
  }
}

const { pipeline } = require('stream');
const { Readable } = require('stream');

function appendToCSV(jsonObject, filePath) {
  // Convert the JSON object to a CSV row
  try {
  const csvRow = Object.values(jsonObject).map(value => `"${value}"`).join(',');  
  fs.appendFileSync(filePath, csvRow + '\n');
  console.log('Data appended to CSV file successfully.');
} catch (error) {
  console.error('Error appending data to CSV file:', error.message);
  throw error;
}
}

function appendToJSON(jsonObject, filePath) {
  // Convert the JSON object to a CSV row
  let existingData = [];
  try{
    try {
      existingData = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    } catch (err) {
      // If the file doesn't exist or has invalid JSON, start with an empty array
    }
    
    // Append the new data to the existing array
    existingData = existingData.concat(jsonObject);
    
    // Stringify the updated JSON data
    const updatedJson = JSON.stringify(existingData, null, 2); // The third argument (2) is the number of spaces for indentation
    
    // Write the updated JSON data back to the file
    fs.writeFileSync(filePath, updatedJson, 'utf8');
    console.log('Data appended to JSON file successfully.');

  }
  catch(error){
    console.error('Error appending data to CSV file:', error.message);
    throw error;
  }
  }
 


async function makeAPostRequest(query, details) {
  const host = details["host"];
  const auth_token = details["auth_token"];
  const stream_id = details["stream_id"];
  const search_index_id = details["search_index_id"];
  const index_pipeline_id = details["index_pipeline_id"];
  const query_pipeline_id = details["query_pipeline_id"];
  const user_id = details["user_id"];
  const search_url =
    host +
    "/searchassistapi/businessapp/searchsdk/stream/" +
    stream_id +
    "/" +
    search_index_id +
    "/search";

  payload["query"] = query;
  payload["queryPipelineId"] = query_pipeline_id;
  payload["indexPipelineId"] = index_pipeline_id;
  payload["streamId"] = stream_id;
  payload["userId"] = user_id;
  headers = { Authorization: auth_token, "Content-Type": "application/json" };

  let search_answer_response;
  let debug_answer_response;

  try {
    const search_response = await axios.post(search_url, payload, { headers });
    await new Promise((resolve) => setTimeout(resolve, 2000));
    search_answer_response = search_response.data;

    const debug_url = `${host}/searchassistapi/businessapp/searchsdk/stream/${stream_id}/${search_index_id}/context/${query_pipeline_id}`;

    try {
      const debug_response = await axios.get(debug_url, { headers });
      debug_answer_response = debug_response.data;

      return {
        search_answer_response,
        debug_answer_response,
        search_error: null,
        debug_error: null,
      };
    } catch (debug_error) {
      console.error(`Debug Error: ${debug_error}`);
      return {
        search_answer_response,
        debug_answer_response: null,
        search_error: null,
        debug_error,
      };
    }
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      console.error(
        `HTTP Error: ${error.response.status} - ${error.response.statusText}`
      );
    } else {
      console.error(`Error: ${error.message}`);
    }

    return {
      search_answer_response: null,
      debug_answer_response: null,
      debug_error: null,
      search_error,
    };
  }
}

async function get_config_data(query_sheet_path) {
  try {
    const response = await axios.post("http://localhost:3000/sendData", {
      FilePath: query_sheet_path,
    });
    return response.data;
  } catch (error) {
    console.error(error);
  }
}

async function fuzzyMatch(ref, refList) {

  for (let i = 0; i < refList.length; i++) {
    const ratio = fuzzball.ratio(ref, refList[i]);
    if (ratio >=85) {
      return ratio;
    }
  }
  return 0;
}

async function ansFuzzyMatch(ref, refList) {
  let max = 0
  let index = -1
  let ref_index_data
  for (i = 0; i < refList.length; i++) {
    const ratio = fuzzball.partial_ratio(ref, refList[i]);
    if (ratio > max) {
      max = ratio
      index = i
      // console.log(`into the loop >>> i : ${i} max : ${max}`)
    }
  }
  return [max, index, refList[index]];
}

async function directStringComparison(ref, refList) {
  for (i = 0; i < refList.length; i++) {
    if (ref === refList[i]) {
      return [true, i, refList[i]]
    }
  }
  return [false, -1];
}

async function stringIncludes(ref, refList) {

  for (let i = 0; i < refList.length; i++) {
    if (ref.includes(refList[i])) {
      return [true, i, refList[i]]
    }
  }
  return [false, -1];
}

async function get_metrics(user_input, snippet_title, snippet_content, snippet_urls, snippet_scores = [], embedings_model,debug = false) {
  const result_metrics = {}
  try {
    snippet_urls = snippet_urls.map(url => decodeURIComponent(url))
  const url_status = await fuzzyMatch(user_input.Expected_URL, snippet_urls);
  const title_status = await fuzzyMatch(user_input.Expected_Title, snippet_title);
  //   console.log(`URL_score : ${url_status}, title_status : ${title_status}`)

  //   const result={ans_snipprt:,ans_staus,url_status,title_status}
  result_metrics['url_status'] = url_status
  result_metrics['title_status'] = title_status
  if (!debug){
    result_metrics['actual_title'] = snippet_title[0];
    result_metrics['actual_url'] = snippet_urls[0];
    result_metrics['actual_score'] = snippet_scores[0];
  }
  const direct_content_score = await directStringComparison(user_input.Expected_Ans, snippet_content);
  result_metrics['Chunk_number_direct_content_score'] = direct_content_score[1]

  if (!direct_content_score[0]) {
    const stringInclude_score = await stringIncludes(user_input.Expected_Ans, snippet_content);
    result_metrics['Chunk_number_stringInclude_score'] = stringInclude_score[1]

    if (!stringInclude_score[0]) {
      const content_score = await ansFuzzyMatch(user_input.Expected_Ans, snippet_content);
      //   console.log(`score : ${content_score}`)
      result_metrics['Chunk_number'] = content_score[1]
      result_metrics['data_index'] = content_score[2]

      if (content_score[0] < 85) {
        result_metrics['Ans_Status'] = false
        result_metrics['Chunk_number'] = -1

        if (embedings_model) {
          // console.log("----entering into fourth stage----")

          const embedding1 = await generate_embeddings(snippet_content);
          const embedding2 = await generate_embeddings(user_input.Expected_Ans);

          let max_embedding_score = 0
          let index_embedding
          let cosineSimilarity
          let embedding_data_index

          for (let i = 0; i < embedding1.length; i++) {
            cosineSimilarity = similarity(embedding1[i], embedding2)
            // console.log(`${cosineSimilarity} ---- ${embedding1.length} ---- ${snippet_content.length}`)
            if (max_embedding_score < cosineSimilarity) {
              max_embedding_score = cosineSimilarity
              index_embedding = i
              embedding_data_index = snippet_content[i]
              // console.log(`entered loop >> ${max_embedding_score} >> index at ${index_embedding}`)
            }
          }

          result_metrics['data_index'] = embedding_data_index

          // console.log(`cosineSimilarity : ${max_embedding_score}`)
          if (max_embedding_score < 0.85) {
            result_metrics['Ans_Status'] = false;
          }
          else {
            result_metrics['Ans_Status'] = true
            result_metrics['Chunk_number'] = index_embedding

          }
        }
      }
      else {
        result_metrics['Ans_Status'] = true
        result_metrics['data_index'] = content_score[2]
      }
    }
    else {
      result_metrics['Ans_Status'] = true
      result_metrics['data_index'] = stringInclude_score[2]
    }
  }
  else {
    result_metrics['Ans_Status'] = true
    result_metrics['data_index'] = direct_content_score[2]
  }
  }
  catch(error){
    console.log(error)
  }

  return result_metrics;
}

async function pre_processing(search_call, user_input, embedings_model) {
  let payload_response
  try {
    payload_response = search_call["search_answer_response"]["template"]["graph_answer"]["payload"];
    // console.log(`Payload : ${payload_response}`);
    let input_data = {};
    let snippet_title = [];
    let snippet_content = [];
    let snippet_urls = [];
    let snippet_scores = [];
    let snippet_type = "";
    if(Object.keys(payload_response).length){
      snippet_type =
      search_call["search_answer_response"]["template"]["graph_answer"][
      "payload"
      ]["center_panel"]["data"][0]["snippet_type"];
      if (snippet_type == "extractive_model") {
        input_data = payload_response["center_panel"]["data"][0];
        if (Array.isArray(input_data.snippet_content) && input_data.snippet_content.length > 0) {
          snippet_content_as_string = input_data.snippet_content.join("\n");
        } 
        else{
          snippet_content_as_string = input_data.snippet_content
        }
        snippet_title.push(input_data.snippet_title);
        snippet_content.push(snippet_content_as_string);
        snippet_urls.push(input_data.url);
        snippet_scores.push(input_data.score);
  
      } else {
        input_data =
        payload_response["center_panel"]["data"][0]["snippet_content"];
        for (let i = 0; i < input_data.length; i++) {
          snippet_content.push(input_data[i]["answer_fragment"]);
          snippet_title.push(input_data[i]["sources"][0]["title"]);
          snippet_urls.push(input_data[i]["sources"][0]["url"]);
          snippet_scores.push("NA")
        }
      }
  
    }
  

    // model performance
    let result_metrics = await get_metrics(user_input, snippet_title, snippet_content, snippet_urls, snippet_scores,embedings_model);
    result_metrics["Model_used"] = snippet_type
    // console.log(result_metrics)

    // calling Debuuger if the ans status is false
    let debugger_input_data = {}
    let debugger_chunk_content = []
    let debugger_chunk_url = []
    let debugger_chunk_score = []
    let debugger_chuck_title = []
    let debugger_result_metrics

    if (search_call['debug_answer_response'] ) {
      // console.log("<<<<<<<<<<<<<<<<<< Debugger >>>>>>>>>>>>>>>>>")

      if (search_call["debug_answer_response"]["answer_debug"]["generative_answers"]) {
        debugger_input_data = search_call["debug_answer_response"]["answer_debug"]["generative_answers"]["qualified_chunks"]["chunks"];
      }
      else if (search_call["debug_answer_response"]["answer_debug"]["extractive_answers"]) {
        debugger_input_data = search_call["debug_answer_response"]["answer_debug"]["extractive_answers"]["qualified_chunks"]["chunks"]; 
      }
      for (let i = 0; i < debugger_input_data.length; i++) {
        debugger_chunk_content.push(debugger_input_data[i]["chunk_text"]);
        debugger_chunk_url.push(debugger_input_data[i]["source_url"]);
        debugger_chunk_score.push(debugger_input_data[i]["score"])
        chunk_more_info = debugger_input_data[i]['more_info']
        let chunk_title = debugger_input_data[i]["source_name"]
        if (chunk_more_info) {
          chunk_more_info.forEach(item => {
            if (item.key === "Chunk Title") {
              chunk_title = item.value;
            }
          });
        }
        debugger_chuck_title.push(chunk_title);
      }

      // console.log(debugger_chunk_content)
      // console.log(debugger_chunk_url)
      // console.log(debugger_chuck_title)

      debugger_result_metrics = await get_metrics(user_input, debugger_chuck_title, debugger_chunk_content, debugger_chunk_url,debugger_chunk_score, embedings_model,true)
      debugger_result_metrics['debug_payload'] = debugger_input_data
      // console.log(debugger_result_metrics)
    }

    return {
      "result_metrics": result_metrics,
      "debugger_result_metrics": debugger_result_metrics
    }


  } catch (error) {
    if (Object.keys(payload_response).length === 0 && payload_response.constructor === Object) {
      // console.log("Payload is empty");
    }
    else {
      console.log(`Unable to retrieve the information, ${error}`);
    }
  }


}

async function updateJsonFile(filePath, keyToUpdate, newValue) {

  // Read the existing JSON data from the file
  const existingData = JSON.parse(fs.readFileSync(filePath, 'utf8'));

  // Update the specific key with the new value
  existingData[keyToUpdate] = newValue;

  // Write the updated data back to the file
  fs.writeFileSync(filePath, JSON.stringify(existingData, null, 2), 'utf8');

  // console.log(`JSON file updated successfully. Updated ${keyToUpdate} to ${newValue}`);
}

async function get_results(CSV_file_path) {
  const server_2_response = await get_config_data(CSV_file_path);
  const Credentials = server_2_response["credentials"]; //json
  const csv_data = server_2_response["csv_data"]; // list
  //   console.log(server_2_response);
  // console.log(Credentials.start_index,csv_data.length)
  for (let index = Credentials.start_index; index < csv_data.length; index++) {
    //   console.log(index);
    try {
      const search_call = await makeAPostRequest(
        csv_data[index]["User_Query"],
        Credentials
      );

      const final_results = await pre_processing(search_call, csv_data[index], Credentials.embedings_model); //so we are passing an index index here

      var appending_objects = {}

      appending_objects["index"] = index
      appending_objects["User_Query"] = csv_data[index]["User_Query"]
      appending_objects["Expected_Ans"] = csv_data[index]["Expected_Ans"]
      appending_objects["Expected_URL"] = csv_data[index]["Expected_URL"]
      appending_objects["Expected_Title"] = csv_data[index]["Expected_Title"]
      appending_objects["Answer_Snippet"] = final_results.result_metrics.data_index
      appending_objects["Actual_Title"] = final_results.result_metrics.actual_title
      appending_objects["Actual_URL"] = final_results.result_metrics.actual_url
      appending_objects["Actual_Score"] = final_results.result_metrics.actual_score
      appending_objects["Answer_Status"] = final_results.result_metrics.Ans_Status
      appending_objects["URL_status"] = Boolean(final_results.result_metrics.url_status)
      appending_objects["Title_Status"] = Boolean(final_results.result_metrics.title_status)
      appending_objects["Chunk_Text"] = ""

      if (final_results.debugger_result_metrics) {
        if (final_results.debugger_result_metrics.Ans_Status == false) {
          appending_objects["Chunk_Positon"] = "Out of Bound"
        }
        else {
          appending_objects["Chunk_Positon"] = final_results.debugger_result_metrics.Chunk_number
          single_line_string = final_results.debugger_result_metrics.data_index;
          appending_objects["Chunk_Text"] = single_line_string
        }

        // appending_objects["Debug_Response"] = final_results.debugger_result_metrics.data_index
      }
      else {
        // appending_objects["Answer_Snippet"] = final_results.result_metrics.data_index
        single_line_string = final_results.result_metrics.data_index;
        appending_objects["Answer_Snippet"] = single_line_string
      }

      appending_objects["Model_Used"] = final_results.result_metrics.Model_used
      appending_objects['Top_Chunks'] = final_results.debugger_result_metrics['debug_payload']
      // console.log(typeof appending_objects["Answer_Snippet"])

      // console.log(appending_objects)
      //appendToJSON(appending_objects, output_file_path)
      appendToCSV(appending_objects, output_file_path)
      updateJsonFile(jsonFilePath, "start_index", index)
    }
    catch (err) {
      console.log(err);
    }
  }
}

(async () => {
  const query_info = await get_results(CSV_file_path);
})();
