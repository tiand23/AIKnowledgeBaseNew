import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import AppLayout from "../components/AppLayout.vue";
import { getOnlineEvalSummary, getEvalRunSummary, listEvalRuns } from "../api/eval";
const activeTab = ref("online");
const onlineDays = ref(7);
const onlineProfile = ref("");
const loadingOnline = ref(false);
const onlineSummary = ref(null);
const runStatusFilter = ref(undefined);
const runLimit = ref(30);
const loadingRuns = ref(false);
const runs = ref([]);
const summary = ref(null);
function pct(v) {
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
    }
    catch (e) {
        ElMessage.error(e?.response?.data?.detail || e?.message || "オンライン評価の取得に失敗しました");
    }
    finally {
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
    }
    catch (e) {
        ElMessage.error(e?.response?.data?.detail || e?.message || "Run一覧の取得に失敗しました");
    }
    finally {
        loadingRuns.value = false;
    }
}
async function onRowClick(row) {
    try {
        const resp = await getEvalRunSummary(row.runId);
        summary.value = resp.data;
    }
    catch (e) {
        summary.value = null;
        ElMessage.error(e?.response?.data?.detail || e?.message || "Run詳細の取得に失敗しました");
    }
}
onMounted(() => {
    void loadOnlineSummary();
    void loadRuns();
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
const __VLS_8 = {}.ElTabs;
/** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    modelValue: (__VLS_ctx.activeTab),
}));
const __VLS_10 = __VLS_9({
    modelValue: (__VLS_ctx.activeTab),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "オンライン評価（自動）",
    name: "online",
}));
const __VLS_14 = __VLS_13({
    label: "オンライン評価（自動）",
    name: "online",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ElAlert;
/** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "入力：期間のみ。出力：システムが自動集計した結果。",
    ...{ class: "hint" },
}));
const __VLS_18 = __VLS_17({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "入力：期間のみ。出力：システムが自動集計した結果。",
    ...{ class: "hint" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
const __VLS_20 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    gutter: (12),
    ...{ class: "toolbar" },
}));
const __VLS_22 = __VLS_21({
    gutter: (12),
    ...{ class: "toolbar" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    xs: (24),
    md: (8),
}));
const __VLS_26 = __VLS_25({
    xs: (24),
    md: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    modelValue: (__VLS_ctx.onlineDays),
    ...{ style: {} },
    placeholder: "期間",
}));
const __VLS_30 = __VLS_29({
    modelValue: (__VLS_ctx.onlineDays),
    ...{ style: {} },
    placeholder: "期間",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: (1),
    label: "直近1日",
}));
const __VLS_34 = __VLS_33({
    value: (1),
    label: "直近1日",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
const __VLS_36 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: (7),
    label: "直近7日",
}));
const __VLS_38 = __VLS_37({
    value: (7),
    label: "直近7日",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
const __VLS_40 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    value: (30),
    label: "直近30日",
}));
const __VLS_42 = __VLS_41({
    value: (30),
    label: "直近30日",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
var __VLS_31;
var __VLS_27;
const __VLS_44 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    xs: (24),
    md: (8),
}));
const __VLS_46 = __VLS_45({
    xs: (24),
    md: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    modelValue: (__VLS_ctx.onlineProfile),
    placeholder: "シナリオ絞り込み（任意）例: design",
    clearable: true,
}));
const __VLS_50 = __VLS_49({
    modelValue: (__VLS_ctx.onlineProfile),
    placeholder: "シナリオ絞り込み（任意）例: design",
    clearable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
var __VLS_47;
const __VLS_52 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    xs: (24),
    md: (8),
    ...{ class: "actions" },
}));
const __VLS_54 = __VLS_53({
    xs: (24),
    md: (8),
    ...{ class: "actions" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loadingOnline),
}));
const __VLS_58 = __VLS_57({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loadingOnline),
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onClick: (__VLS_ctx.loadOnlineSummary)
};
__VLS_59.slots.default;
var __VLS_59;
var __VLS_55;
var __VLS_23;
if (!__VLS_ctx.onlineSummary) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "muted" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_64 = {}.ElRow;
    /** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        gutter: (12),
        ...{ class: "cards" },
    }));
    const __VLS_66 = __VLS_65({
        gutter: (12),
        ...{ class: "cards" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    const __VLS_68 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        xs: (12),
        md: (6),
    }));
    const __VLS_70 = __VLS_69({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    const __VLS_72 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        title: "総質問数",
        value: (__VLS_ctx.onlineSummary.totalQuestions),
    }));
    const __VLS_74 = __VLS_73({
        title: "総質問数",
        value: (__VLS_ctx.onlineSummary.totalQuestions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    var __VLS_71;
    const __VLS_76 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        xs: (12),
        md: (6),
    }));
    const __VLS_78 = __VLS_77({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    const __VLS_80 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        title: "回答成功",
        value: (__VLS_ctx.onlineSummary.successCount),
    }));
    const __VLS_82 = __VLS_81({
        title: "回答成功",
        value: (__VLS_ctx.onlineSummary.successCount),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    var __VLS_79;
    const __VLS_84 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        xs: (12),
        md: (6),
    }));
    const __VLS_86 = __VLS_85({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    const __VLS_88 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        title: "根拠不足",
        value: (__VLS_ctx.onlineSummary.noEvidenceCount),
    }));
    const __VLS_90 = __VLS_89({
        title: "根拠不足",
        value: (__VLS_ctx.onlineSummary.noEvidenceCount),
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    var __VLS_87;
    const __VLS_92 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        xs: (12),
        md: (6),
    }));
    const __VLS_94 = __VLS_93({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    const __VLS_96 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        title: "エラー件数",
        value: (__VLS_ctx.onlineSummary.errorCount),
    }));
    const __VLS_98 = __VLS_97({
        title: "エラー件数",
        value: (__VLS_ctx.onlineSummary.errorCount),
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    var __VLS_95;
    var __VLS_67;
    const __VLS_100 = {}.ElRow;
    /** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        gutter: (12),
        ...{ class: "cards top12" },
    }));
    const __VLS_102 = __VLS_101({
        gutter: (12),
        ...{ class: "cards top12" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    __VLS_103.slots.default;
    const __VLS_104 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        xs: (12),
        md: (6),
    }));
    const __VLS_106 = __VLS_105({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    const __VLS_108 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        title: "検索ヒット率（自動）",
        value: (__VLS_ctx.pct(__VLS_ctx.onlineSummary.retrievalHitRate)),
        suffix: "%",
    }));
    const __VLS_110 = __VLS_109({
        title: "検索ヒット率（自動）",
        value: (__VLS_ctx.pct(__VLS_ctx.onlineSummary.retrievalHitRate)),
        suffix: "%",
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    var __VLS_107;
    const __VLS_112 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
        xs: (12),
        md: (6),
    }));
    const __VLS_114 = __VLS_113({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_113));
    __VLS_115.slots.default;
    const __VLS_116 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        title: "根拠付き率（自動）",
        value: (__VLS_ctx.pct(__VLS_ctx.onlineSummary.withSourcesRate)),
        suffix: "%",
    }));
    const __VLS_118 = __VLS_117({
        title: "根拠付き率（自動）",
        value: (__VLS_ctx.pct(__VLS_ctx.onlineSummary.withSourcesRate)),
        suffix: "%",
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    var __VLS_115;
    const __VLS_120 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        xs: (12),
        md: (6),
    }));
    const __VLS_122 = __VLS_121({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    __VLS_123.slots.default;
    const __VLS_124 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        title: "平均応答時間",
        value: (Math.round(__VLS_ctx.onlineSummary.avgLatencyMs)),
        suffix: "ms",
    }));
    const __VLS_126 = __VLS_125({
        title: "平均応答時間",
        value: (Math.round(__VLS_ctx.onlineSummary.avgLatencyMs)),
        suffix: "ms",
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    var __VLS_123;
    const __VLS_128 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        xs: (12),
        md: (6),
    }));
    const __VLS_130 = __VLS_129({
        xs: (12),
        md: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_131.slots.default;
    const __VLS_132 = {}.ElStatistic;
    /** @type {[typeof __VLS_components.ElStatistic, typeof __VLS_components.elStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        title: "P95応答時間",
        value: (Math.round(__VLS_ctx.onlineSummary.p95LatencyMs)),
        suffix: "ms",
    }));
    const __VLS_134 = __VLS_133({
        title: "P95応答時間",
        value: (Math.round(__VLS_ctx.onlineSummary.p95LatencyMs)),
        suffix: "ms",
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    var __VLS_131;
    var __VLS_103;
    const __VLS_136 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        type: "warning",
        showIcon: true,
        closable: (false),
        title: "注記：Faithfulness / Completeness はアノテーション付きデータが必要です。現時点では自動算出可能な指標を表示します。",
        ...{ class: "top12" },
    }));
    const __VLS_138 = __VLS_137({
        type: "warning",
        showIcon: true,
        closable: (false),
        title: "注記：Faithfulness / Completeness はアノテーション付きデータが必要です。現時点では自動算出可能な指標を表示します。",
        ...{ class: "top12" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    const __VLS_140 = {}.ElRow;
    /** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
        gutter: (12),
        ...{ class: "top12" },
    }));
    const __VLS_142 = __VLS_141({
        gutter: (12),
        ...{ class: "top12" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_141));
    __VLS_143.slots.default;
    const __VLS_144 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        xs: (24),
        lg: (12),
    }));
    const __VLS_146 = __VLS_145({
        xs: (24),
        lg: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    __VLS_147.slots.default;
    const __VLS_148 = {}.ElCard;
    /** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        shadow: "never",
        ...{ class: "sub-card" },
    }));
    const __VLS_150 = __VLS_149({
        shadow: "never",
        ...{ class: "sub-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    __VLS_151.slots.default;
    {
        const { header: __VLS_thisSlot } = __VLS_151.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    const __VLS_152 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        data: (__VLS_ctx.onlineSummary.intentStats),
        border: true,
        size: "small",
    }));
    const __VLS_154 = __VLS_153({
        data: (__VLS_ctx.onlineSummary.intentStats),
        border: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    const __VLS_156 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        prop: "intent",
        label: "intent",
        minWidth: "150",
    }));
    const __VLS_158 = __VLS_157({
        prop: "intent",
        label: "intent",
        minWidth: "150",
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    const __VLS_160 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        prop: "count",
        label: "count",
        width: "100",
    }));
    const __VLS_162 = __VLS_161({
        prop: "count",
        label: "count",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    var __VLS_155;
    var __VLS_151;
    var __VLS_147;
    const __VLS_164 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        xs: (24),
        lg: (12),
    }));
    const __VLS_166 = __VLS_165({
        xs: (24),
        lg: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    const __VLS_168 = {}.ElCard;
    /** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        shadow: "never",
        ...{ class: "sub-card" },
    }));
    const __VLS_170 = __VLS_169({
        shadow: "never",
        ...{ class: "sub-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    {
        const { header: __VLS_thisSlot } = __VLS_171.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    const __VLS_172 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        data: (__VLS_ctx.onlineSummary.dailyStats),
        border: true,
        size: "small",
    }));
    const __VLS_174 = __VLS_173({
        data: (__VLS_ctx.onlineSummary.dailyStats),
        border: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    __VLS_175.slots.default;
    const __VLS_176 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        prop: "date",
        label: "日付",
        width: "120",
    }));
    const __VLS_178 = __VLS_177({
        prop: "date",
        label: "日付",
        width: "120",
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    const __VLS_180 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        prop: "total",
        label: "合計",
        width: "80",
    }));
    const __VLS_182 = __VLS_181({
        prop: "total",
        label: "合計",
        width: "80",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    const __VLS_184 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        prop: "success",
        label: "成功",
        width: "80",
    }));
    const __VLS_186 = __VLS_185({
        prop: "success",
        label: "成功",
        width: "80",
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    const __VLS_188 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        prop: "noEvidence",
        label: "根拠不足",
        width: "90",
    }));
    const __VLS_190 = __VLS_189({
        prop: "noEvidence",
        label: "根拠不足",
        width: "90",
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    const __VLS_192 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
        prop: "error",
        label: "エラー",
        width: "80",
    }));
    const __VLS_194 = __VLS_193({
        prop: "error",
        label: "エラー",
        width: "80",
    }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    const __VLS_196 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        prop: "avgLatencyMs",
        label: "平均応答時間(ms)",
        minWidth: "120",
    }));
    const __VLS_198 = __VLS_197({
        prop: "avgLatencyMs",
        label: "平均応答時間(ms)",
        minWidth: "120",
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    var __VLS_175;
    var __VLS_171;
    var __VLS_167;
    var __VLS_143;
    const __VLS_200 = {}.ElCard;
    /** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        shadow: "never",
        ...{ class: "sub-card top12" },
    }));
    const __VLS_202 = __VLS_201({
        shadow: "never",
        ...{ class: "sub-card top12" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    __VLS_203.slots.default;
    {
        const { header: __VLS_thisSlot } = __VLS_203.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    const __VLS_204 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        data: (__VLS_ctx.onlineSummary.questionSamples),
        border: true,
        size: "small",
    }));
    const __VLS_206 = __VLS_205({
        data: (__VLS_ctx.onlineSummary.questionSamples),
        border: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    __VLS_207.slots.default;
    const __VLS_208 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        prop: "createdAt",
        label: "時刻",
        minWidth: "160",
    }));
    const __VLS_210 = __VLS_209({
        prop: "createdAt",
        label: "時刻",
        minWidth: "160",
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    const __VLS_212 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        prop: "status",
        label: "状態",
        width: "110",
    }));
    const __VLS_214 = __VLS_213({
        prop: "status",
        label: "状態",
        width: "110",
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
    const __VLS_216 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
        prop: "intent",
        label: "intent",
        width: "130",
    }));
    const __VLS_218 = __VLS_217({
        prop: "intent",
        label: "intent",
        width: "130",
    }, ...__VLS_functionalComponentArgsRest(__VLS_217));
    const __VLS_220 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
        prop: "question",
        label: "質問",
        minWidth: "320",
        showOverflowTooltip: true,
    }));
    const __VLS_222 = __VLS_221({
        prop: "question",
        label: "質問",
        minWidth: "320",
        showOverflowTooltip: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_221));
    var __VLS_207;
    var __VLS_203;
}
var __VLS_15;
const __VLS_224 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
    label: "オフライン評価（履歴）",
    name: "offline",
}));
const __VLS_226 = __VLS_225({
    label: "オフライン評価（履歴）",
    name: "offline",
}, ...__VLS_functionalComponentArgsRest(__VLS_225));
__VLS_227.slots.default;
const __VLS_228 = {}.ElAlert;
/** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
// @ts-ignore
const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "入力：Runを選択。出力：当該Runの指標/カバレッジ/合格率。",
    ...{ class: "hint" },
}));
const __VLS_230 = __VLS_229({
    type: "info",
    showIcon: true,
    closable: (false),
    title: "入力：Runを選択。出力：当該Runの指標/カバレッジ/合格率。",
    ...{ class: "hint" },
}, ...__VLS_functionalComponentArgsRest(__VLS_229));
const __VLS_232 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
    gutter: (12),
    ...{ class: "toolbar" },
}));
const __VLS_234 = __VLS_233({
    gutter: (12),
    ...{ class: "toolbar" },
}, ...__VLS_functionalComponentArgsRest(__VLS_233));
__VLS_235.slots.default;
const __VLS_236 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
    xs: (24),
    md: (8),
}));
const __VLS_238 = __VLS_237({
    xs: (24),
    md: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_237));
__VLS_239.slots.default;
const __VLS_240 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
    modelValue: (__VLS_ctx.runStatusFilter),
    ...{ style: {} },
    clearable: true,
    placeholder: "状態过滤",
}));
const __VLS_242 = __VLS_241({
    modelValue: (__VLS_ctx.runStatusFilter),
    ...{ style: {} },
    clearable: true,
    placeholder: "状態过滤",
}, ...__VLS_functionalComponentArgsRest(__VLS_241));
__VLS_243.slots.default;
const __VLS_244 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
    value: "running",
    label: "running",
}));
const __VLS_246 = __VLS_245({
    value: "running",
    label: "running",
}, ...__VLS_functionalComponentArgsRest(__VLS_245));
const __VLS_248 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
    value: "done",
    label: "done",
}));
const __VLS_250 = __VLS_249({
    value: "done",
    label: "done",
}, ...__VLS_functionalComponentArgsRest(__VLS_249));
const __VLS_252 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({
    value: "failed",
    label: "failed",
}));
const __VLS_254 = __VLS_253({
    value: "failed",
    label: "failed",
}, ...__VLS_functionalComponentArgsRest(__VLS_253));
var __VLS_243;
var __VLS_239;
const __VLS_256 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
    xs: (24),
    md: (8),
}));
const __VLS_258 = __VLS_257({
    xs: (24),
    md: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_257));
__VLS_259.slots.default;
const __VLS_260 = {}.ElInputNumber;
/** @type {[typeof __VLS_components.ElInputNumber, typeof __VLS_components.elInputNumber, ]} */ ;
// @ts-ignore
const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
    modelValue: (__VLS_ctx.runLimit),
    min: (1),
    max: (200),
    ...{ style: {} },
}));
const __VLS_262 = __VLS_261({
    modelValue: (__VLS_ctx.runLimit),
    min: (1),
    max: (200),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_261));
