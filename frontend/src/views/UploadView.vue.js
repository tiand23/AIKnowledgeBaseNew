import SparkMD5 from "spark-md5";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { uploadChunk, mergeFile, getUserUploadedFiles, getEsPreview } from "../api/file";
import { getRegisterOrgTags } from "../api/auth";
import { useAuthStore } from "../stores/auth";
import { useProfileStore } from "../stores/profile";
const orgTag = ref("");
const orgTagOptions = ref([]);
const isPublic = ref(false);
const chunkSizeMB = ref(2);
const profile = useProfileStore();
const auth = useAuthStore();
const tasks = ref([]);
const submitting = ref(false);
let statusPollTimer = null;
const historyLoading = ref(false);
const recentUploads = ref([]);
const previewDialogVisible = ref(false);
const previewLoading = ref(false);
const previewRows = ref([]);
const previewTargetName = ref("");
function onFileChange(e) {
    const input = e.target;
    const files = Array.from(input.files || []);
    if (!files.length) {
        return;
    }
    for (const file of files) {
        const id = `${file.name}-${file.size}-${file.lastModified}`;
        if (tasks.value.some((x) => x.id === id)) {
            continue;
        }
        const task = {
            id,
            file,
            fileMd5: "",
            totalChunks: 0,
            uploadedChunks: [],
            progress: 0,
            status: "hashing",
            message: "MD5 計算中",
            submitted: false
        };
        tasks.value.push(task);
        void prepareTask(task);
    }
    input.value = "";
}
async function prepareTask(task) {
    try {
        const file = task.file;
        const chunkBytes = Math.max(1, chunkSizeMB.value) * 1024 * 1024;
        task.totalChunks = Math.ceil(file.size / chunkBytes);
        task.fileMd5 = await computeMd5WithTimeout(file, 30000);
        task.status = "ready";
        task.message = "送信待ち";
    }
    catch (err) {
        task.status = "failed";
        task.message = err?.message || "MD5 計算失敗";
    }
}
async function computeMd5(file) {
    const chunkSize = 2 * 1024 * 1024;
    const chunks = Math.ceil(file.size / chunkSize);
    const spark = new SparkMD5.ArrayBuffer();
    for (let i = 0; i < chunks; i += 1) {
        const start = i * chunkSize;
        const end = Math.min(file.size, start + chunkSize);
        const buffer = await file.slice(start, end).arrayBuffer();
        spark.append(buffer);
    }
    return spark.end();
}
async function computeMd5WithTimeout(file, timeoutMs) {
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error("MD5 計算がタイムアウトしました。削除して再試行してください")), timeoutMs);
    });
    return Promise.race([computeMd5(file), timeoutPromise]);
}
async function submitAll() {
    if (!tasks.value.length) {
        ElMessage.warning("先にファイルを選択してください");
        return;
    }
    submitting.value = true;
    let ok = 0;
    let failed = 0;
    for (const task of tasks.value) {
        if (task.status === "processing" ||
            task.status === "uploading" ||
            task.status === "merging" ||
            task.status === "done") {
            continue;
        }
        const success = await submitSingle(task);
        if (success) {
            ok += 1;
        }
        else {
            failed += 1;
        }
    }
    submitting.value = false;
    if (failed === 0) {
        ElMessage.success(`送信完了: ${ok} 件をバックエンド処理に投入しました`);
    }
    else {
        ElMessage.warning(`送信完了: 成功 ${ok} / 失敗 ${failed}`);
    }
    await refreshUploadedFiles();
    startStatusPolling();
}
async function submitSingle(task) {
    try {
        task.submitted = true;
        if (!task.fileMd5) {
            task.status = "hashing";
            task.message = "MD5 計算中";
            task.fileMd5 = await computeMd5WithTimeout(task.file, 30000);
            task.status = "ready";
            task.message = "MD5 計算完了、アップロード開始";
        }
        task.status = "uploading";
        task.message = "チャンクアップロード中";
        const chunkBytes = Math.max(1, chunkSizeMB.value) * 1024 * 1024;
        task.totalChunks = Math.ceil(task.file.size / chunkBytes);
        for (let i = 0; i < task.totalChunks; i += 1) {
            if (task.uploadedChunks.includes(i)) {
                continue;
            }
            const start = i * chunkBytes;
            const end = Math.min(task.file.size, start + chunkBytes);
            const chunkBlob = task.file.slice(start, end);
            const resp = await uploadChunk({
                file: chunkBlob,
                fileMd5: task.fileMd5,
                chunkIndex: i,
                totalSize: task.file.size,
                fileName: task.file.name,
                totalChunks: task.totalChunks,
                orgTag: orgTag.value || undefined,
                isPublic: isPublic.value
            });
            task.uploadedChunks = resp.data.uploaded || task.uploadedChunks;
            task.progress = Number(Math.min(70, (resp.data.progress || 0) * 0.7).toFixed(2));
        }
        task.status = "merging";
        task.progress = Math.max(task.progress, 74);
        task.message = "自動マージ中";
        const merged = await mergeFile(task.fileMd5, task.file.name);
        task.progress = Math.max(task.progress, 78);
        task.status = "processing";
        task.message = `マージ完了（${formatBytes(merged.data.file_size)}）、バックエンド解析中`;
        startStatusPolling();
        return true;
    }
    catch (err) {
        task.status = "failed";
        task.message = err?.response?.data?.detail || err?.response?.data?.message || "アップロード失敗";
        return false;
    }
}
function clearTasks() {
    tasks.value = [];
    stopStatusPolling();
}
function removeTask(id) {
    tasks.value = tasks.value.filter((x) => x.id !== id);
    if (!tasks.value.some((x) => x.status === "processing")) {
        stopStatusPolling();
    }
}
function statusText(status) {
    if (status === "hashing")
        return "計算中";
    if (status === "ready")
        return "送信待ち";
    if (status === "uploading")
        return "アップロード中";
    if (status === "merging")
        return "マージ中";
    if (status === "processing")
        return "バックエンド処理中";
    if (status === "done")
        return "完了";
    return "失敗";
}
function statusType(status) {
    if (status === "done")
        return "success";
    if (status === "processing")
        return "warning";
    if (status === "failed")
        return "danger";
    if (status === "uploading" || status === "merging")
        return "warning";
    return "info";
}
function parseBackendTime(raw) {
    if (!raw) {
        return NaN;
    }
    const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
    const hasTz = /Z|[+\-]\d{2}:\d{2}$/.test(normalized);
    const iso = hasTz ? normalized : `${normalized}Z`;
    return Date.parse(iso);
}
function applyBackendStatus(task, backendStatus, mergedAt, createdAt) {
    const now = Date.now();
    const refTime = mergedAt || createdAt || "";
    const ts = parseBackendTime(refTime);
    const ageSeconds = Number.isNaN(ts) ? 0 : Math.max(0, Math.floor((now - ts) / 1000));
    if (backendStatus === 0) {
        if (task.status !== "uploading") {
            task.status = "uploading";
            task.message = "アップロード進行中";
        }
        task.progress = Math.min(Math.max(task.progress, 5), 70);
        return;
    }
    if (backendStatus === 1 || backendStatus === 2) {
        if (backendStatus === 1 && ageSeconds > 90) {
            task.status = "failed";
            task.progress = Math.max(task.progress, 85);
            task.message = `マージ後 ${ageSeconds}s 経過しても処理未開始です。削除して再アップロードし、バックエンドログを確認してください。`;
            return;
        }
        task.status = "processing";
        if (backendStatus === 1) {
            const stage = Math.min(86, 78 + Math.floor(ageSeconds / 15));
            task.progress = Math.max(task.progress, stage);
            task.message = `マージ済み。バックエンドタスク待機中（${ageSeconds}s）`;
        }
        else {
            const stage = Math.min(99, 86 + Math.floor(ageSeconds / 8));
            task.progress = Math.max(task.progress, stage);
            task.message = "バックエンド解析中";
        }
        return;
    }
    if (backendStatus === 3) {
        task.status = "done";
        task.progress = 100;
        task.message = "ドキュメント処理完了。検索に利用できます。";
        return;
    }
    if (backendStatus === 4) {
        task.status = "failed";
        task.message = "バックエンド処理に失敗しました。ログ確認または再アップロードしてください。";
    }
}
async function syncTaskStatusFromBackend(task) {
    if (!task.fileMd5 || !task.submitted) {
        return;
    }
    try {
        const resp = await getUserUploadedFiles();
        const file = (resp.data || []).find((x) => x.fileMd5 === task.fileMd5);
        if (!file) {
            return;
        }
        applyBackendStatus(task, file.status, file.mergedAt, file.createdAt);
    }
    catch {
    }
}
async function pollProcessingStatus() {
    const pending = tasks.value.filter((x) => x.submitted && x.status === "processing");
    if (!pending.length) {
        stopStatusPolling();
        return;
    }
    try {
        const resp = await getUserUploadedFiles();
        recentUploads.value = (resp.data || []).slice().sort((a, b) => {
            const ta = parseBackendTime(a.createdAt || "") || 0;
            const tb = parseBackendTime(b.createdAt || "") || 0;
            return tb - ta;
        });
        const map = new Map((resp.data || []).map((x) => [x.fileMd5, x]));
        for (const task of pending) {
            const remote = map.get(task.fileMd5);
            if (remote) {
                applyBackendStatus(task, remote.status, remote.mergedAt, remote.createdAt);
            }
        }
        if (!tasks.value.some((x) => x.status === "processing")) {
            stopStatusPolling();
        }
    }
    catch {
    }
}
async function refreshUploadedFiles() {
    historyLoading.value = true;
    try {
        const resp = await getUserUploadedFiles();
        recentUploads.value = (resp.data || []).slice().sort((a, b) => {
            const ta = parseBackendTime(a.createdAt || "") || 0;
            const tb = parseBackendTime(b.createdAt || "") || 0;
            return tb - ta;
        });
    }
    catch (err) {
        const detail = err?.response?.data?.detail || err?.response?.data?.message || "";
        if (err?.response?.status === 401 || err?.response?.status === 403) {
            ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
        }
        else {
            ElMessage.error(detail || "履歴更新に失敗しました");
        }
    }
    finally {
        historyLoading.value = false;
    }
}
function statusTextByCode(code) {
    if (code === 0)
        return "アップロード中";
    if (code === 1)
        return "処理待ち";
    if (code === 2)
        return "処理中";
    if (code === 3)
        return "完了";
    if (code === 4)
        return "失敗";
    return "不明";
}
function statusTypeByCode(code) {
    if (code === 3)
        return "success";
    if (code === 4)
        return "danger";
    if (code === 1 || code === 2)
        return "warning";
    return "info";
}
function statusDescByCode(code) {
    if (code === 0)
        return "チャンクアップロード中";
    if (code === 1)
        return "マージ済み、バックエンド待機中";
    if (code === 2)
        return "バックエンド解析中";
    if (code === 3)
        return "ドキュメント処理完了（検索可）";
    if (code === 4)
        return "バックエンド処理失敗（ログ確認/再アップロード）";
    return "状態不明";
}
function formatProfileName(profileId) {
    if (!profileId) {
        return profile.selectedName || "-";
    }
    const map = {
        general: "汎用ドキュメント",
        design: "設計書・アーキテクチャ",
        policy: "規程・業務プロセス",
        ops: "運用・障害対応"
    };
    return map[profileId] || profileId;
}
async function openEsPreview(item) {
    previewDialogVisible.value = true;
    previewLoading.value = true;
    previewRows.value = [];
    previewTargetName.value = item.fileName;
    try {
        const resp = await getEsPreview(item.fileMd5, 8);
        previewRows.value = resp.data || [];
    }
    catch (err) {
        const detail = err?.response?.data?.detail || err?.response?.data?.message || "ESプレビュー取得に失敗しました";
        ElMessage.error(detail);
    }
    finally {
        previewLoading.value = false;
    }
}
function startStatusPolling() {
    if (statusPollTimer) {
        return;
    }
    statusPollTimer = setInterval(() => {
        void pollProcessingStatus();
    }, 4000);
    void pollProcessingStatus();
}
function stopStatusPolling() {
    if (statusPollTimer) {
        clearInterval(statusPollTimer);
        statusPollTimer = null;
    }
}
function formatBytes(bytes) {
    if (bytes < 1024)
        return `${bytes} B`;
    if (bytes < 1024 * 1024)
        return `${(bytes / 1024).toFixed(2)} KB`;
    if (bytes < 1024 * 1024 * 1024)
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
async function loadOrgTagOptions() {
    try {
        await auth.refreshUserAccessInfo();
        const resp = await getRegisterOrgTags();
        const userTagIds = (auth.orgTags || []).map((x) => x.trim()).filter(Boolean);
        const preferred = (auth.primaryOrg || "").trim();
        const serverOptions = (resp.data || [])
            .filter((x) => !String(x.tagId || "").startsWith("PRIVATE_"));
        const optionMap = new Map();
        for (const item of serverOptions) {
            optionMap.set(item.tagId, item);
        }
        for (const tagId of userTagIds) {
            if (!optionMap.has(tagId)) {
                optionMap.set(tagId, { tagId, name: tagId, description: "" });
            }
        }
        if (!optionMap.has("DEFAULT")) {
            optionMap.set("DEFAULT", {
                tagId: "DEFAULT",
                name: "全体公開",
                description: "全ユーザー共通で参照可能"
            });
        }
        orgTagOptions.value = Array.from(optionMap.values()).sort((a, b) => a.tagId.localeCompare(b.tagId));
        if (preferred && optionMap.has(preferred)) {
            orgTag.value = preferred;
        }
        else if (!orgTag.value && userTagIds.length) {
            orgTag.value = userTagIds[0];
        }
    }
    catch {
        orgTagOptions.value = [
            { tagId: "DEFAULT", name: "全体公開", description: "全ユーザー共通で参照可能" }
        ];
        if (!orgTag.value) {
            orgTag.value = "DEFAULT";
        }
    }
}
onBeforeUnmount(() => {
    stopStatusPolling();
});
onMounted(() => {
    if (!profile.loaded) {
        void profile.refreshFromServer().catch(() => undefined);
    }
    void loadOrgTagOptions();
    void refreshUploadedFiles();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
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
        ...{ class: "header" },
    });
}
if (__VLS_ctx.profile.selectedName) {
    const __VLS_8 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        type: "info",
        showIcon: true,
        closable: (false),
        title: (`現在のシナリオ: ${__VLS_ctx.profile.selectedName}（固定）`),
        ...{ class: "scene-alert" },
    }));
    const __VLS_10 = __VLS_9({
        type: "info",
        showIcon: true,
        closable: (false),
        title: (`現在のシナリオ: ${__VLS_ctx.profile.selectedName}（固定）`),
        ...{ class: "scene-alert" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
const __VLS_12 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    labelWidth: "120px",
}));
const __VLS_14 = __VLS_13({
    labelWidth: "120px",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    label: "ファイル選択",
}));
const __VLS_18 = __VLS_17({
    label: "ファイル選択",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    ...{ onChange: (__VLS_ctx.onFileChange) },
    type: "file",
    multiple: true,
});
var __VLS_19;
const __VLS_20 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    label: "組織タグ",
}));
const __VLS_22 = __VLS_21({
    label: "組織タグ",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    modelValue: (__VLS_ctx.orgTag),
    filterable: true,
    clearable: true,
    ...{ style: {} },
    placeholder: "組織タグを選択",
}));
const __VLS_26 = __VLS_25({
    modelValue: (__VLS_ctx.orgTag),
    filterable: true,
    clearable: true,
    ...{ style: {} },
    placeholder: "組織タグを選択",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.orgTagOptions))) {
    const __VLS_28 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        key: (item.tagId),
        label: (`${item.name} (${item.tagId})`),
        value: (item.tagId),
    }));
    const __VLS_30 = __VLS_29({
        key: (item.tagId),
        label: (`${item.name} (${item.tagId})`),
        value: (item.tagId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
}
var __VLS_27;
var __VLS_23;
const __VLS_32 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    label: "公開ドキュメント",
}));
const __VLS_34 = __VLS_33({
    label: "公開ドキュメント",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.ElSwitch;
/** @type {[typeof __VLS_components.ElSwitch, typeof __VLS_components.elSwitch, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    modelValue: (__VLS_ctx.isPublic),
}));
const __VLS_38 = __VLS_37({
    modelValue: (__VLS_ctx.isPublic),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
var __VLS_35;
const __VLS_40 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    label: "分割サイズ",
}));
const __VLS_42 = __VLS_41({
    label: "分割サイズ",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
const __VLS_44 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    modelValue: (__VLS_ctx.chunkSizeMB),
    modelModifiers: { number: true, },
    type: "number",
    min: "1",
    max: "20",
}));
const __VLS_46 = __VLS_45({
    modelValue: (__VLS_ctx.chunkSizeMB),
    modelModifiers: { number: true, },
    type: "number",
    min: "1",
    max: "20",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
{
    const { append: __VLS_thisSlot } = __VLS_47.slots;
}
var __VLS_47;
var __VLS_43;
var __VLS_15;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "actions" },
});
const __VLS_48 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.submitting),
    disabled: (!__VLS_ctx.tasks.length),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.submitting),
    disabled: (!__VLS_ctx.tasks.length),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.submitAll)
};
__VLS_51.slots.default;
var __VLS_51;
const __VLS_56 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.submitting || !__VLS_ctx.tasks.length),
}));
const __VLS_58 = __VLS_57({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.submitting || !__VLS_ctx.tasks.length),
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onClick: (__VLS_ctx.clearTasks)
};
__VLS_59.slots.default;
var __VLS_59;
if (__VLS_ctx.tasks.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tip empty" },
    });
}
for (const [task] of __VLS_getVForSourceType((__VLS_ctx.tasks))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (task.id),
        ...{ class: "task-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-name" },
    });
    (task.file.name);
    const __VLS_64 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        type: (__VLS_ctx.statusType(task.status)),
    }));
    const __VLS_66 = __VLS_65({
        type: (__VLS_ctx.statusType(task.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    (__VLS_ctx.statusText(task.status));
    var __VLS_67;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-meta" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.formatBytes(task.file.size));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (task.fileMd5 || "計算中...");
    if (task.message) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (task.message);
    }
    const __VLS_68 = {}.ElProgress;
    /** @type {[typeof __VLS_components.ElProgress, typeof __VLS_components.elProgress, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        percentage: (task.progress),
        strokeWidth: (14),
    }));
    const __VLS_70 = __VLS_69({
        percentage: (task.progress),
        strokeWidth: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "tip" },
    });
    (task.uploadedChunks.length);
    (task.totalChunks || "-");
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-actions" },
    });
    const __VLS_72 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ 'onClick': {} },
        size: "small",
        type: "danger",
        disabled: (__VLS_ctx.submitting),
    }));
    const __VLS_74 = __VLS_73({
        ...{ 'onClick': {} },
        size: "small",
        type: "danger",
        disabled: (__VLS_ctx.submitting),
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    let __VLS_76;
    let __VLS_77;
    let __VLS_78;
    const __VLS_79 = {
        onClick: (...[$event]) => {
            __VLS_ctx.removeTask(task.id);
        }
    };
    __VLS_75.slots.default;
    var __VLS_75;
}
const __VLS_80 = {}.ElDivider;
/** @type {[typeof __VLS_components.ElDivider, typeof __VLS_components.elDivider, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "history-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "history-title" },
});
const __VLS_84 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.historyLoading),
}));
const __VLS_86 = __VLS_85({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.historyLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
let __VLS_88;
let __VLS_89;
let __VLS_90;
const __VLS_91 = {
    onClick: (__VLS_ctx.refreshUploadedFiles)
};
__VLS_87.slots.default;
var __VLS_87;
if (__VLS_ctx.recentUploads.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tip empty" },
    });
}
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.recentUploads))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (item.fileMd5),
        ...{ class: "task-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-name" },
    });
    (item.fileName);
    const __VLS_92 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        type: (__VLS_ctx.statusTypeByCode(item.status)),
    }));
    const __VLS_94 = __VLS_93({
        type: (__VLS_ctx.statusTypeByCode(item.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    (__VLS_ctx.statusTextByCode(item.status));
    var __VLS_95;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-meta" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.formatBytes(item.totalSize));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.fileMd5);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.orgTagName || "-");
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.isPublic ? "公開" : "非公開");
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.formatProfileName(item.kbProfile));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.vectorCount || 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.tableRowCount || 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.imageBlockCount || 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.relationNodeCount || 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (item.relationEdgeCount || 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.statusDescByCode(item.status));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-actions" },
    });
    const __VLS_96 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_98 = __VLS_97({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    let __VLS_100;
    let __VLS_101;
    let __VLS_102;
    const __VLS_103 = {
        onClick: (...[$event]) => {
            __VLS_ctx.openEsPreview(item);
        }
    };
    __VLS_99.slots.default;
    var __VLS_99;
}
var __VLS_7;
const __VLS_104 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    modelValue: (__VLS_ctx.previewDialogVisible),
    title: "ES ドキュメントプレビュー",
    width: "760px",
}));
const __VLS_106 = __VLS_105({
    modelValue: (__VLS_ctx.previewDialogVisible),
    title: "ES ドキュメントプレビュー",
    width: "760px",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
if (__VLS_ctx.previewTargetName) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tip" },
        ...{ style: {} },
    });
    (__VLS_ctx.previewTargetName);
}
const __VLS_108 = {}.ElSkeleton;
/** @type {[typeof __VLS_components.ElSkeleton, typeof __VLS_components.elSkeleton, typeof __VLS_components.ElSkeleton, typeof __VLS_components.elSkeleton, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    loading: (__VLS_ctx.previewLoading),
    rows: (5),
    animated: true,
}));
const __VLS_110 = __VLS_109({
    loading: (__VLS_ctx.previewLoading),
    rows: (5),
    animated: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
if (__VLS_ctx.previewRows.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tip" },
    });
}
for (const [row] of __VLS_getVForSourceType((__VLS_ctx.previewRows))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (`${row.chunkId}-${row.page}-${row.sheet}`),
        ...{ class: "preview-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "preview-head" },
    });
    const __VLS_112 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
        size: "small",
        type: "info",
    }));
    const __VLS_114 = __VLS_113({
        size: "small",
        type: "info",
    }, ...__VLS_functionalComponentArgsRest(__VLS_113));
    __VLS_115.slots.default;
    (row.chunkId);
    var __VLS_115;
    if (row.chunkType) {
        const __VLS_116 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
            size: "small",
        }));
        const __VLS_118 = __VLS_117({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        (row.chunkType);
        var __VLS_119;
    }
    if (row.page !== null && row.page !== undefined) {
        const __VLS_120 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            size: "small",
        }));
        const __VLS_122 = __VLS_121({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        (row.page);
        var __VLS_123;
    }
    if (row.sheet) {
        const __VLS_124 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            size: "small",
        }));
        const __VLS_126 = __VLS_125({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        (row.sheet);
        var __VLS_127;
    }
    const __VLS_128 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        size: "small",
        type: "success",
    }));
    const __VLS_130 = __VLS_129({
        size: "small",
        type: "success",
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_131.slots.default;
    (row.score.toFixed(3));
    var __VLS_131;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "preview-text" },
    });
    (row.textPreview || "-");
}
var __VLS_111;
var __VLS_107;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['scene-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['tip']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['task-card']} */ ;
/** @type {__VLS_StyleScopedClasses['task-head']} */ ;
/** @type {__VLS_StyleScopedClasses['task-name']} */ ;
/** @type {__VLS_StyleScopedClasses['task-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['tip']} */ ;
/** @type {__VLS_StyleScopedClasses['task-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['history-header']} */ ;
/** @type {__VLS_StyleScopedClasses['history-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tip']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['task-card']} */ ;
/** @type {__VLS_StyleScopedClasses['task-head']} */ ;
/** @type {__VLS_StyleScopedClasses['task-name']} */ ;
/** @type {__VLS_StyleScopedClasses['task-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['task-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['tip']} */ ;
/** @type {__VLS_StyleScopedClasses['tip']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-row']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-head']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-text']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            orgTag: orgTag,
            orgTagOptions: orgTagOptions,
            isPublic: isPublic,
            chunkSizeMB: chunkSizeMB,
            profile: profile,
            tasks: tasks,
            submitting: submitting,
            historyLoading: historyLoading,
            recentUploads: recentUploads,
            previewDialogVisible: previewDialogVisible,
            previewLoading: previewLoading,
            previewRows: previewRows,
            previewTargetName: previewTargetName,
            onFileChange: onFileChange,
            submitAll: submitAll,
            clearTasks: clearTasks,
            removeTask: removeTask,
            statusText: statusText,
            statusType: statusType,
            refreshUploadedFiles: refreshUploadedFiles,
            statusTextByCode: statusTextByCode,
            statusTypeByCode: statusTypeByCode,
            statusDescByCode: statusDescByCode,
            formatProfileName: formatProfileName,
            openEsPreview: openEsPreview,
            formatBytes: formatBytes,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
