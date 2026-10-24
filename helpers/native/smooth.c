/*
 * smooth.c -- seek-patch smart_smoothing: motion-compensated temporal noise reduction (tnr.c) on the
 * output of libseekip's first filter, in place, before anything downstream reads it.
 *
 * libseekip's seekip_process runs, per frame (facts read from the disassembly of the libraries of
 * apps 2.2.3 - 2.3.4, arm64-v8a and armeabi-v7a; see docs/smart-smoothing.md):
 *
 *     filter_process(filter1, {in = work0, out = work3, scratch, aux, flags})
 *     ... temperatures, spot meter (from work3) ...
 *     filter_process(filter2, {in = work3, ...})        image frames only
 *
 * and, at a shutter event, filter_process_shutter(filter1) then (filter2).  The flags are the
 * filter-stage mask; for frames that are not images the library clears bits 0x187 first.
 *
 * smooth_android.c points libseekip's GOT entries for those two functions at the wrappers here.
 * Nothing here knows libseekip's own types: a frame is {pixels, pixel count, bytes per pixel},
 * a frame set four frame pointers and the flags, which is all the wrappers touch.
 *
 *   - which state is the first filter: the call whose input is the previous call's output is the
 *     second filter, the previous one the first (learnt again whenever an unknown state appears:
 *     a new camera connection);
 *   - image frames: any of bits 0x187 set;
 *   - while on: alpf (bit 0x4, the library's own temporal smoothing) is cleared for the first
 *     filter, and its output goes through tnr_process in place;
 *   - shutter: the estimate keeps half its weight (tnr_shutter); frames that are not images, and a
 *     pause of over a second (the camera was unplugged, the app paused), restart it;
 *   - stripe correction (tnr lines) and left-edge levelling (tnr edge) can be switched at run time
 *     (smooth_set_options); a change restarts the filter with the new parameters.
 * Anything unexpected (an unknown image size, a missing pointer) leaves the frame to the library.
 */
#if defined(__ANDROID__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE  /* sched_getcpu */
#endif
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#ifdef __ANDROID__
#include <sched.h>
#endif

#include "smooth.h"
#include "tnr.h"

struct frame {
	void *pixels;
	int count;            /* width * height */
	int bytes_per_pixel;  /* 2: u16 */
};

struct frame_set {
	struct frame *in, *out, *scratch, *aux;
	int control_flags;    /* filter-stage mask */
};

#define NOT_IMAGE_CLEARS 0x187  /* the stages seekip_process turns off for frames that are not images */
#define ALPF 0x4                /* the library's temporal filter */
#define GAP_MS 1000.0
#define LOG_EVERY 256

static const struct { int w, h; } SIZES[] = {{206, 156}, {320, 240}};  /* Compact / Nano, Compact Pro */

#define LINES 3  /* "NR new+LE": robust column-stripe correction, both halves of a line must agree */
#define EDGE 6   /* the screen-left strip: the last 6 buffer columns */

static smooth_filter_fn orig_filter;
static smooth_shutter_fn orig_shutter;
static int g_enabled;  /* written by any thread, read by the camera thread (atomic) */
static int g_options = LINES | EDGE << 8;  /* lines | edge << 8; written by any thread (atomic) */

static struct {  /* camera thread only */
	int on;
	void *f1, *f2, *last_state;
	struct frame *last_out;
	struct tnr *t;
	int w, h, options;
	double last_ms;
	struct smooth_stats s;
	double wall, cpu, cpu_max;
	int cores[16];  /* frames per CPU core */
	int logged, warned_size;
} g;

void smooth_set_originals(smooth_filter_fn filter, smooth_shutter_fn shutter)
{
	orig_filter = filter;
	orig_shutter = shutter;
}

void smooth_set_enabled(int on)
{
	__atomic_store_n(&g_enabled, on ? 1 : 0, __ATOMIC_RELEASE);
}

void smooth_set_options(int lines, int edge)
{
	lines = lines < 0 ? 0 : lines > 3 ? 3 : lines;
	edge = edge < 0 ? 0 : edge > TNR_EDGE_MAX ? TNR_EDGE_MAX : edge;
	__atomic_store_n(&g_options, lines | edge << 8, __ATOMIC_RELEASE);
}

void smooth_take_stats(struct smooth_stats *out)
{
	*out = g.s;
	out->noise = g.t ? tnr_sigma(g.t) : 0;
	g.s = (struct smooth_stats){0};
	g.wall = g.cpu = g.cpu_max = 0;
	for (int i = 0; i < 16; i++)
		g.cores[i] = 0;
}

/* "NR new+LE" of the research build: robust column-stripe correction and the screen-left strip,
 * unless switched off (options: lines | edge << 8) */
static void params(struct tnr_params *p, int options)
{
	tnr_default_params(p);
	p->lines = options & 0xff;
	p->edge = options >> 8;
	p->shutter = TNR_SHUTTER_HALVE;
}

static void set_on(int on)
{
	g.on = on;
	g.f1 = g.f2 = g.last_state = NULL;
	g.last_out = NULL;
	if (g.t) {
		tnr_destroy(g.t);
		g.t = NULL;
	}
	smooth_log("smart_smoothing: %s", on ? "on" : "off");
}

