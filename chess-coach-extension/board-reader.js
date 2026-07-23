const BoardReader = (() => {
  'use strict';

  const PIECE_CLASS_MAP = {
    'wp': 'P', 'wn': 'N', 'wb': 'B', 'wr': 'R', 'wq': 'Q', 'wk': 'K',
    'bp': 'p', 'bn': 'n', 'bb': 'b', 'br': 'r', 'bq': 'q', 'bk': 'k'
  };

  function readBoardFromDOM() {
    const board = Array(8).fill(null).map(() => Array(8).fill(null));
    const boardEl = document.querySelector('chess-board, .board, wc-chess-board');
    if (!boardEl) return null;

    const pieces = boardEl.querySelectorAll('.piece');
    if (pieces.length === 0) return null;

    let isFlipped = false;
    const coordsEl = boardEl.querySelector('.coordinates');
    if (coordsEl) {
      const firstCoord = coordsEl.querySelector('coord');
      if (firstCoord && firstCoord.textContent.trim() === '8') {
        isFlipped = true;
      }
    }
    const boardClasses = boardEl.className || '';
    if (boardClasses.includes('flipped')) {
      isFlipped = true;
    }

    for (const pieceEl of pieces) {
      const classList = Array.from(pieceEl.classList);

      let pieceCode = null;
      for (const cls of classList) {
        if (PIECE_CLASS_MAP[cls]) {
          pieceCode = PIECE_CLASS_MAP[cls];
          break;
        }
      }

      let file = -1, rank = -1;
      for (const cls of classList) {
        const match = cls.match(/^square-(\d)(\d)$/);
        if (match) {
          file = parseInt(match[1]) - 1;
          rank = parseInt(match[2]) - 1;
          break;
        }
      }

      if (pieceCode && file >= 0 && rank >= 0) {
        const boardRank = 7 - rank;
        board[boardRank][file] = pieceCode;
      }
    }

    return { board, isFlipped };
  }

  function boardToFEN(boardState) {
    if (!boardState) return null;
    const { board } = boardState;

    let fen = '';
    for (let rank = 0; rank < 8; rank++) {
      let empty = 0;
      for (let file = 0; file < 8; file++) {
        const piece = board[rank][file];
        if (piece === null) {
          empty++;
        } else {
          if (empty > 0) { fen += empty; empty = 0; }
          fen += piece;
        }
      }
      if (empty > 0) fen += empty;
      if (rank < 7) fen += '/';
    }

    return fen;
  }

  function detectTurn() {
    const clockEls = document.querySelectorAll('.clock-component, .clock-bottom, .clock-top');
    for (const el of clockEls) {
      if (el.classList.contains('clock-player-turn') ||
          el.classList.contains('clock-running')) {
        const isBottom = el.classList.contains('clock-bottom') ||
                         el.closest('.board-layout-bottom');
        return isBottom ? 'w' : 'b';
      }
    }

    const moveList = document.querySelector('.move-list, vertical-move-list, wc-move-list');
    if (moveList) {
      const moves = moveList.querySelectorAll('.move, .node');
      if (moves.length > 0) {
        const lastMove = moves[moves.length - 1];
        const moveNodes = lastMove.querySelectorAll('.white-move, .black-move, [data-ply]');
        if (moveNodes.length > 0) {
          const last = moveNodes[moveNodes.length - 1];
          if (last.classList.contains('white-move') || (last.dataset.ply && parseInt(last.dataset.ply) % 2 === 1)) {
            return 'b';
          }
          return 'w';
        }
      }
      return 'w';
    }

    return 'w';
  }

  function detectCastlingRights(board) {
    let rights = '';
    if (board[7][4] === 'K') {
      if (board[7][7] === 'R') rights += 'K';
      if (board[7][0] === 'R') rights += 'Q';
    }
    if (board[0][4] === 'k') {
      if (board[0][7] === 'r') rights += 'k';
      if (board[0][0] === 'r') rights += 'q';
    }
    return rights || '-';
  }

  function getPlayerColor() {
    const boardEl = document.querySelector('chess-board, .board, wc-chess-board');
    if (!boardEl) return 'w';

    if (boardEl.classList.contains('flipped')) return 'b';

    const coords = boardEl.querySelectorAll('.coordinates coord, .coordinate');
    if (coords.length > 0) {
      const first = coords[0].textContent.trim();
      if (first === '8') return 'b';
    }

    return 'w';
  }

  function getFullFEN() {
    const boardState = readBoardFromDOM();
    if (!boardState) return null;

    const position = boardToFEN(boardState);
    const turn = detectTurn();
    const castling = detectCastlingRights(boardState.board);

    return `${position} ${turn} ${castling} - 0 1`;
  }

  function getLastMoveSquares() {
    const highlights = document.querySelectorAll('.highlight');
    const squares = [];
    for (const el of highlights) {
      for (const cls of el.classList) {
        const match = cls.match(/^square-(\d)(\d)$/);
        if (match) {
          const file = parseInt(match[1]) - 1;
          const rank = parseInt(match[2]) - 1;
          squares.push({ file, rank: 7 - rank });
        }
      }
    }
    return squares;
  }

  return {
    readBoardFromDOM,
    boardToFEN,
    getFullFEN,
    detectTurn,
    getPlayerColor,
    getLastMoveSquares
  };
})();

if (typeof window !== 'undefined') {
  window.BoardReader = BoardReader;
}
