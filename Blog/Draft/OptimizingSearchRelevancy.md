## Optimizing Enterprise Search Relevancy

### Introduction

Enterprises today are faced with a growing challenge of effectively managing and retrieving relevant information from an ever-expanding sea of data. Whether it's web pages, internal documents, or a mix of unstructured content, the need for a robust and intelligent search solution is paramount. In this blog post, we'll dive deep into the insights and solutions we discovered while working on a SearchAssist PoC for our enterprise clients.

### The Enterprise Search Challenge

Our clients, like many enterprises, had developed a search application with a set of default configurations. However, as they started onboarding their own data and use cases, they quickly realized that the default settings were not performing as expected. The key issues they faced were:

1. **Data Diversity and Overlap**: Clients had a significant amount of web pages and files, with a high degree of data overlap across multiple records.
2. **Relevancy Issues**: The default settings were only able to achieve 50-60% answer relevancy, leaving room for significant improvement.
3. **Chunking and Retrieval Challenges**: The default 400-token chunking strategy was not optimal for clients with large, biased, and repetitive data sets.
4. **Embedding Generation Bias**: The default approach of including the source information in the embeddings added significant bias, leading to false positives.
5. **Vector Search Limitations**: The default vector search was not effectively handling industry-specific user queries.
6. **Prompt Generation Challenges**: The default prompt was not generating satisfactory answers, even when the retrieval process identified the right chunks.
7. **Fragmented Relevant Chunks**: The default approach of sending the top 10 chunks to the language model was not sufficient, as the relevant information was spread across multiple files.

### Our Approach to Optimization

To address these challenges, we took a comprehensive approach to analyzing the issues and implementing tailored solutions. Here's a detailed breakdown of our findings and the fixes we implemented:

#### 1. Extraction Configuration
- **Web Pages**: For clients with more than 500 web pages, we recommended a page-based chunking strategy or increasing the chunk length to 5,000 tokens. For smaller data sets, the default 400-token chunking remained effective.
- **Files**: For clients with more than 200 pages across multiple files, we suggested a page-based chunking strategy or increasing the chunk length to 5,000 tokens. For smaller data sets, the default 400-token chunking was suitable.
- **Structured Data**: When the data contained tables and images, we implemented a layout-aware extraction strategy to preserve the context and structure of the information.

#### 2. Indexing Configuration
- **Embeddings**: We included only the title and content of the chunks in the embeddings, removing the source information. This helped reduce the bias introduced by the default approach.
- **Source Name**: We only included the source name in the embeddings if the file names were unique and could effectively differentiate the content.

#### 3. Search Configuration
- **Hybrid Search**: For queries that contained industry-specific terms or non-generic keywords, we implemented a hybrid search approach that combined vector search and text-based search.
- **Chunk Prioritization**: For page-based chunking, we sent the top 10 chunks to the language model. For text-based chunking, we increased this to the top 20 chunks to ensure that the relevant information was not fragmented across multiple files.

#### 4. Prompt Engineering
- **Prompt Optimization**: We carefully fine-tuned the prompts used to generate the answers, taking into account the specific requirements and terminology of the client's industry. Below is the prompt we created which includes most of the scenarions.

