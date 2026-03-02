<template>
  <AppLayout>
    <div class="page-wrap chat-page">
      <el-card class="chat-card">
        <template #header>
          <div class="chat-header">
            <div class="chat-title-wrap">
              <span>ナレッジQ&A</span>
              <el-tag v-if="profile.selectedName" type="info" effect="plain">シナリオ: {{ profile.selectedName }}</el-tag>
            </div>
            <div>
              <el-tag v-if="connected" type="success" effect="light" style="margin-right: 8px">接続済み</el-tag>
              <el-tag v-else-if="connecting" type="warning" effect="light" style="margin-right: 8px">接続中</el-tag>
              <el-tag v-else type="info" effect="light" style="margin-right: 8px">未接続</el-tag>
              <el-button size="small" @click="connect" :disabled="connected || connecting">接続</el-button>
              <el-button size="small" type="warning" @click="disconnect" :disabled="!connected && !connecting">切断</el-button>
            </div>
          </div>
        </template>

        <div class="messages" ref="messagesBox">
          <div v-for="(msg, idx) in messages" :key="idx" class="msg-row" :class="msg.role">
            <div class="bubble">
              <div class="role">{{ msg.role === 'user' ? 'あなた' : 'アシスタント' }}</div>
              <div class="content">{{ stripSourceTags(msg.content) }}</div>
              <div v-if="msg.role === 'assistant' && extractSourceRefs(msg.content).length" class="source-links">
                <div class="source-title">参照リンク</div>
                <div class="source-actions">
                  <el-button size="small" @click="openEvidencePanel(msg.content)">証拠パネル</el-button>
                </div>
                <el-link
                  v-for="(refItem, rIdx) in extractSourceRefs(msg.content)"
                  :key="`${idx}-${rIdx}`"
                  type="primary"
                  :underline="false"
                  @click.prevent="openSource(refItem)"
                >
                  [文書{{ refItem.index }}] {{ refItem.fileName }}（{{ refItem.location }}）
                </el-link>
              </div>
            </div>
          </div>
        </div>

        <div class="input-row">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="3"
            placeholder="質問を入力して送信"
            @keydown.ctrl.enter.prevent="sendMessage"
          />
          <el-button type="primary" :disabled="connecting || !inputText.trim()" @click="sendMessage">
            送信
          </el-button>
        </div>
      </el-card>
    </div>
    <el-dialog v-model="evidenceDialogVisible" title="証拠パネル" width="920px">
      <div v-if="evidenceLoading">読み込み中...</div>
      <div v-else>
        <el-tabs v-model="evidenceActiveTab">
          <el-tab-pane label="概要" name="summary">
            <div class="source-title" style="margin-bottom: 8px;">
              参照件数: {{ evidenceItems.length }}
            </div>
            <div v-for="(item, idx) in evidenceItems" :key="`summary-${idx}`" class="preview-row">
              <div class="preview-meta">[文書{{ item.ref.index }}] {{ item.ref.fileName }} / {{ item.ref.location }}</div>
              <div class="preview-text">
                chunk={{ item.ref.chunkId || "-" }}, page={{ item.ref.page || "-" }}, sheet={{ item.ref.sheet || "-" }}
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="構造化データ" name="structured">
            <div v-if="!evidenceStructuredRows.length">表示可能な構造化データがありません。</div>
            <div v-else class="structured-table-wrap">
              <el-table :data="evidenceStructuredRows" size="small" border max-height="420">
                <el-table-column prop="fileName" label="文書" min-width="180" />
                <el-table-column prop="chunkType" label="種別" min-width="120" />
                <el-table-column prop="chunkId" label="chunk" width="84" />
                <el-table-column prop="page" label="page" width="84" />
                <el-table-column prop="sheet" label="sheet" min-width="140" />
                <el-table-column prop="textPreview" label="内容" min-width="260" show-overflow-tooltip />
              </el-table>
            </div>
          </el-tab-pane>
          <el-tab-pane label="画像" name="images">
            <div v-if="!evidenceImages.length">表示可能な画像がありません。</div>
            <div v-else class="evidence-images">
              <div v-for="(img, idx) in evidenceImages" :key="`img-${idx}`" class="evidence-image-card">
                <div class="preview-meta">{{ img.fileName }} / {{ img.location }}</div>
                <a :href="img.url" target="_blank">
                  <img :src="img.url" alt="evidence image" class="evidence-image" />
                </a>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="ソースマップ" name="mapping">
            <div v-if="!evidenceItems.length">表示可能なソース情報がありません。</div>
            <div v-else>
              <div v-for="(item, idx) in evidenceItems" :key="`map-${idx}`" class="preview-row">
                <div class="preview-meta">
                  [文書{{ item.ref.index }}] {{ item.ref.fileName }} / {{ item.ref.location }}
                </div>
                <div class="preview-text">
                  file_md5={{ item.ref.fileMd5 }} / chunk={{ item.ref.chunkId || "-" }} / page={{ item.ref.page || "-" }} / sheet={{ item.ref.sheet || "-" }}
                </div>
                <div v-if="item.originalUrl" style="margin-top: 6px;">
                  <el-link type="primary" :href="item.originalUrl" target="_blank">
                    原ファイルを開く
                  </el-link>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
    <el-dialog v-model="globalEvidenceDialogVisible" title="全体構造化データ / 画像" width="1040px">
      <div v-if="globalEvidenceLoading">読み込み中...</div>
      <div v-else>
        <el-tabs v-model="globalEvidenceActiveTab">
          <el-tab-pane label="文書一覧" name="files">
            <el-table :data="globalEvidenceFiles" size="small" border max-height="380">
              <el-table-column prop="fileName" label="文書名" min-width="220" />
              <el-table-column prop="kbProfile" label="シナリオ" width="160" />
              <el-table-column prop="vectorCount" label="vector" width="90" />
              <el-table-column prop="tableRowCount" label="table" width="90" />
              <el-table-column prop="imageBlockCount" label="image" width="90" />
              <el-table-column prop="relationEdgeCount" label="relation" width="100" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="構造化データ(全体)" name="structured">
            <div v-if="!globalStructuredRows.length">表示可能な構造化データがありません。</div>
            <el-table v-else :data="globalStructuredRows" size="small" border max-height="420">
              <el-table-column prop="fileName" label="文書" min-width="180" />
              <el-table-column prop="chunkType" label="種別" min-width="120" />
              <el-table-column prop="chunkId" label="chunk" width="84" />
              <el-table-column prop="page" label="page" width="84" />
              <el-table-column prop="sheet" label="sheet" min-width="140" />
              <el-table-column prop="textPreview" label="内容" min-width="280" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="画像(全体)" name="images">
            <div v-if="!globalImageRows.length">表示可能な画像がありません。</div>
            <div v-else class="evidence-images">
              <div v-for="(img, idx) in globalImageRows" :key="`gimg-${idx}`" class="evidence-image-card">
                <div class="preview-meta">{{ img.fileName }}</div>
                <a :href="img.url" target="_blank">
                  <img :src="img.url" alt="global evidence image" class="evidence-image" />
                </a>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
    <el-dialog v-model="sourceDialogVisible" title="根拠プレビュー" width="760px">
      <div v-if="sourceLoading">読み込み中...</div>
      <div v-else>
        <div style="margin-bottom: 8px; color: #4b5563;">{{ sourceDialogTitle }}</div>
        <div v-if="sourceOriginalUrl" style="margin-bottom: 12px;">
          <el-link type="primary" :href="sourceOriginalUrl" target="_blank">
            原ファイルを開く
          </el-link>
        </div>
        <div v-if="sourceImageUrls.length" style="margin-bottom: 12px;">
          <div class="source-title" style="margin-bottom: 6px;">図のプレビュー</div>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            <a v-for="(u, i) in sourceImageUrls" :key="`img-${i}`" :href="u" target="_blank">
              <img :src="u" alt="source image" style="max-width: 220px; border: 1px solid #e5e7eb; border-radius: 6px;" />
            </a>
          </div>
        </div>
        <div v-if="sourcePreviewRows.length === 0">該当プレビューがありません。</div>
        <div v-for="(row, i) in sourcePreviewRows" :key="i" class="preview-row">
          <div class="preview-meta">
            断片{{ row.chunkId }} / page={{ row.page ?? "-" }} / sheet={{ row.sheet ?? "-" }}
          </div>
          <div class="preview-text">{{ row.textPreview }}</div>
        </div>
      </div>
    </el-dialog>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { useAuthStore } from "../stores/auth";
