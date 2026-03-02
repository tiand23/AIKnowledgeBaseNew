import { onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getRegisterOrgTags, register } from "../api/auth";
import { useAuthStore } from "../stores/auth";
const router = useRouter();
const auth = useAuthStore();
const registering = ref(false);
const orgTagOptions = ref([]);
const form = reactive({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    orgTags: [],
    primaryOrg: ""
});
watch(() => form.orgTags.slice(), (tags) => {
    if (form.primaryOrg && !tags.includes(form.primaryOrg)) {
        form.primaryOrg = "";
    }
});
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
    }
    catch (err) {
        const status = err?.response?.status;
        const detail = err?.response?.data?.message || err?.response?.data?.detail || err?.message || "登録に失敗しました";
        ElMessage.error(status ? `登録失敗(${status}): ${detail}` : `登録失敗: ${detail}`);
    }
    finally {
        registering.value = false;
    }
}
async function loadRegisterOrgTags() {
    try {
        const resp = await getRegisterOrgTags();
        orgTagOptions.value = resp.data || [];
    }
    catch (e) {
        ElMessage.warning(e?.response?.data?.detail || e?.message || "組織タグ一覧の取得に失敗しました");
    }
}
onMounted(() => {
    void loadRegisterOrgTags();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "register-page" },
});
const __VLS_0 = {}.ElCard;
/** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "register-card" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "register-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
{
    const { header: __VLS_thisSlot } = __VLS_3.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "title" },
    });
}
const __VLS_4 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onSubmit': {} },
    model: (__VLS_ctx.form),
    labelPosition: "top",
}));
const __VLS_6 = __VLS_5({
    ...{ 'onSubmit': {} },
    model: (__VLS_ctx.form),
    labelPosition: "top",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onSubmit: () => { }
};
__VLS_7.slots.default;
const __VLS_12 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "ユーザー名",
}));
const __VLS_14 = __VLS_13({
    label: "ユーザー名",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    modelValue: (__VLS_ctx.form.username),
    placeholder: "3文字以上",
}));
const __VLS_18 = __VLS_17({
    modelValue: (__VLS_ctx.form.username),
    placeholder: "3文字以上",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
var __VLS_15;
const __VLS_20 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    label: "メールアドレス",
}));
const __VLS_22 = __VLS_21({
    label: "メールアドレス",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    modelValue: (__VLS_ctx.form.email),
    placeholder: "メールアドレスを入力",
}));
const __VLS_26 = __VLS_25({
    modelValue: (__VLS_ctx.form.email),
    placeholder: "メールアドレスを入力",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
var __VLS_23;
const __VLS_28 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    label: "パスワード",
}));
const __VLS_30 = __VLS_29({
    label: "パスワード",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    modelValue: (__VLS_ctx.form.password),
    type: "password",
    showPassword: true,
    placeholder: "6文字以上",
}));
const __VLS_34 = __VLS_33({
    modelValue: (__VLS_ctx.form.password),
    type: "password",
    showPassword: true,
    placeholder: "6文字以上",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
var __VLS_31;
const __VLS_36 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    label: "パスワード確認",
}));
const __VLS_38 = __VLS_37({
    label: "パスワード確認",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    modelValue: (__VLS_ctx.form.confirmPassword),
    type: "password",
    showPassword: true,
    placeholder: "もう一度入力",
}));
const __VLS_42 = __VLS_41({
    modelValue: (__VLS_ctx.form.confirmPassword),
    type: "password",
    showPassword: true,
    placeholder: "もう一度入力",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
var __VLS_39;
const __VLS_44 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    label: "所属組織（権限）",
}));
const __VLS_46 = __VLS_45({
    label: "所属組織（権限）",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    modelValue: (__VLS_ctx.form.orgTags),
    multiple: true,
    filterable: true,
    clearable: true,
    ...{ style: {} },
    placeholder: "所属組織タグを選択（任意）",
}));
const __VLS_50 = __VLS_49({
    modelValue: (__VLS_ctx.form.orgTags),
    multiple: true,
    filterable: true,
    clearable: true,
    ...{ style: {} },
    placeholder: "所属組織タグを選択（任意）",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.orgTagOptions))) {
    const __VLS_52 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        key: (item.tagId),
        label: (`${item.name} (${item.tagId})`),
        value: (item.tagId),
    }));
    const __VLS_54 = __VLS_53({
        key: (item.tagId),
        label: (`${item.name} (${item.tagId})`),
        value: (item.tagId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
}
var __VLS_51;
var __VLS_47;
const __VLS_56 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    label: "主組織",
}));
const __VLS_58 = __VLS_57({
    label: "主組織",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    modelValue: (__VLS_ctx.form.primaryOrg),
    clearable: true,
    ...{ style: {} },
    placeholder: "主組織を選択（任意）",
}));
const __VLS_62 = __VLS_61({
    modelValue: (__VLS_ctx.form.primaryOrg),
    clearable: true,
    ...{ style: {} },
    placeholder: "主組織を選択（任意）",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
for (const [tagId] of __VLS_getVForSourceType((__VLS_ctx.form.orgTags))) {
    const __VLS_64 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        key: (`primary-${tagId}`),
        label: (tagId),
        value: (tagId),
    }));
    const __VLS_66 = __VLS_65({
        key: (`primary-${tagId}`),
        label: (tagId),
        value: (tagId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
}
var __VLS_63;
var __VLS_59;
const __VLS_68 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ style: {} },
    loading: (__VLS_ctx.registering),
}));
const __VLS_70 = __VLS_69({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ style: {} },
    loading: (__VLS_ctx.registering),
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
let __VLS_72;
let __VLS_73;
let __VLS_74;
const __VLS_75 = {
    onClick: (__VLS_ctx.onRegister)
};
__VLS_71.slots.default;
var __VLS_71;
var __VLS_7;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bottom-link" },
});
const __VLS_76 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    ...{ 'onClick': {} },
    type: "primary",
    link: true,
}));
const __VLS_78 = __VLS_77({
    ...{ 'onClick': {} },
    type: "primary",
    link: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
let __VLS_80;
let __VLS_81;
let __VLS_82;
const __VLS_83 = {
    onClick: (...[$event]) => {
        __VLS_ctx.router.push('/login');
    }
};
__VLS_79.slots.default;
var __VLS_79;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['register-page']} */ ;
/** @type {__VLS_StyleScopedClasses['register-card']} */ ;
/** @type {__VLS_StyleScopedClasses['title']} */ ;
/** @type {__VLS_StyleScopedClasses['bottom-link']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            router: router,
            registering: registering,
            orgTagOptions: orgTagOptions,
            form: form,
            onRegister: onRegister,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
