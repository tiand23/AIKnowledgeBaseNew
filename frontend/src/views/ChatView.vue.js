import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { useAuthStore } from "../stores/auth";
import { useProfileStore } from "../stores/profile";
import { getEsPreview, getSourceDetail, getUserUploadedFiles } from "../api/file";
const auth = useAuthStore();
const profile = useProfileStore();
const wsRef = ref(null);
const connected = ref(false);
const connecting = ref(false);
const inputText = ref("");
const messages = ref([]);
const messagesBox = ref(null);
const pendingAssistantIndex = ref(null);
const sourceDialogVisible = ref(false);
const sourceLoading = ref(false);
const sourceDialogTitle = ref("");
const sourcePreviewRows = ref([]);
const sourceOriginalUrl = ref("");
const sourceImageUrls = ref([]);
const globalEvidenceDialogVisible = ref(false);
const globalEvidenceLoading = ref(false);
const globalEvidenceActiveTab = ref("files");
const globalEvidenceFiles = ref([]);
const globalStructuredRows = ref([]);
const globalImageRows = ref([]);
const evidenceDialogVisible = ref(false);
const evidenceLoading = ref(false);
const evidenceActiveTab = ref("summary");
const evidenceItems = ref([]);
const evidenceStructuredRows = computed(() => {
    const rows = [];
    for (const item of evidenceItems.value) {
        for (const row of item.previewRows || []) {
            rows.push({
                ...row,
                fileName: item.ref.fileName || "-",
            });
        }
    }
    return rows;
});
const evidenceImages = computed(() => {
    const rows = [];
    for (const item of evidenceItems.value) {
        for (const url of item.imageUrls || []) {
            rows.push({
                url,
                fileName: item.ref.fileName || "-",
                location: item.ref.location || "該当箇所",
            });
        }
    }
    return rows;
});
function extractSourceRefs(text) {
    const refs = [];
    const seen = new Set();
    const re = /\[\[SRC\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^\]]*)\]\]/g;
    let m;
    while ((m = re.exec(text)) !== null) {
        const index = (m[1] || "").trim();
        const fileName = (m[2] || "").trim();
        const fileMd5 = (m[3] || "").trim();
        const chunkId = (m[4] || "").trim();
        const page = (m[5] || "").trim();
        const sheet = (m[6] || "").trim();
        const locationParts = [];
        if (page)
            locationParts.push(`page=${page}`);
        if (sheet)
            locationParts.push(`sheet=${sheet}`);
        const location = locationParts.length ? locationParts.join(" / ") : "該当箇所";
        if (!fileMd5)
            continue;
        const dedupKey = `${fileMd5}::${chunkId}::${page}::${sheet}`;
        if (seen.has(dedupKey))
            continue;
        seen.add(dedupKey);
        refs.push({ index, fileName, fileMd5, chunkId, page, sheet, location });
    }
    return refs;
}
function stripSourceTags(text) {
    let out = text.replace(/\n?\[\[SRC\|[^\]]+\]\]/g, "");
    out = out.replace(/\n*根拠（システム引用）[\s\S]*$/m, "");
    out = out.replace(/\n*根拠\s*\(システム引用\)\s*[\s\S]*$/m, "");
    return out.trimEnd();
}
async function openEvidencePanel(content) {
    const refs = extractSourceRefs(content);
    if (!refs.length) {
        ElMessage.warning("表示可能な証拠がありません");
        return;
    }
    evidenceDialogVisible.value = true;
    evidenceLoading.value = true;
    evidenceActiveTab.value = "summary";
    evidenceItems.value = [];
    try {
        const dedup = new Set();
        const tasks = [];
        for (const refItem of refs) {
            const key = `${refItem.fileMd5}::${refItem.chunkId}::${refItem.page}::${refItem.sheet}`;
            if (dedup.has(key))
                continue;
            dedup.add(key);
            tasks.push(getSourceDetail({
                fileMd5: refItem.fileMd5,
                chunkId: refItem.chunkId,
                page: refItem.page,
                sheet: refItem.sheet,
                size: 10,
            })
                .then((resp) => {
                const rawOriginalUrl = resp.data?.originalUrl || "";
                const rawImageUrls = resp.data?.imageUrls || [];
                const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
                const withToken = (url) => {
                    if (!url || !tokenQuery)
                        return url;
                    return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
                };
                return {
                    ref: refItem,
                    previewRows: (resp.data?.previewRows || []),
                    originalUrl: withToken(rawOriginalUrl),
                    imageUrls: rawImageUrls.map((u) => withToken(u)),
                };
            })
                .catch(() => null));
        }
        const results = await Promise.all(tasks);
        evidenceItems.value = results.filter((x) => !!x);
        if (!evidenceItems.value.length) {
            ElMessage.warning("証拠データを取得できませんでした");
        }
    }
    finally {
        evidenceLoading.value = false;
    }
}
async function openGlobalEvidencePanel() {
    globalEvidenceDialogVisible.value = true;
    globalEvidenceLoading.value = true;
    globalEvidenceActiveTab.value = "files";
    globalEvidenceFiles.value = [];
    globalStructuredRows.value = [];
    globalImageRows.value = [];
    try {
        const listResp = await getUserUploadedFiles();
        const files = (listResp.data || []);
        globalEvidenceFiles.value = files;
        const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
        const withToken = (url) => {
            if (!url || !tokenQuery)
                return url;
            return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
        };
        const tasks = files.slice(0, 20).map(async (file) => {
            const md5 = file.fileMd5;
            const [esResp, srcResp] = await Promise.all([
                getEsPreview(md5, 12).catch(() => ({ data: [] })),
                getSourceDetail({ fileMd5: md5, size: 12 }).catch(() => ({ data: { imageUrls: [] } })),
            ]);
            const rows = (esResp.data || []);
            for (const row of rows) {
                globalStructuredRows.value.push({
                    ...row,
                    fileName: file.fileName,
                });
            }
            const imageUrls = (srcResp.data?.imageUrls || []);
            for (const url of imageUrls) {
                globalImageRows.value.push({
                    fileName: file.fileName,
                    url: withToken(url),
                });
            }
        });
        await Promise.all(tasks);
    }
    catch {
        ElMessage.error("全体証拠データの取得に失敗しました");
    }
    finally {
        globalEvidenceLoading.value = false;
    }
}
async function openSource(refItem) {
    sourceDialogVisible.value = true;
    sourceLoading.value = true;
    sourceDialogTitle.value = `${refItem.fileName} / ${refItem.location}`;
    sourcePreviewRows.value = [];
    sourceOriginalUrl.value = "";
    sourceImageUrls.value = [];
    try {
        const resp = await getSourceDetail({
            fileMd5: refItem.fileMd5,
            chunkId: refItem.chunkId,
            page: refItem.page,
            sheet: refItem.sheet,
            size: 10,
        });
        sourcePreviewRows.value = (resp.data?.previewRows || []);
        const rawOriginalUrl = resp.data?.originalUrl || "";
        const rawImageUrls = resp.data?.imageUrls || [];
        const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
        const withToken = (url) => {
            if (!url || !tokenQuery)
                return url;
            return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
        };
        sourceOriginalUrl.value = withToken(rawOriginalUrl);
        sourceImageUrls.value = rawImageUrls.map((u) => withToken(u));
    }
    catch (e) {
        ElMessage.error("根拠プレビューの取得に失敗しました");
    }
    finally {
        sourceLoading.value = false;
    }
}
function wsUrl() {
    const resolvedHost = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
    const fallbackBase = `${window.location.protocol === "https:" ? "wss" : "ws"}://${resolvedHost}:8000`;
    const base = import.meta.env.VITE_WS_BASE_URL || fallbackBase;
    return `${base}/api/v1/chat?token=${encodeURIComponent(auth.token)}`;
}
function connect() {
    if (!auth.token) {
        ElMessage.warning("先にログインしてください");
        return;
    }
    if ((wsRef.value && connected.value) || connecting.value) {
        return;
    }
    connecting.value = true;
    const ws = new WebSocket(wsUrl());
    wsRef.value = ws;
    ws.onopen = () => {
    };
    ws.onclose = (event) => {
        connecting.value = false;
        connected.value = false;
        wsRef.value = null;
        if (event.code === 1008) {
            ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
        }
    };
    ws.onerror = () => {
        connecting.value = false;
        connected.value = false;
        ElMessage.error("WebSocket 接続エラー");
    };
    ws.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "ping") {
                ws.send(JSON.stringify({ type: "pong" }));
                return;
            }
            if (data.type === "connected") {
                connecting.value = false;
                connected.value = true;
                ElMessage.success("WebSocket 接続完了");
                return;
            }
            if (data.error) {
                ElMessage.error(data.error);
                return;
            }
            if (typeof data.chunk === "string") {
                if (pendingAssistantIndex.value === null) {
                    messages.value.push({ role: "assistant", content: data.chunk });
                    pendingAssistantIndex.value = messages.value.length - 1;
                }
                else {
                    messages.value[pendingAssistantIndex.value].content += data.chunk;
                }
                await scrollBottom();
            }
            if (data.type === "completion") {
                pendingAssistantIndex.value = null;
            }
        }
        catch {
            // ignore non-json frames
        }
    };
}
function disconnect() {
    if (wsRef.value) {
        wsRef.value.close();
        wsRef.value = null;
    }
    connecting.value = false;
    connected.value = false;
}
function sendMessage() {
    const text = inputText.value.trim();
    if (!text) {
        return;
    }
    if (!auth.token) {
        ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
        return;
    }
    if (!wsRef.value || !connected.value) {
        connect();
        ElMessage.warning("接続中です。少し待ってから送信してください。");
        return;
    }
    messages.value.push({ role: "user", content: text });
    wsRef.value.send(text);
    inputText.value = "";
    pendingAssistantIndex.value = null;
    void scrollBottom();
}
async function scrollBottom() {
    await nextTick();
    if (messagesBox.value) {
        messagesBox.value.scrollTop = messagesBox.value.scrollHeight;
    }
}
onBeforeUnmount(() => {
    disconnect();
});
onMounted(() => {
    if (!profile.loaded) {
        void profile.refreshFromServer().catch(() => undefined);
    }
    if (auth.token) {
        connect();
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['msg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['user']} */ ;
/** @type {__VLS_StyleScopedClasses['bubble']} */ ;
// CSS variable injection 
// CSS variable injection end 
/** @type {[typeof AppLayout, typeof AppLayout, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(AppLayout, new AppLayout({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
var __VLS_3 = {};
__VLS_2.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-wrap chat-page" },
});
const __VLS_4 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "chat-card" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "chat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_7.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-title-wrap" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    if (__VLS_ctx.profile.selectedName) {
        const __VLS_8 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
            type: "info",
            effect: "plain",
        }));
        const __VLS_10 = __VLS_9({
            type: "info",
            effect: "plain",
        }, ...__VLS_functionalComponentArgsRest(__VLS_9));
        __VLS_11.slots.default;
        (__VLS_ctx.profile.selectedName);
        var __VLS_11;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    if (__VLS_ctx.connected) {
        const __VLS_12 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
            type: "success",
            effect: "light",
            ...{ style: {} },
        }));
        const __VLS_14 = __VLS_13({
            type: "success",
            effect: "light",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        __VLS_15.slots.default;
        var __VLS_15;
    }
    else if (__VLS_ctx.connecting) {
        const __VLS_16 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            type: "warning",
            effect: "light",
            ...{ style: {} },
        }));
        const __VLS_18 = __VLS_17({
            type: "warning",
            effect: "light",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        __VLS_19.slots.default;
        var __VLS_19;
    }
    else {
        const __VLS_20 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
            type: "info",
            effect: "light",
            ...{ style: {} },
        }));
        const __VLS_22 = __VLS_21({
            type: "info",
            effect: "light",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
        __VLS_23.slots.default;
        var __VLS_23;
    }
    const __VLS_24 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        size: "small",
        disabled: (__VLS_ctx.connected || __VLS_ctx.connecting),
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        size: "small",
        disabled: (__VLS_ctx.connected || __VLS_ctx.connecting),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_28;
    let __VLS_29;
    let __VLS_30;
    const __VLS_31 = {
        onClick: (__VLS_ctx.connect)
    };
    __VLS_27.slots.default;
    var __VLS_27;
    const __VLS_32 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        ...{ 'onClick': {} },
        size: "small",
        type: "warning",
        disabled: (!__VLS_ctx.connected && !__VLS_ctx.connecting),
    }));
    const __VLS_34 = __VLS_33({
        ...{ 'onClick': {} },
        size: "small",
        type: "warning",
        disabled: (!__VLS_ctx.connected && !__VLS_ctx.connecting),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    let __VLS_36;
    let __VLS_37;
    let __VLS_38;
    const __VLS_39 = {
        onClick: (__VLS_ctx.disconnect)
    };
    __VLS_35.slots.default;
    var __VLS_35;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "messages" },
    ref: "messagesBox",
});
/** @type {typeof __VLS_ctx.messagesBox} */ ;
for (const [msg, idx] of __VLS_getVForSourceType((__VLS_ctx.messages))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (idx),
        ...{ class: "msg-row" },
        ...{ class: (msg.role) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bubble" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "role" },
    });
    (msg.role === 'user' ? 'あなた' : 'アシスタント');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content" },
    });
    (__VLS_ctx.stripSourceTags(msg.content));
    if (msg.role === 'assistant' && __VLS_ctx.extractSourceRefs(msg.content).length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-links" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-actions" },
        });
        const __VLS_40 = {}.ElButton;
        /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_42 = __VLS_41({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        let __VLS_44;
        let __VLS_45;
        let __VLS_46;
        const __VLS_47 = {
            onClick: (...[$event]) => {
                if (!(msg.role === 'assistant' && __VLS_ctx.extractSourceRefs(msg.content).length))
                    return;
                __VLS_ctx.openEvidencePanel(msg.content);
            }
        };
        __VLS_43.slots.default;
        var __VLS_43;
        for (const [refItem, rIdx] of __VLS_getVForSourceType((__VLS_ctx.extractSourceRefs(msg.content)))) {
            const __VLS_48 = {}.ElLink;
            /** @type {[typeof __VLS_components.ElLink, typeof __VLS_components.elLink, typeof __VLS_components.ElLink, typeof __VLS_components.elLink, ]} */ ;
            // @ts-ignore
            const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
                ...{ 'onClick': {} },
                key: (`${idx}-${rIdx}`),
                type: "primary",
                underline: (false),
            }));
            const __VLS_50 = __VLS_49({
                ...{ 'onClick': {} },
                key: (`${idx}-${rIdx}`),
                type: "primary",
                underline: (false),
            }, ...__VLS_functionalComponentArgsRest(__VLS_49));
            let __VLS_52;
            let __VLS_53;
            let __VLS_54;
            const __VLS_55 = {
                onClick: (...[$event]) => {
                    if (!(msg.role === 'assistant' && __VLS_ctx.extractSourceRefs(msg.content).length))
                        return;
                    __VLS_ctx.openSource(refItem);
                }
            };
            __VLS_51.slots.default;
            (refItem.index);
            (refItem.fileName);
            (refItem.location);
            var __VLS_51;
        }
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "input-row" },
});
const __VLS_56 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.inputText),
    type: "textarea",
    rows: (3),
    placeholder: "質問を入力して送信",
}));
const __VLS_58 = __VLS_57({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.inputText),
    type: "textarea",
    rows: (3),
    placeholder: "質問を入力して送信",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onKeydown: (__VLS_ctx.sendMessage)
};
var __VLS_59;
const __VLS_64 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    ...{ 'onClick': {} },
    type: "primary",
    disabled: (__VLS_ctx.connecting || !__VLS_ctx.inputText.trim()),
}));
const __VLS_66 = __VLS_65({
    ...{ 'onClick': {} },
    type: "primary",
    disabled: (__VLS_ctx.connecting || !__VLS_ctx.inputText.trim()),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
let __VLS_68;
let __VLS_69;
let __VLS_70;
const __VLS_71 = {
    onClick: (__VLS_ctx.sendMessage)
};
__VLS_67.slots.default;
var __VLS_67;
var __VLS_7;
const __VLS_72 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    modelValue: (__VLS_ctx.evidenceDialogVisible),
    title: "証拠パネル",
    width: "920px",
}));
const __VLS_74 = __VLS_73({
    modelValue: (__VLS_ctx.evidenceDialogVisible),
    title: "証拠パネル",
    width: "920px",
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
if (__VLS_ctx.evidenceLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_76 = {}.ElTabs;
    /** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        modelValue: (__VLS_ctx.evidenceActiveTab),
    }));
    const __VLS_78 = __VLS_77({
        modelValue: (__VLS_ctx.evidenceActiveTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    const __VLS_80 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        label: "概要",
        name: "summary",
    }));
    const __VLS_82 = __VLS_81({
        label: "概要",
        name: "summary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "source-title" },
        ...{ style: {} },
    });
    (__VLS_ctx.evidenceItems.length);
    for (const [item, idx] of __VLS_getVForSourceType((__VLS_ctx.evidenceItems))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (`summary-${idx}`),
            ...{ class: "preview-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "preview-meta" },
        });
        (item.ref.index);
        (item.ref.fileName);
        (item.ref.location);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "preview-text" },
        });
        (item.ref.chunkId || "-");
        (item.ref.page || "-");
        (item.ref.sheet || "-");
    }
    var __VLS_83;
    const __VLS_84 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        label: "構造化データ",
        name: "structured",
    }));
    const __VLS_86 = __VLS_85({
        label: "構造化データ",
        name: "structured",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    if (!__VLS_ctx.evidenceStructuredRows.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "structured-table-wrap" },
        });
        const __VLS_88 = {}.ElTable;
        /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
            data: (__VLS_ctx.evidenceStructuredRows),
            size: "small",
            border: true,
            maxHeight: "420",
        }));
        const __VLS_90 = __VLS_89({
            data: (__VLS_ctx.evidenceStructuredRows),
            size: "small",
            border: true,
            maxHeight: "420",
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        __VLS_91.slots.default;
        const __VLS_92 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            prop: "fileName",
            label: "文書",
            minWidth: "180",
        }));
        const __VLS_94 = __VLS_93({
            prop: "fileName",
            label: "文書",
            minWidth: "180",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        const __VLS_96 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            prop: "chunkType",
            label: "種別",
            minWidth: "120",
        }));
        const __VLS_98 = __VLS_97({
            prop: "chunkType",
            label: "種別",
            minWidth: "120",
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        const __VLS_100 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            prop: "chunkId",
            label: "chunk",
            width: "84",
        }));
        const __VLS_102 = __VLS_101({
            prop: "chunkId",
            label: "chunk",
            width: "84",
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        const __VLS_104 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            prop: "page",
            label: "page",
            width: "84",
        }));
        const __VLS_106 = __VLS_105({
            prop: "page",
            label: "page",
            width: "84",
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        const __VLS_108 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            prop: "sheet",
            label: "sheet",
            minWidth: "140",
        }));
        const __VLS_110 = __VLS_109({
            prop: "sheet",
            label: "sheet",
            minWidth: "140",
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        const __VLS_112 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            prop: "textPreview",
            label: "内容",
            minWidth: "260",
            showOverflowTooltip: true,
        }));
        const __VLS_114 = __VLS_113({
            prop: "textPreview",
            label: "内容",
            minWidth: "260",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        var __VLS_91;
    }
    var __VLS_87;
    const __VLS_116 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        label: "画像",
        name: "images",
    }));
    const __VLS_118 = __VLS_117({
        label: "画像",
        name: "images",
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    __VLS_119.slots.default;
    if (!__VLS_ctx.evidenceImages.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "evidence-images" },
        });
        for (const [img, idx] of __VLS_getVForSourceType((__VLS_ctx.evidenceImages))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (`img-${idx}`),
                ...{ class: "evidence-image-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "preview-meta" },
            });
            (img.fileName);
            (img.location);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
                href: (img.url),
                target: "_blank",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (img.url),
                alt: "evidence image",
                ...{ class: "evidence-image" },
            });
        }
    }
    var __VLS_119;
    const __VLS_120 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        label: "ソースマップ",
        name: "mapping",
    }));
    const __VLS_122 = __VLS_121({
        label: "ソースマップ",
        name: "mapping",
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    __VLS_123.slots.default;
    if (!__VLS_ctx.evidenceItems.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        for (const [item, idx] of __VLS_getVForSourceType((__VLS_ctx.evidenceItems))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (`map-${idx}`),
                ...{ class: "preview-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "preview-meta" },
            });
            (item.ref.index);
            (item.ref.fileName);
            (item.ref.location);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "preview-text" },
            });
            (item.ref.fileMd5);
            (item.ref.chunkId || "-");
            (item.ref.page || "-");
            (item.ref.sheet || "-");
            if (item.originalUrl) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ style: {} },
                });
                const __VLS_124 = {}.ElLink;
                /** @type {[typeof __VLS_components.ElLink, typeof __VLS_components.elLink, typeof __VLS_components.ElLink, typeof __VLS_components.elLink, ]} */ ;
                // @ts-ignore
                const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
                    type: "primary",
                    href: (item.originalUrl),
                    target: "_blank",
                }));
                const __VLS_126 = __VLS_125({
                    type: "primary",
                    href: (item.originalUrl),
                    target: "_blank",
                }, ...__VLS_functionalComponentArgsRest(__VLS_125));
                __VLS_127.slots.default;
                var __VLS_127;
            }
        }
    }
    var __VLS_123;
    var __VLS_79;
}
var __VLS_75;
const __VLS_128 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    modelValue: (__VLS_ctx.globalEvidenceDialogVisible),
    title: "全体構造化データ / 画像",
    width: "1040px",
}));
const __VLS_130 = __VLS_129({
    modelValue: (__VLS_ctx.globalEvidenceDialogVisible),
    title: "全体構造化データ / 画像",
    width: "1040px",
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
if (__VLS_ctx.globalEvidenceLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_132 = {}.ElTabs;
    /** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        modelValue: (__VLS_ctx.globalEvidenceActiveTab),
    }));
    const __VLS_134 = __VLS_133({
        modelValue: (__VLS_ctx.globalEvidenceActiveTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    const __VLS_136 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        label: "文書一覧",
        name: "files",
    }));
    const __VLS_138 = __VLS_137({
        label: "文書一覧",
        name: "files",
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    const __VLS_140 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
        data: (__VLS_ctx.globalEvidenceFiles),
        size: "small",
        border: true,
        maxHeight: "380",
    }));
    const __VLS_142 = __VLS_141({
        data: (__VLS_ctx.globalEvidenceFiles),
        size: "small",
        border: true,
        maxHeight: "380",
    }, ...__VLS_functionalComponentArgsRest(__VLS_141));
    __VLS_143.slots.default;
    const __VLS_144 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        prop: "fileName",
        label: "文書名",
        minWidth: "220",
    }));
    const __VLS_146 = __VLS_145({
        prop: "fileName",
        label: "文書名",
        minWidth: "220",
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    const __VLS_148 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        prop: "kbProfile",
        label: "シナリオ",
        width: "160",
    }));
    const __VLS_150 = __VLS_149({
        prop: "kbProfile",
        label: "シナリオ",
        width: "160",
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    const __VLS_152 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        prop: "vectorCount",
        label: "vector",
        width: "90",
    }));
    const __VLS_154 = __VLS_153({
        prop: "vectorCount",
        label: "vector",
        width: "90",
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    const __VLS_156 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        prop: "tableRowCount",
        label: "table",
        width: "90",
    }));
    const __VLS_158 = __VLS_157({
        prop: "tableRowCount",
        label: "table",
        width: "90",
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    const __VLS_160 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        prop: "imageBlockCount",
        label: "image",
        width: "90",
    }));
    const __VLS_162 = __VLS_161({
        prop: "imageBlockCount",
        label: "image",
        width: "90",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    const __VLS_164 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        prop: "relationEdgeCount",
        label: "relation",
        width: "100",
    }));
    const __VLS_166 = __VLS_165({
        prop: "relationEdgeCount",
        label: "relation",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    var __VLS_143;
    var __VLS_139;
    const __VLS_168 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        label: "構造化データ(全体)",
        name: "structured",
    }));
    const __VLS_170 = __VLS_169({
        label: "構造化データ(全体)",
        name: "structured",
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    if (!__VLS_ctx.globalStructuredRows.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    else {
        const __VLS_172 = {}.ElTable;
        /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
            data: (__VLS_ctx.globalStructuredRows),
            size: "small",
            border: true,
            maxHeight: "420",
        }));
        const __VLS_174 = __VLS_173({
            data: (__VLS_ctx.globalStructuredRows),
            size: "small",
            border: true,
            maxHeight: "420",
        }, ...__VLS_functionalComponentArgsRest(__VLS_173));
        __VLS_175.slots.default;
        const __VLS_176 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
            prop: "fileName",
            label: "文書",
            minWidth: "180",
        }));
        const __VLS_178 = __VLS_177({
            prop: "fileName",
            label: "文書",
            minWidth: "180",
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
        const __VLS_180 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
            prop: "chunkType",
            label: "種別",
            minWidth: "120",
        }));
        const __VLS_182 = __VLS_181({
            prop: "chunkType",
            label: "種別",
            minWidth: "120",
        }, ...__VLS_functionalComponentArgsRest(__VLS_181));
        const __VLS_184 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            prop: "chunkId",
            label: "chunk",
            width: "84",
        }));
        const __VLS_186 = __VLS_185({
            prop: "chunkId",
            label: "chunk",
            width: "84",
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
        const __VLS_188 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
            prop: "page",
            label: "page",
            width: "84",
        }));
        const __VLS_190 = __VLS_189({
            prop: "page",
            label: "page",
            width: "84",
        }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        const __VLS_192 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
            prop: "sheet",
            label: "sheet",
            minWidth: "140",
        }));
        const __VLS_194 = __VLS_193({
            prop: "sheet",
            label: "sheet",
            minWidth: "140",
        }, ...__VLS_functionalComponentArgsRest(__VLS_193));
        const __VLS_196 = {}.ElTableColumn;
        /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
        // @ts-ignore
        const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
            prop: "textPreview",
            label: "内容",
            minWidth: "280",
            showOverflowTooltip: true,
        }));
        const __VLS_198 = __VLS_197({
            prop: "textPreview",
            label: "内容",
            minWidth: "280",
            showOverflowTooltip: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_197));
        var __VLS_175;
    }
    var __VLS_171;
    const __VLS_200 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        label: "画像(全体)",
        name: "images",
    }));
    const __VLS_202 = __VLS_201({
        label: "画像(全体)",
        name: "images",
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    __VLS_203.slots.default;
    if (!__VLS_ctx.globalImageRows.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "evidence-images" },
        });
        for (const [img, idx] of __VLS_getVForSourceType((__VLS_ctx.globalImageRows))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (`gimg-${idx}`),
                ...{ class: "evidence-image-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "preview-meta" },
            });
            (img.fileName);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
                href: (img.url),
                target: "_blank",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (img.url),
                alt: "global evidence image",
                ...{ class: "evidence-image" },
            });
        }
    }
    var __VLS_203;
    var __VLS_135;
}
var __VLS_131;
const __VLS_204 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
    modelValue: (__VLS_ctx.sourceDialogVisible),
    title: "根拠プレビュー",
    width: "760px",
}));
const __VLS_206 = __VLS_205({
    modelValue: (__VLS_ctx.sourceDialogVisible),
    title: "根拠プレビュー",
    width: "760px",
}, ...__VLS_functionalComponentArgsRest(__VLS_205));
__VLS_207.slots.default;
if (__VLS_ctx.sourceLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    (__VLS_ctx.sourceDialogTitle);
    if (__VLS_ctx.sourceOriginalUrl) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ style: {} },
        });
        const __VLS_208 = {}.ElLink;
        /** @type {[typeof __VLS_components.ElLink, typeof __VLS_components.elLink, typeof __VLS_components.ElLink, typeof __VLS_components.elLink, ]} */ ;
        // @ts-ignore
        const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
            type: "primary",
            href: (__VLS_ctx.sourceOriginalUrl),
            target: "_blank",
        }));
        const __VLS_210 = __VLS_209({
            type: "primary",
            href: (__VLS_ctx.sourceOriginalUrl),
            target: "_blank",
        }, ...__VLS_functionalComponentArgsRest(__VLS_209));
        __VLS_211.slots.default;
        var __VLS_211;
    }
    if (__VLS_ctx.sourceImageUrls.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-title" },
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ style: {} },
        });
        for (const [u, i] of __VLS_getVForSourceType((__VLS_ctx.sourceImageUrls))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
                key: (`img-${i}`),
                href: (u),
                target: "_blank",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
                src: (u),
                alt: "source image",
                ...{ style: {} },
            });
        }
    }
    if (__VLS_ctx.sourcePreviewRows.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    for (const [row, i] of __VLS_getVForSourceType((__VLS_ctx.sourcePreviewRows))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (i),
            ...{ class: "preview-row" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "preview-meta" },
        });
        (row.chunkId);
        (row.page ?? "-");
        (row.sheet ?? "-");
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "preview-text" },
        });
        (row.textPreview);
    }
}
var __VLS_207;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-page']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-header']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-title-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['messages']} */ ;
/** @type {__VLS_StyleScopedClasses['msg-row']} */ ;
/** @type {__VLS_StyleScopedClasses['bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['role']} */ ;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['source-links']} */ ;
/** @type {__VLS_StyleScopedClasses['source-title']} */ ;
/** @type {__VLS_StyleScopedClasses['source-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['input-row']} */ ;
/** @type {__VLS_StyleScopedClasses['source-title']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-row']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-text']} */ ;
/** @type {__VLS_StyleScopedClasses['structured-table-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-images']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-image-card']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-image']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-row']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-text']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-images']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-image-card']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-image']} */ ;
/** @type {__VLS_StyleScopedClasses['source-title']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-row']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['preview-text']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            profile: profile,
            connected: connected,
            connecting: connecting,
            inputText: inputText,
            messages: messages,
            messagesBox: messagesBox,
            sourceDialogVisible: sourceDialogVisible,
            sourceLoading: sourceLoading,
            sourceDialogTitle: sourceDialogTitle,
            sourcePreviewRows: sourcePreviewRows,
            sourceOriginalUrl: sourceOriginalUrl,
            sourceImageUrls: sourceImageUrls,
            globalEvidenceDialogVisible: globalEvidenceDialogVisible,
            globalEvidenceLoading: globalEvidenceLoading,
            globalEvidenceActiveTab: globalEvidenceActiveTab,
            globalEvidenceFiles: globalEvidenceFiles,
            globalStructuredRows: globalStructuredRows,
            globalImageRows: globalImageRows,
            evidenceDialogVisible: evidenceDialogVisible,
            evidenceLoading: evidenceLoading,
            evidenceActiveTab: evidenceActiveTab,
            evidenceItems: evidenceItems,
            evidenceStructuredRows: evidenceStructuredRows,
            evidenceImages: evidenceImages,
            extractSourceRefs: extractSourceRefs,
            stripSourceTags: stripSourceTags,
            openEvidencePanel: openEvidencePanel,
            openSource: openSource,
            connect: connect,
            disconnect: disconnect,
            sendMessage: sendMessage,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
