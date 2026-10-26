/*
 * plt.c -- the loaded libseekip.so's dynamic symbols and PLT slots, for seek-thermal-apk-patches' hooks.
 *
 * libseekip calls its own exported functions through its PLT (R_*_JUMP_SLOT relocations); it is
 * linked BIND_NOW with RELRO, so the slots are resolved at load and read-only: plt_swap makes one
 * writable for the store, then read-only again.
 */
#include <dlfcn.h>
#include <elf.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include "plt.h"

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

struct found {
	int count;
	struct plt_lib *lib;
};

static int find_seekip(struct dl_phdr_info *info, size_t size, void *data)
{
	(void)size;
	struct found *f = data;
	const char *name = info->dlpi_name;
	size_t n = name ? strlen(name) : 0;
	if (n >= 12 && strcmp(name + n - 12, "libseekip.so") == 0 && (n == 12 || name[n - 13] == '/')) {
		f->count++;
		f->lib->bias = info->dlpi_addr;
		f->lib->phdr = info->dlpi_phdr;
		f->lib->phnum = info->dlpi_phnum;
	}
	return 0;
}

/* a d_ptr: bionic leaves them unrelocated (an offset in the file's address space) */
static ElfW(Addr) at(const struct plt_lib *lib, ElfW(Addr) p)
{
	return p < lib->bias ? lib->bias + p : p;
}

static int in_segment(const struct plt_lib *lib, ElfW(Word) type, ElfW(Addr) addr, int *writable)
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

const char *plt_open(struct plt_lib *lib)
{
	memset(lib, 0, sizeof(*lib));
	struct found f = {0, lib};
	dl_iterate_phdr(find_seekip, &f);
	if (f.count != 1)
		return f.count ? "more than one libseekip.so loaded" : "libseekip.so is not loaded";

	const ElfW(Dyn) *dyn = NULL;
	for (int i = 0; i < lib->phnum; i++)
		if (lib->phdr[i].p_type == PT_DYNAMIC)
			dyn = (const ElfW(Dyn) *)(lib->bias + lib->phdr[i].p_vaddr);
	if (!dyn)
		return "libseekip.so has no dynamic section";
	ElfW(Addr) symtab = 0, strtab = 0, hash = 0, gnu_hash = 0;
	long pltrel = -1, bind_now = 0;
	for (; dyn->d_tag != DT_NULL; dyn++) {
		switch (dyn->d_tag) {
		case DT_JMPREL: lib->jmprel = at(lib, dyn->d_un.d_ptr); break;
		case DT_PLTRELSZ: lib->pltrelsz = dyn->d_un.d_val; break;
		case DT_PLTREL: pltrel = (long)dyn->d_un.d_val; break;
		case DT_SYMTAB: symtab = at(lib, dyn->d_un.d_ptr); break;
		case DT_STRTAB: strtab = at(lib, dyn->d_un.d_ptr); break;
		case DT_HASH: hash = at(lib, dyn->d_un.d_ptr); break;
		case DT_GNU_HASH: gnu_hash = at(lib, dyn->d_un.d_ptr); break;
		case DT_BIND_NOW: bind_now = 1; break;
		case DT_FLAGS: bind_now |= (dyn->d_un.d_val & DF_BIND_NOW) != 0; break;
		case DT_FLAGS_1: bind_now |= (dyn->d_un.d_val & DF_1_NOW) != 0; break;
		}
	}
	if (!lib->jmprel || !symtab || !strtab || pltrel != (PLT_RELA ? DT_RELA : DT_REL) || !bind_now)
		return "libseekip.so: not the PLT / binding the hook expects";
	lib->syms = (const ElfW(Sym) *)symtab;
	lib->strs = (const char *)strtab;

	/* the number of dynamic symbols: from the SysV hash, or the GNU hash's last chain */
	if (hash) {
		lib->nsyms = ((const uint32_t *)hash)[1];
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
		lib->nsyms = last + 1;
	}
	return NULL;
}

unsigned plt_symbol(const struct plt_lib *lib, const char *name, ElfW(Addr) *addr)
{
	unsigned size = 0;
	for (size_t i = 1; i < lib->nsyms; i++)
		if (lib->syms[i].st_shndx != SHN_UNDEF && strcmp(lib->strs + lib->syms[i].st_name, name) == 0) {
			size = (unsigned)lib->syms[i].st_size;
			if (addr)
				*addr = lib->bias + lib->syms[i].st_value;
		}
	return size;
}

void **plt_slot(const struct plt_lib *lib, const char *name, int *count)
{
	void **slot = NULL;
	*count = 0;
#if PLT_RELA
	const ElfW(Rela) *rel = (const ElfW(Rela) *)lib->jmprel;
	size_t nrel = lib->pltrelsz / sizeof(ElfW(Rela));
#else
	const ElfW(Rel) *rel = (const ElfW(Rel) *)lib->jmprel;
	size_t nrel = lib->pltrelsz / sizeof(ElfW(Rel));
#endif
	for (size_t i = 0; i < nrel; i++)
		if (R_TYPE(rel[i].r_info) == JUMP_SLOT && strcmp(lib->strs + lib->syms[R_SYM(rel[i].r_info)].st_name, name) == 0) {
			slot = (void **)(lib->bias + rel[i].r_offset);
			(*count)++;
		}
	return slot;
}

int plt_swap(const struct plt_lib *lib, void **slot, void *to)
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