import { useProfileStore } from "../stores/profile";
import { getEsPreview, getSourceDetail, getUserUploadedFiles } from "../api/file";
import type { EsPreviewItem, UploadedFileInfo } from "../types/api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type SourceRef = {
  index: string;
  fileName: string;
  fileMd5: string;
  chunkId: string;
  page: string;
  sheet: string;
  location: string;
};

const auth = useAuthStore();
const profile = useProfileStore();
const wsRef = ref<WebSocket | null>(null);
const connected = ref(false);
const connecting = ref(false);
const inputText = ref("");
const messages = ref<ChatMessage[]>([]);
const messagesBox = ref<HTMLElement | null>(null);
const pendingAssistantIndex = ref<number | null>(null);
const sourceDialogVisible = ref(false);
const sourceLoading = ref(false);
const sourceDialogTitle = ref("");
const sourcePreviewRows = ref<EsPreviewItem[]>([]);
const sourceOriginalUrl = ref("");
const sourceImageUrls = ref<string[]>([]);
const globalEvidenceDialogVisible = ref(false);
const globalEvidenceLoading = ref(false);
const globalEvidenceActiveTab = ref("files");
const globalEvidenceFiles = ref<UploadedFileInfo[]>([]);
const globalStructuredRows = ref<Array<EsPreviewItem & { fileName: string }>>([]);
const globalImageRows = ref<Array<{ fileName: string; url: string }>>([]);
const evidenceDialogVisible = ref(false);
const evidenceLoading = ref(false);
const evidenceActiveTab = ref("summary");
type EvidenceItem = {
  ref: SourceRef;
  previewRows: EsPreviewItem[];
  originalUrl: string;
  imageUrls: string[];
};
const evidenceItems = ref<EvidenceItem[]>([]);

