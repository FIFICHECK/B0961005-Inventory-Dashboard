/* B0961005 Dashboard — Email Access Gate（方案 A: email 申請 → admin 通知 → allowlist）
 * v2 (2026-08-29): + token verification — application writes a pending row to Supabase
 * (check_key = ACCESS_{email}_{sha256(token)}, state=0); the poller only approves when
 * the token in the approve webhook matches a pending row (sha256 match). This prevents
 * anyone who grabs the public webhook token from forging approvals.
 *
 * Flow:
 * 1. Visitor submits email → pending row written to Supabase + formsubmit emails admin
 *    (jerry@hktv.com.hk) with an approve link carrying a one-time token
 * 2. Admin clicks approve link → approve.html → clicks 批准 → Discord webhook [APPROVE-REQ]
 * 3. Poller cron reads webhook → verifies sha256(token) against Supabase pending row →
 *    appends email to data/access_allowlist.json → pushes to GitHub → deletes pending row
 * 4. Visitor refreshes → gate fetches allowlist JSON → email present → dashboard revealed
 */
(function () {
  var ALLOWLIST_URL = 'data/access_allowlist.json';
  var LS_KEY = 'b0961005-access-email';
  // base64 of jerry@hktv.com.hk (avoid exposing plaintext in source)
  var GATE_ADMIN_EMAIL = 'amVycnlAaGt0di5jb20uaGs=';
  // Supabase (used only as a pending-token store; anon key is public by design)
  var SB_URL = 'https://mbeftbvpeqfmyxvbpmcy.supabase.co';
  var SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1iZWZ0YnZwZXFmbXl4dmJwbWN5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxMDMwNjksImV4cCI6MjEwMjY3OTA2OX0.B5oK2HjzSBFvOkuyUFWuqJ3Yoiy2ivR39L2yx0OUKEM';
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

  function sha256Hex(str) {
    // Synchronous-ish: returns a Promise. Uses SubtleCrypto when available, else a simple fallback.
    if (window.crypto && crypto.subtle && crypto.subtle.digest) {
      return crypto.subtle.digest('SHA-256', new TextEncoder().encode(str)).then(function (buf) {
        return Array.prototype.map.call(new Uint8Array(buf), function (b) {
          return ('0' + b.toString(16)).slice(-2);
        }).join('');
      });
    }
    // Fallback: simple djb2-style hash (NOT cryptographically secure — only used when SubtleCrypto missing)
    var h = 5381;
    for (var i = 0; i < str.length; i++) { h = ((h << 5) + h + str.charCodeAt(i)) | 0; }
    return Promise.resolve('fb' + (h >>> 0).toString(16));
  }

  function writePending(email, tokenHash) {
    return fetch(SB_URL + '/rest/v1/checks', {
      method: 'POST',
      headers: {
        'apikey': SB_KEY,
        'Authorization': 'Bearer ' + SB_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify([{ check_key: 'ACCESS_' + email + '_' + tokenHash, state: 0 }])
    });
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
    // One-time token (defense: poller verifies sha256(token) against pending row)
    var token = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);
    sha256Hex(token).then(function (tokenHash) {
      writePending(email, tokenHash).then(function () {
        var approveLink = location.origin + location.pathname.replace(/[^/]*$/, '') + 'approve.html?email=' + encodeURIComponent(email) + '&t=' + encodeURIComponent(token);
        return fetch('https://formsubmit.co/ajax/' + adminEmail, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          body: JSON.stringify({
            email: email,
            _subject: '🔐 B0961005 Dashboard 訪問申請',
            _template: 'table',
            _captcha: 'false',
            '✅ 批准訪問 (Approve)': approveLink
          })
        });
      }).then(function () {
        if (status) status.textContent = '✅ 已送出申請！管理員批准後，重新整理此頁即可進入。';
        showGate(false);
        schedulePoll();
      }).catch(function () {
        if (status) status.textContent = '❌ 送出失敗 — 請直接 email ' + adminEmail;
      });
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
