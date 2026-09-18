import { createApp } from "vue";
import App from "./App.vue";
import DiagnosisEntry from "./components/DiagnosisEntry.vue";
import OrganizationDiagnosis from "./components/OrganizationDiagnosis.vue";
import "./styles.css";
import { appPathname } from "./utils/appPaths";

const normalizedPath = appPathname.replace(/\/+$/, "") || "/";
const rootComponent = normalizedPath === "/"
  ? DiagnosisEntry
  : normalizedPath === "/organization"
    ? OrganizationDiagnosis
    : App;

createApp(rootComponent).mount("#root");
