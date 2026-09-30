/**
 * Antigravity Chat Migrator — Frontend Controller
 * Zero external CDN — pure Vanilla JS & pywebview bridge
 */

(function () {
  'use strict';

  // --- 1. Internationalization (i18n) Dictionary ---
  // Notice: Strict adherence to Russian sentence case (no Title Case)
  const TRANSLATIONS = {
    ru: {
      appTitle: 'Antigravity Chat Migrator',
      bannerTagline: '⚡ Синхронизация истории диалогов и исправление привязок воркспейсов',
      bannerSafety: '🛡️ Инвариант холодного диска гарантирован',
      processIdle: 'IDE остановлена (Безопасно)',
      processRunning: 'Antigravity активна (PID: {pids})',
      metricTotal: 'Всего диалогов',
      metricTotalDesc: 'Баз данных .db найдено',
      metricBound: 'В проектах',
      metricBoundDesc: 'Корректно привязаны к коду',
      metricOutside: 'Вне проекта',
      metricOutsideDesc: 'Помечены outside-of-project',
      metricMissing: 'Без аннотаций',
      metricMissingDesc: 'Нет заголовка .pbtxt',
      metricUnregistered: 'Вне реестра',
      metricUnregisteredDesc: 'Воркспейсы не в config.json',
      btnScan: 'Сканировать',
      btnDryRun: 'Симуляция (Dry-Run)',
      btnFix: 'Исправить чаты (Cold Disk)',
      btnBackups: 'Откат из бэкапа',
      searchPlaceholder: 'Поиск по названию, пути или ID...',
      filterAll: 'Все',
      filterOutside: 'Outside of Project',
      filterMissing: 'Без названий',
      filterUnregistered: 'Вне реестра',
      colStatus: 'Статус',
      colTitle: 'Название диалога',
      colWorkspace: 'Рабочая папка',
      colProject: 'Проект',
      colId: 'ID диалога',
      emptyTitle: 'Диалоги не найдены',
      emptySubtitle: 'Нажмите «Сканировать» для сбора истории диалогов Antigravity',
      loadingText: 'Выполняется операция...',
      readyStatus: 'Готов к работе',
      statusOk: 'В порядке',
      statusOutside: 'Вне проекта',
      statusMissing: 'Без аннотации',
      statusUnregistered: 'Вне реестра',
      modalTitle: 'Резервные снимки',
      modalClose: 'Закрыть',
      warnModalTitle: 'Antigravity IDE сейчас запущена',
      warnModalBody: 'Для безопасного восстановления снимка закройте приложение Antigravity.',
      noBackupsFound: 'Резервные копии не обнаружены в каталоге бэкапов',
      btnRestore: 'Восстановить',
      restoringSnapshot: 'Восстановление снимка...',
      restoreSuccess: 'Снимок успешно восстановлен',
      restoreFailed: 'Не удалось восстановить снимок',
      restoreColdViolation: 'Откат заблокирован: Antigravity IDE активна',
      scanStarted: 'Сканирование диалогов...',
      scanComplete: 'Сканирование завершено: найдено {count} диалогов',
      dryRunStarted: 'Запуск симуляции...',
      dryRunComplete: 'Симуляция завершена: обновлений — {updated}, аннотаций — {annotations}',
      fixStarted: 'Синхронизация на холодном диске...',
      fixComplete: 'Синхронизация завершена: обновлено {updated}, создано {annotations} аннотаций',
      fixWarnActive: 'Внимание: Antigravity IDE активна. Запись на горячем диске может повредить базу. Продолжить?',
      copiedId: 'ID скопирован в буфер обмена',
      dialogsCount: '{count} диалогов',
      filesCount: '{count} файлов',
      untitled: 'Без названия',
      navSectionChats: 'Диалоги',
      navAllChats: 'Все диалоги',
      navOutsideChats: 'Вне проектов',
      navMissingChats: 'Без названий',
      navUnregisteredChats: 'Вне реестра',
      navBoundChats: 'Привязаны к проектам',
      navSectionTools: 'Инструменты',
      navSync: 'Синхронизация',
      navBackups: 'Резервные копии',
      navSettings: 'Настройки',
      btnExport: 'Экспорт',
      syncTitle: 'Синхронизация и миграция',
      syncDesc: 'Исправление привязок воркспейсов, восстановление заголовков и синхронизация реестра проектов',
      syncSafetyTitle: 'Инвариант холодного диска',
      syncSafetyText: 'Перед записью обязательно останавливать процессы IDE для предотвращения повреждения SQLite WAL файлов',
      syncSimTitle: 'Симуляция (Dry-Run)',
      syncSimDesc: 'Безопасный анализ без изменений на диске. Проверяет привязки, находит расхождения и генерирует отчет',
      syncFixTitle: 'Боевое исправление (Fix)',
      syncFixDesc: 'Автоматическое создание APFS CoW бэкапа, атомарное обновление SQLite и генерация .pbtxt аннотаций',
      syncLogTitle: 'Лог выполнения',
      btnClearLog: 'Очистить',
      backupsTitle: 'Резервные копии APFS CoW',
      backupsDesc: 'Мгновенные снимки файловой системы APFS с возможностью отката в один клик',
      btnRefreshBackups: 'Обновить список',
      settingsTitle: 'Настройки и система',
      settingsDesc: 'Конфигурация расположения баз данных, хранилища бэкапов и системные параметры',
      lblDataDir: 'Каталог данных Antigravity',
      lblBackupsDir: 'Каталог резервных копий',
      lblPlatform: 'Платформа и система',
      lblAuthor: 'Автор и разработка',
      authorText: 'Даниил К. (Fuheshka)',
      exportSuccess: 'Список диалогов экспортирован',
    },
    en: {
      appTitle: 'Antigravity Chat Migrator',
      bannerTagline: '⚡ Chat trajectory synchronization and workspace binding repair',
      bannerSafety: '🛡️ Cold disk invariant guaranteed',
      processIdle: 'IDE Stopped (Safe)',
      processRunning: 'Antigravity Running (PID: {pids})',
      metricTotal: 'Total Chats',
      metricTotalDesc: '.db conversation databases found',
      metricBound: 'Bound to Projects',
      metricBoundDesc: 'Properly bound to project code',
      metricOutside: 'Outside of Project',
      metricOutsideDesc: 'Marked outside-of-project',
      metricMissing: 'Missing Annotations',
      metricMissingDesc: 'No .pbtxt title metadata',
      metricUnregistered: 'Unregistered Workspaces',
      metricUnregisteredDesc: 'Workspaces not in config.json',
      btnScan: 'Scan',
      btnDryRun: 'Simulation (Dry-Run)',
      btnFix: 'Repair Chats (Cold Disk)',
      btnBackups: 'Backups & Rollback',
      searchPlaceholder: 'Search by title, workspace path, or ID...',
      filterAll: 'All',
      filterOutside: 'Outside of Project',
      filterMissing: 'Missing Titles',
      filterUnregistered: 'Unregistered',
      colStatus: 'Status',
      colTitle: 'Chat Title',
      colWorkspace: 'Workspace Folder',
      colProject: 'Project',
      colId: 'Chat ID',
      emptyTitle: 'No conversations found',
      emptySubtitle: 'Click «Scan» to audit Antigravity conversation history',
      loadingText: 'Executing operation...',
      readyStatus: 'Ready',
      statusOk: 'OK',
      statusOutside: 'Outside Project',
      statusMissing: 'Missing Title',
      statusUnregistered: 'Unregistered',
      modalTitle: 'Safety Snapshots',
      modalClose: 'Close',
      warnModalTitle: 'Antigravity IDE is currently running',
      warnModalBody: 'To safely restore a snapshot, please quit the Antigravity application first.',
      noBackupsFound: 'No safety snapshots found in backup directory',
      btnRestore: 'Restore',
      restoringSnapshot: 'Restoring snapshot...',
      restoreSuccess: 'Snapshot successfully restored',
      restoreFailed: 'Failed to restore snapshot',
      restoreColdViolation: 'Rollback blocked: Antigravity IDE is running',
      scanStarted: 'Scanning conversations...',
      scanComplete: 'Scan finished: found {count} conversations',
      dryRunStarted: 'Running dry-run simulation...',
      dryRunComplete: 'Simulation complete: would update {updated}, create {annotations} annotations',
      fixStarted: 'Executing cold-disk repair...',
      fixComplete: 'Synchronization complete: updated {updated}, generated {annotations} annotations',
      fixWarnActive: 'Warning: Antigravity IDE is active. Hot writing may corrupt databases. Proceed anyway?',
      copiedId: 'ID copied to clipboard',
      dialogsCount: '{count} conversations',
      filesCount: '{count} files',
      untitled: 'Untitled',
      navSectionChats: 'Chats',
      navAllChats: 'All chats',
      navOutsideChats: 'Outside of project',
      navMissingChats: 'Missing titles',
      navUnregisteredChats: 'Unregistered',
      navBoundChats: 'Bound to projects',
      navSectionTools: 'Tools',
      navSync: 'Synchronization',
      navBackups: 'Backups & rollback',
      navSettings: 'Settings',
      btnExport: 'Export',
      syncTitle: 'Synchronization & migration',
      syncDesc: 'Fix workspace bindings, restore chat titles, and synchronize project registry',
      syncSafetyTitle: 'Cold disk invariant',
      syncSafetyText: 'Always stop IDE processes before writing to avoid corrupting SQLite WAL files',
      syncSimTitle: 'Simulation (Dry-Run)',
      syncSimDesc: 'Safe read-only analysis without touching disk. Checks bindings, finds discrepancies, and generates report',
      syncFixTitle: 'Production fix (Cold disk)',
      syncFixDesc: 'Automatic APFS CoW snapshot creation, atomic SQLite updates, and .pbtxt annotation generation',
      syncLogTitle: 'Execution log',
      btnClearLog: 'Clear',
      backupsTitle: 'APFS CoW backups',
      backupsDesc: 'Instant zero-cost APFS filesystem snapshots with one-click instant rollback',
      btnRefreshBackups: 'Refresh list',
      settingsTitle: 'Settings & system',
      settingsDesc: 'Configuration of database locations, backup storage, and system parameters',
      lblDataDir: 'Antigravity data directory',
      lblBackupsDir: 'Backups directory',
      lblPlatform: 'Platform & system',
      lblAuthor: 'Author & credits',
      authorText: 'Daniil K. (Fuheshka)',
      exportSuccess: 'Conversations exported successfully',
    }
  };

  // --- 2. State & State Management ---
  const state = {
    lang: 'ru',
    isRunning: false,
    pids: [],
    conversations: [],
    filteredList: [],
    filter: 'all',
    searchQuery: '',
    backups: [],
    systemInfo: null,
    isBusy: false,
  };

  function t(key, params = {}) {
    const dict = TRANSLATIONS[state.lang] || TRANSLATIONS.ru;
    let str = dict[key] || TRANSLATIONS.en[key] || key;
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    }
    return str;
  }

  function setLanguage(newLang) {
    if (newLang !== 'ru' && newLang !== 'en') return;
    state.lang = newLang;
    try {
      localStorage.setItem('antigravity_migrator_lang', newLang);
    } catch (_) {}

    document.documentElement.lang = newLang;
    document.getElementById('langCurrent').textContent = newLang.toUpperCase();

    // Update all data-i18n elements
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (key && t(key)) {
        el.textContent = t(key);
      }
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      if (key && t(key)) {
        el.placeholder = t(key);
      }
    });

    updateProcessBadgeUI();
    renderTable();
    updateFooterCount();
  }

  // --- 3. Mock API for Browser Preview / Standalone Offline Testing ---
  const mockApi = {
    get_system_info: async () => ({
      os: 'Darwin',
      os_version: '24.0.0',
      platform: 'macOS-15.0',
      app_version: '0.1.0',
      locale: 'ru',
      paths: {
        data_dir: '/Users/demo/.gemini/antigravity',
        backups_dir: '/Users/demo/.gemini/antigravity/backups',
      }
    }),
    get_process_status: async () => ({
      is_running: false,
      pids: [],
      warning: null,
    }),
    run_audit: async () => ({
      total_conversations: 4,
      bound_to_projects: 2,
      outside_of_project: 1,
      missing_annotations: 1,
      unregistered_workspaces: ['/Users/demo/projects/sandbox'],
      conversations: [
        {
          id: '0199a5e1-8842-70b3-90bd-1100aa223344',
          title: 'Implement Dark Glass HUD for macOS',
          workspace_uri: 'file:///Users/demo/projects/hud-widget',
          project_id: 'proj-hud-101',
          project_name: 'hud-widget',
          status: 'ok',
        },
        {
          id: '0199a5e2-9953-71c4-91ce-2211bb334455',
          title: 'Configure MITM DomainFront Tunnel',
          workspace_uri: 'file:///Users/demo/projects/mhr-cfw',
          project_id: 'proj-mhr-202',
          project_name: 'mhr-cfw',
          status: 'ok',
        },
        {
          id: '0199a5e3-aa64-72d5-92df-3322cc445566',
          title: 'Debugging Audio Stream Engine',
          workspace_uri: 'file:///Users/demo/projects/game-audio',
          project_id: 'outside-of-project',
          project_name: 'Outside of Project',
          status: 'outside_of_project',
        },
        {
          id: '0199a5e4-bb75-73e6-93e0-4433dd556677',
          title: 'Untitled Conversation',
          workspace_uri: 'file:///Users/demo/projects/sandbox',
          project_id: 'proj-sandbox',
          project_name: 'sandbox',
          status: 'missing_annotation',
        },
      ]
    }),
    run_fix: async (dry_run, auto_register) => ({
      success: true,
      dry_run: Boolean(dry_run),
      backup_path: '/Users/demo/.gemini/antigravity/backups/snapshot_2026-09-30_12-00-00',
      conversations_scanned: 4,
      conversations_updated: 2,
      annotations_created: 1,
      projects_registered: 1,
      proto_cache_updated: true,
      summaries_db_updated: true,
      errors: [],
    }),
    list_backups: async () => [
      {
        id: '2026-09-30_11-30-00',
        timestamp: 1790757000,
        date_formatted: '2026-09-30 11:30:00',
        files_count: 14,
        size_bytes: 5242880,
        path: '/Users/demo/.gemini/antigravity/backups/2026-09-30_11-30-00',
      },
      {
        id: '2026-09-29_18-45-12',
        timestamp: 1790696712,
        date_formatted: '2026-09-29 18:45:12',
        files_count: 12,
        size_bytes: 4194304,
        path: '/Users/demo/.gemini/antigravity/backups/2026-09-29_18-45-12',
      }
    ],
    restore_backup: async (snapshot_id) => ({
      success: true,
      snapshot_id,
      error: null,
    }),
  };

  function getBridge() {
    if (window.pywebview && window.pywebview.api) {
      return window.pywebview.api;
    }
    return mockApi;
  }

  // --- 4. Process Status Polling & UI ---
  async function checkProcessStatus() {
    try {
      const bridge = getBridge();
      const status = await bridge.get_process_status();
      state.isRunning = Boolean(status.is_running);
      state.pids = Array.isArray(status.pids) ? status.pids : [];
      updateProcessBadgeUI();
    } catch (err) {
      console.warn('Process check failed:', err);
    }
  }

  function updateProcessBadgeUI() {
    const badge = document.getElementById('processBadge');
    const badgeText = document.getElementById('processBadgeText');
    const tooltip = document.getElementById('processTooltip');
    const modalWarn = document.getElementById('modalColdDiskWarn');

    if (!badge || !badgeText) return;

    if (state.isRunning) {
      badge.className = 'badge-status badge-running';
      const count = state.pids.length || 1;
      const pidsStr = state.pids.length ? state.pids.join(', ') : 'active';
      badgeText.textContent = state.lang === 'ru'
        ? `● IDE активна (${count})`
        : `● IDE active (${count})`;
      if (tooltip) {
        tooltip.textContent = `PID: ${pidsStr}`;
      }
      if (modalWarn) modalWarn.classList.remove('hidden');
    } else {
      badge.className = 'badge-status badge-idle';
      badgeText.textContent = state.lang === 'ru'
        ? '● Холодный диск'
        : '● Cold disk';
      if (tooltip) {
        tooltip.textContent = state.lang === 'ru'
          ? 'IDE остановлена. Диск холодный, запись безопасна.'
          : 'IDE stopped. Cold disk, safe to write.';
      }
      if (modalWarn) modalWarn.classList.add('hidden');
    }
  }

  // --- 5. Data Formatting Helpers ---
  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
  }

  function cleanWorkspaceDisplay(uri) {
    if (!uri) return '—';
    try {
      let decoded = decodeURIComponent(uri);
      decoded = decoded.replace(/^file:\/\//, '');
      return decoded;
    } catch (_) {
      return uri;
    }
  }

  // --- 6. Table Rendering & Search/Filter ---
  function applyFilterAndSearch() {
    let list = state.conversations;

    // Filter segmentation
    if (state.filter === 'outside') {
      list = list.filter((c) => c.status === 'outside_of_project');
    } else if (state.filter === 'missing') {
      list = list.filter((c) => c.status === 'missing_annotation');
    } else if (state.filter === 'unregistered') {
      list = list.filter((c) => c.status === 'unregistered_workspace');
    } else if (state.filter === 'bound') {
      list = list.filter((c) => c.status === 'ok');
    }

    // Search query matching
    const q = state.searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter((c) => {
        const titleMatch = (c.title || '').toLowerCase().includes(q);
        const wsMatch = (c.workspace_uri || '').toLowerCase().includes(q);
        const projMatch = (c.project_name || '').toLowerCase().includes(q);
        const idMatch = (c.id || '').toLowerCase().includes(q);
        return titleMatch || wsMatch || projMatch || idMatch;
      });
    }

    state.filteredList = list;
    renderTable();
    updateFooterCount();
  }

  function renderTable() {
    const tbody = document.getElementById('tableBody');
    const emptyState = document.getElementById('emptyState');
    tbody.innerHTML = '';

    if (!state.filteredList.length) {
      emptyState.classList.remove('hidden');
      return;
    }

    emptyState.classList.add('hidden');

    state.filteredList.forEach((item) => {
      const tr = document.createElement('tr');

      // Status pill
      let statusClass = 'status-ok';
      let statusLabel = t('statusOk');
      if (item.status === 'outside_of_project') {
        statusClass = 'status-outside';
        statusLabel = t('statusOutside');
      } else if (item.status === 'missing_annotation') {
        statusClass = 'status-missing';
        statusLabel = t('statusMissing');
      } else if (item.status === 'unregistered_workspace') {
        statusClass = 'status-unregistered';
        statusLabel = t('statusUnregistered');
      }

      const displayPath = cleanWorkspaceDisplay(item.workspace_uri);
      const shortId = (item.id || '').substring(0, 8);

      tr.innerHTML = `
        <td>
          <span class="status-pill ${statusClass}">
            <span class="dot"></span>
            ${escapeHtml(statusLabel)}
          </span>
        </td>
        <td>
          <div class="col-title-wrap">
            <span class="cell-title" title="${escapeHtml(item.title || '')}">${escapeHtml(item.title || t('untitled'))}</span>
          </div>
        </td>
        <td>
          <span class="cell-path" title="${escapeHtml(displayPath)}">${escapeHtml(displayPath)}</span>
        </td>
        <td>
          <span class="cell-project">${escapeHtml(item.project_name || '—')}</span>
        </td>
        <td>
          <span class="cell-id" data-copy-id="${escapeHtml(item.id || '')}" title="Копировать ID">
            ${escapeHtml(shortId)}…
            <svg style="width: 11px; height: 11px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </span>
        </td>
      `;

      tbody.appendChild(tr);
    });

    // Wire copy buttons
    tbody.querySelectorAll('[data-copy-id]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const cid = btn.getAttribute('data-copy-id');
        if (cid) {
          navigator.clipboard.writeText(cid).then(() => {
            showToast(t('copiedId'), 'info');
          }).catch(() => {});
        }
      });
    });
  }

  function updateMetrics(audit) {
    document.getElementById('valTotal').textContent = audit.total_conversations || 0;
    document.getElementById('valBound').textContent = audit.bound_to_projects || 0;
    document.getElementById('valOutside').textContent = audit.outside_of_project || 0;
    document.getElementById('valMissing').textContent = audit.missing_annotations || 0;
    const unreg = Array.isArray(audit.unregistered_workspaces) ? audit.unregistered_workspaces.length : 0;
    document.getElementById('valUnregistered').textContent = unreg;
  }

  function updateFooterCount() {
    const el = document.getElementById('footerCountText');
    if (el) {
      el.textContent = t('dialogsCount', { count: state.filteredList.length });
    }
  }

  function setBusy(busy) {
    state.isBusy = busy;
    const loader = document.getElementById('tableLoader');
    if (busy) {
      loader.classList.remove('hidden');
    } else {
      loader.classList.add('hidden');
    }

    const buttons = ['btnScan', 'btnDryRun', 'btnFix', 'btnBackups'];
    buttons.forEach((id) => {
      const btn = document.getElementById(id);
      if (btn) btn.disabled = busy;
    });
  }

  // --- 7. Toast Notifications ---
  function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'warning') {
      iconSvg = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      iconSvg = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- 8. Split View Navigation & Logs ---
  function appendSyncLog(msg, type = 'info') {
    const logEl = document.getElementById('syncLogOutput');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString();
    const prefix = type === 'error' ? '❌ ' : type === 'success' ? '✅ ' : 'ℹ️ ';
    logEl.textContent += `[${time}] ${prefix}${msg}\n`;
    logEl.scrollTop = logEl.scrollHeight;
  }

  function switchView(viewName) {
    state.currentView = viewName;
    document.querySelectorAll('.view-pane').forEach((pane) => {
      pane.classList.add('hidden');
    });
    const target = document.getElementById('view-' + viewName);
    if (target) {
      target.classList.remove('hidden');
    }

    document.querySelectorAll('.sidebar-nav-item').forEach((item) => {
      const v = item.getAttribute('data-view');
      const f = item.getAttribute('data-filter');
      if (v === viewName) {
        if (!f || f === state.filter) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      } else {
        item.classList.remove('active');
      }
    });

    if (viewName === 'backups') {
      loadBackupsList();
    }
  }

  // --- 9. Core User Actions ---
  async function handleScan() {
    if (state.isBusy) return;
    setBusy(true);
    showToast(t('scanStarted'), 'info');
    appendSyncLog(t('scanStarted'), 'info');

    try {
      const bridge = getBridge();
      const audit = await bridge.run_audit();
      state.conversations = Array.isArray(audit.conversations) ? audit.conversations : [];
      updateMetrics(audit);
      applyFilterAndSearch();
      const msg = t('scanComplete', { count: state.conversations.length });
      showToast(msg, 'success');
      appendSyncLog(msg, 'success');
      document.getElementById('footerStatusText').textContent = t('readyStatus');
    } catch (err) {
      console.error('Scan error:', err);
      showToast(String(err), 'error');
      appendSyncLog(String(err), 'error');
    } finally {
      setBusy(false);
    }
  }

  async function handleDryRun() {
    if (state.isBusy) return;
    setBusy(true);
    showToast(t('dryRunStarted'), 'info');
    appendSyncLog(t('dryRunStarted'), 'info');

    try {
      const bridge = getBridge();
      const res = await bridge.run_fix(true, true);
      const updated = res.conversations_updated || 0;
      const annotations = res.annotations_created || 0;
      const msg = t('dryRunComplete', { updated, annotations });
      showToast(msg, 'info', 5000);
      appendSyncLog(msg, 'success');
    } catch (err) {
      console.error('Dry-run error:', err);
      showToast(String(err), 'error');
      appendSyncLog(String(err), 'error');
    } finally {
      setBusy(false);
    }
  }

  async function handleFix() {
    if (state.isBusy) return;

    // Check process status before hot write
    await checkProcessStatus();
    if (state.isRunning) {
      const confirmed = window.confirm(t('fixWarnActive'));
      if (!confirmed) return;
    }

    setBusy(true);
    showToast(t('fixStarted'), 'warning');
    appendSyncLog(t('fixStarted'), 'warning');

    try {
      const bridge = getBridge();
      const res = await bridge.run_fix(false, true);

      if (res.success) {
        const updated = res.conversations_updated || 0;
        const annotations = res.annotations_created || 0;
        const msg = t('fixComplete', { updated, annotations });
        showToast(msg, 'success', 5000);
        appendSyncLog(msg, 'success');
        // Refresh audit table
        await handleScan();
      } else {
        const errDesc = (res.errors && res.errors.length) ? res.errors.join(', ') : (res.error || 'Failed');
        showToast(errDesc, 'error', 6000);
        appendSyncLog(errDesc, 'error');
      }
    } catch (err) {
      console.error('Fix error:', err);
      showToast(String(err), 'error');
      appendSyncLog(String(err), 'error');
    } finally {
      setBusy(false);
    }
  }

  // --- 9. Modal Backups & Rollback ---
  async function openBackupsModal() {
    const modal = document.getElementById('backupModal');
    modal.classList.remove('hidden');
    await checkProcessStatus();
    await loadBackupsList();
  }

  function closeBackupsModal() {
    const modal = document.getElementById('backupModal');
    modal.classList.add('hidden');
  }

  async function loadBackupsList() {
    const listEl = document.getElementById('backupList');
    const emptyEl = document.getElementById('emptyBackups');
    listEl.innerHTML = '';

    try {
      const bridge = getBridge();
      const snapshots = await bridge.list_backups();
      state.backups = Array.isArray(snapshots) ? snapshots : [];

      if (!state.backups.length) {
        emptyEl.classList.remove('hidden');
        return;
      }

      emptyEl.classList.add('hidden');

      state.backups.forEach((snap) => {
        const item = document.createElement('div');
        item.className = 'backup-item';

        const dateStr = snap.date_formatted || snap.id;
        const countStr = t('filesCount', { count: snap.files_count || 0 });
        const sizeStr = formatBytes(snap.size_bytes || 0);

        item.innerHTML = `
          <div class="backup-meta">
            <span class="backup-date">${escapeHtml(dateStr)}</span>
            <span class="backup-details">${escapeHtml(snap.id)} • ${countStr} • ${sizeStr}</span>
          </div>
          <button class="btn btn-secondary btn-restore" data-snap-id="${escapeHtml(snap.id)}" type="button">
            ${escapeHtml(t('btnRestore'))}
          </button>
        `;

        listEl.appendChild(item);
      });

      // Wire restore buttons
      listEl.querySelectorAll('.btn-restore').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const snapId = btn.getAttribute('data-snap-id');
          if (!snapId) return;
          await handleRestore(snapId);
        });
      });
    } catch (err) {
      console.error('Failed to list backups:', err);
      emptyEl.classList.remove('hidden');
    }
  }

  async function handleRestore(snapshotId) {
    await checkProcessStatus();
    if (state.isRunning) {
      showToast(t('restoreColdViolation'), 'error');
      return;
    }

    showToast(t('restoringSnapshot'), 'info');

    try {
      const bridge = getBridge();
      const res = await bridge.restore_backup(snapshotId);

      if (res.cold_disk_violation) {
        showToast(t('restoreColdViolation'), 'error', 5000);
        return;
      }

      if (res.success) {
        showToast(t('restoreSuccess'), 'success');
        closeBackupsModal();
        await handleScan();
      } else {
        showToast(res.error || t('restoreFailed'), 'error', 5000);
      }
    } catch (err) {
      showToast(String(err), 'error');
    }
  }

  // --- 10. Initialization & Event Wiring ---
  async function init() {
    // 1. Language detection
    let initialLang = 'ru';
    try {
      const savedLang = localStorage.getItem('antigravity_migrator_lang');
      if (savedLang === 'ru' || savedLang === 'en') {
        initialLang = savedLang;
      } else if (navigator.language && !navigator.language.startsWith('ru')) {
        initialLang = 'en';
      }
    } catch (_) {}

    // Check system info from bridge if available
    try {
      const bridge = getBridge();
      const info = await bridge.get_system_info();
      state.systemInfo = info;
      if (info && info.app_version) {
        const verEl = document.getElementById('appVersion');
        if (verEl) verEl.textContent = 'v' + info.app_version;
      }
      if (info) {
        const settingDataDir = document.getElementById('settingDataDir');
        if (settingDataDir && info.paths && info.paths.data_dir) {
          settingDataDir.textContent = info.paths.data_dir;
        }
        const settingBackupsDir = document.getElementById('settingBackupsDir');
        if (settingBackupsDir && info.paths && info.paths.backups_dir) {
          settingBackupsDir.textContent = info.paths.backups_dir;
        }
        const settingPlatform = document.getElementById('settingPlatform');
        if (settingPlatform) {
          settingPlatform.textContent = `${info.platform || 'macOS'} (${info.os || 'Darwin'}) • App v${info.app_version || '0.1.0'}`;
        }
      }
    } catch (_) {}

    setLanguage(initialLang);

    // 2. Wire Buttons & Controls
    document.getElementById('langToggle').addEventListener('click', () => {
      const nextLang = state.lang === 'ru' ? 'en' : 'ru';
      setLanguage(nextLang);
    });

    document.getElementById('btnScan').addEventListener('click', handleScan);
    document.getElementById('btnDryRun').addEventListener('click', handleDryRun);
    document.getElementById('btnFix').addEventListener('click', handleFix);
    document.getElementById('btnBackups').addEventListener('click', () => {
      switchView('backups');
    });

    document.getElementById('btnCloseModal').addEventListener('click', closeBackupsModal);
    document.getElementById('btnModalCloseSecondary').addEventListener('click', closeBackupsModal);

    // Sidebar view switching
    document.querySelectorAll('.sidebar-nav-item[data-filter]').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.sidebar-nav-item').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        state.filter = btn.getAttribute('data-filter') || 'all';
        switchView('chats');
        applyFilterAndSearch();
      });
    });

    document.querySelectorAll('.sidebar-nav-item[data-view]:not([data-filter])').forEach((btn) => {
      btn.addEventListener('click', () => {
        const view = btn.getAttribute('data-view');
        switchView(view);
      });
    });

    // Clear log button
    const btnClearLog = document.getElementById('btnClearLog');
    if (btnClearLog) {
      btnClearLog.addEventListener('click', () => {
        const logEl = document.getElementById('syncLogOutput');
        if (logEl) logEl.textContent = '';
      });
    }

    // Refresh backups button
    const btnRefreshBackups = document.getElementById('btnRefreshBackups');
    if (btnRefreshBackups) {
      btnRefreshBackups.addEventListener('click', () => {
        loadBackupsList();
        showToast(t('btnRefreshBackups'), 'info');
      });
    }

    // Export button
    const btnExport = document.getElementById('btnExport');
    if (btnExport) {
      btnExport.addEventListener('click', () => {
        const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(state.filteredList, null, 2));
        const downloadAnchor = document.createElement('a');
        downloadAnchor.setAttribute('href', dataStr);
        downloadAnchor.setAttribute('download', `antigravity_conversations_${Date.now()}.json`);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
        showToast(t('exportSuccess') || 'Экспорт завершен', 'success');
      });
    }

    // Search input
    const searchInput = document.getElementById('searchInput');
    const btnClearSearch = document.getElementById('btnClearSearch');

    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      if (state.searchQuery) {
        btnClearSearch.classList.remove('hidden');
      } else {
        btnClearSearch.classList.add('hidden');
      }
      applyFilterAndSearch();
    });

    btnClearSearch.addEventListener('click', () => {
      searchInput.value = '';
      state.searchQuery = '';
      btnClearSearch.classList.add('hidden');
      applyFilterAndSearch();
      searchInput.focus();
    });

    // Segmented tabs
    document.querySelectorAll('.segment-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.segment-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        state.filter = btn.getAttribute('data-filter') || 'all';
        applyFilterAndSearch();
      });
    });

    // 3. Initial check & scan
    await checkProcessStatus();
    setInterval(checkProcessStatus, 4000);
    await handleScan();
  }

  // Handle pywebview ready event or DOM ready
  if (window.pywebview) {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    window.addEventListener('pywebviewready', () => {
      if (!state.systemInfo) init();
    });
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        setTimeout(init, 30);
      });
    } else {
      init();
    }
  }
})();
