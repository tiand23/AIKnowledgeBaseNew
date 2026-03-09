<template>
  <AppLayout>
    <div class="page-wrap">
      <el-card>
        <template #header>
          <div class="header">評価センター</div>
        </template>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="オンライン評価（自動）" name="online">
            <el-alert
              type="info"
              show-icon
              :closable="false"
              title="入力：期間のみ。出力：システムが自動集計した結果。"
              class="hint"
            />

            <el-row :gutter="12" class="toolbar">
              <el-col :xs="24" :md="8">
                <el-select v-model="onlineDays" style="width: 100%" placeholder="期間">
                  <el-option :value="1" label="直近1日" />
                  <el-option :value="7" label="直近7日" />
                  <el-option :value="30" label="直近30日" />
                </el-select>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-input v-model="onlineProfile" placeholder="シナリオ絞り込み（任意）例: design" clearable />
              </el-col>
              <el-col :xs="24" :md="8" class="actions">
                <el-button type="primary" :loading="loadingOnline" @click="loadOnlineSummary">評価結果を表示</el-button>
              </el-col>
            </el-row>

            <div v-if="!onlineSummary" class="muted">「評価結果を表示」を押すとオンライン評価を確認できます。</div>
            <div v-else>
              <el-row :gutter="12" class="cards">
                <el-col :xs="12" :md="6"><el-statistic title="総質問数" :value="onlineSummary.totalQuestions" /></el-col>
                <el-col :xs="12" :md="6"><el-statistic title="回答成功" :value="onlineSummary.successCount" /></el-col>
                <el-col :xs="12" :md="6"><el-statistic title="根拠不足" :value="onlineSummary.noEvidenceCount" /></el-col>
                <el-col :xs="12" :md="6"><el-statistic title="エラー件数" :value="onlineSummary.errorCount" /></el-col>
              </el-row>

              <el-row :gutter="12" class="cards top12">
                <el-col :xs="12" :md="6">
                  <el-statistic title="検索ヒット率（自動）" :value="pct(onlineSummary.retrievalHitRate)" suffix="%" />
                </el-col>
                <el-col :xs="12" :md="6">
                  <el-statistic title="根拠付き率（自動）" :value="pct(onlineSummary.withSourcesRate)" suffix="%" />
                </el-col>
                <el-col :xs="12" :md="6">
                  <el-statistic title="平均応答時間" :value="Math.round(onlineSummary.avgLatencyMs)" suffix="ms" />
                </el-col>
                <el-col :xs="12" :md="6">
                  <el-statistic title="P95応答時間" :value="Math.round(onlineSummary.p95LatencyMs)" suffix="ms" />
                </el-col>
              </el-row>

              <el-alert
                type="warning"
                show-icon
                :closable="false"
                title="注記：Faithfulness / Completeness はアノテーション付きデータが必要です。現時点では自動算出可能な指標を表示します。"
                class="top12"
              />

              <el-row :gutter="12" class="top12">
                <el-col :xs="24" :lg="12">
                  <el-card shadow="never" class="sub-card">
                    <template #header><div>意図別内訳</div></template>
                    <el-table :data="onlineSummary.intentStats" border size="small">
                      <el-table-column prop="intent" label="intent" min-width="150" />
                      <el-table-column prop="count" label="count" width="100" />
                    </el-table>
                  </el-card>
                </el-col>
                <el-col :xs="24" :lg="12">
                  <el-card shadow="never" class="sub-card">
                    <template #header><div>日次推移</div></template>
                    <el-table :data="onlineSummary.dailyStats" border size="small">
                      <el-table-column prop="date" label="日付" width="120" />
                      <el-table-column prop="total" label="合計" width="80" />
                      <el-table-column prop="success" label="成功" width="80" />
                      <el-table-column prop="noEvidence" label="根拠不足" width="90" />
                      <el-table-column prop="error" label="エラー" width="80" />
                      <el-table-column prop="avgLatencyMs" label="平均応答時間(ms)" min-width="120" />
                    </el-table>
                  </el-card>
                </el-col>
              </el-row>

              <el-card shadow="never" class="sub-card top12">
                <template #header><div>質問样本（根拠不足/エラー）</div></template>
                <el-table :data="onlineSummary.questionSamples" border size="small">
                  <el-table-column prop="createdAt" label="時刻" min-width="160" />
                  <el-table-column prop="status" label="状態" width="110" />
                  <el-table-column prop="intent" label="intent" width="130" />
                  <el-table-column prop="question" label="質問" min-width="320" show-overflow-tooltip />
                </el-table>
              </el-card>
            </div>
          </el-tab-pane>

          <el-tab-pane label="オフライン評価（履歴）" name="offline">
            <el-alert
              type="info"
              show-icon
              :closable="false"
              title="入力：Runを選択。出力：当該Runの指標/カバレッジ/合格率。"
              class="hint"
            />

            <el-row :gutter="12" class="toolbar">
              <el-col :xs="24" :md="8">
                <el-select v-model="runStatusFilter" style="width: 100%" clearable placeholder="状態过滤">
                  <el-option value="running" label="running" />
                  <el-option value="done" label="done" />
                  <el-option value="failed" label="failed" />
                </el-select>
              </el-col>
              <el-col :xs="24" :md="8">
                <el-input-number v-model="runLimit" :min="1" :max="200" style="width: 100%" />
              </el-col>
              <el-col :xs="24" :md="8" class="actions">
                <el-button type="primary" :loading="loadingRuns" @click="loadRuns">Run一覧を更新</el-button>
              </el-col>
            </el-row>

            <el-table :data="runs" border size="small" @row-click="onRowClick" style="width: 100%">
              <el-table-column prop="runId" label="runId" width="90" />
              <el-table-column prop="runName" label="runName" min-width="220" />
              <el-table-column prop="status" label="status" width="110" />
              <el-table-column prop="env" label="env" width="100" />
              <el-table-column prop="metricsCount" label="metrics" width="90" />
              <el-table-column prop="casesCount" label="cases" width="80" />
              <el-table-column prop="coverageCount" label="coverage" width="90" />
            </el-table>

            <el-divider />
            <div class="table-head">Run詳細</div>
            <div v-if="!summary" class="muted">上のRun行をクリックすると詳細を表示します</div>
            <div v-else>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="runId">{{ summary.run.runId }}</el-descriptions-item>
                <el-descriptions-item label="status">{{ summary.run.status }}</el-descriptions-item>
                <el-descriptions-item label="name">{{ summary.run.runName }}</el-descriptions-item>
                <el-descriptions-item label="env">{{ summary.run.env || "-" }}</el-descriptions-item>
                <el-descriptions-item label="cases">{{ summary.caseStats.total }}</el-descriptions-item>
                <el-descriptions-item label="passed">{{ summary.caseStats.passed }}</el-descriptions-item>
                <el-descriptions-item label="passRate">{{ (summary.caseStats.passRate * 100).toFixed(2) }}%</el-descriptions-item>
                <el-descriptions-item label="git">{{ summary.run.gitCommit || "-" }}</el-descriptions-item>
              </el-descriptions>

              <el-row :gutter="12" class="top12">
                <el-col :xs="24" :lg="12">
                  <el-card shadow="never" class="sub-card">
                    <template #header><div>指標</div></template>
                    <el-table :data="summary.metrics" border size="small">
                      <el-table-column prop="metricKey" label="key" min-width="170" />
                      <el-table-column prop="metricValue" label="value" width="100" />
                      <el-table-column prop="threshold" label="threshold" width="110" />
                      <el-table-column prop="passed" label="passed" width="90" />
                    </el-table>
                  </el-card>
                </el-col>
                <el-col :xs="24" :lg="12">
                  <el-card shadow="never" class="sub-card">
                    <template #header><div>資産カバレッジ</div></template>
                    <el-table :data="summary.coverage" border size="small">
                      <el-table-column prop="assetType" label="assetType" min-width="140" />
                      <el-table-column prop="totalCount" label="total" width="90" />
                      <el-table-column prop="indexedCount" label="indexed" width="100" />
                      <el-table-column prop="coverageRate" label="coverage" width="100" />
                    </el-table>
                  </el-card>
                </el-col>
              </el-row>
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
import { getOnlineEvalSummary, getEvalRunSummary, listEvalRuns } from "../api/eval";
import type { EvalOnlineSummaryData, EvalRunListItem, EvalRunSummaryData } from "../types/api";

