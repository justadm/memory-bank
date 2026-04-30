const STORAGE_KEYS = {
  theme: "memlayer-console-theme",
  locale: "memlayer-console-locale",
  apiBaseUrl: "memlayer-console-api-base-url",
  apiKey: "memlayer-console-api-key"
};

const LEGACY_API_BASE_URL = "http://127.0.0.1:18100";
const MEMORY_TYPES = ["decision", "task", "artifact", "event", "note", "constraint", "risk"];
const NAV_VIEWS = new Set(["dashboard", "projects", "memory", "review", "settings"]);

function defaultApiBaseUrl() {
  if (window.location.protocol === "https:" || window.location.protocol === "http:") {
    return window.location.origin;
  }
  return LEGACY_API_BASE_URL;
}

function resolveInitialApiBaseUrl() {
  const saved = localStorage.getItem(STORAGE_KEYS.apiBaseUrl);
  const preferred = defaultApiBaseUrl();

  if (!saved) {
    return preferred;
  }

  if ((window.location.protocol === "https:" || window.location.protocol === "http:") && (saved === LEGACY_API_BASE_URL || saved === `${window.location.origin}/api`)) {
    localStorage.setItem(STORAGE_KEYS.apiBaseUrl, preferred);
    return preferred;
  }

  return saved;
}

function normalizeView(view) {
  return NAV_VIEWS.has(view) ? view : "dashboard";
}

function baseConsolePath() {
  const marker = "/console";
  const index = window.location.pathname.indexOf(marker);
  return index >= 0 ? window.location.pathname.slice(0, index + marker.length) : "/console";
}

function routePathForView(view) {
  const normalized = normalizeView(view);
  return normalized === "dashboard" ? `${baseConsolePath()}/` : `${baseConsolePath()}/${normalized}`;
}

function resolveViewFromLocation() {
  const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
  const basePath = baseConsolePath().replace(/\/+$/, "");
  if (currentPath === basePath || currentPath === `${basePath}` || currentPath === `${basePath}/`) {
    return "dashboard";
  }
  if (!currentPath.startsWith(basePath)) {
    return "dashboard";
  }
  const suffix = currentPath.slice(basePath.length).replace(/^\/+/, "");
  return normalizeView(suffix.split("/")[0] || "dashboard");
}

const translations = {
  ru: {
    brandTitle: "MemLayer",
    brandSubtitle: "Control Console",
    banner: "Консоль уже работает внутри основного сервиса и подключается к live API Memory Bank: боковое меню, мобильный drawer, RU/EN, темы и tenant-aware auth.",
    apiStatus: "API status",
    apiHealthy: "Подключено",
    apiUnavailable: "Недоступно",
    currentView: "Текущий раздел",
    dashboard: "Панель",
    projects: "Проекты",
    memory: "Память",
    review: "Review",
    settings: "Настройки",
    desktopNote: "Встроенная консоль Memory Bank",
    themeLight: "Light",
    themeDark: "Dark",
    localeRu: "RU",
    localeEn: "EN",
    menu: "Меню",
    close: "Закрыть",
    refresh: "Обновить данные",
    saveSettings: "Сохранить настройки",
    apiBaseUrl: "API URL",
    apiKey: "API key",
    authState: "Auth",
    authRequired: "Для этого API нужен ключ. Добавь его в настройках консоли.",
    authDisabled: "Выключен",
    authAnonymous: "Гость",
    principal: "Principal",
    scopes: "Scopes",
    tenants: "Tenants",
    dashboardCards: {
      totalEntries: "Записи",
      activeEntries: "Активные",
      archivedEntries: "Архивные",
      links: "Связи",
      reuseRate: "Переиспользование",
      orphanRate: "Сироты",
      memoryUsage: "Использование памяти",
      avgQuality: "Среднее качество",
      totalTasks: "Задачи"
    },
    dashboardSections: {
      observability: "Observability Snapshot",
      topAgents: "Топ агентов",
      topExperiments: "Топ экспериментов",
      metrics: "Ключевые метрики",
      balance: "Структура памяти"
    },
    projectsTitle: "Управление проектами",
    createProject: "Создать проект",
    updateProject: "Обновить проект",
    projectName: "Название проекта",
    projectDescription: "Описание",
    projectTenantId: "Tenant ID",
    projectMetadata: "Metadata JSON",
    selectProject: "Выбор проекта",
    create: "Создать",
    update: "Сохранить",
    clear: "Очистить",
    memoryTitle: "Узлы памяти",
    memoryCreate: "Создать запись",
    memoryUpdate: "Изменить запись",
    memorySearch: "Поиск",
    searchMode: "Режим поиска",
    searchModeHybrid: "Hybrid",
    searchModeLexical: "Lexical",
    searchModeSemantic: "Semantic",
    memoryType: "Тип",
    projectFilter: "Проект",
    archiveFilter: "Архив",
    activeOnly: "Только активные",
    archivedOnly: "Только архивные",
    all: "Все",
    importance: "Важность",
    title: "Заголовок",
    content: "Контент",
    sourceAgent: "Source agent",
    archive: "Архивировать",
    conflictTitle: "Конфликты и review",
    conflictLimit: "Лимит конфликтов",
    recentTaskLogs: "Логи задач",
    importConflicts: "Import conflicts",
    noData: "Данные пока не найдены для текущего фильтра.",
    noSelection: "Сначала выбери объект из таблицы.",
    filters: "Фильтры",
    status: "Статус",
    generatedAt: "Сгенерировано",
    recentActivity: "Последняя активность",
    settingsHint: "Все пользовательские настройки хранятся локально в браузере и переедут вместе с фронтендом.",
    mobileHint: "Drawer и верхний shell адаптированы под мобильные экраны.",
    successSaved: "Настройки сохранены.",
    successProjectCreated: "Проект создан.",
    successProjectUpdated: "Проект обновлён.",
    successMemoryCreated: "Запись памяти создана.",
    successMemoryUpdated: "Запись памяти обновлена.",
    successMemoryArchived: "Запись памяти архивирована.",
    errorPrefix: "Ошибка",
    tableSummary: "Сводка",
    taskSummary: "Сводка логов",
    pickEntry: "Запись для редактирования",
    archivedState: "Архивный статус",
    quickOverview: "Быстрый обзор",
    recentProjects: "Недавние проекты",
    reviewQueue: "Очередь review",
    recentImports: "Последние импорты",
    importSummary: "Сводка импортов",
    dashboardProjectCount: "Проектов",
    dashboardConflictCount: "Конфликтов",
    dashboardAgentCount: "Агентов",
    recentUpdated: "Последнее обновление",
    settingsTitle: "Настройки консоли",
    settingsDescription: "Управление локальными параметрами фронтенда, темой, языком и API-адресом.",
    dashboardPageTitle: "Admin Dashboard",
    dashboardPageDescription: "Операционный центр для проекта MemoryBank: метрики, проекты, память, review и качество агентной работы.",
    projectsPageTitle: "Projects Workspace",
    projectsPageDescription: "Создание, редактирование и обзор проектов, импортированных в MemoryBank.",
    memoryPageTitle: "Memory Workspace",
    memoryPageDescription: "Поиск, фильтрация и ручная правка узлов памяти в едином рабочем слое.",
    reviewPageTitle: "Review Queue",
    reviewPageDescription: "Конфликты импорта и task logs, которые требуют внимания оператора.",
    settingsPageTitle: "Console Settings",
    settingsPageDescription: "Локальные настройки интерфейса и соединения с API.",
    select: "Выбрать",
    selected: "Выбрано",
    rows: "строк",
    headers: {
      id: "ID",
      name: "Название",
      description: "Описание",
      created_at: "Создано",
      updated_at: "Обновлено",
      type: "Тип",
      title: "Заголовок",
      importance: "Важность",
      usage_count: "Использований",
      archived: "Архив",
      score: "Score",
      project_id: "Проект",
      entry_id: "Запись",
      requires_review: "Нужен review",
      agent_id: "Agent",
      experiment_id: "Experiment",
      task_description: "Задача",
      used_memory: "Исп. память",
      result_quality_score: "Качество",
      logged_at: "Лог",
      source_agent: "Source agent"
    },
    importHeaders: {
      project_name: "Проект",
      source_path: "Путь",
      imported_entries_count: "Импорт записей",
      import_events_count: "Import events",
      conflicts_detected_count: "Конфликты",
      last_imported_at: "Последний импорт"
    },
    searchInTable: "Поиск по таблице",
    selectedCount: "выбрано",
    archiveSelected: "Архивировать выбранные",
    clearSelection: "Снять выбор"
  },
  en: {
    brandTitle: "MemLayer",
    brandSubtitle: "Control Console",
    banner: "This console now lives inside the main service and talks directly to the live Memory Bank API: sidebar, mobile drawer, RU/EN, themes, and tenant-aware auth.",
    apiStatus: "API status",
    apiHealthy: "Connected",
    apiUnavailable: "Unavailable",
    currentView: "Current section",
    dashboard: "Dashboard",
    projects: "Projects",
    memory: "Memory",
    review: "Review",
    settings: "Settings",
    desktopNote: "Embedded Memory Bank console",
    themeLight: "Light",
    themeDark: "Dark",
    localeRu: "RU",
    localeEn: "EN",
    menu: "Menu",
    close: "Close",
    refresh: "Refresh data",
    saveSettings: "Save settings",
    apiBaseUrl: "API URL",
    apiKey: "API key",
    authState: "Auth",
    authRequired: "This API requires a key. Add one in console settings.",
    authDisabled: "Disabled",
    authAnonymous: "Guest",
    principal: "Principal",
    scopes: "Scopes",
    tenants: "Tenants",
    dashboardCards: {
      totalEntries: "Entries",
      activeEntries: "Active",
      archivedEntries: "Archived",
      links: "Links",
      reuseRate: "Reuse rate",
      orphanRate: "Orphan rate",
      memoryUsage: "Memory usage",
      avgQuality: "Average quality",
      totalTasks: "Tasks"
    },
    dashboardSections: {
      observability: "Observability Snapshot",
      topAgents: "Top agents",
      topExperiments: "Top experiments",
      metrics: "Key metrics",
      balance: "Memory balance"
    },
    projectsTitle: "Project management",
    createProject: "Create project",
    updateProject: "Update project",
    projectName: "Project name",
    projectDescription: "Description",
    projectTenantId: "Tenant ID",
    projectMetadata: "Metadata JSON",
    selectProject: "Select project",
    create: "Create",
    update: "Save",
    clear: "Clear",
    memoryTitle: "Memory entries",
    memoryCreate: "Create entry",
    memoryUpdate: "Update entry",
    memorySearch: "Search",
    searchMode: "Search mode",
    searchModeHybrid: "Hybrid",
    searchModeLexical: "Lexical",
    searchModeSemantic: "Semantic",
    memoryType: "Type",
    projectFilter: "Project",
    archiveFilter: "Archive",
    activeOnly: "Active only",
    archivedOnly: "Archived only",
    all: "All",
    importance: "Importance",
    title: "Title",
    content: "Content",
    sourceAgent: "Source agent",
    archive: "Archive",
    conflictTitle: "Conflicts and review",
    conflictLimit: "Conflict limit",
    recentTaskLogs: "Task logs",
    importConflicts: "Import conflicts",
    noData: "No data for the current filter.",
    noSelection: "Select an item from the table first.",
    filters: "Filters",
    status: "Status",
    generatedAt: "Generated at",
    recentActivity: "Recent activity",
    settingsHint: "All user settings are stored locally in the browser and will travel with the frontend later.",
    mobileHint: "Drawer and top shell are adapted for mobile screens.",
    successSaved: "Settings saved.",
    successProjectCreated: "Project created.",
    successProjectUpdated: "Project updated.",
    successMemoryCreated: "Memory entry created.",
    successMemoryUpdated: "Memory entry updated.",
    successMemoryArchived: "Memory entry archived.",
    errorPrefix: "Error",
    tableSummary: "Summary",
    taskSummary: "Task log summary",
    pickEntry: "Entry to edit",
    archivedState: "Archived state",
    quickOverview: "Quick overview",
    recentProjects: "Recent projects",
    reviewQueue: "Review queue",
    recentImports: "Recent imports",
    importSummary: "Import summary",
    dashboardProjectCount: "Projects",
    dashboardConflictCount: "Conflicts",
    dashboardAgentCount: "Agents",
    recentUpdated: "Recently updated",
    settingsTitle: "Console settings",
    settingsDescription: "Manage local frontend preferences, theme, locale and API endpoint.",
    dashboardPageTitle: "Admin Dashboard",
    dashboardPageDescription: "Operational console for MemoryBank: metrics, projects, memory curation, review queues and agent quality signals.",
    projectsPageTitle: "Projects Workspace",
    projectsPageDescription: "Create, update and inspect projects imported into MemoryBank.",
    memoryPageTitle: "Memory Workspace",
    memoryPageDescription: "Search, filter and manually curate memory entries in a single working surface.",
    reviewPageTitle: "Review Queue",
    reviewPageDescription: "Import conflicts and task logs that need operator attention.",
    settingsPageTitle: "Console Settings",
    settingsPageDescription: "Local interface and API connection preferences.",
    select: "Select",
    selected: "Selected",
    rows: "rows",
    headers: {
      id: "ID",
      name: "Name",
      description: "Description",
      created_at: "Created",
      updated_at: "Updated",
      type: "Type",
      title: "Title",
      importance: "Importance",
      usage_count: "Usage",
      archived: "Archived",
      score: "Score",
      project_id: "Project",
      entry_id: "Entry",
      requires_review: "Needs review",
      agent_id: "Agent",
      experiment_id: "Experiment",
      task_description: "Task",
      used_memory: "Used memory",
      result_quality_score: "Quality",
      logged_at: "Logged",
      source_agent: "Source agent"
    },
    importHeaders: {
      project_name: "Project",
      source_path: "Path",
      imported_entries_count: "Imported entries",
      import_events_count: "Import events",
      conflicts_detected_count: "Conflicts",
      last_imported_at: "Last import"
    },
    searchInTable: "Search table",
    selectedCount: "selected",
    archiveSelected: "Archive selected",
    clearSelection: "Clear selection"
  }
};

