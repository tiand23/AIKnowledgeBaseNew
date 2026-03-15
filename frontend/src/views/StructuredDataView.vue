<template>
  <AppLayout>
    <div class="page-wrap">
      <el-card>
        <template #header>
          <div class="header-row">
            <div>
              <div class="title">全体構造化データ</div>
              <div class="subtitle">新しい文書構造レイヤーに合わせて、原生単元・語義 block・父/子 chunk・visual pages・画像証跡を確認できます。</div>
            </div>
            <el-button type="primary" :loading="overviewLoading || detailLoading" @click="refreshAll">更新</el-button>
          </div>
        </template>

        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="この画面は DB の新構造を直接確認するための運用ビューです。ファイルを選ぶと、document_units / semantic_blocks / parent_chunks / child_chunks / visual_pages / images を表示します。"
          class="hint"
        />

        <div class="summary-strip">
          <div class="summary-card">
            <div class="summary-label">文書数</div>
            <div class="summary-value">{{ overviewRows.length }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">原生単元</div>
            <div class="summary-value">{{ totalDocumentUnits }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">語義 block</div>
            <div class="summary-value">{{ totalSemanticBlocks }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">子 chunk</div>
            <div class="summary-value">{{ totalChildChunks }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">visual page</div>
            <div class="summary-value">{{ totalVisualPages }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">visual embedding</div>
            <div class="summary-value">{{ totalVisualEmbeddings }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">visual index</div>
            <div class="summary-value">{{ totalVisualIndexed }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">画像証跡</div>
            <div class="summary-value">{{ totalImages }}</div>
          </div>
        </div>

        <div class="main-layout">
          <el-card shadow="never" class="inner-card left-panel">
              <template #header>
                <div class="panel-header">
                  <span>文書一覧</span>
                  <span class="panel-subtext">クリックすると右側に詳細を表示します。</span>
                </div>
              </template>
              <el-table
                :data="overviewRows"
                size="small"
                border
                max-height="640"
                highlight-current-row
                :current-row-key="selectedFileMd5"
                row-key="fileMd5"
                @current-change="handleCurrentChange"
                @row-click="handleRowClick"
              >
                <el-table-column prop="fileName" label="文書名" min-width="220" show-overflow-tooltip />
                <el-table-column prop="kbProfile" label="シナリオ" width="120" />
                <el-table-column prop="documentUnitCount" label="unit" width="76" />
                <el-table-column prop="semanticBlockCount" label="block" width="78" />
                <el-table-column prop="parentChunkCount" label="parent" width="84" />
                <el-table-column prop="childChunkCount" label="child" width="76" />
                <el-table-column prop="visualPageCount" label="visual" width="76" />
                <el-table-column prop="imageBlockCount" label="image" width="76" />
              </el-table>
          </el-card>

          <el-card shadow="never" class="inner-card right-panel">
              <template #header>
                <div class="panel-header">
                  <span>選択中の文書</span>
                  <span class="panel-subtext" v-if="detailLoading">読み込み中...</span>
                </div>
              </template>

              <div v-if="!selectedFile" class="empty">左側から文書を選択してください。</div>

              <div v-else>
                <div class="file-meta">
                  <div class="file-title">{{ selectedFile.fileName }}</div>
                  <div class="file-tags">
                    <el-tag size="small" effect="plain">シナリオ: {{ selectedFile.kbProfile || "-" }}</el-tag>
                    <el-tag size="small" effect="plain">組織: {{ selectedFile.orgTagName || "-" }}</el-tag>
                    <el-tag size="small" :type="selectedFile.isPublic ? 'success' : 'info'" effect="light">
                      {{ selectedFile.isPublic ? "公開" : "非公開" }}
                    </el-tag>
                    <el-link v-if="detail.originalUrl" :href="withToken(detail.originalUrl)" target="_blank" type="primary">
                      原ファイルを開く
                    </el-link>
                  </div>
                </div>

                <div class="quality-summary">
                  <el-tag type="success" effect="light">accepted {{ selectedFile.acceptedBlockCount }}</el-tag>
                  <el-tag type="warning" effect="light">weak {{ selectedFile.weakBlockCount }}</el-tag>
                  <el-tag type="danger" effect="light">rejected {{ selectedFile.rejectedBlockCount }}</el-tag>
                  <el-tag effect="plain">visual embedding {{ selectedFile.visualEmbeddingCount }}</el-tag>
                  <el-tag effect="plain">visual index {{ selectedFile.visualIndexedCount }}</el-tag>
                </div>

                <el-tabs v-model="activeTab">
                  <el-tab-pane label="原生単元" name="units">
                    <div v-if="!detail.documentUnits.length" class="empty">document_units がありません。</div>
                    <el-table v-else :data="detail.documentUnits" size="small" border max-height="520">
                      <el-table-column prop="unitType" label="type" width="90" />
                      <el-table-column prop="unitKey" label="unit key" min-width="180" show-overflow-tooltip />
                      <el-table-column prop="unitName" label="name" min-width="160" show-overflow-tooltip />
                      <el-table-column prop="unitOrder" label="order" width="80" />
                      <el-table-column prop="page" label="page" width="80" />
                      <el-table-column prop="sheet" label="sheet" min-width="140" show-overflow-tooltip />
                      <el-table-column prop="section" label="section" min-width="140" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>

                  <el-tab-pane label="語義 block" name="blocks">
                    <div v-if="!detail.semanticBlocks.length" class="empty">semantic_blocks がありません。</div>
                    <el-table v-else :data="detail.semanticBlocks" size="small" border max-height="520">
                      <el-table-column prop="blockIndex" label="idx" width="72" />
                      <el-table-column prop="blockType" label="type" min-width="120" show-overflow-tooltip />
                      <el-table-column prop="sourceParser" label="parser" min-width="120" show-overflow-tooltip />
                      <el-table-column label="quality" width="120">
                        <template #default="{ row }">
                          <el-tag size="small" :type="qualityTagType(row.qualityStatus)" effect="light">
                            {{ row.qualityStatus }} / {{ row.qualityScore }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="sheet" label="sheet" min-width="120" show-overflow-tooltip />
                      <el-table-column prop="page" label="page" width="72" />
                      <el-table-column prop="rowNo" label="row" width="72" />
                      <el-table-column prop="textPreview" label="内容" min-width="260" show-overflow-tooltip />
                      <el-table-column label="画像" width="88">
                        <template #default="{ row }">
                          <el-link v-if="row.imageUrl" :href="withToken(row.imageUrl)" target="_blank" type="primary">
                            あり
                          </el-link>
                          <span v-else>-</span>
                        </template>
                      </el-table-column>
                    </el-table>
                  </el-tab-pane>

                  <el-tab-pane label="父chunk" name="parent">
                    <div v-if="!detail.parentChunks.length" class="empty">parent_chunks がありません。</div>
                    <el-table v-else :data="detail.parentChunks" size="small" border max-height="520">
                      <el-table-column prop="parentChunkId" label="parent id" width="90" />
                      <el-table-column prop="documentUnitKey" label="unit key" min-width="160" show-overflow-tooltip />
                      <el-table-column prop="chunkType" label="type" min-width="110" show-overflow-tooltip />
                      <el-table-column label="quality" width="120">
                        <template #default="{ row }">
                          <el-tag size="small" :type="qualityTagType(row.qualityStatus)" effect="light">
                            {{ row.qualityStatus }} / {{ row.qualityScore }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="textPreview" label="内容" min-width="320" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>

                  <el-tab-pane label="子chunk" name="child">
                    <div v-if="!detail.childChunks.length" class="empty">child_chunks がありません。</div>
                    <el-table v-else :data="detail.childChunks" size="small" border max-height="520">
                      <el-table-column prop="childChunkId" label="child id" width="84" />
                      <el-table-column prop="parentChunkId" label="parent" width="84" />
                      <el-table-column prop="documentUnitKey" label="unit key" min-width="150" show-overflow-tooltip />
                      <el-table-column prop="chunkType" label="type" min-width="110" show-overflow-tooltip />
                      <el-table-column label="quality" width="120">
                        <template #default="{ row }">
                          <el-tag size="small" :type="qualityTagType(row.qualityStatus)" effect="light">
                            {{ row.qualityStatus }} / {{ row.qualityScore }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column label="neighbor" width="120">
                        <template #default="{ row }">
                          {{ row.neighborPrevId ?? "-" }} / {{ row.neighborNextId ?? "-" }}
                        </template>
                      </el-table-column>
                      <el-table-column prop="textPreview" label="内容" min-width="260" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>

                  <el-tab-pane label="画像証跡" name="images">
                    <div v-if="!detail.images.length" class="empty">画像証跡がありません。</div>
                    <div v-else class="image-grid">
                      <div v-for="(img, idx) in detail.images" :key="`img-${idx}`" class="image-card">
                        <div class="image-meta">
                          <div>sheet: {{ img.sheet || "-" }}</div>
                          <div>page: {{ img.page || "-" }}</div>
                          <div>parser: {{ img.sourceParser || "-" }}</div>
                          <div>match: {{ img.matchMode || "-" }} / {{ img.matchConfidence ?? "-" }}</div>
                        </div>
                        <a :href="withToken(img.imageUrl)" target="_blank">
                          <img :src="withToken(img.imageUrl)" alt="structured evidence image" class="image" />
                        </a>
                      </div>
                    </div>
                  </el-tab-pane>

                  <el-tab-pane label="Visual Pages" name="visualPages">
                    <div v-if="!detail.visualPages.length" class="empty">visual_pages がありません。</div>
                    <div v-else class="image-grid">
                      <div v-for="(img, idx) in detail.visualPages" :key="`visual-${idx}`" class="image-card">
                        <div class="image-meta">
                          <div>label: {{ img.pageLabel || "-" }}</div>
                          <div>unit: {{ img.unitType || "-" }} / {{ img.documentUnitId ?? "-" }}</div>
                          <div>sheet: {{ img.sheet || "-" }}</div>
                          <div>page: {{ img.page || "-" }}</div>
                          <div>render: {{ img.renderSource || "-" }} / {{ img.renderVersion || "-" }}</div>
                          <div>quality: {{ img.qualityStatus || "-" }}</div>
                          <div>embedding: {{ img.visualEmbeddingStatus || "-" }}</div>
                          <div>indexed: {{ img.visualIndexed ? "yes" : "no" }}</div>
                          <div>provider: {{ img.visualEmbeddingProvider || "-" }}</div>
                          <div>model: {{ img.visualEmbeddingModel || "-" }}</div>
                          <div v-if="img.visualEmbeddingDim">dim: {{ img.visualEmbeddingDim }}</div>
                          <div v-if="img.visualIndexDocId">doc: {{ img.visualIndexDocId }}</div>
                          <div v-if="img.visualEmbeddingError" class="embedding-error">note: {{ img.visualEmbeddingError }}</div>
                        </div>
                        <a :href="withToken(img.imageUrl)" target="_blank">
                          <img :src="withToken(img.imageUrl)" alt="visual page image" class="image" />
                        </a>
                      </div>
                    </div>
                  </el-tab-pane>

                  <el-tab-pane label="Graph" name="graph">
                    <div v-if="!detail.relationNodes.length && !detail.relationEdges.length" class="empty">relation graph がありません。</div>
                    <div v-else class="graph-pane">
                      <div class="graph-canvas-card">
                        <div class="graph-canvas-header">
                          <div>
                            <div class="graph-title">Graph View</div>
                            <div class="graph-subtitle">Neo4j のように、ページ・コンポーネント・遷移関係を俯瞰できます。ノードをクリックすると下の一覧も絞り込まれます。</div>
                          </div>
                          <el-button v-if="selectedGraphNodeId !== null" size="small" plain @click="selectedGraphNodeId = null">
                            絞り込み解除
                          </el-button>
                        </div>

                        <div class="graph-legend">
                          <span class="legend-item">
                            <span class="legend-dot legend-component"></span>
                            component
                          </span>
                          <span class="legend-item">
                            <span class="legend-dot legend-page"></span>
                            page
                          </span>
                          <span class="legend-item">
                            <span class="legend-dot legend-flow"></span>
                            flow
                          </span>
                          <span class="legend-item">
                            <span class="legend-dot legend-other"></span>
                            other
                          </span>
                        </div>

                        <div class="graph-canvas-wrap">
                          <svg
                            v-if="graphCanvasNodes.length"
                            class="graph-canvas"
                            :viewBox="`0 0 ${GRAPH_CANVAS_WIDTH} ${GRAPH_CANVAS_HEIGHT}`"
                            preserveAspectRatio="xMidYMid meet"
                          >
                            <defs>
                              <marker
                                id="graph-arrow"
                                markerWidth="10"
                                markerHeight="10"
                                refX="9"
                                refY="5"
                                orient="auto"
                                markerUnits="strokeWidth"
                              >
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
                              </marker>
                            </defs>

                            <g v-for="edge in graphCanvasEdges" :key="`edge-${edge.edgeId}`">
                              <line
                                :x1="edge.x1"
                                :y1="edge.y1"
                                :x2="edge.x2"
                                :y2="edge.y2"
                                :class="['graph-edge-line', { 'graph-edge-line--active': edge.isActive }]"
                                marker-end="url(#graph-arrow)"
                              />
                              <text
                                v-if="edge.label"
                                :x="edge.labelX"
                                :y="edge.labelY"
                                class="graph-edge-label"
                              >
                                {{ edge.label }}
                              </text>
                            </g>

                            <g
                              v-for="node in graphCanvasNodes"
                              :key="`node-${node.nodeId}`"
                              class="graph-node"
                              @click="selectedGraphNodeId = node.nodeId"
                            >
                              <circle
                                :cx="node.x"
                                :cy="node.y"
                                :r="node.radius"
                                :fill="node.fill"
                                :class="['graph-node-circle', { 'graph-node-circle--active': node.isActive }]"
                              />
                              <text
                                :x="node.x"
                                :y="node.y + 4"
                                class="graph-node-label"
                              >
                                {{ node.shortLabel }}
                              </text>
                            </g>
                          </svg>
                        </div>
                      </div>

                      <div class="graph-section">
                        <div class="graph-title">Nodes</div>
                        <el-table v-if="filteredRelationNodes.length" :data="filteredRelationNodes" size="small" border max-height="220">
                          <el-table-column prop="nodeId" label="id" width="72" />
                          <el-table-column prop="nodeName" label="name" min-width="160" show-overflow-tooltip />
                          <el-table-column prop="nodeType" label="type" min-width="110" show-overflow-tooltip />
                          <el-table-column prop="page" label="page" width="72" />
                          <el-table-column prop="nodeKey" label="key" min-width="180" show-overflow-tooltip />
                          <el-table-column prop="evidenceText" label="evidence" min-width="220" show-overflow-tooltip />
                        </el-table>
                        <div v-else class="empty graph-empty">node がありません。</div>
                      </div>

                      <div class="graph-section">
                        <div class="graph-title">Edges</div>
                        <el-table v-if="filteredRelationEdges.length" :data="filteredRelationEdges" size="small" border max-height="220">
                          <el-table-column prop="edgeId" label="id" width="72" />
                          <el-table-column prop="srcNodeName" label="src" min-width="140" show-overflow-tooltip />
                          <el-table-column prop="dstNodeName" label="dst" min-width="140" show-overflow-tooltip />
                          <el-table-column prop="relationType" label="type" min-width="100" show-overflow-tooltip />
                          <el-table-column prop="page" label="page" width="72" />
                          <el-table-column prop="relationText" label="relation" min-width="160" show-overflow-tooltip />
                          <el-table-column prop="evidenceText" label="evidence" min-width="220" show-overflow-tooltip />
                        </el-table>
                        <div v-else class="empty graph-empty">edge がありません。</div>
                      </div>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </div>
          </el-card>
        </div>
      </el-card>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getStructuredDetail, getStructuredOverview } from "../api/file";
import type {
  StructuredFileDetailData,
  StructuredOverviewFileInfo,
  StructuredRelationEdgeItem,
  StructuredRelationNodeItem,
} from "../types/api";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const activeTab = ref("units");
const overviewLoading = ref(false);
const detailLoading = ref(false);
const selectedGraphNodeId = ref<number | null>(null);
const GRAPH_CANVAS_WIDTH = 920;
const GRAPH_CANVAS_HEIGHT = 460;
const overviewRows = ref<StructuredOverviewFileInfo[]>([]);
const selectedFileMd5 = ref("");
const detail = ref<StructuredFileDetailData>({
  fileMd5: "",
  fileName: "",
  originalUrl: "",
  documentUnits: [],
  semanticBlocks: [],
  parentChunks: [],
  childChunks: [],
  visualPages: [],
  images: [],
  relationNodes: [],
  relationEdges: [],
});

const selectedFile = computed(() =>
  overviewRows.value.find((row) => row.fileMd5 === selectedFileMd5.value) || null,
);

const totalDocumentUnits = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.documentUnitCount || 0), 0),
);
const totalSemanticBlocks = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.semanticBlockCount || 0), 0),
);
const totalChildChunks = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.childChunkCount || 0), 0),
);
const totalVisualPages = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.visualPageCount || 0), 0),
);
const totalVisualEmbeddings = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.visualEmbeddingCount || 0), 0),
);
const totalVisualIndexed = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.visualIndexedCount || 0), 0),
);
const totalImages = computed(() =>
  overviewRows.value.reduce((sum, row) => sum + (row.imageBlockCount || 0), 0),
);

