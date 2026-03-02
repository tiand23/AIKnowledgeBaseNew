import { http } from "../utils/http";
export async function createEvalRun(payload) {
    const resp = await http.post("/api/v1/eval/runs", payload);
    return resp.data;
}
export async function finishEvalRun(runId, status = "done") {
    const resp = await http.post(`/api/v1/eval/runs/${runId}/finish`, { status });
    return resp.data;
}
export async function upsertEvalMetrics(runId, items) {
    const resp = await http.post(`/api/v1/eval/runs/${runId}/metrics`, { items });
    return resp.data;
}
export async function upsertEvalAssetCoverage(runId, items) {
    const resp = await http.post(`/api/v1/eval/runs/${runId}/asset-coverage`, { items });
    return resp.data;
}
export async function upsertEvalCases(runId, items) {
    const resp = await http.post(`/api/v1/eval/runs/${runId}/cases`, { items });
    return resp.data;
}
export async function upsertEvalEvidences(runId, items) {
    const resp = await http.post(`/api/v1/eval/runs/${runId}/evidences`, { items });
    return resp.data;
}
export async function listEvalRuns(params) {
    const resp = await http.get("/api/v1/eval/runs", { params });
    return resp.data;
}
export async function getEvalRunSummary(runId) {
    const resp = await http.get(`/api/v1/eval/runs/${runId}`);
    return resp.data;
}
export async function getOnlineEvalSummary(params) {
    const resp = await http.get("/api/v1/eval/online/summary", { params });
    return resp.data;
}
