import { http } from "../utils/http";
import type {
  ApiResponse,
  EvalRunData,
  EvalRunListItem,
  EvalRunSummaryData,
  EvalOnlineSummaryData
} from "../types/api";

export async function createEvalRun(payload: { runName: string; gitCommit?: string; env?: string }) {
  const resp = await http.post<ApiResponse<EvalRunData>>("/api/v1/eval/runs", payload);
  return resp.data;
}

export async function finishEvalRun(runId: number, status: "done" | "failed" = "done") {
  const resp = await http.post<ApiResponse<EvalRunData>>(`/api/v1/eval/runs/${runId}/finish`, { status });
  return resp.data;
}

export async function upsertEvalMetrics(runId: number, items: Array<Record<string, unknown>>) {
  const resp = await http.post<ApiResponse<{ affected: number }>>(`/api/v1/eval/runs/${runId}/metrics`, { items });
  return resp.data;
}

export async function upsertEvalAssetCoverage(runId: number, items: Array<Record<string, unknown>>) {
  const resp = await http.post<ApiResponse<{ affected: number }>>(
    `/api/v1/eval/runs/${runId}/asset-coverage`,
    { items }
  );
  return resp.data;
}

export async function upsertEvalCases(runId: number, items: Array<Record<string, unknown>>) {
  const resp = await http.post<ApiResponse<{ affected: number }>>(`/api/v1/eval/runs/${runId}/cases`, { items });
  return resp.data;
}

export async function upsertEvalEvidences(runId: number, items: Array<Record<string, unknown>>) {
  const resp = await http.post<ApiResponse<{ affected: number }>>(`/api/v1/eval/runs/${runId}/evidences`, { items });
  return resp.data;
}

export async function listEvalRuns(params?: { limit?: number; status?: string }) {
  const resp = await http.get<ApiResponse<EvalRunListItem[]>>("/api/v1/eval/runs", { params });
  return resp.data;
}

export async function getEvalRunSummary(runId: number) {
  const resp = await http.get<ApiResponse<EvalRunSummaryData>>(`/api/v1/eval/runs/${runId}`);
  return resp.data;
}

export async function getOnlineEvalSummary(params?: { days?: number; profile?: string }) {
  const resp = await http.get<ApiResponse<EvalOnlineSummaryData>>("/api/v1/eval/online/summary", { params });
  return resp.data;
}
