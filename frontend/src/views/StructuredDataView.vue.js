import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getEsPreview, getSourceDetail, getUserUploadedFiles } from "../api/file";
import { useAuthStore } from "../stores/auth";
const auth = useAuthStore();
const activeTab = ref("files");
const loading = ref(false);
const files = ref([]);
const structuredRows = ref([]);
const imageRows = ref([]);
function withToken(url) {
    const tokenQuery = auth.token ? `token=${encodeURIComponent(auth.token)}` : "";
    if (!url || !tokenQuery)
        return url;
    return url.includes("?") ? `${url}&${tokenQuery}` : `${url}?${tokenQuery}`;
}
async function loadAll() {
    loading.value = true;
    files.value = [];
    structuredRows.value = [];
    imageRows.value = [];
    try {
        const listResp = await getUserUploadedFiles();
        const rows = (listResp.data || []);
        files.value = rows;
        const tasks = rows.slice(0, 30).map(async (file) => {
            const md5 = file.fileMd5;
            const [esResp, srcResp] = await Promise.all([
                getEsPreview(md5, 12).catch(() => ({ data: [] })),
                getSourceDetail({ fileMd5: md5, size: 12 }).catch(() => ({ data: { imageUrls: [] } })),
            ]);
            for (const r of (esResp.data || [])) {
                structuredRows.value.push({ ...r, fileName: file.fileName });
            }
            for (const u of (srcResp.data?.imageUrls || [])) {
                imageRows.value.push({ fileName: file.fileName, url: withToken(u) });
            }
        });
        await Promise.all(tasks);
    }
    catch (e) {
        ElMessage.error(e?.response?.data?.detail || e?.message || "全体構造化データの取得に失敗しました");
    }
    finally {
        loading.value = false;
    }
}
onMounted(() => {
    void loadAll();
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
        ...{ class: "header-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "title" },
    });
    const __VLS_8 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_12;
    let __VLS_13;
    let __VLS_14;
    const __VLS_15 = {
        onClick: (__VLS_ctx.loadAll)
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
    title: "アップロード済み文書から、全体の構造化データと画像を表示します。",
    ...{ class: "hint" },
}));
const __VLS_18 = __VLS_17({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "アップロード済み文書から、全体の構造化データと画像を表示します。",
    ...{ class: "hint" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
const __VLS_20 = {}.ElTabs;
/** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.activeTab),
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.activeTab),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    label: "文書一覧",
    name: "files",
}));
const __VLS_26 = __VLS_25({
    label: "文書一覧",
    name: "files",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    data: (__VLS_ctx.files),
    size: "small",
    border: true,
    maxHeight: "520",
}));
const __VLS_30 = __VLS_29({
    data: (__VLS_ctx.files),
    size: "small",
    border: true,
    maxHeight: "520",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    prop: "fileName",
    label: "文書名",
    minWidth: "240",
}));
const __VLS_34 = __VLS_33({
    prop: "fileName",
    label: "文書名",
    minWidth: "240",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
const __VLS_36 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    prop: "kbProfile",
    label: "シナリオ",
    width: "150",
}));
const __VLS_38 = __VLS_37({
    prop: "kbProfile",
    label: "シナリオ",
    width: "150",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
const __VLS_40 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    prop: "vectorCount",
    label: "vector",
    width: "90",
}));
const __VLS_42 = __VLS_41({
    prop: "vectorCount",
    label: "vector",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
const __VLS_44 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    prop: "tableRowCount",
    label: "table",
    width: "90",
}));
const __VLS_46 = __VLS_45({
    prop: "tableRowCount",
    label: "table",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
const __VLS_48 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    prop: "imageBlockCount",
    label: "image",
    width: "90",
}));
const __VLS_50 = __VLS_49({
    prop: "imageBlockCount",
    label: "image",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
const __VLS_52 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    prop: "relationEdgeCount",
    label: "relation",
    width: "95",
}));
const __VLS_54 = __VLS_53({
    prop: "relationEdgeCount",
    label: "relation",
    width: "95",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
var __VLS_31;
var __VLS_27;
const __VLS_56 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    label: "構造化データ(全体)",
    name: "structured",
}));
const __VLS_58 = __VLS_57({
    label: "構造化データ(全体)",
    name: "structured",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
if (!__VLS_ctx.structuredRows.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty" },
    });
}
else {
    const __VLS_60 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        data: (__VLS_ctx.structuredRows),
        size: "small",
        border: true,
        maxHeight: "520",
    }));
    const __VLS_62 = __VLS_61({
        data: (__VLS_ctx.structuredRows),
        size: "small",
        border: true,
        maxHeight: "520",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    const __VLS_64 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        prop: "fileName",
        label: "文書",
        minWidth: "220",
    }));
    const __VLS_66 = __VLS_65({
        prop: "fileName",
        label: "文書",
        minWidth: "220",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    const __VLS_68 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        prop: "chunkType",
        label: "種別",
        minWidth: "120",
    }));
    const __VLS_70 = __VLS_69({
        prop: "chunkType",
        label: "種別",
        minWidth: "120",
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    const __VLS_72 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        prop: "chunkId",
        label: "chunk",
        width: "84",
    }));
    const __VLS_74 = __VLS_73({
        prop: "chunkId",
        label: "chunk",
        width: "84",
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    const __VLS_76 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        prop: "page",
        label: "page",
        width: "84",
    }));
    const __VLS_78 = __VLS_77({
        prop: "page",
        label: "page",
        width: "84",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    const __VLS_80 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        prop: "sheet",
        label: "sheet",
        minWidth: "150",
    }));
    const __VLS_82 = __VLS_81({
        prop: "sheet",
        label: "sheet",
        minWidth: "150",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    const __VLS_84 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        prop: "textPreview",
        label: "内容",
        minWidth: "300",
        showOverflowTooltip: true,
    }));
    const __VLS_86 = __VLS_85({
        prop: "textPreview",
        label: "内容",
        minWidth: "300",
        showOverflowTooltip: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    var __VLS_63;
}
var __VLS_59;
const __VLS_88 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    label: "画像(全体)",
    name: "images",
}));
const __VLS_90 = __VLS_89({
    label: "画像(全体)",
    name: "images",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
if (!__VLS_ctx.imageRows.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "image-grid" },
    });
    for (const [img, idx] of __VLS_getVForSourceType((__VLS_ctx.imageRows))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (`img-${idx}`),
            ...{ class: "image-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "image-meta" },
        });
        (img.fileName);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
            href: (img.url),
            target: "_blank",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
            src: (img.url),
            alt: "global evidence image",
            ...{ class: "image" },
        });
    }
}
var __VLS_91;
var __VLS_23;
var __VLS_7;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['header-row']} */ ;
/** @type {__VLS_StyleScopedClasses['title']} */ ;
/** @type {__VLS_StyleScopedClasses['hint']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['image-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['image-card']} */ ;
/** @type {__VLS_StyleScopedClasses['image-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['image']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            activeTab: activeTab,
            loading: loading,
            files: files,
            structuredRows: structuredRows,
            imageRows: imageRows,
            loadAll: loadAll,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
