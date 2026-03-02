<template>
  <el-container style="height: 100%">
    <el-header class="header">
      <div class="brand">AI Knowledge Base</div>
      <div class="actions">
        <el-tag v-if="profile.selectedName" type="success" effect="plain">{{ profile.selectedName }}</el-tag>
        <el-tooltip v-if="accessSummary" :content="accessTooltip" placement="bottom">
          <el-tag type="info" effect="plain" class="access-tag">{{ accessSummary }}</el-tag>
        </el-tooltip>
        <span class="user">{{ auth.username || "未ログイン" }}</span>
        <el-button type="danger" link @click="logout">ログアウト</el-button>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="aside">
        <el-menu :default-active="activePath" router>
          <el-menu-item index="/upload">ドキュメントアップロード</el-menu-item>
          <el-menu-item index="/chat">ナレッジQ&A</el-menu-item>
          <el-menu-item index="/eval">評価センター</el-menu-item>
          <el-menu-item index="/structured">全体構造化データ</el-menu-item>
          <el-menu-item index="/intent-keywords">意図キーワード設定</el-menu-item>
          <slot name="menu-extra" />
        </el-menu>
      </el-aside>
      <el-main>
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useProfileStore } from "../stores/profile";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const profile = useProfileStore();
const activePath = computed(() => route.path);
const visibleOrgTags = computed(() =>
  (auth.orgTags || []).filter((x) => x && !x.startsWith("PRIVATE_"))
);
const accessSummary = computed(() => {
  const primary = (auth.primaryOrg || "").trim();
  const tags = visibleOrgTags.value;
  if (!primary && !tags.length) return "";
  const head = primary ? `権限: 主組織 ${primary}` : "権限: 主組織 未設定";
  const list = tags.length ? ` / 所属: ${tags.join(", ")}` : "";
  return `${head}${list}`;
});
const accessTooltip = computed(() => {
  const primary = (auth.primaryOrg || "").trim() || "未設定";
  const tags = visibleOrgTags.value.length ? visibleOrgTags.value.join(", ") : "なし";
  return `主組織: ${primary}\n所属組織: ${tags}`;
});

function logout() {
  auth.logout();
  router.push("/login");
}

onMounted(() => {
  void auth.refreshUserAccessInfo();
});
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.brand {
  font-size: 16px;
  font-weight: 700;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.access-tag {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user {
  color: #374151;
}

.aside {
  border-right: 1px solid #e5e7eb;
  background: #fff;
}

</style>