const state = {
  theme: localStorage.getItem(STORAGE_KEYS.theme) || "dark",
  locale: localStorage.getItem(STORAGE_KEYS.locale) || "ru",
  apiBaseUrl: resolveInitialApiBaseUrl(),
  apiKey: localStorage.getItem(STORAGE_KEYS.apiKey) || "",
  currentView: resolveViewFromLocation(),
  drawerOpen: false,
  messages: [],
  apiHealthy: false,
  auth: null,
  loading: false,
  projects: [],
  observability: null,
  metrics: null,
  taskSummary: null,
  conflicts: [],
  importSummaries: [],
  taskLogs: [],
  memoryItems: [],
  memorySearchResults: [],
  projectFocus: null,
  selectedProjectId: "",
  selectedMemoryId: "",
  selectedMemoryIds: [],
  tableStates: {
    projects: { page: 1, pageSize: 6, sortKey: "updated_at", sortDir: "desc" },
    projectRecentMemory: { page: 1, pageSize: 5, sortKey: "updated_at", sortDir: "desc" },
    projectConflicts: { page: 1, pageSize: 5, sortKey: "created_at", sortDir: "desc" },
    memory: { page: 1, pageSize: 8, sortKey: "updated_at", sortDir: "desc" },
    memorySearch: { page: 1, pageSize: 6, sortKey: "score", sortDir: "desc" },
    reviewConflicts: { page: 1, pageSize: 8, sortKey: "created_at", sortDir: "desc" },
    reviewTasks: { page: 1, pageSize: 8, sortKey: "logged_at", sortDir: "desc" },
    dashboardRecentProjects: { page: 1, pageSize: 5, sortKey: "updated_at", sortDir: "desc" },
    dashboardReviewQueue: { page: 1, pageSize: 5, sortKey: "created_at", sortDir: "desc" },
    dashboardImportSummaries: { page: 1, pageSize: 6, sortKey: "last_imported_at", sortDir: "desc" },
    reviewImportSummaries: { page: 1, pageSize: 8, sortKey: "last_imported_at", sortDir: "desc" }
  },
  forms: {
    dashboardAgentId: "",
    dashboardExperimentId: "",
    conflictAgentId: "",
    conflictExperimentId: "",
    conflictLimit: "20",
    memoryType: "",
    memoryArchived: "false",
    memoryQuery: "",
    memorySearchMode: "hybrid",
    projectSearch: "",
    projectMemorySearch: "",
    reviewTaskSearch: "",
    reviewConflictSearch: ""
  }
};

const navItems = [
  { key: "dashboard", icon: "◔" },
  { key: "projects", icon: "⌘" },
  { key: "memory", icon: "◎" },
  { key: "review", icon: "≈" },
  { key: "settings", icon: "⚙" }
];

const root = document.querySelector("#app");

function t(path) {
  const parts = path.split(".");
  let value = translations[state.locale];
  for (const part of parts) {
    value = value?.[part];
  }
  return value ?? path;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  if (typeof value === "number" && !Number.isInteger(value)) {
    return value.toFixed(2);
  }
  return Intl.NumberFormat(state.locale === "ru" ? "ru-RU" : "en-US").format(Number(value));
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatDate(value) {
  if (!value) {
    return "n/a";
  }
  const locale = state.locale === "ru" ? "ru-RU" : "en-US";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function authStateLabel() {
  if (!state.auth?.auth_enabled) {
    return t("authDisabled");
  }
  if (!state.auth?.authenticated) {
    return t("authAnonymous");
  }
  return state.auth.principal_name || t("authAnonymous");
}

function authScopesLabel() {
  if (!state.auth?.authenticated || !state.auth?.scopes?.length) {
    return "n/a";
  }
  return state.auth.scopes.join(", ");
}

function authTenantsLabel() {
  if (!state.auth?.tenant_ids?.length) {
    return "all";
  }
  return state.auth.tenant_ids.join(", ");
}

function searchModeLabel(mode) {
  const normalized = String(mode || "hybrid").toLowerCase();
  if (normalized === "lexical") {
    return t("searchModeLexical");
  }
  if (normalized === "semantic") {
    return t("searchModeSemantic");
  }
  return t("searchModeHybrid");
}

function renderAuthChips() {
  const chips = [
    `<span class="chip">${escapeHtml(t("authState"))}: ${escapeHtml(authStateLabel())}</span>`
  ];
  if (state.auth?.authenticated && state.auth?.scopes?.length) {
    chips.push(`<span class="chip">${escapeHtml(t("scopes"))}: ${escapeHtml(authScopesLabel())}</span>`);
  }
  if (state.auth?.authenticated) {
    chips.push(`<span class="chip">${escapeHtml(t("tenants"))}: ${escapeHtml(authTenantsLabel())}</span>`);
  }
  return chips.join("");
}

async function navigateToView(view, { push = true } = {}) {
  const normalized = normalizeView(view);
  state.currentView = normalized;
  if (push) {
    window.history.pushState({ view: normalized }, "", routePathForView(normalized));
  }
  state.drawerOpen = false;
  await loadCurrentView();
}

function compareValues(left, right, sortKey) {
  const leftValue = left?.[sortKey];
  const rightValue = right?.[sortKey];
  if (leftValue === rightValue) {
    return 0;
  }
  if (leftValue === null || leftValue === undefined) {
    return 1;
  }
  if (rightValue === null || rightValue === undefined) {
    return -1;
  }
  if (sortKey.endsWith("_at") || sortKey === "logged_at" || sortKey === "created_at" || sortKey === "updated_at") {
    return new Date(leftValue).getTime() - new Date(rightValue).getTime();
  }
  if (typeof leftValue === "number" || typeof rightValue === "number") {
    return Number(leftValue) - Number(rightValue);
  }
  return String(leftValue).localeCompare(String(rightValue), state.locale === "ru" ? "ru" : "en", { sensitivity: "base" });
}

function getTableState(tableKey) {
  if (!tableKey) {
    return null;
  }
  if (!state.tableStates[tableKey]) {
    state.tableStates[tableKey] = { page: 1, pageSize: 8, sortKey: "updated_at", sortDir: "desc" };
  }
  return state.tableStates[tableKey];
}

function getProcessedTableItems(items, options = {}) {
  const tableState = getTableState(options.tableKey);
  const list = Array.isArray(items) ? [...items] : [];

  if (options.filterQuery) {
    const query = options.filterQuery.trim().toLowerCase();
    if (query) {
      const filterKeys = (options.filterKeys || options.columns || []).map((column) => (typeof column === "string" ? column : column.key));
      items = list.filter((item) =>
        filterKeys.some((key) => {
          const value = item?.[key];
          if (value === null || value === undefined) {
            return false;
          }
          return String(typeof value === "object" ? JSON.stringify(value) : value)
            .toLowerCase()
            .includes(query);
        })
      );
    } else {
      items = list;
    }
  } else {
    items = list;
  }

  if (!tableState) {
    return { items, pageItems: items, totalPages: 1, page: 1, pageSize: items.length || 1, totalItems: items.length };
  }

  const sorted = [...items].sort((left, right) => {
    const direction = tableState.sortDir === "asc" ? 1 : -1;
    return compareValues(left, right, tableState.sortKey) * direction;
  });

  const totalItems = sorted.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / tableState.pageSize));
  tableState.page = Math.min(Math.max(1, tableState.page), totalPages);
  const start = (tableState.page - 1) * tableState.pageSize;
  const pageItems = sorted.slice(start, start + tableState.pageSize);
  return {
    items: sorted,
    pageItems,
    totalPages,
    page: tableState.page,
    pageSize: tableState.pageSize,
    totalItems
  };
}

