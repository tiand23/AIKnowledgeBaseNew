import { defineStore } from "pinia";
import { getProfileState } from "../api/profile";

const PROFILE_ID_KEY = "akb_profile_id";
const PROFILE_NAME_KEY = "akb_profile_name";

export const useProfileStore = defineStore("profile", {
  state: () => ({
    selectedProfile: localStorage.getItem(PROFILE_ID_KEY) || "",
    selectedName: localStorage.getItem(PROFILE_NAME_KEY) || "",
    loaded: false
  }),
  actions: {
    setProfile(profileId: string, profileName: string) {
      this.selectedProfile = profileId;
      this.selectedName = profileName;
      localStorage.setItem(PROFILE_ID_KEY, profileId);
      localStorage.setItem(PROFILE_NAME_KEY, profileName);
    },
    clearProfile() {
      this.selectedProfile = "";
      this.selectedName = "";
      this.loaded = false;
      localStorage.removeItem(PROFILE_ID_KEY);
      localStorage.removeItem(PROFILE_NAME_KEY);
    },
    async refreshFromServer() {
      const resp = await getProfileState();
      const data = resp.data;
      if (data?.selected_profile) {
        const selectedName =
          data.selected_name || data.options.find((x) => x.profile_id === data.selected_profile)?.name || "";
        this.setProfile(data.selected_profile, selectedName);
      } else {
        this.clearProfile();
      }
      this.loaded = true;
    }
  }
});

