// Procedural pixel-art sprite generation for 16 persona types

const SPRITE_SIZE = 16;
const SCALE = 3; // 16*3 = 48px display size

// Base palettes keyed by hue family extracted from persona colors
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

function rgbToStr(r, g, b) {
  return `rgb(${r},${g},${b})`;
}

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

function makePalette(hex) {
  const c = hexToRgb(hex);
  const dark = rgbToStr(lerp(c.r, 0, 0.6), lerp(c.g, 0, 0.6), lerp(c.b, 0, 0.6));
  const mid = hex;
  const light = rgbToStr(
    Math.min(255, lerp(c.r, 255, 0.5)),
    Math.min(255, lerp(c.g, 255, 0.5)),
    Math.min(255, lerp(c.b, 255, 0.5))
  );
  const skin = '#F5D0A9';
  const skinShadow = '#D4A574';
  const white = '#FFFFFF';
  const black = '#1a1a2e';
  const accent = rgbToStr(
    Math.min(255, c.r + 40),
    Math.min(255, c.g + 20),
    Math.min(255, c.b + 30)
  );
  return { dark, mid, light, skin, skinShadow, white, black, accent };
}

// Face patterns for different moods - 3x5 pixel grids for eyes + mouth
const FACE_PATTERNS = {
  confident: {
    eyes: [
      [0,1,0, 0,1,0], // left eye, gap, right eye
      [1,1,1, 0,1,1,1],
      [0,0,0, 0,0,0,0],
    ],
    mouth: [
      [0,1,1,0],
      [0,0,0,0],
    ],
  },
  calm: {
    eyes: [
      [0,1,0, 0,0,1,0],
      [0,1,0, 0,0,1,0],
      [0,0,0, 0,0,0,0],
    ],
    mouth: [
      [0,0,0,0],
      [0,1,1,0],
    ],
  },
  worried: {
    eyes: [
      [0,1,0, 0,0,1,0],
      [1,0,0, 0,0,0,1],
      [0,0,0, 0,0,0,0],
    ],
    mouth: [
      [1,0,0,1],
      [0,1,1,0],
    ],
  },
  excited: {
    eyes: [
      [1,0,1, 0,1,0,1],
      [0,1,0, 0,0,1,0],
      [0,0,0, 0,0,0,0],
    ],
    mouth: [
      [1,1,1,1],
      [0,1,1,0],
      [0,0,0,0],
    ],
  },
  panicked: {
    eyes: [
      [1,1,1, 0,1,1,1],
      [1,0,1, 0,1,0,1],
      [0,0,0, 0,0,0,0],
    ],
    mouth: [
      [1,1,1,1],
      [1,0,0,1],
      [0,1,1,0],
    ],
  },
};

// Hair style variations
const HAIR_STYLES = {};
function generateHairStyle(seed) {
  // Use a simple deterministic pattern based on seed
  const hair = [];
  const variants = [
    // Short flat
    [
      [0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0],
      [0,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
    ],
    // Spiky
    [
      [0,0,0,1,0,0,1,0,0,1,0,0,1,0,0,0],
      [0,0,1,1,1,0,1,1,0,1,1,0,1,1,0,0],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    ],
    // Side swept
    [
      [0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0],
      [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    ],
    // Round afro
    [
      [0,0,1,1,1,1,1,1,1,1,1,1,1,0,0,0],
      [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
      [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
      [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
      [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    ],
  ];
  return variants[seed % variants.length];
}

// Hair colors matched to persona color warmth
function getHairColor(hex) {
  const c = hexToRgb(hex);
  // Warm colors -> brown hair, cool -> black/blonde
  if (c.r > c.b + 30) {
    return '#6B4226'; // brown
  } else if (c.b > c.r + 30) {
    return '#F0D060'; // blonde
  } else {
    return '#3a3a4a'; // dark
  }
}

// Build a complete 16x16 sprite pixel grid
function buildSpriteData(mood, colorHex, hairSeed) {
  const palette = makePalette(colorHex);
  const hairColor = getHairColor(colorHex);
  const face = FACE_PATTERNS[mood] || FACE_PATTERNS.calm;
  const hair = generateHairStyle(hairSeed);

  const grid = Array.from({ length: SPRITE_SIZE }, () => Array(SPRITE_SIZE).fill(null));

  // Hair (top rows)
  for (let row = 0; row < hair.length && row < SPRITE_SIZE; row++) {
    for (let col = 0; col < SPRITE_SIZE; col++) {
      if (hair[row][col]) {
        grid[row][col] = hairColor;
      }
    }
  }

  // Face (rows 4-13)
  const faceStart = 4;
  for (let r = faceStart; r < 14; r++) {
    for (let c = 2; c < 14; c++) {
      if (!grid[r][c]) {
        grid[r][c] = palette.skin;
      }
    }
  }
  // Face outline
  for (let c = 3; c < 13; c++) {
    if (!grid[3][c]) grid[3][c] = palette.skinShadow;
    if (!grid[14][c]) grid[14][c] = palette.skinShadow;
  }
  for (let r = 4; r < 14; r++) {
    if (!grid[r][2]) grid[r][2] = palette.skinShadow;
    if (!grid[r][13]) grid[r][13] = palette.skinShadow;
  }

  // Eyes (row 7-8, col 4-10)
  const eyeRow = 7;
  for (let i = 0; i < face.eyes.length; i++) {
    const r = eyeRow + i;
    for (let ci = 0; ci < face.eyes[i].length; ci++) {
      const c = 4 + ci;
      if (face.eyes[i][ci] && r < SPRITE_SIZE && c < SPRITE_SIZE) {
        grid[r][c] = palette.black;
      }
    }
  }

  // Mouth (row 11-12, col 6-9)
  const mouthRow = 11;
  for (let i = 0; i < face.mouth.length; i++) {
    for (let ci = 0; ci < face.mouth[i].length; ci++) {
      const r = mouthRow + i;
      const c = 6 + ci;
      if (r < SPRITE_SIZE && c < SPRITE_SIZE && face.mouth[i][ci]) {
        grid[r][c] = palette.black;
      }
    }
  }

  // Body / shoulders (rows 14-15)
  for (let r = 14; r < SPRITE_SIZE; r++) {
    for (let c = 3; c < 13; c++) {
      if (!grid[r][c]) {
        grid[r][c] = palette.mid;
      }
    }
  }

  // Fill null cells with transparent
  for (let r = 0; r < SPRITE_SIZE; r++) {
    for (let c = 0; c < SPRITE_SIZE; c++) {
      if (!grid[r][c]) {
        grid[r][c] = null;
      }
    }
  }

  return { grid, palette, hairColor };
}

function drawPersonaSprite(ctx, x, y, mood, colorHex, hairSeed) {
  const sprite = buildSpriteData(mood, colorHex, hairSeed);
  const pxSize = SCALE;

  for (let r = 0; r < SPRITE_SIZE; r++) {
    for (let c = 0; c < SPRITE_SIZE; c++) {
      if (sprite.grid[r][c]) {
        ctx.fillStyle = sprite.grid[r][c];
        ctx.fillRect(x + c * pxSize, y + r * pxSize, pxSize, pxSize);
      }
    }
  }

  return sprite;
}

// Generate a hair seed from persona ID string
function hairSeedFromId(id) {
  let sum = 0;
  for (let i = 0; i < id.length; i++) {
    sum += id.charCodeAt(i);
  }
  return sum;
}