```
Role
You are an AI system designed to generate comprehensive, clear, and accurate answers based on the user-provided context.

Instructions
The user will provide content in chunks, labeled with `Content:`. Each chunk includes `source_name` and `chunk_id` identifiers, as shown below:

> `Content: <<SAMPLE CONTENT>> source_name: <<SAMPLE SOURCE>> chunk_id: chk-15`

Analyze each chunk independently and collectively to form a cohesive response to the user query, labeled `QUERY:`.

Steps to Follow

1. Identify Chunk Boundaries
   - Look for text labeled with `Content:` to distinguish individual chunks.

2. Process Each Chunk
   - Review each chunk to determine if it contains relevant information for the query.
   - Extract directly relevant information for the answer, ensuring no assumptions or fabrications are made.

3. Construct the Answer
   - Combine relevant information from multiple chunks to create a thorough and cohesive answer.
   - Present the answer logically, using clear formatting (e.g., bullet points, numbered steps) to enhance readability and comprehension.
   - Place chunk references at the end of each relevant piece of information in the format `[chunk_id]` without additional characters.
   - Aggregate findings if multiple chunks contain relevant information.

4. Provide Complete, Accurate Responses
   - Begin with an overview if necessary, ensuring all necessary background or prerequisites are included.
   - Break down complex information into clear steps or sections.
   - Exclude irrelevant content and respond in the same language as the query and context.
   - If information is unavailable, respond with "I don’t know."

Answer Format

- Introduction: Start with a brief overview or introduction when appropriate.
- Logical Structure: Break down complex information into clear, numbered steps or logical sections.
- Completeness: Include all relevant details from the provided context.
- Formatting: Use bullet points, numbering, and paragraphs for clarity.
- Tone: Maintain a professional, instructional tone.
- Full Process: Describe the complete process from start to finish when applicable.

Reference Format

- Include references to specific chunks using the format `[chunk_id]` at the end of each relevant answer fragment.
- Strictly use only the provided `chunk_ids`.

Example:
> Detailed information here `[chunk_id]` Additional information here `[chunk_id]`.

Special Notes

- For queries related to ongoing or future events, assume relevance to the current date and major current events.
- Do not fabricate any details or chunk references; answer only from the given content.
- Never fabricate or invent `chunk_ids`.
- If necessary information is not available, respond with "I don't know."
- Exclude any irrelevant information or notes.
- Respond in the same language as the user's query and context.
- Provide the most complete answer possible from the available context.
- **Do not mention** anything about the chunks in the final answer.

```


#### Consolidation Configuration

| Optimization Area        | Default Configuration                            | Optimized Configuration                                                                                       |
|--------------------------|-------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| **Extraction Configuration** |                                                                                         |                                                                                                               |
| Web Pages                | 400-token chunking                              | - Page-based chunking for >500 web pages<br>- 5,000-token chunking for >500 web pages                        |
| Files                    | 400-token chunking                              | - Page-based chunking for >200 pages across files<br>- 5,000-token chunking for >200 pages across files      |
| Structured Data          | Standard text extraction                        | Layout-aware extraction for data with tables and images                                                      |
| **Indexing Configuration** |                                                                                         |                                                                                                               |
| Embeddings               | Include title, content, and source name         | Include only title and content                                                                               |
| Source Name              | Always included in embeddings                   | Include only if file names are unique                                                                        |
| **Search Configuration**     |                                                                                     |                                                                                                               |
| Search Type              | Vector search                                   | Hybrid search for industry-specific queries                                                                  |
| Chunk Prioritization     | Top 10 chunks sent to LLM                       | - Top 10 chunks for page-based chunking<br>- Top 20 chunks for text-based chunking                           |
| **Prompt Engineering**       |                                                                                     |                                                                                                               |
| Prompt Design            | Default prompt                                  | Customized prompt based on client industry and requirements                                                  |

  
### Impact and Benefits

By implementing these tailored configurations and prompt engineering, we were able to achieve the following results for our clients:

1. **Improved Relevancy**: The answer relevancy increased from the initial 50-60% to a range of 80-85%, significantly enhancing the user experience.
2. **Effective Handling of Data Diversity**: The new configurations effectively handled clients' diverse data sets, including web pages, files, and structured content.
3. **Reduced Bias and False Positives**: The changes to the embedding generation process helped minimize the bias introduced by source information, leading to more accurate and relevant search results.
4. **Improved Handling of Industry-Specific Queries**: The hybrid search approach and prompt engineering enabled the system to better understand and respond to industry-specific terminology and requirements.
5. **Increased Chunk Prioritization**: Sending more relevant chunks to the language model improved the overall quality and coherence of the search results.

### Conclusion

Optimizing enterprise search relevancy is a complex and ongoing challenge, but the insights and solutions we've shared in this blog post can serve as a starting point for enterprises looking to enhance their search capabilities. By understanding the unique data characteristics, search patterns, and industry requirements, you can tailor your search application configuration and prompt engineering to achieve remarkable improvements in answer relevancy and user satisfaction.

If you're faced with similar enterprise search challenges, we encourage you to explore these strategies and adapt them to your specific use case. Remember, the key to success lies in a deep understanding of your data, your users, and a willingness to continuously iterate and refine your search solution.


