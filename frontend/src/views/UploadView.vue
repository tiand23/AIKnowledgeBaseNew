<template>
  <AppLayout>
    <div class="page-wrap">
      <el-card>
        <template #header>
          <div class="header">複数ファイル分割アップロード</div>
        </template>
        <el-alert
          v-if="profile.selectedName"
          type="info"
          show-icon
          :closable="false"
          :title="`現在のシナリオ: ${profile.selectedName}（固定）`"
          class="scene-alert"
        />

        <el-form label-width="120px">
          <el-form-item label="ファイル選択">
            <input type="file" multiple @change="onFileChange" />
          </el-form-item>
          <el-form-item label="組織タグ">
            <el-select
              v-model="orgTag"
              filterable
              clearable
              style="width: 100%"
              placeholder="組織タグを選択"
            >
              <el-option
                v-for="item in orgTagOptions"
                :key="item.tagId"
                :label="`${item.name} (${item.tagId})`"
                :value="item.tagId"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="公開ドキュメント">
            <el-switch v-model="isPublic" />
          </el-form-item>
          <el-form-item label="分割サイズ">
            <el-input v-model.number="chunkSizeMB" type="number" min="1" max="20">
              <template #append>MB</template>
            </el-input>
          </el-form-item>
        </el-form>

        <div class="actions">
          <el-button type="primary" :loading="submitting" :disabled="!tasks.length" @click="submitAll">
            アップロード開始
          </el-button>
          <el-button :disabled="submitting || !tasks.length" @click="clearTasks">一覧クリア</el-button>
        </div>

        <div v-if="tasks.length === 0" class="tip empty">
          ファイルがありません。先にファイルを選択してください。アップロードは順番に実行され、自動マージされます。
        </div>

        <div v-for="task in tasks" :key="task.id" class="task-card">
          <div class="task-head">
            <div class="task-name">{{ task.file.name }}</div>
            <el-tag :type="statusType(task.status)">{{ statusText(task.status) }}</el-tag>
          </div>
          <div class="task-meta">
            <p><strong>サイズ:</strong> {{ formatBytes(task.file.size) }}</p>
            <p><strong>MD5:</strong> {{ task.fileMd5 || "計算中..." }}</p>
            <p v-if="task.message"><strong>ステータス:</strong> {{ task.message }}</p>
          </div>
          <el-progress :percentage="task.progress" :stroke-width="14" />
          <p class="tip">アップロード済みチャンク: {{ task.uploadedChunks.length }} / {{ task.totalChunks || "-" }}</p>
          <div class="task-actions">
            <el-button size="small" type="danger" :disabled="submitting" @click="removeTask(task.id)">
              削除
            </el-button>
          </div>
        </div>

        <el-divider />

        <div class="history-header">
          <div class="history-title">最近のアップロード履歴</div>
          <el-button size="small" :loading="historyLoading" @click="refreshUploadedFiles">更新</el-button>
        </div>

        <div v-if="recentUploads.length === 0" class="tip empty">履歴はありません（更新で再取得）。</div>

        <div v-for="item in recentUploads" :key="item.fileMd5" class="task-card">
          <div class="task-head">
            <div class="task-name">{{ item.fileName }}</div>
            <el-tag :type="statusTypeByCode(item.status)">{{ statusTextByCode(item.status) }}</el-tag>
          </div>
          <div class="task-meta">
            <p><strong>サイズ:</strong> {{ formatBytes(item.totalSize) }}</p>
            <p><strong>MD5:</strong> {{ item.fileMd5 }}</p>
            <p><strong>組織:</strong> {{ item.orgTagName || "-" }}</p>
            <p><strong>公開:</strong> {{ item.isPublic ? "公開" : "非公開" }}</p>
            <p><strong>シナリオ:</strong> {{ formatProfileName(item.kbProfile) }}</p>
            <p><strong>ベクトルチャンク:</strong> {{ item.vectorCount || 0 }}</p>
            <p><strong>表行:</strong> {{ item.tableRowCount || 0 }}</p>
            <p><strong>画像ブロック:</strong> {{ item.imageBlockCount || 0 }}</p>
            <p><strong>関係ノード:</strong> {{ item.relationNodeCount || 0 }}</p>
            <p><strong>関係エッジ:</strong> {{ item.relationEdgeCount || 0 }}</p>
            <p><strong>詳細:</strong> {{ statusDescByCode(item.status) }}</p>
          </div>
          <div class="task-actions">
            <el-button size="small" @click="openEsPreview(item)">ESプレビュー</el-button>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="previewDialogVisible" title="ES ドキュメントプレビュー" width="760px">
      <div v-if="previewTargetName" class="tip" style="margin-top: 0; margin-bottom: 10px">
        ファイル: {{ previewTargetName }}
      </div>
      <el-skeleton :loading="previewLoading" :rows="5" animated>
        <div v-if="previewRows.length === 0" class="tip">ドキュメントチャンクがありません（処理中の可能性があります）。</div>
        <div v-for="row in previewRows" :key="`${row.chunkId}-${row.page}-${row.sheet}`" class="preview-row">
          <div class="preview-head">
            <el-tag size="small" type="info">chunk: {{ row.chunkId }}</el-tag>
            <el-tag v-if="row.chunkType" size="small">{{ row.chunkType }}</el-tag>
            <el-tag v-if="row.page !== null && row.page !== undefined" size="small">page: {{ row.page }}</el-tag>
            <el-tag v-if="row.sheet" size="small">sheet: {{ row.sheet }}</el-tag>
            <el-tag size="small" type="success">score: {{ row.score.toFixed(3) }}</el-tag>
          </div>
          <div class="preview-text">{{ row.textPreview || "-" }}</div>
        </div>
      </el-skeleton>
    </el-dialog>
  </AppLayout>
