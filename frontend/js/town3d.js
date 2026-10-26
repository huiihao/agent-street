// Agent Street — a low-poly, night-and-day market diorama rendered with Three.js.
//
// The 2D canvas renderer was replaced with a real 3D scene:
//   * the pixel town map becomes a textured diorama base
//   * each location becomes a procedurally built low-poly landmark
//   * agents are animated characters with boids-style separation
//   * day/night lighting, stars, rain and emissive windows are driven by the sim
//   * hover / click use raycasting; labels are DOM overlays projected each frame

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import {
  ACTIVITY_LABELS,
  MOOD_COLORS,
  clamp,
  damp,
  hashString,
  lerp,
  prefersReducedMotion,
  smoothstep,
} from './utils.js';

const MAP_W = 20;
const MAP_H = 14;
const TILE = 1;
const OBSERVERS = new Set(['physicist', 'mathematician', 'social_engineer', 'mystic']);
const OBSERVER_ICONS = { physicist: '⌬', mathematician: 'π', social_engineer: '⚙', mystic: '☾' };

// Short screen labels keep the diorama legible; the full name is the title.
const LOCATION_SHORT = {
  home_ne: 'Blue House',
  home_nw: 'Red House',
  home_se: 'Green House',
  home_sw: 'Yellow House',
  market: 'Trading Floor',
  cafe: 'Morning Brew',
  library: 'Data Library',
  square: 'Town Square',
  park: 'Willow Park',
  rumor: 'Rumor Mill',
  lab: 'Quant Lab',
  hall: 'Guild Hall',
  observatory: 'Observatory',
  math_tower: 'Math Tower',
  fortune_tent: 'Fortune Tent',
};
const LOCATION_PRIORITY = {
  market: 0, cafe: 1, library: 2, square: 3,
  observatory: 4, math_tower: 5, hall: 6, rumor: 7,
  lab: 8, park: 9, fortune_tent: 10,
  home_ne: 20, home_nw: 20, home_se: 20, home_sw: 20,
};

const PALETTE = {
  grass: '#4d7a3a',
  grassAlt: '#568442',
  grassDark: '#426b33',
  flower: '#e8d44d',
  road: '#3a4048',
  roadAlt: '#343a42',
  roadLine: '#d7b54a',
  curb: '#767e88',
  sidewalk: '#8a919a',
  sidewalkAlt: '#7e858e',
  water: '#113b50',
  waterLight: '#1c5a74',
  stone: '#4b5059',
  stoneDark: '#3d424a',
  wood: '#6b4a2f',
  trunk: '#5c3f27',
  leafA: '#2f6b39',
  leafB: '#3c7f45',
  leafC: '#4a9352',
  roofRed: '#7d3b35',
  roofBlue: '#3e4f6b',
  roofGreen: '#3d5c45',
  windowWarm: '#ffd27a',
  windowCool: '#8fd7ff',
};

const C = {
  night: new THREE.Color(0x0a1424),
  dawn: new THREE.Color(0x2b2440),
  day: new THREE.Color(0x8fb8d8),
  dusk: new THREE.Color(0xb4643f),
  rain: new THREE.Color(0x4a5566),
};

const SKY_STOPS = [
  [0, C.night],
  [5.0, C.night],
  [6.5, C.dawn],
  [8.5, C.day],
  [16.5, C.day],
  [18.5, C.dusk],
  [20.5, C.night],
  [24, C.night],
];

function tileToWorld(tx, ty) {
  return {
    x: (tx - (MAP_W - 1) / 2) * TILE,
    z: (ty - (MAP_H - 1) / 2) * TILE,
  };
}

function skyColorAt(hour) {
  for (let i = 0; i < SKY_STOPS.length - 1; i += 1) {
    const [h0, c0] = SKY_STOPS[i];
    const [h1, c1] = SKY_STOPS[i + 1];
    if (hour >= h0 && hour <= h1) {
      const t = (hour - h0) / (h1 - h0 || 1);
      return c0.clone().lerp(c1, t);
    }
  }
  return C.night.clone();
}

function makeCanvas(w, h) {
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  return canvas;
}

function canvasTexture(canvas, { repeat = false } = {}) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.anisotropy = 4;
  if (repeat) {
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
  }
  return texture;
}

function textSprite(text, { color = '#ffffff', font = '700 28px Sora, sans-serif', padding = 12 } = {}) {
  const canvas = makeCanvas(256, 128);
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.font = font;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const width = Math.min(240, ctx.measureText(text).width + padding * 2);
  ctx.fillStyle = 'rgba(6,10,20,0.55)';
  ctx.beginPath();
  ctx.roundRect((256 - width) / 2, 40, width, 48, 12);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillText(text, 128, 64);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.62, 0.31, 1);
  sprite.renderOrder = 999;
  return sprite;
}

function iconSprite(kind) {
  const canvas = makeCanvas(128, 128);
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, 128, 128);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 8;
  ctx.strokeStyle = 'rgba(5,9,16,0.8)';
  const draw = (fill, text, size = 70) => {
    ctx.font = `800 ${size}px "JetBrains Mono", monospace`;
    ctx.strokeText(text, 64, 68);
    ctx.fillStyle = fill;
    ctx.fillText(text, 64, 68);
  };
  if (kind === 'up') draw('#43d17c', '▲');
  else if (kind === 'down') draw('#ff6b6b', '▼');
  else if (kind === 'panic') draw('#ff5252', '!');
  else if (kind === 'chat') draw('#68b6ff', '…', 80);
  else if (kind === 'observer') draw('#c9a7ff', '◎');
  else if (kind === 'trade') draw('#f0c840', '$', 64);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.26, 0.26, 1);
  sprite.renderOrder = 1000;
  return sprite;
}