/* 1: the first filter, 2: the second, 0: not known (yet) */
static int role_of(void *state, struct frame_set *set)
{
	int role = 0;
	if (g.f1 && state == g.f1) {
		role = 1;
	} else if (g.f2 && state == g.f2) {
		role = 2;
	} else if (g.last_state && state != g.last_state && set->in && set->in == g.last_out) {
		g.f1 = g.last_state;  /* this call reads what the previous one wrote */
		g.f2 = state;
		g.s.learned++;
		role = 2;
	} else if (g.f1) {
		g.f1 = g.f2 = NULL;  /* a state never seen: a new connection, learn again */
	}
	g.last_state = state;
	g.last_out = set->out;
	return role;
}

static int image_size(const struct frame *f, int *w, int *h)
{
	if (!f->pixels || f->bytes_per_pixel != 2)
		return 0;
	for (size_t i = 0; i < sizeof(SIZES) / sizeof(SIZES[0]); i++)
		if (f->count == SIZES[i].w * SIZES[i].h) {
			*w = SIZES[i].w;
			*h = SIZES[i].h;
			return 1;
		}
	return 0;
}

static void process(uint16_t *px, int w, int h)
{
	double now = smooth_now_ms(0);
	int options = __atomic_load_n(&g_options, __ATOMIC_ACQUIRE);
	if (g.t && (g.w != w || g.h != h || g.options != options)) {
		tnr_destroy(g.t);  /* a new size, or new options: start again with them */
		g.t = NULL;
	}
	if (!g.t) {
		struct tnr_params p;
		params(&p, options);
		g.t = tnr_create(w, h, &p);
		if (!g.t) {
			if (!g.logged++)
				smooth_log("smart_smoothing: out of memory for %dx%d", w, h);
			return;
		}
		if (options != g.options)
			smooth_log("smart_smoothing: stripe correction %s (lines %d), left-edge levelling %s (edge %d)",
			           p.lines ? "on" : "off", p.lines, p.edge ? "on" : "off", p.edge);
		g.w = w;
		g.h = h;
		g.options = options;
	} else if (now - g.last_ms > GAP_MS) {
		tnr_reset(g.t);  /* the frames stopped: unplugged, paused */
		g.s.gaps++;
	}
	double c0 = smooth_now_ms(1);
#ifdef __ANDROID__
	int core = sched_getcpu();
	if (core >= 0 && core < 16)
		g.cores[core]++;
#endif
	tnr_process(g.t, px, px, NULL);
	double c = smooth_now_ms(1) - c0, end = smooth_now_ms(0);
	g.last_ms = end;
	g.wall += end - now;
	g.cpu += c;
	if (c > g.cpu_max)
		g.cpu_max = c;
	if (++g.s.frames == LOG_EVERY) {
		char cores[16 * 9] = "", *end = cores;
		for (int i = 0; i < 16; i++)
			if (g.cores[i])
				end += snprintf(end, sizeof(cores) - (size_t)(end - cores), " %d:%d", i, g.cores[i]);
		smooth_log("smart_smoothing: %d frames %dx%d: thread cpu %.2f ms/frame (max %.2f), wall %.2f; noise %.2f; "
		           "restarts: %d shutter (halved), %d pause, %d not an image; filters found %d time(s); cores%s",
		           g.s.frames, w, h, g.cpu / g.s.frames, g.cpu_max, g.wall / g.s.frames, tnr_sigma(g.t),
		           g.s.shutters, g.s.gaps, g.s.other, g.s.learned, cores);
		struct smooth_stats ignored;
		smooth_take_stats(&ignored);
	}
}

int smooth_filter_process(void *state, void *frames)
{
	int on = __atomic_load_n(&g_enabled, __ATOMIC_ACQUIRE);
	if (on != g.on)
		set_on(on);
	struct frame_set *set = frames;
	if (!on || !set)
		return orig_filter(state, frames);
	if (role_of(state, set) != 1 || !set->in || !set->out)
		return orig_filter(state, frames);
	if (!(set->control_flags & NOT_IMAGE_CLEARS)) {
		if (g.t)
			tnr_reset(g.t);  /* not an image */
		g.s.other++;
		return orig_filter(state, frames);
	}
	int w, h;
	if (!image_size(set->out, &w, &h)) {
		if (!g.warned_size++)
			smooth_log("smart_smoothing: not a known image (%d pixels, %d bytes each), left alone",
			           set->out->count, set->out->bytes_per_pixel);
		return orig_filter(state, frames);
	}
	int flags = set->control_flags;
	set->control_flags = flags & ~ALPF;
	int rc = orig_filter(state, frames);
	set->control_flags = flags;
	if (rc == 0 && set->out->pixels)
		process((uint16_t *)set->out->pixels, w, h);
	return rc;
}

int smooth_filter_process_shutter(void *state)
{
	if (g.on && g.t && g.f1 && state == g.f1) {
		tnr_shutter(g.t);
		g.s.shutters++;
	}
	return orig_shutter(state);
}
