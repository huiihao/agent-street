/**
 * Town Map — Rich pixel-art Smallville-style town with day/night cycle,
 * smooth agent movement, weather effects, and detailed tile rendering.
 *
 * References: a16z/ai-town (PixiJS pixel town), Moltcraft (isometric CSS),
 *   Stanford generative_agents (Phaser tile-map).
 */
const TILE_PX = 24;
const MAP_COLS = 20;
const MAP_ROWS = 14;

const PALETTE = {
  grass:       '#4a7a3a',
  grassLight:  '#5a8a4a',
  grassDark:   '#3a5a2a',
  road:        '#7a7a7a',
  roadLine:    '#c8c850',
  roadEdge:    '#5a5a5a',
  sidewalk:    '#9a9a9a',
  water:       '#4a8aba',
  waterLight:  '#6ab8da',
  waterDark:   '#2a5a8a',
  treeTrunk:   '#6a4a2a',
  treeLeaf:    '#3a7a3a',
  treeLeafLt:  '#4a9a4a',
  buildingShadow: 'rgba(0,0,0,0.3)',
  night:       'rgba(10,10,40,0.55)',
  evening:     'rgba(40,20,10,0.25)',
  dawn:        'rgba(60,40,20,0.15)',
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
    this._animFrame = 0;
    this._worldHour = 12;
    this._rainDrops = [];
    this._fireflies = [];
    this._initParticles();
    this._animLoop = null;

    this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
    this.canvas.addEventListener('click', (e) => this._onClick(e));
    this.canvas.addEventListener('mouseleave', () => { this.hoveredAgent = null; });
  }

  async init() {
    const resp = await fetch('/api/town');
    const data = await resp.json();
    this.mapData = data.map;
    this.locations = data.locations;
    this._startAnimLoop();
  }

  _initParticles() {
    for (let i = 0; i < 30; i++) {
      this._rainDrops.push({
        x: Math.random() * MAP_COLS * TILE_PX,
        y: Math.random() * MAP_ROWS * TILE_PX,
        speed: 3 + Math.random() * 5,
        len: 3 + Math.random() * 4,
      });
    }
    for (let i = 0; i < 12; i++) {
      this._fireflies.push({
        x: Math.random() * MAP_COLS * TILE_PX,
        y: Math.random() * MAP_ROWS * TILE_PX,
        phase: Math.random() * Math.PI * 2,
        speed: 0.02 + Math.random() * 0.04,
        radius: 2 + Math.random() * 4,
      });
    }
  }

  updateAgentStates(states) {
    states.forEach(s => {
      const prev = this.agents[s.id];
      this.agents[s.id] = {
        ...prev,
        targetX: s.tileX, targetY: s.tileY,
        tileX: prev ? prev.tileX : s.tileX,
        tileY: prev ? prev.tileY : s.tileY,
        targetTX: s.tileX, targetTY: s.tileY,
        location: s.location,
        mood: s.mood,
        color: s.color || (prev ? prev.color : '#888'),
        isMoving: s.isMoving,
      };
    });
  }

  setWorldTime(timeStr) {
    if (!timeStr) return;
    const m = timeStr.match(/(\d{2}):(\d{2})/);
    if (m) this._worldHour = parseInt(m[1]) + parseInt(m[2]) / 60;
  }

  updateConversations(convs) {
    this.conversations = convs || [];
  }

  // ── Animation loop ──────────────────────────────────────────

  _startAnimLoop() {
    const tick = () => {
      this._animFrame++;
      // Smooth agent movement (lerp toward target)
      for (const a of Object.values(this.agents)) {
        if (a.targetTX !== undefined) {
          a.tileX += (a.targetTX - a.tileX) * 0.25;
          a.tileY += (a.targetTY - a.tileY) * 0.25;
          if (Math.abs(a.targetTX - a.tileX) < 0.02) a.tileX = a.targetTX;
          if (Math.abs(a.targetTY - a.tileY) < 0.02) a.tileY = a.targetTY;
        }
      }
      // Animate particles
      for (const d of this._rainDrops) {
        d.y += d.speed;
        d.x -= 0.5;
        if (d.y > MAP_ROWS * TILE_PX) { d.y = -d.len; d.x = Math.random() * MAP_COLS * TILE_PX; }
      }
      for (const f of this._fireflies) {
        f.phase += f.speed;
        f.x += Math.sin(f.phase * 3) * 0.3;
        f.y += Math.cos(f.phase * 2) * 0.2;
      }

      this._renderFrame();
      this._animLoop = requestAnimationFrame(tick);
    };
    this._animLoop = requestAnimationFrame(tick);
  }

  renderFrame() {
    // Public render triggered by WS tick — just updates world time from data
    // The actual redraw happens continuously via requestAnimationFrame
  }

  _renderFrame() {
    this._drawMap();
    this._drawDayNightOverlay();  // darken the world first
    this._drawConversations();
    this._drawWeather();
    this._drawAgents();           // agents ALWAYS on top, full brightness
  }

  // ── Map tiles ───────────────────────────────────────────────

  _drawMap() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    if (!this.mapData) return;

    for (let y = 0; y < MAP_ROWS; y++) {
      for (let x = 0; x < MAP_COLS; x++) {
        const tile = this.mapData[y][x];
        const px = x * TILE_PX;
        const py = y * TILE_PX;

        switch (tile) {
          case 0: this._drawGrass(px, py); break;
          case 1: case 2: this._drawRoad(px, py, tile); break;
          case 4: this._drawTree(px, py); break;
          case 5: this._drawWater(px, py); break;
          case 6: this._drawSidewalk(px, py); break;
        }
      }
    }

    // Buildings on top of tiles
    for (const loc of this.locations) {
      this._drawBuilding(loc);
    }
  }

  _drawGrass(x, y) {
    const ctx = this.ctx;
    ctx.fillStyle = PALETTE.grass;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    // Random subtle grass variation
    const seed = (x * 31 + y * 17) % 7;
    if (seed === 0) ctx.fillStyle = PALETTE.grassLight;
    else if (seed === 1) ctx.fillStyle = PALETTE.grassDark;
    if (seed < 2) ctx.fillRect(x, y, TILE_PX, TILE_PX);
    // Tiny flowers
    if (seed === 3) {
      ctx.fillStyle = '#f0f050';
      ctx.fillRect(x + 6, y + 10, 2, 2);
      ctx.fillRect(x + 14, y + 6, 2, 2);
      ctx.fillStyle = '#f08080';
      ctx.fillRect(x + 16, y + 14, 2, 2);
    }
    // Stone
    if (seed === 4) {
      ctx.fillStyle = '#777';
      ctx.fillRect(x + 10, y + 12, 4, 3);
    }
  }

  _drawRoad(x, y, tile) {
    const ctx = this.ctx;
    ctx.fillStyle = PALETTE.road;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);

    // Dashed center line
    if (tile === 1) {
      // Horizontal road — vertical center line
      if (Math.floor(x / TILE_PX) % 3 === 1) {
        ctx.fillStyle = PALETTE.roadLine;
        ctx.fillRect(x + TILE_PX / 2 - 1, y + 4, 2, 4);
        ctx.fillRect(x + TILE_PX / 2 - 1, y + 16, 2, 4);
      }
    } else if (tile === 2) {
      // Vertical road — horizontal center line
      if (Math.floor(y / TILE_PX) % 3 === 1) {
        ctx.fillStyle = PALETTE.roadLine;
        ctx.fillRect(x + 4, y + TILE_PX / 2 - 1, 4, 2);
        ctx.fillRect(x + 16, y + TILE_PX / 2 - 1, 4, 2);
      }
    }
    // Edge shadow
    ctx.fillStyle = 'rgba(0,0,0,0.08)';
    ctx.fillRect(x, y, TILE_PX, 2);
    ctx.fillRect(x, y, 2, TILE_PX);
  }

  _drawSidewalk(x, y) {
    const ctx = this.ctx;
    ctx.fillStyle = PALETTE.sidewalk;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    // Grid lines
    ctx.fillStyle = '#7a7a7a';
    if (Math.floor(x / TILE_PX) % 2 === 0) {
      ctx.fillRect(x + 11, y, 2, TILE_PX);
    }
  }

  _drawTree(x, y) {
    const ctx = this.ctx;
    // Trunk
    ctx.fillStyle = PALETTE.treeTrunk;
    ctx.fillRect(x + 10, y + 18, 4, 6);
    // Leaves (clustered circles)
    ctx.fillStyle = PALETTE.treeLeaf;
    ctx.beginPath(); ctx.arc(x + 12, y + 12, 10, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = PALETTE.treeLeafLt;
    ctx.beginPath(); ctx.arc(x + 8, y + 8, 6, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = PALETTE.treeLeaf;
    ctx.beginPath(); ctx.arc(x + 16, y + 7, 7, 0, Math.PI * 2); ctx.fill();
    // Shadow under tree
    ctx.fillStyle = 'rgba(0,0,0,0.15)';
    ctx.fillRect(x + 4, y + 20, 16, 3);
  }

  _drawWater(x, y) {
    const ctx = this.ctx;
    const t = this._animFrame * 0.05;
    const shimmer = Math.sin(t + x * 0.3 + y * 0.3) * 0.3;
    const base = PALETTE.water;
    ctx.fillStyle = base;
    ctx.fillRect(x, y, TILE_PX, TILE_PX);
    // Wave highlights
    const h = 5 + shimmer * 3;
    ctx.fillStyle = PALETTE.waterLight;
    ctx.fillRect(x, y + h, TILE_PX, 1);
    ctx.fillStyle = PALETTE.waterDark;
    ctx.fillRect(x, y + h + 4, TILE_PX, 1);
    // Ripples
    ctx.fillStyle = 'rgba(255,255,255,0.15)';
    ctx.fillRect(x + 4 + shimmer * 2, y + 8, 3, 1);
    ctx.fillRect(x + 14 - shimmer * 2, y + 16, 2, 1);
  }

  // ── Buildings ───────────────────────────────────────────────

  _drawBuilding(loc) {
    const ctx = this.ctx;
    const bx = loc.tileX * TILE_PX - TILE_PX / 2;
    const by = loc.tileY * TILE_PX - TILE_PX / 2;
    const w = loc.width * TILE_PX;
    const h = loc.height * TILE_PX;

    // Shadow
    ctx.fillStyle = PALETTE.buildingShadow;
    ctx.fillRect(bx + 3, by + 3, w, h);

    // Wall
    ctx.fillStyle = loc.color;
    ctx.fillRect(bx, by, w, h);

    // Wall texture — horizontal brick lines
    ctx.fillStyle = this._darken(loc.color, 0.08);
    for (let r = 4; r < h; r += 6) {
      ctx.fillRect(bx + 2, by + r, w - 4, 1);
    }

    // Roof
    ctx.fillStyle = this._darken(loc.color, 0.35);
    ctx.fillRect(bx - 1, by - 3, w + 2, 6);
    ctx.fillStyle = this._darken(loc.color, 0.2);
    ctx.fillRect(bx, by + 2, w, 3);

    // Window (if building is big enough)
    if (w >= 48 && h >= 36) {
      const wx = bx + w / 2 - 8;
      const wy = by + h / 2 - 6;
      ctx.fillStyle = '#ffe8a0';
      ctx.fillRect(wx, wy, 16, 12);
      ctx.strokeStyle = '#3a2a1a';
      ctx.lineWidth = 2;
      ctx.strokeRect(wx, wy, 16, 12);
      // Window cross
      ctx.fillStyle = '#3a2a1a';
      ctx.fillRect(wx + 7, wy, 2, 12);
      ctx.fillRect(wx, wy + 5, 16, 2);
    }

    // Door
    const dx = bx + w / 2 - 5;
    const dy = by + h - 14;
    ctx.fillStyle = this._darken(loc.color, 0.45);
    ctx.fillRect(dx, dy, 10, 12);
    ctx.fillStyle = '#f0c040';
    ctx.fillRect(dx + 8, dy + 5, 1, 1); // doorknob

    // Outline
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, w, h);

    // Label
    const labelY = Math.min(by + h + 14, this.canvas.height - 4);
    ctx.fillStyle = '#f0c040';
    ctx.font = '6px "Press Start 2P"';
    ctx.textAlign = 'center';
    ctx.fillText(loc.name, bx + w / 2, labelY);
  }

  // ── Agents ──────────────────────────────────────────────────

  _drawAgents() {
    const ctx = this.ctx;
    // Track drawn positions to offset stacked agents
    const posCount = {};

    for (const [id, a] of Object.entries(this.agents)) {
      const tx = Math.round(a.tileX);
      const ty = Math.round(a.tileY);
      const key = `${tx},${ty}`;
      const stackIdx = posCount[key] || 0;
      posCount[key] = stackIdx + 1;

      // Offset stacked agents so they don't fully overlap
      const offX = (stackIdx % 2) * 6 - 3;
      const offY = Math.floor(stackIdx / 2) * 6 - 3;
      const cx = tx * TILE_PX + TILE_PX / 2 + offX;
      const cy = ty * TILE_PX + TILE_PX / 2 + offY;
      const isSelected = this.selectedAgent === id;
      const isHovered = this.hoveredAgent === id;

      // ── Bold colored body (10x12 px at 1:1, impossible to miss) ──
      ctx.fillStyle = a.color || '#888';
      ctx.fillRect(cx - 5, cy - 6, 10, 12);

      // Hair (darker top)
      ctx.fillStyle = this._darken(a.color || '#888', 0.4);
      ctx.fillRect(cx - 5, cy - 6, 10, 4);

      // Face (skin tone rectangle)
      ctx.fillStyle = '#F5D0A9';
      ctx.fillRect(cx - 3, cy - 1, 6, 4);

      // Eyes (two black dots)
      ctx.fillStyle = '#111';
      ctx.fillRect(cx - 2, cy, 1, 1);
      ctx.fillRect(cx + 1, cy, 1, 1);

      // Mood mouth
      const mouths = { confident: '—', calm: '–', worried: 'o', excited: 'D', panicked: '□' };
      const mouth = mouths[a.mood] || '–';
      ctx.font = '4px monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = '#111';
      ctx.fillText(mouth, cx, cy + 3);

      // ── White outline ──
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1;
      ctx.strokeRect(cx - 6, cy - 7, 12, 14);

      // ── Selection highlight ──
      if (isHovered || isSelected) {
        ctx.strokeStyle = isSelected ? '#f0c040' : 'rgba(255,255,255,0.9)';
        ctx.lineWidth = isSelected ? 3 : 1;
        ctx.strokeRect(cx - 8, cy - 9, 16, 18);
      }

      // ── Shadow ──
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(cx - 4, cy + 6, 8, 3);

      // ── ID label ──
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 6px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(id, cx, cy + 16);

      // ── Moving dots ──
      if (a.isMoving) {
        const phase = this._animFrame % 20;
        for (let i = 0; i < 3; i++) {
          ctx.fillStyle = `rgba(255,255,255,${phase > i * 6 ? 1 : 0.3})`;
          ctx.fillRect(cx - 4 + i * 4, cy + 18, 2, 2);
        }
      }
    }
  }

  _makePal(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return {
      dark: `rgb(${Math.floor(r*0.35)},${Math.floor(g*0.35)},${Math.floor(b*0.35)})`,
      mid: hex,
      light: `rgb(${Math.min(255,r+80)},${Math.min(255,g+80)},${Math.min(255,b+80)})`,
      skin: '#F5D0A9',
    };
  }

  // ── Conversations ───────────────────────────────────────────

  _drawConversations() {
    const ctx = this.ctx;
    for (const conv of this.conversations) {
      const positions = [];
      for (const pid of conv.participants) {
        const a = this.agents[pid];
        if (a) positions.push({ x: a.tileX * TILE_PX + TILE_PX / 2, y: a.tileY * TILE_PX + TILE_PX / 2 });
      }
      if (positions.length < 2) continue;

      const mx = positions.reduce((s, p) => s + p.x, 0) / positions.length;
      const my = positions.reduce((s, p) => s + p.y, 0) / positions.length;

      // Thin connection lines
      for (let i = 0; i < positions.length; i++) {
        for (let j = i + 1; j < positions.length; j++) {
          ctx.strokeStyle = 'rgba(255,240,150,0.25)';
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(positions[i].x, positions[i].y);
          ctx.lineTo(positions[j].x, positions[j].y);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      // Speech bubble
      const lastLine = conv.lines[conv.lines.length - 1];
      const text = lastLine
        ? lastLine.speaker + ': ' + lastLine.content
        : '...';
      const short = text.length > 28 ? text.slice(0, 26) + '..' : text;

      ctx.font = '5px monospace';
      const tw = ctx.measureText(short).width;
      const bw = Math.max(tw + 14, 50);
      const bh = 15;
      const bx = mx - bw / 2;
      const by = my - 38;

      // Bubble body
      ctx.fillStyle = 'rgba(20,20,40,0.92)';
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = '#556';
      ctx.lineWidth = 1;
      ctx.strokeRect(bx, by, bw, bh);
      // Bubble tail
      ctx.fillStyle = 'rgba(20,20,40,0.92)';
      ctx.beginPath();
      ctx.moveTo(bx + bw / 2 - 4, by + bh);
      ctx.lineTo(bx + bw / 2, by + bh + 5);
      ctx.lineTo(bx + bw / 2 + 4, by + bh);
      ctx.fill();
      ctx.strokeStyle = '#556';
      ctx.beginPath();
      ctx.moveTo(bx + bw / 2 - 4, by + bh);
      ctx.lineTo(bx + bw / 2, by + bh + 5);
      ctx.stroke();

      ctx.fillStyle = '#e0e0e0';
      ctx.fillText(short, bx + 7, by + 10);
    }
  }

  // ── Weather ─────────────────────────────────────────────────

  _drawWeather() {
    const ctx = this.ctx;
    const hour = this._worldHour;

    // Rain (occasional, based on world time hash)
    const rainChance = ((hour * 7) % 10) < 2 ? 1 : 0; // ~20% chance
    if (rainChance) {
      ctx.fillStyle = 'rgba(150,180,210,0.4)';
      for (const d of this._rainDrops) {
        ctx.fillRect(d.x, d.y, 1, d.len);
      }
    }

    // Fireflies at night/evening
    if (hour < 6 || hour > 20) {
      const alpha = hour < 6 ? (6 - hour) / 6 : (hour - 20) / 4;
      for (const f of this._fireflies) {
        const pulse = Math.sin(f.phase) * 0.5 + 0.5;
        const a = alpha * pulse * 0.8;
        ctx.fillStyle = `rgba(240,240,100,${a})`;
        ctx.fillRect(f.x - 1, f.y - 1, f.radius, f.radius);
      }
    }

    // Birds during day
    if (hour > 7 && hour < 17 && this._animFrame % 120 < 60) {
      const bx = (this._animFrame * 0.4) % (MAP_COLS * TILE_PX + 40) - 20;
      const by = 20 + Math.sin(this._animFrame * 0.03) * 8;
      ctx.fillStyle = '#333';
      ctx.fillRect(bx, by, 1, 2);
      ctx.fillRect(bx - 3, by + 1, 1, 1);
      ctx.fillRect(bx + 3, by + 1, 1, 1);
      ctx.fillRect(bx + 6, by, 1, 2);
      ctx.fillRect(bx + 3, by + 1, 1, 1);
      ctx.fillRect(bx + 9, by + 1, 1, 1);
    }
  }

  // ── Day/Night overlay ───────────────────────────────────────

  _drawDayNightOverlay() {
    const ctx = this.ctx;
    const h = this._worldHour;

    // Determine overlay based on time of day
    let overlay = null;
    if (h >= 22 || h < 5) {
      overlay = PALETTE.night;          // Deep night 22:00-05:00
    } else if (h >= 20) {
      const t = (h - 20) / 2;           // Evening 20:00-22:00
      overlay = `rgba(25,10,30,${0.15 + t * 0.4})`;
    } else if (h < 7) {
      const t = (7 - h) / 2;            // Dawn 05:00-07:00
      overlay = `rgba(30,20,30,${0.1 + t * 0.4})`;
    }
    // Midday: no overlay

    if (overlay) {
      ctx.fillStyle = overlay;
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }

  // ── Interaction ─────────────────────────────────────────────

  _onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = this.canvas.width / rect.width;
    const sy = this.canvas.height / rect.height;
    const mx = (e.clientX - rect.left) * sx;
    const my = (e.clientY - rect.top) * sy;
    const tx = mx / TILE_PX;
    const ty = my / TILE_PX;

    let best = null, bestDist = 99;
    for (const [id, a] of Object.entries(this.agents)) {
      const d = Math.hypot(a.tileX - tx, a.tileY - ty);
      if (d < 1.6 && d < bestDist) { bestDist = d; best = id; }
    }
    this.hoveredAgent = best;
    this.canvas.style.cursor = best ? 'pointer' : 'default';
  }

  _onClick(e) {
    if (this.hoveredAgent && this.onSelectAgent) {
      this.selectedAgent = this.hoveredAgent;
      this.onSelectAgent(this.hoveredAgent);
    }
  }

  // ── Helpers ─────────────────────────────────────────────────

  _darken(hex, f) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgb(${Math.floor(r*(1-f))},${Math.floor(g*(1-f))},${Math.floor(b*(1-f))})`;
  }

}