const graphNeighborNodeIds = computed(() => {
  if (selectedGraphNodeId.value === null) return new Set<number>();
  const ids = new Set<number>([selectedGraphNodeId.value]);
  for (const edge of detail.value.relationEdges) {
    if (edge.srcNodeId === selectedGraphNodeId.value) ids.add(edge.dstNodeId);
    if (edge.dstNodeId === selectedGraphNodeId.value) ids.add(edge.srcNodeId);
  }
  return ids;
});

const filteredRelationNodes = computed(() => {
  if (selectedGraphNodeId.value === null) return detail.value.relationNodes;
  return detail.value.relationNodes.filter((node) => graphNeighborNodeIds.value.has(node.nodeId));
});

const filteredRelationEdges = computed(() => {
  if (selectedGraphNodeId.value === null) return detail.value.relationEdges;
  return detail.value.relationEdges.filter(
    (edge) => edge.srcNodeId === selectedGraphNodeId.value || edge.dstNodeId === selectedGraphNodeId.value,
  );
});

function graphNodeFill(nodeType?: string | null) {
  const normalized = (nodeType || "").toLowerCase();
  if (normalized.includes("component")) return "#7dd3fc";
  if (normalized.includes("page")) return "#86efac";
  if (normalized.includes("flow")) return "#fca5a5";
  return "#c4b5fd";
}

