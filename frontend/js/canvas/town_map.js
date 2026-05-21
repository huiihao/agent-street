// Town Map canvas — renders the Smallville-style pixel town

const TILE_PX = 24; // pixel size of each tile on screen
const MAP_COLS = 20;
const MAP_ROWS = 14;

const TILE_COLORS = {
    0: '#3a5a3a',  // grass
    1: '#6b6b6b',  // road horizontal
    2: '#6b6b6b',  // road vertical
    3: null,        // building (rendered separately)
    4: '#2a4a2a',  // tree green
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
        this.agents = {}; // id -> {tileX, tileY, location, mood, color, isMoving}
        this.conversations = [];
        this.hoveredAgent = null;
        this.selectedAgent = null;
        this.onSelectAgent = null; // callback

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
        this.drawMap();
    }

    updateAgentStates(states) {
        states.forEach(s => {
            this.agents[s.id] = {
                tileX: s.tileX,
                tileY: s.tileY,
                location: s.location,
                mood: s.mood,
                color: s.color || '#888',
                isMoving: s.isMoving,
            };
        });
    }

    updateConversations(convs) {
        this.conversations = convs || [];
    }

    // ---- Drawing ----

    drawMap() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (!this.mapData) return;

        // Draw tiles
        for (let y = 0; y < MAP_ROWS; y++) {
            for (let x = 0; x < MAP_COLS; x++) {
                const tile = this.mapData[y][x];
                const color = TILE_COLORS[tile];
                if (color) {
                    ctx.fillStyle = color;
                    ctx.fillRect(x * TILE_PX, y * TILE_PX, TILE_PX, TILE_PX);
                }
                // Grid overlay
                ctx.strokeStyle = 'rgba(0,0,0,0.15)';
                ctx.strokeRect(x * TILE_PX, y * TILE_PX, TILE_PX, TILE_PX);

                // Tree detail
                if (tile === 4) {
                    ctx.fillStyle = '#4a7a3a';
                    const cx = x * TILE_PX + TILE_PX / 2;
                    const cy = y * TILE_PX + TILE_PX / 2;
                    ctx.beginPath();
                    ctx.arc(cx, cy, TILE_PX / 3, 0, Math.PI * 2);
                    ctx.fill();
                }
                // Water detail
                if (tile === 5) {
                    ctx.fillStyle = 'rgba(80,140,180,0.4)';
                    for (let i = 0; i < 3; i++) {
                        const wx = x * TILE_PX + 4 + i * 6;
                        const wy = y * TILE_PX + 6 + (i % 2) * 5;
                        ctx.fillRect(wx, wy, 3, 2);
                    }
                }
            }
        }

        // Draw buildings
        this.locations.forEach(loc => {
            const px = loc.tileX * TILE_PX;
            const py = loc.tileY * TILE_PX;
            const w = loc.width * TILE_PX;
            const h = loc.height * TILE_PX;

            // Building body
            ctx.fillStyle = loc.color;
            ctx.fillRect(px - TILE_PX / 2, py - TILE_PX / 2, w, h);

            // Roof (darker)
            ctx.fillStyle = this._darkenColor(loc.color, 0.4);
            ctx.fillRect(px - TILE_PX / 2, py - TILE_PX / 2, w, 5);

            // Outline
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            ctx.strokeRect(px - TILE_PX / 2, py - TILE_PX / 2, w, h);

            // Label
            ctx.fillStyle = '#fff';
            ctx.font = '7px "Press Start 2P"';
            ctx.textAlign = 'center';
            ctx.fillText(loc.name, px + w / 2 - TILE_PX / 2, py + h / 2 + TILE_PX / 2 + 12);
        });
    }

    renderFrame() {
        this.drawMap();
        this._drawConversations();
        this._drawAgents();
    }

    _drawAgents() {
        const ctx = this.ctx;
        for (const [id, agent] of Object.entries(this.agents)) {
            const px = agent.tileX * TILE_PX + TILE_PX / 2;
            const py = agent.tileY * TILE_PX + TILE_PX / 2;
            const isSelected = this.selectedAgent === id;
            const isHovered = this.hoveredAgent === id;

            // Agent dot with color
            const radius = isSelected ? 8 : 6;
            ctx.fillStyle = agent.color || '#888';
            ctx.beginPath();
            ctx.arc(px, py, radius, 0, Math.PI * 2);
            ctx.fill();

            // Mood glow
            const moodGlow = {
                confident: 'rgba(78, 204, 163, 0.5)',
                calm: 'rgba(107, 174, 214, 0.4)',
                worried: 'rgba(240, 160, 64, 0.5)',
                excited: 'rgba(240, 192, 64, 0.6)',
                panicked: 'rgba(233, 69, 96, 0.6)',
            }[agent.mood] || 'rgba(136,136,136,0.3)';
            ctx.fillStyle = moodGlow;
            ctx.beginPath();
            ctx.arc(px, py, radius + 4, 0, Math.PI * 2);
            ctx.fill();

            // Hover/select highlight
            if (isHovered || isSelected) {
                ctx.strokeStyle = isSelected ? '#f0c040' : '#fff';
                ctx.lineWidth = 2;
                const r = radius + 6;
                ctx.strokeRect(px - r, py - r, r * 2, r * 2);
            }

            // ID label
            ctx.fillStyle = '#fff';
            ctx.font = '5px "Press Start 2P"';
            ctx.textAlign = 'center';
            ctx.fillText(id, px, py - radius - 6);

            // Moving indicator
            if (agent.isMoving) {
                ctx.fillStyle = '#fff';
                for (let i = -2; i <= 2; i += 4) {
                    ctx.fillRect(px + i, py - radius - 4, 2, 2);
                }
            }
        }
    }

    _drawConversations() {
        const ctx = this.ctx;
        for (const conv of this.conversations) {
            // Find participants' positions
            const positions = [];
            for (const pid of conv.participants) {
                const agent = this.agents[pid];
                if (agent) {
                    positions.push({ x: agent.tileX * TILE_PX + TILE_PX / 2, y: agent.tileY * TILE_PX + TILE_PX / 2 });
                }
            }
            if (positions.length < 2) continue;

            const midX = positions.reduce((s, p) => s + p.x, 0) / positions.length;
            const midY = positions.reduce((s, p) => s + p.y, 0) / positions.length;

            // Speech bubble
            const bubbleX = midX - 30;
            const bubbleY = midY - 40;
            ctx.fillStyle = 'rgba(0,0,0,0.8)';
            ctx.fillRect(bubbleX, bubbleY, 60, 20);

            // Connect lines between participants
            ctx.strokeStyle = 'rgba(255,255,200,0.4)';
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 2]);
            for (let i = 0; i < positions.length; i++) {
                for (let j = i + 1; j < positions.length; j++) {
                    ctx.beginPath();
                    ctx.moveTo(positions[i].x, positions[i].y);
                    ctx.lineTo(positions[j].x, positions[j].y);
                    ctx.stroke();
                }
            }
            ctx.setLineDash([]);

            // Bubble text
            ctx.fillStyle = '#f0c040';
            ctx.font = '6px "Press Start 2P"';
            ctx.textAlign = 'center';
            ctx.fillText('CHAT', bubbleX + 30, bubbleY + 14);
        }
    }

    // ---- Interaction ----

    _onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const tileX = Math.floor(mx / TILE_PX);
        const tileY = Math.floor(my / TILE_PX);

        let found = null;
        for (const [id, agent] of Object.entries(this.agents)) {
            const dx = agent.tileX - tileX;
            const dy = agent.tileY - tileY;
            if (Math.abs(dx) <= 1 && Math.abs(dy) <= 1) {
                found = id;
                break;
            }
        }
        this.hoveredAgent = found;
        this.canvas.style.cursor = found ? 'pointer' : 'default';
    }

    _onClick(e) {
        if (this.hoveredAgent && this.onSelectAgent) {
            this.selectedAgent = this.hoveredAgent;
            this.onSelectAgent(this.hoveredAgent);
        }
    }

    _darkenColor(hex, factor) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        const d = (c) => Math.floor(c * (1 - factor));
        return `rgb(${d(r)},${d(g)},${d(b)})`;
    }

    getAgentPosition(id) {
        return this.agents[id] || null;
    }
}