</template>

<script setup lang="ts">
import SparkMD5 from "spark-md5";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { uploadChunk, mergeFile, getUserUploadedFiles, getEsPreview } from "../api/file";
import { getRegisterOrgTags } from "../api/auth";
import type { UploadedFileInfo, EsPreviewItem, RegisterOrgTagOption } from "../types/api";
import { useAuthStore } from "../stores/auth";
import { useProfileStore } from "../stores/profile";

const orgTag = ref("");
const orgTagOptions = ref<RegisterOrgTagOption[]>([]);
const isPublic = ref(false);
const chunkSizeMB = ref(2);
const profile = useProfileStore();
const auth = useAuthStore();

type UploadTaskStatus =
  | "hashing"
  | "ready"
  | "uploading"
  | "merging"
  | "processing"
  | "done"
  | "failed";

type UploadTask = {
  id: string;
  file: File;
  fileMd5: string;
  totalChunks: number;
  uploadedChunks: number[];
  progress: number;
  status: UploadTaskStatus;
  message: string;
  submitted: boolean;
};

const tasks = ref<UploadTask[]>([]);
const submitting = ref(false);
let statusPollTimer: ReturnType<typeof setInterval> | null = null;
const historyLoading = ref(false);
const recentUploads = ref<UploadedFileInfo[]>([]);
const previewDialogVisible = ref(false);
const previewLoading = ref(false);
const previewRows = ref<EsPreviewItem[]>([]);
const previewTargetName = ref("");

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) {
    return;
  }

  for (const file of files) {
    const id = `${file.name}-${file.size}-${file.lastModified}`;
    if (tasks.value.some((x) => x.id === id)) {
      continue;
    }
    const task: UploadTask = {
      id,
      file,
      fileMd5: "",
      totalChunks: 0,
      uploadedChunks: [],
      progress: 0,
      status: "hashing",
      message: "MD5 計算中",
      submitted: false
    };
    tasks.value.push(task);
    void prepareTask(task);
  }

  input.value = "";
}

async function prepareTask(task: UploadTask) {
  try {
    const file = task.file;
    const chunkBytes = Math.max(1, chunkSizeMB.value) * 1024 * 1024;
    task.totalChunks = Math.ceil(file.size / chunkBytes);
    task.fileMd5 = await computeMd5WithTimeout(file, 30000);
    task.status = "ready";
    task.message = "送信待ち";
  } catch (err: any) {
    task.status = "failed";
    task.message = err?.message || "MD5 計算失敗";
  }
}

