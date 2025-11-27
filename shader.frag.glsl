#version 140

in vec2 TexCoord; // Wird hier nicht direkt verwendet, Mapping übernimmt die Logik!
out vec4 FragColor;

// --- YUV-Textures ---
uniform sampler2D texY;   // Y-Komponente
uniform sampler2D texUV;  // UV-Komponente

// --- Mosaik-/Segment-Uniforms ---
//uniform int segmentIndex; // 1-16: Quellbereich
const int segmentIndex = 1 ; // 1-16: Quellbereich
const vec2 fullInputSize = vec2(3840.0, 2160.0);
const int segmentsX = 4;
const int segmentsY = 4;
const vec2 subBlockSize = vec2(960.0, 540.0);

// --- Kachelgrößen/Abstände im Ausgangsbild ---
const float tileW = 96.0;
const float tileH = 108.0;
const float spacingX = 133.0;
const float spacingY = 135.0;
const float marginX = 3.0;
const int numTilesPerRow = 10;
const int numTilesPerCol = 5;

// Kalibrierungsparameter fuer 3 Panel mit 150 Masterpixel
const ivec2 offsetxy1[150]=ivec2[150](
// Modul 1
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
// Modul 2
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
// Modul 3
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6),
ivec2(1,1),ivec2(2,2),ivec2(3,3),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(4,4),ivec2(5,5),ivec2(6,6),ivec2(6,6));

// --- YUV-Parameter ---
uniform int uv_swap;      // 0 = U in .r, V in .g ; 1 = swapped
uniform int full_range;   // 0 = limited (video), 1 = full (pc)
uniform int use_bt709;    // 1 = BT.709, 0 = BT.601
uniform int view_mode;    // 0 = normal, 1 = show Y, 2 = show U, 3 = show V

