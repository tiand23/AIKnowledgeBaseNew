import { http } from "../utils/http";
import type {
  ApiResponse,
  LoginData,
  RegisterData,
  RegisterOrgTagOption,
  UserInfoData
} from "../types/api";

export async function login(username: string, password: string) {
  const resp = await http.post<ApiResponse<LoginData>>("/api/v1/auth/login", {
    username,
    password
  });
  return resp.data;
}

export async function register(payload: {
  username: string;
  email: string;
  password: string;
  orgTags?: string[];
  primaryOrg?: string;
}) {
  const resp = await http.post<ApiResponse<RegisterData>>("/api/v1/auth/register", payload);
  return resp.data;
}

export async function getRegisterOrgTags() {
  const resp = await http.get<ApiResponse<RegisterOrgTagOption[]>>("/api/v1/auth/register/org-tags");
  return resp.data;
}

export async function getCurrentUserInfo() {
  const resp = await http.get<ApiResponse<UserInfoData>>("/api/v1/auth/me");
  return resp.data;
}
