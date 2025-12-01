#version 140

in vec2 TexCoord;
out vec4 FragColor;

uniform sampler2D texY;
uniform sampler2D texUV;
uniform sampler2D texPattern;   // new: test pattern RGB texture (unit 2)

uniform int segmentIndex; // 1..16
uniform vec2 u_fullInputSize;    // e.g. 3840,2160
uniform int  u_segmentsX;
uniform int  u_segmentsY;
uniform vec2 u_subBlockSize;     // e.g. 1280,2160

uniform float u_tileW;           // 128
uniform float u_tileH;           // 144
uniform float u_spacingX;        // controlled by control_ini (use as-is)
uniform float u_spacingY;        // controlled by control_ini (use as-is)
uniform float u_marginX;         // left margin
uniform int   u_numTilesPerRow;  // 10
uniform int   u_numTilesPerCol;  // 15

uniform ivec2 offsetxy1[150];

uniform int rot;
uniform int flip_x;
uniform int flip_y;

uniform int gap_count;
uniform int gap_rows[8];

uniform int inputTilesTopToBottom;

uniform int uv_swap;
uniform int full_range;
uniform int use_bt709;
uniform int view_mode;

uniform int u_textureIsFull;     // 1 = full input texture bound, 0 = subblock
uniform vec2 u_windowSize;       // SDL window in pixels
uniform vec2 u_outputSize;       // legacy / fallback
uniform int  u_alignTopLeft;     // 1 = align top-left, 0 = center

uniform int u_showPattern;       // 1 = show pattern (no input), 0 = normal

// helper: rotate a point (u,v) around center (0.5,0.5) by k*90deg clockwise
vec2 rotate90_centered(vec2 uv, int k) {
    vec2 c = vec2(0.5, 0.5);
    vec2 p = uv - c;
    vec2 r;
    int kk = k & 3;
    if (kk == 0) r = p;
    else if (kk == 1) r = vec2(p.y, -p.x);
    else if (kk == 2) r = vec2(-p.x, -p.y);
    else r = vec2(-p.y, p.x);
    return r + c;
}

bool isGapZero(int gapIdx) {
    for (int i = 0; i < 8; ++i) {
        if (i >= gap_count) break;
        if (gap_rows[i] == gapIdx) return true;
    }
    return false;
}

// compute total grid height considering vertical gaps (exact pixel values from control_ini)
float computeTotalGridHeight(int numRows, float tileH, float spacingY) {
    float h = 0.0;
    for (int r = 0; r < numRows; ++r) {
        h += tileH;
        if (r < numRows - 1) {
            if (!isGapZero(r + 1)) h += spacingY;
        }
    }
    return h;
}

vec3 tileIndexToColor(int idx) {
    float r = float((idx * 37) & 0xFF) / 255.0;
    float g = float((idx * 73) & 0xFF) / 255.0;
    float b = float((idx * 151) & 0xFF) / 255.0;
    return vec3(r,g,b);
}

