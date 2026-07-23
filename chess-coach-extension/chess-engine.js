const ChessEngine = (() => {
  'use strict';

  const WHITE = 0, BLACK = 1;
  const PAWN = 1, KNIGHT = 2, BISHOP = 3, ROOK = 4, QUEEN = 5, KING = 6;
  const EMPTY = 0;

  const PIECE_VALUES = [0, 100, 320, 330, 500, 900, 20000];
  const PIECE_CHARS = '.PNBRQKpnbrqk';

  const PST_PAWN = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
  ];

  const PST_KNIGHT = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
  ];

  const PST_BISHOP = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
  ];

  const PST_ROOK = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0
  ];

  const PST_QUEEN = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
  ];

  const PST_KING_MID = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
  ];

  const PST_KING_END = [
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
  ];

  const PST = [null, PST_PAWN, PST_KNIGHT, PST_BISHOP, PST_ROOK, PST_QUEEN, PST_KING_MID];

  const KNIGHT_OFFSETS = [-17, -15, -10, -6, 6, 10, 15, 17];
  const BISHOP_OFFSETS = [-9, -7, 7, 9];
  const ROOK_OFFSETS = [-8, -1, 1, 8];
  const QUEEN_OFFSETS = [-9, -8, -7, -1, 1, 7, 8, 9];
  const KING_OFFSETS = [-9, -8, -7, -1, 1, 7, 8, 9];

  function makePiece(color, type) {
    return (color << 3) | type;
  }

  function pieceColor(piece) {
    return piece >> 3;
  }

  function pieceType(piece) {
    return piece & 7;
  }

  function squareName(sq) {
    const file = sq & 7;
    const rank = sq >> 3;
    return String.fromCharCode(97 + file) + (8 - rank);
  }

  function squareFromName(name) {
    const file = name.charCodeAt(0) - 97;
    const rank = 8 - parseInt(name[1]);
    return rank * 8 + file;
  }

  function mirrorSquare(sq) {
    return (7 - (sq >> 3)) * 8 + (sq & 7);
  }

  class Position {
    constructor() {
      this.board = new Uint8Array(64);
      this.turn = WHITE;
      this.castling = [true, true, true, true]; // WK, WQ, BK, BQ
      this.epSquare = -1;
      this.halfmove = 0;
      this.fullmove = 1;
      this.history = [];
    }

    clone() {
      const p = new Position();
      p.board = new Uint8Array(this.board);
      p.turn = this.turn;
      p.castling = [...this.castling];
      p.epSquare = this.epSquare;
      p.halfmove = this.halfmove;
      p.fullmove = this.fullmove;
      return p;
    }

    loadFEN(fen) {
      const parts = fen.split(' ');
      const ranks = parts[0].split('/');
      this.board.fill(0);

      for (let rank = 0; rank < 8; rank++) {
        let file = 0;
        for (const ch of ranks[rank]) {
          if (ch >= '1' && ch <= '8') {
            file += parseInt(ch);
          } else {
            const color = ch === ch.toUpperCase() ? WHITE : BLACK;
            const typeMap = { p: PAWN, n: KNIGHT, b: BISHOP, r: ROOK, q: QUEEN, k: KING };
            const type = typeMap[ch.toLowerCase()];
            this.board[rank * 8 + file] = makePiece(color, type);
            file++;
          }
        }
      }

      this.turn = parts[1] === 'w' ? WHITE : BLACK;
      this.castling = [
        parts[2].includes('K'),
        parts[2].includes('Q'),
        parts[2].includes('k'),
        parts[2].includes('q')
      ];
      this.epSquare = parts[3] === '-' ? -1 : squareFromName(parts[3]);
      this.halfmove = parseInt(parts[4]) || 0;
      this.fullmove = parseInt(parts[5]) || 1;
      return this;
    }

    toFEN() {
      let fen = '';
      for (let rank = 0; rank < 8; rank++) {
        let empty = 0;
        for (let file = 0; file < 8; file++) {
          const piece = this.board[rank * 8 + file];
          if (piece === EMPTY) {
            empty++;
          } else {
            if (empty > 0) { fen += empty; empty = 0; }
            const chars = '.PNBRQK..pnbrqk';
            fen += chars[piece];
          }
        }
        if (empty > 0) fen += empty;
        if (rank < 7) fen += '/';
      }

      fen += ' ' + (this.turn === WHITE ? 'w' : 'b') + ' ';
      let cas = '';
      if (this.castling[0]) cas += 'K';
      if (this.castling[1]) cas += 'Q';
      if (this.castling[2]) cas += 'k';
      if (this.castling[3]) cas += 'q';
      fen += (cas || '-') + ' ';
      fen += (this.epSquare >= 0 ? squareName(this.epSquare) : '-') + ' ';
      fen += this.halfmove + ' ' + this.fullmove;
      return fen;
    }

    isOnBoard(sq) {
      return sq >= 0 && sq < 64;
    }

    isSquareAttacked(sq, byColor) {
      for (let i = 0; i < 64; i++) {
        const piece = this.board[i];
        if (piece === EMPTY || pieceColor(piece) !== byColor) continue;
        const type = pieceType(piece);

        if (type === PAWN) {
          const dir = byColor === WHITE ? -1 : 1;
          const attacks = [i + dir * 8 - 1, i + dir * 8 + 1];
          for (const a of attacks) {
            if (a === sq && Math.abs((a & 7) - (i & 7)) === 1) return true;
          }
        } else if (type === KNIGHT) {
          for (const offset of KNIGHT_OFFSETS) {
            const to = i + offset;
            if (to === sq && this.isOnBoard(to) && Math.abs((to & 7) - (i & 7)) <= 2) return true;
          }
        } else if (type === KING) {
          for (const offset of KING_OFFSETS) {
            const to = i + offset;
            if (to === sq && this.isOnBoard(to) && Math.abs((to & 7) - (i & 7)) <= 1) return true;
          }
        } else {
          const offsets = type === BISHOP ? BISHOP_OFFSETS :
                          type === ROOK ? ROOK_OFFSETS : QUEEN_OFFSETS;
          for (const offset of offsets) {
            let cur = i + offset;
            while (this.isOnBoard(cur) && Math.abs((cur & 7) - ((cur - offset) & 7)) <= 1) {
              if (cur === sq) return true;
              if (this.board[cur] !== EMPTY) break;
              cur += offset;
            }
          }
        }
      }
      return false;
    }

    findKing(color) {
      const king = makePiece(color, KING);
      for (let i = 0; i < 64; i++) {
        if (this.board[i] === king) return i;
      }
      return -1;
    }

    inCheck(color) {
      const kingSq = this.findKing(color);
      if (kingSq < 0) return false;
      return this.isSquareAttacked(kingSq, 1 - color);
    }

    generateMoves() {
      const moves = [];
      const color = this.turn;

      for (let from = 0; from < 64; from++) {
        const piece = this.board[from];
        if (piece === EMPTY || pieceColor(piece) !== color) continue;
        const type = pieceType(piece);
        const fromFile = from & 7;
        const fromRank = from >> 3;

        if (type === PAWN) {
          const dir = color === WHITE ? -8 : 8;
          const startRank = color === WHITE ? 6 : 1;
          const promoRank = color === WHITE ? 0 : 7;

          const fwd = from + dir;
          if (this.isOnBoard(fwd) && this.board[fwd] === EMPTY) {
            if ((fwd >> 3) === promoRank) {
              for (const promo of [QUEEN, ROOK, BISHOP, KNIGHT]) {
                moves.push({ from, to: fwd, promotion: promo });
              }
            } else {
              moves.push({ from, to: fwd });
              if (fromRank === startRank) {
                const fwd2 = from + dir * 2;
                if (this.board[fwd2] === EMPTY) {
                  moves.push({ from, to: fwd2 });
                }
              }
            }
          }

          for (const df of [-1, 1]) {
            const to = from + dir + df;
            if (!this.isOnBoard(to) || Math.abs((to & 7) - fromFile) !== 1) continue;
            const target = this.board[to];
            if ((target !== EMPTY && pieceColor(target) !== color) || to === this.epSquare) {
              if ((to >> 3) === promoRank) {
                for (const promo of [QUEEN, ROOK, BISHOP, KNIGHT]) {
                  moves.push({ from, to, promotion: promo });
                }
              } else {
                moves.push({ from, to });
              }
            }
          }
        } else if (type === KNIGHT) {
          for (const offset of KNIGHT_OFFSETS) {
            const to = from + offset;
            if (!this.isOnBoard(to) || Math.abs((to & 7) - fromFile) > 2) continue;
            const target = this.board[to];
            if (target === EMPTY || pieceColor(target) !== color) {
              moves.push({ from, to });
            }
          }
        } else if (type === KING) {
          for (const offset of KING_OFFSETS) {
            const to = from + offset;
            if (!this.isOnBoard(to) || Math.abs((to & 7) - fromFile) > 1) continue;
            const target = this.board[to];
            if (target === EMPTY || pieceColor(target) !== color) {
              moves.push({ from, to });
            }
          }

          if (color === WHITE && from === 60) {
            if (this.castling[0] && this.board[61] === EMPTY && this.board[62] === EMPTY &&
                this.board[63] === makePiece(WHITE, ROOK) &&
                !this.isSquareAttacked(60, BLACK) &&
                !this.isSquareAttacked(61, BLACK) &&
                !this.isSquareAttacked(62, BLACK)) {
              moves.push({ from: 60, to: 62, castle: 'K' });
            }
            if (this.castling[1] && this.board[59] === EMPTY && this.board[58] === EMPTY &&
                this.board[57] === EMPTY && this.board[56] === makePiece(WHITE, ROOK) &&
                !this.isSquareAttacked(60, BLACK) &&
                !this.isSquareAttacked(59, BLACK) &&
                !this.isSquareAttacked(58, BLACK)) {
              moves.push({ from: 60, to: 58, castle: 'Q' });
            }
          } else if (color === BLACK && from === 4) {
            if (this.castling[2] && this.board[5] === EMPTY && this.board[6] === EMPTY &&
                this.board[7] === makePiece(BLACK, ROOK) &&
                !this.isSquareAttacked(4, WHITE) &&
                !this.isSquareAttacked(5, WHITE) &&
                !this.isSquareAttacked(6, WHITE)) {
              moves.push({ from: 4, to: 6, castle: 'k' });
            }
            if (this.castling[3] && this.board[3] === EMPTY && this.board[2] === EMPTY &&
                this.board[1] === EMPTY && this.board[0] === makePiece(BLACK, ROOK) &&
                !this.isSquareAttacked(4, WHITE) &&
                !this.isSquareAttacked(3, WHITE) &&
                !this.isSquareAttacked(2, WHITE)) {
              moves.push({ from: 4, to: 2, castle: 'q' });
            }
          }
        } else {
          const offsets = type === BISHOP ? BISHOP_OFFSETS :
                          type === ROOK ? ROOK_OFFSETS : QUEEN_OFFSETS;
          for (const offset of offsets) {
            let to = from + offset;
            while (this.isOnBoard(to) && Math.abs((to & 7) - ((to - offset) & 7)) <= 1) {
              const target = this.board[to];
              if (target === EMPTY) {
                moves.push({ from, to });
              } else {
                if (pieceColor(target) !== color) {
                  moves.push({ from, to });
                }
                break;
              }
              to += offset;
            }
          }
        }
      }

      return moves;
    }

    generateLegalMoves() {
      const pseudoMoves = this.generateMoves();
      const legal = [];
      for (const move of pseudoMoves) {
        const pos = this.clone();
        pos.makeMove(move);
        if (!pos.inCheck(this.turn)) {
          legal.push(move);
        }
      }
      return legal;
    }

    makeMove(move) {
      const piece = this.board[move.from];
      const captured = this.board[move.to];
      const type = pieceType(piece);
      const color = pieceColor(piece);

      this.history.push({
        board: new Uint8Array(this.board),
        castling: [...this.castling],
        epSquare: this.epSquare,
        halfmove: this.halfmove,
        captured
      });

      this.board[move.to] = piece;
      this.board[move.from] = EMPTY;

      if (type === PAWN && move.to === this.epSquare) {
        const capturedPawnSq = move.to + (color === WHITE ? 8 : -8);
        this.board[capturedPawnSq] = EMPTY;
      }

      if (move.promotion) {
        this.board[move.to] = makePiece(color, move.promotion);
      }

      if (move.castle) {
        if (move.castle === 'K') { this.board[61] = this.board[63]; this.board[63] = EMPTY; }
        if (move.castle === 'Q') { this.board[59] = this.board[56]; this.board[56] = EMPTY; }
        if (move.castle === 'k') { this.board[5] = this.board[7]; this.board[7] = EMPTY; }
        if (move.castle === 'q') { this.board[3] = this.board[0]; this.board[0] = EMPTY; }
      }

      this.epSquare = -1;
      if (type === PAWN && Math.abs(move.to - move.from) === 16) {
        this.epSquare = (move.from + move.to) / 2;
      }

      if (move.from === 60 || move.to === 60) { this.castling[0] = false; this.castling[1] = false; }
      if (move.from === 4 || move.to === 4) { this.castling[2] = false; this.castling[3] = false; }
      if (move.from === 63 || move.to === 63) this.castling[0] = false;
      if (move.from === 56 || move.to === 56) this.castling[1] = false;
      if (move.from === 7 || move.to === 7) this.castling[2] = false;
      if (move.from === 0 || move.to === 0) this.castling[3] = false;

      if (type === PAWN || captured !== EMPTY) {
        this.halfmove = 0;
      } else {
        this.halfmove++;
      }

      if (color === BLACK) this.fullmove++;
      this.turn = 1 - this.turn;
    }

    unmakeMove() {
      if (this.history.length === 0) return;
      const h = this.history.pop();
      this.board = h.board;
      this.castling = h.castling;
      this.epSquare = h.epSquare;
      this.halfmove = h.halfmove;
      this.turn = 1 - this.turn;
      if (this.turn === BLACK) this.fullmove--;
    }

    evaluate() {
      let score = 0;
      let whiteMaterial = 0, blackMaterial = 0;

      for (let sq = 0; sq < 64; sq++) {
        const piece = this.board[sq];
        if (piece === EMPTY) continue;
        const color = pieceColor(piece);
        const type = pieceType(piece);
        const value = PIECE_VALUES[type];

        if (color === WHITE) {
          whiteMaterial += value;
        } else {
          blackMaterial += value;
        }

        const pstIndex = color === WHITE ? sq : mirrorSquare(sq);
        const pstValue = PST[type] ? PST[type][pstIndex] : 0;

        if (color === WHITE) {
          score += value + pstValue;
        } else {
          score -= value + pstValue;
        }
      }

      const totalMaterial = whiteMaterial + blackMaterial - 40000;
      const isEndgame = totalMaterial < 2600;

      if (isEndgame) {
        for (let sq = 0; sq < 64; sq++) {
          const piece = this.board[sq];
          if (piece === EMPTY) continue;
          if (pieceType(piece) === KING) {
            const color = pieceColor(piece);
            const pstIndex = color === WHITE ? sq : mirrorSquare(sq);
            const midVal = PST_KING_MID[pstIndex];
            const endVal = PST_KING_END[pstIndex];
            const adjustment = endVal - midVal;
            score += color === WHITE ? adjustment : -adjustment;
          }
        }
      }

      const mobilityMoves = this.generateMoves().length;
      const savedTurn = this.turn;
      this.turn = 1 - this.turn;
      const oppMoves = this.generateMoves().length;
      this.turn = savedTurn;

      const mobilityScore = (mobilityMoves - oppMoves) * 3;
      score += this.turn === WHITE ? mobilityScore : -mobilityScore;

      return this.turn === WHITE ? score : -score;
    }

    isGameOver() {
      const legal = this.generateLegalMoves();
      if (legal.length === 0) {
        if (this.inCheck(this.turn)) {
          return { over: true, result: 'checkmate', winner: 1 - this.turn };
        }
        return { over: true, result: 'stalemate', winner: -1 };
      }
      if (this.halfmove >= 100) {
        return { over: true, result: 'draw', winner: -1 };
      }
      return { over: false };
    }
  }

  class Engine {
    constructor() {
      this.nodes = 0;
      this.maxDepth = 5;
      this.bestMove = null;
      this.analysisLines = [];
    }

    moveToAlgebraic(move) {
      let str = squareName(move.from) + squareName(move.to);
      if (move.promotion) {
        const promoChars = [null, null, 'n', 'b', 'r', 'q'];
        str += promoChars[move.promotion];
      }
      return str;
    }

    moveToSAN(pos, move) {
      const type = pieceType(pos.board[move.from]);
      const captured = pos.board[move.to] !== EMPTY ||
                       (type === PAWN && move.to === pos.epSquare);
      const pieceNames = ['', '', 'N', 'B', 'R', 'Q', 'K'];
      let san = '';

      if (move.castle === 'K' || move.castle === 'k') return 'O-O';
      if (move.castle === 'Q' || move.castle === 'q') return 'O-O-O';

      if (type !== PAWN) {
        san += pieceNames[type];
        const legal = pos.generateLegalMoves();
        const ambiguous = legal.filter(m =>
          m.to === move.to && m.from !== move.from &&
          pieceType(pos.board[m.from]) === type
        );
        if (ambiguous.length > 0) {
          const sameFile = ambiguous.some(m => (m.from & 7) === (move.from & 7));
          const sameRank = ambiguous.some(m => (m.from >> 3) === (move.from >> 3));
          if (!sameFile) {
            san += String.fromCharCode(97 + (move.from & 7));
          } else if (!sameRank) {
            san += (8 - (move.from >> 3));
          } else {
            san += squareName(move.from);
          }
        }
      }

      if (captured) {
        if (type === PAWN) san += String.fromCharCode(97 + (move.from & 7));
        san += 'x';
      }

      san += squareName(move.to);

      if (move.promotion) {
        const promoNames = [null, null, 'N', 'B', 'R', 'Q'];
        san += '=' + promoNames[move.promotion];
      }

      const testPos = pos.clone();
      testPos.makeMove(move);
      if (testPos.inCheck(testPos.turn)) {
        const hasLegal = testPos.generateLegalMoves().length > 0;
        san += hasLegal ? '+' : '#';
      }

      return san;
    }

    quiesce(pos, alpha, beta) {
      this.nodes++;
      const standPat = pos.evaluate();

      if (standPat >= beta) return beta;
      if (standPat > alpha) alpha = standPat;

      const moves = pos.generateLegalMoves().filter(m =>
        pos.board[m.to] !== EMPTY || m.promotion ||
        (pieceType(pos.board[m.from]) === PAWN && m.to === pos.epSquare)
      );

      this.orderMoves(pos, moves);

      for (const move of moves) {
        pos.makeMove(move);
        const score = -this.quiesce(pos, -beta, -alpha);
        pos.unmakeMove();

        if (score >= beta) return beta;
        if (score > alpha) alpha = score;
      }

      return alpha;
    }

    orderMoves(pos, moves) {
      moves.sort((a, b) => {
        let scoreA = 0, scoreB = 0;

        if (pos.board[a.to] !== EMPTY) {
          scoreA += PIECE_VALUES[pieceType(pos.board[a.to])] -
                    PIECE_VALUES[pieceType(pos.board[a.from])] / 10;
        }
        if (pos.board[b.to] !== EMPTY) {
          scoreB += PIECE_VALUES[pieceType(pos.board[b.to])] -
                    PIECE_VALUES[pieceType(pos.board[b.from])] / 10;
        }
        if (a.promotion) scoreA += PIECE_VALUES[a.promotion];
        if (b.promotion) scoreB += PIECE_VALUES[b.promotion];

        return scoreB - scoreA;
      });
    }

    alphaBeta(pos, depth, alpha, beta, isRoot) {
      if (depth <= 0) return this.quiesce(pos, alpha, beta);

      this.nodes++;
      const moves = pos.generateLegalMoves();

      if (moves.length === 0) {
        if (pos.inCheck(pos.turn)) return -99999 + (this.maxDepth - depth);
        return 0;
      }

      this.orderMoves(pos, moves);

      let bestScore = -Infinity;
      for (const move of moves) {
        pos.makeMove(move);
        const score = -this.alphaBeta(pos, depth - 1, -beta, -alpha, false);
        pos.unmakeMove();

        if (score > bestScore) {
          bestScore = score;
          if (isRoot) this.bestMove = move;
        }
        if (score > alpha) alpha = score;
        if (alpha >= beta) break;
      }

      return bestScore;
    }

    analyze(fen, depth) {
      this.maxDepth = depth || 5;
      this.nodes = 0;
      this.bestMove = null;
      this.analysisLines = [];

      const pos = new Position().loadFEN(fen);
      const moves = pos.generateLegalMoves();

      if (moves.length === 0) {
        return {
          bestMove: null,
          evaluation: 0,
          lines: [],
          threats: [],
          gameOver: pos.isGameOver()
        };
      }

      this.orderMoves(pos, moves);

      const scored = [];
      for (const move of moves) {
        pos.makeMove(move);
        const score = -this.alphaBeta(pos, this.maxDepth - 1, -Infinity, Infinity, false);
        pos.unmakeMove();
        scored.push({ move, score, san: this.moveToSAN(pos, move) });
      }

      scored.sort((a, b) => b.score - a.score);

      const best = scored[0];
      this.bestMove = best.move;

      const lines = scored.slice(0, 5).map((s, i) => ({
        rank: i + 1,
        move: this.moveToAlgebraic(s.move),
        san: s.san,
        score: s.score,
        evaluation: this.formatEval(s.score),
        from: s.move.from,
        to: s.move.to
      }));

      const threats = this.findThreats(pos);
      const tactics = this.findTactics(pos, scored);

      return {
        bestMove: {
          from: squareName(best.move.from),
          to: squareName(best.move.to),
          san: best.san,
          algebraic: this.moveToAlgebraic(best.move),
          fromSquare: best.move.from,
          toSquare: best.move.to
        },
        evaluation: this.formatEval(best.score),
        rawScore: best.score,
        lines,
        threats,
        tactics,
        nodes: this.nodes,
        depth: this.maxDepth,
        turn: pos.turn === WHITE ? 'white' : 'black'
      };
    }

    formatEval(score) {
      if (Math.abs(score) > 90000) {
        const mate = Math.ceil((99999 - Math.abs(score)) / 2);
        return score > 0 ? `M${mate}` : `-M${mate}`;
      }
      return (score / 100).toFixed(2);
    }

    findThreats(pos) {
      const threats = [];
      const oppPos = pos.clone();
      oppPos.turn = 1 - oppPos.turn;
      const oppMoves = oppPos.generateLegalMoves();

      for (const move of oppMoves) {
        const target = oppPos.board[move.to];
        if (target !== EMPTY && pieceColor(target) !== oppPos.turn) {
          const attackerType = pieceType(oppPos.board[move.from]);
          const targetType = pieceType(target);

          if (PIECE_VALUES[targetType] >= PIECE_VALUES[attackerType] ||
              targetType === KING) {
            const isProtected = pos.isSquareAttacked(move.to, pos.turn);
            threats.push({
              type: targetType === KING ? 'check' : 'capture',
              attacker: squareName(move.from),
              target: squareName(move.to),
              attackerPiece: this.pieceTypeName(attackerType),
              targetPiece: this.pieceTypeName(targetType),
              protected: isProtected,
              severity: targetType === KING ? 'critical' :
                        PIECE_VALUES[targetType] >= 500 ? 'high' : 'medium',
              fromSquare: move.from,
              toSquare: move.to
            });
          }
        }
      }

      const seen = new Set();
      return threats.filter(t => {
        const key = t.attacker + t.target;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).sort((a, b) => {
        const sev = { critical: 3, high: 2, medium: 1 };
        return (sev[b.severity] || 0) - (sev[a.severity] || 0);
      }).slice(0, 5);
    }

    findTactics(pos, scoredMoves) {
      const tactics = [];

      if (scoredMoves.length >= 2) {
        const gap = scoredMoves[0].score - scoredMoves[1].score;
        if (gap > 150) {
          tactics.push({
            type: 'only_move',
            description: `${scoredMoves[0].san} is clearly the best move (${this.formatEval(gap)} better than alternatives)`
          });
        }
      }

      const bestMove = scoredMoves[0];
      const targetPiece = pos.board[bestMove.move.to];
      if (targetPiece !== EMPTY) {
        const capValue = PIECE_VALUES[pieceType(targetPiece)];
        const attackValue = PIECE_VALUES[pieceType(pos.board[bestMove.move.from])];
        if (capValue > attackValue) {
          tactics.push({
            type: 'winning_capture',
            description: `${bestMove.san} wins material (${this.pieceTypeName(pieceType(pos.board[bestMove.move.from]))} takes ${this.pieceTypeName(pieceType(targetPiece))})`
          });
        }
      }

      if (pos.inCheck(pos.turn)) {
        tactics.push({
          type: 'in_check',
          description: 'You are in check - must respond to the threat'
        });
      }

      const testPos = pos.clone();
      testPos.makeMove(bestMove.move);
      if (testPos.inCheck(testPos.turn)) {
        tactics.push({
          type: 'gives_check',
          description: `${bestMove.san} gives check`
        });
      }

      return tactics;
    }

    pieceTypeName(type) {
      return ['', 'Pawn', 'Knight', 'Bishop', 'Rook', 'Queen', 'King'][type];
    }
  }

  return { Position, Engine, WHITE, BLACK, squareName, squareFromName };
})();

if (typeof window !== 'undefined') {
  window.ChessEngine = ChessEngine;
}
