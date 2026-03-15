import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getStructuredDetail, getStructuredOverview } from "../api/file";
import { useAuthStore } from "../stores/auth";
const auth = useAuthStore();
const activeTab = ref("units");
const overviewLoading = ref(false);
const detailLoading = ref(false);
const selectedGraphNodeId = ref(null);
const GRAPH_CANVAS_WIDTH = 920;
const GRAPH_CANVAS_HEIGHT = 460;
const overviewRows = ref([]);
const selectedFileMd5 = ref("");
const detail = ref({
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
const selectedFile = computed(() => overviewRows.value.find((row) => row.fileMd5 === selectedFileMd5.value) || null);
const totalDocumentUnits = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.documentUnitCount || 0), 0));
const totalSemanticBlocks = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.semanticBlockCount || 0), 0));
const totalChildChunks = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.childChunkCount || 0), 0));
const totalVisualPages = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.visualPageCount || 0), 0));
const totalVisualEmbeddings = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.visualEmbeddingCount || 0), 0));
const totalVisualIndexed = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.visualIndexedCount || 0), 0));
const totalImages = computed(() => overviewRows.value.reduce((sum, row) => sum + (row.imageBlockCount || 0), 0));
const graphNeighborNodeIds = computed(() => {
    if (selectedGraphNodeId.value === null)
        return new Set();
    const ids = new Set([selectedGraphNodeId.value]);
    for (const edge of detail.value.relationEdges) {
        if (edge.srcNodeId === selectedGraphNodeId.value)
            ids.add(edge.dstNodeId);
        if (edge.dstNodeId === selectedGraphNodeId.value)
            ids.add(edge.srcNodeId);
    }
    return ids;
});
const filteredRelationNodes = computed(() => {
    if (selectedGraphNodeId.value === null)
        return detail.value.relationNodes;
    return detail.value.relationNodes.filter((node) => graphNeighborNodeIds.value.has(node.nodeId));
});
const filteredRelationEdges = computed(() => {
    if (selectedGraphNodeId.value === null)
        return detail.value.relationEdges;
    return detail.value.relationEdges.filter((edge) => edge.srcNodeId === selectedGraphNodeId.value || edge.dstNodeId === selectedGraphNodeId.value);
});
function graphNodeFill(nodeType) {
    const normalized = (nodeType || "").toLowerCase();
    if (normalized.includes("component"))
        return "#7dd3fc";
    if (normalized.includes("page"))
        return "#86efac";
    if (normalized.includes("flow"))
        return "#fca5a5";
    return "#c4b5fd";
}
function shortenLabel(label, max = 10) {
    return label.length > max ? `${label.slice(0, max)}…` : label;
}
const graphCanvasNodes = computed(() => {
    const nodes = detail.value.relationNodes;
    if (!nodes.length)
        return [];
    const degreeMap = new Map();
    for (const node of nodes)
        degreeMap.set(node.nodeId, 0);
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
        const isActive = selectedGraphNodeId.value === null ? false : graphNeighborNodeIds.value.has(node.nodeId);
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
    if (!detail.value.relationEdges.length || !graphCanvasNodes.value.length)
        return [];
    const nodeMap = new Map(graphCanvasNodes.value.map((node) => [node.nodeId, node]));
    return detail.value.relationEdges
        .map((edge) => {
        const src = nodeMap.get(edge.srcNodeId);
        const dst = nodeMap.get(edge.dstNodeId);
        if (!src || !dst)
            return null;
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
        const isActive = selectedGraphNodeId.value === null
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
        .filter((edge) => Boolean(edge));
});
function withToken(url) {
    const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
    if (!url || !tokenQuery)
        return url;
    return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
}
function qualityTagType(status) {
    if (status === "accepted")
        return "success";
    if (status === "rejected")
        return "danger";
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
    }
    catch (e) {
        ElMessage.error(e?.response?.data?.detail || e?.message || "構造化総覧の取得に失敗しました");
    }
    finally {
        overviewLoading.value = false;
    }
}
async function loadDetail(fileMd5) {
    if (!fileMd5)
        return;
    detailLoading.value = true;
    try {
        const resp = await getStructuredDetail(fileMd5);
        detail.value = resp.data;
        selectedGraphNodeId.value = null;
    }
    catch (e) {
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
    }
    finally {
        detailLoading.value = false;
    }
}
async function refreshAll() {
    await loadOverview();
    if (selectedFileMd5.value) {
        await loadDetail(selectedFileMd5.value);
    }
}
function handleCurrentChange(row) {
    if (!row?.fileMd5 || row.fileMd5 === selectedFileMd5.value)
        return;
    selectedFileMd5.value = row.fileMd5;
    void loadDetail(row.fileMd5);
}
function handleRowClick(row) {
    handleCurrentChange(row);
}
onMounted(async () => {
    await loadOverview();
    if (selectedFileMd5.value) {
        await loadDetail(selectedFileMd5.value);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['main-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['header-row']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
// CSS variable injection 
// CSS variable injection end 
/** @type {[typeof AppLayout, typeof AppLayout, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(AppLayout, new AppLayout({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
var __VLS_3 = {};
__VLS_2.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-wrap" },
});
const __VLS_4 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_7.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "subtitle" },
    });
    const __VLS_8 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.overviewLoading || __VLS_ctx.detailLoading),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.overviewLoading || __VLS_ctx.detailLoading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_12;
    let __VLS_13;
    let __VLS_14;
    const __VLS_15 = {
        onClick: (__VLS_ctx.refreshAll)
    };
    __VLS_11.slots.default;
    var __VLS_11;
}
const __VLS_16 = {}.ElAlert;
/** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "この画面は DB の新構造を直接確認するための運用ビューです。ファイルを選ぶと、document_units / semantic_blocks / parent_chunks / child_chunks / visual_pages / images を表示します。",
    ...{ class: "hint" },
}));
const __VLS_18 = __VLS_17({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "この画面は DB の新構造を直接確認するための運用ビューです。ファイルを選ぶと、document_units / semantic_blocks / parent_chunks / child_chunks / visual_pages / images を表示します。",
    ...{ class: "hint" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-strip" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.overviewRows.length);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalDocumentUnits);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalSemanticBlocks);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalChildChunks);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalVisualPages);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalVisualEmbeddings);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalVisualIndexed);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "summary-value" },
});
(__VLS_ctx.totalImages);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "main-layout" },
});
const __VLS_20 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    shadow: "never",
    ...{ class: "inner-card left-panel" },
}));
const __VLS_22 = __VLS_21({
    shadow: "never",
    ...{ class: "inner-card left-panel" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_23.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "panel-subtext" },
    });
}
const __VLS_24 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onCurrentChange': {} },
    ...{ 'onRowClick': {} },
    data: (__VLS_ctx.overviewRows),
    size: "small",
    border: true,
    maxHeight: "640",
    highlightCurrentRow: true,
    currentRowKey: (__VLS_ctx.selectedFileMd5),
    rowKey: "fileMd5",
}));
const __VLS_26 = __VLS_25({
    ...{ 'onCurrentChange': {} },
    ...{ 'onRowClick': {} },
    data: (__VLS_ctx.overviewRows),
    size: "small",
    border: true,
    maxHeight: "640",
    highlightCurrentRow: true,
    currentRowKey: (__VLS_ctx.selectedFileMd5),
    rowKey: "fileMd5",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onCurrentChange: (__VLS_ctx.handleCurrentChange)
};
const __VLS_32 = {
    onRowClick: (__VLS_ctx.handleRowClick)
};
__VLS_27.slots.default;
const __VLS_33 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
    prop: "fileName",
    label: "文書名",
    minWidth: "220",
    showOverflowTooltip: true,
}));
const __VLS_35 = __VLS_34({
    prop: "fileName",
    label: "文書名",
    minWidth: "220",
    showOverflowTooltip: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
const __VLS_37 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({
    prop: "kbProfile",
    label: "シナリオ",
    width: "120",
}));
const __VLS_39 = __VLS_38({
    prop: "kbProfile",
    label: "シナリオ",
    width: "120",
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
const __VLS_41 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
    prop: "documentUnitCount",
    label: "unit",
    width: "76",
}));
const __VLS_43 = __VLS_42({
    prop: "documentUnitCount",
    label: "unit",
    width: "76",
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
const __VLS_45 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
    prop: "semanticBlockCount",
    label: "block",
    width: "78",
}));
const __VLS_47 = __VLS_46({
    prop: "semanticBlockCount",
    label: "block",
    width: "78",
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
const __VLS_49 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
    prop: "parentChunkCount",
    label: "parent",
    width: "84",
}));
const __VLS_51 = __VLS_50({
    prop: "parentChunkCount",
    label: "parent",
    width: "84",
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
const __VLS_53 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
    prop: "childChunkCount",
    label: "child",
    width: "76",
}));
const __VLS_55 = __VLS_54({
    prop: "childChunkCount",
    label: "child",
    width: "76",
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
const __VLS_57 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
    prop: "visualPageCount",
    label: "visual",
    width: "76",
}));
const __VLS_59 = __VLS_58({
    prop: "visualPageCount",
    label: "visual",
    width: "76",
}, ...__VLS_functionalComponentArgsRest(__VLS_58));
const __VLS_61 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
    prop: "imageBlockCount",
    label: "image",
    width: "76",
}));
const __VLS_63 = __VLS_62({
    prop: "imageBlockCount",
    label: "image",
    width: "76",
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
var __VLS_27;
var __VLS_23;
const __VLS_65 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({
    shadow: "never",
    ...{ class: "inner-card right-panel" },
}));
const __VLS_67 = __VLS_66({
    shadow: "never",
    ...{ class: "inner-card right-panel" },
}, ...__VLS_functionalComponentArgsRest(__VLS_66));
__VLS_68.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_68.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "panel-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    if (__VLS_ctx.detailLoading) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "panel-subtext" },
        });
    }
}
if (!__VLS_ctx.selectedFile) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-meta" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-title" },
    });
    (__VLS_ctx.selectedFile.fileName);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-tags" },
    });
    const __VLS_69 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
        size: "small",
        effect: "plain",
    }));
    const __VLS_71 = __VLS_70({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_70));
    __VLS_72.slots.default;
    (__VLS_ctx.selectedFile.kbProfile || "-");
    var __VLS_72;
    const __VLS_73 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({
        size: "small",
        effect: "plain",
    }));
    const __VLS_75 = __VLS_74({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_74));
    __VLS_76.slots.default;
    (__VLS_ctx.selectedFile.orgTagName || "-");
    var __VLS_76;
    const __VLS_77 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
        size: "small",
        type: (__VLS_ctx.selectedFile.isPublic ? 'success' : 'info'),
        effect: "light",
    }));
    const __VLS_79 = __VLS_78({
        size: "small",
        type: (__VLS_ctx.selectedFile.isPublic ? 'success' : 'info'),
        effect: "light",
    }, ...__VLS_functionalComponentArgsRest(__VLS_78));
    __VLS_80.slots.default;
    (__VLS_ctx.selectedFile.isPublic ? "公開" : "非公開");
    var __VLS_80;
    if (__VLS_ctx.detail.originalUrl) {
        const __VLS_81 = {}.ElLink;
        /** @type {[typeof __VLS_components.ElLink, typeof __VLS_components.elLink, typeof __VLS_components.ElLink, typeof __VLS_components.elLink, ]} */ ;
        // @ts-ignore
        const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({
            href: (__VLS_ctx.withToken(__VLS_ctx.detail.originalUrl)),
            target: "_blank",
            type: "primary",
        }));
        const __VLS_83 = __VLS_82({
            href: (__VLS_ctx.withToken(__VLS_ctx.detail.originalUrl)),
            target: "_blank",
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_82));
        __VLS_84.slots.default;
        var __VLS_84;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "quality-summary" },
    });
    const __VLS_85 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
        type: "success",
        effect: "light",
    }));
    const __VLS_87 = __VLS_86({
        type: "success",
        effect: "light",
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    __VLS_88.slots.default;
    (__VLS_ctx.selectedFile.acceptedBlockCount);
    var __VLS_88;
    const __VLS_89 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
        type: "warning",
        effect: "light",
    }));
    const __VLS_91 = __VLS_90({
        type: "warning",
        effect: "light",
    }, ...__VLS_functionalComponentArgsRest(__VLS_90));
    __VLS_92.slots.default;
    (__VLS_ctx.selectedFile.weakBlockCount);
    var __VLS_92;
    const __VLS_93 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({
        type: "danger",
        effect: "light",
    }));
    const __VLS_95 = __VLS_94({
        type: "danger",
        effect: "light",
    }, ...__VLS_functionalComponentArgsRest(__VLS_94));
    __VLS_96.slots.default;
    (__VLS_ctx.selectedFile.rejectedBlockCount);
    var __VLS_96;
    const __VLS_97 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
        effect: "plain",
    }));
    const __VLS_99 = __VLS_98({
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_98));
    __VLS_100.slots.default;
    (__VLS_ctx.selectedFile.visualEmbeddingCount);
    var __VLS_100;
    const __VLS_101 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({
        effect: "plain",
    }));
    const __VLS_103 = __VLS_102({
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_102));
    __VLS_104.slots.default;
    (__VLS_ctx.selectedFile.visualIndexedCount);
    var __VLS_104;
    const __VLS_105 = {}.ElTabs;
    /** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
    // @ts-ignore
    const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
        modelValue: (__VLS_ctx.activeTab),
    }));
    const __VLS_107 = __VLS_106({
        modelValue: (__VLS_ctx.activeTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_106));
    __VLS_108.slots.default;
    const __VLS_109 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
        label: "原生単元",
        name: "units",
    }));
    const __VLS_111 = __VLS_110({
        label: "原生単元",
        name: "units",
    }, ...__VLS_functionalComponentArgsRest(__VLS_110));
    __VLS_112.slots.default;
    if (!__VLS_ctx.detail.documentUnits.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        const __VLS_113 = {}.ElTable;
        /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
        // @ts-ignore
        const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
            data: (__VLS_ctx.detail.documentUnits),
            size: "small",
            border: true,
            maxHeight: "520",
        }));
        const __VLS_115 = __VLS_114({
            data: (__VLS_ctx.detail.documentUnits),
            size: "small",
            border: true,
            maxHeight: "520",
        }, ...__VLS_functionalComponentArgsRest(__VLS_114));
        __VLS_116.slots.default;
        const __VLS_117 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
            prop: "unitType",
            label: "type",
            width: "90",
        }));
        const __VLS_119 = __VLS_118({
            prop: "unitType",
            label: "type",
            width: "90",
        }, ...__VLS_functionalComponentArgsRest(__VLS_118));
        const __VLS_121 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
            prop: "unitKey",
            label: "unit key",
            minWidth: "180",
            showOverflowTooltip: true,
        }));
        const __VLS_123 = __VLS_122({
            prop: "unitKey",
            label: "unit key",
            minWidth: "180",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_122));
        const __VLS_125 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
            prop: "unitName",
            label: "name",
            minWidth: "160",
            showOverflowTooltip: true,
        }));
        const __VLS_127 = __VLS_126({
            prop: "unitName",
            label: "name",
            minWidth: "160",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_126));
        const __VLS_129 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({
            prop: "unitOrder",
            label: "order",
            width: "80",
        }));
        const __VLS_131 = __VLS_130({
            prop: "unitOrder",
            label: "order",
            width: "80",
        }, ...__VLS_functionalComponentArgsRest(__VLS_130));
        const __VLS_133 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({
            prop: "page",
            label: "page",
            width: "80",
        }));
        const __VLS_135 = __VLS_134({
            prop: "page",
            label: "page",
            width: "80",
        }, ...__VLS_functionalComponentArgsRest(__VLS_134));
        const __VLS_137 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({
            prop: "sheet",
            label: "sheet",
            minWidth: "140",
            showOverflowTooltip: true,
        }));
        const __VLS_139 = __VLS_138({
            prop: "sheet",
            label: "sheet",
            minWidth: "140",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_138));
        const __VLS_141 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_142 = __VLS_asFunctionalComponent(__VLS_141, new __VLS_141({
            prop: "section",
            label: "section",
            minWidth: "140",
            showOverflowTooltip: true,
        }));
        const __VLS_143 = __VLS_142({
            prop: "section",
            label: "section",
            minWidth: "140",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_142));
        var __VLS_116;
    }
    var __VLS_112;
    const __VLS_145 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
        label: "語義 block",
        name: "blocks",
    }));
    const __VLS_147 = __VLS_146({
        label: "語義 block",
        name: "blocks",
    }, ...__VLS_functionalComponentArgsRest(__VLS_146));
    __VLS_148.slots.default;
    if (!__VLS_ctx.detail.semanticBlocks.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        const __VLS_149 = {}.ElTable;
        /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
        // @ts-ignore
        const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
            data: (__VLS_ctx.detail.semanticBlocks),
            size: "small",
            border: true,
            maxHeight: "520",
        }));
        const __VLS_151 = __VLS_150({
            data: (__VLS_ctx.detail.semanticBlocks),
            size: "small",
            border: true,
            maxHeight: "520",
        }, ...__VLS_functionalComponentArgsRest(__VLS_150));
        __VLS_152.slots.default;
        const __VLS_153 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
            prop: "blockIndex",
            label: "idx",
            width: "72",
        }));
        const __VLS_155 = __VLS_154({
            prop: "blockIndex",
            label: "idx",
            width: "72",
        }, ...__VLS_functionalComponentArgsRest(__VLS_154));
        const __VLS_157 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
            prop: "blockType",
            label: "type",
            minWidth: "120",
            showOverflowTooltip: true,
        }));
        const __VLS_159 = __VLS_158({
            prop: "blockType",
            label: "type",
            minWidth: "120",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_158));
        const __VLS_161 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
            prop: "sourceParser",
            label: "parser",
            minWidth: "120",
            showOverflowTooltip: true,
        }));
        const __VLS_163 = __VLS_162({
            prop: "sourceParser",
            label: "parser",
            minWidth: "120",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_162));
        const __VLS_165 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
            label: "quality",
            width: "120",
        }));
        const __VLS_167 = __VLS_166({
            label: "quality",
            width: "120",
        }, ...__VLS_functionalComponentArgsRest(__VLS_166));
        __VLS_168.slots.default;
        {
            const { default: __VLS_thisSlot } = __VLS_168.slots;
            const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
            const __VLS_169 = {}.ElTag;
            /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
            // @ts-ignore
            const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
                size: "small",
                type: (__VLS_ctx.qualityTagType(row.qualityStatus)),
                effect: "light",
            }));
            const __VLS_171 = __VLS_170({
                size: "small",
                type: (__VLS_ctx.qualityTagType(row.qualityStatus)),
                effect: "light",
            }, ...__VLS_functionalComponentArgsRest(__VLS_170));
            __VLS_172.slots.default;
            (row.qualityStatus);
            (row.qualityScore);
            var __VLS_172;
        }
        var __VLS_168;
        const __VLS_173 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_174 = __VLS_asFunctionalComponent(__VLS_173, new __VLS_173({
            prop: "sheet",
            label: "sheet",
            minWidth: "120",
            showOverflowTooltip: true,
        }));
        const __VLS_175 = __VLS_174({
            prop: "sheet",
            label: "sheet",
            minWidth: "120",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_174));
        const __VLS_177 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_178 = __VLS_asFunctionalComponent(__VLS_177, new __VLS_177({
            prop: "page",
            label: "page",
            width: "72",
        }));
        const __VLS_179 = __VLS_178({
            prop: "page",
            label: "page",
            width: "72",
        }, ...__VLS_functionalComponentArgsRest(__VLS_178));
        const __VLS_181 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
            prop: "rowNo",
            label: "row",
            width: "72",
        }));
        const __VLS_183 = __VLS_182({
            prop: "rowNo",
            label: "row",
            width: "72",
        }, ...__VLS_functionalComponentArgsRest(__VLS_182));
        const __VLS_185 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_186 = __VLS_asFunctionalComponent(__VLS_185, new __VLS_185({
            prop: "textPreview",
            label: "内容",
            minWidth: "260",
            showOverflowTooltip: true,
        }));
        const __VLS_187 = __VLS_186({
            prop: "textPreview",
            label: "内容",
            minWidth: "260",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_186));
        const __VLS_189 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_190 = __VLS_asFunctionalComponent(__VLS_189, new __VLS_189({
            label: "画像",
            width: "88",
        }));
        const __VLS_191 = __VLS_190({
            label: "画像",
            width: "88",
        }, ...__VLS_functionalComponentArgsRest(__VLS_190));
        __VLS_192.slots.default;
        {
            const { default: __VLS_thisSlot } = __VLS_192.slots;
            const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
            if (row.imageUrl) {
                const __VLS_193 = {}.ElLink;
                /** @type {[typeof __VLS_components.ElLink, typeof __VLS_components.elLink, typeof __VLS_components.ElLink, typeof __VLS_components.elLink, ]} */ ;
                // @ts-ignore
                const __VLS_194 = __VLS_asFunctionalComponent(__VLS_193, new __VLS_193({
                    href: (__VLS_ctx.withToken(row.imageUrl)),
                    target: "_blank",
                    type: "primary",
                }));
                const __VLS_195 = __VLS_194({
                    href: (__VLS_ctx.withToken(row.imageUrl)),
                    target: "_blank",
                    type: "primary",
                }, ...__VLS_functionalComponentArgsRest(__VLS_194));
                __VLS_196.slots.default;
                var __VLS_196;
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            }
        }
        var __VLS_192;
        var __VLS_152;
    }
    var __VLS_148;
    const __VLS_197 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_198 = __VLS_asFunctionalComponent(__VLS_197, new __VLS_197({
        label: "父chunk",
        name: "parent",
    }));
    const __VLS_199 = __VLS_198({
        label: "父chunk",
        name: "parent",
    }, ...__VLS_functionalComponentArgsRest(__VLS_198));
    __VLS_200.slots.default;
    if (!__VLS_ctx.detail.parentChunks.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        const __VLS_201 = {}.ElTable;
        /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
        // @ts-ignore
        const __VLS_202 = __VLS_asFunctionalComponent(__VLS_201, new __VLS_201({
            data: (__VLS_ctx.detail.parentChunks),
            size: "small",
            border: true,
            maxHeight: "520",
        }));
        const __VLS_203 = __VLS_202({
            data: (__VLS_ctx.detail.parentChunks),
            size: "small",
            border: true,
            maxHeight: "520",
        }, ...__VLS_functionalComponentArgsRest(__VLS_202));
        __VLS_204.slots.default;
        const __VLS_205 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_206 = __VLS_asFunctionalComponent(__VLS_205, new __VLS_205({
            prop: "parentChunkId",
            label: "parent id",
            width: "90",
        }));
        const __VLS_207 = __VLS_206({
            prop: "parentChunkId",
            label: "parent id",
            width: "90",
        }, ...__VLS_functionalComponentArgsRest(__VLS_206));
        const __VLS_209 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_210 = __VLS_asFunctionalComponent(__VLS_209, new __VLS_209({
            prop: "documentUnitKey",
            label: "unit key",
            minWidth: "160",
            showOverflowTooltip: true,
        }));
        const __VLS_211 = __VLS_210({
            prop: "documentUnitKey",
            label: "unit key",
            minWidth: "160",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_210));
        const __VLS_213 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_214 = __VLS_asFunctionalComponent(__VLS_213, new __VLS_213({
            prop: "chunkType",
            label: "type",
            minWidth: "110",
            showOverflowTooltip: true,
        }));
        const __VLS_215 = __VLS_214({
            prop: "chunkType",
            label: "type",
            minWidth: "110",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_214));
        const __VLS_217 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_218 = __VLS_asFunctionalComponent(__VLS_217, new __VLS_217({
            label: "quality",
            width: "120",
        }));
        const __VLS_219 = __VLS_218({
            label: "quality",
            width: "120",
        }, ...__VLS_functionalComponentArgsRest(__VLS_218));
        __VLS_220.slots.default;
        {
            const { default: __VLS_thisSlot } = __VLS_220.slots;
            const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
            const __VLS_221 = {}.ElTag;
            /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
            // @ts-ignore
            const __VLS_222 = __VLS_asFunctionalComponent(__VLS_221, new __VLS_221({
                size: "small",
                type: (__VLS_ctx.qualityTagType(row.qualityStatus)),
                effect: "light",
            }));
            const __VLS_223 = __VLS_222({
                size: "small",
                type: (__VLS_ctx.qualityTagType(row.qualityStatus)),
                effect: "light",
            }, ...__VLS_functionalComponentArgsRest(__VLS_222));
            __VLS_224.slots.default;
            (row.qualityStatus);
            (row.qualityScore);
            var __VLS_224;
        }
        var __VLS_220;
        const __VLS_225 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_226 = __VLS_asFunctionalComponent(__VLS_225, new __VLS_225({
            prop: "textPreview",
            label: "内容",
            minWidth: "320",
            showOverflowTooltip: true,
        }));
        const __VLS_227 = __VLS_226({
            prop: "textPreview",
            label: "内容",
            minWidth: "320",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_226));
        var __VLS_204;
    }
    var __VLS_200;
    const __VLS_229 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_230 = __VLS_asFunctionalComponent(__VLS_229, new __VLS_229({
        label: "子chunk",
        name: "child",
    }));
    const __VLS_231 = __VLS_230({
        label: "子chunk",
        name: "child",
    }, ...__VLS_functionalComponentArgsRest(__VLS_230));
    __VLS_232.slots.default;
    if (!__VLS_ctx.detail.childChunks.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        const __VLS_233 = {}.ElTable;
        /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
        // @ts-ignore
        const __VLS_234 = __VLS_asFunctionalComponent(__VLS_233, new __VLS_233({
            data: (__VLS_ctx.detail.childChunks),
            size: "small",
            border: true,
            maxHeight: "520",
        }));
        const __VLS_235 = __VLS_234({
            data: (__VLS_ctx.detail.childChunks),
            size: "small",
            border: true,
            maxHeight: "520",
        }, ...__VLS_functionalComponentArgsRest(__VLS_234));
        __VLS_236.slots.default;
        const __VLS_237 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_238 = __VLS_asFunctionalComponent(__VLS_237, new __VLS_237({
            prop: "childChunkId",
            label: "child id",
            width: "84",
        }));
        const __VLS_239 = __VLS_238({
            prop: "childChunkId",
            label: "child id",
            width: "84",
        }, ...__VLS_functionalComponentArgsRest(__VLS_238));
        const __VLS_241 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_242 = __VLS_asFunctionalComponent(__VLS_241, new __VLS_241({
            prop: "parentChunkId",
            label: "parent",
            width: "84",
        }));
        const __VLS_243 = __VLS_242({
            prop: "parentChunkId",
            label: "parent",
            width: "84",
        }, ...__VLS_functionalComponentArgsRest(__VLS_242));
        const __VLS_245 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_246 = __VLS_asFunctionalComponent(__VLS_245, new __VLS_245({
            prop: "documentUnitKey",
            label: "unit key",
            minWidth: "150",
            showOverflowTooltip: true,
        }));
        const __VLS_247 = __VLS_246({
            prop: "documentUnitKey",
            label: "unit key",
            minWidth: "150",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_246));
        const __VLS_249 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_250 = __VLS_asFunctionalComponent(__VLS_249, new __VLS_249({
            prop: "chunkType",
            label: "type",
            minWidth: "110",
            showOverflowTooltip: true,
        }));
        const __VLS_251 = __VLS_250({
            prop: "chunkType",
            label: "type",
            minWidth: "110",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_250));
        const __VLS_253 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_254 = __VLS_asFunctionalComponent(__VLS_253, new __VLS_253({
            label: "quality",
            width: "120",
        }));
        const __VLS_255 = __VLS_254({
            label: "quality",
            width: "120",
        }, ...__VLS_functionalComponentArgsRest(__VLS_254));
        __VLS_256.slots.default;
        {
            const { default: __VLS_thisSlot } = __VLS_256.slots;
            const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
            const __VLS_257 = {}.ElTag;
            /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
            // @ts-ignore
            const __VLS_258 = __VLS_asFunctionalComponent(__VLS_257, new __VLS_257({
                size: "small",
                type: (__VLS_ctx.qualityTagType(row.qualityStatus)),
                effect: "light",
            }));
            const __VLS_259 = __VLS_258({
                size: "small",
                type: (__VLS_ctx.qualityTagType(row.qualityStatus)),
                effect: "light",
            }, ...__VLS_functionalComponentArgsRest(__VLS_258));
            __VLS_260.slots.default;
            (row.qualityStatus);
            (row.qualityScore);
            var __VLS_260;
        }
        var __VLS_256;
        const __VLS_261 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_262 = __VLS_asFunctionalComponent(__VLS_261, new __VLS_261({
            label: "neighbor",
            width: "120",
        }));
        const __VLS_263 = __VLS_262({
            label: "neighbor",
            width: "120",
        }, ...__VLS_functionalComponentArgsRest(__VLS_262));
        __VLS_264.slots.default;
        {
            const { default: __VLS_thisSlot } = __VLS_264.slots;
            const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
            (row.neighborPrevId ?? "-");
            (row.neighborNextId ?? "-");
        }
        var __VLS_264;
        const __VLS_265 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_266 = __VLS_asFunctionalComponent(__VLS_265, new __VLS_265({
            prop: "textPreview",
            label: "内容",
            minWidth: "260",
            showOverflowTooltip: true,
        }));
        const __VLS_267 = __VLS_266({
            prop: "textPreview",
            label: "内容",
            minWidth: "260",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_266));
        var __VLS_236;
    }
    var __VLS_232;
    const __VLS_269 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_270 = __VLS_asFunctionalComponent(__VLS_269, new __VLS_269({
        label: "画像証跡",
        name: "images",
    }));
    const __VLS_271 = __VLS_270({
        label: "画像証跡",
        name: "images",
    }, ...__VLS_functionalComponentArgsRest(__VLS_270));
    __VLS_272.slots.default;
    if (!__VLS_ctx.detail.images.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "image-grid" },
        });
        for (const [img, idx] of __VLS_getVForSourceType((__VLS_ctx.detail.images))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (`img-${idx}`),
                ...{ class: "image-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "image-meta" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.sheet || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.page || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.sourceParser || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.matchMode || "-");
            (img.matchConfidence ?? "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
                href: (__VLS_ctx.withToken(img.imageUrl)),
                target: "_blank",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (__VLS_ctx.withToken(img.imageUrl)),
                alt: "structured evidence image",
                ...{ class: "image" },
            });
        }
    }
    var __VLS_272;
    const __VLS_273 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_274 = __VLS_asFunctionalComponent(__VLS_273, new __VLS_273({
        label: "Visual Pages",
        name: "visualPages",
    }));
    const __VLS_275 = __VLS_274({
        label: "Visual Pages",
        name: "visualPages",
    }, ...__VLS_functionalComponentArgsRest(__VLS_274));
    __VLS_276.slots.default;
    if (!__VLS_ctx.detail.visualPages.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "image-grid" },
        });
        for (const [img, idx] of __VLS_getVForSourceType((__VLS_ctx.detail.visualPages))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (`visual-${idx}`),
                ...{ class: "image-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "image-meta" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.pageLabel || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.unitType || "-");
            (img.documentUnitId ?? "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.sheet || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.page || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.renderSource || "-");
            (img.renderVersion || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.qualityStatus || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.visualEmbeddingStatus || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.visualIndexed ? "yes" : "no");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.visualEmbeddingProvider || "-");
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (img.visualEmbeddingModel || "-");
            if (img.visualEmbeddingDim) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                (img.visualEmbeddingDim);
            }
            if (img.visualIndexDocId) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                (img.visualIndexDocId);
            }
            if (img.visualEmbeddingError) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "embedding-error" },
                });
                (img.visualEmbeddingError);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
                href: (__VLS_ctx.withToken(img.imageUrl)),
                target: "_blank",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (__VLS_ctx.withToken(img.imageUrl)),
                alt: "visual page image",
                ...{ class: "image" },
            });
        }
    }
    var __VLS_276;
    const __VLS_277 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_278 = __VLS_asFunctionalComponent(__VLS_277, new __VLS_277({
        label: "Graph",
        name: "graph",
    }));
    const __VLS_279 = __VLS_278({
        label: "Graph",
        name: "graph",
    }, ...__VLS_functionalComponentArgsRest(__VLS_278));
    __VLS_280.slots.default;
    if (!__VLS_ctx.detail.relationNodes.length && !__VLS_ctx.detail.relationEdges.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-pane" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-canvas-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-canvas-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-subtitle" },
        });
        if (__VLS_ctx.selectedGraphNodeId !== null) {
            const __VLS_281 = {}.ElButton;
            /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
            // @ts-ignore
            const __VLS_282 = __VLS_asFunctionalComponent(__VLS_281, new __VLS_281({
                ...{ 'onClick': {} },
                size: "small",
                plain: true,
            }));
            const __VLS_283 = __VLS_282({
                ...{ 'onClick': {} },
                size: "small",
                plain: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_282));
            let __VLS_285;
            let __VLS_286;
            let __VLS_287;
            const __VLS_288 = {
                onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.selectedFile))
                        return;
                    if (!!(!__VLS_ctx.detail.relationNodes.length && !__VLS_ctx.detail.relationEdges.length))
                        return;
                    if (!(__VLS_ctx.selectedGraphNodeId !== null))
                        return;
                    __VLS_ctx.selectedGraphNodeId = null;
                }
            };
            __VLS_284.slots.default;
            var __VLS_284;
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-legend" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-dot legend-component" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-dot legend-page" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-dot legend-flow" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "legend-dot legend-other" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-canvas-wrap" },
        });
        if (__VLS_ctx.graphCanvasNodes.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
                ...{ class: "graph-canvas" },
                viewBox: (`0 0 ${__VLS_ctx.GRAPH_CANVAS_WIDTH} ${__VLS_ctx.GRAPH_CANVAS_HEIGHT}`),
                preserveAspectRatio: "xMidYMid meet",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.defs, __VLS_intrinsicElements.defs)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.marker, __VLS_intrinsicElements.marker)({
                id: "graph-arrow",
                markerWidth: "10",
                markerHeight: "10",
                refX: "9",
                refY: "5",
                orient: "auto",
                markerUnits: "strokeWidth",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
                d: "M 0 0 L 10 5 L 0 10 z",
                fill: "#94a3b8",
            });
            for (const [edge] of __VLS_getVForSourceType((__VLS_ctx.graphCanvasEdges))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.g, __VLS_intrinsicElements.g)({
                    key: (`edge-${edge.edgeId}`),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
                    x1: (edge.x1),
                    y1: (edge.y1),
                    x2: (edge.x2),
                    y2: (edge.y2),
                    ...{ class: (['graph-edge-line', { 'graph-edge-line--active': edge.isActive }]) },
                    'marker-end': "url(#graph-arrow)",
                });
                if (edge.label) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.text, __VLS_intrinsicElements.text)({
                        x: (edge.labelX),
                        y: (edge.labelY),
                        ...{ class: "graph-edge-label" },
                    });
                    (edge.label);
                }
            }
            for (const [node] of __VLS_getVForSourceType((__VLS_ctx.graphCanvasNodes))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.g, __VLS_intrinsicElements.g)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.selectedFile))
                                return;
                            if (!!(!__VLS_ctx.detail.relationNodes.length && !__VLS_ctx.detail.relationEdges.length))
                                return;
                            if (!(__VLS_ctx.graphCanvasNodes.length))
                                return;
                            __VLS_ctx.selectedGraphNodeId = node.nodeId;
                        } },
                    key: (`node-${node.nodeId}`),
                    ...{ class: "graph-node" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.circle)({
                    cx: (node.x),
                    cy: (node.y),
                    r: (node.radius),
                    fill: (node.fill),
                    ...{ class: (['graph-node-circle', { 'graph-node-circle--active': node.isActive }]) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.text, __VLS_intrinsicElements.text)({
                    x: (node.x),
                    y: (node.y + 4),
                    ...{ class: "graph-node-label" },
                });
                (node.shortLabel);
            }
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-title" },
        });
        if (__VLS_ctx.filteredRelationNodes.length) {
            const __VLS_289 = {}.ElTable;
            /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
            // @ts-ignore
            const __VLS_290 = __VLS_asFunctionalComponent(__VLS_289, new __VLS_289({
                data: (__VLS_ctx.filteredRelationNodes),
                size: "small",
                border: true,
                maxHeight: "220",
            }));
            const __VLS_291 = __VLS_290({
                data: (__VLS_ctx.filteredRelationNodes),
                size: "small",
                border: true,
                maxHeight: "220",
            }, ...__VLS_functionalComponentArgsRest(__VLS_290));
            __VLS_292.slots.default;
            const __VLS_293 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_294 = __VLS_asFunctionalComponent(__VLS_293, new __VLS_293({
                prop: "nodeId",
                label: "id",
                width: "72",
            }));
            const __VLS_295 = __VLS_294({
                prop: "nodeId",
                label: "id",
                width: "72",
            }, ...__VLS_functionalComponentArgsRest(__VLS_294));
            const __VLS_297 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_298 = __VLS_asFunctionalComponent(__VLS_297, new __VLS_297({
                prop: "nodeName",
                label: "name",
                minWidth: "160",
                showOverflowTooltip: true,
            }));
            const __VLS_299 = __VLS_298({
                prop: "nodeName",
                label: "name",
                minWidth: "160",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_298));
            const __VLS_301 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_302 = __VLS_asFunctionalComponent(__VLS_301, new __VLS_301({
                prop: "nodeType",
                label: "type",
                minWidth: "110",
                showOverflowTooltip: true,
            }));
            const __VLS_303 = __VLS_302({
                prop: "nodeType",
                label: "type",
                minWidth: "110",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_302));
            const __VLS_305 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_306 = __VLS_asFunctionalComponent(__VLS_305, new __VLS_305({
                prop: "page",
                label: "page",
                width: "72",
            }));
            const __VLS_307 = __VLS_306({
                prop: "page",
                label: "page",
                width: "72",
            }, ...__VLS_functionalComponentArgsRest(__VLS_306));
            const __VLS_309 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_310 = __VLS_asFunctionalComponent(__VLS_309, new __VLS_309({
                prop: "nodeKey",
                label: "key",
                minWidth: "180",
                showOverflowTooltip: true,
            }));
            const __VLS_311 = __VLS_310({
                prop: "nodeKey",
                label: "key",
                minWidth: "180",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_310));
            const __VLS_313 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_314 = __VLS_asFunctionalComponent(__VLS_313, new __VLS_313({
                prop: "evidenceText",
                label: "evidence",
                minWidth: "220",
                showOverflowTooltip: true,
            }));
            const __VLS_315 = __VLS_314({
                prop: "evidenceText",
                label: "evidence",
                minWidth: "220",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_314));
            var __VLS_292;
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "empty graph-empty" },
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "graph-title" },
        });
        if (__VLS_ctx.filteredRelationEdges.length) {
            const __VLS_317 = {}.ElTable;
            /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
            // @ts-ignore
            const __VLS_318 = __VLS_asFunctionalComponent(__VLS_317, new __VLS_317({
                data: (__VLS_ctx.filteredRelationEdges),
                size: "small",
                border: true,
                maxHeight: "220",
            }));
            const __VLS_319 = __VLS_318({
                data: (__VLS_ctx.filteredRelationEdges),
                size: "small",
                border: true,
                maxHeight: "220",
            }, ...__VLS_functionalComponentArgsRest(__VLS_318));
            __VLS_320.slots.default;
            const __VLS_321 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_322 = __VLS_asFunctionalComponent(__VLS_321, new __VLS_321({
                prop: "edgeId",
                label: "id",
                width: "72",
            }));
            const __VLS_323 = __VLS_322({
                prop: "edgeId",
                label: "id",
                width: "72",
            }, ...__VLS_functionalComponentArgsRest(__VLS_322));
            const __VLS_325 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_326 = __VLS_asFunctionalComponent(__VLS_325, new __VLS_325({
                prop: "srcNodeName",
                label: "src",
                minWidth: "140",
                showOverflowTooltip: true,
            }));
            const __VLS_327 = __VLS_326({
                prop: "srcNodeName",
                label: "src",
                minWidth: "140",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_326));
            const __VLS_329 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_330 = __VLS_asFunctionalComponent(__VLS_329, new __VLS_329({
                prop: "dstNodeName",
                label: "dst",
                minWidth: "140",
                showOverflowTooltip: true,
            }));
            const __VLS_331 = __VLS_330({
                prop: "dstNodeName",
                label: "dst",
                minWidth: "140",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_330));
            const __VLS_333 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_334 = __VLS_asFunctionalComponent(__VLS_333, new __VLS_333({
                prop: "relationType",
                label: "type",
                minWidth: "100",
                showOverflowTooltip: true,
            }));
            const __VLS_335 = __VLS_334({
                prop: "relationType",
                label: "type",
                minWidth: "100",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_334));
            const __VLS_337 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_338 = __VLS_asFunctionalComponent(__VLS_337, new __VLS_337({
                prop: "page",
                label: "page",
                width: "72",
            }));
            const __VLS_339 = __VLS_338({
                prop: "page",
                label: "page",
                width: "72",
            }, ...__VLS_functionalComponentArgsRest(__VLS_338));
            const __VLS_341 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_342 = __VLS_asFunctionalComponent(__VLS_341, new __VLS_341({
                prop: "relationText",
                label: "relation",
                minWidth: "160",
                showOverflowTooltip: true,
            }));
            const __VLS_343 = __VLS_342({
                prop: "relationText",
                label: "relation",
                minWidth: "160",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_342));
            const __VLS_345 = {}.ElTableColumn;
            /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
            // @ts-ignore
            const __VLS_346 = __VLS_asFunctionalComponent(__VLS_345, new __VLS_345({
                prop: "evidenceText",
                label: "evidence",
                minWidth: "220",
                showOverflowTooltip: true,
            }));
            const __VLS_347 = __VLS_346({
                prop: "evidenceText",
                label: "evidence",
                minWidth: "220",
                showOverflowTooltip: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_346));
            var __VLS_320;
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "empty graph-empty" },
            });
        }
    }
    var __VLS_280;
    var __VLS_108;
}
var __VLS_68;
var __VLS_7;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['header-row']} */ ;
/** @type {__VLS_StyleScopedClasses['title']} */ ;
/** @type {__VLS_StyleScopedClasses['subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['hint']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-strip']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-value']} */ ;
/** @type {__VLS_StyleScopedClasses['main-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['inner-card']} */ ;
/** @type {__VLS_StyleScopedClasses['left-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-subtext']} */ ;
/** @type {__VLS_StyleScopedClasses['inner-card']} */ ;
/** @type {__VLS_StyleScopedClasses['right-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-subtext']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['file-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['file-title']} */ ;
/** @type {__VLS_StyleScopedClasses['file-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['image-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['image-card']} */ ;
/** @type {__VLS_StyleScopedClasses['image-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['image']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['image-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['image-card']} */ ;
/** @type {__VLS_StyleScopedClasses['image-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['embedding-error']} */ ;
/** @type {__VLS_StyleScopedClasses['image']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-pane']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas-card']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas-header']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-title']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-legend']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-item']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-component']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-item']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-page']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-item']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-flow']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-item']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['legend-other']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-canvas']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-edge-label']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-node']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-node-label']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-section']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-title']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-section']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-title']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['graph-empty']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            activeTab: activeTab,
            overviewLoading: overviewLoading,
            detailLoading: detailLoading,
            selectedGraphNodeId: selectedGraphNodeId,
            GRAPH_CANVAS_WIDTH: GRAPH_CANVAS_WIDTH,
            GRAPH_CANVAS_HEIGHT: GRAPH_CANVAS_HEIGHT,
            overviewRows: overviewRows,
            selectedFileMd5: selectedFileMd5,
            detail: detail,
            selectedFile: selectedFile,
            totalDocumentUnits: totalDocumentUnits,
            totalSemanticBlocks: totalSemanticBlocks,
            totalChildChunks: totalChildChunks,
            totalVisualPages: totalVisualPages,
            totalVisualEmbeddings: totalVisualEmbeddings,
            totalVisualIndexed: totalVisualIndexed,
            totalImages: totalImages,
            filteredRelationNodes: filteredRelationNodes,
            filteredRelationEdges: filteredRelationEdges,
            graphCanvasNodes: graphCanvasNodes,
            graphCanvasEdges: graphCanvasEdges,
            withToken: withToken,
            qualityTagType: qualityTagType,
            refreshAll: refreshAll,
            handleCurrentChange: handleCurrentChange,
            handleRowClick: handleRowClick,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