var __VLS_259;
const __VLS_264 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
    xs: (24),
    md: (8),
    ...{ class: "actions" },
}));
const __VLS_266 = __VLS_265({
    xs: (24),
    md: (8),
    ...{ class: "actions" },
}, ...__VLS_functionalComponentArgsRest(__VLS_265));
__VLS_267.slots.default;
const __VLS_268 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loadingRuns),
}));
const __VLS_270 = __VLS_269({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loadingRuns),
}, ...__VLS_functionalComponentArgsRest(__VLS_269));
let __VLS_272;
let __VLS_273;
let __VLS_274;
const __VLS_275 = {
    onClick: (__VLS_ctx.loadRuns)
};
__VLS_271.slots.default;
var __VLS_271;
var __VLS_267;
var __VLS_235;
const __VLS_276 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
    ...{ 'onRowClick': {} },
    data: (__VLS_ctx.runs),
    border: true,
    size: "small",
    ...{ style: {} },
}));
const __VLS_278 = __VLS_277({
    ...{ 'onRowClick': {} },
    data: (__VLS_ctx.runs),
    border: true,
    size: "small",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_277));
let __VLS_280;
let __VLS_281;
let __VLS_282;
const __VLS_283 = {
    onRowClick: (__VLS_ctx.onRowClick)
};
__VLS_279.slots.default;
const __VLS_284 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
    prop: "runId",
    label: "runId",
    width: "90",
}));
const __VLS_286 = __VLS_285({
    prop: "runId",
    label: "runId",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_285));
