/*
 * plt.h -- the loaded libseekip.so's dynamic symbols and PLT slots, for seek-thermal-apk-patches' hooks
 * (smooth_android.c, lock.c).
 */
#ifndef SEEKPATCH_PLT_H
#define SEEKPATCH_PLT_H

#include <link.h>
#include <stddef.h>

struct plt_lib {
	ElfW(Addr) bias;
	const ElfW(Phdr) *phdr;
	int phnum;
	const ElfW(Sym) *syms;
	const char *strs;
	size_t nsyms;
	ElfW(Addr) jmprel;
	size_t pltrelsz;
};

/* Finds the one loaded libseekip.so and reads its dynamic section: NULL, or why not. */
const char *plt_open(struct plt_lib *lib);

/* st_size of libseekip's own definition of name (0: none); *addr its address, if addr. */
unsigned plt_symbol(const struct plt_lib *lib, const char *name, ElfW(Addr) *addr);

/* The PLT (JUMP_SLOT) slot through which libseekip calls name, NULL if none; *count the slots found. */
void **plt_slot(const struct plt_lib *lib, const char *name, int *count);

/* Points a slot at `to` (made writable for the store if it is in RELRO): 0, or -1. */
int plt_swap(const struct plt_lib *lib, void **slot, void *to);

#endif
