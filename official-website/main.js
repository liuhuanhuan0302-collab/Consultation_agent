import { getSiteContent } from "./services/site-content.js";
import { selectBusinessModule, selectMetrics, toInternalHref } from "./adapters/site-content-adapter.js";
import { DIAGNOSIS_URL } from "./config.js";
import { getModuleStateContent } from "./ui/module-state.js";
import { formatEmpty, formatMetric, truncateText } from "./utils/formatters.js";
import { getNextTabIndex, setUrlParameter } from "./utils/interactions.js";

const menuToggle = /** @type {HTMLButtonElement | null} */ (document.querySelector(".menu-toggle"));
const mobilePanel = /** @type {HTMLElement | null} */ (document.querySelector(".mobile-panel"));
const siteHeader = document.querySelector(".site-header");
const viewportNotice = /** @type {HTMLElement | null} */ (document.querySelector("[data-viewport-notice]"));
const pageRequestController = new AbortController();
const founderLetter = /** @type {HTMLElement | null} */ (document.querySelector("[data-founder-letter]"));
const FOUNDER_LETTER_STORAGE_KEY = "youkun-founder-letter-dismissed";
const VIEWPORT_NOTICE_STORAGE_KEY = "youkun-viewport-notice-dismissed";
let founderLetterLastFocus = /** @type {HTMLElement | null} */ (null);
let viewportNoticeDismissedInMemory = false;

