/*
 * smooth_android.c -- seek-patch smart_smoothing on Android: finds the loaded libseekip.so, checks it
 * is a library the hook was verified on, and points its GOT entries for filter_process and
 * filter_process_shutter at smooth.c's wrappers.  JNI for seekpatch.Smooth.
 *
 * libseekip calls both functions through its PLT (R_*_JUMP_SLOT relocations); it is linked BIND_NOW
 * with RELRO, so the slots are resolved at load and read-only: each is made writable for the swap,
 * then read-only again.  Before touching anything the slot must hold the address of libseekip's own
 * definition of that symbol, and the sizes of filter_process, filter_process_shutter and
 * seekip_process (the caller whose frame layout the wrappers rely on) must be those of a verified
 * build.  Otherwise nothing is changed and the reason is logged.
 */
#include <android/log.h>
#include <dlfcn.h>
#include <elf.h>
#include <jni.h>
#include <link.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include "smooth.h"

#define TAG "seek-patch"

#if defined(__aarch64__)
#define JUMP_SLOT R_AARCH64_JUMP_SLOT
#define PLT_RELA 1
#elif defined(__arm__)
#define JUMP_SLOT R_ARM_JUMP_SLOT
#define PLT_RELA 0
#else
#error "arm64-v8a and armeabi-v7a only"
#endif

#if defined(__LP64__)
#define R_SYM ELF64_R_SYM
#define R_TYPE ELF64_R_TYPE
#else
#define R_SYM ELF32_R_SYM
#define R_TYPE ELF32_R_TYPE
#endif

/* st_size of filter_process, filter_process_shutter, seekip_process in the verified libseekip builds
 * (libseekip 2.11.3.2; the frame-set layout was read from each build's seekip_process) */
static const struct { unsigned filter, shutter, process; const char *what; } VERIFIED[] = {
#if defined(__aarch64__)
	{932, 64, 5848, "2.11.3.2 arm64, apps 2.2.3 - 2.3.0"},
	{808, 64, 5712, "2.11.3.2 arm64, apps 2.3.1 - 2.3.4"},
#else
	{640, 42, 4408, "2.11.3.2 armv7, apps 2.2.3 - 2.3.0"},
	{520, 42, 4320, "2.11.3.2 armv7, apps 2.3.3 - 2.3.4"},
#endif
};

void smooth_log(const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	__android_log_vprint(ANDROID_LOG_INFO, TAG, fmt, ap);
	va_end(ap);
}