const evidenceStructuredRows = computed(() => {
  const rows: Array<EsPreviewItem & { fileName: string }> = [];
  for (const item of evidenceItems.value) {
    for (const row of item.previewRows || []) {
      rows.push({
        ...row,
        fileName: item.ref.fileName || "-",
      });
    }
  }
  return rows;
});

const evidenceImages = computed(() => {
  const rows: Array<{ url: string; fileName: string; location: string }> = [];
  for (const item of evidenceItems.value) {
    for (const url of item.imageUrls || []) {
      rows.push({
        url,
        fileName: item.ref.fileName || "-",
        location: item.ref.location || "該当箇所",
      });
    }
  }
  return rows;
});

function extractSourceRefs(text: string): SourceRef[] {
  const refs: SourceRef[] = [];
  const seen = new Set<string>();
  const re = /\[\[SRC\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^\]]*)\]\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const index = (m[1] || "").trim();
    const fileName = (m[2] || "").trim();
    const fileMd5 = (m[3] || "").trim();
    const chunkId = (m[4] || "").trim();
    const page = (m[5] || "").trim();
    const sheet = (m[6] || "").trim();
    const locationParts: string[] = [];
    if (page) locationParts.push(`page=${page}`);
    if (sheet) locationParts.push(`sheet=${sheet}`);
    const location = locationParts.length ? locationParts.join(" / ") : "該当箇所";
    if (!fileMd5) continue;
    const dedupKey = `${fileMd5}::${chunkId}::${page}::${sheet}`;
    if (seen.has(dedupKey)) continue;
    seen.add(dedupKey);
    refs.push({ index, fileName, fileMd5, chunkId, page, sheet, location });
  }
  return refs;
}

function stripSourceTags(text: string): string {
  let out = text.replace(/\n?\[\[SRC\|[^\]]+\]\]/g, "");
  out = out.replace(/\n*根拠（システム引用）[\s\S]*$/m, "");
  out = out.replace(/\n*根拠\s*\(システム引用\)\s*[\s\S]*$/m, "");
  return out.trimEnd();
}

