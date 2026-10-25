/*
 * lock.c -- seek-patch lock_range on Android: holds libseekip's contrast curve.  JNI for seekpatch.Lock.
 *
 * libseekip's contrast stage (bclahe_process, the app's only one) builds, every frame, a histogram
 * of the frame's raw values, clips it, averages it with the previous frames' and turns it into the
 * curve that maps each raw value to one of the palette's 256 entries: create_transfer(state).  While
 * locked, the hook skips create_transfer for the stage it was locked on, so the stage keeps applying
 * the curve of the last frame shown: the image does not change at the tap, and a raw value keeps its
 * color from then on.  A call for another stage (the camera was reconnected: a new library context,
 * whose curve was never built) unlocks, and seekpatch.Lock hears of it through released().
 *
 * libseekip calls create_transfer through its PLT (plt.c).  Before touching anything the slot must
 * hold the address of libseekip's own create_transfer, of a size seen in a verified build.
 */
#include <android/log.h>
#include <jni.h>
#include <stdio.h>

#include "plt.h"

#define TAG "seek-patch"

/* st_size of create_transfer in the verified libseekip builds (2.11.3.2) */
static const struct { unsigned size; const char *what; } VERIFIED[] = {
#if defined(__aarch64__)
	{772, "2.11.3.2 arm64, apps 2.2.3 - 2.3.4"},
#else
	{656, "2.11.3.2 armv7, apps 2.2.3 - 2.3.0"},
	{602, "2.11.3.2 armv7, apps 2.3.3 - 2.3.4"},
#endif
};

typedef void (*transfer_fn)(void *state);

static transfer_fn original;
static void *last;    /* the stage of the latest call */
static void *held;    /* the stage whose curve is held; NULL: automatic */
static int pending;   /* hold the next call's stage (no call seen yet when the lock came) */
static int released;  /* a call for another stage ended a lock */

static void lock_create_transfer(void *state)
{
	__atomic_store_n(&last, state, __ATOMIC_RELEASE);
	if (__atomic_exchange_n(&pending, 0, __ATOMIC_ACQ_REL))
		__atomic_store_n(&held, state, __ATOMIC_RELEASE);
	void *h = __atomic_load_n(&held, __ATOMIC_ACQUIRE);
	if (h == state)
		return;
	if (h && __atomic_compare_exchange_n(&held, &h, NULL, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
		__atomic_store_n(&released, 1, __ATOMIC_RELEASE);
	original(state);
}

static char error[200];

static const char *install(void)
{
	struct plt_lib lib;
	const char *why = plt_open(&lib);
	if (why)
		return why;
	ElfW(Addr) defined = 0;
	unsigned size = plt_symbol(&lib, "create_transfer", &defined);
	int known = -1;
	for (size_t i = 0; i < sizeof(VERIFIED) / sizeof(VERIFIED[0]); i++)
		if (size == VERIFIED[i].size)
			known = (int)i;
	if (known < 0) {
		snprintf(error, sizeof(error), "libseekip.so is not a build the hook was verified on (create_transfer %u)", size);
		return error;
	}
	int count;
	void **slot = plt_slot(&lib, "create_transfer", &count);
	if (count > 1)
		return "libseekip.so: two PLT slots for create_transfer";
	if (!slot)
		return "libseekip.so does not call create_transfer through its PLT";
	if (*slot == (void *)lock_create_transfer)
		return NULL;  /* already installed */
	if ((ElfW(Addr))*slot != defined)
		return "libseekip.so's PLT does not point at its own create_transfer (hooked by something else?)";
	original = (transfer_fn)*slot;
	if (plt_swap(&lib, slot, (void *)lock_create_transfer) != 0)
		return "cannot write libseekip.so's PLT slot";
	__android_log_print(ANDROID_LOG_INFO, TAG, "lock_range: hooked libseekip %s", VERIFIED[known].what);
	return NULL;
}

/* seekpatch.Lock.install(): null when hooked, else why not */
JNIEXPORT jstring JNICALL Java_seekpatch_Lock_install(JNIEnv *env, jclass cls)
{
	(void)cls;
	const char *why = install();
	return why ? (*env)->NewStringUTF(env, why) : NULL;
}

/* seekpatch.Lock.hold(boolean): hold the curve of the last frame, or let go.  Right after install()
 * no call has been seen: the next one is held instead, before it builds a new curve. */
JNIEXPORT void JNICALL Java_seekpatch_Lock_hold(JNIEnv *env, jclass cls, jboolean on)
{
	(void)env;
	(void)cls;
	__atomic_store_n(&released, 0, __ATOMIC_RELEASE);
	void *stage = on ? __atomic_load_n(&last, __ATOMIC_ACQUIRE) : NULL;
	__atomic_store_n(&pending, on && !stage, __ATOMIC_RELEASE);
	__atomic_store_n(&held, stage, __ATOMIC_RELEASE);
}

/* seekpatch.Lock.released(): whether a reconnect ended the lock since the last call */
JNIEXPORT jboolean JNICALL Java_seekpatch_Lock_released(JNIEnv *env, jclass cls)
{
	(void)env;
	(void)cls;
	return __atomic_exchange_n(&released, 0, __ATOMIC_ACQ_REL) != 0;
}
