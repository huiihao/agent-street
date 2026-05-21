// Town Map — pixel-art Smallville-style town with sprite-based agents

const TILE_PX = 24;
const MAP_COLS = 20;
const MAP_ROWS = 14;
const SPRITE_SCALE = 2; // drawn at 2x => 32px sprites

const TILE_COLORS = {
    0: '#3a5a3a',  // grass
    1: '#6b6b6b',  // road horizontal
    2: '#6b6b6b',  // road vertical
    3: null,        // building (rendered separately)
    4: '#2a4a2a',  // tree
    5: '#3a6a8a',  // water
    6: '#8a8a8a',  // sidewalk
};

class TownMap {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.ctx.imageSmoothingEnabled = false;
        this.mapData = null;
        this.locations = [];
        this.homeAssignments = {};
        this.agents = {};     // id -> {tileX, tileY, location, mood, color, isMoving}
        this.conversations = [];
        this.hoveredAgent = null;
        this.selectedAgent = null;
        this.onSelectAgent = null;

        this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
        this.canvas.addEventListener('click', (e) => this._onClick(e));
        this.canvas.addEventListener('mouseleave', () => { this.hoveredAgent = null; });
    }

    async init() {
        const resp = await fetch('/api/town');
        const data = await resp.json();
        this.mapData = data.map;
        this.locations = data.locations;
        this.homeAssignments = data.homeAssignments;
        this.renderFrame();
    }

    updateAgentStates(states) {
        states.forEach(s => {
            const existing = this.agents[s.id] || {};
            this.agents[s.id] = {
                ...existing,
                tileX: s.tileX,
                tileY: s.tileY,
                location: s.location,
                mood: s.mood,
                color: s.color || existing.color || '#888',
                isMoving: s.isMoving,
            };
        });
    }

    updateConversations(convs) {
        this.conversations = convs || [];
    }

    // ---- Drawing ----

    renderFrame() {
        this._drawMap();
        this._drawConversations();
        this._drawAgents();
    }

    _drawMap() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (!this.mapData) return;

        // Tiles
        for (let y = 0; y < MAP_ROWS; y++) {
            for (let x = 0; x < MAP_COLS; x++) {
                const tile = this.mapData[y][x];
                const color = TILE_COLORS[tile];
                if (color) {
                    ctx.fillStyle = color;
                    ctx.fillRect(x * TILE_PX, y * TILE_PX, TILE_PX, TILE_PX);
                }

                // Trees
                if (tile === 4) {
                    ctx.fillStyle = '#4a7a3a';
                    const cx = x * TILE_PX + TILE_PX / 2;
                    const cy = y * TILE_PX + TILE_PX / 2 - 2;
                    ctx.beginPath();
                    ctx.arc(cx, cy, TILE_PX / 3, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.fillStyle = '#5a3a1a';
                    ctx.fillRect(cx - 1, cy + TILE_PX / 4, 2, TILE_PX / 4);
                }

                // Water ripples
                if (tile === 5) {
                    ctx.fillStyle = 'rgba(80,160,200,0.3)';
                    for (let i = 0; i < 3; i++) {
                        ctx.fillRect(x * TILE_PX + 4 + i * 6, y * TILE_PX + 6 + (i % 2) * 6, 4, 2);
                    }
                }

                // Grid overlay
                ctx.strokeStyle = 'rgba(0,0,0,0.12)';
                ctx.lineWidth = 0.5;
                ctx.strokeRect(x * TILE_PX, y * TILE_PX, TILE_PX, TILE_PX);
            }
        }

        // Buildings
        this.locations.forEach(loc => {
            const px = loc.tileX * TILE_PX - TILE_PX / 2;
            const py = loc.tileY * TILE_PX - TILE_PX / 2;
            const w = loc.width * TILE_PX;
            const h = loc.height * TILE_PX;

            ctx.fillStyle = loc.color;
            ctx.fillRect(px, py, w, h);
            ctx.fillStyle = this._darken(loc.color, 0.35);
            ctx.fillRect(px, py, w, 5);
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            ctx.strokeRect(px, py, w, h);

            // Label — ensure on-screen
            const labelY = Math.min(py + h + 12, this.canvas.height - 4);
            ctx.fillStyle = '#f0c040';
            ctx.font = '6px "Press Start 2P"';
            ctx.textAlign = 'center';
            ctx.fillText(loc.name, px + w / 2, labelY);
        });
    }

    _drawAgents() {
        const ctx = this.ctx;
        for (const [id, agent] of Object.entries(this.agents)) {
            const cx = agent.tileX * TILE_PX + TILE_PX / 2;
            const cy = agent.tileY * TILE_PX + TILE_PX / 2;

            // Pixel art sprite (centered at cx, cy)
            const spriteX = cx - 8 * SPRITE_SCALE / 2;
            const spriteY = cy - 8 * SPRITE_SCALE / 2;

            ctx.save();
            const seed = this._seedFromId(id);
            const mood = agent.mood || 'calm';
            const color = agent.color || '#888';

            // Draw procedural pixel sprite
            this._drawMiniSprite(ctx, spriteX, spriteY, mood, color, seed, SPRITE_SCALE);
            ctx.restore();

            // Mood glow ring
            const glowColors = {
                confident: 'rgba(78,204,163,0.45)',
                calm: 'rgba(107,174,214,0.35)',
                worried: 'rgba(240,160,64,0.45)',
                excited: 'rgba(240,192,64,0.55)',
                panicked: 'rgba(233,69,96,0.55)',
            };
            ctx.strokeStyle = glowColors[mood] || 'rgba(136,136,136,0.3)';
            ctx.lineWidth = 2;
            ctx.strokeRect(spriteX - 3, spriteY - 3, 8 * SPRITE_SCALE + 6, 8 * SPRITE_SCALE + 6);

            // Select/hover highlight
            if (this.hoveredAgent === id || this.selectedAgent === id) {
                ctx.strokeStyle = this.selectedAgent === id ? '#f0c040' : '#fff';
                ctx.lineWidth = 2;
                ctx.strokeRect(spriteX - 5, spriteY - 5, 8 * SPRITE_SCALE + 10, 8 * SPRITE_SCALE + 10);
            }

            // ID label below sprite
            ctx.fillStyle = '#fff';
            ctx.font = '5px "Press Start 2P"';
            ctx.textAlign = 'center';
            ctx.fillText(id, cx, spriteY + 8 * SPRITE_SCALE + 12);

            // Moving indicator dots
            if (agent.isMoving) {
                ctx.fillStyle = '#fff';
                for (let i = -3; i <= 3; i += 3) {
                    ctx.fillRect(cx + i, spriteY + 8 * SPRITE_SCALE + 16, 2, 2);
                }
            }
        }
    }

    _drawMiniSprite(ctx, x, y, mood, color, seed, scale) {
        // Build a compact 8x8 sprite representing the agent
        const palette = this._makePalette(color);
        const face = this._facePattern(mood);

        for (let row = 0; row < 8; row++) {
            for (let col = 0; col < 8; col++) {
                let fill = null;

                // Hair (top 3 rows, varied by seed)
                if (row < 3 && col >= 1 && col <= 6) {
                    fill = palette.dark;
                    if ((seed + row + col) % 4 === 0) fill = palette.mid;
                }
                // Face (rows 3-5)
                if (row >= 3 && row <= 5 && col >= 2 && col <= 5) {
                    fill = palette.skin;
                }
                // Eyes (row 3, col 2-3 and col 4-5)
                if (row === 3) {
                    if ((col === 2 || col === 3 || col === 4 || col === 5) &&
                        face.eyes[col - 2]) {
                        fill = '#111';
                    }
                }
                // Mouth (row 4-5, col 3-4)
                if (row >= 4 && row <= 5 && col >= 3 && col <= 4) {
                    const mi = (row - 4) * 2 + (col - 3);
                    if (mi < face.mouth.length && face.mouth[mi]) {
                        fill = '#111';
                    }
                }
                // Body (rows 6-7)
                if (row >= 6 && col >= 2 && col <= 5) {
                    fill = palette.mid;
                }

                if (fill) {
                    ctx.fillStyle = fill;
                    ctx.fillRect(x + col * scale, y + row * scale, scale, scale);
                }
            }
        }
    }

    _facePattern(mood) {
        const patterns = {
            confident: { eyes: [1, 0, 1, 1], mouth: [0, 1, 1, 0] },
            calm:     { eyes: [1, 0, 1, 0], mouth: [0, 1, 1, 0] },
            worried:  { eyes: [1, 1, 1, 1], mouth: [1, 0, 0, 1] },
            excited:  { eyes: [1, 1, 1, 1], mouth: [1, 1, 1, 1] },
            panicked: { eyes: [1, 1, 1, 1], mouth: [1, 1, 1, 1] },
        };
        return patterns[mood] || patterns.calm;
    }

    _makePalette(hex) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return {
            dark: `rgb(${Math.floor(r*0.4)},${Math.floor(g*0.4)},${Math.floor(b*0.4)})`,
            mid: hex,
            light: `rgb(${Math.min(255,Math.floor(r*1.4))},${Math.min(255,Math.floor(g*1.4))},${Math.min(255,Math.floor(b*1.4))})`,
            skin: '#F5D0A9',
        };
    }

    _drawConversations() {
        const ctx = this.ctx;
        for (const conv of this.conversations) {
            const positions = [];
            for (const pid of conv.participants) {
                const a = this.agents[pid];
                if (a) positions.push({ x: a.tileX * TILE_PX + TILE_PX / 2, y: a.tileY * TILE_PX + TILE_PX / 2 });
            }
            if (positions.length < 2) continue;

            const midX = positions.reduce((s, p) => s + p.x, 0) / positions.length;
            const midY = positions.reduce((s, p) => s + p.y, 0) / positions.length;

            // Connecting lines
            ctx.strokeStyle = 'rgba(255,240,150,0.35)';
            ctx.lineWidth = 1;
            for (let i = 0; i < positions.length; i++) {
                for (let j = i + 1; j < positions.length; j++) {
                    ctx.beginPath();
                    ctx.moveTo(positions[i].x, positions[i].y);
                    ctx.lineTo(positions[j].x, positions[j].y);
                    ctx.stroke();
                }
            }

            // Speech bubble with last line of conversation
            const lastLine = conv.lines[conv.lines.length - 1];
            const text = lastLine
                ? lastLine.speaker + ': ' + lastLine.content
                : '...';
            const short = text.length > 30 ? text.slice(0, 28) + '..' : text;

            ctx.font = '5px monospace';
            const textW = ctx.measureText(short).width + 12;
            const bubbleW = Math.max(textW, 40);
            const bubbleH = 16;
            const bx = midX - bubbleW / 2;
            const by = midY - 42;

            ctx.fillStyle = 'rgba(0,0,0,0.85)';
            ctx.fillRect(bx, by, bubbleW, bubbleH);
            ctx.strokeStyle = '#555';
            ctx.lineWidth = 1;
            ctx.strokeRect(bx, by, bubbleW, bubbleH);
            ctx.fillStyle = '#fff';
            ctx.fillText(short, bx + 6, by + 11);
        }
    }

    // ---- Interaction ----

    _onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const mx = (e.clientX - rect.left) * scaleX;
        const my = (e.clientY - rect.top) * scaleY;
        const tileX = Math.floor(mx / TILE_PX);
        const tileY = Math.floor(my / TILE_PX);

        // Find closest agent within 1.5 tiles
        let bestAgent = null;
        let bestDist = 999;
        for (const [id, agent] of Object.entries(this.agents)) {
            const dx = agent.tileX - tileX;
            const dy = agent.tileY - tileY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 1.8 && dist < bestDist) {
                bestDist = dist;
                bestAgent = id;
            }
        }
        this.hoveredAgent = bestAgent;
        this.canvas.style.cursor = bestAgent ? 'pointer' : 'default';
    }

    _onClick(e) {
        if (this.hoveredAgent && this.onSelectAgent) {
            this.selectedAgent = this.hoveredAgent;
            this.onSelectAgent(this.hoveredAgent);
        }
    }

    _darken(hex, f) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgb(${Math.floor(r*(1-f))},${Math.floor(g*(1-f))},${Math.floor(b*(1-f))})`;
    }

    _seedFromId(id) {
        let h = 0;
        for (let i = 0; i < id.length; i++) h = ((h << 5) - h) + id.charCodeAt(i);
        return Math.abs(h);
    }
}
