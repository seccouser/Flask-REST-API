# feature/auto-resize-v4l2 — per-tile output offsets + runtime rotate/flip

## Summary
This branch adds per-tile, pixel-accurate output offsets for the 150 tiles rendered by the shader, plus runtime controls to rotate and flip the input image. Offsets are loaded from three module files (modul1.txt, modul2.txt, modul3.txt) and can be reloaded at runtime. The change preserves the existing source sampling logic while moving the displayed tiles on the output; it also hardens shader uniform handling and improves texture reallocation on V4L2 format changes.

## Why
- Allows correcting misaligned tiles by applying per-tile pixel offsets without modifying the input sampling.
- Makes it easy to adjust layout at runtime via simple text files and a reload key.
- Keeps shader and upload logic performant and robust for NV12/NV21 capture formats.

## Key features
- Per-tile output offsets:
  - 150 ivec2 offsets (offsetxy1[150]) passed to the fragment shader via `glUniform2iv`.
  - Interpretation: offset.x positive → shift tile right; negative → left. offset.y positive → shift tile down; negative → up.
  - Offsets move the output tile rectangles only; the input texture sampling region remains unchanged.
- Runtime reload:
  - modul1.txt / modul2.txt / modul3.txt (50 pairs each) are read by the program.
  - Press `k` to reload files at runtime and upload offsets to the shader.
- Input transformations:
  - `rot` uniform (0/1/2/3 → 0°/90°/180°/270° clockwise) applied to input UVs before sampling.
  - `flip_x` and `flip_y` uniforms toggle horizontal/vertical mirroring of the input.
  - Keys: `r` = rotate, `h` = toggle horizontal mirror, `v` = toggle vertical mirror.
- Robustness / UX:
  - Shader uniforms are uploaded every frame to avoid driver optimizations causing missing uniforms.
  - The loader checks executable dir and CWD, logs attempts and read counts.
  - Textures are reallocated on V4L2 format changes; UV swap detection and optional CPU UV swap are supported.

## Files changed / primary locations
- hdmi_simple_display.cpp
  - New/updated: offset file loader + logging, uniform uploads for offsetxy1/rot/flip, key handling (`k`, `h`, `v`, `r`), texture reallocation logic remains.
- shaders/shader.frag.glsl
  - Uses `uniform ivec2 offsetxy1[150]`, applies offsets to the output tile rectangle, applies input UV rotation/flip prior to sampling.
- (No changes to vertex shader.)

## Module file format (modul1.txt / modul2.txt / modul3.txt)
- Up to 50 lines per file (missing entries are zero-filled).
- Each valid line: two signed integers separated by whitespace:
  ```
  <x> <y>
  ```
  Example:
  ```
  -3 5
  0 0
  2 -1
  ```
- Lines starting with `#` or blank lines are ignored.
- Files are searched in the executable directory and in the current working directory.

## How to build & test
1. Build:
   ```bash
   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
   cmake --build build -j$(nproc)
   ```
2. Prepare module files (example, minimal):
   ```bash
   echo "-3 5" > modul1.txt   # first tile: 3px left, 5px down
   # create modul2.txt/modul3.txt similarly (or leave empty)
   ```
3. Run:
   ```bash
   ./build/hdmi_simple_display
   ```
4. Controls:
   - `k` : reload modul1/2/3 and upload offsets
   - `h` : toggle horizontal mirror (input)
   - `v` : toggle vertical mirror (input)
   - `r` : rotate input (step setting configurable; branch defaults to 180° step)
   - `f` : fullscreen toggle
   - `ESC` : exit

## Example workflow
1. Put `modul1.txt` in the same directory as the binary (or in the executable dir). For the first tile add:
   ```
   -3 5
   ```
2. Start the program and press `k`. Console prints show loaded entries and confirm upload. Visual result: first tile moves 3px left and 5px down.

## Notes & gotchas
- If the shader compiler optimizes unused uniforms away, the program will report `loc_* == -1` in the console. The fragment shader in this branch uses the uniforms, so their locations should be valid.
- Offsets can cause overlapping tiles or gaps; gaps are rendered black by design. You may change that to a background color if desired.
- If you alter how offsets map to tiles (different ordering), update the shader's `globalIndex` computation accordingly.

## Suggested commit & PR meta
- Commit message:
  ```
  Add per-tile output offsets and runtime rotate/flip controls; improve offset loader logging
  ```
- PR title:
  ```
  feature/auto-resize-v4l2: per-tile output offsets + runtime rotate/flip
  ```
- PR body: use the Summary + Key features + How to build & test sections above.

## Optional follow-ups (can add as separate PRs)
- On-screen overlay showing current `rot/flip` status for a configurable short duration.
- Persist settings (flip/rotation/defaults) into a small settings file.
- Visual debugging mode to draw tile borders and indices to verify offset mapping.
- Background fill color option for gaps produced by offsets.

---

If you want, I can:
- Create this `PR_DESCRIPTION.md` file and commit it to `feature/auto-resize-v4l2` (give me a commit message), or
- Generate the exact git commands to add, commit and push the file based on your local `git status` (paste `git status --porcelain` and I’ll create the commands).