async function computeMd5(file: File): Promise<string> {
  const chunkSize = 2 * 1024 * 1024;
  const chunks = Math.ceil(file.size / chunkSize);
  const spark = new SparkMD5.ArrayBuffer();

  for (let i = 0; i < chunks; i += 1) {
    const start = i * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const buffer = await file.slice(start, end).arrayBuffer();
    spark.append(buffer);
  }

  return spark.end();
}

async function computeMd5WithTimeout(file: File, timeoutMs: number): Promise<string> {
  const timeoutPromise = new Promise<string>((_, reject) => {
    setTimeout(() => reject(new Error("MD5 計算がタイムアウトしました。削除して再試行してください")), timeoutMs);
  });
  return Promise.race([computeMd5(file), timeoutPromise]);
}

async function submitAll() {
  if (!tasks.value.length) {
    ElMessage.warning("先にファイルを選択してください");
    return;
  }
  submitting.value = true;
  let ok = 0;
  let failed = 0;

  for (const task of tasks.value) {
    if (
      task.status === "processing" ||
      task.status === "uploading" ||
      task.status === "merging" ||
      task.status === "done"
    ) {
      continue;
    }
    const success = await submitSingle(task);
    if (success) {
      ok += 1;
    } else {
      failed += 1;
    }
  }

  submitting.value = false;
  if (failed === 0) {
    ElMessage.success(`送信完了: ${ok} 件をバックエンド処理に投入しました`);
  } else {
    ElMessage.warning(`送信完了: 成功 ${ok} / 失敗 ${failed}`);
  }
  await refreshUploadedFiles();
  startStatusPolling();
}

async function submitSingle(task: UploadTask): Promise<boolean> {
  try {
    task.submitted = true;

    if (!task.fileMd5) {
      task.status = "hashing";
      task.message = "MD5 計算中";
      task.fileMd5 = await computeMd5WithTimeout(task.file, 30000);
      task.status = "ready";
      task.message = "MD5 計算完了、アップロード開始";
    }

    task.status = "uploading";
    task.message = "チャンクアップロード中";

    const chunkBytes = Math.max(1, chunkSizeMB.value) * 1024 * 1024;
    task.totalChunks = Math.ceil(task.file.size / chunkBytes);

    for (let i = 0; i < task.totalChunks; i += 1) {
      if (task.uploadedChunks.includes(i)) {
        continue;
      }
      const start = i * chunkBytes;
      const end = Math.min(task.file.size, start + chunkBytes);
      const chunkBlob = task.file.slice(start, end);

      const resp = await uploadChunk({
        file: chunkBlob,
        fileMd5: task.fileMd5,
        chunkIndex: i,
        totalSize: task.file.size,
        fileName: task.file.name,
        totalChunks: task.totalChunks,
        orgTag: orgTag.value || undefined,
        isPublic: isPublic.value
      });

      task.uploadedChunks = resp.data.uploaded || task.uploadedChunks;
      task.progress = Number(Math.min(70, (resp.data.progress || 0) * 0.7).toFixed(2));
    }

    task.status = "merging";
    task.progress = Math.max(task.progress, 74);
    task.message = "自動マージ中";
    const merged = await mergeFile(task.fileMd5, task.file.name);

    task.progress = Math.max(task.progress, 78);
    task.status = "processing";
    task.message = `マージ完了（${formatBytes(merged.data.file_size)}）、バックエンド解析中`;
    startStatusPolling();
    return true;
  } catch (err: any) {
    task.status = "failed";
    task.message = err?.response?.data?.detail || err?.response?.data?.message || "アップロード失敗";
    return false;
  }
}

function clearTasks() {
  tasks.value = [];
  stopStatusPolling();
}

function removeTask(id: string) {
  tasks.value = tasks.value.filter((x) => x.id !== id);
  if (!tasks.value.some((x) => x.status === "processing")) {
    stopStatusPolling();
  }
}

function statusText(status: UploadTaskStatus) {
  if (status === "hashing") return "計算中";
  if (status === "ready") return "送信待ち";
  if (status === "uploading") return "アップロード中";
  if (status === "merging") return "マージ中";
  if (status === "processing") return "バックエンド処理中";
  if (status === "done") return "完了";
  return "失敗";
}

function statusType(status: UploadTaskStatus) {
  if (status === "done") return "success";
  if (status === "processing") return "warning";
  if (status === "failed") return "danger";
  if (status === "uploading" || status === "merging") return "warning";
  return "info";
}