function shortenLabel(label: string, max = 10) {
  return label.length > max ? `${label.slice(0, max)}…` : label;
}

const graphCanvasNodes = computed(() => {
  const nodes = detail.value.relationNodes;
  if (!nodes.length) return [];

  const degreeMap = new Map<number, number>();
  for (const node of nodes) degreeMap.set(node.nodeId, 0);
  for (const edge of detail.value.relationEdges) {
    degreeMap.set(edge.srcNodeId, (degreeMap.get(edge.srcNodeId) || 0) + 1);
    degreeMap.set(edge.dstNodeId, (degreeMap.get(edge.dstNodeId) || 0) + 1);
  }

  const sorted = [...nodes].sort((a, b) => (degreeMap.get(b.nodeId) || 0) - (degreeMap.get(a.nodeId) || 0));
  const centerX = GRAPH_CANVAS_WIDTH / 2;
  const centerY = GRAPH_CANVAS_HEIGHT / 2;
  const ringBase = 132;

  return sorted.map((node, index) => {
    const degree = degreeMap.get(node.nodeId) || 0;
    let x = centerX;
    let y = centerY;

    if (index > 0) {
      const ring = Math.floor((index - 1) / 8) + 1;
      const ringIndex = (index - 1) % 8;
      const slots = Math.min(8 * ring, Math.max(sorted.length - 1, 1));
      const angle = (Math.PI * 2 * ringIndex) / slots - Math.PI / 2;
      const radius = ringBase * ring;
      x = centerX + Math.cos(angle) * radius;
      y = centerY + Math.sin(angle) * radius;
    }

    const isActive =
      selectedGraphNodeId.value === null ? false : graphNeighborNodeIds.value.has(node.nodeId);

    return {
      ...node,
      x,
      y,
      radius: Math.max(26, Math.min(40, 24 + degree * 3)),
      fill: graphNodeFill(node.nodeType),
      shortLabel: shortenLabel(node.nodeName || node.nodeKey || String(node.nodeId)),
      isActive,
    };
  });
});