// --- Mapping: OpenGL 3.1+; gl_FragCoord.xy integer Pixelposition im Zielbild! ---
void main()
{
    vec2 outPx = gl_FragCoord.xy;

    // --- Subblock berechnen ---
    int segIdx = clamp(segmentIndex, 1, 16) - 1;
    int segCol = segIdx % segmentsX;
    int segRow = segIdx / segmentsX;
    vec2 subBlockOrigin = vec2(float(segCol) * subBlockSize.x, float(segRow) * subBlockSize.y);

    // --- Kachelbereich berechnen ---
    int tileCol = int((outPx.x - marginX) / (tileW + spacingX));
    int tileRow = int(outPx.y / (tileH + spacingY));
    float tileStartX = marginX + float(tileCol) * (tileW + spacingX);
    float tileStartY = float(tileRow) * (tileH + spacingY);

    bool inTile = outPx.x >= tileStartX && outPx.x < tileStartX + tileW &&
    outPx.y >= tileStartY && outPx.y < tileStartY + tileH;

    // --- Zwischenraum: leer/schwarz ---
    if (!(inTile && tileCol < numTilesPerRow && tileRow < numTilesPerCol)) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    // --- Offset innerhalb der Kachel ---
    float pxInTileX = outPx.x - tileStartX;
    float pxInTileY = outPx.y - tileStartY;

    // --- Position im Quellsubblock ---
    float fetchX = tileW * float(tileCol) + pxInTileX;
    float fetchY = tileH * float(tileRow) + pxInTileY;
    vec2 inputCoord = subBlockOrigin + vec2(fetchX, fetchY);

    // --- Texturkoordinaten auf [0,1] ---
    vec2 inputUVCoord = inputCoord / fullInputSize;

    // --- YUV Sample ---
    float Y = texture(texY, inputUVCoord).r * 255.0;
    vec2 uv = texture(texUV, inputUVCoord).rg * 255.0;

    float U = uv.x;
    float V = uv.y;
    if (uv_swap == 1) { float tmp = U; U = V; V = tmp; }

    // --- Debugkanal-View ---
    if (view_mode == 1) {
        float yy = clamp(Y / 255.0, 0.0, 1.0);
        FragColor = vec4(vec3(yy), 1.0);
        return;
    } else if (view_mode == 2) {
        float uu = clamp((U - 128.0) / 256.0 + 0.5, 0.0, 1.0);
        FragColor = vec4(vec3(uu), 1.0);
        return;
    } else if (view_mode == 3) {
        float vv = clamp((V - 128.0) / 256.0 + 0.5, 0.0, 1.0);
        FragColor = vec4(vec3(vv), 1.0);
        return;
    }

    // --- YUV→RGB Umwandlung wie bei dir ---
    float y;
    if (full_range == 1) y = Y;
    else y = 1.164383 * (Y - 16.0);

    float u = U - 128.0;
    float v = V - 128.0;

    vec3 rgb;
    if (use_bt709 == 1) {
        float r = y + 1.792741 * v;
        float g = y - 0.213249 * u - 0.532909 * v;
        float b = y + 2.112402 * u;
        rgb = vec3(r, g, b);
    } else {
        float r = y + 1.596027 * v;
        float g = y - 0.391762 * u - 0.812968 * v;
        float b = y + 2.017232 * u;
        rgb = vec3(r, g, b);
    }

    rgb = clamp(rgb / 255.0, vec3(0.0), vec3(1.0));

    FragColor = vec4(rgb, 1.0);
}
/*
in vec2 TexCoord;
out vec4 FragColor;

uniform sampler2D texY;   // unit 0, GL_R8 (Y)
uniform sampler2D texUV;  // unit 1, GL_RG8 (U,V)
uniform int uv_swap;      // 0 = U in .r, V in .g ; 1 = swapped
uniform int full_range;   // 0 = limited (video), 1 = full (pc)
uniform int use_bt709;    // 1 = BT.709, 0 = BT.601
uniform int view_mode;    // 0 = normal, 1 = show Y, 2 = show U, 3 = show V

// Helper: do YUV->RGB with choice of matrix and range
vec3 yuv_to_rgb(float Y, float U, float V) {
    float y;
    if (full_range == 1) y = Y;
    else y = 1.164383 * (Y - 16.0); // scale limited-range Y

    float u = U - 128.0;
    float v = V - 128.0;

    vec3 rgb;
    if (use_bt709 == 1) {
        // BT.709 coefficients
        float r = y + 1.792741 * v;
        float g = y - 0.213249 * u - 0.532909 * v;
        float b = y + 2.112402 * u;
        rgb = vec3(r, g, b);
    } else {
        // BT.601 coefficients
        float r = y + 1.596027 * v;
        float g = y - 0.391762 * u - 0.812968 * v;
        float b = y + 2.017232 * u;
        rgb = vec3(r, g, b);
    }
    return rgb / 255.0;
}

void main() {
    // Read textures (0..1) -> scale to 0..255
    float Y = texture(texY, TexCoord).r * 255.0;
    vec2 uv = texture(texUV, TexCoord).rg * 255.0;
    float U = uv.x;
    float V = uv.y;
    if (uv_swap == 1) {
        float tmp = U; U = V; V = tmp;
    }

    // debug single-channel views
    if (view_mode == 1) {
        float yy = clamp(Y / 255.0, 0.0, 1.0);
        FragColor = vec4(vec3(yy), 1.0);
        return;
    } else if (view_mode == 2) {
        float uu = clamp((U - 128.0) / 256.0 + 0.5, 0.0, 1.0);
        FragColor = vec4(vec3(uu), 1.0);
        return;
    } else if (view_mode == 3) {
        float vv = clamp((V - 128.0) / 256.0 + 0.5, 0.0, 1.0);
        FragColor = vec4(vec3(vv), 1.0);
        return;
    }

    vec3 rgb = yuv_to_rgb(Y, U, V);

    FragColor = vec4(clamp(rgb, vec3(0.0), vec3(1.0)), 1.0);
}
*/