function parseBackendTime(raw?: string | null): number {
  if (!raw) {
    return NaN;
  }
  const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
  const hasTz = /Z|[+\-]\d{2}:\d{2}$/.test(normalized);
  const iso = hasTz ? normalized : `${normalized}Z`;
  return Date.parse(iso);
}

function applyBackendStatus(task: UploadTask, backendStatus: number, mergedAt?: string | null, createdAt?: string) {
  const now = Date.now();
  const refTime = mergedAt || createdAt || "";
  const ts = parseBackendTime(refTime);
  const ageSeconds = Number.isNaN(ts) ? 0 : Math.max(0, Math.floor((now - ts) / 1000));

  if (backendStatus === 0) {
    if (task.status !== "uploading") {
      task.status = "uploading";
      task.message = "アップロード進行中";
    }
    task.progress = Math.min(Math.max(task.progress, 5), 70);
    return;
  }
  if (backendStatus === 1 || backendStatus === 2) {
    if (backendStatus === 1 && ageSeconds > 90) {
      task.status = "failed";
      task.progress = Math.max(task.progress, 85);
      task.message = `マージ後 ${ageSeconds}s 経過しても処理未開始です。削除して再アップロードし、バックエンドログを確認してください。`;
      return;
    }
    task.status = "processing";
    if (backendStatus === 1) {
      const stage = Math.min(86, 78 + Math.floor(ageSeconds / 15));
      task.progress = Math.max(task.progress, stage);
      task.message = `マージ済み。バックエンドタスク待機中（${ageSeconds}s）`;
    } else {
      const stage = Math.min(99, 86 + Math.floor(ageSeconds / 8));
      task.progress = Math.max(task.progress, stage);
      task.message = "バックエンド解析中";
    }
    return;
  }
  if (backendStatus === 3) {
    task.status = "done";
    task.progress = 100;
    task.message = "ドキュメント処理完了。検索に利用できます。";
    return;
  }
  if (backendStatus === 4) {
    task.status = "failed";
    task.message = "バックエンド処理に失敗しました。ログ確認または再アップロードしてください。";
  }
}

async function syncTaskStatusFromBackend(task: UploadTask) {
  if (!task.fileMd5 || !task.submitted) {
    return;
  }
  try {
    const resp = await getUserUploadedFiles();
    const file = (resp.data || []).find((x) => x.fileMd5 === task.fileMd5);
    if (!file) {
      return;
    }
    applyBackendStatus(task, file.status, file.mergedAt, file.createdAt);
  } catch {
  }
}

async function pollProcessingStatus() {
  const pending = tasks.value.filter((x) => x.submitted && x.status === "processing");
  if (!pending.length) {
    stopStatusPolling();
    return;
  }
  try {
    const resp = await getUserUploadedFiles();
    recentUploads.value = (resp.data || []).slice().sort((a, b) => {
      const ta = parseBackendTime(a.createdAt || "") || 0;
      const tb = parseBackendTime(b.createdAt || "") || 0;
      return tb - ta;
    });
    const map = new Map((resp.data || []).map((x) => [x.fileMd5, x]));
    for (const task of pending) {
      const remote = map.get(task.fileMd5);
      if (remote) {
        applyBackendStatus(task, remote.status, remote.mergedAt, remote.createdAt);
      }
    }
    if (!tasks.value.some((x) => x.status === "processing")) {
      stopStatusPolling();
    }
  } catch {
  }
}

async function refreshUploadedFiles() {
  historyLoading.value = true;
  try {
    const resp = await getUserUploadedFiles();
    recentUploads.value = (resp.data || []).slice().sort((a, b) => {
      const ta = parseBackendTime(a.createdAt || "") || 0;
      const tb = parseBackendTime(b.createdAt || "") || 0;
      return tb - ta;
    });
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.response?.data?.message || "";
    if (err?.response?.status === 401 || err?.response?.status === 403) {
      ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
    } else {
      ElMessage.error(detail || "履歴更新に失敗しました");
    }
  } finally {
    historyLoading.value = false;
  }
}

