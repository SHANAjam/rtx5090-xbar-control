// XBAR L2 data-integrity checker (CUDA source).
//
// This is the original kernel published by Loong0x00 in LACT issue #1147:
// https://github.com/ilya-zlobintsev/LACT/issues/1147
//
// The bundled xbar_l2_check.exe is built from this source. Keeping the source
// in the repository makes the trust chain auditable.

#include <cstdint>

__device__ __forceinline__ uint32_t pattern(uint32_t i) {
    return i * 747796405u + 2891336453u;
}

__global__ void xbar_l2_check(const uint32_t *data, uint32_t mask,
                              unsigned long long *errors) {
    uint32_t s = blockIdx.x * blockDim.x + threadIdx.x;
    for (uint32_t n = 0; n != (1u << 20); ++n) {
        s = s * 1664525u + 1013904223u;
        uint32_t i = s & mask, got;
        asm volatile("ld.global.cg.u32 %0, [%1];"
                     : "=r"(got) : "l"(data + i));
        if (got != pattern(i))
            atomicAdd(errors, 1ULL);
    }
}
