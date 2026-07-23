# Chess Coach - Browser Extension for chess.com

A Chrome extension that analyzes your chess.com games in real-time, showing you the best moves, opponent threats, and learning tips to help you improve your ELO.

## Features

- **Best Move Analysis** - See the strongest move in any position with evaluation score
- **Top 5 Move Ranking** - Compare alternative moves and understand why one is better
- **Threat Detection** - See what your opponent is threatening before it's too late
- **Tactical Alerts** - Get notified about winning captures, checks, and critical moments
- **Learning Tips** - Context-aware advice that teaches chess principles as you play
- **Board Arrows** - Green arrows for best moves, blue for alternatives, red for threats
- **Auto-Analysis** - Automatically analyzes after every move (toggle on/off)
- **Draggable Panel** - Position the analysis panel wherever you want
- **Adjustable Depth** - Choose analysis depth (3-7) to balance speed vs strength

## Installation

1. Download or clone this repository
2. Open Chrome and go to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top-right)
4. Click **Load unpacked**
5. Select the `chess-coach-extension` folder
6. Navigate to chess.com and start a game - the coach panel appears automatically

## How to Use

### During a Game
1. The analysis panel appears on the right side of the screen
2. After each move, the engine automatically analyzes the position
3. **Green arrow** on the board = best move for you
4. **Blue arrows** = strong alternative moves
5. **Red arrows** = opponent's threats to watch out for

### Panel Sections
- **Best Move** - The strongest move with its evaluation
- **Top Moves** - Hover over any line to highlight it on the board
- **Opponent Threats** - Pieces your opponent can capture or checks they can deliver
- **Tactical Notes** - Special situations like forced moves or winning captures
- **Learning Tip** - Advice based on the position type

### Settings (Popup)
Click the extension icon to:
- Enable/disable the coach
- Toggle auto-analysis
- Show/hide board arrows
- Adjust analysis depth

## How It Helps You Improve

1. **Before moving**: Check what the engine suggests and compare it to your idea
2. **Threat awareness**: Train yourself to spot opponent threats by reviewing the threats panel
3. **Pattern recognition**: The tactical notes help you recognize common patterns
4. **Learning tips**: Understand positional concepts like when to trade pieces, how to play winning/losing positions
5. **Post-game review**: Use with analysis board to review your games move by move

## Technical Details

- Built-in JavaScript chess engine with alpha-beta search and quiescence
- Piece-square tables for positional evaluation
- Mobility scoring for piece activity
- No external dependencies or network calls - everything runs locally
- Works with live games, daily games, and analysis board on chess.com

## Analysis Depth Guide

| Depth | Speed | Strength | Best For |
|-------|-------|----------|----------|
| 3 | Instant | Basic tactics | Bullet games |
| 4 | Fast | Good tactics | Blitz games |
| 5 | Normal | Strong tactics | Rapid games (default) |
| 6 | Slow | Deep analysis | Post-game review |
| 7 | Very slow | Thorough | Deep analysis |
