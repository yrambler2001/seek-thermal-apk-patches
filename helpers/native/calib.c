/*
 * calib.c -- seek-patch calibration on Android: every temperature libseekip reports goes through
 * k * t + b.  JNI for seekpatch.Calib.
 *
 * libseekip's thermography_process turns each frame into degrees: the per-pixel image and the spot,
 * minimum and maximum.  Whatever the app shows or saves reads those (through seekip_process), and so
 * does the library's own temperature coloring later in the same frame (Span & Level, the isotherm
 * modes): the hook calls the original, then rewrites its outputs in place.  The library's internal
 * state (its min / max hysteresis, its rounding) stays in measured degrees, so nothing compounds from
 * frame to frame.  Only the active window is rewritten: the 16-bit output is written there alone.
 *
 * k and b are in degrees C; the library's output unit (thermography feature 50029: C, F or K) is read
 * every frame and b converted, so k * t + b holds in C whatever the unit.
 *
 * libseekip calls thermography_process through its PLT (plt.c).  Before touching anything the slot
 * must hold the address of libseekip's own thermography_process, and the sizes of thermography_process
 * and thermography_getfeature must be those of a verified build (the frame layout below is theirs).
 */
#include <android/log.h>
#include <jni.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "plt.h"

#define TAG "seek-patch"

/* st_size of thermography_process and thermography_getfeature in the verified libseekip builds */
static const struct { unsigned process, getfeature; const char *what; } VERIFIED[] = {
#if defined(__aarch64__)
	{10548, 1848, "2.11.3.2 arm64, apps 2.2.3 - 2.3.0"},
	{11488, 1824, "2.11.3.2 arm64, apps 2.3.1 - 2.3.4"},
#else
	{8516, 1732, "2.11.3.2 armv7, apps 2.2.3 - 2.3.0"},
	{8644, 1812, "2.11.3.2 armv7, apps 2.3.3 - 2.3.4"},
#endif
};

/* thermography_process's frame (libseekip 2.11.3.2) */
struct image {
	int width;  /* the row stride of the output loops */
	int height;
	int elem_size;
	void *data;
};

struct results {
	float spot, min, max;
	uint32_t min_x, min_y, max_x, max_y;
};

struct frame {
	struct image raw, filtered, output;
	struct results results;
};

_Static_assert(offsetof(struct frame, results) == (sizeof(void *) == 8 ? 72 : 48), "thermography frame layout");

/* thermography_getfeature's features */
enum {
	WINDOW_Y = 50006,    /* the active window's first column (window_y .. + window_h) */
	WINDOW_X = 50007,    /* its first row (window_x .. + window_w) */
	WINDOW_H = 50008,
	WINDOW_W = 50009,
	STAT_FLAGS = 50013,  /* bit 1: results not rounded to 0.1 */
	UNIT = 50029,        /* 0 C, 1 F, 2 K */
	SPOT_ON = 50031,     /* the spot was measured */
	FRAME_ON = 50032,    /* the minimum and maximum were */
};

typedef int (*process_fn)(void *context, struct frame *frame);
typedef int (*getfeature_fn)(void *context, unsigned feature, void *out, unsigned size);

static process_fn original;
static getfeature_fn getfeature;

/* the (k, b) the hook applies: two slots, the one to read published by index */
static struct { float k, b; } slots[2] = {{1.0f, 0.0f}, {1.0f, 0.0f}};
static int current;

static int get(void *context, unsigned feature, void *out)
{
	return getfeature(context, feature, out, 4);
}

static float tenth(float v)
{
	return roundf(v * 10.0f) / 10.0f;
}

