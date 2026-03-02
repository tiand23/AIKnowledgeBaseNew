import { http } from "../utils/http";
export async function login(username, password) {
    const resp = await http.post("/api/v1/auth/login", {
        username,
        password
    });
    return resp.data;
}
export async function register(payload) {
    const resp = await http.post("/api/v1/auth/register", payload);
    return resp.data;
}
export async function getRegisterOrgTags() {
    const resp = await http.get("/api/v1/auth/register/org-tags");
    return resp.data;
}
export async function getCurrentUserInfo() {
    const resp = await http.get("/api/v1/auth/me");
    return resp.data;
}
