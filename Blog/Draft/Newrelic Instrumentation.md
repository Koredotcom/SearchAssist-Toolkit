# Ensuring Full Visibility: Our Path to Effective Monitoring with New Relic

## Introduction
Imagine diving deep into the complex world of application debugging. We began our journey by sifting through logs, hunting for errors and tracking time metrics. Extracting and analyzing these time values manually became a laborious and inefficient task. This led us to explore monitoring tools that could streamline the process.

Enter New Relic. At first glance, it seemed like the perfect solution to our monitoring woes. It offered robust features and intuitive insights that promised to make our job easier. However, as we delved deeper, we encountered a significant gap: our asynchronous components, specifically RabbitMQ queues, were slipping through the cracks.

Determined to achieve comprehensive monitoring, we set out to bridge this gap. This document chronicles our journey to enhance our application monitoring, focusing on how we tackled the challenge of integrating RabbitMQ with New Relic to ensure nothing goes unnoticed.

## The Challenge

### Achieving Distributed Tracing
Our primary objective was to implement distributed tracing across multiple services to gain a comprehensive view of our application's performance. Leveraging New Relic’s monitoring features, we successfully set up distributed tracing, which allowed us to track and visualize interactions between various services.

### RabbitMQ Instrumentation Issues
However, we encountered a significant issue with RabbitMQ queues. Despite our efforts, these queues were not properly instrumented, creating a blind spot in our monitoring setup. This lack of instrumentation prevented us from obtaining critical insights into RabbitMQ’s performance and operational issues. We struggled to track message processing times, detect bottlenecks, and understand how delays in queue handling affected overall application performance. This gap severely hindered our ability to maintain optimal system performance and promptly address emerging issues.

#### Initial Implementation
To address the monitoring gap, we took a multi-faceted approach. First, we identified the segments where the flow was becoming uninstrumented. We implemented a solution to pass the traceId of the parent trace to the queues, ensuring continuity by appending it to the child queue trace.

To further enhance this process, we leveraged New Relic's dashboards feature. By creating custom dashboards, we could visualize and track the flow of traces through RabbitMQ queues more effectively. These dashboards allowed us to see how traces were propagated through the queues, providing real-time insights into performance and latency. This visual representation made it easier to identify and address bottlenecks or issues within the queueing system, ensuring that our monitoring efforts were both comprehensive and actionable.

#### Technical Blueprint
We utilized key New Relic methods to ensure accurate tracing and monitoring:

1. **getTraceMetadata()**: Retrieves trace metadata, including traceId and spanId, essential for distributed tracing.
2. **addCustomAttribute()**: Adds custom attributes to the current transaction, allowing attachment of relevant metadata.
3. **startBackgroundTransaction()**: Starts a background transaction, typically used for non-web transactions like message consumers.
4. **getTransaction()**: Retrieves the current transaction object for further manipulation or termination.
5. **end()**: Ends the current transaction, indicating that the work is complete.
6. **startSegment()**: Creates a new segment within the current transaction, which helps in tracking and segmenting different parts of the request.


#### The Solution Approaches

##### Code snippets to add before publishing to the queue

To ensure that each message sent to the queue retains traceability, you need to create a segment and attach the custom trace ID:

```javascript
nr.startSegment('QueuePublishingSegment', true, async () => {
  // Retrieve the current trace ID or set a new one if it doesn't exist
  context.customTraceId = context.customTraceId || nr.getTraceMetadata()?.traceId;
  
  // Add the custom trace ID as an attribute to the current transaction
  nr.addCustomAttribute("customTraceId", context.customTraceId);
});
```

#### Code snippets to wrap while processing the queue

