import { http } from "../utils/http";
export async function uploadChunk(payload) {
    const form = new FormData();
    form.append("file", payload.file, payload.fileName);
    form.append("fileMd5", payload.fileMd5);
    form.append("chunkIndex", String(payload.chunkIndex));
    form.append("totalSize", String(payload.totalSize));
    form.append("fileName", payload.fileName);
    form.append("totalChunks", String(payload.totalChunks));
    if (payload.orgTag) {
        form.append("orgTag", payload.orgTag);
    }
    form.append("isPublic", String(payload.isPublic ?? false));
    const resp = await http.post("/api/v1/upload/chunk", form, {
        headers: { "Content-Type": "multipart/form-data" }
    });
    return resp.data;
}
export async function getUploadStatus(fileMd5) {
    const resp = await http.get("/api/v1/upload/status", {
        params: { file_md5: fileMd5 }
    });
    return resp.data;
}
export async function mergeFile(fileMd5, fileName) {
    const resp = await http.post("/api/v1/upload/merge", {
        file_md5: fileMd5,
        file_name: fileName
    });
    return resp.data;
}
export async function getUserUploadedFiles() {
    const resp = await http.get("/api/v1/documents/uploads");
    return resp.data;
}
export async function getEsPreview(fileMd5, size = 5) {
    const resp = await http.get("/api/v1/documents/es-preview", {
        params: { file_md5: fileMd5, size }
    });
    return resp.data;
}
export async function getSourceDetail(payload) {
    const params = {
        file_md5: payload.fileMd5,
        size: payload.size ?? 10
    };
    if (payload.chunkId !== undefined && payload.chunkId !== "") {
        params.chunk_id = Number(payload.chunkId);
    }
    if (payload.page !== undefined && payload.page !== "") {
        params.page = Number(payload.page);
    }
    if (payload.sheet) {
        params.sheet = payload.sheet;
    }
    const resp = await http.get("/api/v1/documents/source-detail", {
        params
    });
    return resp.data;
}
export async function getStructuredOverview() {
    const resp = await http.get("/api/v1/documents/structured-overview");
    return resp.data;
}
export async function getStructuredDetail(fileMd5) {
    const resp = await http.get("/api/v1/documents/structured-detail", {
        params: { file_md5: fileMd5 }
    });
    return resp.data;
}
