import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import AppLayout from "../components/AppLayout.vue";
import { getProfileState, selectProfile } from "../api/profile";
import { useProfileStore } from "../stores/profile";
const router = useRouter();
const profileStore = useProfileStore();
const saving = ref(false);
const options = ref([]);
const selectedProfileId = ref("");
const profileExamples = {
    general: ["最新版の手順書はどこですか", "この用語は社内でどう定義されていますか"],
    design: ["このDB項目変更の影響範囲は", "この業務フローはどのシステム間ですか"],
    policy: ["この金額は何段階の承認が必要ですか", "どの版がこの日付で有効ですか"],
    ops: ["同様障害の過去対応は", "変更後に発生したアラートは"]
};
function getExamples(profileId) {
    return profileExamples[profileId] || ["このシナリオに沿って検索・回答してください"];
}
async function refresh() {
    const resp = await getProfileState();
    const data = resp.data;
    options.value = data?.options || [];
    if (data?.selected_profile) {
        const selectedName = data.selected_name || options.value.find((x) => x.profile_id === data.selected_profile)?.name || "";
        profileStore.setProfile(data.selected_profile, selectedName);
        ElMessage.success(`現在のシナリオ: ${selectedName || data.selected_profile}`);
        router.push("/upload");
        return;
    }
    if (!selectedProfileId.value && options.value.length > 0) {
        selectedProfileId.value = options.value[0].profile_id;
    }
}
async function onConfirm() {
    if (!selectedProfileId.value) {
        return;
    }
    saving.value = true;
    try {
        const resp = await selectProfile(selectedProfileId.value);
        const data = resp.data;
        if (!data?.selected_profile) {
            throw new Error("シナリオ保存に失敗しました");
        }
        const selectedName = data.selected_name || data.options.find((x) => x.profile_id === data.selected_profile)?.name || "";
        profileStore.setProfile(data.selected_profile, selectedName);
        ElMessage.success(`シナリオを確定しました: ${selectedName || data.selected_profile}`);
        router.push("/upload");
    }
    catch (err) {
        ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || "シナリオ保存に失敗しました");
    }
    finally {
        saving.value = false;
    }
}
onMounted(() => {
    void refresh();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['examples']} */ ;
/** @type {__VLS_StyleScopedClasses['examples']} */ ;
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
const __VLS_8 = {}.ElAlert;
/** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    type: "warning",
    showIcon: true,
    closable: (false),
    title: "シナリオは作成後に変更できません。切り替える場合はデータを初期化してください。",
    ...{ class: "mb-16" },
}));
const __VLS_10 = __VLS_9({
    type: "warning",
    showIcon: true,
    closable: (false),
    title: "シナリオは作成後に変更できません。切り替える場合はデータを初期化してください。",
    ...{ class: "mb-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid" },
});
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.options))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.selectedProfileId = item.profile_id;
            } },
        key: (item.profile_id),
        ...{ class: "card" },
        ...{ class: ({ active: __VLS_ctx.selectedProfileId === item.profile_id }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "name" },
    });
    (item.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "desc" },
    });
    (item.description);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "examples" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "examples-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    for (const [q] of __VLS_getVForSourceType((__VLS_ctx.getExamples(item.profile_id)))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
            key: (q),
        });
        (q);
    }
    if (__VLS_ctx.selectedProfileId === item.profile_id) {
        const __VLS_12 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
            size: "small",
            type: "success",
        }));
        const __VLS_14 = __VLS_13({
            size: "small",
            type: "success",
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        __VLS_15.slots.default;
        var __VLS_15;
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "actions" },
});
const __VLS_16 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
    disabled: (!__VLS_ctx.selectedProfileId),
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
    disabled: (!__VLS_ctx.selectedProfileId),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.onConfirm)
};
__VLS_19.slots.default;
var __VLS_19;
const __VLS_24 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.refresh)
};
__VLS_27.slots.default;
var __VLS_27;
var __VLS_7;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-16']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['name']} */ ;
/** @type {__VLS_StyleScopedClasses['desc']} */ ;
/** @type {__VLS_StyleScopedClasses['examples']} */ ;
/** @type {__VLS_StyleScopedClasses['examples-title']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            saving: saving,
            options: options,
            selectedProfileId: selectedProfileId,
            getExamples: getExamples,
            refresh: refresh,
            onConfirm: onConfirm,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