const __VLS_288 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
    prop: "runName",
    label: "runName",
    minWidth: "220",
}));
const __VLS_290 = __VLS_289({
    prop: "runName",
    label: "runName",
    minWidth: "220",
}, ...__VLS_functionalComponentArgsRest(__VLS_289));
const __VLS_292 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
    prop: "status",
    label: "status",
    width: "110",
}));
const __VLS_294 = __VLS_293({
    prop: "status",
    label: "status",
    width: "110",
}, ...__VLS_functionalComponentArgsRest(__VLS_293));
const __VLS_296 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
    prop: "env",
    label: "env",
    width: "100",
}));
const __VLS_298 = __VLS_297({
    prop: "env",
    label: "env",
    width: "100",
}, ...__VLS_functionalComponentArgsRest(__VLS_297));
const __VLS_300 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
    prop: "metricsCount",
    label: "metrics",
    width: "90",
}));
const __VLS_302 = __VLS_301({
    prop: "metricsCount",
    label: "metrics",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_301));
const __VLS_304 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
    prop: "casesCount",
    label: "cases",
    width: "80",
}));
const __VLS_306 = __VLS_305({
    prop: "casesCount",
    label: "cases",
    width: "80",
}, ...__VLS_functionalComponentArgsRest(__VLS_305));
const __VLS_308 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
    prop: "coverageCount",
    label: "coverage",
    width: "90",
}));
const __VLS_310 = __VLS_309({
    prop: "coverageCount",
    label: "coverage",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_309));
