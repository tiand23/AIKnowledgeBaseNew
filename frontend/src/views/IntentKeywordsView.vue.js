import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getIntentKeywordsConfig, updateIntentKeywordsConfig } from "../api/profile";
const loading = ref(false);
const saving = ref(false);
const updatedAt = ref("");
const formItems = ref([]);
function splitKeywords(text) {
    const rows = String(text || "").split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    const out = [];
    const seen = new Set();
    for (const row of rows) {
        const v = row.toLowerCase();
        if (seen.has(v))
            continue;
        seen.add(v);
        out.push(v);
    }
    return out;
}
async function loadConfig() {
    loading.value = true;
    try {
        const resp = await getIntentKeywordsConfig();
        formItems.value = (resp.data?.categories || []).map((item) => ({
            key: item.key,
            label: item.label,
            keywordsText: (item.keywords || []).join("\n")
        }));
        updatedAt.value = resp.data?.updated_at || "";
    }
    catch (e) {
        ElMessage.error(e?.response?.data?.detail || e?.message || "キーワード設定の取得に失敗しました");
    }
    finally {
        loading.value = false;
    }
}
async function saveConfig() {
    saving.value = true;
    try {
        const payload = formItems.value.map((item) => ({
            key: item.key,
            keywords: splitKeywords(item.keywordsText)
        }));
        const resp = await updateIntentKeywordsConfig(payload);
        formItems.value = (resp.data?.categories || []).map((item) => ({
            key: item.key,
            label: item.label,
            keywordsText: (item.keywords || []).join("\n")
        }));
        updatedAt.value = resp.data?.updated_at || "";
        ElMessage.success("意図キーワード設定を保存しました。");
    }
    catch (e) {
        ElMessage.error(e?.response?.data?.detail || e?.message || "キーワード設定の保存に失敗しました");
    }
    finally {
        saving.value = false;
    }
}
onMounted(() => {
    void loadConfig();
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
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "actions" },
    });
    const __VLS_8 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_12;
    let __VLS_13;
    let __VLS_14;
    const __VLS_15 = {
        onClick: (__VLS_ctx.loadConfig)
    };
    __VLS_11.slots.default;
    var __VLS_11;
    const __VLS_16 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.saving),
    }));
    const __VLS_18 = __VLS_17({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.saving),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    let __VLS_20;
    let __VLS_21;
    let __VLS_22;
    const __VLS_23 = {
        onClick: (__VLS_ctx.saveConfig)
    };
    __VLS_19.slots.default;
    var __VLS_19;
}
const __VLS_24 = {}.ElAlert;
/** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    type: "info",
    showIcon: true,
    closable: (false),
    ...{ class: "hint" },
    title: "このページは、質問文をどの意図として判定するか（例：画面レイアウト、フロー、統計）を調整するための管理画面です。",
}));
const __VLS_26 = __VLS_25({
    type: "info",
    showIcon: true,
    closable: (false),
    ...{ class: "hint" },
    title: "このページは、質問文をどの意図として判定するか（例：画面レイアウト、フロー、統計）を調整するための管理画面です。",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
const __VLS_28 = {}.ElDescriptions;
/** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    border: true,
    column: (1),
    size: "small",
    ...{ class: "hint2" },
}));
const __VLS_30 = __VLS_29({
    border: true,
    column: (1),
    size: "small",
    ...{ class: "hint2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ElDescriptionsItem;
/** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    label: "何のため？",
}));
const __VLS_34 = __VLS_33({
    label: "何のため？",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
const __VLS_36 = {}.ElDescriptionsItem;
/** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    label: "いつ変更する？",
}));
const __VLS_38 = __VLS_37({
    label: "いつ変更する？",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
const __VLS_40 = {}.ElDescriptionsItem;
/** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    label: "変更の影響範囲",
}));
const __VLS_42 = __VLS_41({
    label: "変更の影響範囲",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
var __VLS_43;
const __VLS_44 = {}.ElDescriptionsItem;
/** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    label: "入力ルール",
}));
const __VLS_46 = __VLS_45({
    label: "入力ルール",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
var __VLS_47;
var __VLS_31;
if (__VLS_ctx.updatedAt) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "muted" },
    });
    (__VLS_ctx.updatedAt);
}
const __VLS_48 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    labelPosition: "top",
    ...{ class: "form" },
}));
const __VLS_50 = __VLS_49({
    labelPosition: "top",
    ...{ class: "form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.loading) }, null, null);
__VLS_51.slots.default;
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.formItems))) {
    const __VLS_52 = {}.ElFormItem;
    /** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        key: (item.key),
        label: (`${item.label} (${item.key})`),
    }));
    const __VLS_54 = __VLS_53({
        key: (item.key),
        label: (`${item.label} (${item.key})`),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    const __VLS_56 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        modelValue: (item.keywordsText),
        type: "textarea",
        rows: (4),
        placeholder: "1行に1キーワード",
    }));
    const __VLS_58 = __VLS_57({
        modelValue: (item.keywordsText),
        type: "textarea",
        rows: (4),
        placeholder: "1行に1キーワード",
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    var __VLS_55;
}
var __VLS_51;
var __VLS_7;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['header-row']} */ ;
/** @type {__VLS_StyleScopedClasses['title']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['hint']} */ ;
/** @type {__VLS_StyleScopedClasses['hint2']} */ ;
/** @type {__VLS_StyleScopedClasses['muted']} */ ;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            loading: loading,
            saving: saving,
            updatedAt: updatedAt,
            formItems: formItems,
            loadConfig: loadConfig,
            saveConfig: saveConfig,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
