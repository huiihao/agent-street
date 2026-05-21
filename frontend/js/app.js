// Bootstrap the Mimic Stock Market frontend
(function () {
  const ws = new WSClient('ws://' + window.location.host + '/ws');
  const personaGrid = new PersonaGrid('persona-canvas');
  const stockChart = new StockChart('chart-canvas');
  const leaderboard = new Leaderboard('leader-canvas');
  const tradeFeed = new TradeFeed('trade-feed');

  const btnStart = document.getElementById('btn-start');
  const btnStop = document.getElementById('btn-stop');
  const btnReset = document.getElementById('btn-reset');
  const stStatus = document.getElementById('st-status');
  const stTick = document.getElementById('st-tick');
  const stSim = document.getElementById('st-sim');

  // Load persona definitions
  fetch('/api/personas')
    .then(r => r.json())
    .then(defs => {
      personaGrid.setDefs(defs);
      const colors = {};
      defs.forEach(d => { colors[d.id] = d.color; });
      leaderboard.setColors(colors);
      personaGrid.render();
    });

  // WebSocket event handlers
  ws.on('tick', (data) => {
    // Update persona grid
    if (data.personas) {
      personaGrid.update(data.personas);
      leaderboard.update(data.personas);
    }

    // Update stock chart
    if (data.prices) {
      stockChart.addTick(data.prices, data.tick);
    }

    // Update trade feed
    if (data.trades) {
      tradeFeed.append(data.trades);
    }

    // Update sentiment bar
    if (data.sentiment !== undefined) {
      const pct = ((data.sentiment + 1) / 2) * 100;
      document.getElementById('sentiment-fill').style.width = pct + '%';
    }

    // Update status
    stTick.textContent = 'TICK ' + data.tick;
  });

  ws.on('sim_state', (data) => {
    const running = data.running;
    btnStart.disabled = running;
    btnStop.disabled = !running;
    stSim.textContent = 'SIM: ' + (running ? 'RUNNING' : 'STOPPED');
    stSim.className = running ? 'running' : 'stopped';
  });

  ws.on('connection', (connected) => {
    stStatus.textContent = connected ? '● CONNECTED' : '● DISCONNECTED';
    stStatus.className = connected ? 'connected' : 'disconnected';
  });

  // Button handlers
  btnStart.addEventListener('click', () => ws.send('start'));
  btnStop.addEventListener('click', () => ws.send('stop'));
  btnReset.addEventListener('click', () => ws.send('reset'));

  // Connect
  ws.connect();
})();
