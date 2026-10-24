/* tnr.h -- motion-compensated temporal noise reduction on a u16 image (seek-patch smart_smoothing).
 * Written for seek-patch; see tnr.c.  MIT license. */
#ifndef SEEKPATCH_TNR_H
#define SEEKPATCH_TNR_H

#include <stdint.h>

struct tnr_params {
	float cap, k, k2, eps, noise0, local_prior, local_max, fpn_rate, reset_inliers, edge_rate;
	int levels, iters, tile, local, zbox, lines, fpn, fpn_clip, shutter, edge;
};

enum { TNR_SHUTTER_RESET = 0, TNR_SHUTTER_KEEP = 1, TNR_SHUTTER_HALVE = 2 };
#define TNR_EDGE_MAX 16

struct tnr;

void tnr_default_params(struct tnr_params *p);
struct tnr *tnr_create(int width, int height, const struct tnr_params *p);
void tnr_destroy(struct tnr *t);
void tnr_reset(struct tnr *t);
void tnr_shutter(struct tnr *t);  /* a shutter restart: reset, keep or halve the weights (params.shutter) */
/* one frame: in and out may be the same buffer; outf (optional) receives the float output */
void tnr_process(struct tnr *t, const uint16_t *in, uint16_t *out, float *outf);
struct tnr_params *tnr_params_of(struct tnr *t);
float tnr_sigma(const struct tnr *t);

#endif
