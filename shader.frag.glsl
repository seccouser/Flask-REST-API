#version 140

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