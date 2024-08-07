//QuickStart Guide - https://developer.adobe.com/document-services/docs/overview/pdf-extract-api/quickstarts/nodejs/

const PDFServicesSdk = require('@adobe/pdfservices-node-sdk');
const fs = require('fs');
const AdmZip = require('adm-zip');

const OUTPUT_ZIP = './ExtractTextInfoFromPDF.zip';

//Remove if the output already exists.
if (fs.existsSync(OUTPUT_ZIP)) fs.unlinkSync(OUTPUT_ZIP);

const INPUT_PDF = './sc_cookie_brownie_proc2883013233763893968.pdf'; //File path of the document for which extraction to be happened. 

const credentials = PDFServicesSdk.Credentials
    .servicePrincipalCredentialsBuilder()
    .withClientId("<clientId>")               //ClientId provided by adobe
    .withClientSecret("<clientSecret>")       //ClientSecret provided by adobe
    .build();

// Create an ExecutionContext using credentials
const executionContext = PDFServicesSdk.ExecutionContext.create(credentials);

// Create a new operation instance.
const extractPDFOperation = PDFServicesSdk.ExtractPDF.Operation.createNew(),
    input = PDFServicesSdk.FileRef.createFromLocalFile(
        INPUT_PDF,
        PDFServicesSdk.ExtractPDF.SupportedSourceFormat.pdf
    );

// Build extractPDF options
const options = new PDFServicesSdk.ExtractPDF.options.ExtractPdfOptions.Builder()
    .addElementsToExtract(PDFServicesSdk.ExtractPDF.options.ExtractElementType.TEXT).build()


extractPDFOperation.setInput(input);
extractPDFOperation.setOptions(options);