double smooth_now_ms(int thread_cpu)
{
	struct timespec ts;
	clock_gettime(thread_cpu ? CLOCK_THREAD_CPUTIME_ID : CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

struct lib {
	int found;
	ElfW(Addr) bias;
	const ElfW(Phdr) *phdr;
	int phnum;
};

static int find_seekip(struct dl_phdr_info *info, size_t size, void *data)
{
	(void)size;
	struct lib *lib = data;
	const char *name = info->dlpi_name;
	size_t n = name ? strlen(name) : 0;
	if (n >= 12 && strcmp(name + n - 12, "libseekip.so") == 0 && (n == 12 || name[n - 13] == '/')) {
		lib->found++;
		lib->bias = info->dlpi_addr;
		lib->phdr = info->dlpi_phdr;
		lib->phnum = info->dlpi_phnum;
	}
	return 0;
}

/* a d_ptr: bionic leaves them unrelocated (an offset in the file's address space) */
static ElfW(Addr) at(const struct lib *lib, ElfW(Addr) p)
{
	return p < lib->bias ? lib->bias + p : p;
}

static int in_segment(const struct lib *lib, ElfW(Word) type, ElfW(Addr) addr, int *writable)
{
	for (int i = 0; i < lib->phnum; i++) {
		const ElfW(Phdr) *ph = &lib->phdr[i];
		ElfW(Addr) start = lib->bias + ph->p_vaddr;
		if (ph->p_type == type && addr >= start && addr + sizeof(void *) <= start + ph->p_memsz) {
			if (writable)
				*writable = (ph->p_flags & PF_W) != 0;
			return 1;
		}
	}
	return 0;
}

static int swap(const struct lib *lib, void **slot, void *to)
{
	int relro = in_segment(lib, PT_GNU_RELRO, (ElfW(Addr))slot, NULL), writable = 0;
	if (!relro && !(in_segment(lib, PT_LOAD, (ElfW(Addr))slot, &writable) && writable))
		return -1;
	long page = sysconf(_SC_PAGESIZE);
	void *start = (void *)((ElfW(Addr))slot & ~(ElfW(Addr))(page - 1));
	if (relro && mprotect(start, page, PROT_READ | PROT_WRITE) != 0)
		return -1;
	__atomic_store_n(slot, to, __ATOMIC_RELEASE);
	if (relro)
		mprotect(start, page, PROT_READ);
	return 0;
}

static char error[200];

static const char *install(void)
{
	struct lib lib = {0};
	dl_iterate_phdr(find_seekip, &lib);
	if (lib.found != 1)
		return lib.found ? "more than one libseekip.so loaded" : "libseekip.so is not loaded";

	const ElfW(Dyn) *dyn = NULL;
	for (int i = 0; i < lib.phnum; i++)
		if (lib.phdr[i].p_type == PT_DYNAMIC)
			dyn = (const ElfW(Dyn) *)(lib.bias + lib.phdr[i].p_vaddr);
	if (!dyn)
		return "libseekip.so has no dynamic section";
	ElfW(Addr) jmprel = 0, symtab = 0, strtab = 0, hash = 0, gnu_hash = 0;
	size_t pltrelsz = 0;
	long pltrel = -1, bind_now = 0;
	for (; dyn->d_tag != DT_NULL; dyn++) {
		switch (dyn->d_tag) {
		case DT_JMPREL: jmprel = at(&lib, dyn->d_un.d_ptr); break;
		case DT_PLTRELSZ: pltrelsz = dyn->d_un.d_val; break;
		case DT_PLTREL: pltrel = (long)dyn->d_un.d_val; break;
		case DT_SYMTAB: symtab = at(&lib, dyn->d_un.d_ptr); break;
		case DT_STRTAB: strtab = at(&lib, dyn->d_un.d_ptr); break;
		case DT_HASH: hash = at(&lib, dyn->d_un.d_ptr); break;
		case DT_GNU_HASH: gnu_hash = at(&lib, dyn->d_un.d_ptr); break;
		case DT_BIND_NOW: bind_now = 1; break;
		case DT_FLAGS: bind_now |= (dyn->d_un.d_val & DF_BIND_NOW) != 0; break;
		case DT_FLAGS_1: bind_now |= (dyn->d_un.d_val & DF_1_NOW) != 0; break;
		}
	}
	if (!jmprel || !symtab || !strtab || pltrel != (PLT_RELA ? DT_RELA : DT_REL) || !bind_now)
		return "libseekip.so: not the PLT / binding the hook expects";
	const ElfW(Sym) *syms = (const ElfW(Sym) *)symtab;
	const char *strs = (const char *)strtab;

	/* the number of dynamic symbols: from the SysV hash, or the GNU hash's last chain */
	size_t nsyms = 0;
	if (hash) {
		nsyms = ((const uint32_t *)hash)[1];
	} else if (gnu_hash) {
		const uint32_t *gh = (const uint32_t *)gnu_hash;
		uint32_t nbuckets = gh[0], symoffset = gh[1], bloom = gh[2];
		const uint32_t *buckets = (const uint32_t *)((const ElfW(Addr) *)(gh + 4) + bloom), *chain = buckets + nbuckets;
		uint32_t last = 0;
		for (uint32_t i = 0; i < nbuckets; i++)
			if (buckets[i] > last)
				last = buckets[i];
		if (last >= symoffset)
			while (!(chain[last - symoffset] & 1))
				last++;
		nsyms = last + 1;
	}
	unsigned sizes[3] = {0};
	ElfW(Addr) defined[2] = {0};
	static const char *const NAMES[3] = {"filter_process", "filter_process_shutter", "seekip_process"};
	for (size_t i = 1; i < nsyms; i++)
		for (int k = 0; k < 3; k++)
			if (syms[i].st_shndx != SHN_UNDEF && strcmp(strs + syms[i].st_name, NAMES[k]) == 0) {
				sizes[k] = (unsigned)syms[i].st_size;
				if (k < 2)
					defined[k] = lib.bias + syms[i].st_value;
			}
	int known = -1;
	for (size_t i = 0; i < sizeof(VERIFIED) / sizeof(VERIFIED[0]); i++)
		if (sizes[0] == VERIFIED[i].filter && sizes[1] == VERIFIED[i].shutter && sizes[2] == VERIFIED[i].process)
			known = (int)i;
	if (known < 0) {
		snprintf(error, sizeof(error), "libseekip.so is not a build the hook was verified on (sizes %u / %u / %u)",
		         sizes[0], sizes[1], sizes[2]);
		return error;
	}

	void **slots[2] = {NULL, NULL};
#if PLT_RELA
	const ElfW(Rela) *rel = (const ElfW(Rela) *)jmprel;
	size_t nrel = pltrelsz / sizeof(ElfW(Rela));
#else
	const ElfW(Rel) *rel = (const ElfW(Rel) *)jmprel;
	size_t nrel = pltrelsz / sizeof(ElfW(Rel));
#endif
	for (size_t i = 0; i < nrel; i++) {
		if (R_TYPE(rel[i].r_info) != JUMP_SLOT)
			continue;
		const char *name = strs + syms[R_SYM(rel[i].r_info)].st_name;
		for (int k = 0; k < 2; k++)
			if (strcmp(name, NAMES[k]) == 0) {
				if (slots[k])
					return "libseekip.so: two PLT slots for one function";
				slots[k] = (void **)(lib.bias + rel[i].r_offset);
			}
	}
	if (!slots[0] || !slots[1])
		return "libseekip.so does not call filter_process / filter_process_shutter through its PLT";
	if (*slots[0] == (void *)smooth_filter_process && *slots[1] == (void *)smooth_filter_process_shutter)
		return NULL;  /* already installed */
	if ((ElfW(Addr))*slots[0] != defined[0] || (ElfW(Addr))*slots[1] != defined[1])
		return "libseekip.so's PLT does not point at its own filter functions (hooked by something else?)";

	smooth_set_originals((smooth_filter_fn)*slots[0], (smooth_shutter_fn)*slots[1]);
	if (swap(&lib, slots[1], (void *)smooth_filter_process_shutter) != 0)
		return "cannot write libseekip.so's PLT slots";
	if (swap(&lib, slots[0], (void *)smooth_filter_process) != 0) {
		swap(&lib, slots[1], (void *)defined[1]);
		return "cannot write libseekip.so's PLT slots";
	}
	smooth_log("smart_smoothing: hooked libseekip %s", VERIFIED[known].what);
	return NULL;
}

/* seekpatch.Smooth.install(): null when hooked, else why not */
JNIEXPORT jstring JNICALL Java_seekpatch_Smooth_install(JNIEnv *env, jclass cls)
{
	(void)cls;
	const char *why = install();
	return why ? (*env)->NewStringUTF(env, why) : NULL;
}

/* seekpatch.Smooth.enable(boolean) */
JNIEXPORT void JNICALL Java_seekpatch_Smooth_enable(JNIEnv *env, jclass cls, jboolean on)
{
	(void)env;
	(void)cls;
	smooth_set_enabled(on);
}