function hasDismissedViewportNotice() {
  if (viewportNoticeDismissedInMemory) return true;
  try {
    return window.sessionStorage.getItem(VIEWPORT_NOTICE_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function dismissViewportNotice() {
  viewportNoticeDismissedInMemory = true;
  try {
    window.sessionStorage.setItem(VIEWPORT_NOTICE_STORAGE_KEY, "true");
  } catch {
    // Private browsing may deny storage; the in-memory state still prevents repeats.
  }
}

function isDesktopLikeNarrowViewport() {
  const narrowViewport = window.matchMedia("(max-width: 1120px)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;
  const hoverAvailable = window.matchMedia("(hover: hover)").matches;
  return narrowViewport && finePointer && hoverAvailable;
}

function showViewportNoticeIfNeeded() {
  if (!viewportNotice || hasDismissedViewportNotice() || !isDesktopLikeNarrowViewport()) return;
  viewportNotice.hidden = false;
  viewportNotice.classList.add("is-visible");
}

if (viewportNotice) {
  viewportNotice.querySelector("[data-viewport-notice-close]")?.addEventListener("click", () => {
    dismissViewportNotice();
    viewportNotice.hidden = true;
    viewportNotice.classList.remove("is-visible");
  });
  window.setTimeout(showViewportNoticeIfNeeded, 180);
}

function hasDismissedFounderLetter() {
  try {
    return window.sessionStorage.getItem(FOUNDER_LETTER_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function dismissFounderLetter() {
  try {
    window.sessionStorage.setItem(FOUNDER_LETTER_STORAGE_KEY, "true");
  } catch {
    // Private browsing may deny storage; the dialog still closes for this visit.
  }
}

function closeFounderLetter({ restoreFocus = true } = {}) {
  if (!founderLetter) return;
  founderLetter.classList.remove("is-visible");
  document.body.classList.remove("founder-letter-active");
  dismissFounderLetter();
  // 先淡出（opacity 过渡），过渡结束后再真正隐藏，避免隐形遮罩拦截页面点击
  window.setTimeout(() => {
    founderLetter.setAttribute("aria-hidden", "true");
    founderLetter.hidden = true;
    if (restoreFocus) founderLetterLastFocus?.focus();
  }, 240);
}

function showFounderLetter() {
  if (!founderLetter || hasDismissedFounderLetter()) return;
  founderLetterLastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  founderLetter.hidden = false;
  founderLetter.setAttribute("aria-hidden", "false");
  document.body.classList.add("founder-letter-active");
  requestAnimationFrame(() => founderLetter.classList.add("is-visible"));
  const closeButton = founderLetter.querySelector("[data-founder-letter-close]");
  if (closeButton instanceof HTMLElement) closeButton.focus();
}

if (founderLetter) {
  founderLetter.querySelectorAll("[data-founder-letter-close]").forEach((element) => {
    element.addEventListener("click", () => closeFounderLetter());
  });
  founderLetter.querySelectorAll("[data-founder-letter-action]").forEach((element) => {
    element.addEventListener("click", () => closeFounderLetter({ restoreFocus: false }));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !founderLetter.hidden) closeFounderLetter();
  });
  window.setTimeout(showFounderLetter, 220);
}

document.querySelectorAll("[data-assessment-link]").forEach((element) => {
  if (element instanceof HTMLAnchorElement) element.href = DIAGNOSIS_URL;
});

function closeMobileMenu({ restoreFocus = false } = {}) {
  if (!menuToggle || !mobilePanel) return;
  mobilePanel.classList.remove("open");
  mobilePanel.setAttribute("aria-hidden", "true");
  menuToggle.setAttribute("aria-expanded", "false");
  menuToggle.setAttribute("aria-label", "打开导航菜单");
  if (restoreFocus) menuToggle.focus();
}

function openMobileMenu() {
  if (!menuToggle || !mobilePanel) return;
  mobilePanel.classList.add("open");
  mobilePanel.setAttribute("aria-hidden", "false");
  menuToggle.setAttribute("aria-expanded", "true");
  menuToggle.setAttribute("aria-label", "关闭导航菜单");
}

if (menuToggle && mobilePanel) {
  menuToggle.addEventListener("click", () => {
    if (mobilePanel.classList.contains("open")) closeMobileMenu();
    else openMobileMenu();
  });

  mobilePanel.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => closeMobileMenu());
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && mobilePanel.classList.contains("open")) {
      closeMobileMenu({ restoreFocus: true });
    }
  });

  document.addEventListener("pointerdown", (event) => {
    if (!(event.target instanceof Node)) return;
    if (mobilePanel.classList.contains("open") && siteHeader && !siteHeader.contains(event.target)) {
      closeMobileMenu();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 1023) closeMobileMenu();
  });
}

const navigationLinks = /** @type {NodeListOf<HTMLAnchorElement>} */ (
  document.querySelectorAll('.desktop-nav a[href^="#"], .mobile-panel a[href^="#"]')
);

/** @param {string} hash */
function setActiveNavigation(hash) {
  navigationLinks.forEach((link) => {
    const isCurrent = link.hash === hash;
    link.classList.toggle("active", isCurrent);
    if (isCurrent) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}

navigationLinks.forEach((link) => {
  link.addEventListener("click", () => setActiveNavigation(link.hash));
});

window.addEventListener("hashchange", () => setActiveNavigation(window.location.hash));
if (window.location.hash) setActiveNavigation(window.location.hash);

if ("IntersectionObserver" in window) {
  const navigationTargets = Array.from(new Set(Array.from(navigationLinks, (link) => link.hash)))
    .map((hash) => document.querySelector(hash))
    .filter((element) => element instanceof HTMLElement);

  const navigationObserver = new IntersectionObserver(
    (entries) => {
      const visibleEntry = entries
        .filter((entry) => entry.isIntersecting)
        .sort((first, second) => second.intersectionRatio - first.intersectionRatio)[0];
      if (visibleEntry?.target.id) setActiveNavigation(`#${visibleEntry.target.id}`);
    },
    { rootMargin: "-22% 0px -62%", threshold: [0, 0.2, 0.5] },
  );

  navigationTargets.forEach((target) => navigationObserver.observe(target));
}

/**
 * @param {ParentNode} root
 * @param {string} selector
 * @param {unknown} value
 * @param {string=} fallback
 */
function setText(root, selector, value, fallback) {
  const element = root.querySelector(selector);
  if (element) element.textContent = formatEmpty(value, fallback);
}

/** @param {HTMLElement} root */
function clearModuleMessage(root) {
  root.querySelector(":scope > .module-state")?.remove();
}

/**
 * @param {HTMLElement} root
 * @param {'loading' | 'success' | 'empty' | 'error'} state
 * @param {(() => void)=} retry
 */
function setModuleState(root, state, retry) {
  const stateContent = getModuleStateContent(state);
  clearModuleMessage(root);
  root.dataset.state = state;
  root.setAttribute("aria-busy", String(stateContent.ariaBusy));
  root.querySelectorAll("[data-list]").forEach((element) => {
    element.toggleAttribute("hidden", state === "empty");
  });

  if (state !== "error" && state !== "empty") return;

  const message = document.createElement("div");
  message.className = `module-state module-state-${state}`;
  message.setAttribute("role", state === "error" ? "alert" : "status");
  const messageText = document.createElement("span");
  messageText.textContent = stateContent.message;
  message.append(messageText);

  if (stateContent.canRetry && retry) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "module-retry";
    button.textContent = "重新加载";
    button.addEventListener("click", () => {
      button.disabled = true;
      button.textContent = "正在加载…";
      retry();
    }, { once: true });
    message.append(button);
  }

  root.append(message);
}

/**
 * @param {string} name
 * @param {(root: HTMLElement, content: import('./types/site-content.js').SiteContent) => boolean | void} render
 * @param {boolean} force
 */
async function hydrateModule(name, render, force = false) {
  const root = /** @type {HTMLElement | null} */ (document.querySelector(`[data-module="${name}"]`));
  if (!root) return;

  setModuleState(root, "loading");

  try {
    const content = await getSiteContent({ force, signal: pageRequestController.signal });
    if (pageRequestController.signal.aborted) return;
    const hasContent = render(root, content);
    setModuleState(root, hasContent === false ? "empty" : "success");
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    setModuleState(root, "error", () => hydrateModule(name, render, true));
  }
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderHero(root, content) {
  if (!content.hero?.title) return false;

  setText(root, '[data-field="hero.eyebrow"]', content.hero.eyebrow, content.company.positioning);
  setText(root, '[data-field="hero.title"]', content.hero.title, content.company.positioning);
  setText(root, '[data-field="hero.description"]', content.hero.description, content.company.profile);
  setText(root, '[data-field="facts.scenarioCount"]', formatMetric({ value: content.facts.scenarioCount, suffix: "+" }));
  setText(root, '[data-field="transformationStages.count"]', `${content.transformationStages.length} 阶段`);

  const actions = /** @type {NodeListOf<HTMLAnchorElement>} */ (root.querySelectorAll('[data-list="hero.actions"] a'));
  content.hero.actions.slice(0, actions.length).forEach((action, index) => {
    actions[index].textContent = action.label;
    actions[index].href = toInternalHref(action.href);
  });

  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderMetrics(root, content) {
  const metrics = selectMetrics(content);
  const host = root.querySelector('[data-list="metrics"]');
  if (!host || !metrics.length) return false;

  const fragment = document.createDocumentFragment();
  metrics.forEach((metric) => {
    const item = document.createElement("div");
    const value = document.createElement("strong");
    const label = document.createElement("span");
    value.textContent = formatMetric(metric);
    label.textContent = formatEmpty(metric.label);
    item.append(value, label);
    fragment.append(item);
  });
  host.replaceChildren(fragment);
  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderPainPoints(root, content) {
  const host = root.querySelector('[data-list="painPoints"]');
  if (!host || !content.painPoints.length) return false;

  const fragment = document.createDocumentFragment();
  content.painPoints.forEach((point, index) => {
    const card = document.createElement("article");
    card.className = "info-card";

    const icon = document.createElement("span");
    icon.className = "card-icon";
    icon.textContent = String(index + 1).padStart(2, "0");

    const title = document.createElement("h3");
    title.textContent = point.title;
    const lead = document.createElement("p");
    lead.className = "card-lead";
    lead.textContent = point.lead || "";
    const description = document.createElement("p");
    description.textContent = truncateText(point.description, 76);
    card.append(icon, title, lead, description);
    fragment.append(card);
  });

  host.replaceChildren(fragment);
  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderDiagnosis(root, content) {
  const diagnosis = content.diagnosis;
  if (!diagnosis?.dimensions.length) return false;

  setText(root, '[data-field="diagnosis.title"]', diagnosis.title);
  setText(root, '[data-field="diagnosis.description"]', diagnosis.description);
  setText(root, '[data-field="diagnosis.outputs"]', diagnosis.outputs.join(" / "));

  const host = root.querySelector('[data-list="diagnosis.dimensions"]');
  if (!host) return false;
  const fragment = document.createDocumentFragment();
  diagnosis.dimensions.forEach((dimension) => {
    const item = document.createElement("span");
    item.textContent = dimension;
    fragment.append(item);
  });
  host.replaceChildren(fragment);
  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderSolutions(root, content) {
  const host = root.querySelector('[data-list="solutions"]');
  if (!host || !content.solutions.length) return false;

  const fragment = document.createDocumentFragment();
  content.solutions.forEach((solution) => {
    const card = document.createElement("article");
    card.className = "solution-card";
    if (solution.id === "agent" || solution.id === "training") card.id = solution.id;

    const label = document.createElement("span");
    label.textContent = solution.label || "解决方案";
    const title = document.createElement("h3");
    title.textContent = solution.title;
    const description = document.createElement("p");
    description.textContent = solution.description;
    card.append(label, title, description);
    fragment.append(card);
  });
  host.replaceChildren(fragment);
  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderTransformationStages(root, content) {
  const host = root.querySelector('[data-list="transformationStages"]');
  if (!host || !content.transformationStages.length) return false;

  const fragment = document.createDocumentFragment();
  content.transformationStages.forEach((stage, index) => {
    const card = document.createElement("article");
    const order = document.createElement("span");
    order.className = "stage-order";
    order.textContent = String(index + 1).padStart(2, "0");
    const name = document.createElement("strong");
    name.textContent = stage.name;
    const description = document.createElement("p");
    description.textContent = stage.description;
    card.append(order, name, description);
    fragment.append(card);
  });
  host.replaceChildren(fragment);
  return true;
}

/**
 * @param {HTMLElement} root
 * @param {import('./types/site-content.js').BusinessModule | null} businessModule
 */
function updateBusinessContent(root, businessModule, labelledBy = "") {
  const host = root.querySelector('[data-list="businessModules.content"]');
  if (!host || !businessModule) return;
  host.setAttribute("aria-labelledby", labelledBy);

  const details = [
    ["核心内容", businessModule.core],
    ["客户价值", businessModule.value],
    ["服务方式", businessModule.method],
  ];
  const fragment = document.createDocumentFragment();
  details.forEach(([titleText, descriptionText]) => {
    const card = document.createElement("article");
    const title = document.createElement("h3");
    title.textContent = titleText;
    const description = document.createElement("p");
    description.textContent = descriptionText;
    card.append(title, description);
    fragment.append(card);
  });
  host.replaceChildren(fragment);
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderBusinessModules(root, content) {
  const host = root.querySelector('[data-list="businessModules.tabs"]');
  if (!host || !content.businessModules.length) return false;

  host.setAttribute("role", "tablist");
  const contentHost = /** @type {HTMLElement | null} */ (root.querySelector('[data-list="businessModules.content"]'));
  if (contentHost) {
    contentHost.id = "business-module-panel";
    contentHost.setAttribute("role", "tabpanel");
    contentHost.setAttribute("tabindex", "0");
  }

  const requestedModuleId = new URL(window.location.href).searchParams.get("service");
  const initialModule = selectBusinessModule(content, requestedModuleId || "");
  const initialModuleId = content.businessModules.some((item) => item.id === requestedModuleId)
    ? requestedModuleId
    : initialModule?.id;
  const fragment = document.createDocumentFragment();

  /**
   * @param {string} moduleId
   * @param {{focus?: boolean, syncUrl?: boolean}=} options
   */
  const activateModule = (moduleId, { focus = false, syncUrl = true } = {}) => {
    const selectedModule = selectBusinessModule(content, moduleId);
    if (!selectedModule) return;
    const buttons = /** @type {NodeListOf<HTMLButtonElement>} */ (host.querySelectorAll('[role="tab"]'));
    buttons.forEach((item) => {
      const isActive = item.dataset.moduleId === selectedModule.id;
      item.classList.toggle("active", isActive);
      item.setAttribute("aria-selected", String(isActive));
      item.tabIndex = isActive ? 0 : -1;
      if (isActive && focus) item.focus();
    });
    updateBusinessContent(root, selectedModule, `business-tab-${selectedModule.id}`);
    if (syncUrl) {
      window.history.replaceState(
        window.history.state,
        "",
        setUrlParameter(window.location.href, "service", selectedModule.id),
      );
    }
  };

  content.businessModules.forEach((businessModule) => {
    const button = document.createElement("button");
    button.type = "button";
    button.id = `business-tab-${businessModule.id}`;
    button.dataset.moduleId = businessModule.id;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", "business-module-panel");
    button.textContent = businessModule.name;
    const isInitial = businessModule.id === initialModuleId;
    button.classList.toggle("active", isInitial);
    button.setAttribute("aria-selected", String(isInitial));
    button.tabIndex = isInitial ? 0 : -1;
    button.addEventListener("click", () => {
      activateModule(businessModule.id);
    });
    button.addEventListener("keydown", (event) => {
      const buttons = /** @type {NodeListOf<HTMLButtonElement>} */ (host.querySelectorAll('[role="tab"]'));
      const currentIndex = Array.from(buttons).indexOf(button);
      const nextIndex = getNextTabIndex(currentIndex, buttons.length, event.key);
      if (nextIndex === currentIndex && !["Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const nextButton = buttons[nextIndex];
      if (nextButton?.dataset.moduleId) activateModule(nextButton.dataset.moduleId, { focus: true });
    });
    fragment.append(button);
  });

  host.replaceChildren(fragment);
  if (initialModuleId) activateModule(initialModuleId, { syncUrl: Boolean(requestedModuleId) });
  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderMethodology(root, content) {
  const principles = content.methodology?.principles || [];
  const host = root.querySelector('[data-list="methodology.principles"]');
  if (!host || !principles.length) return false;

  const fragment = document.createDocumentFragment();
  principles.forEach((principle) => {
    const item = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = principle.name;
    const description = document.createElement("span");
    description.textContent = principle.description;
    item.append(title, description);
    fragment.append(item);
  });
  host.replaceChildren(fragment);
  return true;
}

/** @param {HTMLElement} root @param {import('./types/site-content.js').SiteContent} content */
function renderAbout(root, content) {
  if (!content.company?.profile) return false;
  setText(root, '[data-field="company.profile"]', content.company.profile);
  setText(root, '[data-field="company.mission"]', content.company.mission);
  return true;
}

function restoreInitialHashPosition() {
  const hashId = window.location.hash.slice(1);
  if (!hashId) return;

  let targetId = hashId;
  try {
    targetId = decodeURIComponent(hashId);
  } catch {
    return;
  }

  const target = document.getElementById(targetId);
  if (!target) return;

  const root = document.documentElement;
  const previousScrollBehavior = root.style.scrollBehavior;
  root.style.scrollBehavior = "auto";
  target.scrollIntoView({ block: "start" });
  requestAnimationFrame(() => {
    root.style.scrollBehavior = previousScrollBehavior;
  });
}

const moduleHydration = [
  hydrateModule("hero", renderHero),
  hydrateModule("about", renderAbout),
  hydrateModule("metrics", renderMetrics),
  hydrateModule("painPoints", renderPainPoints),
  hydrateModule("diagnosis", renderDiagnosis),
  hydrateModule("solutions", renderSolutions),
  hydrateModule("transformationStages", renderTransformationStages),
  hydrateModule("businessModules", renderBusinessModules),
  hydrateModule("methodology", renderMethodology),
];

Promise.allSettled(moduleHydration).then(() => {
  requestAnimationFrame(restoreInitialHashPosition);
});

window.addEventListener("beforeunload", () => pageRequestController.abort(), { once: true });
