import axios from "axios";
import { ElMessage } from "element-plus";
const resolvedHost = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
const fallbackBaseURL = `${window.location.protocol}//${resolvedHost}:8000`;
const envBaseURL = import.meta.env.VITE_API_BASE_URL || "";
const shouldUseFallback = !envBaseURL ||
    (window.location.hostname !== "localhost" &&
        window.location.hostname !== "127.0.0.1" &&
        /localhost|127\.0\.0\.1/.test(envBaseURL));
const baseURL = shouldUseFallback ? fallbackBaseURL : envBaseURL;
export const http = axios.create({
    baseURL,
    timeout: 30000
});
let authExpiredNoticeAt = 0;
http.interceptors.request.use((config) => {
    const token = localStorage.getItem("akb_token");
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
http.interceptors.response.use((resp) => resp, (error) => {
    const status = error?.response?.status;
    const detail = String(error?.response?.data?.detail || error?.response?.data?.message || "").toLowerCase();
    const isAuthExpired = status === 401 ||
        status === 403 ||
        detail.includes("not authenticated") ||
        detail.includes("token") ||
        detail.includes("unauthorized");
    if (isAuthExpired) {
        localStorage.removeItem("akb_token");
        localStorage.removeItem("akb_username");
        localStorage.removeItem("akb_user_id");
        const now = Date.now();
        if (now - authExpiredNoticeAt > 3000) {
            authExpiredNoticeAt = now;
            ElMessage.warning("セッションの有効期限が切れました。再ログインしてください。");
        }
    }
    return Promise.reject(error);
});