function getProjectOptions() {
  const base = [{ value: "", label: state.locale === "ru" ? "Все проекты" : "All projects" }];
  return base.concat(
    state.projects.map((project) => ({
      value: project.id,
      label: `${project.name}`
    }))
  );
}

function pushMessage(type, text) {
  const normalized = String(text || "").trim();
  const existingIndex = state.messages.findIndex((message) => message.type === type && message.text === normalized);
  if (existingIndex >= 0) {
    const [existing] = state.messages.splice(existingIndex, 1);
    state.messages = [existing, ...state.messages].slice(0, 4);
  } else {
    state.messages = [{ id: crypto.randomUUID(), type, text: normalized }, ...state.messages].slice(0, 4);
  }
  render();
}

function clearMessagesByType(type) {
  state.messages = state.messages.filter((message) => message.type !== type);
}

function currentPageMeta() {
  const map = {
    dashboard: {
      title: t("dashboardPageTitle"),
      description: t("dashboardPageDescription")
    },
    projects: {
      title: t("projectsPageTitle"),
      description: t("projectsPageDescription")
    },
    memory: {
      title: t("memoryPageTitle"),
      description: t("memoryPageDescription")
    },
    review: {
      title: t("reviewPageTitle"),
      description: t("reviewPageDescription")
    },
    settings: {
      title: t("settingsPageTitle"),
      description: t("settingsPageDescription")
    }
  };
  return map[state.currentView] || map.dashboard;
}