When processing messages from the queue, wrap the logic in a background transaction to maintain traceability:
```javascript
nr.startBackgroundTransaction('QueueProcessingTransaction', async function transactionHandler() {
  // Retrieve the current transaction object
  const transaction = nr.getTransaction();
  
  // Use the custom trace ID for this transaction
  const customTraceId = context?.customTraceId || nr.getTraceMetadata()?.traceId;
  nr.addCustomAttribute("customTraceId", customTraceId);

  try {
    // Process the message from the queue
    // [Insert your message processing logic here]

  } finally {
    // End the transaction to finalize timing and metrics
    transaction.end();
  }
});
```

#### Using Dashboards to Monitor Custom Attributes

To gain deeper insights into the performance of RabbitMQ queues, we utilized New Relic’s dashboards to monitor custom attributes. This approach allowed us to visualize and track specific metrics and transaction flows that are crucial for understanding the behavior and performance of our queueing system.

By leveraging New Relic’s dashboards, we could create custom visualizations and queries to monitor the propagation of custom trace IDs through our RabbitMQ queues. Here’s how we used NRQL queries to enhance our monitoring capabilities:

##### Monitoring All Components Involved in the Flow
To visualize all the components involved in a specific transaction flow, including RabbitMQ queues, use the following NRQL query:

```sql
SELECT message.queueName, duration, databaseDuration, traceId 
FROM Transaction 
WHERE customTraceId = 'value of customTraceId'
```

#### Calculating the Total Duration of the Flow

```sql
SELECT sum(duration) AS 'Total Transaction (s)' FROM Transaction WHERE customTraceId = 'value of customtraceId' OR traceId = 'value of parent traceId'
```

This query aggregates the total duration of the transaction flow, helping you understand how long the entire process takes, from start to finish.

By setting up these custom dashboards and queries, we were able to gain comprehensive visibility into the performance of RabbitMQ queues, enabling more effective monitoring and quicker identification of performance issues.

## Comprehensive Solution and Its Impact

By implementing New Relic's tracing and monitoring capabilities with custom attributes and effective dashboard queries, we achieved comprehensive monitoring of our RabbitMQ queues. This solution not only addressed the gaps in RabbitMQ instrumentation but also provided a framework that can be applied to trace and monitor any asynchronous components within our application. The approach allowed us to gain valuable insights into RabbitMQ’s performance, promptly identify potential issues, and ensure optimal system performance. By leveraging this method, we enhanced our overall monitoring capabilities and improved our ability to manage and troubleshoot asynchronous components effectively.

## Conclusion
Our journey to monitor RabbitMQ with New Relic was both challenging and rewarding. While the standard enablement of New Relic's features successfully addressed our need for distributed tracing across multiple services, we encountered specific issues with RabbitMQ queues that required a custom implementation. By addressing these gaps in instrumentation and leveraging New Relic's tracing capabilities, custom attributes, and effective dashboard queries, we developed a comprehensive monitoring solution. This approach not only enhanced our visibility into RabbitMQ’s performance but also provided a robust framework for tracing and monitoring asynchronous components across our application. With this solution, we can now ensure complete visibility into our application's performance and swiftly address any emerging issues.


## References

- [Enabling New Relic for Node, Python, and Other Stack Components](https://docs.google.com/document/d/1MTT2afwh6noTEPQck-zKGGF7M7V1EgC2SGxzAcT3GrA/edit)
- [Configuration Changes During Deployment for Node, Python, and CPP Server](https://docs.google.com/document/d/14kgXBuft6I3iESy-6NiQKwyTI7j5PvzSoPR9pB1cf2E/edit#heading=h.ibjm5ssqs52m)
- [Creating a Dashboard in New Relic](https://developer.newrelic.com/contribute-to-quickstarts/create-a-dashboard/)
- [Introduction to NRQL - New Relic's Query Language](https://docs.newrelic.com/docs/nrql/get-started/introduction-nrql-new-relics-query-language/)
- [New Relic Node.js Agent API Guide](https://docs.newrelic.com/docs/apm/agents/nodejs-agent/api-guides/nodejs-agent-api/)
