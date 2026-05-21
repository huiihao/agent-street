(function () {
  const ws = new WSClient('ws://' + window.location.host + '/ws');
  const townMap = new TownMap('town-canvas');
  const stockChart = new StockChart('chart-canvas');
  const leaderboard = new Leaderboard('leader-canvas');
  const tradeFeed = new TradeFeed('trade-feed');
  const agentDetail = new AgentDetail('agent-detail');

  const btnStart = document.getElementById('btn-start');
  const btnStop = document.getElementById('btn-stop');
  const btnReset = document.getElementById('btn-reset');
  const stStatus = document.getElementById('st-status');
  const stTick = document.getElementById('st-tick');
  const stSim = document.getElementById('st-sim');

  // Load town map and persona definitions
  townMap.init();

  fetch('/api/personas')
    .then(r => r.json())
    .then(defs => {
      agentDetail.setDefs(defs);
      const colors = {};
      defs.forEach(d => {
        colors[d.id] = d.color;
        // Pre-seed town map agent colors from persona defs
        if (!townMap.agents[d.id]) townMap.agents[d.id] = {};
        townMap.agents[d.id].color = d.color;
      });
      leaderboard.setColors(colors);
    })
    .catch(e => console.error('Failed to load persona defs:', e));

  // Click agent -> detail panel
  townMap.onSelectAgent = (agentId) => {
    agentDetail.show(agentId);
  };

  // WebSocket tick handler
  ws.on('tick', (data) => {
    if (data.personas) {
      townMap.updateAgentStates(data.personas);
      agentDetail.updateStates(data.personas);
      leaderboard.update(data.personas);
      if (agentDetail.currentId) agentDetail.render();
    }
    if (data.conversations) {
      townMap.updateConversations(data.conversations);
    }
    if (data.prices) {
      stockChart.addTick(data.prices, data.tick);
    }
    if (data.trades) {
      tradeFeed.append(data.trades);
    }
    if (data.sentiment !== undefined) {
      const pct = ((data.sentiment + 1) / 2) * 100;
      document.getElementById('sentiment-fill').style.width = pct + '%';
    }
    townMap.renderFrame();
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

  btnStart.addEventListener('click', () => ws.send('start'));
  btnStop.addEventListener('click', () => ws.send('stop'));
  btnReset.addEventListener('click', () => ws.send('reset'));

  ws.connect();
})();
