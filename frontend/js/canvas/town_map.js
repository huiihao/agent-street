/**
 * Agent Street Town Map — Star-Office-UI polished pixel art + MiroFish boids.
 *
 * Star-Office-UI inspiration: state-driven sprite animation, zone-based layout,
 *   speech bubbles, cohesive pixel palette, ambient lighting.
 * MiroFish inspiration: boids flocking (separation/alignment/cohesion),
 *   sentiment auras, emergent group clustering, opinion cascades.
 */
const TILE_PX = 28;
const MAP_COLS = 20;
const MAP_ROWS = 14;
const SC = 2; // sprite scale

// ── Star-Office-UI cohesive pixel palette ─────────────────
const P = {
  grass:       '#5a8f4a',
  grassAlt:    '#4f7d41',
  grassFlower: '#e8d44d',
  grassStone:  '#7a7a6a',
  road:        '#8a8a82',
  roadLine:    '#d4c840',
  roadEdge:    '#6a6a62',
  sidewalk:    '#a0a098',
  sidewalkLine:'#8a8a82',
  water:       '#4a8ab8',
  waterShimmer:'#7ab8d8',
  waterDeep:   '#306080',
  treeTrunk:   '#7a5630',
  treeCanopy:  '#3a7a3a',
  treeCanopyLt:'#4a9a4a',
  bldgShadow:  'rgba(0,0,0,0.35)',
  nightOverlay:'rgba(8,8,36,0.55)',
  eveningOvl:  'rgba(40,18,10,0.22)',
  dawnOvl:     'rgba(55,35,15,0.12)',
  agentShadow: 'rgba(0,0,0,0.35)',
  skinLight:   '#f8d8b8',
  skinShadow:  '#d4a878',
  white:       '#f0ece4',
  black:       '#1a1a2e',
  gold:        '#f0c840',
  red:         '#e84855',
  green:       '#4ecca3',
  blue:        '#5a9ed4',
};

// ── MiroFish boids constants ───────────────────────────────
const BOIDS = {
  sepRadius: 2.5,    // tiles — separation distance
  cohRadius: 4.0,    // tiles — cohesion distance
  sepWeight: 0.6,    // how strongly to separate
  cohWeight: 0.3,    // how strongly to cohere
  maxSpeed:  0.15,   // max tile-units per frame
};

// ── Activity states (Star-Office-UI inspired) ──────────────
const ACTIVITY = {
  idle:     { color: '#555', label: 'idle' },
  moving:   { color: '#4ecca3', label: 'moving' },
  trading:  { color: '#f0c840', label: 'trading' },
  chatting: { color: '#5a9ed4', label: 'chatting' },
  panicking:{ color: '#e84855', label: 'panicking' },
};

class TownMap {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.ctx.imageSmoothingEnabled = false;
    this.mapData = null;
    this.locations = [];
    this.agents = {};
    this.conversations = [];
    this.hoveredAgent = null;
    this.selectedAgent = null;
    this.onSelectAgent = null;
    this._t = 0;           // animation frame counter
    this._worldHour = 12;
    this._rain = [];
    this._fireflies = [];
    this._lastTrades = {};
    this._sentiment = 0;
    this._initParticles();
    this._loop = null;

