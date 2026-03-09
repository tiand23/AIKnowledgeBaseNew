import { http } from "../utils/http";
export async function getProfileState() {
    const resp = await http.get("/api/v1/profile");
    return resp.data;
}
export async function selectProfile(profileId) {
    const resp = await http.post("/api/v1/profile/select", {
        profile_id: profileId
    });
    return resp.data;
}
export async function getIntentKeywordsConfig() {
    const resp = await http.get("/api/v1/profile/intent-keywords");
    return resp.data;
}
export async function updateIntentKeywordsConfig(categories) {
    const resp = await http.put("/api/v1/profile/intent-keywords", {
        categories
    });
    return resp.data;
}