const activeTab = ref("online");

const onlineDays = ref(7);
const onlineProfile = ref("");
const loadingOnline = ref(false);
const onlineSummary = ref<EvalOnlineSummaryData | null>(null);

const runStatusFilter = ref<string | undefined>(undefined);
const runLimit = ref(30);
const loadingRuns = ref(false);
const runs = ref<EvalRunListItem[]>([]);
const summary = ref<EvalRunSummaryData | null>(null);

function pct(v: number) {
  return Math.round((Number(v || 0) * 10000)) / 100;
}

async function loadOnlineSummary() {
  loadingOnline.value = true;
  try {
    const resp = await getOnlineEvalSummary({
      days: onlineDays.value,
      profile: onlineProfile.value.trim() || undefined
    });
    onlineSummary.value = resp.data;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "オンライン評価の取得に失敗しました");
  } finally {
    loadingOnline.value = false;
  }
}

async function loadRuns() {
  loadingRuns.value = true;
  try {
    const resp = await listEvalRuns({
      limit: runLimit.value,
      status: runStatusFilter.value || undefined
    });
    runs.value = resp.data || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "Run一覧の取得に失敗しました");
  } finally {
    loadingRuns.value = false;
  }
}

async function onRowClick(row: EvalRunListItem) {
  try {
    const resp = await getEvalRunSummary(row.runId);
    summary.value = resp.data;
  } catch (e: any) {
    summary.value = null;
    ElMessage.error(e?.response?.data?.detail || e?.message || "Run詳細の取得に失敗しました");
  }
}

onMounted(() => {
  void loadOnlineSummary();
  void loadRuns();
});
</script>

<style scoped>
.page-wrap {
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  font-size: 18px;
  font-weight: 700;
}

.hint {
  margin-bottom: 14px;
}

.toolbar {
  margin-bottom: 12px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cards {
  margin-top: 8px;
}

.top12 {
  margin-top: 12px;
}

.sub-card {
  margin-bottom: 12px;
}

.table-head {
  font-weight: 600;
  margin-bottom: 8px;
}

.muted {
  color: #6b7280;
}
</style>
