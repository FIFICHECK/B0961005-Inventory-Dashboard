/* B0961005 Dashboard — Email Access Gate
 * Flow: visitor enters email → row written to Supabase checks table (state=0, pending)
 *       → Hermes cron notifies owner → owner approves → Hermes sets state=1
 *       → frontend polls, sees state=1, reveals dashboard.
 * Storage: localStorage remembers email across visits.
 */
(function () {
  var SB_URL = 'https://mbeftbvpeqfmyxvbpmcy.supabase.co';
  var SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1iZWZ0YnZwZXFmbXl4dmJwbWN5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxMDMwNjksImV4cCI6MjEwMjY3OTA2OX0.B5oK2HjzSBFvOkuyUFWuqJ3Yoiy2ivR39L2yx0OUKEM';
  var LS_KEY = 'b0961005_gate_email';
  var POLL_MS = 10000;

  function normEmail(e) { return String(e || '').trim().toLowerCase(); }

  function getStoredEmail() {
    try { return normEmail(localStorage.getItem(LS_KEY)); } catch (e) { return ''; }
  }

  function setStoredEmail(e) {
    try { localStorage.setItem(LS_KEY, normEmail(e)); } catch (err) { /* private mode */ }
  }

  function gateEl(id) { return document.getElementById(id); }

  function showGate(form) {
    var g = gateEl('accessGate');
    if (g) g.style.display = 'flex';
    var formBox = gateEl('gateFormBox');
    if (formBox) formBox.style.display = form ? 'block' : 'none';
    var status = gateEl('gateStatus');
    if (status) status.textContent = form ? '' : '已提交申請，等待批核… 會自動更新。';
  }

  function hideGate() {
    var g = gateEl('accessGate');
    if (g) g.style.display = 'none';
  }

  function requestAccess() {
    var email = normEmail(gateEl('gateEmail') ? gateEl('gateEmail').value : '');
    var status = gateEl('gateStatus');
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!re.test(email)) {
      if (status) status.textContent = '請輸入有效 email 地址。';
      return;
    }
    setStoredEmail(email);
    var row = { check_key: 'ACCESS_' + email, state: 0 };
    fetch(SB_URL + '/rest/v1/checks', {
      method: 'POST',
      headers: {
        'apikey': SB_KEY,
        'Authorization': 'Bearer ' + SB_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify([row])
    }).then(function (r) {
      if (status) status.textContent = '已提交申請（' + email + '），等待批核… 批核後會自動載入。';
      showGate(false);
      schedulePoll();
    }).catch(function () {
      if (status) status.textContent = '提交失敗，請稍後再試。';
    });
  }

  function checkAccess() {
    var email = getStoredEmail();
    if (!email) { showGate(true); return; }
    fetch(SB_URL + '/rest/v1/checks?check_key=eq.ACCESS_' + encodeURIComponent(email) + '&select=state', {
      headers: { 'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY }
    }).then(function (r) { return r.json(); }).then(function (rows) {
      if (Array.isArray(rows) && rows.length > 0 && rows[0].state === 1) {
        hideGate();
      } else if (Array.isArray(rows) && rows.length > 0 && rows[0].state === 0) {
        showGate(false);
        schedulePoll();
      } else {
        // No row yet (or rejected/unknown) — show form
        showGate(true);
      }
    }).catch(function () {
      // Supabase unreachable — allow entry (fail-open) to avoid locking out legit visitors
      hideGate();
    });
  }

  function schedulePoll() {
    if (window.__gatePolling) return;
    window.__gatePolling = setInterval(function () {
      var email = getStoredEmail();
      if (!email) { clearInterval(window.__gatePolling); window.__gatePolling = null; showGate(true); return; }
      fetch(SB_URL + '/rest/v1/checks?check_key=eq.ACCESS_' + encodeURIComponent(email) + '&select=state', {
        headers: { 'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY }
      }).then(function (r) { return r.json(); }).then(function (rows) {
        if (Array.isArray(rows) && rows.length > 0 && rows[0].state === 1) {
          clearInterval(window.__gatePolling);
          window.__gatePolling = null;
          hideGate();
        }
      }).catch(function () { /* retry next tick */ });
    }, POLL_MS);
  }

  // Expose for inline onclick
  window.requestAccess = requestAccess;
  window.gateLogout = function () {
    try { localStorage.removeItem(LS_KEY); } catch (e) {}
    showGate(true);
  };

  // Init: gate overlay is injected by the HTML; run check on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkAccess);
  } else {
    checkAccess();
  }
})();
