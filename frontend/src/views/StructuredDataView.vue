<template>
  <AppLayout>
    <div class="page-wrap">
      <el-card>
        <template #header>
          <div class="header-row">
            <div class="title">全体構造化データ</div>
            <el-button type="primary" :loading="loading" @click="loadAll">更新</el-button>
          </div>
        </template>

        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="アップロード済み文書から、全体の構造化データと画像を表示します。"
          class="hint"
        />

        <el-tabs v-model="activeTab">
          <el-tab-pane label="文書一覧" name="files">
            <el-table :data="files" size="small" border max-height="520">
              <el-table-column prop="fileName" label="文書名" min-width="240" />
              <el-table-column prop="kbProfile" label="シナリオ" width="150" />
              <el-table-column prop="vectorCount" label="vector" width="90" />
              <el-table-column prop="tableRowCount" label="table" width="90" />
              <el-table-column prop="imageBlockCount" label="image" width="90" />
              <el-table-column prop="relationEdgeCount" label="relation" width="95" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="構造化データ(全体)" name="structured">
            <div v-if="!structuredRows.length" class="empty">表示可能な構造化データがありません。</div>
            <el-table v-else :data="structuredRows" size="small" border max-height="520">
              <el-table-column prop="fileName" label="文書" min-width="220" />
              <el-table-column prop="chunkType" label="種別" min-width="120" />
              <el-table-column prop="chunkId" label="chunk" width="84" />
              <el-table-column prop="page" label="page" width="84" />
              <el-table-column prop="sheet" label="sheet" min-width="150" />
              <el-table-column prop="textPreview" label="内容" min-width="300" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="画像(全体)" name="images">
            <div v-if="!imageRows.length" class="empty">表示可能な画像がありません。</div>
            <div v-else class="image-grid">
              <div v-for="(img, idx) in imageRows" :key="`img-${idx}`" class="image-card">
                <div class="image-meta">{{ img.fileName }}</div>
                <a :href="img.url" target="_blank">
                  <img :src="img.url" alt="global evidence image" class="image" />
                </a>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getEsPreview, getSourceDetail, getUserUploadedFiles } from "../api/file";
import type { EsPreviewItem, UploadedFileInfo } from "../types/api";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const activeTab = ref("files");
const loading = ref(false);
const files = ref<UploadedFileInfo[]>([]);
const structuredRows = ref<Array<EsPreviewItem & { fileName: string }>>([]);
const imageRows = ref<Array<{ fileName: string; url: string }>>([]);

function withToken(url: string) {
  const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
  if (!url || !tokenQuery) return url;
  return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
}

async function loadAll() {
  loading.value = true;
  files.value = [];
  structuredRows.value = [];
  imageRows.value = [];
  try {
    const listResp = await getUserUploadedFiles();
    const rows = (listResp.data || []) as UploadedFileInfo[];
    files.value = rows;

    const tasks = rows.slice(0, 30).map(async (file) => {
      const md5 = file.fileMd5;
      const [esResp, srcResp] = await Promise.all([
        getEsPreview(md5, 12).catch(() => ({ data: [] as EsPreviewItem[] })),
        getSourceDetail({ fileMd5: md5, size: 12 }).catch(() => ({ data: { imageUrls: [] as string[] } })),
      ]);

      for (const r of (esResp.data || []) as EsPreviewItem[]) {
        structuredRows.value.push({ ...r, fileName: file.fileName });
      }
      for (const u of ((srcResp.data?.imageUrls || []) as string[])) {
        imageRows.value.push({ fileName: file.fileName, url: withToken(u) });
      }
    });
    await Promise.all(tasks);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "全体構造化データの取得に失敗しました");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped>
.page-wrap {
  max-width: 1400px;
  margin: 0 auto;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.hint {
  margin-bottom: 12px;
}

.empty {
  color: #6b7280;
  padding: 12px 0;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}

.image-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  background: #f9fafb;
}

.image-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.image {
  max-width: 100%;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
</style>
