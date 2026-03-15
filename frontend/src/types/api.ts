export type ApiResponse<T> = {
  code: number;
  message: string;
  data: T;
};

export type LoginData = {
  access_token: string;
  token_type: string;
  user_id: number;
  username: string;
  email: string;
};

export type UserInfoData = {
  id: number;
  username: string;
  role: string;
  orgTags: string[];
  primaryOrg?: string | null;
};

export type CaptchaData = {
  captcha_id: string;
  captcha_image: string;
};

export type RegisterData = {
  id: number;
  username: string;
  email: string;
  access_token: string;
  token_type: string;
};

export type RegisterOrgTagOption = {
  tagId: string;
  name: string;
  description?: string | null;
};

export type UploadChunkRespData = {
  uploaded: number[];
  progress: number;
};

export type UploadStatusData = {
  uploaded: number[];
  progress: number;
  total_chunks: number;
};

export type MergeData = {
  object_url: string;
  file_size: number;
};

export type UploadedFileInfo = {
  fileMd5: string;
  fileName: string;
  totalSize: number;
  status: number;
  userId: string;
  orgTagName?: string | null;
  kbProfile?: string | null;
  isPublic: boolean;
  createdAt?: string;
  mergedAt?: string | null;
  vectorCount?: number;
  tableRowCount?: number;
  imageBlockCount?: number;
  relationNodeCount?: number;
  relationEdgeCount?: number;
};

export type EsPreviewItem = {
  chunkId: number;
  chunkType?: string | null;
  page?: number | null;
  sheet?: string | null;
  textPreview: string;
  score: number;
};

export type SourceDetailData = {
  fileMd5: string;
  fileName: string;
  objectPath?: string | null;
  originalUrl?: string | null;
  imageUrls?: string[];
  previewRows: EsPreviewItem[];
};

export type StructuredOverviewFileInfo = {
  fileMd5: string;
  fileName: string;
  totalSize: number;
  status: number;
  userId: string;
  orgTagName?: string | null;
  kbProfile?: string | null;
  isPublic: boolean;
  createdAt?: string;
  mergedAt?: string | null;
  vectorCount: number;
  tableRowCount: number;
  imageBlockCount: number;
  relationNodeCount: number;
  relationEdgeCount: number;
  documentUnitCount: number;
  semanticBlockCount: number;
  parentChunkCount: number;
  childChunkCount: number;
  visualPageCount: number;
  visualEmbeddingCount: number;
  visualIndexedCount: number;
  acceptedBlockCount: number;
  weakBlockCount: number;
  rejectedBlockCount: number;
};

export type StructuredDocumentUnitItem = {
  unitType: string;
  unitKey: string;
  unitName?: string | null;
  unitOrder?: number | null;
  page?: number | null;
  sheet?: string | null;
  section?: string | null;
  parentUnitKey?: string | null;
};

export type StructuredSemanticBlockItem = {
  blockIndex: number;
  documentUnitKey?: string | null;
  blockType: string;
  sourceParser?: string | null;
  page?: number | null;
  sheet?: string | null;
  section?: string | null;
  rowNo?: number | null;
  qualityScore: number;
  qualityStatus: string;
  parserConfidence?: number | null;
  validationFlags: string[];
  textPreview: string;
  imageUrl?: string | null;
};

export type StructuredParentChunkItem = {
  parentChunkId: number;
  documentUnitKey?: string | null;
  chunkType?: string | null;
  qualityScore: number;
  qualityStatus: string;
  textPreview: string;
};

export type StructuredChildChunkItem = {
  childChunkId: number;
  parentChunkId?: number | null;
  documentUnitKey?: string | null;
  chunkType?: string | null;
  qualityScore: number;
  qualityStatus: string;
  neighborPrevId?: number | null;
  neighborNextId?: number | null;
  textPreview: string;
};

export type StructuredImageItem = {
  page?: number | null;
  sheet?: string | null;
  sourceParser?: string | null;
  imageUrl: string;
  imageWidth?: number | null;
  imageHeight?: number | null;
  matchMode?: string | null;
  matchConfidence?: number | null;
};

