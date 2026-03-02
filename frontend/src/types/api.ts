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