const graphCanvasEdges = computed(() => {
  if (!detail.value.relationEdges.length || !graphCanvasNodes.value.length) return [];
  const nodeMap = new Map<number, (typeof graphCanvasNodes.value)[number]>(
    graphCanvasNodes.value.map((node) => [node.nodeId, node]),
  );

  return detail.value.relationEdges
    .map((edge) => {
      const src = nodeMap.get(edge.srcNodeId);
      const dst = nodeMap.get(edge.dstNodeId);
      if (!src || !dst) return null;

      const dx = dst.x - src.x;
      const dy = dst.y - src.y;
      const len = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const ux = dx / len;
      const uy = dy / len;
      const x1 = src.x + ux * src.radius;
      const y1 = src.y + uy * src.radius;
      const x2 = dst.x - ux * dst.radius;
      const y2 = dst.y - uy * dst.radius;
      const label = edge.relationType || "";
      const isActive =
        selectedGraphNodeId.value === null
          ? false
          : edge.srcNodeId === selectedGraphNodeId.value || edge.dstNodeId === selectedGraphNodeId.value;

      return {
        ...edge,
        x1,
        y1,
        x2,
        y2,
        label,
        labelX: (x1 + x2) / 2,
        labelY: (y1 + y2) / 2 - 6,
        isActive,
      };
    })
    .filter((edge): edge is NonNullable<typeof edge> => Boolean(edge));
});

