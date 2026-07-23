(() => {
  'use strict';

  let isEnabled = true;
  let showArrows = true;
  let showPanel = true;
  let autoAnalyze = true;
  let analysisDepth = 5;
  let lastFEN = null;
  let panelEl = null;
  let arrowCanvas = null;
  let currentAnalysis = null;

  function init() {
    chrome.storage.sync.get({
      enabled: true,
      showArrows: true,
      showPanel: true,
      autoAnalyze: true,
      depth: 5
    }, (settings) => {
      isEnabled = settings.enabled;
      showArrows = settings.showArrows;
      showPanel = settings.showPanel;
      autoAnalyze = settings.autoAnalyze;
      analysisDepth = settings.depth;
      if (isEnabled) startObserving();
    });

    chrome.storage.onChanged.addListener((changes) => {
      if (changes.enabled) {
        isEnabled = changes.enabled.newValue;
        if (isEnabled) {
          startObserving();
        } else {
          cleanup();
        }
      }
      if (changes.showArrows) showArrows = changes.showArrows.newValue;
      if (changes.showPanel) showPanel = changes.showPanel.newValue;
      if (changes.autoAnalyze) autoAnalyze = changes.autoAnalyze.newValue;
      if (changes.depth) analysisDepth = changes.depth.newValue;

      if (isEnabled && currentAnalysis) {
        renderAnalysis(currentAnalysis);
      }
    });
  }

  function startObserving() {
    createPanel();
    observeBoard();
    if (autoAnalyze) {
      setTimeout(() => analyzeCurrentPosition(), 1000);
    }
  }

  function cleanup() {
    if (panelEl) { panelEl.remove(); panelEl = null; }
    clearArrows();
  }

  function createPanel() {
    if (panelEl) return;

    panelEl = document.createElement('div');
    panelEl.id = 'chess-coach-panel';
    panelEl.innerHTML = `
      <div class="cc-header">
        <span class="cc-title">Chess Coach</span>
        <div class="cc-controls">
          <button class="cc-btn cc-analyze-btn" title="Analyze position">Analyze</button>
          <button class="cc-btn cc-minimize-btn" title="Minimize">_</button>
        </div>
      </div>
      <div class="cc-body">
        <div class="cc-status">Waiting for position...</div>
        <div class="cc-eval-bar-container">
          <div class="cc-eval-bar">
            <div class="cc-eval-fill"></div>
          </div>
          <span class="cc-eval-score"></span>
        </div>
        <div class="cc-section cc-best-move-section" style="display:none">
          <div class="cc-section-title">Best Move</div>
          <div class="cc-best-move"></div>
        </div>
        <div class="cc-section cc-lines-section" style="display:none">
          <div class="cc-section-title">Top Moves</div>
          <div class="cc-lines"></div>
        </div>
        <div class="cc-section cc-threats-section" style="display:none">
          <div class="cc-section-title">Opponent Threats</div>
          <div class="cc-threats"></div>
        </div>
        <div class="cc-section cc-tactics-section" style="display:none">
          <div class="cc-section-title">Tactical Notes</div>
          <div class="cc-tactics"></div>
        </div>
        <div class="cc-section cc-learning-section" style="display:none">
          <div class="cc-section-title">Learning Tip</div>
          <div class="cc-learning"></div>
        </div>
      </div>
    `;

    document.body.appendChild(panelEl);

    const analyzeBtn = panelEl.querySelector('.cc-analyze-btn');
    analyzeBtn.addEventListener('click', () => analyzeCurrentPosition());

    const minimizeBtn = panelEl.querySelector('.cc-minimize-btn');
    minimizeBtn.addEventListener('click', () => {
      const body = panelEl.querySelector('.cc-body');
      const isMinimized = body.style.display === 'none';
      body.style.display = isMinimized ? 'block' : 'none';
      minimizeBtn.textContent = isMinimized ? '_' : '+';
    });

    makeDraggable(panelEl);
  }

  function makeDraggable(el) {
    const header = el.querySelector('.cc-header');
    let isDragging = false, startX, startY, startLeft, startTop;

    header.addEventListener('mousedown', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = el.getBoundingClientRect();
      startLeft = rect.left;
      startTop = rect.top;
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      el.style.left = (startLeft + dx) + 'px';
      el.style.top = (startTop + dy) + 'px';
      el.style.right = 'auto';
    });

    document.addEventListener('mouseup', () => { isDragging = false; });
  }

  function observeBoard() {
    const observer = new MutationObserver(() => {
      if (!isEnabled || !autoAnalyze) return;
      const fen = BoardReader.getFullFEN();
      if (fen && fen !== lastFEN) {
        lastFEN = fen;
        debounceAnalyze();
      }
    });

    const tryObserve = () => {
      const boardEl = document.querySelector('chess-board, .board, wc-chess-board');
      if (boardEl) {
        observer.observe(boardEl, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style'] });
        const fen = BoardReader.getFullFEN();
        if (fen) {
          lastFEN = fen;
          analyzeCurrentPosition();
        }
      } else {
        setTimeout(tryObserve, 1000);
      }
    };

    tryObserve();

    const pageObserver = new MutationObserver(() => {
      const boardEl = document.querySelector('chess-board, .board, wc-chess-board');
      if (boardEl && !boardEl.dataset.ccObserved) {
        boardEl.dataset.ccObserved = 'true';
        observer.observe(boardEl, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style'] });
      }
    });
    pageObserver.observe(document.body, { childList: true, subtree: true });
  }

  let analyzeTimer = null;
  function debounceAnalyze() {
    clearTimeout(analyzeTimer);
    analyzeTimer = setTimeout(() => analyzeCurrentPosition(), 300);
  }

  function analyzeCurrentPosition() {
    if (!isEnabled) return;

    const fen = BoardReader.getFullFEN();
    if (!fen) {
      updateStatus('No board detected - navigate to a game');
      return;
    }

    updateStatus('Analyzing...');

    setTimeout(() => {
      try {
        const engine = new ChessEngine.Engine();
        const analysis = engine.analyze(fen, analysisDepth);
        analysis.fen = fen;
        analysis.playerColor = BoardReader.getPlayerColor();
        currentAnalysis = analysis;
        renderAnalysis(analysis);
      } catch (e) {
        updateStatus('Analysis error: ' + e.message);
      }
    }, 10);
  }

  function updateStatus(text) {
    if (!panelEl) return;
    const statusEl = panelEl.querySelector('.cc-status');
    if (statusEl) statusEl.textContent = text;
  }

  function renderAnalysis(analysis) {
    if (!panelEl) return;

    const statusEl = panelEl.querySelector('.cc-status');
    statusEl.textContent = `Depth ${analysis.depth} | ${analysis.nodes.toLocaleString()} positions | ${analysis.turn}'s turn`;

    renderEvalBar(analysis);
    renderBestMove(analysis);
    renderLines(analysis);
    renderThreats(analysis);
    renderTactics(analysis);
    renderLearningTip(analysis);

    if (showArrows) {
      drawArrows(analysis);
    } else {
      clearArrows();
    }
  }

  function renderEvalBar(analysis) {
    const container = panelEl.querySelector('.cc-eval-bar-container');
    const fill = panelEl.querySelector('.cc-eval-fill');
    const scoreEl = panelEl.querySelector('.cc-eval-score');

    container.style.display = 'flex';
    scoreEl.textContent = analysis.evaluation;

    let pct;
    if (typeof analysis.evaluation === 'string' && analysis.evaluation.includes('M')) {
      pct = analysis.evaluation.startsWith('-') ? 5 : 95;
    } else {
      const score = parseFloat(analysis.evaluation);
      pct = 50 + Math.max(-50, Math.min(50, score * 10));
    }

    fill.style.width = pct + '%';
    fill.className = 'cc-eval-fill' + (pct >= 50 ? ' cc-eval-white' : ' cc-eval-black');
  }

  function renderBestMove(analysis) {
    const section = panelEl.querySelector('.cc-best-move-section');
    const el = panelEl.querySelector('.cc-best-move');

    if (!analysis.bestMove) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    el.innerHTML = `
      <div class="cc-move-display">
        <span class="cc-move-san">${analysis.bestMove.san}</span>
        <span class="cc-move-eval">${analysis.evaluation}</span>
      </div>
      <div class="cc-move-detail">${analysis.bestMove.from} → ${analysis.bestMove.to}</div>
    `;
  }

  function renderLines(analysis) {
    const section = panelEl.querySelector('.cc-lines-section');
    const el = panelEl.querySelector('.cc-lines');

    if (!analysis.lines || analysis.lines.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    el.innerHTML = analysis.lines.map((line, i) => `
      <div class="cc-line ${i === 0 ? 'cc-line-best' : ''}" data-from="${line.from}" data-to="${line.to}">
        <span class="cc-line-rank">${line.rank}.</span>
        <span class="cc-line-san">${line.san}</span>
        <span class="cc-line-eval">${line.evaluation}</span>
      </div>
    `).join('');

    el.querySelectorAll('.cc-line').forEach(lineEl => {
      lineEl.addEventListener('mouseenter', () => {
        const from = parseInt(lineEl.dataset.from);
        const to = parseInt(lineEl.dataset.to);
        highlightSquares(from, to, '#4CAF50');
      });
      lineEl.addEventListener('mouseleave', () => {
        clearHighlights();
      });
    });
  }

  function renderThreats(analysis) {
    const section = panelEl.querySelector('.cc-threats-section');
    const el = panelEl.querySelector('.cc-threats');

    if (!analysis.threats || analysis.threats.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    const severityIcons = { critical: '⚠', high: '▲', medium: '●' };
    const severityColors = { critical: '#f44336', high: '#ff9800', medium: '#ffc107' };

    el.innerHTML = analysis.threats.map(t => `
      <div class="cc-threat" style="border-left: 3px solid ${severityColors[t.severity]}">
        <span class="cc-threat-icon">${severityIcons[t.severity]}</span>
        <span class="cc-threat-text">
          ${t.attackerPiece} on ${t.attacker} ${t.type === 'check' ? 'gives check' : `threatens ${t.targetPiece} on ${t.target}`}
          ${t.protected ? '(defended)' : '(undefended!)'}
        </span>
      </div>
    `).join('');
  }

  function renderTactics(analysis) {
    const section = panelEl.querySelector('.cc-tactics-section');
    const el = panelEl.querySelector('.cc-tactics');

    if (!analysis.tactics || analysis.tactics.length === 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    el.innerHTML = analysis.tactics.map(t => `
      <div class="cc-tactic">
        <span class="cc-tactic-type">${formatTacticType(t.type)}</span>
        <span class="cc-tactic-desc">${t.description}</span>
      </div>
    `).join('');
  }

  function formatTacticType(type) {
    const labels = {
      only_move: 'Key Move',
      winning_capture: 'Win Material',
      in_check: 'In Check',
      gives_check: 'Check!'
    };
    return labels[type] || type;
  }

  function renderLearningTip(analysis) {
    const section = panelEl.querySelector('.cc-learning-section');
    const el = panelEl.querySelector('.cc-learning');

    const tip = generateLearningTip(analysis);
    if (!tip) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    el.innerHTML = `<div class="cc-tip">${tip}</div>`;
  }

  function generateLearningTip(analysis) {
    const score = analysis.rawScore;
    const threats = analysis.threats || [];
    const tactics = analysis.tactics || [];

    if (tactics.some(t => t.type === 'in_check')) {
      return 'When in check, look for ways to block, capture the attacker, or move the king to a safe square. Prioritize keeping material.';
    }

    if (tactics.some(t => t.type === 'winning_capture')) {
      return 'A piece can be captured for free or by trading up in value. Always scan for undefended pieces before making your move.';
    }

    if (threats.some(t => t.severity === 'critical')) {
      return 'Your opponent has a dangerous threat. Before playing your plan, always ask: "What is my opponent threatening?" Defensive awareness prevents blunders.';
    }

    if (threats.some(t => !t.protected)) {
      return 'You have an undefended piece under attack. A good habit: after each opponent move, check if any of your pieces are hanging (unprotected).';
    }

    if (Math.abs(score) < 50) {
      return 'The position is roughly equal. Focus on improving your worst-placed piece, controlling the center, and creating small advantages.';
    }

    if (score > 300) {
      return 'You have a significant advantage. In winning positions, simplify by trading pieces (not pawns). Fewer pieces make it harder for your opponent to create counterplay.';
    }

    if (score < -300) {
      return 'You are behind in this position. Look for tactical complications and avoid trading pieces. Create threats that force your opponent to find precise moves.';
    }

    if (tactics.some(t => t.type === 'only_move')) {
      return 'This position has one clearly best move. Train yourself to spot these critical moments by asking: "Is there a forcing move (check, capture, or threat)?"';
    }

    return 'Take your time to evaluate the position. Consider: piece activity, king safety, pawn structure, and control of key squares.';
  }

  function drawArrows(analysis) {
    clearArrows();
    const boardEl = document.querySelector('chess-board, .board, wc-chess-board');
    if (!boardEl) return;

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.id = 'cc-arrow-overlay';
    svg.setAttribute('viewBox', '0 0 100 100');
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:50;';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const markers = [
      { id: 'cc-arrow-best', color: '#66bb6a' },
      { id: 'cc-arrow-alt', color: '#42a5f5' },
      { id: 'cc-arrow-threat', color: '#ef5350' }
    ];

    for (const m of markers) {
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      marker.setAttribute('id', m.id);
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '8');
      marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '4');
      marker.setAttribute('markerHeight', '4');
      marker.setAttribute('orient', 'auto-start-reverse');
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
      path.setAttribute('fill', m.color);
      marker.appendChild(path);
      defs.appendChild(marker);
    }
    svg.appendChild(defs);

    const isFlipped = boardEl.classList.contains('flipped');

    if (analysis.bestMove) {
      const fromSq = analysis.bestMove.fromSquare;
      const toSq = analysis.bestMove.toSquare;
      addArrow(svg, fromSq, toSq, '#66bb6a', 'cc-arrow-best', 0.9, isFlipped);
    }

    if (analysis.lines) {
      for (let i = 1; i < Math.min(3, analysis.lines.length); i++) {
        const line = analysis.lines[i];
        addArrow(svg, line.from, line.to, '#42a5f5', 'cc-arrow-alt', 0.5, isFlipped);
      }
    }

    if (analysis.threats) {
      for (const threat of analysis.threats.slice(0, 2)) {
        addArrow(svg, threat.fromSquare, threat.toSquare, '#ef5350', 'cc-arrow-threat', 0.6, isFlipped);
      }
    }

    boardEl.style.position = boardEl.style.position || 'relative';
    boardEl.appendChild(svg);
    arrowCanvas = svg;
  }

  function addArrow(svg, fromSq, toSq, color, markerId, opacity, isFlipped) {
    let fromFile = fromSq & 7;
    let fromRank = fromSq >> 3;
    let toFile = toSq & 7;
    let toRank = toSq >> 3;

    let x1, y1, x2, y2;
    if (isFlipped) {
      x1 = (7 - fromFile) * 12.5 + 6.25;
      y1 = fromRank * 12.5 + 6.25;
      x2 = (7 - toFile) * 12.5 + 6.25;
      y2 = toRank * 12.5 + 6.25;
    } else {
      x1 = fromFile * 12.5 + 6.25;
      y1 = fromRank * 12.5 + 6.25;
      x2 = toFile * 12.5 + 6.25;
      y2 = toRank * 12.5 + 6.25;
    }

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', x1);
    line.setAttribute('y1', y1);
    line.setAttribute('x2', x2);
    line.setAttribute('y2', y2);
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-width', '1.8');
    line.setAttribute('stroke-opacity', opacity);
    line.setAttribute('stroke-linecap', 'round');
    line.setAttribute('marker-end', `url(#${markerId})`);
    svg.appendChild(line);
  }

  function clearArrows() {
    const existing = document.getElementById('cc-arrow-overlay');
    if (existing) existing.remove();
    arrowCanvas = null;
  }

  function highlightSquares(fromSq, toSq, color) {
    clearHighlights();
    const boardEl = document.querySelector('chess-board, .board, wc-chess-board');
    if (!boardEl) return;

    const isFlipped = boardEl.classList.contains('flipped');

    for (const sq of [fromSq, toSq]) {
      const file = sq & 7;
      const rank = sq >> 3;
      const div = document.createElement('div');
      div.className = 'cc-highlight';

      let left, top;
      if (isFlipped) {
        left = (7 - file) * 12.5;
        top = rank * 12.5;
      } else {
        left = file * 12.5;
        top = rank * 12.5;
      }

      div.style.cssText = `
        position: absolute;
        left: ${left}%;
        top: ${top}%;
        width: 12.5%;
        height: 12.5%;
        background: ${color};
        opacity: 0.3;
        pointer-events: none;
        z-index: 45;
      `;
      boardEl.appendChild(div);
    }
  }

  function clearHighlights() {
    document.querySelectorAll('.cc-highlight').forEach(el => el.remove());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
