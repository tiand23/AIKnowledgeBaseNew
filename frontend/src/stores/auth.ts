import { defineStore } from "pinia";
import { getCurrentUserInfo } from "../api/auth";

type LoginPayload = {
  accessToken: string;
  username: string;
  userId: number;
};

const TOKEN_KEY = "akb_token";
const USERNAME_KEY = "akb_username";
const USER_ID_KEY = "akb_user_id";
const ORG_TAGS_KEY = "akb_org_tags";
const PRIMARY_ORG_KEY = "akb_primary_org";
const ROLE_KEY = "akb_role";
const PROFILE_ID_KEY = "akb_profile_id";
const PROFILE_NAME_KEY = "akb_profile_name";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || "",
    username: localStorage.getItem(USERNAME_KEY) || "",
    userId: Number(localStorage.getItem(USER_ID_KEY) || 0),
    orgTags: (localStorage.getItem(ORG_TAGS_KEY) || "")
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean),
    primaryOrg: localStorage.getItem(PRIMARY_ORG_KEY) || "",
    role: localStorage.getItem(ROLE_KEY) || ""
  }),
  actions: {
    login(payload: LoginPayload) {
      this.token = payload.accessToken;
      this.username = payload.username;
      this.userId = payload.userId;
      localStorage.setItem(TOKEN_KEY, payload.accessToken);
      localStorage.setItem(USERNAME_KEY, payload.username);
      localStorage.setItem(USER_ID_KEY, String(payload.userId));
    },
    setUserAccessInfo(payload: { role?: string; orgTags?: string[]; primaryOrg?: string }) {
      this.role = payload.role || "";
      this.orgTags = (payload.orgTags || []).filter(Boolean);
      this.primaryOrg = payload.primaryOrg || "";
      localStorage.setItem(ROLE_KEY, this.role);
      localStorage.setItem(ORG_TAGS_KEY, this.orgTags.join(","));
      localStorage.setItem(PRIMARY_ORG_KEY, this.primaryOrg);
    },
    async refreshUserAccessInfo() {
      if (!this.token) return;
      try {
        const resp = await getCurrentUserInfo();
        const data = resp.data;
        this.setUserAccessInfo({
          role: data?.role || "",
          orgTags: data?.orgTags || [],
          primaryOrg: data?.primaryOrg || ""
        });
      } catch {
      }
    },
    logout() {
      this.token = "";
      this.username = "";
      this.userId = 0;
      this.orgTags = [];
      this.primaryOrg = "";
      this.role = "";
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USERNAME_KEY);
      localStorage.removeItem(USER_ID_KEY);
      localStorage.removeItem(ORG_TAGS_KEY);
      localStorage.removeItem(PRIMARY_ORG_KEY);
      localStorage.removeItem(ROLE_KEY);
      localStorage.removeItem(PROFILE_ID_KEY);
      localStorage.removeItem(PROFILE_NAME_KEY);
    }
  }
});
