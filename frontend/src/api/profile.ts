import { http } from "../utils/http";
import type {
  ApiResponse,
  IntentKeywordsConfigData,
  ProfileStateData
} from "../types/api";

export async function getProfileState() {
  const resp = await http.get<ApiResponse<ProfileStateData>>("/api/v1/profile");
  return resp.data;
}

export async function selectProfile(profileId: string) {
  const resp = await http.post<ApiResponse<ProfileStateData>>("/api/v1/profile/select", {
    profile_id: profileId
  });
  return resp.data;
}

export async function getIntentKeywordsConfig() {
  const resp = await http.get<ApiResponse<IntentKeywordsConfigData>>("/api/v1/profile/intent-keywords");
  return resp.data;
}

export async function updateIntentKeywordsConfig(categories: Array<{ key: string; keywords: string[] }>) {
  const resp = await http.put<ApiResponse<IntentKeywordsConfigData>>("/api/v1/profile/intent-keywords", {
    categories
  });
  return resp.data;
}
