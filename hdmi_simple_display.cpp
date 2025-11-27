// hdmi_simple_display.cpp
// Production: auto-resize, tiled uploads, V4L2 events, CLI, CPU UV-swap option, improved tiled upload reuse
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <getopt.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <cerrno>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <algorithm>
#include <GL/glew.h>
#include <SDL2/SDL.h>
#include <SDL2/SDL_opengl.h>
#include <sys/stat.h>
#include <limits.h>
#include <string>
#include <vector>
#include <fstream>
#include <sys/stat.h>
#include <limits.h>
#include <unistd.h>
#include <iostream>

#define DEVICE "/dev/video0"
#define DEFAULT_WIDTH 1920
#define DEFAULT_HEIGHT 1080
#define WINDOW_TITLE "hdmi_simple_display (OpenGL YUV Shader)"
#define BUF_COUNT 4 // MMAP buffer count

static bool opt_auto_resize_window = false;
static bool opt_cpu_uv_swap = false; // if true, do CPU swap at upload
static int opt_uv_swap_override = -1; // -1 = auto, 0/1 override
static int opt_full_range = 0; // 0 limited, 1 full
static int opt_use_bt709 = 1; // 1 = BT.709, 0 = BT.601

std::string loadShaderSource(const char* filename) {
    std::ifstream file(filename);
    return std::string((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
}

int xioctl(int fd, int req, void* arg) {
    int r;
    do { r = ioctl(fd, req, arg); } while (r == -1 && errno == EINTR);
    return r;
}

GLuint compileShader(const std::string& source, GLenum type) {
    GLuint shader = glCreateShader(type);
    const char* src = source.c_str();
    glShaderSource(shader, 1, &src, nullptr);
    glCompileShader(shader);
    GLint status;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &status);
    if (!status) {
        std::string msg;
        msg.resize(16384);
        glGetShaderInfoLog(shader, (GLsizei)msg.size(), nullptr, &msg[0]);
        std::cerr << "Shader compilation failed: " << msg << std::endl;
        exit(EXIT_FAILURE);
    }
    return shader;
}

GLuint createShaderProgram(const char* vert_path, const char* frag_path) {
    auto vert_source = loadShaderSource(vert_path);
    auto frag_source = loadShaderSource(frag_path);

    GLuint vert = compileShader(vert_source, GL_VERTEX_SHADER);
    GLuint frag = compileShader(frag_source, GL_FRAGMENT_SHADER);
    GLuint prog = glCreateProgram();
    glAttachShader(prog, vert);
    glAttachShader(prog, frag);
    glLinkProgram(prog);
    GLint status;
    glGetProgramiv(prog, GL_LINK_STATUS, &status);
    if (!status) {
        std::string msg;
        msg.resize(16384);
        glGetProgramInfoLog(prog, (GLsizei)msg.size(), nullptr, &msg[0]);
        std::cerr << "Shader link failed: " << msg << std::endl;
        exit(EXIT_FAILURE);
    }
    glDeleteShader(vert);
    glDeleteShader(frag);
    return prog;
}

struct PlaneMap { void* addr; size_t length; };

std::string fourcc_to_str(uint32_t f) {
    char s[5] = { (char)(f & 0xFF), (char)((f>>8)&0xFF), (char)((f>>16)&0xFF), (char)((f>>24)&0xFF), 0 };
    return std::string(s);
}

// Query current V4L2 format (width/height/pixelformat)
bool get_v4l2_format(int fd, uint32_t &width, uint32_t &height, uint32_t &pixelformat) {
    v4l2_format fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    if (xioctl(fd, VIDIOC_G_FMT, &fmt) < 0) {
        return false;
    }
    width = fmt.fmt.pix_mp.width;
    height = fmt.fmt.pix_mp.height;
    pixelformat = fmt.fmt.pix_mp.pixelformat;
    return true;
}

// Reallocate GL textures for new width/height and uv size (must be called in GL context)
void reallocate_textures(GLuint texY, GLuint texUV, int newW, int newH, int uvW, int uvH) {
    glBindTexture(GL_TEXTURE_2D, texY);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, newW, newH, 0, GL_RED, GL_UNSIGNED_BYTE, nullptr);

    glBindTexture(GL_TEXTURE_2D, texUV);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RG8, uvW, uvH, 0, GL_RG, GL_UNSIGNED_BYTE, nullptr);
}

