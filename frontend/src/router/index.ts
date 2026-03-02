import { createRouter, createWebHistory } from "vue-router";
import LoginView from "../views/LoginView.vue";
import RegisterView from "../views/RegisterView.vue";
import UploadView from "../views/UploadView.vue";
import ChatView from "../views/ChatView.vue";
import ProfileSetupView from "../views/ProfileSetupView.vue";
import EvalView from "../views/EvalView.vue";
import StructuredDataView from "../views/StructuredDataView.vue";
import IntentKeywordsView from "../views/IntentKeywordsView.vue";
import { useAuthStore } from "../stores/auth";
import { useProfileStore } from "../stores/profile";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/setup" },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
    { path: "/setup", name: "setup", component: ProfileSetupView, meta: { requiresAuth: true } },
    { path: "/upload", name: "upload", component: UploadView, meta: { requiresAuth: true } },
    { path: "/chat", name: "chat", component: ChatView, meta: { requiresAuth: true } },
    { path: "/eval", name: "eval", component: EvalView, meta: { requiresAuth: true } },
    { path: "/structured", name: "structured", component: StructuredDataView, meta: { requiresAuth: true } },
    { path: "/intent-keywords", name: "intent-keywords", component: IntentKeywordsView, meta: { requiresAuth: true } }
  ]
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  const profileStore = useProfileStore();
  if (to.meta.requiresAuth && !auth.token) {
    return "/login";
  }
  if ((to.path === "/login" || to.path === "/register") && auth.token) {
    return "/setup";
  }

  if (to.meta.requiresAuth) {
    if (!profileStore.loaded) {
      try {
        await profileStore.refreshFromServer();
      } catch {
        return "/login";
      }
    }
    if (!profileStore.selectedProfile && to.path !== "/setup") {
      return "/setup";
    }
    if (profileStore.selectedProfile && to.path === "/setup") {
      return "/upload";
    }
  }
  return true;
});

export default router;
