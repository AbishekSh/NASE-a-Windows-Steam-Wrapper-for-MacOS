#include <stdio.h>
#include <windows.h>

int main(void) {
    BOOL wow64 = FALSE;
    IsWow64Process(GetCurrentProcess(), &wow64);
    printf("NASE_WOW64_PROBE_OK pointer_bits=%u wow64=%u\n", (unsigned)(sizeof(void *) * 8), (unsigned)wow64);
    return sizeof(void *) == 4 ? 0 : 2;
}