// Improved tiled upload: reuse a single tile buffer to avoid repeated allocations
void upload_texture_tiled(GLenum format, GLuint tex, int srcW, int srcH,
                          const unsigned char* src, int maxTexSize, int pixelSizePerTexel) {
    // tile dims
    int tileW = std::min(srcW, maxTexSize);
    int tileH = std::min(srcH, maxTexSize);

    static std::vector<unsigned char> tileBuf; // reused across calls

    for (int y = 0; y < srcH; y += tileH) {
        int h = std::min(tileH, srcH - y);
        if (srcW <= maxTexSize) {
            const unsigned char* ptr = src + (size_t)y * (size_t)srcW * pixelSizePerTexel;
            glBindTexture(GL_TEXTURE_2D, tex);
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, y, srcW, h, format, GL_UNSIGNED_BYTE, ptr);
        } else {
            for (int x = 0; x < srcW; x += tileW) {
                int w = std::min(tileW, srcW - x);
                // prepare contiguous tile buffer
                tileBuf.resize((size_t)h * (size_t)w * pixelSizePerTexel);
                for (int row = 0; row < h; ++row) {
                    const unsigned char* srcRow = src + (size_t)(y + row) * (size_t)srcW * pixelSizePerTexel + (size_t)x * pixelSizePerTexel;
                    unsigned char* dstRow = tileBuf.data() + (size_t)row * (size_t)w * pixelSizePerTexel;
                    memcpy(dstRow, srcRow, (size_t)w * pixelSizePerTexel);
                }
                glBindTexture(GL_TEXTURE_2D, tex);
                glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
                glTexSubImage2D(GL_TEXTURE_2D, 0, x, y, w, h, format, GL_UNSIGNED_BYTE, tileBuf.data());
            }
        }
    }
}

void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog << " [options]\n"
              << "  --uv-swap=auto|0|1         (default auto) auto detect NV12/NV21 or override\n"
              << "  --range=limited|full       (default limited)\n"
              << "  --matrix=709|601           (default 709)\n"
              << "  --auto-resize-window       resize SDL window on format change\n"
              << "  --cpu-uv-swap              perform UV swap on CPU at upload and avoid runtime shader swap\n"
              << "  -h, --help                 show this help\n";
}

