// Gate scanner: camera QR scanning with manual-entry fallback. Decisions come from the TicketAgent.
(function () {
  var resultBox = document.getElementById('result');
  var lastCode = '', lastTime = 0, scanner = null;

  function show(data) {
    var cls = data.ok ? 'alert-success' : (data.result === 'error' ? 'alert-secondary' : 'alert-danger');
    resultBox.className = 'alert ' + cls;
    var title = data.ok ? 'ADMIT' : 'REJECT';
    var who = data.holder ? ' · ' + data.holder + ' (' + data.category + ')' : '';
    var extra = data.suspicious ? ' ⚠ Repeated scans of this code - possible shared screenshot.' : '';
    resultBox.textContent = '';
    var strong = document.createElement('strong');
    strong.textContent = (data.result === 'error' ? 'ERROR' : title) + ': ';
    resultBox.appendChild(strong);
    resultBox.appendChild(document.createTextNode((data.ok ? 'Ticket valid' : data.reason) + who + extra));
    if (navigator.vibrate) { navigator.vibrate(data.ok ? 80 : [120, 60, 120]); }
  }

  // The camera keeps seeing the same QR for as long as it is held up, so the same code from the camera is
  // ignored for 10 seconds (otherwise the first ADMIT is followed by "already used" and false repeat-scan alarms).
  // Typing/pasting a code is always sent (1 s guard only against a double click).
  function check(code, fromCamera) {
    code = (code || '').trim();
    // QR now holds a link like https://site/verify/<code>; keep only the code
    var m = code.match(/\/verify\/([^\/?#\s]+)/);
    if (m) { code = m[1]; }
    if (!code) { return; }
    var now = Date.now();
    var cooldown = fromCamera === true ? 10000 : 1000;
    if (code === lastCode && now - lastTime < cooldown) { return; }
    lastCode = code; lastTime = now;
    fetch('/staff/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.getElementById('csrf').value},
      body: JSON.stringify({code: code, event_id: document.getElementById('event').value})
    }).then(function (r) { return r.json(); }).then(show).catch(function () {
      show({ok: false, result: 'error', reason: 'Network problem - try again.'});
    });
  }

  document.getElementById('check').addEventListener('click', function () {
    var box = document.getElementById('manual');
    check(box.value); box.value = '';
  });
  document.getElementById('manual').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); document.getElementById('check').click(); }
  });
  document.getElementById('startcam').addEventListener('click', function () {
    if (scanner) { return; }
    if (typeof Html5Qrcode === 'undefined') { show({ok: false, result: 'error', reason: 'Camera library not loaded - use manual entry.'}); return; }
    scanner = new Html5Qrcode('reader');
    scanner.start({facingMode: 'environment'}, {fps: 10, qrbox: 240}, function (text) { check(text, true); }).catch(function () {
      scanner = null;
      show({ok: false, result: 'error', reason: 'Camera not available (allow camera access, HTTPS required). Use manual entry.'});
    });
  });
})();