async function openEvidencePanel(content: string) {
  const refs = extractSourceRefs(content);
  if (!refs.length) {
    ElMessage.warning("表示可能な証拠がありません");
    return;
  }
  evidenceDialogVisible.value = true;
  evidenceLoading.value = true;
  evidenceActiveTab.value = "summary";
  evidenceItems.value = [];
  try {
    const dedup = new Set<string>();
    const tasks: Array<Promise<EvidenceItem | null>> = [];
    for (const refItem of refs) {
      const key = `${refItem.fileMd5}::${refItem.chunkId}::${refItem.page}::${refItem.sheet}`;
      if (dedup.has(key)) continue;
      dedup.add(key);
      tasks.push(
        getSourceDetail({
          fileMd5: refItem.fileMd5,
          chunkId: refItem.chunkId,
          page: refItem.page,
          sheet: refItem.sheet,
          size: 10,
        })
          .then((resp) => {
            const rawOriginalUrl = resp.data?.originalUrl || "";
            const rawImageUrls = resp.data?.imageUrls || [];
            const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
            const withToken = (url: string) => {
              if (!url || !tokenQuery) return url;
              return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
            };
            return {
              ref: refItem,
              previewRows: (resp.data?.previewRows || []) as EsPreviewItem[],
              originalUrl: withToken(rawOriginalUrl),
              imageUrls: rawImageUrls.map((u) => withToken(u)),
            };
          })
          .catch(() => null),
      );
    }
    const results = await Promise.all(tasks);
    evidenceItems.value = results.filter((x): x is EvidenceItem => !!x);
    if (!evidenceItems.value.length) {
      ElMessage.warning("証拠データを取得できませんでした");
    }
  } finally {
    evidenceLoading.value = false;
  }
}

async function openGlobalEvidencePanel() {
  globalEvidenceDialogVisible.value = true;
  globalEvidenceLoading.value = true;
  globalEvidenceActiveTab.value = "files";
  globalEvidenceFiles.value = [];
  globalStructuredRows.value = [];
  globalImageRows.value = [];
  try {
    const listResp = await getUserUploadedFiles();
    const files = (listResp.data || []) as UploadedFileInfo[];
    globalEvidenceFiles.value = files;
    const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
    const withToken = (url: string) => {
      if (!url || !tokenQuery) return url;
      return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
    };
    const tasks = files.slice(0, 20).map(async (file) => {
      const md5 = file.fileMd5;
      const [esResp, srcResp] = await Promise.all([
        getEsPreview(md5, 12).catch(() => ({ data: [] as EsPreviewItem[] })),
        getSourceDetail({ fileMd5: md5, size: 12 }).catch(() => ({ data: { imageUrls: [] as string[] } })),
      ]);
      const rows = (esResp.data || []) as EsPreviewItem[];
      for (const row of rows) {
        globalStructuredRows.value.push({
          ...row,
          fileName: file.fileName,
        });
      }
      const imageUrls = (srcResp.data?.imageUrls || []) as string[];
      for (const url of imageUrls) {
        globalImageRows.value.push({
          fileName: file.fileName,
          url: withToken(url),
        });
      }
    });
    await Promise.all(tasks);
  } catch {
    ElMessage.error("全体証拠データの取得に失敗しました");
  } finally {
    globalEvidenceLoading.value = false;
  }
}

async function openSource(refItem: SourceRef) {
  sourceDialogVisible.value = true;
  sourceLoading.value = true;
  sourceDialogTitle.value = `${refItem.fileName} / ${refItem.location}`;
  sourcePreviewRows.value = [];
  sourceOriginalUrl.value = "";
  sourceImageUrls.value = [];
  try {
    const resp = await getSourceDetail({
      fileMd5: refItem.fileMd5,
      chunkId: refItem.chunkId,
      page: refItem.page,
      sheet: refItem.sheet,
      size: 10,
    });
    sourcePreviewRows.value = (resp.data?.previewRows || []) as EsPreviewItem[];
    const rawOriginalUrl = resp.data?.originalUrl || "";
    const rawImageUrls = resp.data?.imageUrls || [];
    const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
    const withToken = (url: string) => {
      if (!url || !tokenQuery) return url;
      return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
    };
    sourceOriginalUrl.value = withToken(rawOriginalUrl);
    sourceImageUrls.value = rawImageUrls.map((u) => withToken(u));
  } catch (e) {
    ElMessage.error("根拠プレビューの取得に失敗しました");
  } finally {
    sourceLoading.value = false;
  }
}

