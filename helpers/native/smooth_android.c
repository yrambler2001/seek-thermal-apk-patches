/*
 * smooth_android.c -- seek-patch smart_smoothing on Android: finds the loaded libseekip.so, checks it
 * is a library the hook was verified on, and points its GOT entries for filter_process and
 * filter_process_shutter at smooth.c's wrappers.  JNI for seekpatch.Smooth.
 *
 * libseekip calls both functions through its PLT (plt.c finds the slots and swaps them).  Before
 * touching anything the slot must hold the address of libseekip's own definition of that symbol,
 * and the sizes of filter_process, filter_process_shutter and seekip_process (the caller whose
 * frame layout the wrappers rely on) must be those of a verified build.  Otherwise nothing is
 * changed and the reason is logged.
 */
#include <android/log.h>
#include <jni.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "plt.h"
#include "smooth.h"

#define TAG "seek-patch"

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

static char error[200];

static const char *install(void)
{
	struct plt_lib lib;
	const char *why = plt_open(&lib);
	if (why)
		return why;
	static const char *const NAMES[3] = {"filter_process", "filter_process_shutter", "seekip_process"};
	unsigned sizes[3];
	ElfW(Addr) defined[2] = {0};
	for (int k = 0; k < 3; k++)
		sizes[k] = plt_symbol(&lib, NAMES[k], k < 2 ? &defined[k] : NULL);
	int known = -1;
	for (size_t i = 0; i < sizeof(VERIFIED) / sizeof(VERIFIED[0]); i++)
		if (sizes[0] == VERIFIED[i].filter && sizes[1] == VERIFIED[i].shutter && sizes[2] == VERIFIED[i].process)
			known = (int)i;
	if (known < 0) {
		snprintf(error, sizeof(error), "libseekip.so is not a build the hook was verified on (sizes %u / %u / %u)",
		         sizes[0], sizes[1], sizes[2]);
		return error;
	}

	void **slots[2];
	for (int k = 0; k < 2; k++) {
		int count;
		slots[k] = plt_slot(&lib, NAMES[k], &count);
		if (count > 1)
			return "libseekip.so: two PLT slots for one function";
	}
	if (!slots[0] || !slots[1])
		return "libseekip.so does not call filter_process / filter_process_shutter through its PLT";
	if (*slots[0] == (void *)smooth_filter_process && *slots[1] == (void *)smooth_filter_process_shutter)
		return NULL;  /* already installed */
	if ((ElfW(Addr))*slots[0] != defined[0] || (ElfW(Addr))*slots[1] != defined[1])
		return "libseekip.so's PLT does not point at its own filter functions (hooked by something else?)";

	smooth_set_originals((smooth_filter_fn)*slots[0], (smooth_shutter_fn)*slots[1]);
	if (plt_swap(&lib, slots[1], (void *)smooth_filter_process_shutter) != 0)
		return "cannot write libseekip.so's PLT slots";
	if (plt_swap(&lib, slots[0], (void *)smooth_filter_process) != 0) {
		plt_swap(&lib, slots[1], (void *)defined[1]);
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

/* seekpatch.Smooth.setOptions(int lines, int edge): stripe correction and left-edge levelling, 0 = off */
JNIEXPORT void JNICALL Java_seekpatch_Smooth_setOptions(JNIEnv *env, jclass cls, jint lines, jint edge)
{
	(void)env;
	(void)cls;
	smooth_set_options(lines, edge);
}
