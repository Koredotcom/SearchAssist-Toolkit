class RequestWrapper {
  constructor(headers, body, files) {
    this._headers = headers || {};
    this._body = body || {};
    this._files = files || {};
    this._mappings = {
      headers: {},
      body: {},
      files: {}
    };
  }

  setMappings(mappings) {
    this._mappings = mappings;
  }

  getValue(source, key) {
    const mapping = this._mappings[source]?.[key];
    if (!mapping) return null;

    const value = this[`_${source}`]?.[mapping];
    return Array.isArray(value) ? value[0] : value;
  }

  getHeader(key) {
    return this.getValue('headers', key);
  }

  getBodyField(key) {
    return this.getValue('body', key);
  }

  getFile(key) {
    return this.getValue('files', key);
  }

  getDocumentField(key) {
    // Check in root body
    const rootValue = this.getValue('body', key);
    if (rootValue) return rootValue;

    // Check in documentMeta
    const metaValue = this._body?.documentMeta?.[key];
    if (metaValue) return metaValue;

    // Check in meta_data inside documentMeta
    const metaDataValue = this._body?.documentMeta?.meta_data?.[key];
    return metaDataValue || null;
  }

  // Add new direct getters for document fields
  getDocumentMeta() {
    return this._body?.documentMeta || null;
  }

  getMetaData() {
    return this._body?.documentMeta?.meta_data || null;
  }

  getStrategyBatchId() {
    return this.getDocumentField('strategyBatchId');
  }

  getExtractedChunks() {
    return this.getDocumentField('extractedChunks') || [];
  }

  getExtractedText() {
    return this.getDocumentField('extractedText');
  }

  getExtractedMetadata() {
    return this.getDocumentField('extractedMetadata') || {};
  }

  // Processing Fields
  getProcessingStatus() {
    return this.getDocumentField('processingStatus');
  }

  getErrorDetails() {
    return this.getDocumentField('errorDetails');
  }

  getProcessingTime() {
    return this.getDocumentField('processingTime');
  }

  // Count Fields with defaults
  getChunkCount() {
    return this.getDocumentField('chunkCount') || 0;
  }

  getPageCount() {
    return this.getDocumentField('page_count') || 0;
  }

  getCharacterCount() {
    return this.getDocumentField('characterCount') || 0;
  }

  getWordCount() {
    return this.getDocumentField('wordCount') || 0;
  }

  getSentenceCount() {
    return this.getDocumentField('sentenceCount') || 0;
  }

  getParagraphCount() {
    return this.getDocumentField('paragraphCount') || 0;
  }

  // Score Fields with defaults
  getConfidenceScore() {
    return this.getDocumentField('confidenceScore') || 0;
  }

  getQualityScore() {
    return this.getDocumentField('qualityScore') || 0;
  }

  getRelevanceScore() {
    return this.getDocumentField('relevanceScore') || 0;
  }

  // Object Fields with defaults
  getProcessingMetrics() {
    return this.getDocumentField('processingMetrics') || {};
  }

  getValidationResults() {
    return this.getDocumentField('validationResults') || {};
  }

  getEnrichmentData() {
    return this.getDocumentField('enrichmentData') || {};
  }

  getClassificationResults() {
    return this.getDocumentField('classificationResults') || {};
  }

  getSentimentAnalysis() {
    return this.getDocumentField('sentimentAnalysis') || {};
  }

  getEntityExtraction() {
    return this.getDocumentField('entityExtraction') || {};
  }

  // Array Fields with defaults
  getKeyPhrases() {
    return this.getDocumentField('keyPhrases') || [];
  }

  getTopics() {
    return this.getDocumentField('topics') || [];
  }

  getCategories() {
    return this.getDocumentField('categories') || [];
  }

  getTags() {
    return this.getDocumentField('tags') || [];
  }

  // Document Fields
  getTitle() {
    return this.getDocumentField('title');
  }

  getExtractionMethod() {
    return this.getDocumentField('extractionMethod');
  }

  getExtractionMethodType() {
    return this.getDocumentField('extractionMethodType');
  }

  getExtractionStrategy() {
    return this.getDocumentField('extractionStrategy');
  }

  // Boolean Fields with defaults
  getUnifiedXo() {
    return this.getDocumentField('unified_xo') || false;
  }

  getDownloadFile() {
    return this.getDocumentField('downloadFile') || false;
  }

  getIsExempt() {
    return this.getDocumentField('is_exempt') || false;
  }

  getWorkShiftRequired() {
    return this.getDocumentField('work_shift_required') || false;
  }

  // Social Fields with defaults
  getCommentCount() {
    return this.getDocumentField('comment_count') || 0;
  }

  getViewCount() {
    return this.getDocumentField('view_count') || 0;
  }

  getUpvoteCount() {
    return this.getDocumentField('upvote_count') || 0;
  }

  getDownvoteCount() {
    return this.getDocumentField('downvote_count') || 0;
  }

  getShareCount() {
    return this.getDocumentField('share_count') || 0;
  }

  getSummary() {
    return this.getDocumentField('summary');
  }

  getCustomFields() {
    return this.getDocumentField('customFields') || {};
  }

  getVersionInfo() {
    return this.getDocumentField('versionInfo') || {};
  }

  getAuditTrail() {
    return this.getDocumentField('auditTrail') || [];
  }

  getProcessingHistory() {
    return this.getDocumentField('processingHistory') || [];
  }

  getSystemMetadata() {
    return this.getDocumentField('systemMetadata') || {};
  }

  getCustomMetadata() {
    return this.getDocumentField('customMetadata') || {};
  }

  getSourceMetadata() {
    return this.getDocumentField('sourceMetadata') || {};
  }

  getProcessingConfig() {
    return this.getDocumentField('processingConfig') || {};
  }

  getExtractionRules() {
    return this.getDocumentField('extractionRules') || [];
  }

  getValidationRules() {
    return this.getDocumentField('validationRules') || [];
  }

  getEnrichmentRules() {
    return this.getDocumentField('enrichmentRules') || [];
  }

  getProcessingRules() {
    return this.getDocumentField('processingRules') || [];
  }

  getChunkId() {
    return this.getDocumentField('chunkId');
  }

  getDocumentId() {
    return this.getDocumentField('docId');
  }

  getSourceId() {
    return this.getDocumentField('sourceId');
  }

  getSearchIndexId() {
    return this.getDocumentField('searchIndexId');
  }

  getExtractionModel() {
    return this.getDocumentField('extractionModel');
  }

  getChunkTitle() {
    return this.getDocumentField('chunkTitle');
  }

  getRecordUrl() {
    return this.getDocumentField('recordUrl');
  }

  getRecordTitle() {
    return this.getDocumentField('recordTitle');
  }

  getSysFileType() {
    return this.getDocumentField('sys_file_type');
  }

  getSourceName() {
    return this.getDocumentField('sourceName');
  }

  getSourceType() {
    return this.getDocumentField('sourceType');
  }

  getSourceAcl() {
    return this.getDocumentField('sourceAcl') || ["*"];
  }

  getSourceUrl() {
    return this.getDocumentField('sourceUrl');
  }

  getChunkType() {
    return this.getDocumentField('chunkType');
  }

  getChunkText() {
    return this.getDocumentField('chunkText');
  }

  getChunkMeta() {
    return this.getDocumentField('chunkMeta') || {};
  }

  getPageNumber() {
    return this.getDocumentField('pageNumber');
  }

  getStatus() {
    return this.getDocumentField('status');
  }

  getPriority() {
    return this.getDocumentField('priority');
  }

  getIssueType() {
    return this.getDocumentField('issue_type');
  }

  getDocPath() {
    return this.getDocumentField('doc_path');
  }

  getDocId() {
    return this.getDocumentField('docId');
  }

  getTopic() {
    return this.getDocumentField('topic');
  }

  getArticleId() {
    return this.getDocumentField('article_id');
  }

  getArticleCount() {
    return this.getDocumentField('article_count');
  }

  getPopularity() {
    return this.getDocumentField('popularity');
  }

  getRelatedArticles() {
    return this.getDocumentField('related_articles') || [];
  }

  getCreatedOn() {
    return this.getDocumentField('createdOn');
  }

  getUpdatedOn() {
    return this.getDocumentField('updatedOn');
  }

  getCreatedBy() {
    return this.getDocumentField('createdBy');
  }

  getUpdatedBy() {
    return this.getDocumentField('updatedBy');
  }

  getSysContentType() {
    return this.getDocumentField('sys_content_type');
  }

  getSysRacl() {
    return this.getDocumentField('sys_racl');
  }

  getSysSourceName() {
    return this.getDocumentField('sys_source_name');
  }

  getCollection() {
    return this.getDocumentField('collection');
  }

  getGroupName() {
    return this.getDocumentField('group_name');
  }

  getArticleSource() {
    return this.getDocumentField('article_source');
  }

  getUserId() {
    return this.getDocumentField('user_id');
  }

  getStreamId() {
    return this.getDocumentField('streamId');
  }

  getFileContent() {
    return this.getDocumentField('file_content');
  }

  getPagesInfo() {
    return this.getDocumentField('pages_info') || {};
  }

  getFileFormat() {
    return this.getDocumentField('file_format');
  }

  getText() {
    return this.getDocumentField('text');
  }

  getContent() {
    return this.getDocumentField('content');
  }

  getFileContentType() {
    return this.getDocumentField('file_content_type');
  }

  getModifiedOn() {
    return this.getDocumentField('modifiedOn');
  }

  getLastSyncAt() {
    return this.getDocumentField('lastSyncAt');
  }

  getClosedOn() {
    return this.getDocumentField('closedOn');
  }

  // Business Fields
  getType() {
    return this.getDocumentField('type');
  }

  getDocSource() {
    return this.getDocumentField('docSource') || {};
  }

  getProduct() {
    return this.getDocumentField('product');
  }

  getPartner() {
    return this.getDocumentField('partner');
  }

  getLeadSource() {
    return this.getDocumentField('lead_source');
  }

  getTotalRevenue() {
    return this.getDocumentField('total_revenue');
  }

  getRecentDealAmount() {
    return this.getDocumentField('recent_deal_amount');
  }

  getDeals() {
    return this.getDocumentField('deals') || [];
  }

  // Project Fields
  getProjectId() {
    return this.getDocumentField('project_id');
  }

  getProjectName() {
    return this.getDocumentField('project_name');
  }

  getProjectStatus() {
    return this.getDocumentField('project_status');
  }

  getProjectDescription() {
    return this.getDocumentField('project_description');
  }

  getProjectOwnerId() {
    return this.getDocumentField('project_owner_id');
  }

  getProjectOwnerName() {
    return this.getDocumentField('project_owner_name');
  }

  getProjectOwnerEmail() {
    return this.getDocumentField('project_owner_email');
  }

  // Workspace Fields
  getWorkspaceId() {
    return this.getDocumentField('workspace_id');
  }

  getWorkspaceName() {
    return this.getDocumentField('workspace_name');
  }

  getOrganisationId() {
    return this.getDocumentField('organisation_id');
  }

  getOrganisationName() {
    return this.getDocumentField('organisation_name');
  }

  getSpaceMeta() {
    return this.getDocumentField('space_meta');
  }

  getSpace() {
    return this.getDocumentField('space');
  }

  // Site Fields
  getSiteId() {
    return this.getDocumentField('site_id');
  }

  getSiteName() {
    return this.getDocumentField('site_name');
  }

  getSiteUrl() {
    return this.getDocumentField('site_url');
  }

  getWebsite() {
    return this.getDocumentField('website');
  }

  // Assignment Fields
  getAssignee() {
    return this.getDocumentField('assignee');
  }

  getAssigneeName() {
    return this.getDocumentField('assignee_name');
  }

  getAssigneeEmail() {
    return this.getDocumentField('assignee_email');
  }

  getReporter() {
    return this.getDocumentField('reporter');
  }

  getReporterName() {
    return this.getDocumentField('reporter_name');
  }

  getReporterEmail() {
    return this.getDocumentField('reporter_email');
  }

  getDueDate() {
    return this.getDocumentField('due_date');
  }

  getSprint() {
    return this.getDocumentField('sprint');
  }

  // Company Fields
  getCompanyId() {
    return this.getDocumentField('company_id');
  }

  getCompanyName() {
    return this.getDocumentField('company_name');
  }

  getContactId() {
    return this.getDocumentField('contact_id');
  }

  getContactName() {
    return this.getDocumentField('contact_name');
  }

  getCompanies() {
    return this.getDocumentField('companies') || [];
  }

  getDepartment() {
    return this.getDocumentField('department');
  }

  // Repository Fields
  getRepositoryId() {
    return this.getDocumentField('repository_id');
  }

  getRepositoryName() {
    return this.getDocumentField('repository_name');
  }

  getBranch() {
    return this.getDocumentField('branch');
  }

  getSourceBranch() {
    return this.getDocumentField('source_branch');
  }

  getDestinationBranch() {
    return this.getDocumentField('destination_branch');
  }

  getCommitId() {
    return this.getDocumentField('commit_id');
  }

  // Communication Fields
  getThreadId() {
    return this.getDocumentField('thread_id');
  }

  getConversationId() {
    return this.getDocumentField('conversation_id');
  }

  getChannelId() {
    return this.getDocumentField('channel_id');
  }

  getIsChannelPrivate() {
    return this.getDocumentField('is_channel_private') || false;
  }

  getChannelType() {
    return this.getDocumentField('channel_type');
  }

  getMessageType() {
    return this.getDocumentField('message_type');
  }

  getMentionedUsers() {
    return this.getDocumentField('mentioned_users') || [];
  }

  // Resource Fields
  getResourceType() {
    return this.getDocumentField('resource_type');
  }

  getResourceName() {
    return this.getDocumentField('resource_name') || [];
  }

  // Parent Fields
  getParentName() {
    return this.getDocumentField('parent_name');
  }

  getParentUrl() {
    return this.getDocumentField('parent_url');
  }

  getParentId() {
    return this.getDocumentField('parent_id');
  }

  getParentIncident() {
    return this.getDocumentField('parent_incident');
  }

  // Social Fields
  getComments() {
    return this.getDocumentField('comments') || [];
  }

  // Access Control Fields
  getAccessLevel() {
    return this.getDocumentField('access_level');
  }

  getVisibility() {
    return this.getDocumentField('visibility');
  }

  getAvailability() {
    return this.getDocumentField('availability');
  }

  // Additional Communication Fields
  getChannelName() {
    return this.getDocumentField('channel_name');
  }

  getAuthors() {
    return this.getDocumentField('authors') || [];
  }

  getReactions() {
    return this.getDocumentField('reactions') || [];
  }

  getAttachments() {
    return this.getDocumentField('attachments') || [];
  }

  // Worker Fields
  getWorkerId() {
    return this.getDocumentField('worker_id');
  }

  getWorkerType() {
    return this.getDocumentField('worker_type');
  }

  getOrganization() {
    return this.getDocumentField('organization');
  }

  getSuperiorOrgName() {
    return this.getDocumentField('superior_org_name');
  }

  getManager() {
    return this.getDocumentField('manager');
  }

  getJobFamilyGroup() {
    return this.getDocumentField('job_family_group');
  }

  getManagementLevel() {
    return this.getDocumentField('management_level');
  }

  getJobFamilies() {
    return this.getDocumentField('job_families') || [];
  }

  // Custom Fields
  getCfs1() {
    return this.getDocumentField('cfs1');
  }

  getCfs2() {
    return this.getDocumentField('cfs2');
  }

  getCfs3() {
    return this.getDocumentField('cfs3');
  }

  getCfs4() {
    return this.getDocumentField('cfs4');
  }

  getCfs5() {
    return this.getDocumentField('cfs5');
  }

  getCfa1() {
    return this.getDocumentField('cfa1');
  }

  getCfa2() {
    return this.getDocumentField('cfa2');
  }

  getCfa3() {
    return this.getDocumentField('cfa3');
  }

  getCfa4() {
    return this.getDocumentField('cfa4');
  }

  getCfa5() {
    return this.getDocumentField('cfa5');
  }

  // Additional Timestamp Fields
  getCreatedAt() {
    return this.getDocumentField('created_at');
  }

  getUpdatedAt() {
    return this.getDocumentField('updated_at');
  }

  getPublishedAt() {
    return this.getDocumentField('published_at');
  }

  getArchivedAt() {
    return this.getDocumentField('archived_at');
  }

  getDeletedAt() {
    return this.getDocumentField('deleted_at');
  }

  getClosedDate() {
    return this.getDocumentField('closed_date');
  }

  getOpenedDate() {
    return this.getDocumentField('opened_date');
  }

  getSLADueDate() {
    return this.getDocumentField('sla_due_date');
  }

  getResolvedAt() {
    return this.getDocumentField('resolved_at');
  }

  getDeliveryTime() {
    return this.getDocumentField('delivery_time');
  }

  getCheckedDate() {
    return this.getDocumentField('checked_date');
  }

  getReviewDate() {
    return this.getDocumentField('review_date');
  }

  getStartDate() {
    return this.getDocumentField('start_date');
  }

  // Cost Fields
  getCost() {
    return this.getDocumentField('cost');
  }

  getPrice() {
    return this.getDocumentField('price');
  }

  getOrder() {
    return this.getDocumentField('order');
  }

  // Incident Fields
  getIncidentNumber() {
    return this.getDocumentField('incident_number');
  }

  getSeverity() {
    return this.getDocumentField('severity');
  }

  getUrgency() {
    return this.getDocumentField('urgency');
  }

  // Source Fields
  getCategory() {
    return this.getDocumentField('category');
  }

  getSubCategory() {
    return this.getDocumentField('sub_category');
  }

  getLanguage() {
    return this.getDocumentField('language');
  }

  getLocation() {
    return this.getDocumentField('location');
  }

  getCountry() {
    return this.getDocumentField('country');
  }

  getCity() {
    return this.getDocumentField('city');
  }

  getRegion() {
    return this.getDocumentField('region');
  }

  getConnectorType() {
    return this.getDocumentField('connector_type');
  }

  getDownloadUrl() {
    return this.getDocumentField('download_url');
  }

  // User Document Fields
  getDocCreatedBy() {
    return this.getDocumentField('doc_created_by');
  }

  getDocCreatedByName() {
    return this.getDocumentField('doc_created_by_name');
  }

  getDocCreatedByEmail() {
    return this.getDocumentField('doc_created_by_email');
  }

  getDocCreatedOn() {
    return this.getDocumentField('doc_created_on');
  }

  getDocUpdatedBy() {
    return this.getDocumentField('doc_updated_by');
  }

  getDocUpdatedByName() {
    return this.getDocumentField('doc_updated_by_name');
  }

  getDocUpdatedByEmail() {
    return this.getDocumentField('doc_updated_by_email');
  }

  getDocUpdatedOn() {
    return this.getDocumentField('doc_updated_on');
  }

  getOwnerId() {
    return this.getDocumentField('owner_id');
  }

  getOwnerName() {
    return this.getDocumentField('owner_name');
  }

  getOwnerEmail() {
    return this.getDocumentField('owner_email');
  }

  // Pipeline Fields
  getPipeline() {
    return this.getDocumentField('pipeline') || {};
  }

  getOpportunityId() {
    return this.getDocumentField('opportunity_id');
  }

  getStage() {
    return this.getDocumentField('stage');
  }

  getProbability() {
    return this.getDocumentField('probability');
  }

  getAmount() {
    return this.getDocumentField('amount');
  }

  getExpectedRevenue() {
    return this.getDocumentField('expected_revenue');
  }

  // Fiscal Fields
  getFiscalQuarter() {
    return this.getDocumentField('fiscal_quarter');
  }

  getFiscalYear() {
    return this.getDocumentField('fiscal_year');
  }

  // Status Fields
  getIsWon() {
    return this.getDocumentField('is_won') || false;
  }

  getIsPublished() {
    return this.getDocumentField('is_published') || false;
  }

  getIsChannelExtShared() {
    return this.getDocumentField('is_channel_ext_shared') || false;
  }

  getIsAttachment() {
    return this.getDocumentField('is_attachment') || false;
  }

  getIsThread() {
    return this.getDocumentField('is_thread') || false;
  }

  getIsMention() {
    return this.getDocumentField('is_mention') || false;
  }

  getIsReaction() {
    return this.getDocumentField('is_reaction') || false;
  }

  // Contact Fields
  getPrimaryContacts() {
    return this.getDocumentField('primary_contacts') || [];
  }

  getContacts() {
    return this.getDocumentField('contacts') || [];
  }

  // Product Fields
  getProducts() {
    return this.getDocumentField('products') || [];
  }

  getTotalProductAmount() {
    return this.getDocumentField('total_product_amount') || 0;
  }

  // Order Fields
  getOrderNumber() {
    return this.getDocumentField('order_number');
  }

  getOrigin() {
    return this.getDocumentField('origin');
  }

  getEscalated() {
    return this.getDocumentField('escalated') || false;
  }

  getConverted() {
    return this.getDocumentField('converted') || false;
  }

  getScore() {
    return this.getDocumentField('score') || 0;
  }

  getDescription() {
    return this.getDocumentField('description');
  }

  // Story Fields
  getLinkedStories() {
    return this.getDocumentField('linked_stories') || [];
  }

  getStoryId() {
    return this.getDocumentField('story_id');
  }

  // Drive Fields
  getDriveType() {
    return this.getDocumentField('drive_type');
  }

  getDriveId() {
    return this.getDocumentField('drive_id');
  }

  getBlog() {
    return this.getDocumentField('blog');
  }

  getReviewers() {
    return this.getDocumentField('reviewers') || [];
  }

  // Additional Fields
  getSlug() {
    return this.getDocumentField('slug');
  }

  getTopicSlug() {
    return this.getDocumentField('topic_slug');
  }

  getTickets() {
    return this.getDocumentField('tickets') || [];
  }

  getWorkflowName() {
    return this.getDocumentField('workflow_name');
  }

  getCheckLists() {
    return this.getDocumentField('check_lists') || [];
  }

  getList() {
    return this.getDocumentField('list') || [];
  }

  getAncestors() {
    return this.getDocumentField('ancestors') || [];
  }

  // Industry Fields
  getIndustry() {
    return this.getDocumentField('industry');
  }

  getAnnualRevenue() {
    return this.getDocumentField('annual_revenue');
  }

  getCallbackUrl() {
    return this.getHeader('callbackUrl');
  }

  getTraceId() {
    return this.getHeader('traceId');
  }
}

module.exports = RequestWrapper; 