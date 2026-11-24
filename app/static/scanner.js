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

  function check(code) {
    code = (code || '').trim();
    if (!code) { return; }
    var now = Date.now();
    if (code === lastCode && now - lastTime < 3000) { return; }  // ignore the camera re-reading the same QR
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
    scanner.start({facingMode: 'environment'}, {fps: 10, qrbox: 240}, check).catch(function () {
      scanner = null;
      show({ok: false, result: 'error', reason: 'Camera not available (allow camera access, HTTPS required). Use manual entry.'});
    });
  });
})();
