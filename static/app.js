(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  function fmtAge(sec) {
    if (sec === null || sec === undefined) return '—';
    if (sec < 60) return sec.toFixed(1) + 's';
    return (sec / 60).toFixed(1) + 'm';
  }

  function statusPill(drone) {
    if (drone.connected) {
      return '<span class="pill ok">ONLINE</span>';
    }
    if (drone.error === 'stale') {
      return '<span class="pill warn">STALE</span>';
    }
    return '<span class="pill bad">OFFLINE</span>';
  }

  function renderDrones(summary) {
    var body = $('drone-body');
    var drones = summary.drones || [];
    $('stat-connected').textContent = summary.connected || 0;
    $('stat-total').textContent = summary.total || 0;
    $('stat-uptime').textContent = (summary.uptime_sec || 0) + 's';
    $('refresh-age').textContent = new Date().toLocaleTimeString();

    if (!drones.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty">No drones discovered yet</td></tr>';
      return;
    }

    body.innerHTML = drones.map(function (d) {
      return (
        '<tr>' +
          '<td>' + statusPill(d) + '</td>' +
          '<td>' + (d.ip || '') + '</td>' +
          '<td>' + (d.mac || '—') + '</td>' +
          '<td>' + (d.battery != null ? d.battery + '%' : '—') + '</td>' +
          '<td>' + (d.sn || '—') + '</td>' +
          '<td>' + (d.sdk || '—') + '</td>' +
          '<td>' + fmtAge(d.age_sec) + '</td>' +
          '<td>' + (d.error || '') + '</td>' +
          '<td><button type="button" class="secondary btn-battery" data-ip="' + d.ip + '">battery?</button></td>' +
        '</tr>'
      );
    }).join('');

    Array.prototype.forEach.call(document.querySelectorAll('.btn-battery'), function (btn) {
      btn.addEventListener('click', function () {
        var ip = btn.getAttribute('data-ip');
        fetch('/api/drones/' + encodeURIComponent(ip) + '/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: 'battery?' })
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            alert(ip + ' → ' + (data.response != null ? data.response : 'no response'));
            refresh();
          })
          .catch(function (err) { alert(err); });
      });
    });
  }

  function renderAp(ap) {
    if (!ap) return;
    $('ap-ssid').textContent = ap.ssid || '—';
    $('info-ssid').textContent = ap.ssid || '—';
    $('info-password').textContent = ap.password || '—';
    $('info-gateway').textContent = ap.gateway || '—';
    $('info-iface').textContent = ap.interface || '—';
    if (ap.dhcp_range) {
      $('info-dhcp').textContent = ap.dhcp_range[0] + ' – ' + ap.dhcp_range[1];
    }
    $('info-mode').textContent = ap.dry_run ? 'dry-run' : (ap.running ? 'running' : 'stopped');
  }

  function refresh() {
    fetch('/api/status')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderAp(data.ap);
        renderDrones(data.drones || {});
      })
      .catch(function (err) {
        console.error(err);
      });
  }

  $('btn-refresh').addEventListener('click', refresh);

  $('add-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var ip = $('add-ip').value.trim();
    fetch('/api/drones/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip: ip })
    })
      .then(function (r) { return r.json(); })
      .then(function () {
        $('add-ip').value = '';
        refresh();
      });
  });

  $('broadcast-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var command = $('broadcast-cmd').value.trim();
    fetch('/api/broadcast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: command })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        $('broadcast-result').textContent = JSON.stringify(data.results || {}, null, 2);
        refresh();
      });
  });

  refresh();
  setInterval(refresh, 2000);
})();
