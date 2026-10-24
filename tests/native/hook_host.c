/* hook_host: drive smart_smoothing's hook (helpers/native/smooth.c) on the host with a stand-in for the
 * image library, or (-DDIRECT) run the filter directly on the same frames, as the research build did.
 *
 *   hook_host IN.u16 W H N OUT.u16 [key=value ...]
 *     shutter=K   a shutter event before frame K (the library's filter_process_shutter, both filters)
 *     other=K     frame K is not an image (the library clears stages 0x187, the second filter skips it)
 *     off=1       smart smoothing stays off
 *     lines=N     stripe correction (tnr lines, default 3; 0 = off), set before the first frame
 *     edge=N      left-edge levelling (tnr edge, default 6; 0 = off)
 *     plain=K     from frame K both are switched off (smooth_set_options(0, 0) between two frames)
 *
 * The stand-in library mirrors what seekip_process does with its two filters, in the layout the hook
 * expects: filter 1 reads work0 and writes work3, filter 2 reads work3.  Both "filters" copy.
 * DIRECT: frame 0 passes through, frames 1.. go through tnr_process with "NR new+LE" (lines 3, edge 6,
 * shutter halve), tnr_shutter before frame K -- what the hook gives once it has found the filters on
 * frame 0.  Prints one line of counters. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "tnr.h"
#ifndef DIRECT
#include "smooth.h"
#endif

struct frame {
	void *pixels;
	int count;
	int bytes_per_pixel;
};

struct frame_set {
	struct frame *in, *out, *scratch, *aux;
	int control_flags;
};

static int filter1, filter2;  /* the filters' states: only their addresses matter */
static int alpf_seen, filter2_calls, shutter_calls;

static int stand_in_filter(void *state, void *frames)
{
	struct frame_set *s = frames;
	if (state == &filter1 && (s->control_flags & 0x4))
		alpf_seen++;
	if (state == &filter2)
		filter2_calls++;
	memcpy(s->out->pixels, s->in->pixels, (size_t)s->in->count * 2);
	return 0;
}

static int stand_in_shutter(void *state)
{
	(void)state;
	shutter_calls++;
	return 0;
}

#ifndef DIRECT
void smooth_log(const char *fmt, ...)
{
	(void)fmt;
}

double smooth_now_ms(int thread_cpu)
{
	struct timespec ts;
	clock_gettime(thread_cpu ? CLOCK_THREAD_CPUTIME_ID : CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}
#endif

int main(int argc, char **argv)
{
	if (argc < 6) {
		fprintf(stderr, "usage: %s IN.u16 W H N OUT.u16 [shutter=K] [other=K] [off=1] [lines=N] [edge=N] [plain=K]\n", argv[0]);
		return 2;
	}
	int w = atoi(argv[2]), h = atoi(argv[3]), n = atoi(argv[4]), shutter = -1, other = -1, off = 0, lines = 3, edge = 6, plain = -1;
	for (int i = 6; i < argc; i++) {
		char key[16];
		int v;
		if (sscanf(argv[i], "%15[^=]=%d", key, &v) != 2)
			return 2;
		if (!strcmp(key, "shutter")) shutter = v;
		else if (!strcmp(key, "other")) other = v;
		else if (!strcmp(key, "off")) off = v;
		else if (!strcmp(key, "lines")) lines = v;
		else if (!strcmp(key, "edge")) edge = v;
		else if (!strcmp(key, "plain")) plain = v;
		else return 2;
	}
	size_t px = (size_t)w * h;
	uint16_t *frames = malloc(px * n * 2), *out = malloc(px * n * 2);
	FILE *f = fopen(argv[1], "rb");
	if (!f || fread(frames, 2, px * n, f) != px * n)
		return 3;
	fclose(f);
#ifdef DIRECT
	(void)stand_in_filter;
	(void)stand_in_shutter;
	struct tnr_params p;
	tnr_default_params(&p);
	p.lines = lines;
	p.edge = edge;
	p.shutter = TNR_SHUTTER_HALVE;
	struct tnr *t = tnr_create(w, h, &p);
	memcpy(out, frames, px * 2);
	for (int i = 1; i < n; i++) {
		if (i == plain) {  /* new options: the hook starts the filter again with them */
			tnr_destroy(t);
			p.lines = p.edge = 0;
			t = tnr_create(w, h, &p);
		}
		if (i == shutter)
			tnr_shutter(t);
		if (i == other) {  /* not an image: left alone, and the next image starts afresh */
			tnr_reset(t);
			memcpy(out + px * i, frames + px * i, px * 2);
			continue;
		}
		tnr_process(t, frames + px * i, out + px * i, NULL);
	}
	printf("direct %d frames\n", n);
#else
	uint16_t *work0 = malloc(px * 2), *work3 = malloc(px * 2), *work4 = malloc(px * 2), *work2 = malloc(px * 2);
	struct frame w0 = {work0, (int)px, 2}, w3 = {work3, (int)px, 2}, w4 = {work4, (int)px, 2}, w2 = {work2, (int)px, 2};
	struct frame aux = {NULL, 0, 0}, none = {NULL, 0, 0};
	smooth_set_originals(stand_in_filter, stand_in_shutter);
	smooth_set_enabled(!off);
	smooth_set_options(lines, edge);
	for (int i = 0; i < n; i++) {
		if (i == plain)
			smooth_set_options(0, 0);
		if (i == shutter) {
			smooth_filter_process_shutter(&filter1);
			smooth_filter_process_shutter(&filter2);
		}
		memcpy(work0, frames + px * i, px * 2);
		struct frame_set first = {&w0, &w3, &w4, &aux, i == other ? 0x86 & ~0x187 : 0x86};
		smooth_filter_process(&filter1, &first);
		memcpy(out + px * i, work3, px * 2);
		if (i != other) {
			struct frame_set second = {&w3, &w2, &none, &aux, 0x10};
			smooth_filter_process(&filter2, &second);
		}
	}
	struct smooth_stats s;
	smooth_take_stats(&s);
	printf("hook frames=%d learned=%d shutters=%d other=%d alpf_seen=%d filter2=%d shutter_calls=%d\n", s.frames,
	       s.learned, s.shutters, s.other, alpf_seen, filter2_calls, shutter_calls);
#endif
	f = fopen(argv[5], "wb");
	if (!f || fwrite(out, 2, px * n, f) != px * n)
		return 3;
	fclose(f);
	return 0;
}
