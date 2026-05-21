// Agent detail panel — shown when clicking an agent on the town map

class AgentDetail {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentId = null;
        this.personaDefs = {};
        this.agentStates = {};
    }

    setDefs(defs) {
        defs.forEach(d => { this.personaDefs[d.id] = d; });
    }

    updateStates(states) {
        states.forEach(s => { this.agentStates[s.id] = s; });
    }

    show(agentId) {
        this.currentId = agentId;
        this.render();
    }

    hide() {
        this.currentId = null;
        this.container.innerHTML = '<div style="padding:16px;color:#888;text-align:center">Click an agent on the map</div>';
    }

    render() {
        if (!this.currentId) {
            this.hide();
            return;
        }
        const def = this.personaDefs[this.currentId] || {};
        const state = this.agentStates[this.currentId] || {};
        const pnlStr = (state.pnl || 0) >= 0 ? '+' + (state.pnl || 0).toFixed(0) : (state.pnl || 0).toFixed(0);
        const pnlClass = (state.pnl || 0) >= 0 ? 'positive' : 'negative';

        const moodMap = {
            confident: 'Confident',
            calm: 'Calm',
            worried: 'Worried',
            excited: 'Excited',
            panicked: 'Panicked',
        };

        this.container.innerHTML = `
            <div class="agent-detail-card">
                <div class="agent-header" style="border-left: 4px solid ${def.color || '#888'}">
                    <span class="agent-id">${this.currentId}</span>
                    <span class="agent-name">${def.name || ''}</span>
                    <span class="agent-mood mood-${state.mood || 'calm'}">${moodMap[state.mood] || 'Calm'}</span>
                </div>
                <div class="agent-motto">"${def.motto || ''}"</div>
                <div class="agent-backstory">${def.backstory || state.backstory || ''}</div>
                <div class="agent-stats">
                    <div class="stat-row"><span>Location</span><span>${state.location || 'Home'}</span></div>
                    <div class="stat-row"><span>Cash</span><span>$${(state.cash || 0).toFixed(0)}</span></div>
                    <div class="stat-row"><span>P&L</span><span class="${pnlClass}">$${pnlStr}</span></div>
                    <div class="stat-row"><span>Positions</span><span>${state.positions || 0}</span></div>
                </div>
                <div class="agent-thoughts">
                    <div class="thoughts-title">Recent Thoughts</div>
                    ${(state.thoughts || []).map(t =>
                        `<div class="thought-line">${t.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>`
                    ).join('')}
                    ${(!state.thoughts || state.thoughts.length === 0) ?
                        '<div class="thought-line" style="color:#666">No thoughts yet...</div>' : ''}
                </div>
            </div>
        `;
    }
}
