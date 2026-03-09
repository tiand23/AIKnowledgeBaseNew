<template>
  <div class="register-page">
    <el-card class="register-card">
      <template #header>
        <div class="title">アカウント登録</div>
      </template>

      <el-form :model="form" label-position="top" @submit.prevent>
        <el-form-item label="ユーザー名">
          <el-input v-model="form.username" placeholder="3文字以上" />
        </el-form-item>
        <el-form-item label="メールアドレス">
          <el-input v-model="form.email" placeholder="メールアドレスを入力" />
        </el-form-item>
        <el-form-item label="パスワード">
          <el-input v-model="form.password" type="password" show-password placeholder="6文字以上" />
        </el-form-item>
        <el-form-item label="パスワード確認">
          <el-input v-model="form.confirmPassword" type="password" show-password placeholder="もう一度入力" />
        </el-form-item>
        <el-form-item label="所属組織（権限）">
          <el-select
            v-model="form.orgTags"
            multiple
            filterable
            clearable
            style="width: 100%"
            placeholder="所属組織タグを選択（任意）"
          >
            <el-option
              v-for="item in orgTagOptions"
              :key="item.tagId"
              :label="`${item.name} (${item.tagId})`"
              :value="item.tagId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="主組織">
          <el-select
            v-model="form.primaryOrg"
            clearable
            style="width: 100%"
            placeholder="主組織を選択（任意）"
          >
            <el-option
              v-for="tagId in form.orgTags"
              :key="`primary-${tagId}`"
              :label="tagId"
              :value="tagId"
            />
          </el-select>
        </el-form-item>

        <el-button type="primary" style="width: 100%" :loading="registering" @click="onRegister">
          登録してログイン
        </el-button>
      </el-form>

      <div class="bottom-link">
        すでにアカウントをお持ちですか？
        <el-button type="primary" link @click="router.push('/login')">ログインへ</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getRegisterOrgTags, register } from "../api/auth";
import { useAuthStore } from "../stores/auth";
import type { RegisterOrgTagOption } from "../types/api";

const router = useRouter();
const auth = useAuthStore();
const registering = ref(false);
const orgTagOptions = ref<RegisterOrgTagOption[]>([]);

const form = reactive({
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
  orgTags: [] as string[],
  primaryOrg: ""
});

watch(
  () => form.orgTags.slice(),
  (tags) => {
    if (form.primaryOrg && !tags.includes(form.primaryOrg)) {
      form.primaryOrg = "";
    }
  }
);

async function onRegister() {
  if (!form.username || !form.email || !form.password) {
    ElMessage.warning("登録情報をすべて入力してください");
    return;
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.warning("パスワードが一致しません");
    return;
  }

  registering.value = true;
  try {
    const resp = await register({
      username: form.username,
      email: form.email,
      password: form.password,
      orgTags: form.orgTags,
      primaryOrg: form.primaryOrg || undefined,
    });

    auth.login({
      accessToken: resp.data.access_token,
      username: resp.data.username,
      userId: resp.data.id
    });
    await auth.refreshUserAccessInfo();
    ElMessage.success("登録が完了し、自動ログインしました");
    router.push("/setup");
  } catch (err: any) {
    const status = err?.response?.status;
    const detail = err?.response?.data?.message || err?.response?.data?.detail || err?.message || "登録に失敗しました";
    ElMessage.error(status ? `登録失敗(${status}): ${detail}` : `登録失敗: ${detail}`);
  } finally {
    registering.value = false;
  }
}

async function loadRegisterOrgTags() {
  try {
    const resp = await getRegisterOrgTags();
    orgTagOptions.value = resp.data || [];
  } catch (e: any) {
    ElMessage.warning(e?.response?.data?.detail || e?.message || "組織タグ一覧の取得に失敗しました");
  }
}

onMounted(() => {
  void loadRegisterOrgTags();
});
</script>

<style scoped>
.register-page {
  width: 100%;
  min-height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #dbeafe, #eef2ff);
  padding: 24px;
}

.register-card {
  width: 520px;
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.bottom-link {
  margin-top: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #6b7280;
}
</style>