// --- New helpers: getExecutableDir(), fileExists(), findShaderFile() ---
static std::string getExecutableDir() {
    // Try SDL_GetBasePath() first (portable)
    char* base = SDL_GetBasePath();
    if (base) {
        std::string dir(base);
        SDL_free(base);
        if (!dir.empty() && dir.back() != '/' && dir.back() != '\\') dir.push_back('/');
        return dir;
    }

    // Fallback: try /proc/self/exe (Linux)
#if defined(__linux__)
    char buf[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (len > 0) {
        buf[len] = '\0';
        std::string path(buf);
        auto pos = path.find_last_of('/');
        if (pos != std::string::npos) return path.substr(0, pos + 1);
    }
#endif

    // Last resort: current directory
    return std::string("./");
}

static bool fileExists(const std::string &path) {
    struct stat sb;
    return (stat(path.c_str(), &sb) == 0 && S_ISREG(sb.st_mode));
}

static std::string findShaderFile(const std::string &name, std::vector<std::string>* outAttempts = nullptr) {
    if (name.empty()) return std::string();

    std::vector<std::string> candidates;

    // direct name (cwd)
    candidates.push_back(name);

    // executable dir + name and some relatives
    std::string exeDir = getExecutableDir();
    if (!exeDir.empty()) {
        candidates.push_back(exeDir + name);
        candidates.push_back(exeDir + "shaders/" + name);
        candidates.push_back(exeDir + "../" + name);           // parent of exe dir
        candidates.push_back(exeDir + "../shaders/" + name);   // parent/shaders
        candidates.push_back(exeDir + "../../shaders/" + name);// two levels up (useful for build/source layouts)
        candidates.push_back(exeDir + "assets/" + name);       // possible assets folder
    }

    // local shaders folder relative to cwd
    candidates.push_back(std::string("shaders/") + name);

    // common system-wide locations (optional)
    candidates.push_back(std::string("/usr/local/share/hdmi-in-display/shaders/") + name);
    candidates.push_back(std::string("/usr/share/hdmi-in-display/shaders/") + name);

    // record attempts if requested
    if (outAttempts) {
        outAttempts->clear();
        outAttempts->reserve(candidates.size());
    }

    for (const auto &p : candidates) {
        if (outAttempts) outAttempts->push_back(p);
        if (fileExists(p)) return p;
    }
    return std::string();
}
// --- end helpers ---

int main(int argc, char** argv) {
  static struct option longopts[] = {
    {"uv-swap", required_argument, nullptr, 0},
    {"range", required_argument, nullptr, 0},
    {"matrix", required_argument, nullptr, 0},
    {"auto-resize-window", no_argument, nullptr, 0},
    {"cpu-uv-swap", no_argument, nullptr, 0},
    {"help", no_argument, nullptr, 'h'},
    {0,0,0,0}
  };

  // parse CLI options
  for (;;) {
    int idx = 0;
    int c = getopt_long(argc, argv, "h", longopts, &idx);
    if (c == -1) break;
    if (c == 'h') {
      print_usage(argv[0]);
      return 0;
    }
    if (c == 0) {
      std::string name = longopts[idx].name;
      if (name == "uv-swap") {
        std::string v = optarg ? optarg : "auto";
        if (v == "auto") opt_uv_swap_override = -1;
        else if (v == "0") opt_uv_swap_override = 0;
        else if (v == "1") opt_uv_swap_override = 1;
        else { std::cerr << "Invalid uv-swap value\n"; print_usage(argv[0]); return 1; }
      } else if (name == "range") {
        std::string v = optarg ? optarg : "limited";
        if (v == "limited") opt_full_range = 0;
        else if (v == "full") opt_full_range = 1;
        else { std::cerr << "Invalid range\n"; print_usage(argv[0]); return 1; }
      } else if (name == "matrix") {
        std::string v = optarg ? optarg : "709";
        if (v == "709") opt_use_bt709 = 1;
        else if (v == "601") opt_use_bt709 = 0;
        else { std::cerr << "Invalid matrix\n"; print_usage(argv[0]); return 1; }
      } else if (name == "auto-resize-window") {
        opt_auto_resize_window = true;
      } else if (name == "cpu-uv-swap") {
        opt_cpu_uv_swap = true;
      }
    }
  }

  int fd = open(DEVICE, O_RDWR | O_NONBLOCK);
  if (fd < 0) {
    perror("open video0");
    return 1;
  }

  // Initial format detection
  uint32_t cur_width = DEFAULT_WIDTH, cur_height = DEFAULT_HEIGHT, cur_pixfmt = 0;
  if (!get_v4l2_format(fd, cur_width, cur_height, cur_pixfmt)) {
    cur_width = DEFAULT_WIDTH;
    cur_height = DEFAULT_HEIGHT;
  }

  // Try to request NV24 initially (may be rejected)
  v4l2_format fmt;
  memset(&fmt, 0, sizeof(fmt));
  fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
  fmt.fmt.pix_mp.width = cur_width;
  fmt.fmt.pix_mp.height = cur_height;
  fmt.fmt.pix_mp.pixelformat = v4l2_fourcc('N','V','2','4');
  fmt.fmt.pix_mp.field = V4L2_FIELD_NONE;
  fmt.fmt.pix_mp.num_planes = 1;
  if (xioctl(fd, VIDIOC_S_FMT, &fmt) < 0) {
    std::cerr << "VIDIOC_S_FMT: " << strerror(errno) << " (" << errno << ")\n";
  }
  // re-read actual
  get_v4l2_format(fd, cur_width, cur_height, cur_pixfmt);

  // Subscribe to V4L2 source change events (optional; ignore failure)
  v4l2_event_subscription sub;
  memset(&sub, 0, sizeof(sub));
  sub.type = V4L2_EVENT_SOURCE_CHANGE;
  if (ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, &sub) < 0) {
    // not fatal
  }

  // Request buffers (MMAP)
  v4l2_requestbuffers req;
  memset(&req, 0, sizeof(req));
  req.count = BUF_COUNT;
  req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
  req.memory = V4L2_MEMORY_MMAP;
  if (xioctl(fd, VIDIOC_REQBUFS, &req) < 0) {
    perror("VIDIOC_REQBUFS");
    close(fd);
    return 1;
  }

  std::vector<std::vector<PlaneMap>> buffers(req.count);

  for (unsigned i = 0; i < req.count; ++i) {
    v4l2_buffer buf;
    v4l2_plane planes[VIDEO_MAX_PLANES] = {0};
    memset(&buf, 0, sizeof(buf));
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    buf.index = i;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.m.planes = planes;
    buf.length = VIDEO_MAX_PLANES;

    if (xioctl(fd, VIDIOC_QUERYBUF, &buf) < 0) {
      perror("VIDIOC_QUERYBUF");
      close(fd);
      return 1;
    }
    buffers[i].resize(buf.length);
    for (unsigned p = 0; p < buf.length; ++p) {
      buffers[i][p].length = planes[p].length;
      buffers[i][p].addr = mmap(nullptr, planes[p].length, PROT_READ|PROT_WRITE, MAP_SHARED, fd, planes[p].m.mem_offset);
      if (buffers[i][p].addr == MAP_FAILED) {
        perror("mmap plane");
        close(fd);
        return 1;
      }
    }
    if (xioctl(fd, VIDIOC_QBUF, &buf) < 0) {
      perror("VIDIOC_QBUF");
      close(fd);
      return 1;
    }
  }

  int buf_type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
  if (xioctl(fd, VIDIOC_STREAMON, &buf_type) < 0) {
    perror("VIDIOC_STREAMON");
    close(fd);
    return 1;
  }

  // Init SDL + GL
  if (SDL_Init(SDL_INIT_VIDEO) != 0) {
    std::cerr << "SDL_Init failed: " << SDL_GetError() << std::endl;
    close(fd);
    return 1;
  }

  SDL_Window* win = SDL_CreateWindow(WINDOW_TITLE,
      SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
      (int)cur_width, (int)cur_height, SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE);
  if (!win) {
    std::cerr << "SDL_CreateWindow failed: " << SDL_GetError() << std::endl;
    close(fd);
    return 1;
  }
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
  SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);

  SDL_GLContext glc = SDL_GL_CreateContext(win);
  if (!glc) {
    std::cerr << "SDL_GL_CreateContext failed: " << SDL_GetError() << std::endl;
    close(fd);
    return 1;
  }

  if (glewInit() != GLEW_OK) {
    std::cerr << "GLEW init failed!" << std::endl;
    close(fd);
    return 1;
  }

  // Query maximum supported texture size (used by tiled uploads)
  GLint gl_max_tex = 0;
  glGetIntegerv(GL_MAX_TEXTURE_SIZE, &gl_max_tex);

  // Start in fullscreen (desktop) immediately
  if (SDL_SetWindowFullscreen(win, SDL_WINDOW_FULLSCREEN_DESKTOP) != 0) {
    // ignore failure to set fullscreen
  }
  int win_w = 0, win_h = 0;
  SDL_GetWindowSize(win, &win_w, &win_h);
  glViewport(0, 0, win_w, win_h);

  // ----- Shaders and geometry -----
  // Resolve shader paths robustly so launching from other working directories still finds them
  {
    std::vector<std::string> attempts;
    std::string vertPath = findShaderFile("shader.vert.glsl", &attempts);
    if (vertPath.empty()) {
      std::cerr << "Vertex shader not found. Tried the following paths:\n";
      for (const auto &p : attempts) std::cerr << "  " << p << "\n";
      close(fd);
      return 1;
    }

    attempts.clear();
    std::string fragPath = findShaderFile("shader.frag.glsl", &attempts);
    if (fragPath.empty()) {
      std::cerr << "Fragment shader not found. Tried the following paths:\n";
      for (const auto &p : attempts) std::cerr << "  " << p << "\n";
      close(fd);
      return 1;
    }

    GLuint program = createShaderProgram(vertPath.c_str(), fragPath.c_str());

    glUseProgram(program);

    float verts[] = {
      -1, -1,     0, 0,
       1, -1,     1, 0,
      -1,  1,     0, 1,
       1,  1,     1, 1,
  };
    GLuint vbo = 0, vao = 0;
    glGenBuffers(1, &vbo);
    glGenVertexArrays(1, &vao);

    glBindVertexArray(vao);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(verts), verts, GL_STATIC_DRAW);

    glEnableVertexAttribArray(0); // position
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1); // texcoord
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)(2 * sizeof(float)));
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glBindVertexArray(0);

    // ----- Create two textures: texY (R8) and texUV (RG8) -----
    GLuint texY = 0, texUV = 0;
    glGenTextures(1, &texY);
    glBindTexture(GL_TEXTURE_2D, texY);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    glGenTextures(1, &texUV);
    glBindTexture(GL_TEXTURE_2D, texUV);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    // Decide initial uv texture size based on current pixfmt
    int uv_w = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21) ? (int)(cur_width/2) : (int)cur_width;
    int uv_h = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21) ? (int)(cur_height/2) : (int)cur_height;
    reallocate_textures(texY, texUV, (int)cur_width, (int)cur_height, uv_w, uv_h);

    // Uniforms: set sampler units and toggles
    glUseProgram(program);
    GLint loc_texY = glGetUniformLocation(program, "texY");
    GLint loc_texUV = glGetUniformLocation(program, "texUV");
    if (loc_texY >= 0) glUniform1i(loc_texY, 0);
    if (loc_texUV >= 0) glUniform1i(loc_texUV, 1);

    GLint loc_uv_swap = glGetUniformLocation(program, "uv_swap");
    GLint loc_use_bt709 = glGetUniformLocation(program, "use_bt709");
    GLint loc_full_range = glGetUniformLocation(program, "full_range");
    GLint loc_view_mode = glGetUniformLocation(program, "view_mode");

    // Stable defaults for typical HDMI capture
    int uv_swap = 0;     // default; may be auto-set below
    if (opt_uv_swap_override >= 0) {
      uv_swap = opt_uv_swap_override;
    } else {
      // auto detect NV12/NV21
      if (cur_pixfmt == V4L2_PIX_FMT_NV21) {
        uv_swap = 1;
      } else if (cur_pixfmt == V4L2_PIX_FMT_NV12) {
        uv_swap = 0;
      } else {
        uv_swap = 0; // conservative default
      }
    }

    // If CPU swap requested, we'll perform swap on upload and ensure shader uses uv_swap=0
    if (opt_cpu_uv_swap) {
      uv_swap = 0;
    }

    if (loc_uv_swap >= 0) glUniform1i(loc_uv_swap, uv_swap);
    if (loc_use_bt709 >= 0) glUniform1i(loc_use_bt709, opt_use_bt709);
    if (loc_full_range >= 0) glUniform1i(loc_full_range, opt_full_range);
    if (loc_view_mode >= 0) glUniform1i(loc_view_mode, 0);

    // Minimal console output (no per-frame debug)
    bool running = true;

    // We'll periodically check VIDIOC_G_FMT every N frames to detect changes faster, but we also use events
    const uint64_t CHECK_FMT_INTERVAL = 120;
    uint64_t frame_count = 0;

    // Prepare pollfd for device (we'll watch for POLLIN = frame, POLLPRI = event)
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = POLLIN | POLLPRI;

    // tmp buffers/helpers for CPU swap or fallback
    std::vector<unsigned char> tmpUVbuf; // for CPU swap of UV when needed
    std::vector<unsigned char> tmpFallback; // fallback for packed format

    // Track fullscreen state for 'F' toggle
    bool is_fullscreen = true;

    while (running) {
      // Use poll to wait for either frame data (POLLIN) or event (POLLPRI)
      int ret = poll(&pfd, 1, 2000); // 2s timeout
      if (ret < 0) {
        if (errno == EINTR) continue;
        perror("poll");
        break;
      } else if (ret == 0) {
        // timeout, do periodic checks below
      } else {
        if (pfd.revents & POLLPRI) {
          v4l2_event ev;
          while (ioctl(fd, VIDIOC_DQEVENT, &ev) == 0) {
            if (ev.type == V4L2_EVENT_SOURCE_CHANGE) {
              uint32_t new_w=0, new_h=0, new_pf=0;
              if (get_v4l2_format(fd, new_w, new_h, new_pf)) {
                if (new_w != cur_width || new_h != cur_height || new_pf != cur_pixfmt) {
                  cur_width = new_w;
                  cur_height = new_h;
                  cur_pixfmt = new_pf;
                  uv_w = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21) ? (int)(cur_width/2) : (int)cur_width;
                  uv_h = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21) ? (int)(cur_height/2) : (int)cur_height;
                  reallocate_textures(texY, texUV, (int)cur_width, (int)cur_height, uv_w, uv_h);
                  if (opt_auto_resize_window) SDL_SetWindowSize(win, (int)cur_width, (int)cur_height);
                  if (opt_uv_swap_override < 0 && !opt_cpu_uv_swap) {
                    int old_uv = uv_swap;
                    if (cur_pixfmt == V4L2_PIX_FMT_NV21) uv_swap = 1;
                    else if (cur_pixfmt == V4L2_PIX_FMT_NV12) uv_swap = 0;
                    if (uv_swap != old_uv && loc_uv_swap >= 0) {
                      glUseProgram(program);
                      glUniform1i(loc_uv_swap, uv_swap);
                    }
                  }
                }
              }
            }
          }
        }
      }

      // Periodic format check
      if ((frame_count % CHECK_FMT_INTERVAL) == 0) {
        uint32_t new_w=0, new_h=0, new_pf=0;
        if (get_v4l2_format(fd, new_w, new_h, new_pf)) {
          if (new_w != cur_width || new_h != cur_height || new_pf != cur_pixfmt) {
            cur_width = new_w;
            cur_height = new_h;
            cur_pixfmt = new_pf;
            uv_w = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21) ? (int)(cur_width/2) : (int)cur_width;
            uv_h = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21) ? (int)(cur_height/2) : (int)cur_height;
            reallocate_textures(texY, texUV, (int)cur_width, (int)cur_height, uv_w, uv_h);
            if (opt_auto_resize_window) SDL_SetWindowSize(win, (int)cur_width, (int)cur_height);
            if (opt_uv_swap_override < 0 && !opt_cpu_uv_swap) {
              int old_uv = uv_swap;
              if (cur_pixfmt == V4L2_PIX_FMT_NV21) uv_swap = 1;
              else if (cur_pixfmt == V4L2_PIX_FMT_NV12) uv_swap = 0;
              if (uv_swap != old_uv && loc_uv_swap >= 0) {
                glUseProgram(program);
                glUniform1i(loc_uv_swap, uv_swap);
              }
            }
          }
        }
      }

      // Now try to dequeue a video buffer
      v4l2_buffer buf;
      v4l2_plane planes[VIDEO_MAX_PLANES];
      memset(&buf, 0, sizeof(buf));
      memset(planes, 0, sizeof(planes));
      buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
      buf.memory = V4L2_MEMORY_MMAP;
      buf.m.planes = planes;
      buf.length = VIDEO_MAX_PLANES;

      if (xioctl(fd, VIDIOC_DQBUF, &buf) < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
          ++frame_count;
          continue;
        } else {
          perror("VIDIOC_DQBUF");
          break;
        }
      }

      unsigned char* base = (unsigned char*)buffers[buf.index][0].addr;
      size_t bytesused0 = planes[0].bytesused;

      // sizes
      size_t Y_len = (size_t)cur_width * (size_t)cur_height;
      size_t UV_len = 0;
      bool isNV12_NV21 = (cur_pixfmt == V4L2_PIX_FMT_NV12 || cur_pixfmt == V4L2_PIX_FMT_NV21);
      if (isNV12_NV21) UV_len = (size_t)cur_width * ((size_t)cur_height / 2);
      else UV_len = (size_t)cur_width * (size_t)cur_height * 2;
      size_t total_expected = Y_len + UV_len;

      unsigned char* ybase = nullptr;
      unsigned char* uvbase = nullptr;

      if (buf.length >= 2 && buffers[buf.index].size() >= 2) {
        ybase = (unsigned char*)buffers[buf.index][0].addr;
        uvbase = (unsigned char*)buffers[buf.index][1].addr;
      } else if (bytesused0 >= total_expected) {
        ybase = base;
        uvbase = base + Y_len;
      } else {
        ybase = base;
        uvbase = nullptr;
      }

      // Upload Y
      if (ybase) {
        if ((int)cur_width <= gl_max_tex && (int)cur_height <= gl_max_tex) {
          glActiveTexture(GL_TEXTURE0);
          glBindTexture(GL_TEXTURE_2D, texY);
          glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
          glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, (int)cur_width, (int)cur_height, GL_RED, GL_UNSIGNED_BYTE, ybase);
        } else {
          upload_texture_tiled(GL_RED, texY, (int)cur_width, (int)cur_height, ybase, gl_max_tex, 1);
        }
      }

      // Upload UV
      if (uvbase) {
        int upload_w = isNV12_NV21 ? (int)(cur_width/2) : (int)cur_width;
        int upload_h = isNV12_NV21 ? (int)(cur_height/2) : (int)cur_height;

        if (opt_cpu_uv_swap && cur_pixfmt == V4L2_PIX_FMT_NV21) {
          size_t need = (size_t)upload_w * (size_t)upload_h * 2;
          if (tmpUVbuf.size() < need) tmpUVbuf.resize(need);
          unsigned char* dst = tmpUVbuf.data();

          if (isNV12_NV21) {
            for (int y = 0; y < upload_h; ++y) {
              const unsigned char* srcRow = uvbase + (size_t)y * (size_t)cur_width;
              unsigned char* dstRow = dst + (size_t)y * (size_t)upload_w * 2;
              for (int x = 0; x < upload_w; ++x) {
                unsigned char v = srcRow[x*2 + 0];
                unsigned char u = srcRow[x*2 + 1];
                dstRow[x*2 + 0] = u;
                dstRow[x*2 + 1] = v;
              }
            }
          } else {
            for (int y = 0; y < upload_h; ++y) {
              const unsigned char* srcRow = uvbase + (size_t)y * (size_t)upload_w * 2;
              unsigned char* dstRow = dst + (size_t)y * (size_t)upload_w * 2;
              for (int x = 0; x < upload_w; ++x) {
                unsigned char v = srcRow[x*2 + 0];
                unsigned char u = srcRow[x*2 + 1];
                dstRow[x*2 + 0] = u;
                dstRow[x*2 + 1] = v;
              }
            }
          }

          if (upload_w <= gl_max_tex && upload_h <= gl_max_tex) {
            glActiveTexture(GL_TEXTURE1);
            glBindTexture(GL_TEXTURE_2D, texUV);
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, upload_w, upload_h, GL_RG, GL_UNSIGNED_BYTE, tmpUVbuf.data());
          } else {
            upload_texture_tiled(GL_RG, texUV, upload_w, upload_h, tmpUVbuf.data(), gl_max_tex, 2);
          }
        } else {
          if (upload_w <= gl_max_tex && upload_h <= gl_max_tex) {
            glActiveTexture(GL_TEXTURE1);
            glBindTexture(GL_TEXTURE_2D, texUV);
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, upload_w, upload_h, GL_RG, GL_UNSIGNED_BYTE, uvbase);
          } else {
            upload_texture_tiled(GL_RG, texUV, upload_w, upload_h, uvbase, gl_max_tex, 2);
          }
        }
      } else {
        // fallback packed interleaved (Y,U,V per pixel)
        size_t need = Y_len + (size_t)cur_width * (size_t)cur_height * 2;
        if (tmpFallback.size() < need) tmpFallback.resize(need);
        unsigned char* dst = tmpFallback.data();
        unsigned char* src = base;
        for (size_t i = 0, j = 0; i < (size_t)cur_width * (size_t)cur_height; ++i) {
          dst[j++] = src[i*3 + 0];
          dst[j++] = src[i*3 + 1];
          dst[j++] = src[i*3 + 2];
        }
        unsigned char* tmpY = dst;
        unsigned char* tmpUV = dst + Y_len;
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, texY);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, (int)cur_width, (int)cur_height, GL_RED, GL_UNSIGNED_BYTE, tmpY);
        glActiveTexture(GL_TEXTURE1);
        glBindTexture(GL_TEXTURE_2D, texUV);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, (int)cur_width, (int)cur_height, GL_RG, GL_UNSIGNED_BYTE, tmpUV);
      }

      // Draw
      glClear(GL_COLOR_BUFFER_BIT);
      glUseProgram(program);

      if (!opt_cpu_uv_swap && loc_uv_swap >= 0) glUniform1i(loc_uv_swap, uv_swap);
      if (loc_use_bt709 >= 0) glUniform1i(loc_use_bt709, opt_use_bt709);
      if (loc_full_range >= 0) glUniform1i(loc_full_range, opt_full_range);

      glActiveTexture(GL_TEXTURE0);
      glBindTexture(GL_TEXTURE_2D, texY);
      glActiveTexture(GL_TEXTURE1);
      glBindTexture(GL_TEXTURE_2D, texUV);

      glBindVertexArray(vao);
      glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

      SDL_GL_SwapWindow(win);

      // Requeue buffer
      if (xioctl(fd, VIDIOC_QBUF, &buf) < 0) {
        perror("VIDIOC_QBUF (requeue)");
        break;
      }

      // Events: minimal toggles
      SDL_Event e;
      while (SDL_PollEvent(&e)) {
        if (e.type == SDL_QUIT) running = false;
        else if (e.type == SDL_KEYDOWN) {
          SDL_Keycode k = e.key.keysym.sym;
          if (k == SDLK_ESCAPE) running = false;
          else if (k == SDLK_f) {
            // Toggle fullscreen desktop mode
            Uint32 flags = SDL_GetWindowFlags(win);
            if (flags & SDL_WINDOW_FULLSCREEN_DESKTOP) {
              SDL_SetWindowFullscreen(win, 0);
              is_fullscreen = false;
            } else {
              SDL_SetWindowFullscreen(win, SDL_WINDOW_FULLSCREEN_DESKTOP);
              is_fullscreen = true;
            }
          }
        }
      }

      ++frame_count;
    }

    // Cleanup
    glDeleteTextures(1, &texY);
    glDeleteTextures(1, &texUV);
    glDeleteBuffers(1, &vbo);
    glDeleteVertexArrays(1, &vao);
    glDeleteProgram(program);
    SDL_GL_DeleteContext(glc);
    SDL_DestroyWindow(win);
    SDL_Quit();

    for (auto& bufv : buffers)
      for (auto& pm : bufv)
        if (pm.addr && pm.length) munmap(pm.addr, pm.length);

    close(fd);
    return 0;
  }
}