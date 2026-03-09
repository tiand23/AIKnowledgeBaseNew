<template>
  <AppLayout>
    <div class="page-wrap">
      <el-card>
        <template #header>
          <div class="header">ナレッジシナリオ初期化</div>
        </template>

        <el-alert
          type="warning"
          show-icon
          :closable="false"
          title="シナリオは作成後に変更できません。切り替える場合はデータを初期化してください。"
          class="mb-16"
        />

        <div class="grid">
          <div
            v-for="item in options"
            :key="item.profile_id"
            class="card"
            :class="{ active: selectedProfileId === item.profile_id }"
            @click="selectedProfileId = item.profile_id"
          >
            <div class="name">{{ item.name }}</div>
            <div class="desc">{{ item.description }}</div>
            <div class="examples">
              <div class="examples-title">代表的な質問</div>
              <ul>
                <li v-for="q in getExamples(item.profile_id)" :key="q">{{ q }}</li>
              </ul>
            </div>
            <el-tag v-if="selectedProfileId === item.profile_id" size="small" type="success">選択中</el-tag>
          </div>
        </div>

        <div class="actions">
          <el-button type="primary" :loading="saving" :disabled="!selectedProfileId" @click="onConfirm">
            このシナリオで開始
          </el-button>
          <el-button @click="refresh">更新</el-button>
        </div>
      </el-card>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import AppLayout from "../components/AppLayout.vue";
import { getProfileState, selectProfile } from "../api/profile";
import { useProfileStore } from "../stores/profile";
import type { ProfileOption } from "../types/api";

const router = useRouter();
const profileStore = useProfileStore();
const saving = ref(false);
const options = ref<ProfileOption[]>([]);
const selectedProfileId = ref("");

const profileExamples: Record<string, string[]> = {
  general: ["最新版の手順書はどこですか", "この用語は社内でどう定義されていますか"],
  design: ["このDB項目変更の影響範囲は", "この業務フローはどのシステム間ですか"],
  policy: ["この金額は何段階の承認が必要ですか", "どの版がこの日付で有効ですか"],
  ops: ["同様障害の過去対応は", "変更後に発生したアラートは"]
};

function getExamples(profileId: string) {
  return profileExamples[profileId] || ["このシナリオに沿って検索・回答してください"];
}

async function refresh() {
  const resp = await getProfileState();
  const data = resp.data;
  options.value = data?.options || [];
  if (data?.selected_profile) {
    const selectedName =
      data.selected_name || options.value.find((x) => x.profile_id === data.selected_profile)?.name || "";
    profileStore.setProfile(data.selected_profile, selectedName);
    ElMessage.success(`現在のシナリオ: ${selectedName || data.selected_profile}`);
    router.push("/upload");
    return;
  }
  if (!selectedProfileId.value && options.value.length > 0) {
    selectedProfileId.value = options.value[0].profile_id;
  }
}

async function onConfirm() {
  if (!selectedProfileId.value) {
    return;
  }
  saving.value = true;
  try {
    const resp = await selectProfile(selectedProfileId.value);
    const data = resp.data;
    if (!data?.selected_profile) {
      throw new Error("シナリオ保存に失敗しました");
    }
    const selectedName =
      data.selected_name || data.options.find((x) => x.profile_id === data.selected_profile)?.name || "";
    profileStore.setProfile(data.selected_profile, selectedName);
    ElMessage.success(`シナリオを確定しました: ${selectedName || data.selected_profile}`);
    router.push("/upload");
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || "シナリオ保存に失敗しました");
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void refresh();
});
</script>

<style scoped>
.header {
  font-size: 18px;
  font-weight: 700;
}

.mb-16 {
  margin-bottom: 16px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.card {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  background: #fff;
}

.card.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.name {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 6px;
}

.desc {
  color: #4b5563;
  min-height: 48px;
  margin-bottom: 8px;
}

.examples {
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 8px;
  margin-bottom: 8px;
}

.examples-title {
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
}

.examples ul {
  margin: 0;
  padding-left: 18px;
}

.examples li {
  color: #374151;
  font-size: 12px;
  line-height: 1.5;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