function withToken(url: string) {
  const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
  if (!url || !tokenQuery) return url;
  return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
}

function qualityTagType(status?: string | null) {
  if (status === "accepted") return "success";
  if (status === "rejected") return "danger";
  return "warning";
}

async function loadOverview() {
  overviewLoading.value = true;
  try {
    const resp = await getStructuredOverview();
    overviewRows.value = resp.data || [];
    if (!selectedFileMd5.value && overviewRows.value.length) {
      selectedFileMd5.value = overviewRows.value[0].fileMd5;
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "構造化総覧の取得に失敗しました");
  } finally {
    overviewLoading.value = false;
  }
}

async function loadDetail(fileMd5: string) {
  if (!fileMd5) return;
  detailLoading.value = true;
  try {
    const resp = await getStructuredDetail(fileMd5);
    detail.value = resp.data;
    selectedGraphNodeId.value = null;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "構造化明細の取得に失敗しました");
    detail.value = {
      fileMd5: "",
      fileName: "",
      originalUrl: "",
      documentUnits: [],
      semanticBlocks: [],
      parentChunks: [],
      childChunks: [],
      visualPages: [],
      images: [],
      relationNodes: [],
      relationEdges: [],
    };
  } finally {
    detailLoading.value = false;
  }
}

async function refreshAll() {
  await loadOverview();
  if (selectedFileMd5.value) {
    await loadDetail(selectedFileMd5.value);
  }
}