// Execute the operation
extractPDFOperation.execute(executionContext)
    .then(result => result.saveAsFile(OUTPUT_ZIP))
    .then(() => {
        console.log('Successfully extracted information from PDF.\n');
        let zip = new AdmZip(OUTPUT_ZIP);
        let jsondata = zip.readAsText('structuredData.json');
        let data = JSON.parse(jsondata);

        // Script for Creating Snippet

        let inputArray = [];
        for (let i = 0; i < data.elements.length; i++) {
            inputArray.push({
                "path": data.elements[i].Path,
                "text": data.elements[i].Text ? data.elements[i].Text : ""
            })
        }

        let contentInclusions = [
            "L", "P", "Sub", "ParagraphSpan", "Span", "StyleSpan", "Aside"
        ];

        function convertPathToNestedArray(inputArray) {
            return inputArray.map(obj => {
                const pathSegments = obj.path.split('/').filter(segment => segment !== '');
                return {
                    path: pathSegments,
                    text: obj.text,
                };
            });
        }

        function generateOutputArray(inputArray) {

            let elementIndexWithoutSection = 0;
            let snippetsWithoutSection = [];
            let outputArray = [];
            generateOutputForCurrentSectionV2(inputArray, 1, []);

            function findHeaderOfCurrentSection(inputArray, depth, previousDepthArray) {
                for (let i = 0; i < inputArray.length; i++) {
                    let path = inputArray[i]["path"];
                    let isCurrentElementMatchingDepth = isDepthMatching(path, depth, previousDepthArray);
                    if (isCurrentElementMatchingDepth) {
                        let currentPathElement = path[depth];
                        let isCurrentElementASection = checkElementIsASection(currentPathElement);
                        if (!isCurrentElementASection) {
                            let isCurrentElementAHeading = checkElementIsAHeading(currentPathElement, path, depth);
                            if (isCurrentElementAHeading) {
                                inputArray[i]["processed"] = true;
                                return inputArray[i]["text"];
                            }
                        }
                    }
                }
            }

            function validParagraphContent(path, depth, contentInclusions) {
                let currentPathElement = path[depth];

                let isCurrentElementStartingWithH = currentPathElement.indexOf("H") === 0;
                if (isCurrentElementStartingWithH) {
                    currentPathElement = path[depth + 1];
                }

                let isValidContent = false;
                for (let phrase of contentInclusions) {
                    if (currentPathElement.indexOf(phrase) === 0) {
                        isValidContent = true;
                    }
                }

                return isValidContent;
            }

            function findContentOfCurrentSection(inputArray, depth, previousDepthArray) {
                let currentSectionContent = [];
                let currentSectionList = [];
                for (let i = 0; i < inputArray.length; i++) {
                    let path = inputArray[i]["path"];
                    let isCurrentElementMatchingDepth = isDepthMatching(path, depth, previousDepthArray);
                    if (isCurrentElementMatchingDepth) {
                        let currentPathElement = path[depth];
                        let isCurrentElementAHeading = checkElementIsAHeading(currentPathElement, path, depth);
                        let isCurrentElementASection = checkElementIsASection(currentPathElement);
                        if (!isCurrentElementASection && !isCurrentElementAHeading) {
                            if (validParagraphContent(path, depth, contentInclusions)) {
                                if (currentPathElement.startsWith("L")) {
                                    if (!currentSectionList[i]) {
                                        currentSectionList.push({
                                            "order": i,
                                            "content": inputArray[i]["text"]
                                        });
                                    }
                                }
                                else {
                                    if (!currentSectionContent[i]) {
                                        currentSectionContent.push({
                                            "order": i,
                                            "content": inputArray[i]["text"]
                                        });
                                    }
                                }
                            }
                            inputArray[i]["processed"] = true;
                        }
                    }
                }
                let finalListContent = [];
                let finalContent = "";
                if (currentSectionList.length > 0 && currentSectionContent.length > 0) {
                    currentSectionList = currentSectionList.concat(currentSectionContent);
                    currentSectionList.sort((a, b) => a.order - b.order)
                    for (let i = 0; i < currentSectionList.length; i++) {
                        if (currentSectionList[i].content.length > 0)
                            finalListContent.push(currentSectionList[i].content)
                    }
                    return finalListContent;
                }
                else if (currentSectionList.length > 0) {
                    for (let i = 0; i < currentSectionList.length; i++) {
                        if (currentSectionList[i].content.length > 0)
                            finalListContent.push(currentSectionList[i].content)
                    }
                    return finalListContent;
                }
                else if (currentSectionContent.length > 0) {
                    for (let i = 0; i < currentSectionContent.length; i++) {
                        if (currentSectionContent[i].content.length > 0)
                            finalContent = finalContent + currentSectionContent[i].content
                    }
                    return finalContent;
                }
            }

            function isDepthMatching(path, depth, previousDepthArray) {
                let isCurrentElementMatchingDepth = true;
                for (let d = 1; d < depth; d++) {
                    if (path[d] !== previousDepthArray[d - 1]) {
                        isCurrentElementMatchingDepth = false;
                    }
                }
                return isCurrentElementMatchingDepth;
            }

            function checkElementIsASection(element) {
                return element.indexOf("Sect") === 0;
            }

            function checkElementIsAHeading(element, path, depth) {
                return element.indexOf("H") === 0 && path[depth + 1] === undefined;
            }

            function checkProcessStatus(inputArray, path) {
                for (let input of inputArray) {
                    if (input["path"] === path) {
                        return input["processed"] || false;
                    }
                }
            }

            function findExistingOutputForCurrentSection(outputArray, path) {
                for (let i = 0; i < outputArray.length; i++) {
                    let outputItem = outputArray[i];
                    if (outputItem["path"] === path) {
                        return i;
                    }
                }
                return -1;
            }

            function checkIfCallIsFromImmediateParent(path, depth, previousDepthArray) {
                let isImmediateParent = true;
                let isCurrentElementMatchingDepth = isDepthMatching(path, depth, previousDepthArray);
                let trailingPathFromCurrentSection = path.slice(depth);
                let sectionPresentInTrailingPath = false;
                for (let item of trailingPathFromCurrentSection) {
                    if (checkElementIsASection(item)) {
                        sectionPresentInTrailingPath = true;
                    }
                }
                isImmediateParent = isCurrentElementMatchingDepth && !sectionPresentInTrailingPath;
                return isImmediateParent;
            }

            function generateOutputForCurrentSectionV2(inputArray, depth, previousDepthArray) {
                for (let k = 0; k < inputArray.length; k++) {
                    let path = inputArray[k]["path"];

                    let isCurrentPathAlreadyProcessed = checkProcessStatus(inputArray, path);

                    if (isCurrentPathAlreadyProcessed) {
                        continue;
                    }

                    let isCurrentElementMatchingDepth = isDepthMatching(path, depth, previousDepthArray);

                    if (isCurrentElementMatchingDepth) {
                        let isCurrentElementASection = path[depth].indexOf("Sect") === 0;

                        if (isCurrentElementASection) {
                            let currentSectionHeader = findHeaderOfCurrentSection(inputArray, depth + 1, [...previousDepthArray, path[depth]]);
                            let currentSectionContent = findContentOfCurrentSection(inputArray, depth + 1, [...previousDepthArray, path[depth]]);
                            let subSectionObject = generateOutputForCurrentSectionV2(inputArray, depth + 1, [...previousDepthArray, path[depth]]);

                            if (!subSectionObject && !currentSectionHeader) {
                                currentSectionHeader = currentSectionContent;
                            }

                            if (!subSectionObject && !currentSectionContent) {
                                continue;
                            }
                            if (Array.isArray(currentSectionContent) && subSectionObject && subSectionObject["title"]) {
                                currentSectionContent.push(subSectionObject["title"])
                            }
                            let currentSectionObject = {
                                title: currentSectionHeader,
                                content: currentSectionContent,
                                path: previousDepthArray.join("/") + "/" + path[depth],
                                parent: path[1]
                            };

                            let isImmediateParent = checkIfCallIsFromImmediateParent(path, depth, previousDepthArray);

                            let existingOutputObjectIndex = findExistingOutputForCurrentSection(outputArray, previousDepthArray.join("/") + "/" + path[depth]);
                            if (isImmediateParent && existingOutputObjectIndex > -1) {
                                let existingObj = outputArray[existingOutputObjectIndex];
                                existingObj["content"] = existingObj["content"] + (subSectionObject && subSectionObject["title"]);
                            } else if (existingOutputObjectIndex === -1) {
                                outputArray.push(currentSectionObject);
                            }

                            if (depth > 1) {
                                return currentSectionObject;
                            }
                        }

                        else {
                            let isValidContent = false;
                            for (let phrase of contentInclusions) {
                                if (inputArray[k]["path"][inputArray[k]["path"].length - 1].startsWith(phrase)) {
                                    isValidContent = true;
                                    break;
                                }
                            }
                            if ((inputArray[k]["path"][inputArray[k]["path"].length - 1].startsWith("H") || inputArray[k]["path"][inputArray[k]["path"].length - 1].startsWith("Title"))) {
                                let currentSectionObject = {
                                    title: inputArray[k]["text"],
                                    content: [],
                                    path: inputArray[k]["path"],
                                    parent: inputArray[k]["path"]
                                };
                                snippetsWithoutSection.push(currentSectionObject);
                                elementIndexWithoutSection++;
                            }
                            else if (elementIndexWithoutSection > 0 && isValidContent) {
                                snippetsWithoutSection[elementIndexWithoutSection - 1].content.push(inputArray[k]["text"]);
                            }
                            else {
                                if (isValidContent) {
                                    let currentSectionObject = {
                                        title: "",
                                        content: [inputArray[k]["text"]],
                                        path: inputArray[k]["path"],
                                        parent: inputArray[k]["path"]
                                    };
                                    snippetsWithoutSection.push(currentSectionObject);
                                    elementIndexWithoutSection++;
                                }
                            }   
                        }
                    }
                }
            }
            outputArray = outputArray.concat(snippetsWithoutSection)
            return outputArray.filter(function (snippet) {
                return snippet.content;
            });
        }
        fs.writeFileSync("structuredDataResult.json", JSON.stringify(generateOutputArray(convertPathToNestedArray(inputArray))));
    })
    .catch(err => console.log(err));