void main()
{
    // If test pattern requested, render it immediately (pattern texture if bound, else procedural)
    if (u_showPattern == 1) {
        // If a pattern texture is provided (bound to unit 2), show it.
        // We invert v so user-supplied images map naturally.
        vec4 tcol = texture(texPattern, vec2(TexCoord.x, 1.0 - TexCoord.y));
        // If pattern texture is empty or not provided (will sample black), fall back to procedural.
        if (tcol.r > 0.0 || tcol.g > 0.0 || tcol.b > 0.0) {
            FragColor = tcol;
            return;
        }
        // Procedural fallback pattern: three vertical columns (red, green, blue) with white tile borders.
        // Use u_outputSize/u_tileW to draw grid-like tiles similar to your test image.
        float tileW = u_tileW;
        float tileH = u_tileH;
        float spacingX = u_spacingX;
        float spacingY = u_spacingY;
        float marginX = u_marginX;
        vec2 win = max(u_windowSize, vec2(1.0));
        vec2 grid = vec2(2.0 * marginX + float(u_numTilesPerRow) * tileW + float(u_numTilesPerRow - 1) * spacingX,
                         computeTotalGridHeight(u_numTilesPerCol, tileH, spacingY));
        // Map TexCoord to logical coordinates (approx)
        vec2 px = TexCoord * win;
        // Determine column in 3 vertical bands
        float band = floor(3.0 * px.x / win.x);
        vec3 col = vec3(0.5,0.0,0.0);
        if (band < 1.0) col = vec3(0.8, 0.1, 0.1);
        else if (band < 2.0) col = vec3(0.1, 0.8, 0.1);
        else col = vec3(0.15, 0.15, 0.9);
        // draw thin white grid lines: create virtual tile coordinates
        float gx = mod(px.x, tileW + spacingX);
        float gy = mod(px.y, tileH + spacingY);
        if (gx < 2.0 || gy < 2.0) {
            FragColor = vec4(1.0,1.0,1.0,1.0);
        } else {
            FragColor = vec4(col, 1.0);
        }
        return;
    }

    // --- Compute logical grid size from control params (use spacing exactly as given) ---
    float gridW = 2.0 * u_marginX + float(u_numTilesPerRow) * u_tileW + float(u_numTilesPerRow - 1) * u_spacingX;
    float gridH = computeTotalGridHeight(u_numTilesPerCol, u_tileH, u_spacingY);

    // --- Determine integer scale to map logical grid onto window pixels ---
    vec2 win = max(u_windowSize, vec2(1.0));
    vec2 grid = max(vec2(gridW, gridH), vec2(1.0));
    float sx = floor(win.x / grid.x);
    float sy = floor(win.y / grid.y);
    float scale = max(1.0, min(sx, sy));
    vec2 usedPx = grid * scale;

    vec2 origin;
    if (u_alignTopLeft == 1) {
        origin = vec2(0.0, win.y - usedPx.y);
    } else {
        origin = (win - usedPx) * 0.5;
    }

    vec2 winPx = gl_FragCoord.xy;
    vec2 logicalBottom = (winPx - origin) / scale;

    if (logicalBottom.x < 0.0 || logicalBottom.y < 0.0 || logicalBottom.x >= grid.x || logicalBottom.y >= grid.y) {
        FragColor = vec4(0.0,0.0,0.0,1.0);
        return;
    }

    vec2 outPxTL = vec2(logicalBottom.x, grid.y - 1.0 - logicalBottom.y);

    int segIdx = clamp(segmentIndex, 1, 16) - 1;
    int segCol = segIdx % max(1, u_segmentsX);
    int segRow = segIdx / max(1, u_segmentsX);
    vec2 subBlockOrigin = vec2(float(segCol) * u_subBlockSize.x, float(segRow) * u_subBlockSize.y);

    float cellW = u_tileW + u_spacingX;
    int tileCol = int(floor((outPxTL.x - u_marginX + 1e-6) / cellW));

    int tileRow = -1;
    float yAcc = 0.0;
    for (int r = 0; r < u_numTilesPerCol; ++r) {
        float rowStart = yAcc;
        float rowEnd = rowStart + u_tileH;
        if (outPxTL.y >= rowStart && outPxTL.y < rowEnd) {
            tileRow = r;
            break;
        }
        bool gapAfter = isGapZero(r + 1);
        if (!gapAfter) yAcc = rowEnd + u_spacingY;
        else yAcc = rowEnd;
    }

    if (tileCol < 0 || tileCol >= u_numTilesPerRow || tileRow < 0 || tileRow >= u_numTilesPerCol) {
        FragColor = vec4(0.0,0.0,0.0,1.0);
        return;
    }

    float tileStartX = u_marginX + float(tileCol) * (u_tileW + u_spacingX);

    float tileStartY_top = 0.0;
    for (int r = 0; r < tileRow; ++r) {
        tileStartY_top += u_tileH;
        bool gapAfter = isGapZero(r + 1);
        if (!gapAfter) tileStartY_top += u_spacingY;
    }

    int tileIndexWithinSubblock = tileRow * u_numTilesPerRow + tileCol;
    int clampedIndex = clamp(tileIndexWithinSubblock, 0, 149);
    ivec2 off_i = offsetxy1[clampedIndex];
    float offx = float(off_i.x);
    float offy = float(off_i.y);

    vec2 tileRectStart = vec2(tileStartX, tileStartY_top);
    vec2 tileRectEnd = tileRectStart + vec2(u_tileW, u_tileH);

    if (!(outPxTL.x >= tileRectStart.x && outPxTL.x < tileRectEnd.x &&
          outPxTL.y >= tileRectStart.y && outPxTL.y < tileRectEnd.y)) {
        FragColor = vec4(0.0,0.0,0.0,1.0);
        return;
    }

    float pxInTileX = outPxTL.x - tileRectStart.x;
    float pxInTileY = outPxTL.y - tileRectStart.y;

    int sourceTileRow = inputTilesTopToBottom == 1 ? tileRow : (u_numTilesPerCol - 1 - tileRow);

    float fetchX = u_tileW * float(tileCol) + pxInTileX - offx;
    float fetchY = u_tileH * float(sourceTileRow) + pxInTileY - offy;

    float tileSrcX0 = u_tileW * float(tileCol);
    float tileSrcX1 = tileSrcX0 + u_tileW;
    float tileSrcY0 = u_tileH * float(sourceTileRow);
    float tileSrcY1 = tileSrcY0 + u_tileH;

    if (fetchX < tileSrcX0 || fetchX >= tileSrcX1 || fetchY < tileSrcY0 || fetchY >= tileSrcY1) {
        FragColor = vec4(0.0,0.0,0.0,1.0);
        return;
    }

    vec2 inputCoord = subBlockOrigin + vec2(fetchX, fetchY);
    inputCoord = clamp(inputCoord, vec2(0.0), u_fullInputSize - vec2(1.0));

    vec2 inputUV;
    if (u_textureIsFull == 1) {
        inputUV.x = inputCoord.x / u_fullInputSize.x;
        inputUV.y = 1.0 - (inputCoord.y / u_fullInputSize.y);
    } else {
        vec2 local = inputCoord - subBlockOrigin;
        inputUV.x = local.x / u_subBlockSize.x;
        inputUV.y = 1.0 - (local.y / u_subBlockSize.y);
    }
    inputUV = clamp(inputUV, vec2(0.0), vec2(1.0));

    vec2 uvTrans = rotate90_centered(inputUV, rot);
    if (flip_x == 1) uvTrans.x = 1.0 - uvTrans.x;
    if (flip_y == 1) uvTrans.y = 1.0 - uvTrans.y;
    uvTrans = clamp(uvTrans, vec2(0.0), vec2(1.0));

    if (view_mode == 1) {
        vec3 col = vec3(fract(inputUV.x * 8.0), fract((1.0 - inputUV.y) * 8.0), 0.0);
        FragColor = vec4(smoothstep(vec3(0.15), vec3(0.85), col), 1.0);
        return;
    } else if (view_mode == 2) {
        vec3 c = tileIndexToColor(tileIndexWithinSubblock);
        FragColor = vec4(c, 1.0);
        return;
    }

    float Y = texture(texY, uvTrans).r * 255.0;
    vec2 uv = texture(texUV, uvTrans).rg * 255.0;
    float U = uv.x, V = uv.y;
    if (uv_swap == 1) { float tmp = U; U = V; V = tmp; }

    float yVal = (full_range == 1) ? Y : 1.164383 * (Y - 16.0);
    float uVal = U - 128.0;
    float vVal = V - 128.0;
    vec3 rgb;
    if (use_bt709 == 1) {
        rgb.r = yVal + 1.792741 * vVal;
        rgb.g = yVal - 0.213249 * uVal - 0.532909 * vVal;
        rgb.b = yVal + 2.112402 * uVal;
    } else {
        rgb.r = yVal + 1.596027 * vVal;
        rgb.g = yVal - 0.391762 * uVal - 0.812968 * vVal;
        rgb.b = yVal + 2.017232 * uVal;
    }
    rgb = clamp(rgb / 255.0, vec3(0.0), vec3(1.0));
    FragColor = vec4(rgb, 1.0);
}