function wsUrl() {
  const resolvedHost = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
  const fallbackBase = `${window.location.protocol === "https:" ? "wss" : "ws"}://${resolvedHost}:8000`;
  const base = (import.meta.env.VITE_WS_BASE_URL as string) || fallbackBase;
  return `${base}/api/v1/chat?token=${encodeURIComponent(auth.token)}`;
}

function connect() {
  if (!auth.token) {
    ElMessage.warning("先にログインしてください");
    return;
  }
  if ((wsRef.value && connected.value) || connecting.value) {
    return;
  }
  connecting.value = true;
  const ws = new WebSocket(wsUrl());
  wsRef.value = ws;

  ws.onopen = () => {
  };

  ws.onclose = (event) => {
    connecting.value = false;
    connected.value = false;
    wsRef.value = null;
    if (event.code === 1008) {
      ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
    }
  };

  ws.onerror = () => {
    connecting.value = false;
    connected.value = false;
    ElMessage.error("WebSocket 接続エラー");
  };

  ws.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "ping") {
        ws.send(JSON.stringify({ type: "pong" }));
        return;
      }
      if (data.type === "connected") {
        connecting.value = false;
        connected.value = true;
        ElMessage.success("WebSocket 接続完了");
        return;
      }
      if (data.error) {
        ElMessage.error(data.error);
        return;
      }
      if (typeof data.chunk === "string") {
        if (pendingAssistantIndex.value === null) {
          messages.value.push({ role: "assistant", content: data.chunk });
          pendingAssistantIndex.value = messages.value.length - 1;
        } else {
          messages.value[pendingAssistantIndex.value].content += data.chunk;
        }
        await scrollBottom();
      }
      if (data.type === "completion") {
        pendingAssistantIndex.value = null;
      }
    } catch {
      // ignore non-json frames
    }
  };
}

function disconnect() {
  if (wsRef.value) {
    wsRef.value.close();
    wsRef.value = null;
  }
  connecting.value = false;
  connected.value = false;
}

function sendMessage() {
  const text = inputText.value.trim();
  if (!text) {
    return;
  }
  if (!auth.token) {
    ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
    return;
  }
  if (!wsRef.value || !connected.value) {
    connect();
    ElMessage.warning("接続中です。少し待ってから送信してください。");
    return;
  }
  messages.value.push({ role: "user", content: text });
  wsRef.value.send(text);
  inputText.value = "";
  pendingAssistantIndex.value = null;
  void scrollBottom();
}

async function scrollBottom() {
  await nextTick();
  if (messagesBox.value) {
    messagesBox.value.scrollTop = messagesBox.value.scrollHeight;
  }
}

onBeforeUnmount(() => {
  disconnect();
});

onMounted(() => {
  if (!profile.loaded) {
    void profile.refreshFromServer().catch(() => undefined);
  }
  if (auth.token) {
    connect();
  }
});
</script>

<style scoped>
.chat-page {
  height: calc(100vh - 64px);
}

.chat-card {
  height: 100%;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
}

.chat-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.messages {
  height: calc(100vh - 320px);
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  background: #f9fafb;
}

.msg-row {
  display: flex;
  margin-bottom: 10px;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 70%;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
}

.msg-row.user .bubble {
  background: #dbeafe;
  border-color: #bfdbfe;
}

.role {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

.source-links {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #d1d5db;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.source-actions {
  margin-bottom: 2px;
}

.source-title {
  font-size: 12px;
  color: #6b7280;
}

.preview-row {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
  background: #f9fafb;
}

.preview-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.preview-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.input-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
}

.structured-table-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}

.evidence-images {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}

.evidence-image-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  background: #f9fafb;
}

.evidence-image {
  max-width: 100%;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
</style>