function statusTextByCode(code: number) {
  if (code === 0) return "アップロード中";
  if (code === 1) return "処理待ち";
  if (code === 2) return "処理中";
  if (code === 3) return "完了";
  if (code === 4) return "失敗";
  return "不明";
}

function statusTypeByCode(code: number) {
  if (code === 3) return "success";
  if (code === 4) return "danger";
  if (code === 1 || code === 2) return "warning";
  return "info";
}

function statusDescByCode(code: number) {
  if (code === 0) return "チャンクアップロード中";
  if (code === 1) return "マージ済み、バックエンド待機中";
  if (code === 2) return "バックエンド解析中";
  if (code === 3) return "ドキュメント処理完了（検索可）";
  if (code === 4) return "バックエンド処理失敗（ログ確認/再アップロード）";
  return "状態不明";
}

function formatProfileName(profileId?: string | null) {
  if (!profileId) {
    return profile.selectedName || "-";
  }
  const map: Record<string, string> = {
    general: "汎用ドキュメント",
    design: "設計書・アーキテクチャ",
    policy: "規程・業務プロセス",
    ops: "運用・障害対応"
  };
  return map[profileId] || profileId;
}

async function openEsPreview(item: UploadedFileInfo) {
  previewDialogVisible.value = true;
  previewLoading.value = true;
  previewRows.value = [];
  previewTargetName.value = item.fileName;
  try {
    const resp = await getEsPreview(item.fileMd5, 8);
    previewRows.value = resp.data || [];
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.response?.data?.message || "ESプレビュー取得に失敗しました";
    ElMessage.error(detail);
  } finally {
    previewLoading.value = false;
  }
}

function startStatusPolling() {
  if (statusPollTimer) {
    return;
  }
  statusPollTimer = setInterval(() => {
    void pollProcessingStatus();
  }, 4000);
  void pollProcessingStatus();
}

function stopStatusPolling() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

async function loadOrgTagOptions() {
  try {
    await auth.refreshUserAccessInfo();
    const resp = await getRegisterOrgTags();
    const userTagIds = (auth.orgTags || []).map((x) => x.trim()).filter(Boolean);
    const preferred = (auth.primaryOrg || "").trim();

    const serverOptions = (resp.data || [])
      .filter((x) => !String(x.tagId || "").startsWith("PRIVATE_"));

    const optionMap = new Map<string, RegisterOrgTagOption>();
    for (const item of serverOptions) {
      optionMap.set(item.tagId, item);
    }
    for (const tagId of userTagIds) {
      if (!optionMap.has(tagId)) {
        optionMap.set(tagId, { tagId, name: tagId, description: "" });
      }
    }
    if (!optionMap.has("DEFAULT")) {
      optionMap.set("DEFAULT", {
        tagId: "DEFAULT",
        name: "全体公開",
        description: "全ユーザー共通で参照可能"
      });
    }

    orgTagOptions.value = Array.from(optionMap.values()).sort((a, b) => a.tagId.localeCompare(b.tagId));

    if (preferred && optionMap.has(preferred)) {
      orgTag.value = preferred;
    } else if (!orgTag.value && userTagIds.length) {
      orgTag.value = userTagIds[0];
    }
  } catch {
    orgTagOptions.value = [
      { tagId: "DEFAULT", name: "全体公開", description: "全ユーザー共通で参照可能" }
    ];
    if (!orgTag.value) {
      orgTag.value = "DEFAULT";
    }
  }
}

onBeforeUnmount(() => {
  stopStatusPolling();
});

onMounted(() => {
  if (!profile.loaded) {
    void profile.refreshFromServer().catch(() => undefined);
  }
  void loadOrgTagOptions();
  void refreshUploadedFiles();
});
</script>

<style scoped>
.header {
  font-size: 16px;
  font-weight: 700;
}

.scene-alert {
  margin-bottom: 12px;
}

.actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.task-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fafafa;
}

.task-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.task-name {
  font-weight: 600;
}

.task-meta {
  font-size: 14px;
  color: #374151;
  margin-bottom: 8px;
}

.task-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.tip {
  margin-top: 8px;
  color: #6b7280;
}

.empty {
  margin-top: 8px;
  margin-bottom: 8px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.history-title {
  font-size: 15px;
  font-weight: 700;
}

.preview-row {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
}

.preview-head {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.preview-text {
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