async function apiRequest(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };
  if (state.apiKey) {
    headers.Authorization = `Bearer ${state.apiKey}`;
  }
  const response = await fetch(`${state.apiBaseUrl}${path}`, {
    headers,
    ...options
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(`${t("errorPrefix")}: ${response.status} ${detail}`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return response.json();
}

async function loadHealth() {
  try {
    const payload = await apiRequest("/health");
    state.apiHealthy = payload?.status === "ok" || Boolean(payload);
  } catch {
    state.apiHealthy = false;
  }
}

async function loadAuthStatus() {
  try {
    state.auth = await apiRequest("/auth/me");
  } catch {
    state.auth = null;
  }
}

async function loadProjects() {
  state.projects = await apiRequest("/projects");
}

async function loadDashboardData() {
  const params = new URLSearchParams();
  if (state.selectedProjectId) {
    params.set("project_id", state.selectedProjectId);
  }
  if (state.forms.dashboardAgentId) {
    params.set("agent_id", state.forms.dashboardAgentId);
  }
  if (state.forms.dashboardExperimentId) {
    params.set("experiment_id", state.forms.dashboardExperimentId);
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const [metrics, observability, taskSummary, conflicts] = await Promise.all([
    apiRequest(`/metrics/overview${query}`),
    apiRequest("/admin/observability/summary"),
    apiRequest(`/task-logs/summary${query}`),
    apiRequest(`/admin/import-conflicts?limit=5${state.selectedProjectId ? `&project_id=${encodeURIComponent(state.selectedProjectId)}` : ""}`)
  ]);
  const importSummaries = await apiRequest("/admin/imports/summary?limit=6");
  state.metrics = metrics;
  state.observability = observability;
  state.taskSummary = taskSummary;
  state.conflicts = conflicts.items || [];
  state.importSummaries = importSummaries.items || [];
}

async function loadProjectFocusData() {
  if (!state.selectedProjectId) {
    state.projectFocus = null;
    return;
  }
  const projectId = encodeURIComponent(state.selectedProjectId);
  const [metrics, recentMemory, conflicts] = await Promise.all([
    apiRequest(`/metrics/overview?project_id=${projectId}`),
    apiRequest(`/memory?project_id=${projectId}&archived=false`),
    apiRequest(`/admin/import-conflicts?project_id=${projectId}&limit=20`)
  ]);
  state.projectFocus = {
    metrics,
    recentMemory: recentMemory.items || [],
    conflicts: conflicts.items || []
  };
}

async function loadMemoryData() {
  const listParams = new URLSearchParams();
  if (state.selectedProjectId) {
    listParams.set("project_id", state.selectedProjectId);
  }
  if (state.forms.memoryType) {
    listParams.set("type", state.forms.memoryType);
  }
  if (state.forms.memoryArchived !== "all") {
    listParams.set("archived", state.forms.memoryArchived);
  }
  const listQuery = listParams.toString() ? `?${listParams.toString()}` : "";
  const listing = await apiRequest(`/memory${listQuery}`);
  state.memoryItems = listing.items || [];

  if (state.forms.memoryQuery.trim()) {
    const searchParams = new URLSearchParams({ query: state.forms.memoryQuery.trim(), limit: "20" });
    searchParams.set("mode", state.forms.memorySearchMode || "hybrid");
    if (state.selectedProjectId) {
      searchParams.set("project_id", state.selectedProjectId);
    }
    const searchResults = await apiRequest(`/memory/search?${searchParams.toString()}`);
    state.memorySearchResults = searchResults.items || [];
  } else {
    state.memorySearchResults = [];
  }
}

async function loadReviewData() {
  const conflictParams = new URLSearchParams({ limit: state.forms.conflictLimit || "20" });
  if (state.selectedProjectId) {
    conflictParams.set("project_id", state.selectedProjectId);
  }
  const taskParams = new URLSearchParams();
  if (state.forms.conflictAgentId) {
    taskParams.set("agent_id", state.forms.conflictAgentId);
  }
  if (state.forms.conflictExperimentId) {
    taskParams.set("experiment_id", state.forms.conflictExperimentId);
  }
  const [conflicts, taskLogs, taskSummary] = await Promise.all([
    apiRequest(`/admin/import-conflicts?${conflictParams.toString()}`),
    apiRequest(`/task-logs?${taskParams.toString()}`),
    apiRequest(`/task-logs/summary?${taskParams.toString()}`)
  ]);
  const importSummaries = await apiRequest("/admin/imports/summary?limit=20");
  state.conflicts = conflicts.items || [];
  state.taskLogs = taskLogs.items || [];
  state.taskSummary = taskSummary;
  state.importSummaries = importSummaries.items || [];
}

async function loadCurrentView() {
  state.loading = true;
  render();
  try {
    await loadHealth();
    await loadAuthStatus();
    if (state.auth?.auth_enabled && !state.auth?.authenticated) {
      state.projects = [];
      state.metrics = null;
      state.observability = null;
      state.taskSummary = null;
      state.conflicts = [];
      state.taskLogs = [];
      state.memoryItems = [];
      state.memorySearchResults = [];
      state.projectFocus = null;
      clearMessagesByType("error");
      clearMessagesByType("info");
      pushMessage("info", t("authRequired"));
      return;
    }
    await loadProjects();
    if ((state.currentView === "projects" || state.currentView === "memory") && !state.selectedProjectId && state.projects[0]?.id) {
      state.selectedProjectId = state.projects[0].id;
    }
    if (state.currentView === "dashboard") {
      await loadDashboardData();
    }
    if (state.currentView === "projects") {
      await loadProjectFocusData();
    }
    if (state.currentView === "memory") {
      await loadMemoryData();
      if (!state.selectedMemoryId && state.memoryItems[0]?.id) {
        state.selectedMemoryId = state.memoryItems[0].id;
      }
    }
    if (state.currentView === "review") {
      await loadReviewData();
    }
    clearMessagesByType("error");
  } catch (error) {
    pushMessage("error", error.message);
  } finally {
    state.loading = false;
    render();
  }
}

function navMarkup({ mobile = false } = {}) {
  return `
    <ul class="nav-list">
      ${navItems
        .map(
          (item) => `
        <li>
          <button class="nav-link ${state.currentView === item.key ? "active" : ""}" data-action="navigate" data-view="${item.key}" ${
            mobile ? 'data-close-drawer="true"' : ""
          }>
            <span class="nav-icon">${item.icon}</span>
            <span>${escapeHtml(t(item.key))}</span>
          </button>
        </li>`
        )
        .join("")}
    </ul>
  `;
}

function messagesMarkup() {
  if (!state.messages.length) {
    return "";
  }
  return `
    <div class="message-stack">
      ${state.messages
        .map((message) => `<div class="message ${message.type}">${escapeHtml(message.text)}</div>`)
        .join("")}
    </div>
  `;
}

function projectSelectMarkup(name, selectedValue = "", includeAll = true) {
  const options = includeAll ? getProjectOptions() : state.projects.map((project) => ({ value: project.id, label: project.name }));
  return `
    <select name="${escapeHtml(name)}">
      ${options
        .map(
          (option) => `
        <option value="${escapeHtml(option.value)}" ${selectedValue === option.value ? "selected" : ""}>
          ${escapeHtml(option.label)}
        </option>`
        )
        .join("")}
    </select>
  `;
}

function columnLabel(column) {
  const importLabel = t(`importHeaders.${column}`);
  if (importLabel !== `importHeaders.${column}`) {
    return importLabel;
  }
  return t(`headers.${column}`);
}

function normalizeColumns(columns) {
  return columns.map((column) => (typeof column === "string" ? { key: column, label: columnLabel(column) } : column));
}

function renderStatusChip(value) {
  const normalized = typeof value === "string" ? value.toLowerCase() : value;
  let statusClass = "";
  let text = value;
  if (typeof normalized === "boolean") {
    statusClass = normalized ? "status-true" : "status-false";
    text = normalized ? "true" : "false";
  } else if (normalized === "active" || normalized === "ok") {
    statusClass = "status-active";
  } else if (normalized === "archived") {
    statusClass = "status-archived";
  } else if (normalized === "review" || normalized === "requires_review") {
    statusClass = "status-review";
  }
  return `<span class="chip ${statusClass}">${escapeHtml(text)}</span>`;
}

function formatCellValue(column, value) {
  if (value === null || value === undefined || value === "") {
    return `<span class="muted">n/a</span>`;
  }
  if (typeof value === "boolean") {
    return renderStatusChip(value);
  }
  if (column === "archived" || column === "requires_review" || column === "used_memory") {
    return renderStatusChip(Boolean(value));
  }
  if (column.endsWith("_at") || column === "logged_at" || column === "created_at" || column === "updated_at") {
    return escapeHtml(formatDate(value));
  }
  if (column === "importance" || column === "usage_count" || column === "score" || column === "result_quality_score") {
    return escapeHtml(formatNumber(value));
  }
  if (typeof value === "object") {
    return `<span class="mono">${escapeHtml(JSON.stringify(value))}</span>`;
  }
  if (String(value).length > 90 && (column === "description" || column === "task_description" || column === "content")) {
    return escapeHtml(String(value).slice(0, 90)) + "…";
  }
  return escapeHtml(String(value));
}

function renderBarRow(label, value) {
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  return `
    <div class="bar-row">
      <div class="bar-head">
        <span>${escapeHtml(label)}</span>
        <span class="mono">${safe.toFixed(1)}%</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${safe}%;"></div></div>
    </div>
  `;
}

function renderTableSearchField(name, value) {
  return `
    <div class="field" style="min-width: 220px; margin-bottom: 12px;">
      <label>${escapeHtml(t("searchInTable"))}</label>
      <input name="${escapeHtml(name)}" value="${escapeHtml(value || "")}" />
    </div>
  `;
}

function renderDashboardView() {
  const metrics = state.metrics;
  const observability = state.observability;
  if (!metrics || !observability) {
    return `<div class="empty-state">${escapeHtml(t("noData"))}</div>`;
  }

  const cards = [
    { label: t("dashboardCards.totalEntries"), value: formatNumber(metrics.memory.total_entries), meta: `${t("dashboardCards.activeEntries")} ${formatNumber(metrics.memory.active_entries)}` },
    { label: t("dashboardCards.archivedEntries"), value: formatNumber(metrics.memory.archived_entries), meta: `${t("dashboardCards.links")} ${formatNumber(metrics.graph.total_links)}` },
    { label: t("dashboardCards.totalTasks"), value: formatNumber(metrics.tasks.total_tasks), meta: `${t("dashboardCards.memoryUsage")} ${formatPercent(metrics.tasks.memory_usage_rate)}` },
    { label: t("dashboardCards.reuseRate"), value: formatPercent(metrics.memory.reuse_rate), meta: `${t("dashboardCards.orphanRate")} ${formatPercent(metrics.memory.orphan_rate)}` },
    { label: t("dashboardCards.avgQuality"), value: formatNumber(metrics.tasks.avg_quality_score), meta: `${t("dashboardCards.memoryUsage")} ${formatPercent(state.taskSummary?.memory_usage_rate)}` },
    { label: t("dashboardCards.links"), value: formatNumber(metrics.graph.total_links), meta: `avg link strength ${formatNumber(metrics.graph.avg_link_strength)}` }
  ];

  const topAgentsCount = observability.top_agents?.length || 0;
  const reviewQueueCount = state.conflicts?.length || 0;
  const recentProjects = [...state.projects]
    .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
    .slice(0, 5);

  return `
    <div class="toolbar-card panel">
      <div class="field-grid compact">
        <div class="field">
          <label>${escapeHtml(t("projectFilter"))}</label>
          ${projectSelectMarkup("selectedProjectId", state.selectedProjectId, true)}
        </div>
        <div class="field">
          <label>Agent ID</label>
          <input name="dashboardAgentId" value="${escapeHtml(state.forms.dashboardAgentId)}" />
        </div>
        <div class="field">
          <label>Experiment ID</label>
          <input name="dashboardExperimentId" value="${escapeHtml(state.forms.dashboardExperimentId)}" />
        </div>
      </div>
      <div class="form-actions">
        <button class="primary-button" data-action="refresh-view">${escapeHtml(t("refresh"))}</button>
      </div>
    </div>

    <section class="cards-grid">
      ${cards
        .map(
          (card) => `
        <article class="panel stat-card">
          <div class="stat-label">${escapeHtml(card.label)}</div>
          <div class="stat-value">${escapeHtml(card.value)}</div>
          <div class="stat-meta">${escapeHtml(card.meta)}</div>
        </article>`
        )
        .join("")}
    </section>

    <section class="panel-grid">
      <article class="panel">
        <h3>${escapeHtml(t("dashboardSections.metrics"))}</h3>
        <div class="metrics-list">
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("status"))}</span><span class="metric-value">${escapeHtml(observability.status)}</span></div>
          <div class="metric-row"><span class="metric-name">Environment</span><span class="metric-value">${escapeHtml(observability.environment)}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("generatedAt"))}</span><span class="metric-value">${escapeHtml(formatDate(observability.generated_at))}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("recentActivity"))}</span><span class="metric-value">${escapeHtml(formatNumber(observability.recent_activity.memory_entries_created))} memory / ${escapeHtml(formatNumber(observability.recent_activity.task_logs_created))} logs</span></div>
        </div>
      </article>
      <article class="panel">
        <h3>${escapeHtml(t("dashboardSections.observability"))}</h3>
        <div class="metrics-list">
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("dashboardCards.reuseRate"))}</span><span class="metric-value">${escapeHtml(formatPercent(observability.memory.reuse_rate))}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("dashboardCards.orphanRate"))}</span><span class="metric-value">${escapeHtml(formatPercent(observability.memory.orphan_rate))}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("dashboardCards.avgQuality"))}</span><span class="metric-value">${escapeHtml(formatNumber(observability.tasks.avg_quality_score))}</span></div>
          <div class="metric-row"><span class="metric-name">Consistency</span><span class="metric-value">${escapeHtml(formatNumber(observability.tasks.avg_consistency_score))}</span></div>
        </div>
      </article>
    </section>

    <section class="panel" style="margin-top:18px;">
      <h3>${escapeHtml(t("dashboardSections.balance"))}</h3>
      <div class="bar-list">
        ${renderBarRow(t("dashboardCards.reuseRate"), Number(metrics.memory.reuse_rate) * 100)}
        ${renderBarRow(t("dashboardCards.orphanRate"), Number(metrics.memory.orphan_rate) * 100)}
        ${renderBarRow(t("dashboardCards.memoryUsage"), Number(metrics.tasks.memory_usage_rate) * 100)}
      </div>
    </section>

    <section class="stack" style="margin-top:18px;">
      <article class="panel">
        <h3>${escapeHtml(t("quickOverview"))}</h3>
        <div class="summary-grid">
          <div class="summary-tile">
            <div class="summary-kicker">${escapeHtml(t("dashboardProjectCount"))}</div>
            <div class="summary-value">${escapeHtml(formatNumber(state.projects.length))}</div>
            <div class="summary-copy">${escapeHtml(t("recentUpdated"))}: ${escapeHtml(recentProjects[0] ? formatDate(recentProjects[0].updated_at) : "n/a")}</div>
          </div>
          <div class="summary-tile">
            <div class="summary-kicker">${escapeHtml(t("dashboardConflictCount"))}</div>
            <div class="summary-value">${escapeHtml(formatNumber(reviewQueueCount))}</div>
            <div class="summary-copy">${escapeHtml(t("reviewQueue"))}</div>
          </div>
          <div class="summary-tile">
            <div class="summary-kicker">${escapeHtml(t("dashboardAgentCount"))}</div>
            <div class="summary-value">${escapeHtml(formatNumber(topAgentsCount))}</div>
            <div class="summary-copy">${escapeHtml(t("dashboardSections.topAgents"))}</div>
          </div>
        </div>
      </article>

      <section class="split">
        <article class="table-card">
          <h3>${escapeHtml(t("recentProjects"))}</h3>
          ${renderTable(recentProjects, ["name", "description", "updated_at"], {
            tableKey: "dashboardRecentProjects"
          })}
        </article>
        <article class="table-card">
          <h3>${escapeHtml(t("reviewQueue"))}</h3>
          ${renderTable((state.conflicts || []).slice(0, 5), ["title", "type", "requires_review", "created_at"], {
            tableKey: "dashboardReviewQueue"
          })}
        </article>
      </section>

      <section class="table-card" style="margin-top:18px;">
        <h3>${escapeHtml(t("recentImports"))}</h3>
        ${renderTable((state.importSummaries || []).slice(0, 6), ["project_name", "source_path", "imported_entries_count", "conflicts_detected_count", "last_imported_at"], {
          tableKey: "dashboardImportSummaries"
        })}
      </section>
    </section>

    <section class="split" style="margin-top:18px;">
      ${renderBreakdownTable(t("dashboardSections.topAgents"), observability.top_agents)}
      ${renderBreakdownTable(t("dashboardSections.topExperiments"), observability.top_experiments)}
    </section>
  `;
}

function renderBreakdownTable(title, items) {
  if (!items?.length) {
    return `<article class="table-card"><h3>${escapeHtml(title)}</h3><div class="empty-state">${escapeHtml(t("noData"))}</div></article>`;
  }
  return `
    <article class="table-card">
      <h3>${escapeHtml(title)}</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Key</th>
              <th>Tasks</th>
              <th>Memory usage</th>
              <th>Avg quality</th>
            </tr>
          </thead>
          <tbody>
            ${items
              .map(
                (item) => `
              <tr>
                <td class="mono">${escapeHtml(item.key)}</td>
                <td>${escapeHtml(formatNumber(item.total_tasks))}</td>
                <td>${escapeHtml(formatPercent(item.memory_usage_rate))}</td>
                <td>${escapeHtml(formatNumber(item.avg_quality_score))}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </article>
  `;
}

function renderProjectsView() {
  const selectedProject = state.projects.find((project) => project.id === state.selectedProjectId) || state.projects[0] || null;
  const projectMetrics = state.projectFocus?.metrics;
  const projectRecentMemory = state.projectFocus?.recentMemory || [];
  const projectConflicts = state.projectFocus?.conflicts || [];
  return `
    <section class="split">
      <article class="panel">
        <h3>${escapeHtml(t("createProject"))}</h3>
        <form id="project-create-form">
          <div class="field-grid">
            <div class="field">
              <label>${escapeHtml(t("projectName"))}</label>
              <input name="name" required />
            </div>
            <div class="field">
              <label>${escapeHtml(t("projectDescription"))}</label>
              <input name="description" />
            </div>
            <div class="field">
              <label>${escapeHtml(t("projectTenantId"))}</label>
              <input name="tenantId" value="${escapeHtml(state.auth?.tenant_ids?.length === 1 ? state.auth.tenant_ids[0] : "")}" />
            </div>
            <div class="field" style="grid-column: span 2;">
              <label>${escapeHtml(t("projectMetadata"))}</label>
              <textarea name="metadata">{}</textarea>
            </div>
          </div>
          <div class="form-actions">
            <button class="primary-button" type="submit">${escapeHtml(t("create"))}</button>
          </div>
        </form>
      </article>
      <article class="panel">
        <h3>${escapeHtml(t("updateProject"))}</h3>
        ${
          selectedProject
            ? `
          <form id="project-update-form">
            <div class="field-grid">
              <div class="field">
                <label>${escapeHtml(t("selectProject"))}</label>
                ${projectSelectMarkup("selectedProjectId", selectedProject.id, false)}
              </div>
              <div class="field">
                <label>${escapeHtml(t("projectName"))}</label>
                <input name="name" value="${escapeHtml(selectedProject.name)}" required />
              </div>
              <div class="field">
                <label>${escapeHtml(t("projectDescription"))}</label>
                <input name="description" value="${escapeHtml(selectedProject.description || "")}" />
              </div>
              <div class="field">
                <label>${escapeHtml(t("projectTenantId"))}</label>
                <input name="tenantId" value="${escapeHtml(selectedProject.tenant_id || "")}" />
              </div>
              <div class="field" style="grid-column: span 2;">
                <label>${escapeHtml(t("projectMetadata"))}</label>
                <textarea name="metadata">${escapeHtml(JSON.stringify(selectedProject.metadata || {}, null, 2))}</textarea>
              </div>
            </div>
            <div class="form-actions">
              <button class="primary-button" type="submit">${escapeHtml(t("update"))}</button>
            </div>
          </form>`
            : `<div class="empty-state">${escapeHtml(t("noData"))}</div>`
        }
      </article>
    </section>

    ${
      selectedProject && projectMetrics
        ? `
      <section class="stack" style="margin-top:18px;">
        <article class="panel">
          <h3>${escapeHtml(selectedProject.name)}</h3>
          <p class="muted">${escapeHtml(selectedProject.description || "")}</p>
          <div class="form-actions" style="margin-top: 0; margin-bottom: 18px;">
            ${selectedProject.tenant_id ? `<div class="chip">${escapeHtml(t("projectTenantId"))}: ${escapeHtml(selectedProject.tenant_id)}</div>` : ""}
            ${selectedProject.metadata?.source_path ? `<div class="chip">source: ${escapeHtml(selectedProject.metadata.source_path)}</div>` : ""}
          </div>
          <div class="summary-grid">
            <div class="summary-tile">
              <div class="summary-kicker">${escapeHtml(t("dashboardCards.totalEntries"))}</div>
              <div class="summary-value">${escapeHtml(formatNumber(projectMetrics.memory.total_entries))}</div>
              <div class="summary-copy">${escapeHtml(t("dashboardCards.activeEntries"))}: ${escapeHtml(formatNumber(projectMetrics.memory.active_entries))}</div>
            </div>
            <div class="summary-tile">
              <div class="summary-kicker">${escapeHtml(t("dashboardCards.links"))}</div>
              <div class="summary-value">${escapeHtml(formatNumber(projectMetrics.graph.total_links))}</div>
              <div class="summary-copy">${escapeHtml(t("dashboardCards.reuseRate"))}: ${escapeHtml(formatPercent(projectMetrics.memory.reuse_rate))}</div>
            </div>
            <div class="summary-tile">
              <div class="summary-kicker">${escapeHtml(t("reviewQueue"))}</div>
              <div class="summary-value">${escapeHtml(formatNumber(projectConflicts.length))}</div>
              <div class="summary-copy">${escapeHtml(t("dashboardCards.orphanRate"))}: ${escapeHtml(formatPercent(projectMetrics.memory.orphan_rate))}</div>
            </div>
          </div>
        </article>

        <section class="split">
          <article class="table-card">
            <h3>${escapeHtml(t("memoryTitle"))}</h3>
            ${renderTableSearchField("projectMemorySearch", state.forms.projectMemorySearch)}
            ${renderTable(projectRecentMemory, ["type", "title", "importance", "usage_count", "updated_at"], {
              tableKey: "projectRecentMemory",
              selectable: "memory",
              selectedId: state.selectedMemoryId,
              filterQuery: state.forms.projectMemorySearch,
              filterKeys: ["title", "content", "type"]
            })}
          </article>
          <article class="table-card">
            <h3>${escapeHtml(t("reviewQueue"))}</h3>
            ${renderTable(projectConflicts, ["title", "type", "requires_review", "created_at"], {
              tableKey: "projectConflicts"
            })}
          </article>
        </section>
      </section>`
        : ""
    }

    <section class="table-card" style="margin-top:18px;">
      <h3>${escapeHtml(t("projectsTitle"))}</h3>
      ${renderTableSearchField("projectSearch", state.forms.projectSearch)}
      ${renderTable(state.projects, ["name", "tenant_id", "description", "updated_at"], {
        tableKey: "projects",
        selectable: "project",
        selectedId: selectedProject?.id,
        filterQuery: state.forms.projectSearch,
        filterKeys: ["name", "description", "tenant_id"]
      })}
    </section>
  `;
}

function renderMemoryView() {
  const selectedEntry = state.memoryItems.find((item) => item.id === state.selectedMemoryId) || state.memoryItems[0] || null;
  return `
    <section class="panel toolbar-card">
      <h3>${escapeHtml(t("filters"))}</h3>
      <div class="field-grid">
        <div class="field">
          <label>${escapeHtml(t("projectFilter"))}</label>
          ${projectSelectMarkup("selectedProjectId", state.selectedProjectId, true)}
        </div>
        <div class="field">
          <label>${escapeHtml(t("memoryType"))}</label>
          <select name="memoryType">
            <option value="">${escapeHtml(t("all"))}</option>
            ${MEMORY_TYPES.map((type) => `<option value="${type}" ${state.forms.memoryType === type ? "selected" : ""}>${type}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>${escapeHtml(t("archiveFilter"))}</label>
          <select name="memoryArchived">
            <option value="false" ${state.forms.memoryArchived === "false" ? "selected" : ""}>${escapeHtml(t("activeOnly"))}</option>
            <option value="true" ${state.forms.memoryArchived === "true" ? "selected" : ""}>${escapeHtml(t("archivedOnly"))}</option>
            <option value="all" ${state.forms.memoryArchived === "all" ? "selected" : ""}>${escapeHtml(t("all"))}</option>
          </select>
        </div>
        <div class="field">
          <label>${escapeHtml(t("memorySearch"))}</label>
          <input name="memoryQuery" value="${escapeHtml(state.forms.memoryQuery)}" />
        </div>
        <div class="field">
          <label>${escapeHtml(t("searchMode"))}</label>
          <select name="memorySearchMode">
            <option value="hybrid" ${state.forms.memorySearchMode === "hybrid" ? "selected" : ""}>${escapeHtml(t("searchModeHybrid"))}</option>
            <option value="lexical" ${state.forms.memorySearchMode === "lexical" ? "selected" : ""}>${escapeHtml(t("searchModeLexical"))}</option>
            <option value="semantic" ${state.forms.memorySearchMode === "semantic" ? "selected" : ""}>${escapeHtml(t("searchModeSemantic"))}</option>
          </select>
        </div>
      </div>
      <div class="form-actions">
        <button class="primary-button" data-action="refresh-view">${escapeHtml(t("refresh"))}</button>
      </div>
    </section>

    <section class="split">
      <article class="panel">
        <h3>${escapeHtml(t("pickEntry"))}</h3>
        ${
          selectedEntry
            ? `
          <div class="metrics-list">
            <div class="metric-row"><span class="metric-name">${escapeHtml(columnLabel("type"))}</span><span class="metric-value">${escapeHtml(selectedEntry.type)}</span></div>
            <div class="metric-row"><span class="metric-name">${escapeHtml(columnLabel("title"))}</span><span class="metric-value">${escapeHtml(selectedEntry.title || "n/a")}</span></div>
            <div class="metric-row"><span class="metric-name">${escapeHtml(columnLabel("importance"))}</span><span class="metric-value">${escapeHtml(formatNumber(selectedEntry.importance))}</span></div>
            <div class="metric-row"><span class="metric-name">${escapeHtml(columnLabel("usage_count"))}</span><span class="metric-value">${escapeHtml(formatNumber(selectedEntry.usage_count))}</span></div>
            <div class="metric-row"><span class="metric-name">${escapeHtml(columnLabel("archived"))}</span><span class="metric-value">${renderStatusChip(Boolean(selectedEntry.archived))}</span></div>
            <div class="metric-row"><span class="metric-name">${escapeHtml(columnLabel("updated_at"))}</span><span class="metric-value">${escapeHtml(formatDate(selectedEntry.updated_at))}</span></div>
          </div>
          <div class="panel" style="margin-top:18px; padding:16px;">
            <div class="summary-kicker">${escapeHtml(columnLabel("content"))}</div>
            <div>${escapeHtml(selectedEntry.content || "")}</div>
          </div>
          ${
            selectedEntry.metadata && Object.keys(selectedEntry.metadata).length
              ? `
            <div class="panel" style="margin-top:18px; padding:16px;">
              <div class="summary-kicker">Metadata</div>
              <div class="mono">${escapeHtml(JSON.stringify(selectedEntry.metadata, null, 2))}</div>
            </div>`
              : ""
          }`
            : `<div class="empty-state">${escapeHtml(t("noSelection"))}</div>`
        }
      </article>
      <article class="panel">
        <h3>${escapeHtml(t("memoryCreate"))}</h3>
        <form id="memory-create-form">
          <div class="field-grid">
            <div class="field">
              <label>${escapeHtml(t("projectFilter"))}</label>
              ${projectSelectMarkup("projectId", state.selectedProjectId, false)}
            </div>
            <div class="field">
              <label>${escapeHtml(t("memoryType"))}</label>
              <select name="type">${MEMORY_TYPES.map((type) => `<option value="${type}">${type}</option>`).join("")}</select>
            </div>
            <div class="field">
              <label>${escapeHtml(t("title"))}</label>
              <input name="title" />
            </div>
            <div class="field">
              <label>${escapeHtml(t("sourceAgent"))}</label>
              <input name="sourceAgent" />
            </div>
            <div class="field">
              <label>${escapeHtml(t("importance"))}</label>
              <select name="importance">${[1, 2, 3, 4, 5].map((value) => `<option value="${value}" ${value === 3 ? "selected" : ""}>${value}</option>`).join("")}</select>
            </div>
            <div class="field" style="grid-column: span 3;">
              <label>${escapeHtml(t("content"))}</label>
              <textarea name="content" required></textarea>
            </div>
          </div>
          <div class="form-actions">
            <button class="primary-button" type="submit">${escapeHtml(t("create"))}</button>
          </div>
        </form>
      </article>
      <article class="panel">
        <h3>${escapeHtml(t("memoryUpdate"))}</h3>
        ${
          selectedEntry
            ? `
          <form id="memory-update-form" data-entry-id="${escapeHtml(selectedEntry.id)}">
            <div class="field-grid">
              <div class="field">
                <label>${escapeHtml(t("pickEntry"))}</label>
                <select name="selectedMemoryId">
                  ${state.memoryItems
                    .map(
                      (item) => `
                    <option value="${escapeHtml(item.id)}" ${item.id === selectedEntry.id ? "selected" : ""}>
                      ${escapeHtml(item.title || item.id)}
                    </option>`
                    )
                    .join("")}
                </select>
              </div>
              <div class="field">
                <label>${escapeHtml(t("title"))}</label>
                <input name="title" value="${escapeHtml(selectedEntry.title || "")}" />
              </div>
              <div class="field">
                <label>${escapeHtml(t("sourceAgent"))}</label>
                <input name="sourceAgent" value="${escapeHtml(selectedEntry.source_agent || "")}" />
              </div>
              <div class="field">
                <label>${escapeHtml(t("importance"))}</label>
                <select name="importance">${[1, 2, 3, 4, 5]
                  .map((value) => `<option value="${value}" ${value === selectedEntry.importance ? "selected" : ""}>${value}</option>`)
                  .join("")}</select>
              </div>
              <div class="field" style="grid-column: span 4;">
                <label>${escapeHtml(t("content"))}</label>
                <textarea name="content">${escapeHtml(selectedEntry.content || "")}</textarea>
              </div>
            </div>
            <div class="form-actions">
              <button class="primary-button" type="submit">${escapeHtml(t("update"))}</button>
              <button class="danger-button" type="button" data-action="archive-memory" data-entry-id="${escapeHtml(selectedEntry.id)}">${escapeHtml(t("archive"))}</button>
            </div>
          </form>`
            : `<div class="empty-state">${escapeHtml(t("noSelection"))}</div>`
        }
      </article>
    </section>

    <section class="table-card" style="margin-top:18px;">
      <h3>${escapeHtml(t("memoryTitle"))}</h3>
      <div class="form-actions" style="margin-top: 0; margin-bottom: 12px;">
        <div class="chip">${escapeHtml(formatNumber(state.selectedMemoryIds.length))} ${escapeHtml(t("selectedCount"))}</div>
        <button class="ghost-button" type="button" data-action="clear-memory-selection">${escapeHtml(t("clearSelection"))}</button>
        <button class="danger-button" type="button" data-action="archive-selected-memory" ${state.selectedMemoryIds.length ? "" : "disabled"}>${escapeHtml(t("archiveSelected"))}</button>
      </div>
      ${renderTable(state.memoryItems, ["type", "title", "importance", "usage_count", "archived", "updated_at"], {
        tableKey: "memory",
        selectable: "memory",
        selectedId: selectedEntry?.id,
        multiselect: "memory",
        filterQuery: state.forms.memoryQuery,
        filterKeys: ["title", "content", "type", "source_agent"]
      })}
    </section>

    ${
      state.memorySearchResults.length
        ? `
      <section class="table-card" style="margin-top:18px;">
        <h3>${escapeHtml(t("memorySearch"))}</h3>
        <div class="table-note" style="margin-bottom: 12px;">${escapeHtml(t("searchMode"))}: ${escapeHtml(searchModeLabel(state.forms.memorySearchMode))}</div>
        ${renderTable(state.memorySearchResults, ["type", "title", "match_mode", "score", "semantic_score", "lexical_score", "importance", "usage_count"], {
          tableKey: "memorySearch",
          selectable: "memory",
          selectedId: selectedEntry?.id,
          multiselect: "memory"
        })}
      </section>`
        : ""
    }
  `;
}

function renderReviewView() {
  return `
    <section class="panel toolbar-card">
      <h3>${escapeHtml(t("filters"))}</h3>
      <div class="field-grid">
        <div class="field">
          <label>${escapeHtml(t("projectFilter"))}</label>
          ${projectSelectMarkup("selectedProjectId", state.selectedProjectId, true)}
        </div>
        <div class="field">
          <label>Agent ID</label>
          <input name="conflictAgentId" value="${escapeHtml(state.forms.conflictAgentId)}" />
        </div>
        <div class="field">
          <label>Experiment ID</label>
          <input name="conflictExperimentId" value="${escapeHtml(state.forms.conflictExperimentId)}" />
        </div>
        <div class="field">
          <label>${escapeHtml(t("conflictLimit"))}</label>
          <input name="conflictLimit" type="number" min="1" max="100" value="${escapeHtml(state.forms.conflictLimit)}" />
        </div>
      </div>
      <div class="form-actions">
        <button class="primary-button" data-action="refresh-view">${escapeHtml(t("refresh"))}</button>
      </div>
    </section>

    <section class="cards-grid">
      <article class="panel stat-card">
        <div class="stat-label">${escapeHtml(t("importConflicts"))}</div>
        <div class="stat-value">${escapeHtml(formatNumber(state.conflicts.length))}</div>
        <div class="stat-meta">${escapeHtml(t("tableSummary"))}</div>
      </article>
      <article class="panel stat-card">
        <div class="stat-label">${escapeHtml(t("recentTaskLogs"))}</div>
        <div class="stat-value">${escapeHtml(formatNumber(state.taskLogs.length))}</div>
        <div class="stat-meta">${escapeHtml(t("taskSummary"))}</div>
      </article>
      <article class="panel stat-card">
        <div class="stat-label">${escapeHtml(t("dashboardCards.memoryUsage"))}</div>
        <div class="stat-value">${escapeHtml(formatPercent(state.taskSummary?.memory_usage_rate))}</div>
        <div class="stat-meta">avg duplicates ${escapeHtml(formatNumber(state.taskSummary?.avg_duplicate_count))}</div>
      </article>
    </section>

    <section class="split" style="margin-top:18px;">
      <article class="table-card">
        <h3>${escapeHtml(t("importConflicts"))}</h3>
        ${renderTableSearchField("reviewConflictSearch", state.forms.reviewConflictSearch)}
        ${renderTable(state.conflicts, ["title", "type", "requires_review", "created_at"], {
          tableKey: "reviewConflicts",
          filterQuery: state.forms.reviewConflictSearch,
          filterKeys: ["title", "type"]
        })}
      </article>
      <article class="table-card">
        <h3>${escapeHtml(t("recentTaskLogs"))}</h3>
        ${renderTableSearchField("reviewTaskSearch", state.forms.reviewTaskSearch)}
        ${renderTable(state.taskLogs, ["agent_id", "experiment_id", "task_description", "used_memory", "result_quality_score", "logged_at"], {
          tableKey: "reviewTasks",
          filterQuery: state.forms.reviewTaskSearch,
          filterKeys: ["agent_id", "experiment_id", "task_description"]
        })}
      </article>
    </section>

    <section class="table-card" style="margin-top:18px;">
      <h3>${escapeHtml(t("importSummary"))}</h3>
      ${renderTable(state.importSummaries, ["project_name", "source_path", "imported_entries_count", "import_events_count", "conflicts_detected_count", "last_imported_at"], {
        tableKey: "reviewImportSummaries"
      })}
    </section>
  `;
}

function renderSettingsView() {
  return `
    <section class="split">
      <article class="panel">
        <h3>${escapeHtml(t("settings"))}</h3>
        <form id="settings-form">
          <div class="field-grid compact">
            <div class="field">
              <label>${escapeHtml(t("apiBaseUrl"))}</label>
              <input name="apiBaseUrl" value="${escapeHtml(state.apiBaseUrl)}" />
            </div>
            <div class="field">
              <label>${escapeHtml(t("apiKey"))}</label>
              <input name="apiKey" type="password" value="${escapeHtml(state.apiKey)}" placeholder="Bearer key" />
            </div>
            <div class="field">
              <label>${escapeHtml(t("localeEn"))} / ${escapeHtml(t("localeRu"))}</label>
              <select name="locale">
                <option value="ru" ${state.locale === "ru" ? "selected" : ""}>RU</option>
                <option value="en" ${state.locale === "en" ? "selected" : ""}>EN</option>
              </select>
            </div>
            <div class="field">
              <label>${escapeHtml(t("themeDark"))} / ${escapeHtml(t("themeLight"))}</label>
              <select name="theme">
                <option value="dark" ${state.theme === "dark" ? "selected" : ""}>Dark</option>
                <option value="light" ${state.theme === "light" ? "selected" : ""}>Light</option>
              </select>
            </div>
          </div>
          <div class="form-actions">
            <button class="primary-button" type="submit">${escapeHtml(t("saveSettings"))}</button>
          </div>
        </form>
      </article>
      <article class="panel">
        <h3>Console status</h3>
        <div class="metrics-list">
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("apiStatus"))}</span><span class="metric-value">${escapeHtml(state.apiHealthy ? t("apiHealthy") : t("apiUnavailable"))}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("authState"))}</span><span class="metric-value">${escapeHtml(authStateLabel())}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("scopes"))}</span><span class="metric-value">${escapeHtml(authScopesLabel())}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("tenants"))}</span><span class="metric-value">${escapeHtml(authTenantsLabel())}</span></div>
          <div class="metric-row"><span class="metric-name">${escapeHtml(t("currentView"))}</span><span class="metric-value">${escapeHtml(t(state.currentView))}</span></div>
          <div class="metric-row"><span class="metric-name">Theme</span><span class="metric-value">${escapeHtml(state.theme)}</span></div>
          <div class="metric-row"><span class="metric-name">Locale</span><span class="metric-value">${escapeHtml(state.locale.toUpperCase())}</span></div>
        </div>
        <p class="muted">${escapeHtml(t("settingsHint"))}</p>
        <p class="muted">${escapeHtml(t("mobileHint"))}</p>
      </article>
    </section>
  `;
}

function renderTable(items, columns, options = {}) {
  if (!items?.length) {
    return `<div class="empty-state">${escapeHtml(t("noData"))}</div>`;
  }
  const normalizedColumns = normalizeColumns(columns);
  const processed = getProcessedTableItems(items, {
    tableKey: options.tableKey,
    filterQuery: options.filterQuery,
    filterKeys: options.filterKeys,
    columns: normalizedColumns
  });
  return `
    <div class="table-toolbar">
      <div class="table-note">${escapeHtml(formatNumber(processed.totalItems))} ${escapeHtml(t("rows"))}</div>
      <div class="table-note">
        ${
          options.tableKey
            ? `
          <button class="row-button" type="button" data-action="paginate-table" data-table-key="${escapeHtml(options.tableKey)}" data-direction="prev" ${processed.page <= 1 ? "disabled" : ""}>←</button>
          <span class="mono">${processed.page}/${processed.totalPages}</span>
          <button class="row-button" type="button" data-action="paginate-table" data-table-key="${escapeHtml(options.tableKey)}" data-direction="next" ${processed.page >= processed.totalPages ? "disabled" : ""}>→</button>`
            : ""
        }
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            ${options.multiselect ? `<th></th>` : ""}
            ${normalizedColumns
              .map((column) => {
                if (!options.tableKey) {
                  return `<th>${escapeHtml(column.label || column.key)}</th>`;
                }
                const tableState = getTableState(options.tableKey);
                const isActive = tableState.sortKey === column.key;
                const marker = isActive ? (tableState.sortDir === "asc" ? " ↑" : " ↓") : "";
                return `<th><button class="row-button" type="button" data-action="sort-table" data-table-key="${escapeHtml(options.tableKey)}" data-sort-key="${escapeHtml(column.key)}">${escapeHtml(column.label || column.key)}${marker}</button></th>`;
              })
              .join("")}
            ${options.selectable ? `<th>${escapeHtml(t("select"))}</th>` : ""}
          </tr>
        </thead>
        <tbody>
          ${processed.pageItems
            .map(
              (item) => `
            <tr class="${options.selectedId && (item.id === options.selectedId || item.entry_id === options.selectedId) ? "is-selected" : ""}">
              ${
                options.multiselect
                  ? `<td>
                  <input
                    type="checkbox"
                    data-action="toggle-row-selection"
                    data-selectable="${escapeHtml(options.multiselect)}"
                    data-id="${escapeHtml(item.id || item.entry_id || "")}"
                    ${state.selectedMemoryIds.includes(item.id || item.entry_id || "") ? "checked" : ""}
                  />
                </td>`
                  : ""
              }
              ${normalizedColumns
                .map((column) => {
                  const value = item[column.key];
                  return `<td>${formatCellValue(column.key, value)}</td>`;
                })
                .join("")}
              ${
                options.selectable
                  ? `<td>
                  <button
                    class="row-button"
                    type="button"
                    data-action="select-row"
                    data-selectable="${escapeHtml(options.selectable)}"
                    data-id="${escapeHtml(item.id || item.entry_id || "")}"
                  >
                    ${escapeHtml(options.selectedId && (item.id === options.selectedId || item.entry_id === options.selectedId) ? t("selected") : t("select"))}
                  </button>
                </td>`
                  : ""
              }
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderView() {
  if (state.currentView === "projects") {
    return renderProjectsView();
  }
  if (state.currentView === "memory") {
    return renderMemoryView();
  }
  if (state.currentView === "review") {
    return renderReviewView();
  }
  if (state.currentView === "settings") {
    return renderSettingsView();
  }
  return renderDashboardView();
}

function render() {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.lang = state.locale;
  const pageMeta = currentPageMeta();
  document.title = `${pageMeta.title} · MemLayer`;

  root.innerHTML = `
    <div class="drawer-backdrop ${state.drawerOpen ? "open" : ""}" data-action="close-drawer"></div>
    <aside class="mobile-drawer ${state.drawerOpen ? "open" : ""}">
      <div class="mobile-drawer-head">
        <div class="brand-row" style="margin-bottom:0;">
          <div class="brand-mark">✓</div>
          <div class="brand-copy">
            <div class="brand-title">${escapeHtml(t("brandTitle"))}</div>
            <div class="brand-subtitle">${escapeHtml(t("brandSubtitle"))}</div>
          </div>
        </div>
        <button class="icon-button close-button" data-action="close-drawer">${escapeHtml(t("close"))}</button>
      </div>
      ${navMarkup({ mobile: true })}
    </aside>

    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand-row">
          <div class="brand-mark">✓</div>
          <div class="brand-copy">
            <div class="brand-title">${escapeHtml(t("brandTitle"))}</div>
            <div class="brand-subtitle">${escapeHtml(t("brandSubtitle"))}</div>
          </div>
        </div>
        ${navMarkup()}
        <div class="sidebar-footer">
          <div class="status-box">
            <div class="status-label">${escapeHtml(t("apiStatus"))}</div>
            <div class="status-value">${escapeHtml(state.apiHealthy ? t("apiHealthy") : t("apiUnavailable"))}</div>
          </div>
          <div class="status-box">
            <div class="status-label">${escapeHtml(t("authState"))}</div>
            <div class="status-value muted">${escapeHtml(authStateLabel())}</div>
          </div>
          <div class="status-box">
            <div class="status-label">${escapeHtml(t("desktopNote"))}</div>
            <div class="status-value muted">${escapeHtml(state.apiBaseUrl)}</div>
          </div>
        </div>
      </aside>

      <div class="layout-main">
        <header class="topbar">
          <div class="topbar-left">
            <button class="icon-button hidden-desktop" data-action="open-drawer">${escapeHtml(t("menu"))}</button>
            <div class="topbar-brand">
              <div class="brand-mark">✓</div>
              <span>${escapeHtml(t("brandTitle"))}</span>
            </div>
          </div>
          <div class="topbar-right">
            <div class="toggle-group">
              <button data-action="set-locale" data-locale="en" class="${state.locale === "en" ? "active" : ""}">EN</button>
              <button data-action="set-locale" data-locale="ru" class="${state.locale === "ru" ? "active" : ""}">RU</button>
            </div>
            <div class="toggle-group">
              <button data-action="set-theme" data-theme="light" class="${state.theme === "light" ? "active" : ""}">${escapeHtml(t("themeLight"))}</button>
              <button data-action="set-theme" data-theme="dark" class="${state.theme === "dark" ? "active" : ""}">${escapeHtml(t("themeDark"))}</button>
            </div>
            <button class="ghost-button" data-action="refresh-view">${escapeHtml(t("refresh"))}</button>
          </div>
        </header>

        <main class="content">
          ${messagesMarkup()}
          <section class="page-head">
            <div>
              <h1 class="page-title">${escapeHtml(pageMeta.title)}</h1>
              <p class="page-description">${escapeHtml(pageMeta.description)}</p>
            </div>
            <div class="page-head-chips">
              <div class="chip">${escapeHtml(t("currentView"))}: ${escapeHtml(t(state.currentView))}</div>
              ${renderAuthChips()}
            </div>
          </section>
          <section class="banner panel">
            <div>●</div>
            <div>${escapeHtml(t("banner"))}</div>
          </section>
          ${state.loading ? `<div class="message info">Loading...</div>` : ""}
          ${renderView()}
        </main>
      </div>
    </div>
  `;
}

function parseJsonInput(raw) {
  const value = (raw || "").trim();
  if (!value) {
    return {};
  }
  return JSON.parse(value);
}

async function handleProjectCreate(form) {
  const formData = new FormData(form);
  const payload = {
    name: String(formData.get("name") || "").trim(),
    description: String(formData.get("description") || "").trim() || null,
    tenant_id: String(formData.get("tenantId") || "").trim() || null,
    metadata: parseJsonInput(String(formData.get("metadata") || "{}"))
  };
  await apiRequest("/projects", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  pushMessage("success", t("successProjectCreated"));
  form.reset();
  await loadCurrentView();
}

async function handleProjectUpdate(form) {
  const formData = new FormData(form);
  const projectId = String(formData.get("selectedProjectId") || "").trim();
  if (!projectId) {
    throw new Error(t("noSelection"));
  }
  const payload = {
    name: String(formData.get("name") || "").trim(),
    description: String(formData.get("description") || "").trim() || null,
    tenant_id: String(formData.get("tenantId") || "").trim() || null,
    metadata: parseJsonInput(String(formData.get("metadata") || "{}"))
  };
  await apiRequest(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  state.selectedProjectId = projectId;
  pushMessage("success", t("successProjectUpdated"));
  await loadCurrentView();
}

async function handleMemoryCreate(form) {
  const formData = new FormData(form);
  const payload = {
    project_id: String(formData.get("projectId") || "").trim() || null,
    type: String(formData.get("type") || "").trim(),
    title: String(formData.get("title") || "").trim() || null,
    source_agent: String(formData.get("sourceAgent") || "").trim() || null,
    importance: Number(formData.get("importance") || 3),
    content: String(formData.get("content") || "").trim(),
    metadata: {}
  };
  await apiRequest("/memory", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  pushMessage("success", t("successMemoryCreated"));
  form.reset();
  await loadCurrentView();
}

async function handleMemoryUpdate(form) {
  const formData = new FormData(form);
  const entryId = String(form.dataset.entryId || "").trim();
  if (!entryId) {
    throw new Error(t("noSelection"));
  }
  const payload = {
    title: String(formData.get("title") || "").trim() || null,
    source_agent: String(formData.get("sourceAgent") || "").trim() || null,
    importance: Number(formData.get("importance") || 3),
    content: String(formData.get("content") || "").trim()
  };
  await apiRequest(`/memory/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  state.selectedMemoryId = entryId;
  pushMessage("success", t("successMemoryUpdated"));
  await loadCurrentView();
}

async function archiveMemory(entryId) {
  await apiRequest(`/memory/${entryId}/archive`, {
    method: "POST"
  });
  pushMessage("success", t("successMemoryArchived"));
  await loadCurrentView();
}

async function archiveSelectedMemory() {
  const ids = [...state.selectedMemoryIds];
  for (const id of ids) {
    await apiRequest(`/memory/${id}/archive`, {
      method: "POST"
    });
  }
  state.selectedMemoryIds = [];
  pushMessage("success", `${ids.length} ${t("archiveSelected").toLowerCase()}`);
  await loadCurrentView();
}

function syncFormValue(name, value) {
  if (name in state.forms) {
    state.forms[name] = value;
  }
  if (name === "selectedProjectId") {
    state.selectedProjectId = value;
  }
  if (name === "selectedMemoryId") {
    state.selectedMemoryId = value;
  }
}

function attachEvents() {
  root.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) {
      return;
    }
    const action = target.dataset.action;
    try {
      if (action === "navigate") {
        await navigateToView(target.dataset.view);
      }
      if (action === "open-drawer") {
        state.drawerOpen = true;
        render();
      }
      if (action === "close-drawer") {
        state.drawerOpen = false;
        render();
      }
      if (action === "set-theme") {
        state.theme = target.dataset.theme;
        localStorage.setItem(STORAGE_KEYS.theme, state.theme);
        render();
      }
      if (action === "set-locale") {
        state.locale = target.dataset.locale;
        localStorage.setItem(STORAGE_KEYS.locale, state.locale);
        render();
      }
      if (action === "refresh-view") {
        await loadCurrentView();
      }
      if (action === "archive-memory") {
        await archiveMemory(target.dataset.entryId);
      }
      if (action === "archive-selected-memory") {
        await archiveSelectedMemory();
      }
      if (action === "clear-memory-selection") {
        state.selectedMemoryIds = [];
        render();
      }
      if (action === "select-row") {
        const selectable = target.dataset.selectable;
        const id = target.dataset.id || "";
        if (selectable === "project") {
          state.selectedProjectId = id;
          if (state.currentView === "projects") {
            await loadProjectFocusData();
          }
          render();
        }
        if (selectable === "memory") {
          state.selectedMemoryId = id;
          if (state.currentView === "projects") {
            state.currentView = "memory";
            await loadCurrentView();
            return;
          }
          render();
        }
      }
      if (action === "sort-table") {
        const tableState = getTableState(target.dataset.tableKey);
        const sortKey = target.dataset.sortKey;
        if (tableState.sortKey === sortKey) {
          tableState.sortDir = tableState.sortDir === "asc" ? "desc" : "asc";
        } else {
          tableState.sortKey = sortKey;
          tableState.sortDir = "asc";
        }
        tableState.page = 1;
        render();
      }
      if (action === "paginate-table") {
        const tableState = getTableState(target.dataset.tableKey);
        tableState.page += target.dataset.direction === "next" ? 1 : -1;
        render();
      }
    } catch (error) {
      pushMessage("error", error.message);
    }
  });

  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement)) {
      return;
    }
    if (target instanceof HTMLInputElement && target.dataset.action === "toggle-row-selection") {
      const id = target.dataset.id || "";
      if (target.checked) {
        if (!state.selectedMemoryIds.includes(id)) {
          state.selectedMemoryIds = [...state.selectedMemoryIds, id];
        }
      } else {
        state.selectedMemoryIds = state.selectedMemoryIds.filter((item) => item !== id);
      }
      render();
      return;
    }
    syncFormValue(target.name, target.value);
    if (target.name === "selectedProjectId" && state.currentView === "projects") {
      loadProjectFocusData().then(render).catch((error) => pushMessage("error", error.message));
    } else {
      render();
    }
  });

  root.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    try {
      if (form.id === "project-create-form") {
        await handleProjectCreate(form);
      }
      if (form.id === "project-update-form") {
        await handleProjectUpdate(form);
      }
      if (form.id === "memory-create-form") {
        await handleMemoryCreate(form);
      }
      if (form.id === "memory-update-form") {
        await handleMemoryUpdate(form);
      }
      if (form.id === "settings-form") {
        const formData = new FormData(form);
        state.apiBaseUrl = String(formData.get("apiBaseUrl") || defaultApiBaseUrl()).trim() || defaultApiBaseUrl();
        state.apiKey = String(formData.get("apiKey") || "").trim();
        state.locale = String(formData.get("locale") || "ru");
        state.theme = String(formData.get("theme") || "dark");
        localStorage.setItem(STORAGE_KEYS.apiBaseUrl, state.apiBaseUrl);
        localStorage.setItem(STORAGE_KEYS.apiKey, state.apiKey);
        localStorage.setItem(STORAGE_KEYS.locale, state.locale);
        localStorage.setItem(STORAGE_KEYS.theme, state.theme);
        pushMessage("success", t("successSaved"));
        await loadCurrentView();
      }
    } catch (error) {
      pushMessage("error", error.message);
    }
  });
}

async function boot() {
  window.addEventListener("popstate", async () => {
    state.currentView = resolveViewFromLocation();
    state.drawerOpen = false;
    await loadCurrentView();
  });
  attachEvents();
  render();
  await loadCurrentView();
}

boot();