function radialTexture(inner = 'rgba(255,255,255,0.8)', outer = 'rgba(255,255,255,0)') {
  const canvas = makeCanvas(128, 128);
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  gradient.addColorStop(0, inner);
  gradient.addColorStop(1, outer);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export class Town3D {
  constructor(container, options = {}) {
    this.container = container;
    this.onSelectAgent = options.onSelectAgent || (() => {});
    this.onHoverAgent = options.onHoverAgent || (() => {});

    this.mapData = null;
    this.locations = [];
    this.homeAssignments = {};
    this.personaDefs = new Map();
    this.agents = new Map();
    this.hitMeshes = [];
    this.buildingLabels = [];
    this.buildingParts = [];
    this.windowMaterials = [];
    this.waterMaterials = [];
    this.lamps = [];
    this.treeTops = [];
    this.animatedRotors = [];
    this.hovered = null;
    this.selected = null;
    this.tick = 0;
    this.worldHour = 12;
    this.ambientHour = 12;
    this.ambientHourTarget = 12;
    this.lampLights = [];
    this.rain = false;
    this.time = 0;
    this._running = true;
    this._pointer = new THREE.Vector2();
    this._raycaster = new THREE.Raycaster();
    this._lastPointer = { x: 0, y: 0 };
    this._downAt = null;
    this._cameraTween = null;
    this._userInteracted = false;
    this.labelsVisible = true;
    this._baseCameraDistance = Math.hypot(14, 17.65, 21);
    this._tickerAccumulator = 0;
    this._tickerTexture = null;
    this._tickerCanvas = null;

    this._initScene();
    this._initEffects();
    this._bindEvents();
    this._resize();
    this._startIntro();
    this._animate();
  }

  // ── scene ────────────────────────────────────────────────

  _initScene() {
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(C.day.clone().getHex(), 0.012);

    this.camera = new THREE.PerspectiveCamera(34, 1, 0.1, 180);
    this.camera.position.set(14, 18, 21);

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.domElement.className = 'town-canvas-3d';
    this.container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0.35, 0);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.07;
    this.controls.minDistance = 9;
    this.controls.maxDistance = 48;
    this.controls.minPolarAngle = 0.28;
    this.controls.maxPolarAngle = 1.25;
    this.controls.screenSpacePanning = false;
    this.controls.autoRotate = false;
    this.controls.autoRotateSpeed = 0.35;
    this.controls.addEventListener('start', () => {
      this.controls.autoRotate = false;
      this._userInteracted = true;
    });

    this.hemi = new THREE.HemisphereLight(0xbfd9ff, 0x2a2a1a, 0.55);
    this.scene.add(this.hemi);

    this.ambient = new THREE.AmbientLight(0xffffff, 0.22);
    this.scene.add(this.ambient);

    this.sun = new THREE.DirectionalLight(0xffe0b0, 2.2);
    this.sun.position.set(12, 18, 8);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.camera.near = 1;
    this.sun.shadow.camera.far = 70;
    this.sun.shadow.camera.left = -16;
    this.sun.shadow.camera.right = 16;
    this.sun.shadow.camera.top = 14;
    this.sun.shadow.camera.bottom = -14;
    this.sun.shadow.bias = -0.0006;
    this.sun.shadow.normalBias = 0.02;
    this.scene.add(this.sun);

    this.moon = new THREE.DirectionalLight(0x7799ff, 0.0);
    this.moon.position.set(-12, 14, -8);
    this.scene.add(this.moon);

    this.groundGroup = new THREE.Group();
    this.buildingGroup = new THREE.Group();
    this.treeGroup = new THREE.Group();
    this.agentGroup = new THREE.Group();
    this.fxGroup = new THREE.Group();
    this.scene.add(this.groundGroup, this.buildingGroup, this.treeGroup, this.agentGroup, this.fxGroup);

    this.labelLayer = document.createElement('div');
    this.labelLayer.className = 'town-labels';
    this.container.appendChild(this.labelLayer);

    this.tip = document.createElement('div');
    this.tip.className = 'town-tip';
    this.tip.hidden = true;
    this.container.appendChild(this.tip);

    this._radial = radialTexture('rgba(255,255,255,0.9)', 'rgba(255,255,255,0)');
    this._shadowTexture = radialTexture('rgba(0,0,0,0.55)', 'rgba(0,0,0,0)');
  }

  _initEffects() {
    // Stars
    const starGeo = new THREE.BufferGeometry();
    const starPositions = [];
    for (let i = 0; i < 900; i += 1) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI * 0.46;
      const r = 46 + Math.random() * 12;
      starPositions.push(
        Math.cos(theta) * Math.sin(phi) * r,
        Math.cos(phi) * r,
        Math.sin(theta) * Math.sin(phi) * r,
      );
    }
    starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3));
    this.starMaterial = new THREE.PointsMaterial({
      color: 0xdde8ff,
      size: 0.24,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      fog: false,
      sizeAttenuation: true,
    });
    this.stars = new THREE.Points(starGeo, this.starMaterial);
    this.stars.frustumCulled = false;
    this.scene.add(this.stars);

    // Rain
    const dropCount = 520;
    const positions = new Float32Array(dropCount * 6);
    this._rainDrops = [];
    for (let i = 0; i < dropCount; i += 1) {
      const x = (Math.random() - 0.5) * (MAP_W + 6);
      const y = Math.random() * 12;
      const z = (Math.random() - 0.5) * (MAP_H + 6);
      const len = 0.18 + Math.random() * 0.22;
      this._rainDrops.push({ x, y, z, len, speed: 7 + Math.random() * 5 });
      positions.set([x, y, z, x, y - len, z], i * 6);
    }
    const rainGeo = new THREE.BufferGeometry();
    rainGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.rainMaterial = new THREE.LineBasicMaterial({
      color: 0xa8c8e8,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
    });
    this.rainLines = new THREE.LineSegments(rainGeo, this.rainMaterial);
    this.rainLines.frustumCulled = false;
    this.rainLines.visible = false;
    this.scene.add(this.rainLines);

    // Fireflies
    const fireflyPositions = [];
    this._fireflies = [];
    for (let i = 0; i < 46; i += 1) {
      const x = (Math.random() - 0.5) * (MAP_W - 2);
      const z = (Math.random() - 0.5) * (MAP_H - 2);
      fireflyPositions.push(x, 0.3 + Math.random() * 1.4, z);
      this._fireflies.push({ phase: Math.random() * Math.PI * 2, speed: 0.4 + Math.random() * 0.9, baseY: 0.3 + Math.random() * 1.4 });
    }
    const fireflyGeo = new THREE.BufferGeometry();
    fireflyGeo.setAttribute('position', new THREE.Float32BufferAttribute(fireflyPositions, 3));
    this.fireflyMaterial = new THREE.PointsMaterial({
      color: 0xf5ef8a,
      size: 0.075,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.fireflies = new THREE.Points(fireflyGeo, this.fireflyMaterial);
    this.scene.add(this.fireflies);
  }

  // ── public API ───────────────────────────────────────────

  setTownData(data) {
    if (!data) return;
    this.mapData = data.map;
    this.locations = data.locations || [];
    this.homeAssignments = data.homeAssignments || {};
    this._buildGround();
    this._buildBuildings();
    this._buildTrees();
    this._buildLocationLabels();
    this._buildAgents();
    this._spawnIdleAgents();
  }

  setPersonas(defs) {
    this.personaDefs.clear();
    (defs || []).forEach((def) => this.personaDefs.set(def.id, def));
    for (const [id, agent] of this.agents) {
      const def = this.personaDefs.get(id);
      if (def) {
        agent.def = def;
        this._applyAgentColor(agent, def.color);
      }
    }
  }

  updateFrame(frame) {
    if (!frame) return;
    this.tick = frame.tick;
    this.worldHour = frame.worldHour ?? this.worldHour;
    this.ambientHourTarget = frame.ambientHour ?? this.ambientHourTarget;
    this.rain = Boolean(frame.weather?.rain);

    const tradesByAgent = new Map();
    for (const trade of frame.trades || []) {
      tradesByAgent.set(trade.persona, trade);
    }

    for (const p of frame.personas || []) {
      let agent = this.agents.get(p.id);
      if (!agent) {
        agent = this._createAgent(p);
        this.agents.set(p.id, agent);
      }
      agent.def = this.personaDefs.get(p.id) || agent.def || p;
      agent.name = p.name;
      agent.color = p.color || agent.color;
      agent.mood = p.mood || 'calm';
      agent.activity = p.activity || 'idle';
      agent.returnPct = p.returnPct ?? 0;
      agent.equity = p.equity ?? 0;
      agent.pnl = p.pnl ?? 0;
      agent.holdings = p.holdings || [];
      agent.location = p.location || '';
      agent.signals = p.signals || {};
      agent.isObserver = Boolean(p.isObserver) || OBSERVERS.has(p.id);
      agent.targetTX = p.tileX;
      agent.targetTY = p.tileY;

      const trade = tradesByAgent.get(p.id);
      if (trade) {
        agent.lastTrade = trade;
        agent.lastTradeTick = frame.tick;
        agent.lastTradeDirection = trade.direction;
      }
      this._applyAgentColor(agent, agent.color);
      this._updateAgentLabel(agent);
    }

    this._updateTicker(frame);
  }

  resetAgentPositions() {
    const observerHomes = {
      physicist: 'observatory',
      mathematician: 'math_tower',
      social_engineer: 'hall',
      mystic: 'fortune_tent',
    };
    for (const agent of this.agents.values()) {
      const locId = agent.isObserver ? observerHomes[agent.id] : this.homeAssignments[agent.id];
      const loc = this.locations.find((item) => item.id === locId);
      const tx = loc ? loc.tileX : (MAP_W - 1) / 2;
      const ty = loc ? loc.tileY : (MAP_H - 1) / 2;
      const world = tileToWorld(tx, ty);
      agent.tx = tx;
      agent.ty = ty;
      agent.targetTX = tx;
      agent.targetTY = ty;
      agent.vx = 0;
      agent.vy = 0;
      agent.activity = 'idle';
      agent.lastTrade = null;
      agent.lastTradeTick = -100;
      agent.group.position.set(world.x, 0, world.z);
    }
    this.selected = null;
    this.hovered = null;
    for (const agent of this.agents.values()) agent.ring.visible = false;
    this.tip.hidden = true;
  }

  setSelected(id) {
    this.selected = id;
    for (const [agentId, agent] of this.agents) {
      agent.ring.visible = agentId === id;
    }
  }

  focusAgent(id) {
    const agent = this.agents.get(id);
    if (!agent) return;
    const target = new THREE.Vector3(agent.group.position.x, 0.45, agent.group.position.z);
    const offset = this.camera.position.clone().sub(this.controls.target);
    const dist = Math.min(22, Math.max(12, offset.length()));
    offset.setLength(dist);
    const toPos = target.clone().add(offset);
    toPos.y = Math.max(8, toPos.y);
    this.controls.enabled = false;
    this._userInteracted = true;
    this._cameraTween = {
      fromPos: this.camera.position.clone(),
      toPos,
      fromTarget: this.controls.target.clone(),
      toTarget: target,
      t: 0,
      duration: prefersReducedMotion() ? 0.01 : 0.85,
    };
  }

  _cameraScale() {
    const aspect = (this._width || 1) / (this._height || 1);
    if (aspect >= 2.2) return 0.80;
    if (aspect >= 1.9) return 0.88;
    if (aspect >= 1.5) return 1.0;
    if (aspect >= 1.15) return 1.12;
    if (aspect >= 0.9) return 1.38;
    return 1.55;
  }

  _defaultCameraPosition() {
    const target = new THREE.Vector3(0, 0.35, 0);
    const direction = new THREE.Vector3(14, 17.65, 21).normalize();
    return target.clone().addScaledVector(direction, this._baseCameraDistance * this._cameraScale());
  }

  _applyResponsiveFraming() {
    if (this._userInteracted || this._cameraTween) return;
    const toPos = this._defaultCameraPosition();
    const offset = toPos.clone().sub(this.controls.target);
    this.camera.position.copy(this.controls.target).add(offset);
    this.controls.update();
  }

  resetCamera() {
    const fromPos = this.camera.position.clone();
    const fromTarget = this.controls.target.clone();
    const toPos = this._defaultCameraPosition();
    const toTarget = new THREE.Vector3(0, 0.35, 0);
    this._cameraTween = {
      fromPos, toPos, fromTarget, toTarget, t: 0, duration: prefersReducedMotion() ? 0.01 : 1.1,
    };
  }

  toggleAutoRotate() {
    this.controls.autoRotate = !this.controls.autoRotate;
    return this.controls.autoRotate;
  }

  toggleLabels(force) {
    this.labelsVisible = typeof force === 'boolean' ? force : !this.labelsVisible;
    return this.labelsVisible;
  }

  dispose() {
    this._running = false;
    if (this._resizeObserver) this._resizeObserver.disconnect();
    if (this._raf) cancelAnimationFrame(this._raf);
    this.renderer.dispose();
    this.container.innerHTML = '';
  }

  // ── ground ───────────────────────────────────────────────

  _buildGround() {
    this.groundGroup.clear();
    this.waterMaterials = [];
    if (!this.mapData) return;

    const px = 32;
    const canvas = makeCanvas(MAP_W * px, MAP_H * px);
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;

    const hashAt = (x, y, salt = 0) => hashString(`${x}:${y}:${salt}`);
    const square = this.locations.find((loc) => loc.id === 'square');

    for (let y = 0; y < MAP_H; y += 1) {
      for (let x = 0; x < MAP_W; x += 1) {
        const tile = this.mapData[y]?.[x] ?? 0;
        const ox = x * px;
        const oy = y * px;
        const h = hashAt(x, y);

        if (tile === 5) {
          ctx.fillStyle = PALETTE.water;
          ctx.fillRect(ox, oy, px, px);
          ctx.fillStyle = PALETTE.waterLight;
          ctx.globalAlpha = 0.25;
          ctx.fillRect(ox + 4 + (h % 9), oy + 8 + (h % 5), 12, 2);
          ctx.fillRect(ox + 14 + (h % 7), oy + 20 + (h % 3), 9, 1);
          ctx.globalAlpha = 1;
          continue;
        }

        if (tile === 1 || tile === 2) {
          ctx.fillStyle = h % 3 === 0 ? PALETTE.roadAlt : PALETTE.road;
          ctx.fillRect(ox, oy, px, px);
          // Subtle asphalt grain.
          for (let i = 0; i < 5; i += 1) {
            const gx = (hashAt(x, y, i + 1) % (px - 2)) + 1;
            const gy = (hashAt(x, y, i + 11) % (px - 2)) + 1;
            ctx.fillStyle = i % 2 ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.08)';
            ctx.fillRect(ox + gx, oy + gy, 2, 2);
          }
          if (tile === 1) {
            ctx.fillStyle = PALETTE.curb;
            ctx.fillRect(ox, oy, px, 2);
            ctx.fillRect(ox, oy + px - 2, px, 2);
            if (x % 2 === 0) {
              ctx.fillStyle = PALETTE.roadLine;
              ctx.fillRect(ox + 3, oy + px / 2 - 1, 12, 2);
            }
          } else {
            ctx.fillStyle = PALETTE.curb;
            ctx.fillRect(ox, oy, 2, px);
            ctx.fillRect(ox + px - 2, oy, 2, px);
            if (y % 2 === 0) {
              ctx.fillStyle = PALETTE.roadLine;
              ctx.fillRect(ox + px / 2 - 1, oy + 3, 2, 12);
            }
          }
          // Zebra crossings near the three horizontal sidewalk streets.
          if ((y === 4 || y === 8 || y === 11) && (x === 5 || x === 6 || x === 11 || x === 12)) {
            ctx.fillStyle = 'rgba(235,240,245,0.7)';
            for (let i = 0; i < 4; i += 1) {
              ctx.fillRect(ox + 4 + i * 7, oy + 4, 4, px - 8);
            }
          }
          continue;
        }

        if (tile === 6) {
          ctx.fillStyle = h % 2 ? PALETTE.sidewalk : PALETTE.sidewalkAlt;
          ctx.fillRect(ox, oy, px, px);
          ctx.strokeStyle = 'rgba(40,46,54,0.35)';
          ctx.lineWidth = 1;
          ctx.strokeRect(ox + 0.5, oy + 0.5, px - 1, px - 1);
          ctx.strokeRect(ox + px / 2 + 0.5, oy + 0.5, px / 2 - 1, px / 2 - 1);
          ctx.strokeRect(ox + 0.5, oy + px / 2 + 0.5, px / 2 - 1, px / 2 - 1);
          continue;
        }

        if (tile === 3) {
          const inSquare = square && Math.abs(x - square.tileX) <= 1 && Math.abs(y - square.tileY) <= 1;
          if (inSquare) {
            ctx.fillStyle = h % 2 ? '#676b72' : '#5d6168';
            ctx.fillRect(ox, oy, px, px);
            ctx.strokeStyle = 'rgba(30,34,40,0.4)';
            ctx.strokeRect(ox + 0.5, oy + 0.5, px - 1, px - 1);
            ctx.beginPath();
            ctx.arc(ox + px / 2, oy + px / 2, px * 0.28, 0, Math.PI * 2);
            ctx.stroke();
          } else {
            ctx.fillStyle = PALETTE.stoneDark;
            ctx.fillRect(ox, oy, px, px);
            ctx.fillStyle = PALETTE.stone;
            ctx.fillRect(ox + 3, oy + 3, px - 6, px - 6);
          }
          continue;
        }

        // Grass base (also under trees).
        ctx.fillStyle = h % 4 === 0 ? PALETTE.grassAlt : PALETTE.grass;
        ctx.fillRect(ox, oy, px, px);
        for (let i = 0; i < 6; i += 1) {
          const gx = (hashAt(x, y, i + 21) % (px - 3)) + 1;
          const gy = (hashAt(x, y, i + 31) % (px - 3)) + 1;
          ctx.fillStyle = i % 3 === 0 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)';
          ctx.fillRect(ox + gx, oy + gy, 3, 2);
        }
        if (tile === 4) {
          ctx.fillStyle = 'rgba(0,0,0,0.16)';
          ctx.beginPath();
          ctx.ellipse(ox + px / 2, oy + px * 0.72, px * 0.31, px * 0.14, 0, 0, Math.PI * 2);
          ctx.fill();
        } else if (h % 17 === 0) {
          ctx.fillStyle = PALETTE.flower;
          ctx.fillRect(ox + 8 + (h % 12), oy + 16, 2, 2);
        }
      }
    }

    // Dark inset border around the diorama.
    ctx.strokeStyle = 'rgba(5,9,16,0.9)';
    ctx.lineWidth = 5;
    ctx.strokeRect(2.5, 2.5, MAP_W * px - 5, MAP_H * px - 5);
    ctx.strokeStyle = 'rgba(90,150,190,0.35)';
    ctx.lineWidth = 1;
    ctx.strokeRect(6.5, 6.5, MAP_W * px - 13, MAP_H * px - 13);

    const texture = canvasTexture(canvas);
    texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(MAP_W, MAP_H),
      new THREE.MeshStandardMaterial({ map: texture, roughness: 0.96, metalness: 0.0 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0;
    ground.receiveShadow = true;
    this.groundGroup.add(ground);

    // Diorama base: a heavy slab with a bevel-like rim.
    const base = new THREE.Mesh(
      new THREE.BoxGeometry(MAP_W + 1.6, 0.9, MAP_H + 1.6),
      new THREE.MeshStandardMaterial({ color: 0x141a26, roughness: 0.72, metalness: 0.15 }),
    );
    base.position.y = -0.47;
    base.castShadow = true;
    base.receiveShadow = true;
    this.groundGroup.add(base);

    const rim = new THREE.Mesh(
      new THREE.BoxGeometry(MAP_W + 2.0, 0.16, MAP_H + 2.0),
      new THREE.MeshStandardMaterial({ color: 0x0a101a, roughness: 0.5, metalness: 0.35 }),
    );
    rim.position.y = -0.94;
    this.groundGroup.add(rim);

    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(MAP_W + 1.6, 0.9, MAP_H + 1.6)),
      new THREE.LineBasicMaterial({ color: 0x2f5a78, transparent: true, opacity: 0.55 }),
    );
    edge.position.y = -0.47;
    this.groundGroup.add(edge);

    this._buildWater();
    this._buildStreetFurniture();
  }

  _buildWater() {
    if (!this.mapData) return;
    const seen = new Set();
    const groups = [];
    const key = (x, y) => `${x},${y}`;
    const isWater = (x, y) => this.mapData[y]?.[x] === 5;

    for (let y = 0; y < MAP_H; y += 1) {
      for (let x = 0; x < MAP_W; x += 1) {
        if (!isWater(x, y) || seen.has(key(x, y))) continue;
        const queue = [[x, y]];
        const cells = [];
        seen.add(key(x, y));
        while (queue.length) {
          const [cx, cy] = queue.pop();
          cells.push([cx, cy]);
          for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
            const nx = cx + dx;
            const ny = cy + dy;
            if (nx >= 0 && nx < MAP_W && ny >= 0 && ny < MAP_H && !seen.has(key(nx, ny)) && isWater(nx, ny)) {
              seen.add(key(nx, ny));
              queue.push([nx, ny]);
            }
          }
        }
        groups.push(cells);
      }
    }

    for (const cells of groups) {
      const xs = cells.map(([x]) => x);
      const ys = cells.map(([, y]) => y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = (maxX - minX + 1) * TILE;
      const depth = (maxY - minY + 1) * TILE;
      const center = tileToWorld((minX + maxX) / 2, (minY + maxY) / 2);

      const material = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: true,
        side: THREE.DoubleSide,
        uniforms: {
          uTime: { value: 0 },
          uDeep: { value: new THREE.Color(0x0a2c3f) },
          uShallow: { value: new THREE.Color(0x2b7c9e) },
          uSky: { value: C.day.clone() },
        },
        vertexShader: `
          uniform float uTime;
          varying vec2 vUv;
          varying float vWave;
          void main() {
            vUv = uv;
            vec3 p = position;
            float wave = sin(p.x * 3.2 + uTime * 1.3) * 0.5
                       + cos(p.y * 4.1 - uTime * 1.1) * 0.5;
            p.z += wave * 0.018;
            vWave = wave;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
          }
        `,
        fragmentShader: `
          uniform float uTime;
          uniform vec3 uDeep;
          uniform vec3 uShallow;
          uniform vec3 uSky;
          varying vec2 vUv;
          varying float vWave;
          void main() {
            float ripple = sin(vUv.x * 18.0 + uTime * 1.6) * 0.5
                         + cos(vUv.y * 22.0 - uTime * 1.2) * 0.5;
            float mixAmt = 0.45 + 0.25 * ripple + 0.15 * vWave;
            vec3 color = mix(uDeep, uShallow, clamp(mixAmt, 0.0, 1.0));
            float glint = pow(max(0.0, sin(vUv.x * 42.0 + vUv.y * 31.0 + uTime * 2.2)), 28.0);
            color += vec3(glint) * 0.55;
            color = mix(color, uSky, 0.08);
            gl_FragColor = vec4(color, 0.94);
          }
        `,
      });
      const water = new THREE.Mesh(new THREE.PlaneGeometry(width, depth, 24, 24), material);
      water.rotation.x = -Math.PI / 2;
      water.position.set(center.x, 0.026, center.z);
      water.receiveShadow = true;
      this.groundGroup.add(water);
      this.waterMaterials.push(material);

      // Stone rim around the pond.
      const rimMat = new THREE.MeshStandardMaterial({ color: 0x777d86, roughness: 0.9 });
      const rimY = 0.055;
      const rimH = 0.12;
      const t = 0.1;
      const rims = [
        [width + t * 2, t, center.x, center.z - depth / 2 - t / 2],
        [width + t * 2, t, center.x, center.z + depth / 2 + t / 2],
        [t, depth, center.x - width / 2 - t / 2, center.z],
        [t, depth, center.x + width / 2 + t / 2, center.z],
      ];
      for (const [rw, rd, rx, rz] of rims) {
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(rw, rimH, rd), rimMat);
        mesh.position.set(rx, rimY, rz);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        this.groundGroup.add(mesh);
      }

      // Lily pads.
      for (let i = 0; i < 3; i += 1) {
        const lily = new THREE.Mesh(
          new THREE.CircleGeometry(0.12 + i * 0.02, 12),
          new THREE.MeshStandardMaterial({ color: 0x3e7c4a, roughness: 0.8 }),
        );
        lily.rotation.x = -Math.PI / 2;
        lily.position.set(
          center.x + (i - 1) * 0.32,
          0.045,
          center.z + (i % 2 ? 0.24 : -0.2),
        );
        this.groundGroup.add(lily);
      }
    }
  }

  _buildStreetFurniture() {
    // Lamps at road intersections; only a few cast real light for performance.
    const lampSpots = [
      [-0.5, 4], [3.5, 4], [8.5, 4], [13.5, 4],
      [-3.5, 12], [8.5, 12], [2.5, 8], [10.5, 8],
    ];
    lampSpots.forEach(([tx, ty], index) => {
      const { x, z } = tileToWorld(tx, ty);
      const group = new THREE.Group();
      const pole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.025, 0.035, 0.82, 6),
        new THREE.MeshStandardMaterial({ color: 0x2a3038, roughness: 0.6, metalness: 0.4 }),
      );
      pole.position.y = 0.41;
      pole.castShadow = true;
      group.add(pole);
      const bulbMat = new THREE.MeshStandardMaterial({
        color: 0xffd98a,
        emissive: 0xffc35a,
        emissiveIntensity: 0.1,
        roughness: 0.4,
      });
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.075, 10, 8), bulbMat);
      bulb.position.y = 0.86;
      group.add(bulb);
      const cap = new THREE.Mesh(
        new THREE.ConeGeometry(0.1, 0.08, 8),
        new THREE.MeshStandardMaterial({ color: 0x1d232b, roughness: 0.7, metalness: 0.4 }),
      );
      cap.position.y = 0.94;
      group.add(cap);
      group.position.set(x, 0, z);
      this.groundGroup.add(group);
      this.lamps.push({ bulbMat, group });

      if (index < 5) {
        const light = new THREE.PointLight(0xffb85c, 0, 7, 2);
        light.position.set(x, 0.9, z);
        this.scene.add(light);
        this.lampLights = this.lampLights || [];
        this.lampLights.push(light);
      }
    });

    // Parked cars for scale, kept clear of the crosswalks.
    this._addCar(2.5, 4, 0x3f6f9e, 0);
    this._addCar(7.5, 4, 0x8f5b48, 0);
    this._addCar(12.5, 4, 0x9e6b3f, Math.PI);
    this._addCar(16.5, 4, 0x4d6f5a, Math.PI);
    this._buildEntrance();
    this._buildLandscaping();
  }

  _decorFree(tx, ty) {
    const x = Math.round(tx);
    const y = Math.round(ty);
    const tile = this.mapData?.[y]?.[x] ?? 0;
    return tile === 0 || tile === 6;
  }

  _addPlanter(tx, ty, flowerColor = 0xe8d44d) {
    if (!this._decorFree(tx, ty)) return;
    const { x, z } = tileToWorld(tx, ty);
    const group = new THREE.Group();
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(0.48, 0.22, 0.32),
      new THREE.MeshStandardMaterial({ color: 0x5b4430, roughness: 0.88 }),
    );
    box.position.y = 0.11;
    box.castShadow = true;
    group.add(box);
    const soil = new THREE.Mesh(
      new THREE.BoxGeometry(0.40, 0.035, 0.25),
      new THREE.MeshStandardMaterial({ color: 0x2d2118, roughness: 1 }),
    );
    soil.position.y = 0.225;
    group.add(soil);
    const shrub = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.14, 0),
      new THREE.MeshStandardMaterial({ color: 0x477f45, roughness: 0.86, flatShading: true }),
    );
    shrub.position.y = 0.33;
    shrub.castShadow = true;
    group.add(shrub);
    for (let i = 0; i < 4; i += 1) {
      const flower = new THREE.Mesh(
        new THREE.SphereGeometry(0.035, 5, 4),
        new THREE.MeshStandardMaterial({
          color: i % 2 ? flowerColor : 0xf1efe2,
          emissive: flowerColor,
          emissiveIntensity: 0.08,
          roughness: 0.65,
        }),
      );
      flower.position.set(-0.13 + i * 0.085, 0.43 + (i % 2) * 0.025, (i % 2 ? 0.05 : -0.04));
      group.add(flower);
    }
    group.position.set(x, 0, z);
    group.rotation.y = (hashString(`${tx}:${ty}:planter`) % 360) * Math.PI / 180;
    this.groundGroup.add(group);
  }

  _addBench(tx, ty, rotation = 0) {
    if (!this._decorFree(tx, ty)) return;
    const { x, z } = tileToWorld(tx, ty);
    const wood = new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.84 });
    const metal = new THREE.MeshStandardMaterial({ color: 0x303844, roughness: 0.55, metalness: 0.4 });
    const group = new THREE.Group();
    const seat = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.055, 0.22), wood);
    seat.position.y = 0.22;
    seat.castShadow = true;
    group.add(seat);
    const back = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.19, 0.045), wood);
    back.position.set(0, 0.36, -0.095);
    back.castShadow = true;
    group.add(back);
    for (const side of [-1, 1]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.22, 0.18), metal);
      leg.position.set(side * 0.24, 0.11, 0);
      group.add(leg);
    }
    group.position.set(x, 0, z);
    group.rotation.y = rotation;
    this.groundGroup.add(group);
  }

  _addRock(tx, ty, scale = 1) {
    const { x, z } = tileToWorld(tx, ty);
    const rock = new THREE.Mesh(
      new THREE.DodecahedronGeometry(0.13 * scale, 0),
      new THREE.MeshStandardMaterial({ color: 0x6f7478, roughness: 0.94, flatShading: true }),
    );
    rock.position.set(x, 0.09 * scale, z);
    rock.rotation.set(0.2, (hashString(`${tx}:${ty}`) % 360) * Math.PI / 180, -0.1);
    rock.castShadow = true;
    this.groundGroup.add(rock);
  }

  _addReeds(tx, ty) {
    const { x, z } = tileToWorld(tx, ty);
    const group = new THREE.Group();
    const stemMat = new THREE.MeshStandardMaterial({ color: 0x547c42, roughness: 0.9 });
    for (let i = 0; i < 5; i += 1) {
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.007, 0.012, 0.34, 4), stemMat);
      stem.position.set((i - 2) * 0.045, 0.17, (i % 3 - 1) * 0.05);
      stem.rotation.z = (i - 2) * 0.09;
      group.add(stem);
    }
    group.position.set(x, 0, z);
    this.groundGroup.add(group);
  }

  _addPath(tx, ty1, ty2, width = 0.3) {
    const a = tileToWorld(tx, ty1);
    const b = tileToWorld(tx, ty2);
    const length = Math.abs(b.z - a.z);
    if (length < 0.02) return;
    const path = new THREE.Mesh(
      new THREE.PlaneGeometry(width, length),
      new THREE.MeshStandardMaterial({ color: 0x8d8879, roughness: 0.96 }),
    );
    path.rotation.x = -Math.PI / 2;
    path.position.set(a.x, 0.014, (a.z + b.z) / 2);
    path.receiveShadow = true;
    this.groundGroup.add(path);
    // A darker seam makes the path read as paving rather than a floating strip.
    const seam = new THREE.Mesh(
      new THREE.PlaneGeometry(width + 0.04, length),
      new THREE.MeshBasicMaterial({ color: 0x4d514d, transparent: true, opacity: 0.35 }),
    );
    seam.rotation.x = -Math.PI / 2;
    seam.position.set(a.x, 0.008, (a.z + b.z) / 2);
    this.groundGroup.add(seam);
  }

  _addConifer(parent, x, z, scale = 1) {
    const group = new THREE.Group();
    const trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.035, 0.055, 0.3, 6),
      new THREE.MeshStandardMaterial({ color: PALETTE.trunk, roughness: 0.95 }),
    );
    trunk.position.y = 0.15;
    trunk.castShadow = true;
    group.add(trunk);
    const colors = [PALETTE.leafA, PALETTE.leafB, PALETTE.leafC];
    for (let i = 0; i < 3; i += 1) {
      const cone = new THREE.Mesh(
        new THREE.ConeGeometry(0.27 - i * 0.055, 0.32, 7),
        new THREE.MeshStandardMaterial({ color: colors[i], roughness: 0.86, flatShading: true }),
      );
      cone.position.y = 0.34 + i * 0.16;
      cone.castShadow = true;
      group.add(cone);
    }
    group.position.set(x, 0, z);
    group.scale.setScalar(scale);
    parent.add(group);
  }

  _buildEntrance() {
    // Front-right entrance: it frames the empty foreground without crowding
    // the fountain and Town Square label.
    const { x, z } = tileToWorld(15, 12.25);
    const group = new THREE.Group();
    const wood = new THREE.MeshStandardMaterial({ color: 0x5d422c, roughness: 0.86 });
    const darkWood = new THREE.MeshStandardMaterial({ color: 0x3e2b1d, roughness: 0.9 });
    for (const side of [-1, 1]) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.12, 1.12, 0.12), wood);
      post.position.set(side * 0.96, 0.56, 0);
      post.castShadow = true;
      group.add(post);
      const cap = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.12, 4), darkWood);
      cap.position.set(side * 0.96, 1.18, 0);
      group.add(cap);
      const lantern = new THREE.Mesh(
        new THREE.SphereGeometry(0.07, 8, 6),
        new THREE.MeshStandardMaterial({
          color: 0xffd88a,
          emissive: 0xffb84a,
          emissiveIntensity: 0.8,
          roughness: 0.35,
        }),
      );
      lantern.position.set(side * 0.96, 0.92, 0.09);
      group.add(lantern);
    }
    const beam = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.13, 0.14), wood);
    beam.position.y = 1.12;
    beam.castShadow = true;
    group.add(beam);
    const signCanvas = makeCanvas(512, 112);
    const sctx = signCanvas.getContext('2d');
    sctx.fillStyle = '#1a120d';
    sctx.fillRect(0, 0, 512, 112);
    sctx.strokeStyle = '#d6b36a';
    sctx.lineWidth = 5;
    sctx.strokeRect(5, 5, 502, 102);
    sctx.fillStyle = '#f3d893';
    sctx.font = '700 42px Sora, sans-serif';
    sctx.textAlign = 'center';
    sctx.textBaseline = 'middle';
    sctx.fillText('AGENT STREET', 256, 48);
    sctx.fillStyle = '#9fb5bf';
    sctx.font = '600 17px "JetBrains Mono", monospace';
    sctx.letterSpacing = '5px';
    sctx.fillText('MARKET DIORAMA', 256, 83);
    const sign = new THREE.Mesh(
      new THREE.PlaneGeometry(1.64, 0.36),
      new THREE.MeshStandardMaterial({ map: canvasTexture(signCanvas), roughness: 0.8 }),
    );
    sign.position.set(0, 0.94, 0.075);
    group.add(sign);
    group.position.set(x, 0, z);
    this.groundGroup.add(group);

    this._addPlanter(14.2, 12.25, 0xe8d44d);
    this._addPlanter(15.3, 12.25, 0xe88a8a);
    this._addPath(15, 11.05, 12.3, 0.34);
    this._addConifer(group, -1.45, 0.12, 0.72);
    this._addConifer(group, 1.45, 0.12, 0.72);
  }

  _buildLandscaping() {
    // Planters and benches read as small town furniture at the default zoom.
    this._addPlanter(7.0, 7.2, 0xe8d44d);
    this._addPlanter(13.0, 7.2, 0xe88a8a);
    this._addPlanter(4.4, 9.7, 0x9ad8ff);
    this._addPlanter(15.6, 9.7, 0xe8d44d);
    this._addPlanter(7.6, 12.7, 0xe88a8a);
    this._addPlanter(12.4, 12.7, 0x9ad8ff);
    this._addBench(4.0, 8.5, 0);
    this._addBench(16.0, 8.5, Math.PI);
    this._addBench(8.2, 10.7, Math.PI / 2);
    this._addBench(11.8, 10.7, -Math.PI / 2);
    this._addPath(5, 5.6, 7.9, 0.32);
    this._addPath(2, 10.2, 10.95, 0.32);
    // Reeds and rocks soften the pond edge.
    this._addRock(8.55, 9.1, 1.0);
    this._addRock(10.45, 9.25, 0.9);
    this._addRock(8.7, 10.55, 0.8);
    this._addRock(10.35, 10.45, 1.05);
    this._addReeds(8.75, 9.8);
    this._addReeds(10.35, 9.75);
    this._addReeds(9.25, 8.8);
    this._addReeds(10.25, 10.2);
  }

  _addCar(x, z, color, rotation) {
    const { x: wx, z: wz } = tileToWorld(x, z);
    const group = new THREE.Group();
    const bodyMat = new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: 0.25 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.14, 0.22), bodyMat);
    body.position.y = 0.12;
    body.castShadow = true;
    group.add(body);
    const cabin = new THREE.Mesh(
      new THREE.BoxGeometry(0.24, 0.12, 0.19),
      new THREE.MeshStandardMaterial({ color: 0x1a2230, roughness: 0.3, metalness: 0.5 }),
    );
    cabin.position.set(-0.02, 0.24, 0);
    cabin.castShadow = true;
    group.add(cabin);
    const wheelMat = new THREE.MeshStandardMaterial({ color: 0x111418, roughness: 0.9 });
    for (const [dx, dz] of [[-0.14, 0.11], [0.14, 0.11], [-0.14, -0.11], [0.14, -0.11]]) {
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 0.03, 8), wheelMat);
      wheel.rotation.x = Math.PI / 2;
      wheel.position.set(dx, 0.06, dz);
      group.add(wheel);
    }
    group.position.set(wx, 0, wz);
    group.rotation.y = rotation;
    this.groundGroup.add(group);
  }

  // ── buildings ────────────────────────────────────────────

  _buildBuildings() {
    this.buildingGroup.clear();
    this.windowMaterials = [];
    this.animatedRotors = [];
    for (const loc of this.locations) {
      const { x, z } = tileToWorld(loc.tileX, loc.tileY);
      const anchorZ = z + 0.35;
      let group = null;
      let labelHeight = 1.8;

      switch (loc.id) {
        case 'square':
          group = this._buildSquare(loc, x, anchorZ);
          labelHeight = 1.6;
          break;
        case 'park':
          group = this._buildPark(loc, x, anchorZ);
          labelHeight = 1.15;
          break;
        case 'market':
          group = this._buildMarket(loc, x, anchorZ);
          labelHeight = 3.2;
          break;
        case 'cafe':
          group = this._buildCafe(loc, x, anchorZ);
          labelHeight = 1.75;
          break;
        case 'library':
          group = this._buildLibrary(loc, x, anchorZ);
          labelHeight = 2.45;
          break;
        case 'observatory':
          group = this._buildObservatory(loc, x, anchorZ);
          labelHeight = 2.05;
          break;
        case 'math_tower':
          group = this._buildMathTower(loc, x, anchorZ);
          labelHeight = 3.9;
          break;
        case 'fortune_tent':
          group = this._buildTent(loc, x, anchorZ);
          labelHeight = 2.0;
          break;
        case 'rumor':
          group = this._buildRumor(loc, x, anchorZ);
          labelHeight = 1.65;
          break;
        case 'lab':
          group = this._buildLab(loc, x, anchorZ);
          labelHeight = 2.25;
          break;
        case 'hall':
          group = this._buildHall(loc, x, anchorZ);
          labelHeight = 2.2;
          break;
        default:
          group = this._buildHouse(loc, x, anchorZ);
          labelHeight = 1.75;
      }

      if (group) {
        this.buildingGroup.add(group);
        this.buildingParts.push({ id: loc.id, group, labelHeight, x, z: anchorZ });
      }
    }
  }

  _facadeMaterial(wallHex, windowHex, cols, rows, seed, options = {}) {
    const size = 128;
    const canvas = makeCanvas(size, size);
    const ctx = canvas.getContext('2d');
    const glow = makeCanvas(size, size);
    const gctx = glow.getContext('2d');
    gctx.fillStyle = '#000000';
    gctx.fillRect(0, 0, size, size);

    ctx.fillStyle = wallHex;
    ctx.fillRect(0, 0, size, size);
    // Wall grain / panel seams.
    for (let i = 0; i < 26; i += 1) {
      const y = (hashString(`${seed}:${i}`) % size);
      ctx.fillStyle = i % 2 ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.045)';
      ctx.fillRect(0, y, size, 1);
    }
    const marginX = 14;
    const marginY = 16;
    const gapX = (size - marginX * 2) / cols;
    const gapY = (size - marginY * 2) / rows;
    const winW = gapX * 0.52;
    const winH = gapY * 0.48;
    for (let row = 0; row < rows; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        const h = hashString(`${seed}:${row}:${col}`);
        const lit = h % 100 < (options.litChance ?? 58);
        const x = marginX + col * gapX + (gapX - winW) / 2;
        const y = marginY + row * gapY + (gapY - winH) / 2;
        ctx.fillStyle = options.darkWindow || '#15202c';
        ctx.fillRect(x - 1, y - 1, winW + 2, winH + 2);
        ctx.fillStyle = lit ? windowHex : (options.dark || '#1a2836');
        ctx.fillRect(x, y, winW, winH);
        ctx.strokeStyle = 'rgba(5,10,16,0.55)';
        ctx.strokeRect(x + 0.5, y + 0.5, winW - 1, winH - 1);
        if (lit) {
          gctx.fillStyle = windowHex;
          gctx.fillRect(x, y, winW, winH);
        }
      }
    }
    // Door
    if (options.door) {
      const dw = 18;
      const dh = 26;
      ctx.fillStyle = options.doorColor || '#2a1d18';
      ctx.fillRect(size / 2 - dw / 2, size - dh - 4, dw, dh);
      ctx.fillStyle = 'rgba(255,210,122,0.7)';
      ctx.fillRect(size / 2 - 1, size - dh + 3, 2, 4);
    }

    const map = canvasTexture(canvas);
    const emissiveMap = canvasTexture(glow);
    return new THREE.MeshStandardMaterial({
      map,
      emissiveMap,
      emissive: 0xffffff,
      emissiveIntensity: 0.06,
      roughness: options.roughness ?? 0.78,
      metalness: options.metalness ?? 0.05,
    });
  }

  _registerFacade(material) {
    this.windowMaterials.push(material);
    return material;
  }

  _plinth(group, w, d, height = 0.12) {
    const plinth = new THREE.Mesh(
      new THREE.BoxGeometry(w + 0.14, height, d + 0.14),
      new THREE.MeshStandardMaterial({ color: 0x5a5f68, roughness: 0.95 }),
    );
    plinth.position.y = height / 2;
    plinth.castShadow = true;
    plinth.receiveShadow = true;
    group.add(plinth);
  }

  _buildHouse(loc, x, z) {
    const group = new THREE.Group();
    const w = Math.max(0.9, (loc.width - 0.35) * TILE);
    const d = Math.max(0.8, (loc.height - 0.35) * TILE);
    const bodyH = 0.72 + (hashString(loc.id) % 18) / 100;
    const wall = loc.color || '#6B8EB5';
    const facade = this._registerFacade(this._facadeMaterial(
      wall, PALETTE.windowWarm, 2, 2, loc.id, { litChance: 68, door: true },
    ));
    this._plinth(group, w, d);
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, bodyH, d), facade);
    body.position.y = bodyH / 2 + 0.1;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const roofMat = new THREE.MeshStandardMaterial({
      color: loc.id.includes('ne') ? PALETTE.roofBlue
        : loc.id.includes('nw') ? PALETTE.roofRed
          : loc.id.includes('se') ? PALETTE.roofGreen : '#7a6334',
      roughness: 0.82,
      flatShading: true,
      side: THREE.DoubleSide,
    });
    const roofH = 0.34 + (hashString(`${loc.id}:r`) % 10) / 100;
    const roof = new THREE.Mesh(this._gableGeometry(w + 0.18, d + 0.18, roofH), roofMat);
    roof.position.y = bodyH + 0.1;
    roof.castShadow = true;
    group.add(roof);

    const chimney = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 0.26, 0.12),
      new THREE.MeshStandardMaterial({ color: 0x6b5b4d, roughness: 0.95 }),
    );
    chimney.position.set(w * 0.24, bodyH + roofH * 0.55, -d * 0.18);
    chimney.castShadow = true;
    group.add(chimney);

    // Porch
    const porch = new THREE.Mesh(
      new THREE.BoxGeometry(w * 0.46, 0.05, 0.22),
      new THREE.MeshStandardMaterial({ color: 0x5b4632, roughness: 0.9 }),
    );
    porch.position.set(0, 0.11, d / 2 + 0.12);
    porch.castShadow = true;
    group.add(porch);

    // Small bushes.
    for (const side of [-1, 1]) {
      const bush = new THREE.Mesh(
        new THREE.IcosahedronGeometry(0.12 + Math.random() * 0.04, 0),
        new THREE.MeshStandardMaterial({ color: 0x3f7a46, roughness: 0.85, flatShading: true }),
      );
      bush.position.set(side * (w * 0.38), 0.16, d / 2 + 0.18);
      bush.castShadow = true;
      group.add(bush);
    }

    group.position.set(x, 0, z);
    return group;
  }

  _gableGeometry(w, d, h) {
    const hw = w / 2;
    const hd = d / 2;
    const positions = new Float32Array([
      -hw, 0, -hd, hw, 0, -hd, -hw, 0, hd, hw, 0, hd,
      -hw, h, 0, hw, h, 0,
    ]);
    const indices = [
      2, 3, 5, 2, 5, 4,       // south slope
      1, 0, 4, 1, 4, 5,       // north slope
      0, 2, 4,                // west gable
      3, 1, 5,                // east gable
      0, 1, 3, 0, 3, 2,       // bottom
    ];
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
  }

  _buildCafe(loc, x, z) {
    const group = new THREE.Group();
    const w = Math.max(1.3, loc.width * 0.82);
    const d = Math.max(1.0, loc.height * 0.82);
    const h = 1.05;
    const facade = this._registerFacade(this._facadeMaterial(
      '#c4906b', PALETTE.windowWarm, 3, 2, 'cafe', { litChance: 82, door: true, doorColor: '#3a2418' },
    ));
    this._plinth(group, w, d);
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.1;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const roof = new THREE.Mesh(
      new THREE.BoxGeometry(w + 0.12, 0.1, d + 0.12),
      new THREE.MeshStandardMaterial({ color: 0x4a3024, roughness: 0.8 }),
    );
    roof.position.y = h + 0.15;
    roof.castShadow = true;
    group.add(roof);

    // Striped awning.
    const awningCanvas = makeCanvas(128, 64);
    const actx = awningCanvas.getContext('2d');
    for (let i = 0; i < 8; i += 1) {
      actx.fillStyle = i % 2 ? '#d8c6a2' : '#a84536';
      actx.fillRect(i * 16, 0, 16, 64);
    }
    const awningMat = new THREE.MeshStandardMaterial({ map: canvasTexture(awningCanvas), roughness: 0.85 });
    const awning = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.9, 0.26), awningMat);
    awning.position.set(0, h - 0.03, d / 2 + 0.16);
    awning.rotation.x = -0.42;
    awning.castShadow = true;
    group.add(awning);

    // Sign.
    const signCanvas = makeCanvas(256, 96);
    const sctx = signCanvas.getContext('2d');
    sctx.fillStyle = '#241812';
    sctx.fillRect(0, 0, 256, 96);
    sctx.strokeStyle = '#e8c88a';
    sctx.lineWidth = 4;
    sctx.strokeRect(4, 4, 248, 88);
    sctx.fillStyle = '#f3dba6';
    sctx.font = '700 38px Sora, sans-serif';
    sctx.textAlign = 'center';
    sctx.textBaseline = 'middle';
    sctx.fillText('MORNING BREW', 128, 49);
    const sign = new THREE.Mesh(
      new THREE.PlaneGeometry(w * 0.9, 0.34),
      new THREE.MeshStandardMaterial({ map: canvasTexture(signCanvas), roughness: 0.8 }),
    );
    sign.position.set(0, h - 0.32, d / 2 + 0.02);
    group.add(sign);

    // Outdoor tables.
    for (const [tx, tz] of [[-w * 0.38, d / 2 + 0.3], [w * 0.38, d / 2 + 0.3]]) {
      const table = new THREE.Group();
      const top = new THREE.Mesh(
        new THREE.CylinderGeometry(0.2, 0.2, 0.035, 12),
        new THREE.MeshStandardMaterial({ color: 0x7a5b3e, roughness: 0.8 }),
      );
      top.position.y = 0.34;
      top.castShadow = true;
      table.add(top);
      const leg = new THREE.Mesh(
        new THREE.CylinderGeometry(0.02, 0.02, 0.34, 6),
        new THREE.MeshStandardMaterial({ color: 0x3a2a20, roughness: 0.8 }),
      );
      leg.position.y = 0.17;
      table.add(leg);
      const umbrella = new THREE.Mesh(
        new THREE.ConeGeometry(0.32, 0.18, 8),
        new THREE.MeshStandardMaterial({ color: 0xb4513f, roughness: 0.8, flatShading: true }),
      );
      umbrella.position.y = 0.62;
      umbrella.castShadow = true;
      table.add(umbrella);
      table.position.set(tx, 0, tz);
      group.add(table);
    }

    group.position.set(x, 0, z);
    return group;
  }

  _buildLibrary(loc, x, z) {
    const group = new THREE.Group();
    const w = Math.max(1.5, loc.width * 0.86);
    const d = Math.max(1.0, loc.height * 0.86);
    const h = 1.55;
    const facade = this._registerFacade(this._facadeMaterial(
      '#8ba0b5', PALETTE.windowCool, 4, 3, 'library', { litChance: 45, door: true, doorColor: '#2b2118' },
    ));
    this._plinth(group, w, d, 0.16);
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.14;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    // Columns and pediment.
    const columnMat = new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: 0.85 });
    for (let i = 0; i < 4; i += 1) {
      const col = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.055, h * 0.78, 8), columnMat);
      col.position.set(-w * 0.36 + (i * w * 0.72) / 3, h * 0.39 + 0.14, d / 2 + 0.12);
      col.castShadow = true;
      group.add(col);
    }
    const pediment = new THREE.Mesh(
      this._gableGeometry(w * 0.86, 0.4, 0.3),
      new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: 0.85, flatShading: true, side: THREE.DoubleSide }),
    );
    pediment.position.set(0, h + 0.14, d / 2 + 0.12);
    pediment.rotation.y = 0;
    pediment.castShadow = true;
    group.add(pediment);

    const roof = new THREE.Mesh(
      new THREE.BoxGeometry(w + 0.1, 0.12, d + 0.1),
      new THREE.MeshStandardMaterial({ color: 0x5b6470, roughness: 0.8 }),
    );
    roof.position.y = h + 0.16;
    roof.castShadow = true;
    group.add(roof);

    // Steps.
    for (let i = 0; i < 3; i += 1) {
      const step = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.7 - i * 0.08, 0.05, 0.16),
        new THREE.MeshStandardMaterial({ color: 0x9a9488, roughness: 0.9 }),
      );
      step.position.set(0, 0.03 + i * 0.045, d / 2 + 0.28 - i * 0.12);
      step.receiveShadow = true;
      group.add(step);
    }

    group.position.set(x, 0, z);
    return group;
  }

  _buildMarket(loc, x, z) {
    const group = new THREE.Group();
    const w = Math.max(0.95, loc.width * 0.82);
    const d = Math.max(1.5, loc.height * 0.84);
    const h = 2.5;
    const facade = this._registerFacade(this._facadeMaterial(
      '#33475e', PALETTE.windowCool, 2, 7, 'market',
      { litChance: 78, metalness: 0.55, roughness: 0.32, darkWindow: '#0c1824' },
    ));
    this._plinth(group, w, d, 0.16);
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.14;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const band = new THREE.Mesh(
      new THREE.BoxGeometry(w + 0.08, 0.07, d + 0.08),
      new THREE.MeshStandardMaterial({
        color: 0x2ad4ff,
        emissive: 0x2ad4ff,
        emissiveIntensity: 0.8,
        roughness: 0.4,
      }),
    );
    band.position.y = h + 0.12;
    group.add(band);
    this.windowMaterials.push(band.material);

    // Holo ring above the trading floor.
    const rotor = new THREE.Group();
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.34, 0.012, 8, 40),
      new THREE.MeshBasicMaterial({ color: 0x64d8ff, transparent: true, opacity: 0.65 }),
    );
    ring.rotation.x = Math.PI / 2;
    rotor.add(ring);
    const ring2 = ring.clone();
    ring2.rotation.z = Math.PI / 3;
    ring2.scale.setScalar(0.78);
    rotor.add(ring2);
    rotor.position.y = h + 0.68;
    group.add(rotor);
    this.animatedRotors.push({ mesh: rotor, speed: 0.6 });

    // Ticker board (canvas updated from live frames).
    this._tickerCanvas = makeCanvas(512, 96);
    this._tickerTexture = canvasTexture(this._tickerCanvas);
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(w * 0.92, 0.18),
      new THREE.MeshBasicMaterial({ map: this._tickerTexture, transparent: true }),
    );
    board.position.set(0, h - 0.28, d / 2 + 0.02);
    group.add(board);

    group.position.set(x, 0, z);
    return group;
  }

  _buildObservatory(loc, x, z) {
    const group = new THREE.Group();
    const radius = Math.max(0.6, Math.min(loc.width, loc.height) * 0.38);
    const baseH = 0.95;
    this._plinth(group, radius * 2.3, radius * 2.3, 0.14);
    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(radius, radius * 1.06, baseH, 16),
      this._registerFacade(this._facadeMaterial(
        '#3a3a5a', PALETTE.windowCool, 4, 2, 'observatory', { litChance: 35 },
      )),
    );
    base.position.y = baseH / 2 + 0.12;
    base.castShadow = true;
    base.receiveShadow = true;
    group.add(base);

    const dome = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0x4b4b6e, roughness: 0.55, metalness: 0.35 }),
    );
    dome.position.y = baseH + 0.12;
    dome.castShadow = true;
    group.add(dome);

    const slit = new THREE.Mesh(
      new THREE.BoxGeometry(radius * 0.22, 0.03, radius * 1.05),
      new THREE.MeshStandardMaterial({ color: 0x0b0e1c, roughness: 0.9 }),
    );
    slit.position.set(0, baseH + radius * 0.82, 0);
    group.add(slit);

    const scope = new THREE.Mesh(
      new THREE.CylinderGeometry(0.055, 0.075, 0.9, 10),
      new THREE.MeshStandardMaterial({ color: 0x9aa4c4, roughness: 0.4, metalness: 0.6 }),
    );
    scope.position.set(0, baseH + radius + 0.12, 0.05);
    scope.rotation.x = Math.PI * 0.18;
    scope.castShadow = true;
    group.add(scope);

    const light = new THREE.PointLight(0x88a8ff, 0.8, 4, 2);
    light.position.set(0, baseH + radius + 0.3, 0);
    group.add(light);

    group.position.set(x, 0, z);
    return group;
  }

  _buildMathTower(loc, x, z) {
    const group = new THREE.Group();
    const w = 0.62;
    const d = 0.62;
    const h = 2.9;
    this._plinth(group, w + 0.3, d + 0.3, 0.18);
    const facade = this._registerFacade(this._facadeMaterial(
      '#4a4a6a', 0xb79cff, 2, 6, 'math', { litChance: 62, metalness: 0.3, roughness: 0.5 },
    ));
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.16;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const antenna = new THREE.Mesh(
      new THREE.CylinderGeometry(0.012, 0.02, 0.7, 6),
      new THREE.MeshStandardMaterial({ color: 0x9aa0b8, metalness: 0.6, roughness: 0.4 }),
    );
    antenna.position.y = h + 0.5;
    group.add(antenna);

    const orb = new THREE.Group();
    const ico = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.2, 0),
      new THREE.MeshBasicMaterial({ color: 0xb79cff, wireframe: true, transparent: true, opacity: 0.8 }),
    );
    orb.add(ico);
    const ico2 = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.13, 0),
      new THREE.MeshBasicMaterial({ color: 0x8f6cff, wireframe: true, transparent: true, opacity: 0.5 }),
    );
    orb.add(ico2);
    orb.position.y = h + 0.95;
    group.add(orb);
    this.animatedRotors.push({ mesh: orb, speed: 0.9 });

    group.position.set(x, 0, z);
    return group;
  }

  _buildTent(loc, x, z) {
    const group = new THREE.Group();
    const radius = 0.8;
    const h = 1.35;
    const canvas = makeCanvas(128, 128);
    const ctx = canvas.getContext('2d');
    for (let i = 0; i < 10; i += 1) {
      ctx.fillStyle = i % 2 ? '#d9c6a3' : '#7d3550';
      ctx.fillRect(i * 13, 0, 13, 128);
    }
    const tentMat = new THREE.MeshStandardMaterial({
      map: canvasTexture(canvas),
      roughness: 0.85,
      side: THREE.DoubleSide,
      flatShading: true,
    });
    const tent = new THREE.Mesh(new THREE.ConeGeometry(radius, h, 12, 1, true), tentMat);
    tent.position.y = h / 2 + 0.12;
    tent.castShadow = true;
    group.add(tent);

    const pole = new THREE.Mesh(
      new THREE.CylinderGeometry(0.015, 0.025, 0.55, 6),
      new THREE.MeshStandardMaterial({ color: 0x3a2a20, roughness: 0.8 }),
    );
    pole.position.y = h + 0.28;
    group.add(pole);
    const flagCanvas = makeCanvas(64, 32);
    const fctx = flagCanvas.getContext('2d');
    fctx.fillStyle = '#e0b84c';
    fctx.beginPath();
    fctx.moveTo(0, 0);
    fctx.lineTo(64, 16);
    fctx.lineTo(0, 32);
    fctx.fill();
    const flag = new THREE.Mesh(
      new THREE.PlaneGeometry(0.26, 0.14),
      new THREE.MeshStandardMaterial({ map: canvasTexture(flagCanvas), side: THREE.DoubleSide, transparent: true }),
    );
    flag.position.set(0.14, h + 0.48, 0);
    group.add(flag);

    const crystal = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.14, 0),
      new THREE.MeshStandardMaterial({
        color: 0xd78ab8, emissive: 0xd78ab8, emissiveIntensity: 0.6,
        roughness: 0.2, metalness: 0.2, transparent: true, opacity: 0.9,
      }),
    );
    crystal.position.set(0, 0.42, radius + 0.18);
    group.add(crystal);
    const table = new THREE.Mesh(
      new THREE.CylinderGeometry(0.2, 0.24, 0.1, 10),
      new THREE.MeshStandardMaterial({ color: 0x4a2f3e, roughness: 0.8 }),
    );
    table.position.set(0, 0.24, radius + 0.18);
    group.add(table);

    const lantern = new THREE.PointLight(0xff9ecb, 1.1, 4, 2);
    lantern.position.set(0, 1.1, 0);
    group.add(lantern);

    group.position.set(x, 0, z);
    return group;
  }

  _buildRumor(loc, x, z) {
    const group = new THREE.Group();
    const w = 0.92;
    const d = 0.92;
    const h = 0.78;
    this._plinth(group, w, d, 0.08);
    const facade = this._registerFacade(this._facadeMaterial(
      '#b58a5a', PALETTE.windowWarm, 2, 1, 'rumor',
      { litChance: 85, door: true, doorColor: '#3a2418' },
    ));
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.06;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);
    const roof = new THREE.Mesh(
      this._gableGeometry(w + 0.16, d + 0.16, 0.3),
      new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.82, flatShading: true, side: THREE.DoubleSide }),
    );
    roof.position.y = h + 0.06;
    roof.castShadow = true;
    group.add(roof);

    const signCanvas = makeCanvas(256, 80);
    const sctx = signCanvas.getContext('2d');
    sctx.fillStyle = '#241812';
    sctx.fillRect(0, 0, 256, 80);
    sctx.strokeStyle = '#e8c88a';
    sctx.lineWidth = 3;
    sctx.strokeRect(3, 3, 250, 74);
    sctx.fillStyle = '#f3dba6';
    sctx.font = '700 30px Sora, sans-serif';
    sctx.textAlign = 'center';
    sctx.textBaseline = 'middle';
    sctx.fillText('RUMOR MILL', 128, 41);
    const sign = new THREE.Mesh(
      new THREE.PlaneGeometry(w * 0.96, 0.26),
      new THREE.MeshStandardMaterial({ map: canvasTexture(signCanvas), roughness: 0.8 }),
    );
    sign.position.set(0, h - 0.22, d / 2 + 0.02);
    group.add(sign);

    const boardCanvas = makeCanvas(128, 160);
    const bctx = boardCanvas.getContext('2d');
    bctx.fillStyle = '#d8cbb4';
    bctx.fillRect(0, 0, 128, 160);
    bctx.fillStyle = '#241812';
    bctx.font = '700 20px "JetBrains Mono", monospace';
    bctx.textAlign = 'center';
    bctx.fillText('BULL', 64, 38);
    bctx.fillText('BEAR', 64, 118);
    bctx.fillStyle = '#8c3d32';
    bctx.fillRect(14, 52, 100, 3);
    bctx.fillRect(14, 132, 100, 3);
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(0.28, 0.34),
      new THREE.MeshStandardMaterial({ map: canvasTexture(boardCanvas), roughness: 0.9 }),
    );
    board.position.set(w * 0.36, 0.3, d / 2 + 0.26);
    board.rotation.x = -0.12;
    group.add(board);

    const antenna = new THREE.Mesh(
      new THREE.CylinderGeometry(0.012, 0.018, 0.55, 6),
      new THREE.MeshStandardMaterial({ color: 0x5b6575, metalness: 0.5, roughness: 0.4 }),
    );
    antenna.position.set(-w * 0.28, h + 0.38, 0);
    group.add(antenna);
    const beacon = new THREE.Mesh(
      new THREE.SphereGeometry(0.045, 8, 6),
      new THREE.MeshStandardMaterial({ color: 0xff5a5a, emissive: 0xff3a3a, emissiveIntensity: 0.9 }),
    );
    beacon.position.set(-w * 0.28, h + 0.67, 0);
    group.add(beacon);

    const light = new THREE.PointLight(0xffc98a, 0.9, 3.5, 2);
    light.position.set(0, h, d / 2 + 0.3);
    group.add(light);
    group.position.set(x, 0, z);
    return group;
  }

  _buildLab(loc, x, z) {
    const group = new THREE.Group();
    const w = 1.35;
    const d = 1.35;
    const h = 1.15;
    this._plinth(group, w, d, 0.12);
    const facade = this._registerFacade(this._facadeMaterial(
      '#33475e', PALETTE.windowCool, 3, 3, 'lab',
      { litChance: 82, metalness: 0.5, roughness: 0.32, darkWindow: '#0b1824' },
    ));
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.1;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const roof = new THREE.Mesh(
      new THREE.BoxGeometry(w + 0.08, 0.08, d + 0.08),
      new THREE.MeshStandardMaterial({ color: 0x1b2838, roughness: 0.6, metalness: 0.4 }),
    );
    roof.position.y = h + 0.15;
    group.add(roof);

    const signCanvas = makeCanvas(256, 80);
    const sctx = signCanvas.getContext('2d');
    sctx.fillStyle = '#07121c';
    sctx.fillRect(0, 0, 256, 80);
    sctx.strokeStyle = '#5ad1ff';
    sctx.lineWidth = 3;
    sctx.strokeRect(3, 3, 250, 74);
    sctx.fillStyle = '#8fe6ff';
    sctx.font = '700 28px "JetBrains Mono", monospace';
    sctx.textAlign = 'center';
    sctx.textBaseline = 'middle';
    sctx.fillText('QUANT LAB', 128, 41);
    const sign = new THREE.Mesh(
      new THREE.PlaneGeometry(w * 0.9, 0.22),
      new THREE.MeshBasicMaterial({ map: canvasTexture(signCanvas), transparent: true }),
    );
    sign.position.set(0, h - 0.25, d / 2 + 0.02);
    group.add(sign);

    const dishBase = new THREE.Mesh(
      new THREE.CylinderGeometry(0.02, 0.03, 0.24, 6),
      new THREE.MeshStandardMaterial({ color: 0x9aa4b4, metalness: 0.6, roughness: 0.4 }),
    );
    dishBase.position.set(w * 0.25, h + 0.32, -d * 0.2);
    group.add(dishBase);
    const dish = new THREE.Mesh(
      new THREE.SphereGeometry(0.17, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0xc9d4e6, metalness: 0.7, roughness: 0.3, side: THREE.DoubleSide }),
    );
    dish.scale.set(1, 0.45, 1);
    dish.rotation.z = Math.PI * 0.16;
    dish.position.set(w * 0.25, h + 0.47, -d * 0.2);
    group.add(dish);

    const rotor = new THREE.Group();
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.22, 0.008, 6, 28),
      new THREE.MeshBasicMaterial({ color: 0x5ad1ff, transparent: true, opacity: 0.7 }),
    );
    ring.rotation.x = Math.PI / 2;
    rotor.add(ring);
    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.08, 0),
      new THREE.MeshBasicMaterial({ color: 0x8fe6ff, wireframe: true }),
    );
    rotor.add(core);
    rotor.position.set(-w * 0.24, h + 0.48, 0);
    group.add(rotor);
    this.animatedRotors.push({ mesh: rotor, speed: 0.9 });

    const light = new THREE.PointLight(0x5ad1ff, 0.9, 4, 2);
    light.position.set(0, h + 0.2, 0);
    group.add(light);
    group.position.set(x, 0, z);
    return group;
  }

  _buildHall(loc, x, z) {
    const group = new THREE.Group();
    const w = 1.6;
    const d = 1.25;
    const h = 1.2;
    this._plinth(group, w, d, 0.14);
    const facade = this._registerFacade(this._facadeMaterial(
      '#8a7a5a', PALETTE.windowWarm, 3, 2, 'hall',
      { litChance: 55, door: true, doorColor: '#2b2118' },
    ));
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
    body.position.y = h / 2 + 0.12;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    const columnMat = new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: 0.85 });
    for (let i = 0; i < 4; i += 1) {
      const col = new THREE.Mesh(new THREE.CylinderGeometry(0.038, 0.046, h * 0.7, 8), columnMat);
      col.position.set(-w * 0.36 + (i * w * 0.72) / 3, h * 0.35 + 0.12, d / 2 + 0.1);
      col.castShadow = true;
      group.add(col);
    }
    const pediment = new THREE.Mesh(
      this._gableGeometry(w * 0.86, 0.4, 0.28),
      new THREE.MeshStandardMaterial({ color: 0xd8d2c6, roughness: 0.85, flatShading: true, side: THREE.DoubleSide }),
    );
    pediment.position.set(0, h + 0.12, d / 2 + 0.1);
    pediment.castShadow = true;
    group.add(pediment);

    const roof = new THREE.Mesh(
      new THREE.BoxGeometry(w + 0.08, 0.1, d + 0.08),
      new THREE.MeshStandardMaterial({ color: 0x5b4a38, roughness: 0.82 }),
    );
    roof.position.y = h + 0.12;
    roof.castShadow = true;
    group.add(roof);

    const clockCanvas = makeCanvas(96, 96);
    const cctx = clockCanvas.getContext('2d');
    cctx.fillStyle = '#e9e2d2';
    cctx.beginPath();
    cctx.arc(48, 48, 42, 0, Math.PI * 2);
    cctx.fill();
    cctx.strokeStyle = '#3d3328';
    cctx.lineWidth = 4;
    cctx.stroke();
    cctx.lineWidth = 3;
    cctx.beginPath();
    cctx.moveTo(48, 48);
    cctx.lineTo(48, 24);
    cctx.moveTo(48, 48);
    cctx.lineTo(66, 54);
    cctx.stroke();
    const clock = new THREE.Mesh(
      new THREE.CircleGeometry(0.13, 20),
      new THREE.MeshBasicMaterial({ map: canvasTexture(clockCanvas), transparent: true }),
    );
    clock.position.set(0, h + 0.4, d / 2 + 0.13);
    group.add(clock);

    for (let i = 0; i < 3; i += 1) {
      const step = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.62 - i * 0.06, 0.04, 0.13),
        new THREE.MeshStandardMaterial({ color: 0x9a9488, roughness: 0.9 }),
      );
      step.position.set(0, 0.03 + i * 0.04, d / 2 + 0.24 - i * 0.1);
      step.receiveShadow = true;
      group.add(step);
    }

    const light = new THREE.PointLight(0xffd49a, 0.8, 4, 2);
    light.position.set(0, h + 0.3, d / 2 + 0.3);
    group.add(light);
    group.position.set(x, 0, z);
    return group;
  }

  _buildSquare(loc, x, z) {
    const group = new THREE.Group();
    const basin = new THREE.Mesh(
      new THREE.CylinderGeometry(0.85, 0.92, 0.2, 24),
      new THREE.MeshStandardMaterial({ color: 0x8a8f99, roughness: 0.9 }),
    );
    basin.position.y = 0.1;
    basin.castShadow = true;
    basin.receiveShadow = true;
    group.add(basin);
    const water = new THREE.Mesh(
      new THREE.CircleGeometry(0.76, 24),
      new THREE.MeshStandardMaterial({
        color: 0x2f8fbf, emissive: 0x1d5c7a, emissiveIntensity: 0.35,
        roughness: 0.2, metalness: 0.1, transparent: true, opacity: 0.9,
      }),
    );
    water.rotation.x = -Math.PI / 2;
    water.position.y = 0.21;
    group.add(water);
    const column = new THREE.Mesh(
      new THREE.CylinderGeometry(0.1, 0.14, 0.7, 12),
      new THREE.MeshStandardMaterial({ color: 0x9a9fa8, roughness: 0.8 }),
    );
    column.position.y = 0.45;
    column.castShadow = true;
    group.add(column);
    const bowl = new THREE.Mesh(
      new THREE.CylinderGeometry(0.36, 0.22, 0.12, 16),
      new THREE.MeshStandardMaterial({ color: 0x9a9fa8, roughness: 0.8 }),
    );
    bowl.position.y = 0.83;
    bowl.castShadow = true;
    group.add(bowl);
    const orb = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 12, 10),
      new THREE.MeshStandardMaterial({
        color: 0x8fd7ff, emissive: 0x4aa8d8, emissiveIntensity: 0.8, roughness: 0.2,
      }),
    );
    orb.position.y = 1.0;
    group.add(orb);

    // Benches around the fountain.
    const benchMat = new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.85 });
    for (let i = 0; i < 4; i += 1) {
      const angle = (i / 4) * Math.PI * 2 + Math.PI / 4;
      const bench = new THREE.Group();
      const seat = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.05, 0.16), benchMat);
      seat.position.y = 0.2;
      seat.castShadow = true;
      bench.add(seat);
      for (const side of [-1, 1]) {
        const leg = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.2, 0.14), benchMat);
        leg.position.set(side * 0.22, 0.1, 0);
        bench.add(leg);
      }
      bench.position.set(Math.cos(angle) * 1.35, 0, Math.sin(angle) * 1.35);
      bench.rotation.y = -angle + Math.PI / 2;
      group.add(bench);
    }

    group.position.set(x, 0, z);
    return group;
  }

  _buildPark(loc, x, z) {
    const group = new THREE.Group();
    // A small wooden dock at the pond edge and a gazebo under the willows.
    const wood = new THREE.MeshStandardMaterial({ color: PALETTE.wood, roughness: 0.85 });
    const dock = new THREE.Group();
    for (let i = 0; i < 5; i += 1) {
      const plank = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.04, 0.12), wood);
      plank.position.set(0, 0.06, -0.4 + i * 0.18);
      plank.castShadow = true;
      dock.add(plank);
    }
    for (const [px, pz] of [[-0.5, -0.4], [0.5, -0.4], [-0.5, 0.32], [0.5, 0.32]]) {
      const post = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.28, 6), wood);
      post.position.set(px, 0.14, pz);
      dock.add(post);
    }
    dock.position.set(0.1, 0, 0.1);
    group.add(dock);

    // Gazebo.
    const gazebo = new THREE.Group();
    const floor = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.08, 8), wood);
    floor.position.y = 0.06;
    floor.receiveShadow = true;
    gazebo.add(floor);
    for (let i = 0; i < 4; i += 1) {
      const angle = (i / 4) * Math.PI * 2 + Math.PI / 4;
      const post = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.032, 0.8, 6), wood);
      post.position.set(Math.cos(angle) * 0.45, 0.48, Math.sin(angle) * 0.45);
      post.castShadow = true;
      gazebo.add(post);
    }
    const roof = new THREE.Mesh(
      new THREE.ConeGeometry(0.62, 0.34, 8),
      new THREE.MeshStandardMaterial({ color: 0x4f6b4a, roughness: 0.8, flatShading: true }),
    );
    roof.position.y = 1.0;
    roof.castShadow = true;
    gazebo.add(roof);
    gazebo.position.set(-1.0, 0, -0.7);
    group.add(gazebo);

    group.position.set(x, 0, z);
    return group;
  }

  // ── trees & labels ───────────────────────────────────────

  _buildTrees() {
    this.treeGroup.clear();
    this.treeTops = [];
    if (!this.mapData) return;

    const placeTree = (tx, ty, scale = 1) => {
      const { x, z } = tileToWorld(tx, ty);
      const jitterX = ((hashString(`${tx}:${ty}:x`) % 100) / 100 - 0.5) * 0.4;
      const jitterZ = ((hashString(`${tx}:${ty}:z`) % 100) / 100 - 0.5) * 0.4;
      const group = new THREE.Group();
      const trunk = new THREE.Mesh(
        new THREE.CylinderGeometry(0.035, 0.06, 0.34, 6),
        new THREE.MeshStandardMaterial({ color: PALETTE.trunk, roughness: 0.95 }),
      );
      trunk.position.y = 0.17;
      trunk.castShadow = true;
      group.add(trunk);
      const canopy = new THREE.Group();
      const colors = [PALETTE.leafA, PALETTE.leafB, PALETTE.leafC];
      for (let i = 0; i < 3; i += 1) {
        const cone = new THREE.Mesh(
          new THREE.ConeGeometry(0.3 - i * 0.06, 0.34, 7, 1),
          new THREE.MeshStandardMaterial({ color: colors[i], roughness: 0.85, flatShading: true }),
        );
        cone.position.y = 0.36 + i * 0.18;
        cone.castShadow = true;
        canopy.add(cone);
      }
      group.add(canopy);
      group.position.set(x + jitterX, 0, z + jitterZ);
      group.rotation.y = (hashString(`${tx}:${ty}:r`) % 360) * (Math.PI / 180);
      const s = scale * (0.85 + (hashString(`${tx}:${ty}:s`) % 35) / 100);
      group.scale.setScalar(s);
      this.treeGroup.add(group);
      this.treeTops.push({ canopy, phase: Math.random() * Math.PI * 2 });
    };

    for (let y = 0; y < MAP_H; y += 1) {
      for (let x = 0; x < MAP_W; x += 1) {
        if (this.mapData[y]?.[x] === 4) placeTree(x, y);
      }
    }
    // Extra greenery around the park.
    const park = this.locations.find((loc) => loc.id === 'park');
    if (park) {
      for (const [dx, dy] of [[-2, -1], [2, -1], [-2, 1], [2, 1], [-1.5, 0.5]]) {
        placeTree(park.tileX + dx, park.tileY + dy, 0.9);
      }
    }

    // Flower patches: instanced tiny blooms on free grass tiles.
    const bloomGeo = new THREE.SphereGeometry(0.035, 4, 4);
    const bloomColors = [0xe8d44d, 0xe88a8a, 0x9ad8ff];
    const freeTiles = [];
    for (let y = 1; y < MAP_H - 1; y += 1) {
      for (let x = 1; x < MAP_W - 1; x += 1) {
        if (this.mapData[y]?.[x] === 0 && hashString(`${x}:${y}:f`) % 9 === 0) freeTiles.push([x, y]);
      }
    }
    bloomColors.forEach((color, index) => {
      const count = Math.min(14, Math.floor(freeTiles.length / 3));
      const mesh = new THREE.InstancedMesh(
        bloomGeo,
        new THREE.MeshStandardMaterial({ color, roughness: 0.7, emissive: color, emissiveIntensity: 0.05 }),
        count,
      );
      const dummy = new THREE.Object3D();
      for (let i = 0; i < count; i += 1) {
        const [tx, ty] = freeTiles[(i * 3 + index * 5) % freeTiles.length];
        const { x, z } = tileToWorld(tx, ty);
        dummy.position.set(x + ((i % 5) - 2) * 0.06, 0.05, z + ((i % 3) - 1) * 0.06);
        dummy.scale.setScalar(0.8 + (i % 3) * 0.2);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
      }
      this.treeGroup.add(mesh);
    });
  }

  _buildLocationLabels() {
    for (const entry of this.buildingLabels) {
      entry.el.remove();
    }
    this.buildingLabels = [];
    for (const loc of this.locations) {
      const el = document.createElement('div');
      el.className = 'town-label town-label--loc';
      el.title = loc.name;
      const icon = document.createElement('span');
      icon.className = 'town-label-icon';
      icon.textContent = loc.icon || '•';
      const label = document.createElement('span');
      label.textContent = LOCATION_SHORT[loc.id] || loc.name;
      el.append(icon, label);
      this.labelLayer.appendChild(el);
      const anchor = this.buildingParts.find((part) => part.id === loc.id);
      const world = new THREE.Vector3(
        anchor ? anchor.x : tileToWorld(loc.tileX, loc.tileY).x,
        anchor ? anchor.labelHeight : 1.2,
        anchor ? anchor.z : tileToWorld(loc.tileX, loc.tileY).z,
      );
      this.buildingLabels.push({
        id: loc.id,
        el,
        world,
        width: Math.max(54, el.offsetWidth || 76),
        height: Math.max(12, el.offsetHeight || 14),
        priority: LOCATION_PRIORITY[loc.id] ?? 15,
      });
    }
  }

  // ── agents ───────────────────────────────────────────────

  _buildAgents() {
    for (const [id, agent] of this.agents) {
      agent.group.removeFromParent();
      agent.labelEl?.remove();
    }
    this.agents.clear();
    this.hitMeshes = [];
  }

  _spawnIdleAgents() {
    if (!this.personaDefs.size) return;
    for (const [id, def] of this.personaDefs) {
      if (this.agents.has(id)) continue;
      const persona = {
        id,
        name: def.name || id,
        color: def.color,
        isObserver: OBSERVERS.has(id),
        mood: 'calm',
        tileX: 10,
        tileY: 7,
      };
      const agent = this._createAgent(persona);
      this.agents.set(id, agent);
    }
    this.resetAgentPositions();
  }

  _createAgent(persona) {
    const isObserver = Boolean(persona.isObserver) || OBSERVERS.has(persona.id);
    const color = persona.color || '#8a94a6';
    const bodyMat = new THREE.MeshStandardMaterial({ color, roughness: 0.68, metalness: 0.05 });
    const skinMat = new THREE.MeshStandardMaterial({ color: 0xf0c9a8, roughness: 0.75 });
    const darkMat = new THREE.MeshStandardMaterial({ color: 0x1b2230, roughness: 0.85 });
    const hairMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(color).multiplyScalar(0.55), roughness: 0.9 });

    const group = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.105, 0.12, 4, 8), bodyMat);
    body.position.y = 0.33;
    body.castShadow = true;
    group.add(body);

    const head = new THREE.Mesh(new THREE.SphereGeometry(0.105, 16, 12), skinMat);
    head.position.y = 0.55;
    head.castShadow = true;
    group.add(head);

    const hair = new THREE.Mesh(
      new THREE.SphereGeometry(0.108, 16, 12, 0, Math.PI * 2, 0, Math.PI * 0.58),
      hairMat,
    );
    hair.position.y = 0.57;
    hair.rotation.x = -0.12;
    group.add(hair);

    const eyeMat = new THREE.MeshBasicMaterial({ color: 0x141821 });
    for (const dx of [-0.035, 0.035]) {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(0.012, 6, 6), eyeMat);
      eye.position.set(dx, 0.555, 0.1);
      group.add(eye);
    }

    const legs = [];
    for (const dx of [-0.055, 0.055]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.16, 0.06), darkMat);
      leg.position.set(dx, 0.1, 0);
      leg.castShadow = true;
      group.add(leg);
      legs.push(leg);
    }

    const haloMat = new THREE.SpriteMaterial({
      map: this._radial,
      color: MOOD_COLORS[persona.mood] || MOOD_COLORS.calm,
      transparent: true,
      opacity: 0.26,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const halo = new THREE.Sprite(haloMat);
    halo.scale.set(0.55, 0.55, 1);
    halo.position.y = 0.08;
    group.add(halo);

    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(0.42, 0.42),
      new THREE.MeshBasicMaterial({
        map: this._shadowTexture, transparent: true, opacity: 0.5, depthWrite: false,
      }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.012;
    group.add(shadow);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.2, 0.245, 28),
      new THREE.MeshBasicMaterial({ color: 0xf0c840, transparent: true, opacity: 0.9, side: THREE.DoubleSide }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.02;
    ring.visible = false;
    group.add(ring);

    // Invisible pick volume — easier to hit than a tiny head.
    const hit = new THREE.Mesh(
      new THREE.CylinderGeometry(0.22, 0.22, 0.78, 8),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
    );
    hit.position.y = 0.38;
    hit.userData.agentId = persona.id;
    group.add(hit);
    this.hitMeshes.push(hit);

    const icons = {
      up: iconSprite('up'),
      down: iconSprite('down'),
      chat: iconSprite('chat'),
      panic: iconSprite('panic'),
      observer: iconSprite('observer'),
      trade: iconSprite('trade'),
    };
    const icon = new THREE.Group();
    for (const sprite of Object.values(icons)) {
      sprite.visible = false;
      sprite.position.y = 0.92;
      icon.add(sprite);
    }
    group.add(icon);

    const labelEl = document.createElement('div');
    labelEl.className = `town-label town-label--agent${isObserver ? ' is-observer' : ''}`;
    const dot = document.createElement('span');
    dot.className = 'town-dot';
    dot.style.background = color;
    const text = document.createElement('span');
    text.textContent = isObserver ? OBSERVER_ICONS[persona.id] || persona.id : persona.id;
    labelEl.append(dot, text);
    this.labelLayer.appendChild(labelEl);

    const fallback = this.locations.find((loc) => loc.id === (
      persona.id === 'physicist' ? 'observatory'
        : persona.id === 'mathematician' ? 'math_tower'
          : persona.id === 'social_engineer' ? 'hall'
            : persona.id === 'mystic' ? 'fortune_tent' : 'square'
    ));
    const startTile = fallback
      ? { x: fallback.tileX, y: fallback.tileY }
      : { x: MAP_W / 2, y: MAP_H / 2 };
    const start = tileToWorld(startTile.x, startTile.y);

    const agent = {
      id: persona.id,
      def: this.personaDefs.get(persona.id) || persona,
      name: persona.name || persona.id,
      color,
      group,
      body,
      bodyMat,
      head,
      hair,
      hairMat,
      legs,
      halo,
      haloMat,
      ring,
      hit,
      icons,
      icon,
      labelEl,
      isObserver,
      tx: startTile.x,
      ty: startTile.y,
      targetTX: startTile.x,
      targetTY: startTile.y,
      offsetX: isObserver ? 0 : Math.cos((hashString(persona.id) % 360) * Math.PI / 180) * 0.42,
      offsetY: isObserver ? 0 : Math.sin((hashString(persona.id) % 360) * Math.PI / 180) * 0.32,
      vx: 0,
      vy: 0,
      phase: Math.random() * Math.PI * 2,
      activity: 'idle',
      mood: 'calm',
      lastTrade: null,
      lastTradeTick: -100,
      lastTradeDirection: null,
      returnPct: 0,
      equity: 0,
      location: '',
      holdings: [],
      signals: {},
      selected: false,
    };
    group.position.set(start.x, 0, start.z);
    this.agentGroup.add(group);
    return agent;
  }

  _applyAgentColor(agent, color) {
    if (!color || agent.color === color && agent.appliedColor === color) return;
    agent.appliedColor = color;
    agent.bodyMat.color.set(color);
    agent.hairMat.color.set(new THREE.Color(color).multiplyScalar(0.55));
    const dot = agent.labelEl?.querySelector('.town-dot');
    if (dot) dot.style.background = color;
  }

  _updateAgentLabel(agent) {
    const text = agent.labelEl?.querySelector('span:last-child');
    if (text) text.textContent = agent.isObserver
      ? (OBSERVER_ICONS[agent.id] || agent.name)
      : agent.id;
    agent.haloMat.color.set(MOOD_COLORS[agent.mood] || MOOD_COLORS.calm);
  }

  _updateAgents(dt) {
    const list = [...this.agents.values()];
    for (const agent of list) {
      let pushX = 0;
      let pushY = 0;
      for (const other of list) {
        if (other === agent) continue;
        const dx = agent.tx - other.tx;
        const dy = agent.ty - other.ty;
        const dist = Math.hypot(dx, dy);
        if (dist > 0.001 && dist < 0.92) {
          const force = (0.92 - dist) * 3.8;
          pushX += (dx / dist) * force;
          pushY += (dy / dist) * force;
        }
      }

      const targetX = agent.isObserver ? agent.targetTX : agent.targetTX + agent.offsetX;
      const targetY = agent.isObserver ? agent.targetTY : agent.targetTY + agent.offsetY;
      const dx = targetX - agent.tx;
      const dy = targetY - agent.ty;
      const dist = Math.hypot(dx, dy);
      let desiredX = dx * 3.4 + pushX;
      let desiredY = dy * 3.4 + pushY;
      const speed = Math.hypot(desiredX, desiredY);
      if (speed > 2.4) {
        desiredX = (desiredX / speed) * 2.4;
        desiredY = (desiredY / speed) * 2.4;
      }
      agent.vx = damp(agent.vx, desiredX, 7, dt);
      agent.vy = damp(agent.vy, desiredY, 7, dt);
      agent.tx += agent.vx * dt;
      agent.ty += agent.vy * dt;
      if (dist < 0.035) {
        agent.tx = targetX;
        agent.ty = targetY;
      }
      agent.tx = clamp(agent.tx, 0, MAP_W - 1);
      agent.ty = clamp(agent.ty, 0, MAP_H - 1);

      const world = tileToWorld(agent.tx, agent.ty);
      const moving = Math.hypot(agent.vx, agent.vy) > 0.08;
      let y = 0;
      if (moving) {
        y = Math.abs(Math.sin(this.time * 9 + agent.phase)) * 0.035;
      } else {
        y = Math.sin(this.time * 1.7 + agent.phase) * 0.006;
      }
      if (agent.activity === 'panicking') {
        y += Math.sin(this.time * 22 + agent.phase) * 0.012;
      }
      agent.group.position.set(world.x, y, world.z);

      if (moving) {
        const targetRot = Math.atan2(agent.vx, agent.vy);
        agent.group.rotation.y = dampAngle(agent.group.rotation.y, targetRot, 8, dt);
      }
      for (let i = 0; i < agent.legs.length; i += 1) {
        const leg = agent.legs[i];
        if (moving) {
          leg.rotation.x = Math.sin(this.time * 12 + agent.phase + (i ? Math.PI : 0)) * 0.6;
        } else {
          leg.rotation.x = damp(leg.rotation.x, 0, 10, dt);
        }
      }
      agent.body.rotation.z = moving ? Math.sin(this.time * 9 + agent.phase) * 0.04 : 0;

      // Icon choice.
      const currentTick = this.tick;
      const tradedRecently = currentTick - agent.lastTradeTick <= 2;
      const show = {
        up: tradedRecently && agent.lastTradeDirection === 'BUY' && agent.activity !== 'panicking',
        down: tradedRecently && agent.lastTradeDirection === 'SELL' && agent.activity !== 'panicking',
        chat: agent.activity === 'chatting',
        panic: agent.activity === 'panicking',
        observer: agent.isObserver,
        trade: false,
      };
      for (const [kind, sprite] of Object.entries(agent.icons)) {
        sprite.visible = Boolean(show[kind]);
      }
      const activeIcon = agent.icons.up.visible ? agent.icons.up
        : agent.icons.down.visible ? agent.icons.down
          : agent.icons.panic.visible ? agent.icons.panic
            : agent.icons.chat.visible ? agent.icons.chat
              : agent.icons.observer.visible ? agent.icons.observer : null;
      if (activeIcon) {
        activeIcon.position.y = 0.9 + Math.sin(this.time * 4 + agent.phase) * 0.03;
        const pulse = 1 + Math.sin(this.time * 6 + agent.phase) * 0.08;
        activeIcon.scale.set(0.26 * pulse, 0.26 * pulse, 1);
      }

      agent.haloMat.opacity = agent.activity === 'panicking' ? 0.42 : 0.24;
      const scaleTarget = this.hovered === agent.id || this.selected === agent.id ? 1.08 : 1;
      const s = damp(agent.group.scale.x, scaleTarget, 10, dt);
      agent.group.scale.setScalar(s);
      if (agent.ring.visible) {
        agent.ring.material.opacity = 0.55 + Math.sin(this.time * 4) * 0.25;
        agent.ring.rotation.z += dt * 0.6;
      }
      agent.visible = true;
    }
  }

  _updateLabels() {
    const width = this._width;
    const height = this._height;
    if (!width || !height) return;
    const v = new THREE.Vector3();

    // Agent labels are intentionally transient: the scene stays readable when
    // 20 traders are present, and hovering/selecting reveals the identity.
    for (const agent of this.agents.values()) {
      const active = this.labelsVisible && (
        this.hovered === agent.id || this.selected === agent.id
      );
      if (!active) {
        agent.labelEl.style.opacity = '0';
        continue;
      }
      v.set(agent.group.position.x, agent.group.position.y + 0.78, agent.group.position.z);
      v.project(this.camera);
      const visible = v.z < 1 && Math.abs(v.x) < 1.15 && Math.abs(v.y) < 1.15;
      if (!visible) {
        agent.labelEl.style.opacity = '0';
        continue;
      }
      const x = clamp((v.x * 0.5 + 0.5) * width, 24, width - 24);
      const y = (-v.y * 0.5 + 0.5) * height;
      agent.labelEl.style.opacity = '1';
      agent.labelEl.style.transform = `translate(-50%, -100%) translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    }

    if (!this.labelsVisible) {
      for (const entry of this.buildingLabels) entry.el.style.opacity = '0';
      return;
    }

    const projected = [];
    for (const entry of this.buildingLabels) {
      v.copy(entry.world);
      v.project(this.camera);
      const visible = v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1;
      if (!visible) {
        entry.el.style.opacity = '0';
        continue;
      }
      projected.push({
        entry,
        x: (v.x * 0.5 + 0.5) * width,
        y: (-v.y * 0.5 + 0.5) * height,
      });
    }

    // Place landmarks first; houses only get a slot if one remains. Candidate
    // offsets keep the label near its roof while resolving the dense north row.
    projected.sort((a, b) => (
      a.entry.priority - b.entry.priority || a.y - b.y
    ));
    const placed = [];
    const offsets = [
      [0, 0], [0, -16], [0, -32], [0, -48],
      [-14, -16], [14, -16], [0, 16], [-14, 16],
      [14, 16], [0, -64], [-28, -32], [28, -32],
      [0, -80], [0, 32],
    ];
    for (const item of projected) {
      const entry = item.entry;
      const halfWidth = entry.width / 2;
      let chosen = null;
      for (const [dx, dy] of offsets) {
        const x = clamp(item.x + dx, halfWidth + 8, width - halfWidth - 8);
        const y = clamp(item.y + dy, 12, height - 8);
        const collides = placed.some((other) => (
          Math.abs(other.x - x) < (other.width + entry.width) / 2 + 4
          && Math.abs(other.y - y) < (other.height + entry.height) / 2 + 4
        ));
        if (!collides) {
          chosen = { x, y };
          break;
        }
      }
      if (!chosen) {
        entry.el.style.opacity = '0';
        continue;
      }
      placed.push({ ...chosen, width: entry.width, height: entry.height });
      entry.el.style.opacity = entry.priority >= 20 ? '0.54' : '0.80';
      entry.el.style.transform = `translate(-50%, -100%) translate(${chosen.x.toFixed(1)}px, ${chosen.y.toFixed(1)}px)`;
    }
  }

  // ── environment ──────────────────────────────────────────

  _updateEnvironment(dt) {
    this.ambientHour = damp(this.ambientHour, this.ambientHourTarget ?? this.ambientHour, 3, dt);
    const hour = this.ambientHour;
    const sky = skyColorAt(hour);
    const daylight = smoothstep(5.6, 7.6, hour) * (1 - smoothstep(17.2, 19.4, hour));
    const night = 1 - daylight;

    if (this.rain) {
      sky.lerp(C.rain, 0.35);
    }
    this.scene.fog.color.copy(sky);
    this.scene.fog.density = 0.008 + (this.rain ? 0.006 : 0.002) + night * 0.003;

    const sunAngle = clamp((hour - 6) / 12, 0, 1);
    const sunX = Math.cos(sunAngle * Math.PI) * 16;
    const sunY = Math.max(1.5, Math.sin(sunAngle * Math.PI) * 20);
    const sunZ = -6 + sunAngle * 8;
    this.sun.position.set(sunX, sunY, sunZ);
    this.sun.intensity = (0.06 + 2.4 * daylight) * (this.rain ? 0.72 : 1);
    const warm = smoothstep(0.35, 0.0, Math.abs(sunAngle - 0.5));
    this.sun.color.setRGB(1.0, lerp(0.86, 0.94, warm), lerp(0.68, 0.86, warm));

    this.hemi.intensity = 0.44 + 0.46 * daylight;
    this.ambient.intensity = 0.44 + 0.16 * daylight;
    this.ambient.color.setRGB(
      lerp(0.56, 1.0, daylight),
      lerp(0.66, 1.0, daylight),
      lerp(0.98, 1.0, daylight),
    );
    this.moon.intensity = 1.15 * night;
    this.starMaterial.opacity = Math.pow(night, 1.6) * 0.95;
    this.stars.rotation.y += dt * 0.002;
    this.fireflyMaterial.opacity = night * (this.rain ? 0.25 : 0.8);

    const winGlow = 0.06 + 1.9 * night + (this.rain ? 0.15 : 0);
    for (const mat of this.windowMaterials) {
      if (mat.emissiveIntensity !== undefined) mat.emissiveIntensity = winGlow;
    }
    const lampIntensity = 4.6 * night + 0.2;
    for (const light of this.lampLights || []) light.intensity = lampIntensity;
    for (const { bulbMat } of this.lamps) bulbMat.emissiveIntensity = 0.12 + night * 1.4;

    for (const water of this.waterMaterials) {
      water.uniforms.uTime.value = this.time;
      water.uniforms.uSky.value.copy(sky);
    }
    for (const rotor of this.animatedRotors) {
      rotor.mesh.rotation.y += dt * rotor.speed;
    }
    for (const tree of this.treeTops) {
      tree.canopy.rotation.z = Math.sin(this.time * 0.8 + tree.phase) * 0.018;
    }

    // Fireflies drift.
    const positions = this.fireflies.geometry.attributes.position;
    for (let i = 0; i < this._fireflies.length; i += 1) {
      const f = this._fireflies[i];
      positions.setY(i, f.baseY + Math.sin(this.time * f.speed + f.phase) * 0.18);
    }
    positions.needsUpdate = true;

    const skyTop = sky.clone().multiplyScalar(0.52);
    const skyMid = sky.clone().multiplyScalar(0.82);
    const skyBottom = sky.clone().lerp(new THREE.Color(0xffffff), 0.22);
    const skyKey = `${skyTop.getHexString()}|${skyMid.getHexString()}|${skyBottom.getHexString()}|${night > 0.5}`;
    if (skyKey !== this._skyKey) {
      this._skyKey = skyKey;
      this.container.style.setProperty('--sky-top', `#${skyTop.getHexString()}`);
      this.container.style.setProperty('--sky-mid', `#${skyMid.getHexString()}`);
      this.container.style.setProperty('--sky-bottom', `#${skyBottom.getHexString()}`);
      this.container.style.setProperty('--sky-glow', night > 0.5 ? 'rgba(120, 165, 235, 0.12)' : 'rgba(255, 238, 205, 0.18)');
    }

    this.renderer.toneMappingExposure = 1.00 + daylight * 0.10;
    this._updateRain(dt, night);
  }

  _updateRain(dt, night) {
    this.rainLines.visible = this.rain;
    if (!this.rain) return;
    const positions = this.rainLines.geometry.attributes.position;
    for (let i = 0; i < this._rainDrops.length; i += 1) {
      const drop = this._rainDrops[i];
      drop.y -= drop.speed * dt;
      drop.x -= dt * 0.6;
      if (drop.y < 0) {
        drop.y = 11 + Math.random() * 3;
        drop.x = (Math.random() - 0.5) * (MAP_W + 6);
        drop.z = (Math.random() - 0.5) * (MAP_H + 6);
      }
      positions.setXYZ(i * 2, drop.x, drop.y, drop.z);
      positions.setXYZ(i * 2 + 1, drop.x, drop.y - drop.len, drop.z);
    }
    positions.needsUpdate = true;
    this.rainMaterial.opacity = 0.2 + 0.25 * (1 - night * 0.3);
  }

  _updateTicker(frame) {
    if (!this._tickerTexture || !this._tickerCanvas) return;
    this._tickerAccumulator += 1;
    if (this._tickerAccumulator < 20) return;
    this._tickerAccumulator = 0;
    const ctx = this._tickerCanvas.getContext('2d');
    const w = this._tickerCanvas.width;
    const h = this._tickerCanvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(4,10,20,0.82)';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#2ad4ff';
    ctx.font = '700 22px "JetBrains Mono", monospace';
    ctx.textBaseline = 'middle';
    ctx.fillText('LIVE', 12, h / 2);
    let x = 78;
    const prices = frame.prices || {};
    const changes = frame.changes || {};
    for (const [symbol, price] of Object.entries(prices)) {
      const change = changes[symbol] || 0;
      ctx.fillStyle = change >= 0 ? '#43d17c' : '#ff6b6b';
      const text = `${symbol} ${price >= 1000 ? price.toFixed(1) : price.toFixed(2)} ${change >= 0 ? '▲' : '▼'}${Math.abs(change * 100).toFixed(2)}%`;
      ctx.fillText(text, x, h / 2);
      x += ctx.measureText(text).width + 26;
      if (x > w - 60) break;
    }
    this._tickerTexture.needsUpdate = true;
  }

  // ── interaction & camera ─────────────────────────────────

  _bindEvents() {
    this._onPointerMove = (event) => this._pointerMove(event);
    this._onPointerDown = (event) => {
      this._downAt = { x: event.clientX, y: event.clientY };
    };
    this._onPointerUp = (event) => this._pointerUp(event);
    this._onPointerLeave = () => this._clearHover();
    this.renderer.domElement.addEventListener('pointermove', this._onPointerMove);
    this.renderer.domElement.addEventListener('pointerdown', this._onPointerDown);
    this.renderer.domElement.addEventListener('pointerup', this._onPointerUp);
    this.renderer.domElement.addEventListener('pointerleave', this._onPointerLeave);

    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(this.container);
    window.addEventListener('resize', () => this._resize());
  }

  _resize() {
    const rect = this.container.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    if (width === this._width && height === this._height) return;
    this._width = width;
    this._height = height;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(width, height, false);
    this._applyResponsiveFraming();
  }

  _raycast(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this._pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this._pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this._raycaster.setFromCamera(this._pointer, this.camera);
    const hits = this._raycaster.intersectObjects(this.hitMeshes, false);
    if (!hits.length) return null;
    return hits[0].object.userData.agentId || null;
  }

  _pointerMove(event) {
    this._lastPointer = { x: event.clientX, y: event.clientY };
    const id = this._raycast(event);
    if (id !== this.hovered) {
      this.hovered = id;
      this.renderer.domElement.style.cursor = id ? 'pointer' : 'grab';
      this.onHoverAgent(id);
      if (!id) this._clearHover();
    }
    if (id) this._showTip(id, event);
  }

  _pointerUp(event) {
    if (!this._downAt) return;
    const moved = Math.hypot(event.clientX - this._downAt.x, event.clientY - this._downAt.y);
    this._downAt = null;
    if (moved > 5) return;
    const id = this._raycast(event);
    if (id) {
      this.setSelected(id);
      this.onSelectAgent(id);
    } else {
      this.setSelected(null);
      this.onSelectAgent(null);
    }
  }

  _clearHover() {
    this.hovered = null;
    this.tip.hidden = true;
    this.renderer.domElement.style.cursor = 'grab';
    this.onHoverAgent(null);
  }

  _showTip(id, event) {
    const agent = this.agents.get(id);
    if (!agent) return;
    const rect = this.container.getBoundingClientRect();
    const x = clamp(event.clientX - rect.left + 16, 8, rect.width - 220);
    const y = clamp(event.clientY - rect.top + 16, 8, rect.height - 110);
    this.tip.style.transform = `translate(${x}px, ${y}px)`;

    const pnl = agent.returnPct || 0;
    this.tip.replaceChildren();
    const head = document.createElement('div');
    head.className = 'town-tip-head';
    const dot = document.createElement('span');
    dot.className = 'town-dot';
    dot.style.background = agent.color;
    const title = document.createElement('strong');
    title.textContent = agent.isObserver ? agent.name : `${agent.id} · ${agent.name}`;
    head.append(dot, title);
    const meta = document.createElement('div');
    meta.className = 'town-tip-meta';
    meta.textContent = `${ACTIVITY_LABELS[agent.activity] || agent.activity} · ${agent.location || 'Agent Street'}`;
    const row = document.createElement('div');
    row.className = 'town-tip-row';
    const equity = document.createElement('span');
    equity.textContent = `Equity ${agent.equity ? `$${agent.equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '—'}`;
    const ret = document.createElement('span');
    ret.className = pnl >= 0 ? 'pos' : 'neg';
    ret.textContent = `${pnl >= 0 ? '+' : ''}${(pnl * 100).toFixed(2)}%`;
    row.append(equity, ret);
    this.tip.append(head, meta, row);
    this.tip.hidden = false;
  }

  _startIntro() {
    if (prefersReducedMotion()) {
      this.camera.position.set(14, 18, 21);
      return;
    }
    this.controls.enabled = false;
    const toPos = this._defaultCameraPosition();
    this._cameraTween = {
      fromPos: toPos.clone().multiplyScalar(1.35),
      toPos,
      fromTarget: new THREE.Vector3(0, 0, 0),
      toTarget: new THREE.Vector3(0, 0.35, 0),
      t: 0,
      duration: 2.2,
    };
  }

  _updateCameraTween(dt) {
    if (!this._cameraTween) return;
    const tween = this._cameraTween;
    tween.t += dt;
    const raw = clamp(tween.t / tween.duration, 0, 1);
    const t = raw < 0.5 ? 4 * raw ** 3 : 1 - (-2 * raw + 2) ** 3 / 2;
    this.camera.position.lerpVectors(tween.fromPos, tween.toPos, t);
    this.controls.target.lerpVectors(tween.fromTarget, tween.toTarget, t);
    if (raw >= 1) {
      this._cameraTween = null;
      this.controls.enabled = true;
      this.controls.update();
    }
  }

  // ── loop ─────────────────────────────────────────────────

  _animate() {
    if (!this._running) return;
    this._raf = requestAnimationFrame(() => this._animate());
    const dt = Math.min(0.05, this._clockDelta());
    if (document.hidden) return;
    this.time += dt;
    this._updateEnvironment(dt);
    this._updateAgents(dt);
    this._updateCameraTween(dt);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this._updateLabels();
  }

  _clockDelta() {
    if (!this._clock) {
      this._clock = new THREE.Clock();
      return 0.016;
    }
    return this._clock.getDelta();
  }
}

function dampAngle(current, target, lambda, dt) {
  let delta = target - current;
  while (delta > Math.PI) delta -= Math.PI * 2;
  while (delta < -Math.PI) delta += Math.PI * 2;
  return current + delta * (1 - Math.exp(-lambda * dt));
}
