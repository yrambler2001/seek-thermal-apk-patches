/* smooth.h -- seek-patch smart_smoothing: the hook around libseekip's first filter (see smooth.c). */
#ifndef SEEKPATCH_SMOOTH_H
#define SEEKPATCH_SMOOTH_H

/* libseekip's filter_process(state, frames) and filter_process_shutter(state) */
typedef int (*smooth_filter_fn)(void *state, void *frames);
typedef int (*smooth_shutter_fn)(void *state);

/* The originals the wrappers call (the GOT entries they replace). */
void smooth_set_originals(smooth_filter_fn filter, smooth_shutter_fn shutter);
/* The replacements. */
int smooth_filter_process(void *state, void *frames);
int smooth_filter_process_shutter(void *state);
/* Any thread: turn the filter on or off (off = the library's own processing, untouched). */
void smooth_set_enabled(int on);

/* Counters since the last call (the host test reads them; Android logs them every 256 frames). */
struct smooth_stats {
	int frames, shutters, gaps, other, learned;
	float noise;
};
void smooth_take_stats(struct smooth_stats *out);

/* Provided by the platform file (smooth_android.c, or the host test). */
void smooth_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
double smooth_now_ms(int thread_cpu);

#endif