export type StructuredVisualPageItem = {
  visualPageId: number;
  documentUnitId?: number | null;
  unitType?: string | null;
  page?: number | null;
  sheet?: string | null;
  section?: string | null;
  pageLabel?: string | null;
  renderSource?: string | null;
  renderVersion?: string | null;
  qualityStatus: string;
  visualEmbeddingStatus?: string | null;
  visualEmbeddingProvider?: string | null;
  visualEmbeddingModel?: string | null;
  visualEmbeddingDim?: number | null;
  visualEmbeddingError?: string | null;
  visualIndexed: boolean;
  visualIndexDocId?: string | null;
  imageUrl: string;
  imageWidth?: number | null;
  imageHeight?: number | null;
};

export type StructuredRelationNodeItem = {
  nodeId: number;
  nodeKey: string;
  nodeName: string;
  nodeType?: string | null;
  page?: number | null;
  evidenceText?: string | null;
};

export type StructuredRelationEdgeItem = {
  edgeId: number;
  srcNodeId: number;
  srcNodeName: string;
  dstNodeId: number;
  dstNodeName: string;
  relationType: string;
  relationText?: string | null;
  page?: number | null;
  evidenceText?: string | null;
};

export type StructuredFileDetailData = {
  fileMd5: string;
  fileName: string;
  originalUrl?: string | null;
  documentUnits: StructuredDocumentUnitItem[];
  semanticBlocks: StructuredSemanticBlockItem[];
  parentChunks: StructuredParentChunkItem[];
  childChunks: StructuredChildChunkItem[];
  images: StructuredImageItem[];
  visualPages: StructuredVisualPageItem[];
  relationNodes: StructuredRelationNodeItem[];
  relationEdges: StructuredRelationEdgeItem[];
};

export type ProfileOption = {
  profile_id: string;
  name: string;
  description: string;
};

export type ProfileStateData = {
  selected_profile?: string | null;
  selected_name?: string | null;
  locked: boolean;
  options: ProfileOption[];
};

export type IntentKeywordCategory = {
  key: string;
  label: string;
  keywords: string[];
};

export type IntentKeywordsConfigData = {
  categories: IntentKeywordCategory[];
  updated_at?: string | null;
};

export type EvalRunData = {
  runId: number;
  runName: string;
  gitCommit?: string | null;
  env?: string | null;
  status: string;
  startedAt: string;
  finishedAt?: string | null;
  createdBy?: number | null;
};

export type EvalRunListItem = {
  runId: number;
  runName: string;
  gitCommit?: string | null;
  env?: string | null;
  status: string;
  startedAt: string;
  finishedAt?: string | null;
  metricsCount: number;
  casesCount: number;
  coverageCount: number;
};

export type EvalMetricItem = {
  metricKey: string;
  metricValue: number;
  threshold?: number | null;
  passed?: boolean | null;
  dimension?: string | null;
  note?: string | null;
};

export type EvalAssetCoverageItem = {
  assetType: string;
  totalCount: number;
  indexedCount: number;
  coverageRate: number;
  note?: string | null;
};

export type EvalRunSummaryData = {
  run: EvalRunData;
  metrics: EvalMetricItem[];
  coverage: EvalAssetCoverageItem[];
  caseStats: {
    total: number;
    passed: number;
    passRate: number;
  };
};

export type EvalOnlineIntentStat = {
  intent: string;
  count: number;
};

export type EvalOnlineDailyStat = {
  date: string;
  total: number;
  success: number;
  noEvidence: number;
  error: number;
  avgLatencyMs: number;
};

export type EvalOnlineQuestionSample = {
  createdAt: string;
  status: string;
  intent?: string | null;
  question: string;
  answer?: string | null;
};

export type EvalOnlineSummaryData = {
  windowStart: string;
  windowEnd: string;
  totalQuestions: number;
  successCount: number;
  noEvidenceCount: number;
  errorCount: number;
  archivedCount: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
  retrievalHitRate: number;
  withSourcesRate: number;
  intentStats: EvalOnlineIntentStat[];
  dailyStats: EvalOnlineDailyStat[];
  questionSamples: EvalOnlineQuestionSample[];
};