    this.canvas.addEventListener('mousemove', e => this._mouseMove(e));
    this.canvas.addEventListener('click', e => this._click(e));
    this.canvas.addEventListener('mouseleave', () => this.hoveredAgent = null);
  }

  // ── Public API ──────────────────────────────────────────

  async init() {
    const r = await fetch('/api/town');
    const d = await r.json();
    this.mapData = d.map;
    this.locations = d.locations;
    this._startLoop();
  }

  updateAgentStates(states) {
    if (!states) return;
    states.forEach(s => {
      const prev = this.agents[s.id];
      const had = prev && prev.tx !== undefined;
      this.agents[s.id] = {
        ...prev,
        tx: had ? prev.tx : s.tileX,
        ty: had ? prev.ty : s.tileY,
        vx: prev ? (prev.vx || 0) : 0,
        vy: prev ? (prev.vy || 0) : 0,
        targetTX: s.tileX,
        targetTY: s.tileY,
        location: s.location,
        mood: s.mood,
        color: s.color || (prev ? prev.color : '#888'),
        isMoving: s.isMoving,
      };
    });
  }

  updateTrades(trades) {
    if (!trades) return;
    for (const t of trades) {
      if (!['physicist','mathematician','mystic'].includes(t.persona)) {
        this._lastTrades[t.persona] = { dir: t.direction, reason: t.reason, tick: this._t };
      }
    }
  }

  updateConversations(convs) { this.conversations = convs || []; }
  setWorldTime(t) {
    if (!t) return;
    const m = t.match(/(\d{2}):(\d{2})/);
    if (m) this._worldHour = parseInt(m[1]) + parseInt(m[2]) / 60;
  }
  setSentiment(v) { this._sentiment = v || 0; }
  renderFrame() {}

  // ── Animation loop ──────────────────────────────────────

  _startLoop() {
    const tick = () => {
      this._t++;
      this._applyBoids();
      this._draw();
      this._loop = requestAnimationFrame(tick);
    };
    this._loop = requestAnimationFrame(tick);
  }

  // ── MiroFish boids ──────────────────────────────────────

  _applyBoids() {
    const agents = Object.values(this.agents);
    if (agents.length < 2) return;

    for (const a of agents) {
      let sepX = 0, sepY = 0, cohX = 0, cohY = 0;
      let sepN = 0, cohN = 0;

      for (const b of agents) {
        if (a === b) continue;
        const dx = a.tx - b.tx;
        const dy = a.ty - b.ty;
        const dist = Math.hypot(dx, dy);

        // Separation: steer away from nearby agents
        if (dist < BOIDS.sepRadius && dist > 0.01) {
          sepX += dx / dist;
          sepY += dy / dist;
          sepN++;
        }
        // Cohesion: steer toward group center
        if (dist < BOIDS.cohRadius) {
          cohX += b.tx;
          cohY += b.ty;
          cohN++;
        }
      }

      if (cohN > 0) {
        cohX = cohX / cohN - a.tx;
        cohY = cohY / cohN - a.ty;
      }

      // Combine forces + target attraction
      const toTargetX = a.targetTX - a.tx;
      const toTargetY = a.targetTY - a.ty;
      const targetDist = Math.hypot(toTargetX, toTargetY);

      let fx = toTargetX * 0.15;  // target attraction
      let fy = toTargetY * 0.15;
      if (sepN > 0) { fx += sepX * BOIDS.sepWeight; fy += sepY * BOIDS.sepWeight; }
      if (cohN > 0) { fx += cohX * BOIDS.cohWeight; fy += cohY * BOIDS.cohWeight; }

      // Apply velocity with max speed
      a.vx = (a.vx || 0) + fx;
      a.vy = (a.vy || 0) + fy;
      const speed = Math.hypot(a.vx, a.vy);
      if (speed > BOIDS.maxSpeed) {
        a.vx = a.vx / speed * BOIDS.maxSpeed;
        a.vy = a.vy / speed * BOIDS.maxSpeed;
      }

      a.tx += a.vx;
      a.ty += a.vy;

      // Arrival: snap to target if close
      if (targetDist < 0.15) { a.tx = a.targetTX; a.ty = a.targetTY; a.vx = 0; a.vy = 0; }
    }
  }

  // ── Master draw ─────────────────────────────────────────

  _draw() {
    this._drawMap();
    this._drawOverlay();
    this._drawConversations();
    this._drawWeather();
    this._drawAgents();
  }

  // ── Map tiles ───────────────────────────────────────────

  _drawMap() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (!this.mapData) return;

    for (let y = 0; y < MAP_ROWS; y++) {
      for (let x = 0; x < MAP_COLS; x++) {
        const t = this.mapData[y][x], px = x * TILE_PX, py = y * TILE_PX;
        if (t === 0) this._grass(px, py, x, y);
        else if (t === 1 || t === 2) this._road(px, py, t, x);
        else if (t === 4) this._tree(px, py);
        else if (t === 5) this._water(px, py, x, y);
        else if (t === 6) this._walk(px, py, x);
      }
    }
    for (const loc of this.locations) this._building(loc);
  }

  _grass(x, y, gx, gy) {
    const ctx = this.ctx;
    const s = (gx * 7 + gy * 13) % 5;
    ctx.fillStyle = s < 2 ? P.grassAlt : P.grass;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    if (s === 3) { // flower
      ctx.fillStyle = P.grassFlower;
      ctx.fillRect(x + 8, y + 10, 2, 2); ctx.fillRect(x + 16, y + 6, 2, 2);
    }
    if (s === 4) { // stone
      ctx.fillStyle = P.grassStone;
      ctx.fillRect(x + 10, y + 14, 4, 3);
    }
  }

  _road(x, y, tile, gx) {
    const ctx = this.ctx;
    ctx.fillStyle = P.road;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    // Lane dashes
    if (tile === 1) {
      if (gx % 3 === 1) {
        ctx.fillStyle = P.roadLine;
        ctx.fillRect(x + TILE_PX / 2 - 1, y + 4, 2, 5);
        ctx.fillRect(x + TILE_PX / 2 - 1, y + 16, 2, 5);
      }
    } else {
      if (gx % 3 === 1) {
        ctx.fillStyle = P.roadLine;
        ctx.fillRect(x + 4, y + TILE_PX / 2 - 1, 5, 2);
        ctx.fillRect(x + 16, y + TILE_PX / 2 - 1, 5, 2);
      }
    }
    ctx.fillStyle = 'rgba(0,0,0,0.06)';
    ctx.fillRect(x, y, TILE_PX, 1);
  }

  _walk(x, y, gx) {
    const ctx = this.ctx;
    ctx.fillStyle = P.sidewalk;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    if (gx % 2 === 0) { ctx.fillStyle = P.sidewalkLine; ctx.fillRect(x + 11, y, 2, TILE_PX); }
  }

  _tree(x, y) {
    const ctx = this.ctx;
    ctx.fillStyle = P.treeTrunk;
    ctx.fillRect(x + 11, y + 17, 4, 7);
    ctx.fillStyle = 'rgba(0,0,0,0.15)';
    ctx.fillRect(x + 5, y + 20, 16, 3);
    ctx.fillStyle = P.treeCanopy;
    ctx.beginPath(); ctx.arc(x + 13, y + 11, 10, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = P.treeCanopyLt;
    ctx.beginPath(); ctx.arc(x + 8, y + 7, 6, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = P.treeCanopy;
    ctx.beginPath(); ctx.arc(x + 17, y + 6, 7, 0, Math.PI * 2); ctx.fill();
  }

  _water(x, y, gx, gy) {
    const ctx = this.ctx;
    const w = Math.sin(this._t * 0.04 + gx * 0.4 + gy * 0.4) * 0.3;
    ctx.fillStyle = P.water;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    ctx.fillStyle = P.waterShimmer;
    ctx.fillRect(x, y + 6 + w * 3, TILE_PX, 1);
    ctx.fillStyle = P.waterDeep;
    ctx.fillRect(x, y + 11 + w * 2, TILE_PX, 1);
    ctx.fillStyle = 'rgba(255,255,255,0.12)';
    ctx.fillRect(x + 5 + w, y + 9, 2, 1);
  }

  _building(loc) {
    const ctx = this.ctx;
    const bx = loc.tileX * TILE_PX - TILE_PX / 2;
    const by = loc.tileY * TILE_PX - TILE_PX / 2;
    const w = loc.width * TILE_PX;
    const h = loc.height * TILE_PX;
    const c = loc.color;

    ctx.fillStyle = P.bldgShadow;
    ctx.fillRect(bx + 3, by + 3, w, h);
    ctx.fillStyle = c;
    ctx.fillRect(bx, by, w, h);
    ctx.fillStyle = this._darken(c, 0.08);
    for (let r = 5; r < h; r += 7) ctx.fillRect(bx + 2, by + r, w - 4, 1);
    ctx.fillStyle = this._darken(c, 0.35);
    ctx.fillRect(bx - 1, by - 3, w + 2, 5);
    if (w >= 48 && h >= 36) {
      const wx = bx + w / 2 - 8, wy = by + 10;
      ctx.fillStyle = '#ffe8a0';
      ctx.fillRect(wx, wy, 16, 12);
      ctx.strokeStyle = '#3a2a1a'; ctx.lineWidth = 2;
      ctx.strokeRect(wx, wy, 16, 12);
      ctx.fillStyle = '#3a2a1a';
      ctx.fillRect(wx + 7, wy, 2, 12); ctx.fillRect(wx, wy + 5, 16, 2);
    }
    ctx.fillStyle = this._darken(c, 0.45);
    ctx.fillRect(bx + w / 2 - 5, by + h - 12, 10, 10);
    ctx.fillStyle = P.gold; ctx.fillRect(bx + w / 2 + 3, by + h - 8, 1, 1);
    ctx.strokeStyle = P.black; ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, w, h);
    const ly = Math.min(by + h + 14, this.canvas.height - 4);
    ctx.fillStyle = P.gold;
    ctx.font = '6px "Press Start 2P"';
    ctx.textAlign = 'center';
    ctx.fillText(loc.name, bx + w / 2, ly);
  }

  // ── Day/night ───────────────────────────────────────────

  _drawOverlay() {
    const h = this._worldHour;
    let ov = null;
    if (h >= 22 || h < 5) ov = P.nightOverlay;
    else if (h >= 20) ov = `rgba(25,10,30,${0.12 + (h - 20) / 2 * 0.43})`;
    else if (h < 7) ov = `rgba(30,20,30,${0.08 + (7 - h) / 2 * 0.42})`;
    if (ov) { this.ctx.fillStyle = ov; this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height); }
  }

  // ── Weather ─────────────────────────────────────────────

  _drawWeather() {
    const ctx = this.ctx;
    const rainChance = ((this._worldHour * 7) % 10) < 2;
    if (rainChance) {
      ctx.fillStyle = 'rgba(140,170,200,0.35)';
      for (const d of this._rain) {
        d.y += d.spd; d.x -= 0.6;
        if (d.y > MAP_ROWS * TILE_PX) { d.y = -d.len; d.x = Math.random() * MAP_COLS * TILE_PX; }
        ctx.fillRect(d.x, d.y, 1, d.len);
      }
    }
    if (this._worldHour < 6 || this._worldHour > 20) {
      const a = this._worldHour < 6 ? (6 - this._worldHour) / 6 : (this._worldHour - 20) / 4;
      for (const f of this._fireflies) {
        f.ph += f.spd;
        const pulse = Math.sin(f.ph) * 0.5 + 0.5;
        ctx.fillStyle = `rgba(240,240,100,${a * pulse * 0.7})`;
        ctx.fillRect(f.x - 1, f.y - 1, f.r, f.r);
      }
    }
    // Birds
    if (this._worldHour > 7 && this._worldHour < 17 && this._t % 120 < 60) {
      const bx = (this._t * 0.35) % (MAP_COLS * TILE_PX + 40) - 20;
      const by = 18 + Math.sin(this._t * 0.025) * 6;
      ctx.fillStyle = '#333';
      ctx.fillRect(bx, by, 4, 2); ctx.fillRect(bx + 7, by, 4, 2);
    }
  }

  // ── Agents ──────────────────────────────────────────────

  _drawAgents() {
    const ctx = this.ctx;
    // Diagnostic
    const n = Object.keys(this.agents).length;
    ctx.fillStyle = 'rgba(0,255,0,0.3)';
    ctx.font = '6px monospace'; ctx.textAlign = 'left';
    ctx.fillText('A:' + n, 4, this.canvas.height - 4);

    for (const [id, a] of Object.entries(this.agents)) {
      const tx = Math.round(a.tx), ty = Math.round(a.ty);
      const cx = tx * TILE_PX + TILE_PX / 2;
      const cy = ty * TILE_PX + TILE_PX / 2;
      const sel = this.selectedAgent === id;
      const hov = this.hoveredAgent === id;
      const obs = ['physicist','mathematician','mystic'].includes(id);

      // Activity state
      const trade = this._lastTrades[id];
      const trading = trade && (this._t - trade.tick) < 80;
      const chatting = this.conversations.some(c => c.participants.includes(id));
      const st = obs ? 'idle' : trading ? 'trading' : chatting ? 'chatting' : a.isMoving ? 'moving' : 'idle';
      const stC = ACTIVITY[st].color;

      // Shadow
      ctx.fillStyle = P.agentShadow;
      ctx.fillRect(cx - 7, cy + 7, 14, 4);

      // Sentiment aura (MiroFish: opinion visible as colored halo)
      const sentimentGlow = this._getMoodGlow(a.mood);
      ctx.fillStyle = sentimentGlow;
      ctx.fillRect(cx - 12, cy - 12, 24, 24);

      // Activity dot
      ctx.fillStyle = stC;
      ctx.fillRect(cx - 8, cy - 16, 4, 4);

      // Sprite
      if (obs) {
        this._drawObserverAt(ctx, cx, cy, id);
      } else {
        this._drawTraderAt(ctx, cx, cy, id, a.mood, a.color, st);
        // Trade indicator
        if (trading && trade) {
          const alpha = Math.max(0, 1 - (this._t - trade.tick) / 80);
          if (alpha > 0.1) {
            const icons = { BUY: '▲', SELL: '▼' };
            const colors = { BUY: P.green, SELL: P.red };
            if (trade.reason === 'panic_sell') {
              ctx.fillStyle = `rgba(232,72,85,${alpha})`;
              ctx.font = 'bold 11px monospace'; ctx.textAlign = 'center';
              ctx.fillText('!', cx, cy - 20);
            } else {
              ctx.fillStyle = colors[trade.dir] || P.gold;
              ctx.fillStyle = ctx.fillStyle.replace(')', `,${alpha})`).replace('rgb', 'rgba');
              ctx.font = 'bold 11px monospace'; ctx.textAlign = 'center';
              ctx.fillText(icons[trade.dir] || '$', cx, cy - 20);
            }
          }
        }
      }

      // ID label
      ctx.fillStyle = obs ? '#aaa' : P.white;
      ctx.font = obs ? '5px monospace' : 'bold 6px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(obs ? id.slice(0,4)+'..' : id, cx, cy + 14);

      // Selection ring
      if (hov || sel) {
        ctx.strokeStyle = sel ? P.gold : 'rgba(255,255,255,0.7)';
        ctx.lineWidth = sel ? 2 : 1;
        ctx.setLineDash([2, 2]);
        ctx.strokeRect(cx - 10, cy - 14, 20, 30);
        ctx.setLineDash([]);
      }
    }
  }

  _getMoodGlow(mood) {
    return {
      confident: 'rgba(78,204,163,0.35)',
      calm: 'rgba(90,158,212,0.25)',
      worried: 'rgba(240,160,64,0.35)',
      excited: 'rgba(240,200,64,0.45)',
      panicked: 'rgba(232,72,85,0.45)',
    }[mood] || 'rgba(136,136,136,0.2)';
  }

  // ── Trader sprite (Star-Office-UI style) ────────────────

  _drawTraderAt(ctx, cx, cy, id, mood, color, activity) {
    const c = this._pal(color);
    const bob = activity === 'moving' ? Math.sin(this._t * 0.25) * 2 : 0;
    const isPanic = mood === 'panicked';
    const isExcited = mood === 'excited';

    // Legs with bobbing
    ctx.fillStyle = this._darken(color, 0.25);
    ctx.fillRect(cx - 3, cy + 4 + bob, 2, 4);
    ctx.fillRect(cx + 1, cy + 4 - bob, 2, 4);
    // Feet
    ctx.fillStyle = P.black;
    ctx.fillRect(cx - 4, cy + 7, 3, 1.5);
    ctx.fillRect(cx + 1, cy + 7, 3, 1.5);

    // Body
    const bw = 8, bh = 7;
    const bx = cx - bw / 2, by = cy - 3 + bob * 0.5;
    ctx.fillStyle = c.mid;
    ctx.fillRect(bx, by, bw, bh);

    // Arms (wider when excited)
    const armSpread = isExcited ? 3 : 1;
    ctx.fillStyle = c.mid;
    ctx.fillRect(bx - armSpread, by + 1, 1, 3);
    ctx.fillRect(bx + bw + armSpread - 1, by + 1, 1, 3);

    // Head
    ctx.fillStyle = P.skinLight;
    ctx.fillRect(cx - 3, cy - 9 + bob, 6, 5);

    // Hair
    ctx.fillStyle = c.light;
    const h = [[-2,-1],[-1,-2],[0,-2],[1,-2],[2,-1]];
    for (const [hx, hy] of h) ctx.fillRect(cx + hx, cy - 9 + bob + hy, 1, 1);

    // Eyes
    ctx.fillStyle = P.black;
    ctx.fillRect(cx - 2, cy - 6 + bob, 1, 1);
    ctx.fillRect(cx + 1, cy - 6 + bob, 1, 1);

    // Mouth
    const mouths = { confident: [0,1,2], calm: [-2,2,2], worried: [0,0,1], excited: [-2,1,3], panicked: [0,2,3] };
    const m = mouths[mood] || mouths.calm;
    ctx.fillRect(cx + m[0], cy - 3 + bob + m[1], m[2], 1);

    // White outline
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(bx - 1, by - 1, bw + 2, bh + 2);
  }

  // ── Observer sprite ─────────────────────────────────────

  _drawObserverAt(ctx, cx, cy, id) {
    if (id === 'physicist') {
      ctx.fillStyle = '#3A3A5A';
      ctx.fillRect(cx - 1, cy - 3, 2, 7);
      ctx.fillStyle = '#7B9ECF';
      ctx.fillRect(cx - 3, cy - 5, 2, 3); ctx.fillRect(cx + 1, cy - 5, 2, 3);
      ctx.fillStyle = P.skinLight;
      ctx.fillRect(cx - 2, cy - 6, 4, 3);
      ctx.fillStyle = P.black;
      ctx.fillRect(cx - 1, cy - 5, 1, 1); ctx.fillRect(cx + 0, cy - 5, 1, 1);
    } else if (id === 'mathematician') {
      ctx.fillStyle = '#4A4A6A';
      ctx.fillRect(cx - 4, cy - 2, 8, 1);
      ctx.fillStyle = '#9E7BCF';
      ctx.fillRect(cx - 1, cy - 4, 2, 6);
      ctx.fillStyle = P.skinLight;
      ctx.fillRect(cx - 2, cy - 6, 4, 3);
      ctx.fillStyle = P.black;
      ctx.fillRect(cx - 1, cy - 5, 1, 1); ctx.fillRect(cx + 0, cy - 5, 1, 1);
      ctx.fillStyle = P.white;
      ctx.fillRect(cx - 2, cy - 1, 4, 1);
    } else {
      ctx.fillStyle = '#6A3A6A';
      ctx.fillRect(cx - 3, cy - 1, 6, 5);
      ctx.fillStyle = 'rgba(207,123,174,0.5)';
      ctx.beginPath(); ctx.arc(cx, cy - 2, 4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#CF7BAE';
      ctx.fillRect(cx - 1, cy - 5, 2, 4);
      ctx.fillStyle = P.skinLight;
      ctx.fillRect(cx - 2, cy - 7, 4, 3);
      ctx.fillStyle = P.black;
      ctx.fillRect(cx - 1, cy - 6, 1, 1); ctx.fillRect(cx + 0, cy - 6, 1, 1);
    }
  }

  // ── Conversations (Star-Office-UI speech bubbles) ────────

  _drawConversations() {
    const ctx = this.ctx;
    for (const conv of this.conversations) {
      const pts = [];
      for (const pid of conv.participants) {
        const a = this.agents[pid];
        if (a) pts.push({ x: a.tx * TILE_PX + TILE_PX / 2, y: a.ty * TILE_PX + TILE_PX / 2 });
      }
      if (pts.length < 2) continue;

      const mx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
      const my = pts.reduce((s, p) => s + p.y, 0) / pts.length;
      const last = conv.lines[conv.lines.length - 1];
      const text = last ? last.speaker + ': ' + last.content : '';
      const short = text.length > 24 ? text.slice(0, 22) + '..' : text;

      ctx.font = '5px monospace';
      const tw = ctx.measureText(short).width;
      const bw = Math.max(tw + 14, 50), bh = 14;
      const bx = mx - bw / 2, by = my - 34;

      ctx.fillStyle = 'rgba(16,16,32,0.92)';
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = '#445';
      ctx.lineWidth = 1;
      ctx.strokeRect(bx, by, bw, bh);
      ctx.fillStyle = 'rgba(16,16,32,0.92)';
      ctx.beginPath();
      ctx.moveTo(bx + bw / 2 - 4, by + bh);
      ctx.lineTo(bx + bw / 2, by + bh + 5);
      ctx.lineTo(bx + bw / 2 + 4, by + bh);
      ctx.fill();
      ctx.fillStyle = '#ddd';
      ctx.fillText(short, bx + 7, by + 10);
    }
  }

  // ── Interaction ─────────────────────────────────────────

  _mouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = this.canvas.width / rect.width;
    const sy = this.canvas.height / rect.height;
    const mx = (e.clientX - rect.left) * sx / TILE_PX;
    const my = (e.clientY - rect.top) * sy / TILE_PX;
    let best = null, bestD = 99;
    for (const [id, a] of Object.entries(this.agents)) {
      const d = Math.hypot(a.tx - mx, a.ty - my);
      if (d < 2 && d < bestD) { bestD = d; best = id; }
    }
    this.hoveredAgent = best;
    this.canvas.style.cursor = best ? 'pointer' : 'default';
  }

  _click(e) {
    if (this.hoveredAgent && this.onSelectAgent) {
      this.selectedAgent = this.hoveredAgent;
      this.onSelectAgent(this.hoveredAgent);
    }
  }

  // ── Helpers ─────────────────────────────────────────────

  _pal(hex) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return {
      dark: `rgb(${Math.floor(r*0.35)},${Math.floor(g*0.35)},${Math.floor(b*0.35)})`,
      mid: hex,
      light: `rgb(${Math.min(255,r+80)},${Math.min(255,g+80)},${Math.min(255,b+80)})`,
      skin: P.skinLight,
    };
  }

  _darken(hex, f) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return `rgb(${Math.floor(r*(1-f))},${Math.floor(g*(1-f))},${Math.floor(b*(1-f))})`;
  }

  _initParticles() {
    for (let i = 0; i < 30; i++) this._rain.push({
      x: Math.random() * MAP_COLS * TILE_PX, y: Math.random() * MAP_ROWS * TILE_PX,
      spd: 3 + Math.random() * 5, len: 3 + Math.random() * 4,
    });
    for (let i = 0; i < 12; i++) this._fireflies.push({
      x: Math.random() * MAP_COLS * TILE_PX, y: Math.random() * MAP_ROWS * TILE_PX,
      ph: Math.random() * Math.PI * 2, spd: 0.02 + Math.random() * 0.04, r: 2 + Math.random() * 4,
    });
  }
}