function handleCurrentChange(row?: StructuredOverviewFileInfo | null) {
  if (!row?.fileMd5 || row.fileMd5 === selectedFileMd5.value) return;
  selectedFileMd5.value = row.fileMd5;
  void loadDetail(row.fileMd5);
}

function handleRowClick(row: StructuredOverviewFileInfo) {
  handleCurrentChange(row);
}

onMounted(async () => {
  await loadOverview();
  if (selectedFileMd5.value) {
    await loadDetail(selectedFileMd5.value);
  }
});
</script>

<style scoped>
.page-wrap {
  max-width: 1680px;
  margin: 0 auto;
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.subtitle {
  margin-top: 6px;
  color: #6b7280;
  font-size: 13px;
}

.hint {
  margin-bottom: 16px;
}

.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.summary-card {
  flex: 1 1 160px;
  min-width: 160px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
  background: #f8fafc;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.summary-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.main-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(520px, 1.3fr);
  gap: 16px;
  margin-top: 8px;
}

.inner-card {
  min-height: 760px;
}

.left-panel,
.right-panel {
  width: 100%;
}

.panel-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.panel-subtext {
  color: #6b7280;
  font-size: 12px;
}

.empty {
  color: #6b7280;
  padding: 18px 0;
}

.file-meta {
  margin-bottom: 12px;
}

.file-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 8px;
}

