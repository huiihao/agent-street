(function () {
  const ws = new WSClient('ws://' + window.location.host + '/ws');
  const townMap = new TownMap('town-canvas');
  const stockChart = new StockChart('chart-canvas');
  const leaderboard = new Leaderboard('leader-canvas');
  const tradeFeed = new TradeFeed('trade-feed');
  const agentDetail = new AgentDetail('agent-detail');
  const observerReports = new ObserverReports('observer-reports');

  const btnStart = document.getElementById('btn-start');
  const btnStop = document.getElementById('btn-stop');
  const btnReset = document.getElementById('btn-reset');
  const stStatus = document.getElementById('st-status');
  const stTick = document.getElementById('st-tick');
  const stSim = document.getElementById('st-sim');
  const stWorldTime = document.getElementById('st-world-time');
  const stSpeed = document.getElementById('st-speed');

  // Speed control: click to cycle 1x -> 2x -> 5x -> MAX -> 1x
  const speeds = [1, 2, 5, 20];
  let speedIdx = 0;
  stSpeed.style.cursor = 'pointer';
  stSpeed.title = 'Click to change simulation speed';
  stSpeed.addEventListener('click', () => {
    speedIdx = (speedIdx + 1) % speeds.length;
    const s = speeds[speedIdx];
    stSpeed.textContent = s >= 20 ? '⚡MAX' : '⚡' + s + 'x';
    ws.send('speed:' + s);
  });

  // Load town map and persona definitions
  townMap.init();

  fetch('/api/personas')
    .then(r => r.json())
    .then(defs => {
      agentDetail.setDefs(defs);
      const colors = {};
      defs.forEach(d => {
        colors[d.id] = d.color;
        if (!townMap.agents[d.id]) townMap.agents[d.id] = {};
        townMap.agents[d.id].color = d.color;
      });
      leaderboard.setColors(colors);
    })
    .catch(e => console.error('Failed to load persona defs:', e));

  townMap.onSelectAgent = (agentId) => {
    agentDetail.show(agentId);
  };

  // WebSocket tick handler
  ws.on('tick', (data) => {
    if (data.personas) {
      townMap.updateAgentStates(data.personas);
      agentDetail.updateStates(data.personas);
      const traders = (data.personas || []).filter(
        p => !['physicist', 'mathematician', 'mystic'].includes(p.id)
      );
      leaderboard.update(traders);
      if (agentDetail.currentId) agentDetail.render();
    }
    if (data.conversations) {
      townMap.updateConversations(data.conversations);
    }
    if (data.prices) {
      stockChart.addTick(data.prices, data.tick);
    }
    if (data.observerReports) {
      observerReports.append(data.observerReports);
    }
    if (data.trades) {
      townMap.updateTrades(data.trades);
      tradeFeed.append(data.trades);
    }
    if (data.sentiment !== undefined) {
      const pct = ((data.sentiment + 1) / 2) * 100;
      document.getElementById('sentiment-fill').style.width = pct + '%';
    }
    townMap.renderFrame();

    // Update world time and tick
    if (data.worldTime) {
      stWorldTime.textContent = '🕐 ' + data.worldTime;
      townMap.setWorldTime(data.worldTime);
    }
    stTick.textContent = 'TICK ' + data.tick;
  });

  ws.on('sim_state', (data) => {
    const running = data.running;
    btnStart.disabled = running;
    btnStop.disabled = !running;
    stSim.textContent = 'SIM: ' + (running ? 'RUNNING' : 'STOPPED');
    stSim.className = running ? 'running' : 'stopped';
    if (data.speed) {
      const s = data.speed;
      stSpeed.textContent = s >= 20 ? 'MAX' : s + 'x';
    }
  });

  ws.on('connection', (connected) => {
    stStatus.textContent = connected ? '● CONNECTED' : '● DISCONNECTED';
    stStatus.className = connected ? 'connected' : 'disconnected';
  });

  btnStart.addEventListener('click', () => ws.send('start'));
  btnStop.addEventListener('click', () => ws.send('stop'));
  btnReset.addEventListener('click', () => ws.send('reset'));

  ws.connect();
})();
