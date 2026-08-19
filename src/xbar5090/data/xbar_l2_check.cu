// XBAR L2 data-integrity checker (CUDA source, full host + device).
//
// This is the original L2 checker published by Loong0x00 in LACT issue #1147
// (https://github.com/ilya-zlobintsev/LACT/issues/1147), with a small
// maintainable host wrapper:
//   - --mb controls the checker buffer size (default 32 MiB).
//   - Error messages include the numeric CUDA error code so failures such as
//     "cudaMalloc data: (null)" on some systems are actionable instead of
//     opaque.
//   - load mode runs a concurrent stress kernel to add L2/global traffic.
//
// The PTX-specific L2 load is unchanged:
//   ld.global.cg.u32 bypasses L1 allocation and exercises the L2/global path.

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <string>

#include <cuda_runtime.h>

__host__ __device__ __forceinline__ uint32_t pattern(uint32_t i) {
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

__global__ void stress_kernel(uint32_t *dummy, uint32_t mask,
                              uint32_t stress_iters) {
    uint32_t s = blockIdx.x * blockDim.x + threadIdx.x;
    for (uint32_t n = 0; n < stress_iters; ++n) {
        s = s * 1664525u + 1013904223u;
        uint32_t i = s & mask;
        dummy[i] = dummy[i] * 1664525u + 1013904223u;
    }
}

static int gpu_blocks = 1360;
static int gpu_threads = 256;
static int gpu_rounds = 1;
static std::string gpu_mode = "idle";
static int stress_iters = 100000;
static int mb = 32;

static bool parse_args(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next = [&](const char *name) -> const char * {
            if (i + 1 >= argc) {
                fprintf(stderr, "missing value for %s\n", name);
                return nullptr;
            }
            return argv[++i];
        };
        if (arg == "--blocks") {
            const char *v = next("--blocks");
            if (!v) return false;
            gpu_blocks = atoi(v);
            if (gpu_blocks <= 0) { fprintf(stderr, "bad --blocks\n"); return false; }
        } else if (arg == "--threads") {
            const char *v = next("--threads");
            if (!v) return false;
            gpu_threads = atoi(v);
            if (gpu_threads <= 0) { fprintf(stderr, "bad --threads\n"); return false; }
        } else if (arg == "--rounds") {
            const char *v = next("--rounds");
            if (!v) return false;
            gpu_rounds = atoi(v);
            if (gpu_rounds <= 0) { fprintf(stderr, "bad --rounds\n"); return false; }
        } else if (arg == "--mode") {
            const char *v = next("--mode");
            if (!v) return false;
            gpu_mode = v;
            if (gpu_mode != "idle" && gpu_mode != "load") {
                fprintf(stderr, "bad --mode (idle|load)\n");
                return false;
            }
        } else if (arg == "--stress-iters") {
            const char *v = next("--stress-iters");
            if (!v) return false;
            stress_iters = atoi(v);
            if (stress_iters <= 0) { fprintf(stderr, "bad --stress-iters\n"); return false; }
        } else if (arg == "--mb") {
            const char *v = next("--mb");
            if (!v) return false;
            mb = atoi(v);
            if (mb <= 0 || mb > 4096) { fprintf(stderr, "bad --mb\n"); return false; }
        } else {
            fprintf(stderr, "unknown arg: %s\n", arg.c_str());
            return false;
        }
    }
    return true;
}

static const char *err_string(cudaError_t err) {
    // cudaGetErrorString can return NULL for a not-yet-initialized runtime on
    // some systems; fall back to a numeric representation.
    const char *s = cudaGetErrorString(err);
    return s ? s : "(unknown error)";
}

#define CUDA_CHECK(label, expr)                                                 \
    do {                                                                        \
        cudaError_t err = (expr);                                               \
        if (err != cudaSuccess) {                                               \
            fprintf(stderr, "CUDA error: %s: %s [code=%d]\n",                   \
                    label, err_string(err), (int)err);                          \
            return 1;                                                           \
        }                                                                       \
    } while (0)

