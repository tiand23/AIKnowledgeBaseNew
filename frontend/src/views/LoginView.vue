<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="title">ナレッジベース ログイン</div>
      </template>
      <el-form :model="form" label-position="top" @submit.prevent>
        <el-form-item label="ユーザー名">
          <el-input v-model="form.username" placeholder="ユーザー名を入力" />
        </el-form-item>
        <el-form-item label="パスワード">
          <el-input v-model="form.password" type="password" show-password placeholder="パスワードを入力" />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width: 100%" @click="onLogin">
          ログイン
        </el-button>
      </el-form>
      <div class="bottom-link">
        アカウントをお持ちでないですか？
        <el-button type="primary" link @click="router.push('/register')">新規登録</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { login } from "../api/auth";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const loading = ref(false);

const form = reactive({
  username: "",
  password: ""
});

async function onLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning("ユーザー名とパスワードを入力してください");
    return;
  }
  loading.value = true;
  try {
    const resp = await login(form.username, form.password);
    auth.login({
      accessToken: resp.data.access_token,
      username: resp.data.username,
      userId: resp.data.user_id
    });
    await auth.refreshUserAccessInfo();
    ElMessage.success("ログインしました");
    router.push("/setup");
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || err?.response?.data?.detail || "ログインに失敗しました");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #dbeafe, #eef2ff);
}

.login-card {
  width: 420px;
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