var __VLS_279;
const __VLS_312 = {}.ElDivider;
/** @type {[typeof __VLS_components.ElDivider, typeof __VLS_components.elDivider, ]} */ ;
// @ts-ignore
const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({}));
const __VLS_314 = __VLS_313({}, ...__VLS_functionalComponentArgsRest(__VLS_313));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-head" },
});
if (!__VLS_ctx.summary) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "muted" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_316 = {}.ElDescriptions;
    /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
        column: (2),
        border: true,
        size: "small",
    }));
    const __VLS_318 = __VLS_317({
        column: (2),
        border: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_317));
    __VLS_319.slots.default;
    const __VLS_320 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
        label: "runId",
    }));
    const __VLS_322 = __VLS_321({
        label: "runId",
    }, ...__VLS_functionalComponentArgsRest(__VLS_321));
    __VLS_323.slots.default;
    (__VLS_ctx.summary.run.runId);
    var __VLS_323;
    const __VLS_324 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({
        label: "status",
    }));
    const __VLS_326 = __VLS_325({
        label: "status",
    }, ...__VLS_functionalComponentArgsRest(__VLS_325));
    __VLS_327.slots.default;
    (__VLS_ctx.summary.run.status);
    var __VLS_327;
    const __VLS_328 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
        label: "name",
    }));
    const __VLS_330 = __VLS_329({
        label: "name",
    }, ...__VLS_functionalComponentArgsRest(__VLS_329));
    __VLS_331.slots.default;
    (__VLS_ctx.summary.run.runName);
    var __VLS_331;
    const __VLS_332 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
        label: "env",
    }));
    const __VLS_334 = __VLS_333({
        label: "env",
    }, ...__VLS_functionalComponentArgsRest(__VLS_333));
    __VLS_335.slots.default;
    (__VLS_ctx.summary.run.env || "-");
    var __VLS_335;
    const __VLS_336 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
        label: "cases",
    }));
    const __VLS_338 = __VLS_337({
        label: "cases",
    }, ...__VLS_functionalComponentArgsRest(__VLS_337));
    __VLS_339.slots.default;
    (__VLS_ctx.summary.caseStats.total);
    var __VLS_339;
    const __VLS_340 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_341 = __VLS_asFunctionalComponent(__VLS_340, new __VLS_340({
        label: "passed",
    }));
    const __VLS_342 = __VLS_341({
        label: "passed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_341));
    __VLS_343.slots.default;
    (__VLS_ctx.summary.caseStats.passed);
    var __VLS_343;
    const __VLS_344 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
        label: "passRate",
    }));
    const __VLS_346 = __VLS_345({
        label: "passRate",
    }, ...__VLS_functionalComponentArgsRest(__VLS_345));
    __VLS_347.slots.default;
    ((__VLS_ctx.summary.caseStats.passRate * 100).toFixed(2));
    var __VLS_347;
    const __VLS_348 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_349 = __VLS_asFunctionalComponent(__VLS_348, new __VLS_348({
        label: "git",
    }));
    const __VLS_350 = __VLS_349({
        label: "git",
    }, ...__VLS_functionalComponentArgsRest(__VLS_349));
    __VLS_351.slots.default;
    (__VLS_ctx.summary.run.gitCommit || "-");
    var __VLS_351;
    var __VLS_319;
    const __VLS_352 = {}.ElRow;
    /** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
    // @ts-ignore
    const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
        gutter: (12),
        ...{ class: "top12" },
    }));
    const __VLS_354 = __VLS_353({
        gutter: (12),
        ...{ class: "top12" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_353));
    __VLS_355.slots.default;
    const __VLS_356 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({
        xs: (24),
        lg: (12),
    }));
    const __VLS_358 = __VLS_357({
        xs: (24),
        lg: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_357));
    __VLS_359.slots.default;
    const __VLS_360 = {}.ElCard;
    /** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
    // @ts-ignore
    const __VLS_361 = __VLS_asFunctionalComponent(__VLS_360, new __VLS_360({
        shadow: "never",
        ...{ class: "sub-card" },
    }));
    const __VLS_362 = __VLS_361({
        shadow: "never",
        ...{ class: "sub-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_361));
    __VLS_363.slots.default;
    {
        const { header: __VLS_thisSlot } = __VLS_363.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    const __VLS_364 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
        data: (__VLS_ctx.summary.metrics),
        border: true,
        size: "small",
    }));
    const __VLS_366 = __VLS_365({
        data: (__VLS_ctx.summary.metrics),
        border: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_365));
    __VLS_367.slots.default;
    const __VLS_368 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_369 = __VLS_asFunctionalComponent(__VLS_368, new __VLS_368({
        prop: "metricKey",
        label: "key",
        minWidth: "170",
    }));
    const __VLS_370 = __VLS_369({
        prop: "metricKey",
        label: "key",
        minWidth: "170",
    }, ...__VLS_functionalComponentArgsRest(__VLS_369));
    const __VLS_372 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_373 = __VLS_asFunctionalComponent(__VLS_372, new __VLS_372({
        prop: "metricValue",
        label: "value",
        width: "100",
    }));
    const __VLS_374 = __VLS_373({
        prop: "metricValue",
        label: "value",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_373));
    const __VLS_376 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_377 = __VLS_asFunctionalComponent(__VLS_376, new __VLS_376({
        prop: "threshold",
        label: "threshold",
        width: "110",
    }));
    const __VLS_378 = __VLS_377({
        prop: "threshold",
        label: "threshold",
        width: "110",
    }, ...__VLS_functionalComponentArgsRest(__VLS_377));
    const __VLS_380 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_381 = __VLS_asFunctionalComponent(__VLS_380, new __VLS_380({
        prop: "passed",
        label: "passed",
        width: "90",
    }));
    const __VLS_382 = __VLS_381({
        prop: "passed",
        label: "passed",
        width: "90",
    }, ...__VLS_functionalComponentArgsRest(__VLS_381));
    var __VLS_367;
    var __VLS_363;
    var __VLS_359;
    const __VLS_384 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_385 = __VLS_asFunctionalComponent(__VLS_384, new __VLS_384({
        xs: (24),
        lg: (12),
    }));
    const __VLS_386 = __VLS_385({
        xs: (24),
        lg: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_385));
    __VLS_387.slots.default;
    const __VLS_388 = {}.ElCard;
    /** @type {[typeof __VLS_components.ElCard, typeof __VLS_components.elCard, typeof __VLS_components.ElCard, typeof __VLS_components.elCard, ]} */ ;
    // @ts-ignore
    const __VLS_389 = __VLS_asFunctionalComponent(__VLS_388, new __VLS_388({
        shadow: "never",
        ...{ class: "sub-card" },
    }));
    const __VLS_390 = __VLS_389({
        shadow: "never",
        ...{ class: "sub-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_389));
    __VLS_391.slots.default;
    {
        const { header: __VLS_thisSlot } = __VLS_391.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    }
    const __VLS_392 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_393 = __VLS_asFunctionalComponent(__VLS_392, new __VLS_392({
        data: (__VLS_ctx.summary.coverage),
        border: true,
        size: "small",
    }));
    const __VLS_394 = __VLS_393({
        data: (__VLS_ctx.summary.coverage),
        border: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_393));
    __VLS_395.slots.default;
    const __VLS_396 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_397 = __VLS_asFunctionalComponent(__VLS_396, new __VLS_396({
        prop: "assetType",
        label: "assetType",
        minWidth: "140",
    }));
    const __VLS_398 = __VLS_397({
        prop: "assetType",
        label: "assetType",
        minWidth: "140",
    }, ...__VLS_functionalComponentArgsRest(__VLS_397));
    const __VLS_400 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_401 = __VLS_asFunctionalComponent(__VLS_400, new __VLS_400({
        prop: "totalCount",
        label: "total",
        width: "90",
    }));
    const __VLS_402 = __VLS_401({
        prop: "totalCount",
        label: "total",
        width: "90",
    }, ...__VLS_functionalComponentArgsRest(__VLS_401));
    const __VLS_404 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_405 = __VLS_asFunctionalComponent(__VLS_404, new __VLS_404({
        prop: "indexedCount",
        label: "indexed",
        width: "100",
    }));
    const __VLS_406 = __VLS_405({
        prop: "indexedCount",
        label: "indexed",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_405));
    const __VLS_408 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_409 = __VLS_asFunctionalComponent(__VLS_408, new __VLS_408({
        prop: "coverageRate",
        label: "coverage",
        width: "100",
    }));
    const __VLS_410 = __VLS_409({
        prop: "coverageRate",
        label: "coverage",
        width: "100",
    }, ...__VLS_functionalComponentArgsRest(__VLS_409));
    var __VLS_395;
    var __VLS_391;
    var __VLS_387;
    var __VLS_355;
}
var __VLS_227;
var __VLS_11;
var __VLS_7;
var __VLS_2;
/** @type {__VLS_StyleScopedClasses['page-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['hint']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['muted']} */ ;
/** @type {__VLS_StyleScopedClasses['cards']} */ ;
/** @type {__VLS_StyleScopedClasses['cards']} */ ;
/** @type {__VLS_StyleScopedClasses['top12']} */ ;
/** @type {__VLS_StyleScopedClasses['top12']} */ ;
/** @type {__VLS_StyleScopedClasses['top12']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-card']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-card']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-card']} */ ;
/** @type {__VLS_StyleScopedClasses['top12']} */ ;
/** @type {__VLS_StyleScopedClasses['hint']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['table-head']} */ ;
/** @type {__VLS_StyleScopedClasses['muted']} */ ;
/** @type {__VLS_StyleScopedClasses['top12']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-card']} */ ;
/** @type {__VLS_StyleScopedClasses['sub-card']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AppLayout: AppLayout,
            activeTab: activeTab,
            onlineDays: onlineDays,
            onlineProfile: onlineProfile,
            loadingOnline: loadingOnline,
            onlineSummary: onlineSummary,
            runStatusFilter: runStatusFilter,
            runLimit: runLimit,
            loadingRuns: loadingRuns,
            runs: runs,
            summary: summary,
            pct: pct,
            loadOnlineSummary: loadOnlineSummary,
            loadRuns: loadRuns,
            onRowClick: onRowClick,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