static void apply(void *context, struct frame *f, float k, float b)
{
	unsigned unit = 0, flags = 0, window[4];
	int spot = 0, frame = 0;
	if (get(context, UNIT, &unit) || get(context, STAT_FLAGS, &flags) || get(context, SPOT_ON, &spot)
	    || get(context, FRAME_ON, &frame))
		return;
	for (int i = 0; i < 4; i++)
		if (get(context, WINDOW_Y + i, &window[i]))
			return;
	/* k * t + b in C, as k * t + b' in the output unit */
	if (unit == 1)
		b = 1.8f * b + 32.0f * (1.0f - k);
	else if (unit == 2)
		b = b + 273.15f * (1.0f - k);
	else if (unit != 0)
		return;

	struct image *out = &f->output;
	unsigned col0 = window[0], row0 = window[1], cols = window[2], rows = window[3];
	unsigned long stride = (unsigned long)out->width, size = stride * (unsigned long)out->height;
	if (out->data && out->width > 0 && out->height > 0 && rows && cols && col0 + cols <= stride
	    && (row0 + rows - 1) * stride + col0 + cols <= size) {
		for (unsigned r = row0; r < row0 + rows; r++) {
			if (out->elem_size == 4) {
				float *p = (float *)out->data + r * stride + col0;
				for (unsigned c = 0; c < cols; c++)
					p[c] = k * p[c] + b;
			} else if (out->elem_size == 2) {  /* (t + 40) * 64, clamped */
				uint16_t *p = (uint16_t *)out->data + r * stride + col0;
				for (unsigned c = 0; c < cols; c++) {
					float v = (k * (p[c] / 64.0f - 40.0f) + b + 40.0f) * 64.0f;
					p[c] = v <= 0.0f ? 0 : v >= 65535.0f ? 65535 : (uint16_t)v;
				}
			}
		}
	}

	struct results *res = &f->results;
	if (spot) {
		res->spot = k * res->spot + b;
		if (!(flags & 2))
			res->spot = tenth(res->spot);
	}
	if (frame) {  /* k > 0: the extremes stay where they are */
		res->min = k * res->min + b;
		res->max = k * res->max + b;
		if (!(flags & 2)) {
			res->min = tenth(res->min);
			res->max = tenth(res->max);
		}
	}
}

static int calib_thermography_process(void *context, struct frame *frame)
{
	int rc = original(context, frame);
	int i = __atomic_load_n(&current, __ATOMIC_ACQUIRE);
	float k = slots[i].k, b = slots[i].b;
	if (rc == 0 && frame && (k != 1.0f || b != 0.0f))
		apply(context, frame, k, b);
	return rc;
}

static char error[200];

static const char *install(void)
{
	struct plt_lib lib;
	const char *why = plt_open(&lib);
	if (why)
		return why;
	ElfW(Addr) defined = 0, query = 0;
	unsigned process = plt_symbol(&lib, "thermography_process", &defined);
	unsigned features = plt_symbol(&lib, "thermography_getfeature", &query);
	int known = -1;
	for (size_t i = 0; i < sizeof(VERIFIED) / sizeof(VERIFIED[0]); i++)
		if (process == VERIFIED[i].process && features == VERIFIED[i].getfeature)
			known = (int)i;
	if (known < 0) {
		snprintf(error, sizeof(error), "libseekip.so is not a build the hook was verified on (sizes %u / %u)",
		         process, features);
		return error;
	}
	int count;
	void **slot = plt_slot(&lib, "thermography_process", &count);
	if (count > 1)
		return "libseekip.so: two PLT slots for thermography_process";
	if (!slot)
		return "libseekip.so does not call thermography_process through its PLT";
	if (*slot == (void *)calib_thermography_process)
		return NULL;  /* already installed */
	if ((ElfW(Addr))*slot != defined)
		return "libseekip.so's PLT does not point at its own thermography_process (hooked by something else?)";
	getfeature = (getfeature_fn)query;
	original = (process_fn)*slot;
	if (plt_swap(&lib, slot, (void *)calib_thermography_process) != 0)
		return "cannot write libseekip.so's PLT slot";
	__android_log_print(ANDROID_LOG_INFO, TAG, "calibration: hooked libseekip %s", VERIFIED[known].what);
	return NULL;
}

/* seekpatch.Calib.install(): null when hooked, else why not */
JNIEXPORT jstring JNICALL Java_seekpatch_Calib_install(JNIEnv *env, jclass cls)
{
	(void)cls;
	const char *why = install();
	return why ? (*env)->NewStringUTF(env, why) : NULL;
}

/* seekpatch.Calib.set(float k, float b): from the next frame on, t -> k * t + b (degrees C) */
JNIEXPORT void JNICALL Java_seekpatch_Calib_set(JNIEnv *env, jclass cls, jfloat k, jfloat b)
{
	(void)env;
	(void)cls;
	if (!(k > 0.0f) || !isfinite(k) || !isfinite(b))
		return;
	int next = !__atomic_load_n(&current, __ATOMIC_ACQUIRE);
	slots[next].k = k;
	slots[next].b = b;
	__atomic_store_n(&current, next, __ATOMIC_RELEASE);
}