int main(int argc, char **argv) {
    if (!parse_args(argc, argv))
        return 2;

    size_t bytes = (size_t)mb * 1024 * 1024;
    size_t words = bytes / sizeof(uint32_t);
    if ((words & (words - 1)) != 0) {
        fprintf(stderr, "--mb must make a power-of-two word count\n");
        return 2;
    }
    uint32_t mask = (uint32_t)(words - 1);

    uint32_t *host_data = (uint32_t *)malloc(bytes);
    if (!host_data) {
        fprintf(stderr, "host malloc failed\n");
        return 1;
    }
    for (size_t i = 0; i < words; ++i)
        host_data[i] = pattern((uint32_t)i);

    uint32_t *data = nullptr;
    CUDA_CHECK("cudaMalloc data", cudaMalloc(&data, bytes));
    unsigned long long *errors = nullptr;
    CUDA_CHECK("cudaMalloc errors", cudaMalloc(&errors, sizeof(*errors)));
    uint32_t *dummy = nullptr;
    if (gpu_mode == "load") {
        size_t dummy_words = (size_t)gpu_blocks * gpu_threads;
        if (dummy_words == 0)
            dummy_words = 1;
        size_t dummy_bytes = dummy_words * sizeof(uint32_t);
        CUDA_CHECK("cudaMalloc dummy", cudaMalloc(&dummy, dummy_bytes));
        CUDA_CHECK("cudaMemset dummy", cudaMemset(dummy, 0, dummy_bytes));
    }

    CUDA_CHECK("cudaMemcpy data", cudaMemcpy(data, host_data, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK("cudaMemset errors", cudaMemset(errors, 0, sizeof(*errors)));

    cudaStream_t stream_a = nullptr, stream_b = nullptr;
    if (gpu_mode == "load") {
        CUDA_CHECK("cudaStreamCreate", cudaStreamCreateWithFlags(&stream_a, cudaStreamNonBlocking));
        CUDA_CHECK("cudaStreamCreate", cudaStreamCreateWithFlags(&stream_b, cudaStreamNonBlocking));
    }

    auto start = std::chrono::high_resolution_clock::now();
    for (int round = 0; round < gpu_rounds; ++round) {
        CUDA_CHECK("cudaMemset errors", cudaMemset(errors, 0, sizeof(*errors)));
        if (gpu_mode == "load") {
            size_t dummy_words = (size_t)gpu_blocks * gpu_threads;
            uint32_t dummy_mask = (uint32_t)(dummy_words - 1);
            stress_kernel<<<gpu_blocks, gpu_threads, 0, stream_a>>>(
                dummy, dummy_mask, (uint32_t)stress_iters);
            CUDA_CHECK("stress launch", cudaGetLastError());
            xbar_l2_check<<<gpu_blocks, gpu_threads, 0, stream_b>>>(
                data, mask, errors);
            CUDA_CHECK("checker launch", cudaGetLastError());
            CUDA_CHECK("stress sync", cudaStreamSynchronize(stream_a));
            CUDA_CHECK("device sync", cudaStreamSynchronize(stream_b));
        } else {
            xbar_l2_check<<<gpu_blocks, gpu_threads>>>(data, mask, errors);
            CUDA_CHECK("checker launch", cudaGetLastError());
            CUDA_CHECK("device sync", cudaDeviceSynchronize());
        }
        unsigned long long host_errors = 0;
        CUDA_CHECK("cudaMemcpy errors",
                   cudaMemcpy(&host_errors, errors, sizeof(host_errors), cudaMemcpyDeviceToHost));
        auto end = std::chrono::high_resolution_clock::now();
        double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();
        printf("round=%u mode=%s errors=%llu elapsed_ms=%.3f\n",
               round, gpu_mode.c_str(), host_errors, elapsed_ms);
    }

    if (stream_a) cudaStreamDestroy(stream_a);
    if (stream_b) cudaStreamDestroy(stream_b);
    if (dummy) cudaFree(dummy);
    cudaFree(errors);
    cudaFree(data);
    free(host_data);
    return 0;
}
