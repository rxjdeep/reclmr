// ===== Module: lego3d =====
let longPressFired = false;

function saveLegoFile(path) {
  // Use a hidden iframe to trigger download (more reliable on iOS than anchor click)
  const iframe = document.createElement('iframe');
  iframe.style.display = 'none';
  iframe.src = `/api/lego/download?path=${encodeURIComponent(path)}`;
  document.body.appendChild(iframe);
  setTimeout(() => iframe.remove(), 3000);
}

// Context menu = long-press on iOS Safari
document.addEventListener('contextmenu', e => {
  // On thumbnail with save path
  const thumb = e.target.closest('.lego-thumb[data-save-path]');
  if (thumb) {
    e.preventDefault();
    saveLegoFile(thumb.dataset.savePath);
    if (navigator.vibrate) navigator.vibrate(50);
    return;
  }
  // On full image viewer
  const viewer = document.getElementById('lego-image-viewer');
  if (viewer && viewer.style.display !== 'none' && legoCurrentImage) {
    e.preventDefault();
    saveLegoFile(legoCurrentImage);
    if (navigator.vibrate) navigator.vibrate(50);
    return;
  }
});

// ─── Service Worker ──────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js?v=107').catch(() => {});
  // a new version arrived while an old page was showing: reload into it, but never while something is playing
  var shellStale = false;
  function shellPlaying() { return Array.prototype.some.call(document.querySelectorAll('audio'), function (a) { return !a.paused && !a.ended; }); }
  function shellReload() { if (!shellPlaying()) location.reload(); }
  navigator.serviceWorker.addEventListener('message', function (e) {
    if (!e.data || e.data.t !== 'shell-updated') return;
    if (window.reclmrUpdateCheck) { window.reclmrUpdateCheck(); return; }       // reloads only if this page is really behind the server (one reload, not one per message)
    if (performance.now() < 10000) shellReload(); else shellStale = true;
  });
  document.addEventListener('visibilitychange', function () { if (shellStale && !document.hidden) { shellStale = false; shellReload(); } });
}

// ─── Init (wrapped in try-catch so one failure doesn't brick everything) ─
// Delayed slightly so auth.js can check authentication first.
// If login screen is showing, skip init until user authenticates.
function reclmrInit() {
  // Don't init if login screen is visible (not yet authenticated)
  var loginScreen = document.getElementById('login-screen');
  if (loginScreen && loginScreen.style.display !== 'none' && loginScreen.style.display !== '') {
    // Login screen is showing - retry in 500ms
    setTimeout(reclmrInit, 500);
    return;
  }
  if (typeof loadHomeUser === 'function') loadHomeUser();      // the name for the prompt on the home screen
  buildStatusChips();
  buildAppGrid();
  buildProjectsSection();
  loadQuickStats();
  updateNotifBadge();
  refreshNotifications();
  refreshProjectCards();
  setInterval(loadQuickStats, 2000);
  setInterval(refreshProjectCards, 120000);
  setInterval(refreshNotifications, 60000);
}
try { reclmrInit(); } catch(e) { console.error('recl/\\mr init error:', e); showCrashRecovery(e); }

// Restore screen from URL hash on load/refresh
function restoreFromHash() {
  navApply(navHash(), true);  // see nav.js; empty hash stays on the home screen
}
// Wait until every module script has run (music.js etc. load after this file)
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', restoreFromHash);
else restoreFromHash();

// ─── VOICE SYSTEM ───────────────────────────────────────
