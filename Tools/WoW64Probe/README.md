# NASE WoW64 probe

This PE32 console program verifies that a selected Wine runtime can start
32-bit Windows executables inside NASE's normal 64-bit prefixes.

```sh
i686-w64-mingw32-gcc -Os -s nase_wow64_probe.c -o nase_wow64_probe.exe
```
