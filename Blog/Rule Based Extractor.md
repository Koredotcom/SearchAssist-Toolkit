
# Extractive Snippets: Understanding the HTML Structure for Optimal Extraction

## Introduction

In SearchAssist, we offer two types of extractors: a text-based extractor and an extractive extractor. In this guide, we will be focusing on the extractive snippets, which consist of a title, content, and URL. By understanding the required HTML structure, you can optimize your content for better extraction results.

## How the Extractor Works

Our extractor removes all headers and footers from the HTML content. The extraction process follows a systematic approach to create meaningful chunks of content. Here's a step-by-step breakdown of how it works:

### Step 1: Initial Chunk Creation

1. **Title Extraction**: The extractor first identifies the title of the HTML document and creates the initial chunk with this title.
2. **Paragraph Tags**: Following the title, the extractor consolidates all `<p>` (paragraph) tags present in the entire HTML document into a single, large chunk.

### Step 2: Subsequent Chunk Creation

From the second chunk onwards, the extractor processes the HTML content based on header tags. Here's the detailed process:

1. **Header Tags**: The extractor identifies all header tags (e.g., `<h1>`, `<h2>`, `<h3>`, etc.).
2. **Content Under Headers**: For each header tag, the extractor collects the content (paragraph tags `<p>` and span tags `<span>`) immediately following it to form a chunk.
3. **New Header Detection**: The process continues until another header tag is encountered. At this point, the extractor creates a new chunk with the new header and its associated content.
4. **Special Case Handling**: If a header tag contains a `<strong>` or `<span>` tag, the content of these tags will be used as the header instead of the header tag itself.

This method ensures that each chunk is contextually meaningful, with headers acting as separators and paragraph or span content providing detailed information under each header.

## Example HTML Structure

### Standard HTML Example

To illustrate the standard process, let's consider an example HTML structure:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Sample Document</title>
</head>
<body>
  <header>
    <h1>Main Title</h1>
  </header>

  <h1>Section 1</h1>
  <p>Introduction to section 1. This is a paragraph that provides an overview.</p>
 
  <h1>Subsection 1.1</h1>
  <p>Details about subsection 1.1. This paragraph contains more detailed information.</p>
  <ol>
    <li>Ordered list item 1 under section 1</li>
    <li>Ordered list item 2 under section 1</li>
  </ol>
  
  <h3>Subsection 1.2</h3>
  <p>Details about subsection 1.2. This paragraph contains more detailed information.</p>

  <h2>Section 2</h2>
  <p>Introduction to section 2. This is a paragraph that provides an overview.</p>
  <ol>
    <li>Ordered list item 1 under section 2</li>
    <li>Ordered list item 2 under section 2</li>
  </ol>

  <h3>Subsection 2.1</h3>
  <p>Details about subsection 2.1. This paragraph contains more detailed information.</p>

  <footer>
    <p>Footer content that will be removed during processing.</p>
  </footer>
</body>
</html>
```

### Chunk Extraction for the Above HTML

![Example Image](./Assets/ExtractiveHtmlEx2.png)

The highlighted boxes with each color are a single chunk, where the heading tag is the title of the chunk, and the content is the other part.

## HTML Example with strong Tag in Headings

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Example Page</title>
</head>
<body>
  <h2>Heading 1</h2>
  <p>Some content which is a paragraph 1 in this HTML block</p>
  <h2>This is the h2 block of this HTML content <strong>The BOLD Part</strong></h2>
  <p>Some content which is a snippet of some length belonging to the paragraph tag</p>
  <h2>important information</h2>
  <ul>
    <li><strong>Item 1:</strong> Details about item 1.</li>
    <li><strong>Item 2:</strong> Details about item 2.</li>
  </ul>
</body>
</html>
```

### Chunk Extraction for the Above HTML

![Example Image](./Assets/ExtractiveHtmlEx1.png)

The highlighted boxes with each color are a single chunk, where the heading tag is the title of the chunk, and the content is the other part.

## Case Study: Handling HTML Without Headings

In a recent project, our team encountered a common challenge: processing HTML content that lacked essential structure. Specifically, the content was devoid of heading tags, a critical component for our HTML extractor to generate meaningful chunks. Without these structural markers, the extractor was unable to identify distinct sections within the text, rendering it ineffective. The head tag was present in advi elemtn which had a class head.
To illustrate, consider this simple HTML snippet:

```html
<div class= "heading 1">Relavnt Headings </div>
<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>   
```

Our extractor would be unable to create chunks from this content due to the absence of heading tags

### Crafting a Solution:
To address this issue, we implemented a custom script designed to inject a heading tag at the beginning of the content. This approach was feasible due to two key factors:

- **Content Length**: The HTML content was relatively short.
- **Known Heading**: We had prior knowledge of the appropriate heading for the content.

By prepending an h1 tag, we transformed the original HTML into the following:

### HTML
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relevant Heading</title>
</head>
<body>
    <div class="heading">Relevant Heading</div>
    <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>
</body>
</html>

```

### Implementation:
We utilized a custom script within our workbench to achieve this transformation:

```Painless
def pattern =/<div\s+class="heading">(.*?)<\/div>/;
Matcher matcher = pattern.matcher(ctx.html);
String title;
if (matcher.find()){
    title = matcher.group(1);
    String makeTitle = "<h1>" + title + "</h1>";
    String Content = "<p>" + ctx.content + "</p>";
    ctx.html = makeTitle + Content;
}
```

#### The Final Chunk
```json
 {
    "title": "Relevant Heading",
    "content": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
    "source": "Lorem ipsum",
    "url": "https://www.abcd.com/"
 }

```
## Conclusion

Understanding the HTML structure is crucial for optimizing content extraction. By following the guidelines and handling special cases as demonstrated, you can ensure that your HTML content is processed efficiently, leading to more accurate and contextually relevant extractive snippets.