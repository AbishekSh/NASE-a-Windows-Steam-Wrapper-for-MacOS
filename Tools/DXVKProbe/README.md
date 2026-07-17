# NASE DXVK-macOS graphics probe

This small Windows program creates a real Vulkan instance and logical device, then creates a D3D11 hardware device. The profile verifier runs it through the pinned Wine/DXVK-macOS stack and validates the generated DXVK log.

Rebuild the bundled executable on macOS with MacPorts MinGW:

```sh
x86_64-w64-mingw32-gcc -O2 -I/opt/local/include nase_graphics_probe.c -o nase_graphics_probe.exe -ld3d11 -ldxgi
```

The executable has no network or filesystem behavior beyond DXVK's own diagnostic log output.

Pinned executable SHA-256: `4e5e75469dccfe63eabced92b00d05cdb265ab822154988fdabc1b1b4462081a`.
