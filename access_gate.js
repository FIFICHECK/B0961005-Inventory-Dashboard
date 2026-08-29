/* B0961005 Dashboard — Email Access Gate（方案 A: email 申請 → admin 通知 → allowlist）
 * Flow (same as P0068001):
 * 1. Visitor submits email → formsubmit.co emails admin (jerry@hktv.com.hk) with an approve link
 * 2. Admin clicks approve link → approve.html → clicks 批准 → Discord webhook [APPROVE-REQ-B0961005]
 * 3. Poller cron reads webhook → appends email to data/access_allowlist.json → pushes to GitHub
 * 4. Visitor refreshes → gate fetches allowlist JSON → email present → dashboard revealed
 * Storage: localStorage remembers email across visits.
 */
(function () {
  var ALLOWLIST_URL = 'data/access_allowlist.json';
  var LS_KEY = 'b0961005-access-email';
  // base64 of jerry@hktv.com.hk (avoid exposing plaintext in source)
  var GATE_ADMIN_EMAIL = 'amVycnlAaGt0di5jb20uaGs=';
  var POLL_MS = 15000;

  function normEmail(e) { return String(e || '').trim().toLowerCase(); }

  function decodeAdminEmail() {
    try { return atob(GATE_ADMIN_EMAIL); } catch (e) { return ''; }
  }

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
    if (status) status.textContent = form ? '' : '已送出申請！管理員批准後，重新整理此頁即可進入。';
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
    var adminEmail = decodeAdminEmail();
    // One-time token to prevent approve URL being guessed
    var token = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);
    var approveLink = location.origin + location.pathname.replace(/[^/]*$/, '') + 'approve.html?email=' + encodeURIComponent(email) + '&t=' + encodeURIComponent(token);
    fetch('https://formsubmit.co/ajax/' + adminEmail, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({
        email: email,
        _subject: '🔐 B0961005 Dashboard 訪問申請',
        _template: 'table',
        _captcha: 'false',
        '✅ 批准訪問 (Approve)': approveLink
      })
    }).then(function () {
      if (status) status.textContent = '✅ 已送出申請！管理員批准後，重新整理此頁即可進入。';
      showGate(false);
      schedulePoll();
    }).catch(function () {
      if (status) status.textContent = '❌ 送出失敗 — 請直接 email ' + adminEmail;
    });
  }

  function checkAccess() {
    var email = getStoredEmail();
    if (!email) { showGate(true); return; }
    fetch(ALLOWLIST_URL + '?v=' + Date.now())
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (lst) {
        var norm = (lst || []).map(String).map(function (s) { return s.trim().toLowerCase(); });
        if (norm.indexOf(email) >= 0) {
          hideGate();
        } else {
          showGate(false);
          schedulePoll();
        }
      })
      .catch(function () {
        // allowlist unreachable — fail-open to avoid locking out legit visitors
        hideGate();
      });
  }

  function schedulePoll() {
    if (window.__gatePolling) return;
    window.__gatePolling = setInterval(function () {
      var email = getStoredEmail();
      if (!email) { clearInterval(window.__gatePolling); window.__gatePolling = null; showGate(true); return; }
      fetch(ALLOWLIST_URL + '?v=' + Date.now())
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (lst) {
          var norm = (lst || []).map(String).map(function (s) { return s.trim().toLowerCase(); });
          if (norm.indexOf(email) >= 0) {
            clearInterval(window.__gatePolling);
            window.__gatePolling = null;
            hideGate();
          }
        })
        .catch(function () { /* retry next tick */ });
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
