<template>
  <AppLayout>
    <div class="page-wrap">
      <el-card>
        <template #header>
          <div class="header-row">
            <div class="title">意図キーワード設定</div>
            <div class="actions">
              <el-button :loading="loading" @click="loadConfig">再読み込み</el-button>
              <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
            </div>
          </div>
        </template>

        <el-alert
          type="info"
          show-icon
          :closable="false"
          class="hint"
          title="このページは、質問文をどの意図として判定するか（例：画面レイアウト、フロー、統計）を調整するための管理画面です。"
        />

        <el-descriptions border :column="1" size="small" class="hint2">
          <el-descriptions-item label="何のため？">
            ユーザー表現の揺れ（例：図/イメージ/遷移図）を吸収し、検索方向と回答精度を安定させます。
          </el-descriptions-item>
          <el-descriptions-item label="いつ変更する？">
            特定の質問が意図違いで処理される時、または新しい業務用語を追加したい時に更新してください。
          </el-descriptions-item>
          <el-descriptions-item label="変更の影響範囲">
            保存後すぐに意図判定・検索ルート・図系フォールバックに反映されます（サービス再起動不要）。
          </el-descriptions-item>
          <el-descriptions-item label="入力ルール">
            1行に1キーワード。重複は自動除去されます。空欄のみの場合は既定キーワードに戻ります。
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="updatedAt" class="muted">最終更新: {{ updatedAt }}</div>

        <el-form label-position="top" v-loading="loading" class="form">
          <el-form-item
            v-for="item in formItems"
            :key="item.key"
            :label="`${item.label} (${item.key})`"
          >
            <el-input
              v-model="item.keywordsText"
              type="textarea"
              :rows="4"
              placeholder="1行に1キーワード"
            />
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getIntentKeywordsConfig, updateIntentKeywordsConfig } from "../api/profile";

const loading = ref(false);
const saving = ref(false);
const updatedAt = ref("");
const formItems = ref<Array<{ key: string; label: string; keywordsText: string }>>([]);

function splitKeywords(text: string): string[] {
  const rows = String(text || "").split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const v = row.toLowerCase();
    if (seen.has(v)) continue;
    seen.add(v);
    out.push(v);
  }
  return out;
}

async function loadConfig() {
  loading.value = true;
  try {
    const resp = await getIntentKeywordsConfig();
    formItems.value = (resp.data?.categories || []).map((item) => ({
      key: item.key,
      label: item.label,
      keywordsText: (item.keywords || []).join("\n")
    }));
    updatedAt.value = resp.data?.updated_at || "";
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "キーワード設定の取得に失敗しました");
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  saving.value = true;
  try {
    const payload = formItems.value.map((item) => ({
      key: item.key,
      keywords: splitKeywords(item.keywordsText)
    }));
    const resp = await updateIntentKeywordsConfig(payload);
    formItems.value = (resp.data?.categories || []).map((item) => ({
      key: item.key,
      label: item.label,
      keywordsText: (item.keywords || []).join("\n")
    }));
    updatedAt.value = resp.data?.updated_at || "";
    ElMessage.success("意図キーワード設定を保存しました。");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "キーワード設定の保存に失敗しました");
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void loadConfig();
});
</script>

<style scoped>
.page-wrap {
  max-width: 1200px;
  margin: 0 auto;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.actions {
  display: flex;
  gap: 8px;
}

.hint {
  margin-bottom: 10px;
}

.hint2 {
  margin-bottom: 12px;
}

.muted {
  color: #6b7280;
  margin-bottom: 8px;
}

.form {
  margin-top: 8px;
}
</style>