.file-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.quality-summary {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.image-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #f9fafb;
}

.embedding-error {
  color: #b45309;
  word-break: break-word;
}

.image-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
  line-height: 1.6;
}

.image {
  max-width: 100%;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.graph-pane {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.graph-canvas-card {
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  padding: 12px;
  background:
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.12), transparent 30%),
    linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%);
}

.graph-canvas-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.graph-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.graph-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #475569;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.12);
}

.legend-component {
  background: #7dd3fc;
}

.legend-page {
  background: #86efac;
}

.legend-flow {
  background: #fca5a5;
}

.legend-other {
  background: #c4b5fd;
}

.graph-canvas-wrap {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background:
    linear-gradient(0deg, rgba(148, 163, 184, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.06) 1px, transparent 1px),
    #ffffff;
  background-size: 24px 24px, 24px 24px, auto;
}

.graph-canvas {
  display: block;
  width: 100%;
  min-width: 720px;
  height: 460px;
}

.graph-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  background: #fafafa;
}

.graph-title {
  font-size: 13px;
  font-weight: 700;
  color: #374151;
  margin-bottom: 8px;
}

.graph-empty {
  padding: 8px 0 4px;
}

.graph-edge-line {
  stroke: #94a3b8;
  stroke-width: 2;
  opacity: 0.65;
}

.graph-edge-line--active {
  stroke: #2563eb;
  stroke-width: 3;
  opacity: 1;
}

.graph-edge-label {
  font-size: 11px;
  fill: #475569;
  text-anchor: middle;
  paint-order: stroke;
  stroke: #ffffff;
  stroke-width: 4px;
  stroke-linejoin: round;
}

.graph-node {
  cursor: pointer;
}

.graph-node-circle {
  stroke: #ffffff;
  stroke-width: 3;
  filter: drop-shadow(0 4px 8px rgba(15, 23, 42, 0.12));
}

.graph-node-circle--active {
  stroke: #1d4ed8;
  stroke-width: 4;
}

.graph-node-label {
  font-size: 11px;
  font-weight: 700;
  fill: #0f172a;
  text-anchor: middle;
  pointer-events: none;
}

@media (max-width: 1100px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .header-row {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-card {
    min-width: calc(50% - 6px);
  }
}
</style>
