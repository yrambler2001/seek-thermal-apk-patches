/*
 * tnr.c -- motion-compensated recursive temporal noise reduction (seek-patch smart_smoothing).
 *
 * Written from scratch for seek-patch's research (superres: live/prototype/tnr.py is the reference
 * implementation, live/native/seekip/src/tnr/tnr.c the original of this file, minus its seekip glue).
 * It contains no Seek code: it works on a plain u16 image and includes only libc / libm headers.
 * MIT license, like the rest of seek-patch.
 *
 *   1. align the new frame f to the running estimate acc (last frame's coordinates): f(x) ~ acc(x + t) + c,
 *      Gauss-Newton with Huber weights on a 2-level pyramid (t: shift, c: level offset);
 *   2. refine per 16 px tile: a regularised shift per tile, smoothed, interpolated to every pixel;
 *   3. warp acc (Catmull-Rom) and its per-pixel weight (bilinear) into the new frame;
 *   4. blend per pixel: out = (w a + f) / (w + 1), w = min(weight, cap - 1) scaled down to 0 as the
 *      residual |f - a| goes from k to 2k expected standard deviations (noise of both, plus eps px of
 *      misalignment on edges; also tested on the 3x3 mean residual, as motion is coherent);
 *   5. the noise is re-estimated every frame from flat, settled pixels.
 *
 * Optional: per-frame column/row offsets (lines), the screen-left strip (edge) and a learnt fixed
 * pattern in sensor coordinates.  No dependencies beyond libc/libm; every buffer is allocated by
 * tnr_create.
 *
 * Speed: the hot loops (alignment sums, the per-pixel warp, the blend) have NEON versions on arm64
 * (build with -DTNR_NO_NEON for the portable scalar code, which computes the same thing).
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "tnr.h"

#if defined(__ARM_NEON) && defined(__aarch64__) && !defined(TNR_NO_NEON)
#include <arm_neon.h>
#define TNR_NEON 1
#endif

#define MAX_LEVELS 4


#ifdef TNR_PROFILE  /* host harness only: time per section */
#include <time.h>
double tnr_prof[10];
static double prof_t0;
static double prof_now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6; }
#define PROF_START() (prof_t0 = prof_now())
#define PROF(i) do { double _t = prof_now(); tnr_prof[i] += _t - prof_t0; prof_t0 = _t; } while (0)
#else
#define PROF_START() ((void)0)
#define PROF(i) ((void)0)
#endif

struct tnr {
	int w, h, n;
	struct tnr_params p;
	int have;
	float sigma;
	float *acc, *wt, *fpn;
	float *f, *a, *gx, *gy, *r, *box, *tmp, *wtw, *var, *z, *sel, *sel2;
	float *pa[MAX_LEVELS], *pf[MAX_LEVELS];
	int pw[MAX_LEVELS], ph[MAX_LEVELS];
	float *tdx, *tdy, *tt[5];
	float *col, *row, *lscr;              /* lines: per-frame column / row offsets, 4 x max(w, h) scratch */
	int *tcol;                            /* tile field -> pixels: tile column and weight of each x */
	float *tcolw, *udx, *vdy, *tfx, *tfy; /* ... the field interpolated in x per tile row, per-row scratch */
	float *accp;                          /* acc with a 1 px replicated border (the warp's taps) */
	int nx, ny;
	uint32_t hist[2048];  /* median() */
	float edge_off[TNR_EDGE_MAX];  /* the edge strip's per-column offset (EMA) */
	int edge_have;
};

void tnr_default_params(struct tnr_params *p)
{
	p->cap = 8.0f;
	p->k = 3.0f;
	p->k2 = 6.0f;
	p->eps = 0.05f;
	p->noise0 = 6.0f;
	p->local_prior = 0.1f;
	p->local_max = 1.5f;
	p->fpn_rate = 1.0f / 64;
	p->reset_inliers = 0.5f;
	p->levels = 2;
	p->iters = 3;
	p->tile = 16;
	p->local = 1;
	p->zbox = 1;
	p->lines = 0;
	p->fpn = 0;
	p->fpn_clip = 1;
	p->shutter = TNR_SHUTTER_HALVE;
	p->edge = 0;
	p->edge_rate = 1.0f / 32;  /* measured: live/prototype/shutter.py */
}

/* ---- helpers ------------------------------------------------------------------------------------ */

static inline float clampf(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }

/* bilinear, coordinates clamped to [0, w-1.001] x [0, h-1.001] (edge replicated) */
static inline float lin(const float *img, int w, int h, float x, float y)
{
	float xc = clampf(x, 0.0f, (float)w - 1.001f), yc = clampf(y, 0.0f, (float)h - 1.001f);
	int x0 = (int)xc, y0 = (int)yc;
	float fx = xc - (float)x0, fy = yc - (float)y0;
	const float *p = img + y0 * w + x0;
	return (p[0] * (1 - fx) + p[1] * fx) * (1 - fy) + (p[w] * (1 - fx) + p[w + 1] * fx) * fy;
}

/* Catmull-Rom (a = -0.5), edge replicated */
static inline float cubic(const float *img, int w, int h, float x, float y)
{
	float xc = clampf(x, 0.0f, (float)w - 1.001f), yc = clampf(y, 0.0f, (float)h - 1.001f);
	int x0 = (int)floorf(xc), y0 = (int)floorf(yc);
	float tx = xc - (float)x0, ty = yc - (float)y0;
	float wx[4], wy[4];
	float t2 = tx * tx, t3 = t2 * tx;
	wx[0] = (-t3 + 2 * t2 - tx) * 0.5f;
	wx[1] = (3 * t3 - 5 * t2 + 2) * 0.5f;
	wx[2] = (-3 * t3 + 4 * t2 + tx) * 0.5f;
	wx[3] = (t3 - t2) * 0.5f;
	t2 = ty * ty;
	t3 = t2 * ty;
	wy[0] = (-t3 + 2 * t2 - ty) * 0.5f;
	wy[1] = (3 * t3 - 5 * t2 + 2) * 0.5f;
	wy[2] = (-3 * t3 + 4 * t2 + ty) * 0.5f;
	wy[3] = (t3 - t2) * 0.5f;
	if (x0 >= 1 && x0 <= w - 3 && y0 >= 1 && y0 <= h - 3) {  /* all 16 taps inside */
		const float *r0 = img + (y0 - 1) * w + x0 - 1;
		float s0 = wx[0] * r0[0] + wx[1] * r0[1] + wx[2] * r0[2] + wx[3] * r0[3];
		r0 += w;
		float s1 = wx[0] * r0[0] + wx[1] * r0[1] + wx[2] * r0[2] + wx[3] * r0[3];
		r0 += w;
		float s2 = wx[0] * r0[0] + wx[1] * r0[1] + wx[2] * r0[2] + wx[3] * r0[3];
		r0 += w;
		float s3 = wx[0] * r0[0] + wx[1] * r0[1] + wx[2] * r0[2] + wx[3] * r0[3];
		return wy[0] * s0 + wy[1] * s1 + wy[2] * s2 + wy[3] * s3;
	}
	int xs[4];
	for (int i = 0; i < 4; i++) {
		int xi = x0 + i - 1;
		xs[i] = xi < 0 ? 0 : (xi > w - 1 ? w - 1 : xi);
	}
	float out = 0;
	for (int j = 0; j < 4; j++) {
		int yj = y0 + j - 1;
		yj = yj < 0 ? 0 : (yj > h - 1 ? h - 1 : yj);
		const float *row = img + yj * w;
		out += wy[j] * (wx[0] * row[xs[0]] + wx[1] * row[xs[1]] + wx[2] * row[xs[2]] + wx[3] * row[xs[3]]);
	}
	return out;
}

static void down2(const float *restrict src, int w, int h, float *restrict dst)
{
	int w2 = w / 2, h2 = h / 2;
	for (int y = 0; y < h2; y++) {
		const float *restrict p0 = src + 2 * y * w, *restrict p1 = p0 + w;
		float *restrict o = dst + y * w2;
		for (int x = 0; x < w2; x++)
			o[x] = 0.25f * (p0[2 * x] + p1[2 * x] + p0[2 * x + 1] + p1[2 * x + 1]);
	}
}

/* central differences, one-sided at the border */
static void grad(const float *restrict img, int w, int h, float *restrict gx, float *restrict gy)
{
	for (int y = 0; y < h; y++) {
		const float *restrict row = img + y * w;
		float *restrict ox = gx + y * w;
		for (int x = 1; x < w - 1; x++)
			ox[x] = 0.5f * (row[x + 1] - row[x - 1]);
		ox[0] = row[1] - row[0];
		ox[w - 1] = row[w - 1] - row[w - 2];
	}
	for (int x = 0; x < w; x++) {
		gy[x] = img[w + x] - img[x];
		gy[(h - 1) * w + x] = img[(h - 1) * w + x] - img[(h - 2) * w + x];
	}
	for (int y = 1; y < h - 1; y++) {
		const float *restrict up = img + (y - 1) * w, *restrict dn = img + (y + 1) * w;
		float *restrict o = gy + y * w;
		for (int x = 0; x < w; x++)
			o[x] = 0.5f * (dn[x] - up[x]);
	}
}

/* 3x3 mean, edge replicated (separable: column sums, then rows) */
static void box3(const float *restrict img, int w, int h, float *restrict tmp, float *restrict out)
{
	const float s = 1.0f / 9.0f;
	for (int y = 0; y < h; y++) {
		const float *restrict r0 = img + (y > 0 ? y - 1 : 0) * w, *restrict r1 = img + y * w;
		const float *restrict r2 = img + (y < h - 1 ? y + 1 : h - 1) * w;
		float *restrict o = out + y * w;
		for (int x = 0; x < w; x++)
			tmp[x] = r0[x] + r1[x] + r2[x];
		for (int x = 1; x < w - 1; x++)
			o[x] = (tmp[x - 1] + tmp[x] + tmp[x + 1]) * s;
		o[0] = (2 * tmp[0] + tmp[1]) * s;
		o[w - 1] = (tmp[w - 2] + 2 * tmp[w - 1]) * s;
	}
}

/* k-th smallest (0-based), reorders v */
static float select_k(float *v, int n, int k)
{
	int lo = 0, hi = n - 1;
	while (lo < hi) {
		float piv = v[(lo + hi) >> 1];
		int i = lo, j = hi;
		while (i <= j) {
			while (v[i] < piv) i++;
			while (v[j] > piv) j--;
			if (i <= j) {
				float t = v[i];
				v[i] = v[j];
				v[j] = t;
				i++;
				j--;
			}
		}
		if (k <= j)
			hi = j;
		else if (k >= i)
			lo = i;
		else
			return v[k];
	}
	return v[k];
}

/* float -> uint32 with the same order (no NaNs here) */
static inline uint32_t fkey(float f)
{
	uint32_t b;
	memcpy(&b, &f, 4);
	return (b & 0x80000000u) ? ~b : (b | 0x80000000u);
}

/* median as numpy computes it (mean of the two middle values for even n); overwrites v.  Exact: a
 * histogram of the top 11 bits of the order-preserving key finds the bucket holding the middle, a
 * branch-free pass keeps that bucket's values, and quickselect runs on those only.  hist: 2048 words. */
static float median(float *v, int n, uint32_t *hist)
{
	if (n <= 0)
		return 0;
	int k = n / 2, below = 0, m = 0;
	if (n >= 256) {
		memset(hist, 0, 2048 * sizeof(uint32_t));
		for (int i = 0; i < n; i++)
			hist[fkey(v[i]) >> 21]++;
		uint32_t b = 0;
		while (below + (int)hist[b] <= k)
			below += (int)hist[b++];
		float lomax = -INFINITY;
		for (int i = 0; i < n; i++) {
			float x = v[i];
			uint32_t kb = fkey(x) >> 21;
			v[m] = x;
			m += kb == b;
			lomax = (kb < b && x > lomax) ? x : lomax;
		}
		float hi = select_k(v, m, k - below);
		if (n & 1)
			return hi;
		float lo = lomax;  /* the next smaller value: in a lower bucket, or before hi in this one */
		for (int i = 0; i < k - below; i++)
			lo = v[i] > lo ? v[i] : lo;
		return 0.5f * (lo + hi);
	}
	float hi = select_k(v, n, k);
	if (n & 1)
		return hi;
	float lo = v[0];
	for (int i = 1; i < k; i++)
		if (v[i] > lo)
			lo = v[i];
	return 0.5f * (lo + hi);
}

/* ---- life cycle ---------------------------------------------------------------------------------- */

struct tnr *tnr_create(int width, int height, const struct tnr_params *p)
{
	if (width < 8 || height < 8)
		return NULL;
	struct tnr *t = calloc(1, sizeof(*t));
	if (!t)
		return NULL;
	t->w = width;
	t->h = height;
	t->n = width * height;
	if (p)
		t->p = *p;
	else
		tnr_default_params(&t->p);
	if (t->p.levels < 1)
		t->p.levels = 1;
	if (t->p.levels > MAX_LEVELS)
		t->p.levels = MAX_LEVELS;
	if (t->p.tile < 4)
		t->p.tile = 4;
	float **bufs[] = {&t->acc, &t->wt, &t->fpn, &t->f, &t->a, &t->gx, &t->gy, &t->r, &t->box,
	                  &t->wtw, &t->var, &t->z, &t->sel, &t->sel2};
	for (unsigned i = 0; i < sizeof(bufs) / sizeof(bufs[0]); i++) {
		*bufs[i] = calloc((size_t)t->n, sizeof(float));
		if (!*bufs[i]) {
			tnr_destroy(t);
			return NULL;
		}
	}
	t->pw[0] = width;
	t->ph[0] = height;
	for (int l = 1; l < MAX_LEVELS; l++) {
		t->pw[l] = t->pw[l - 1] / 2;
		t->ph[l] = t->ph[l - 1] / 2;
		t->pa[l] = calloc((size_t)t->pw[l] * t->ph[l] + 1, sizeof(float));
		t->pf[l] = calloc((size_t)t->pw[l] * t->ph[l] + 1, sizeof(float));
		if (!t->pa[l] || !t->pf[l]) {
			tnr_destroy(t);
			return NULL;
		}
	}
	/* the tile grid is sized for the smallest tile allowed, so the tile size can change later */
	int maxt = ((width + 3) / 4) * ((height + 3) / 4);
	t->tdx = calloc((size_t)maxt, sizeof(float));
	t->tdy = calloc((size_t)maxt, sizeof(float));
	for (int i = 0; i < 5; i++)
		t->tt[i] = calloc((size_t)maxt, sizeof(float));
	int wm = width > height ? width : height;
	t->col = calloc((size_t)width, sizeof(float));
	t->row = calloc((size_t)height, sizeof(float));
	t->lscr = calloc((size_t)wm * 4, sizeof(float));
	t->tmp = calloc((size_t)wm, sizeof(float));
	t->tcol = calloc((size_t)width, sizeof(int));
	t->tcolw = calloc((size_t)width, sizeof(float));
	t->udx = calloc((size_t)width, sizeof(float));
	t->vdy = calloc((size_t)width, sizeof(float));
	t->tfx = calloc((size_t)width * ((height + 3) / 4 + 1), sizeof(float));
	t->tfy = calloc((size_t)width * ((height + 3) / 4 + 1), sizeof(float));
	t->accp = calloc((size_t)(width + 2) * (height + 2), sizeof(float));
	if (!t->tdx || !t->tdy || !t->tt[4] || !t->col || !t->row || !t->lscr || !t->tmp || !t->tcol ||
	    !t->tcolw || !t->udx || !t->vdy || !t->tfx || !t->tfy || !t->accp) {
		tnr_destroy(t);
		return NULL;
	}
	t->sigma = t->p.noise0;
	return t;
}

void tnr_destroy(struct tnr *t)
{
	if (!t)
		return;
	float *bufs[] = {t->acc, t->wt, t->fpn, t->f, t->a, t->gx, t->gy, t->r, t->box, t->tmp, t->wtw, t->var,
	                 t->z, t->sel, t->sel2, t->tdx, t->tdy, t->col, t->row, t->lscr, t->tcolw,
	                 t->udx, t->vdy, t->tfx, t->tfy, t->accp};
	for (unsigned i = 0; i < sizeof(bufs) / sizeof(bufs[0]); i++)
		free(bufs[i]);
	free(t->tcol);
	for (int l = 1; l < MAX_LEVELS; l++) {
		free(t->pa[l]);
		free(t->pf[l]);
	}
	for (int i = 0; i < 5; i++)
		free(t->tt[i]);
	free(t);
}

void tnr_reset(struct tnr *t)
{
	if (t)
		t->have = 0;
}

/* the library's shutter restart (a NUC update): what happens to the running estimate */
void tnr_shutter(struct tnr *t)
{
	if (!t || !t->have)
		return;
	switch (t->p.shutter) {
	case TNR_SHUTTER_KEEP:  /* the level offset c and the residual test absorb the step */
		break;
	case TNR_SHUTTER_HALVE:
		for (int i = 0; i < t->n; i++)
			t->wt[i] = t->wt[i] > 2.0f ? 0.5f * t->wt[i] : 1.0f;
		break;
	default:
		t->have = 0;
	}
}

struct tnr_params *tnr_params_of(struct tnr *t) { return t ? &t->p : NULL; }
float tnr_sigma(const struct tnr *t) { return t ? t->sigma : 0; }

/* ---- frame-wide alignment: f(x) ~ acc(x + t) + c -------------------------------------------------- */

static void solve3(double H[3][3], const double g[3], double d[3])
{
	double a[3][4];
	for (int i = 0; i < 3; i++) {
		for (int j = 0; j < 3; j++)
			a[i][j] = H[i][j];
		a[i][3] = g[i];
	}
	for (int c = 0; c < 3; c++) {
		int piv = c;
		for (int i = c + 1; i < 3; i++)
			if (fabs(a[i][c]) > fabs(a[piv][c]))
				piv = i;
		if (piv != c)
			for (int j = 0; j < 4; j++) {
				double tmp = a[c][j];
				a[c][j] = a[piv][j];
				a[piv][j] = tmp;
			}
		if (a[c][c] == 0) {
			d[0] = d[1] = d[2] = 0;
			return;
		}
		for (int i = c + 1; i < 3; i++) {
			double m = a[i][c] / a[c][c];
			for (int j = c; j < 4; j++)
				a[i][j] -= m * a[c][j];
		}
	}
	for (int i = 2; i >= 0; i--) {
		double s = a[i][3];
		for (int j = i + 1; j < 3; j++)
			s -= a[i][j] * d[j];
		d[i] = s / a[i][i];
	}
}

/* one row of the Gauss-Newton sums for a pure shift (the same bilinear weights for every sample):
 * s = {h00, h01, h02, h11, h12, h22, g0, g1, g2}; returns the number of inliers (|r| < 3 sig) */
static int gn_row(const float *restrict Ar, const float *restrict Gx, const float *restrict Gy, const float *restrict Fr,
                  int w, int x0, int x1, const float bw[4], float cf, float inv_s, float sig, float s[9])
{
	float w00 = bw[0], w01 = bw[1], w10 = bw[2], w11 = bw[3];
	float h00 = 0, h01 = 0, h02 = 0, h11 = 0, h12 = 0, h22 = 0, g0 = 0, g1 = 0, g2 = 0;
	int nin = 0, x = x0;
#ifdef TNR_NEON
	{
		float32x4_t v00 = vdupq_n_f32(w00), v01 = vdupq_n_f32(w01), v10 = vdupq_n_f32(w10), v11 = vdupq_n_f32(w11);
		float32x4_t vc = vdupq_n_f32(cf), vis = vdupq_n_f32(inv_s), v2s = vdupq_n_f32(2 * sig), v3s = vdupq_n_f32(3 * sig);
		float32x4_t one = vdupq_n_f32(1.0f), tiny = vdupq_n_f32(1e-9f), z = vdupq_n_f32(0.0f);
		float32x4_t a00 = z, a01 = z, a02 = z, a11 = z, a12 = z, a22 = z, b0 = z, b1 = z, b2 = z;
		uint32x4_t cnt = vdupq_n_u32(0);
		for (; x + 3 <= x1; x += 4) {
			float32x4_t a = vmulq_f32(v00, vld1q_f32(Ar + x));
			a = vfmaq_f32(a, v01, vld1q_f32(Ar + x + 1));
			a = vfmaq_f32(a, v10, vld1q_f32(Ar + x + w));
			a = vfmaq_f32(a, v11, vld1q_f32(Ar + x + w + 1));
			float32x4_t ax = vmulq_f32(v00, vld1q_f32(Gx + x));
			ax = vfmaq_f32(ax, v01, vld1q_f32(Gx + x + 1));
			ax = vfmaq_f32(ax, v10, vld1q_f32(Gx + x + w));
			ax = vfmaq_f32(ax, v11, vld1q_f32(Gx + x + w + 1));
			ax = vmulq_f32(ax, vis);
			float32x4_t ay = vmulq_f32(v00, vld1q_f32(Gy + x));
			ay = vfmaq_f32(ay, v01, vld1q_f32(Gy + x + 1));
			ay = vfmaq_f32(ay, v10, vld1q_f32(Gy + x + w));
			ay = vfmaq_f32(ay, v11, vld1q_f32(Gy + x + w + 1));
			ay = vmulq_f32(ay, vis);
			float32x4_t r = vsubq_f32(vsubq_f32(vld1q_f32(Fr + x), a), vc);
			float32x4_t ar = vabsq_f32(r);
			float32x4_t wg = vbslq_f32(vcltq_f32(ar, v2s), one, vdivq_f32(v2s, vmaxq_f32(ar, tiny)));
			float32x4_t wax = vmulq_f32(wg, ax), way = vmulq_f32(wg, ay);
			a00 = vfmaq_f32(a00, wax, ax);
			a01 = vfmaq_f32(a01, wax, ay);
			a02 = vaddq_f32(a02, wax);
			a11 = vfmaq_f32(a11, way, ay);
			a12 = vaddq_f32(a12, way);
			a22 = vaddq_f32(a22, wg);
			b0 = vfmaq_f32(b0, wax, r);
			b1 = vfmaq_f32(b1, way, r);
			b2 = vfmaq_f32(b2, wg, r);
			cnt = vsubq_u32(cnt, vcltq_f32(ar, v3s));
		}
		h00 = vaddvq_f32(a00); h01 = vaddvq_f32(a01); h02 = vaddvq_f32(a02);
		h11 = vaddvq_f32(a11); h12 = vaddvq_f32(a12); h22 = vaddvq_f32(a22);
		g0 = vaddvq_f32(b0); g1 = vaddvq_f32(b1); g2 = vaddvq_f32(b2);
		nin = (int)vaddvq_u32(cnt);
	}
#endif
	for (; x <= x1; x++) {
		float a = w00 * Ar[x] + w01 * Ar[x + 1] + w10 * Ar[x + w] + w11 * Ar[x + w + 1];
		float ax = (w00 * Gx[x] + w01 * Gx[x + 1] + w10 * Gx[x + w] + w11 * Gx[x + w + 1]) * inv_s;
		float ay = (w00 * Gy[x] + w01 * Gy[x + 1] + w10 * Gy[x + w] + w11 * Gy[x + w + 1]) * inv_s;
		float r = Fr[x] - a - cf, ar = fabsf(r);
		float wg = ar < 2 * sig ? 1.0f : 2 * sig / (ar > 1e-9f ? ar : 1e-9f);
		float wax = wg * ax, way = wg * ay;
		h00 += wax * ax;
		h01 += wax * ay;
		h02 += wax;
		h11 += way * ay;
		h12 += way;
		h22 += wg;
		g0 += wax * r;
		g1 += way * r;
		g2 += wg * r;
		nin += ar < 3 * sig;
	}
	s[0] = h00; s[1] = h01; s[2] = h02; s[3] = h11; s[4] = h12; s[5] = h22; s[6] = g0; s[7] = g1; s[8] = g2;
	return nin;
}

static void align(struct tnr *t, float *out_tx, float *out_ty, float *out_c, float *out_inl)
{
	const struct tnr_params *p = &t->p;
	int L = p->levels;
	t->pa[0] = t->acc;
	t->pf[0] = t->f;
	for (int l = 1; l < L; l++) {
		down2(t->pa[l - 1], t->pw[l - 1], t->ph[l - 1], t->pa[l]);
		down2(t->pf[l - 1], t->pw[l - 1], t->ph[l - 1], t->pf[l]);
	}
	int ns = 0;  /* the level offset's first guess: median over every other row and column */
	for (int y = 0; y < t->h; y += 2)
		for (int x = 0; x < t->w; x += 2)
			t->sel[ns++] = t->f[y * t->w + x] - t->acc[y * t->w + x];
	double c = median(t->sel, ns, t->hist), m0 = 0, m1 = 0;
	float inl = 1.0f;
	for (int lev = L - 1; lev >= 0; lev--) {
		int s = 1 << lev, w = t->pw[lev], h = t->ph[lev];
		const float *A = t->pa[lev], *F = t->pf[lev];
		grad(A, w, h, t->gx, t->gy);
		float sig = t->sigma / (float)s;
		for (int it = 0; it < p->iters; it++) {
			double H[3][3] = {{0}}, g[3] = {0}, d[3];
			long nok = 0, nin = 0;
			float dxs = (float)(m0 / s), dys = (float)(m1 / s);
			/* a pure shift: every sample has the same bilinear weights; pixels whose sample falls outside
			 * the level are skipped (as are the few exactly on its last row or column) */
			int ix = (int)floorf(dxs), iy = (int)floorf(dys);
			float fx = dxs - (float)ix, fy = dys - (float)iy;
			float bw[4] = {(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy};
			int x0 = ix < 0 ? -ix : 0, x1 = (w - 2 - ix) < (w - 1) ? (w - 2 - ix) : (w - 1);
			int y0 = iy < 0 ? -iy : 0, y1 = (h - 2 - iy) < (h - 1) ? (h - 2 - iy) : (h - 1);
			float cf = (float)c, inv_s = 1.0f / (float)s;
			int ystep = lev == 0 ? 2 : 1;  /* full resolution: every other row is plenty for a shift */
			for (int y = y0 + (lev == 0 ? (y0 & 1) : 0); y <= y1; y += ystep) {
				float sr[9];
				int off = (y + iy) * w + ix;
				nin += gn_row(A + off, t->gx + off, t->gy + off, F + y * w, w, x0, x1, bw, cf, inv_s, sig, sr);
				if (x1 >= x0)
					nok += x1 - x0 + 1;
				H[0][0] += sr[0]; H[0][1] += sr[1]; H[0][2] += sr[2]; H[1][1] += sr[3]; H[1][2] += sr[4]; H[2][2] += sr[5];
				g[0] += sr[6]; g[1] += sr[7]; g[2] += sr[8];
			}
			H[1][0] = H[0][1];
			H[2][0] = H[0][2];
			H[2][1] = H[1][2];
			double reg = 1e-6 * (H[0][0] + H[1][1] + H[2][2]) / 3 + 1e-9;
			for (int i = 0; i < 3; i++)
				H[i][i] += reg;
			solve3(H, g, d);
			m0 += d[0];
			m1 += d[1];
			c += d[2];
			if (lev == 0)
				inl = nok ? (float)nin / (float)nok : 0.0f;
			if (hypot(d[0], d[1]) < 0.01)
				break;
		}
	}
	*out_tx = (float)m0;
	*out_ty = (float)m1;
	*out_c = (float)c;
	*out_inl = inl;
}

/* acc warped by a pure shift into t->a: separable Catmull-Rom where all taps are inside, cubic() elsewhere */
static void cubic_shift(struct tnr *t, float tx, float ty)
{
	int w = t->w, h = t->h;
	int ix = (int)floorf(tx), iy = (int)floorf(ty);
	float fx = tx - (float)ix, fy = ty - (float)iy, wx[4], wy[4];
	float t2 = fx * fx, t3 = t2 * fx;
	wx[0] = (-t3 + 2 * t2 - fx) * 0.5f; wx[1] = (3 * t3 - 5 * t2 + 2) * 0.5f;
	wx[2] = (-3 * t3 + 4 * t2 + fx) * 0.5f; wx[3] = (t3 - t2) * 0.5f;
	t2 = fy * fy; t3 = t2 * fy;
	wy[0] = (-t3 + 2 * t2 - fy) * 0.5f; wy[1] = (3 * t3 - 5 * t2 + 2) * 0.5f;
	wy[2] = (-3 * t3 + 4 * t2 + fy) * 0.5f; wy[3] = (t3 - t2) * 0.5f;
	/* interior: x + ix - 1 >= 0, x + ix + 2 <= w - 1 (and the same for y) */
	int xa = 1 - ix, xb = w - 3 - ix, ya = 1 - iy, yb = h - 3 - iy;
	if (xa < 0) xa = 0;
	if (xb > w - 1) xb = w - 1;
	if (ya < 0) ya = 0;
	if (yb > h - 1) yb = h - 1;
	float *restrict hp = t->box;  /* horizontal pass, rows of acc */
	float *restrict A = t->a;
	const float wx0 = wx[0], wx1 = wx[1], wx2 = wx[2], wx3 = wx[3], wy0 = wy[0], wy1 = wy[1], wy2 = wy[2], wy3 = wy[3];
	if (xa <= xb)
		for (int yy = 0; yy < h; yy++) {
			const float *restrict src = t->acc + yy * w + ix - 1;
			float *restrict dst = hp + yy * w;
			for (int x = xa; x <= xb; x++)
				dst[x] = wx0 * src[x] + wx1 * src[x + 1] + wx2 * src[x + 2] + wx3 * src[x + 3];
		}
	for (int y = 0; y < h; y++) {
		float *restrict o = A + y * w;
		if (y < ya || y > yb || xa > xb) {
			for (int x = 0; x < w; x++)
				o[x] = cubic(t->acc, w, h, (float)x + tx, (float)y + ty);
			continue;
		}
		const float *restrict c0 = hp + (y + iy - 1) * w, *restrict c1 = c0 + w, *restrict c2 = c1 + w, *restrict c3 = c2 + w;
		for (int x = 0; x < xa; x++)
			o[x] = cubic(t->acc, w, h, (float)x + tx, (float)y + ty);
		for (int x = xa; x <= xb; x++)
			o[x] = wy0 * c0[x] + wy1 * c1[x] + wy2 * c2[x] + wy3 * c3[x];
		for (int x = xb + 1; x < w; x++)
			o[x] = cubic(t->acc, w, h, (float)x + tx, (float)y + ty);
	}
}

/* ---- per-tile refinement: the local shift of each tile (tdx, tdy) ---------------------------------- */

/* the Huber-weighted sums of one run of pixels: s += {gx gx, gx gy, gy gy, gx r, gy r} */
static void tile_run(const float *restrict gx, const float *restrict gy, const float *restrict f, const float *restrict a,
                     int n, float c, float sig, float s[5])
{
	int x = 0;
	float hxx = 0, hxy = 0, hyy = 0, bx = 0, by = 0;
#ifdef TNR_NEON
	{
		float32x4_t vc = vdupq_n_f32(c), v2s = vdupq_n_f32(2 * sig), one = vdupq_n_f32(1.0f), tiny = vdupq_n_f32(1e-9f);
		float32x4_t z = vdupq_n_f32(0.0f), sxx = z, sxy = z, syy = z, sbx = z, sby = z;
		for (; x + 4 <= n; x += 4) {
			float32x4_t vgx = vld1q_f32(gx + x), vgy = vld1q_f32(gy + x);
			float32x4_t r = vsubq_f32(vld1q_f32(f + x), vaddq_f32(vld1q_f32(a + x), vc)), ar = vabsq_f32(r);
			float32x4_t wg = vbslq_f32(vcltq_f32(ar, v2s), one, vdivq_f32(v2s, vmaxq_f32(ar, tiny)));
			float32x4_t wgx = vmulq_f32(wg, vgx), wgy = vmulq_f32(wg, vgy);
			sxx = vfmaq_f32(sxx, wgx, vgx);
			sxy = vfmaq_f32(sxy, wgx, vgy);
			syy = vfmaq_f32(syy, wgy, vgy);
			sbx = vfmaq_f32(sbx, wgx, r);
			sby = vfmaq_f32(sby, wgy, r);
		}
		hxx = vaddvq_f32(sxx); hxy = vaddvq_f32(sxy); hyy = vaddvq_f32(syy); bx = vaddvq_f32(sbx); by = vaddvq_f32(sby);
	}
#endif
	for (; x < n; x++) {
		float r = f[x] - (a[x] + c), ar = fabsf(r);
		float wg = ar < 2 * sig ? 1.0f : 2 * sig / (ar > 1e-9f ? ar : 1e-9f);
		hxx += wg * gx[x] * gx[x];
		hxy += wg * gx[x] * gy[x];
		hyy += wg * gy[x] * gy[x];
		bx += wg * gx[x] * r;
		by += wg * gy[x] * r;
	}
	s[0] += hxx; s[1] += hxy; s[2] += hyy; s[3] += bx; s[4] += by;
}

static void local_field(struct tnr *t, float c)
{
	const struct tnr_params *p = &t->p;
	int w = t->w, h = t->h, T = p->tile;
	int nx = (w + T - 1) / T, ny = (h + T - 1) / T;
	grad(t->a, w, h, t->gx, t->gy);  /* the gradient of the shifted estimate (+ c: the same) */
	float sig = t->sigma;
	float *hxx = t->tt[0], *hxy = t->tt[1], *hyy = t->tt[2], *bx = t->tt[3], *by = t->tt[4];
	for (int k = 0; k < nx * ny; k++) {
		float s[5] = {0, 0, 0, 0, 0};
		int y0 = (k / nx) * T, x0 = (k % nx) * T;
		int ye = y0 + T < h ? y0 + T : h, xe = x0 + T < w ? x0 + T : w;
		for (int y = y0; y < ye; y++) {
			int i = y * w + x0;
			tile_run(t->gx + i, t->gy + i, t->f + i, t->a + i, xe - x0, c, sig, s);
		}
		hxx[k] = s[0]; hxy[k] = s[1]; hyy[k] = s[2]; bx[k] = s[3]; by[k] = s[4];
	}
	float lam = sig * sig / (p->local_prior * p->local_prior);
	for (int k = 0; k < nx * ny; k++) {
		float a = hxx[k] + lam, b = hxy[k], d = hyy[k] + lam;
		float det = a * d - b * b;
		float dx = (d * bx[k] - b * by[k]) / det, dy = (a * by[k] - b * bx[k]) / det;
		float mag = sqrtf(dx * dx + dy * dy);
		float sc = mag > 1e-9f ? p->local_max / mag : 1e9f;
		if (sc < 1) {
			dx *= sc;
			dy *= sc;
		}
		t->tdx[k] = dx;
		t->tdy[k] = dy;
	}
	/* 1-2-1 smoothing on the tile grid, edges replicated (rows, then columns) */
	float *tmp = hxx;
	for (int pass = 0; pass < 2; pass++) {
		float *q = pass ? t->tdy : t->tdx;
		for (int j = 0; j < ny; j++)
			for (int i = 0; i < nx; i++) {
				int jm = j > 0 ? j - 1 : 0, jp = j < ny - 1 ? j + 1 : ny - 1;
				tmp[j * nx + i] = (q[jm * nx + i] + 2 * q[j * nx + i] + q[jp * nx + i]) * 0.25f;
			}
		for (int j = 0; j < ny; j++)
			for (int i = 0; i < nx; i++) {
				int im = i > 0 ? i - 1 : 0, ip = i < nx - 1 ? i + 1 : nx - 1;
				q[j * nx + i] = (tmp[j * nx + im] + 2 * tmp[j * nx + i] + tmp[j * nx + ip]) * 0.25f;
			}
	}
	/* tile centres at T*i + (T-1)/2: the column and weight of every x (the clamp to n-1.001 is lin()'s) */
	for (int x = 0; x < w; x++) {
		float gxc = clampf(clampf(((float)x - (T - 1) * 0.5f) / T, 0.0f, (float)(nx - 1)), 0.0f, (float)nx - 1.001f);
		t->tcol[x] = (int)gxc;
		t->tcolw[x] = gxc - (float)(int)gxc;
	}
	for (int j = 0; j < ny; j++) {  /* each tile row interpolated in x (y follows per pixel row) */
		const float *dx0 = t->tdx + j * nx, *dy0 = t->tdy + j * nx;
		float *ox = t->tfx + j * w, *oy = t->tfy + j * w;
		for (int x = 0; x < w; x++) {
			int x0 = t->tcol[x];
			float fx = t->tcolw[x];
			ox[x] = dx0[x0] * (1 - fx) + dx0[x0 + 1] * fx;
			oy[x] = dy0[x0] * (1 - fx) + dy0[x0 + 1] * fx;
		}
	}
	t->nx = nx;
	t->ny = ny;
}

/* ---- the per-pixel warp: acc (Catmull-Rom) and wt (bilinear, 0 outside) at x + t + the tile field ----- */

static inline void warp_px(struct tnr *t, float u, float v, float c, int i)
{
	int w = t->w, h = t->h;
	int inside = u >= 0 && u <= (float)(w - 1) && v >= 0 && v <= (float)(h - 1);
	t->wtw[i] = inside ? lin(t->wt, w, h, u, v) : 0.0f;
	t->a[i] = cubic(t->acc, w, h, u, v) + c;
}

#ifdef TNR_NEON
/* the 4x4 window at p combined over its rows with the y weights Q: the 4 column sums */
static inline float32x4_t cr_cols(const float *p, int w, float32x4_t Q)
{
	float32x4_t s = vmulq_laneq_f32(vld1q_f32(p), Q, 0);
	s = vfmaq_laneq_f32(s, vld1q_f32(p + w), Q, 1);
	s = vfmaq_laneq_f32(s, vld1q_f32(p + 2 * w), Q, 2);
	return vfmaq_laneq_f32(s, vld1q_f32(p + 3 * w), Q, 3);
}

static inline void cr_weights(float32x4_t t, float32x4_t out[4])
{
	float32x4_t h = vdupq_n_f32(0.5f), t2 = vmulq_f32(t, t), t3 = vmulq_f32(t2, t);
	out[0] = vmulq_f32(vsubq_f32(vfmaq_n_f32(vnegq_f32(t3), t2, 2.0f), t), h);
	out[1] = vmulq_f32(vaddq_f32(vfmsq_f32(vmulq_n_f32(t3, 3.0f), t2, vdupq_n_f32(5.0f)), vdupq_n_f32(2.0f)), h);
	out[2] = vmulq_f32(vaddq_f32(vfmaq_n_f32(vmulq_n_f32(t3, -3.0f), t2, 4.0f), t), h);
	out[3] = vmulq_f32(vsubq_f32(t3, t2), h);
}

/* 4x4 transpose: lane j of the inputs -> vector j */
static inline void transpose4(const float32x4_t in[4], float32x4_t out[4])
{
	float32x4x2_t a = vtrnq_f32(in[0], in[1]), b = vtrnq_f32(in[2], in[3]);
	out[0] = vcombine_f32(vget_low_f32(a.val[0]), vget_low_f32(b.val[0]));
	out[1] = vcombine_f32(vget_low_f32(a.val[1]), vget_low_f32(b.val[1]));
	out[2] = vcombine_f32(vget_high_f32(a.val[0]), vget_high_f32(b.val[0]));
	out[3] = vcombine_f32(vget_high_f32(a.val[1]), vget_high_f32(b.val[1]));
}
#endif

static void warp_local(struct tnr *t, float tx, float ty, float c)
{
	const int w = t->w, h = t->h, ny = t->ny, T = t->p.tile, wp = w + 2;
	float *restrict udx = t->udx, *restrict vdy = t->vdy;
	/* acc with a replicated 1 px border: the Catmull-Rom taps of a clamped coordinate never leave it, and
	 * reading the border is exactly cubic()'s edge clamping */
	float *restrict ap = t->accp;
	for (int y = -1; y <= h; y++) {
		const float *src = t->acc + (y < 0 ? 0 : (y >= h ? h - 1 : y)) * w;
		float *dst = ap + (y + 1) * wp;
		memcpy(dst + 1, src, sizeof(float) * w);
		dst[0] = src[0];
		dst[w + 1] = src[w - 1];
	}
	for (int y = 0; y < h; y++) {
		/* this row's tile field: the two x-interpolated tile rows, interpolated in y */
		float gyc = clampf(clampf(((float)y - (T - 1) * 0.5f) / T, 0.0f, (float)(ny - 1)), 0.0f, (float)ny - 1.001f);
		int y0 = (int)gyc;
		float fy = gyc - (float)y0;
		const float *X0 = t->tfx + y0 * w, *X1 = X0 + w, *Y0 = t->tfy + y0 * w, *Y1 = Y0 + w;
		float yy = (float)y + ty;
		int x = 0;
#ifndef TNR_NEON
		for (int i = 0; i < w; i++) {
			udx[i] = X0[i] * (1 - fy) + X1[i] * fy;
			vdy[i] = Y0[i] * (1 - fy) + Y1[i] * fy;
		}
#else
		const float32x4_t vfy = vdupq_n_f32(fy), vofy = vdupq_n_f32(1 - fy);
		const float32x4_t zero = vdupq_n_f32(0.0f), one = vdupq_n_f32(1.0f), vtx = vdupq_n_f32(tx), vyy = vdupq_n_f32(yy);
		const float32x4_t umax = vdupq_n_f32((float)w - 1.001f), vmax = vdupq_n_f32((float)h - 1.001f), vc = vdupq_n_f32(c);
		const float32x4_t uin = vdupq_n_f32((float)(w - 1)), vin = vdupq_n_f32((float)(h - 1));
		const int32x4_t inc = {0, 1, 2, 3}, vwp = vdupq_n_s32(wp), vw = vdupq_n_s32(w);
		const float *wt = t->wt;
		(void)udx;
		(void)vdy;
		for (int xg = 0; xg < w; xg += 4) {
			x = xg + 4 <= w ? xg : w - 4;  /* the last group overlaps the previous one (same values) */
			float32x4_t dxl = vfmaq_f32(vmulq_f32(vld1q_f32(X0 + x), vofy), vld1q_f32(X1 + x), vfy);
			float32x4_t dyl = vfmaq_f32(vmulq_f32(vld1q_f32(Y0 + x), vofy), vld1q_f32(Y1 + x), vfy);
			float32x4_t u = vaddq_f32(vaddq_f32(vcvtq_f32_s32(vaddq_s32(vdupq_n_s32(x), inc)), vtx), dxl);
			float32x4_t v = vaddq_f32(vyy, dyl);
			float32x4_t uc = vminq_f32(vmaxq_f32(u, zero), umax), vcl = vminq_f32(vmaxq_f32(v, zero), vmax);
			int32x4_t ix = vcvtq_s32_f32(uc), iy = vcvtq_s32_f32(vcl);
			float32x4_t fx = vsubq_f32(uc, vcvtq_f32_s32(ix)), fy4 = vsubq_f32(vcl, vcvtq_f32_s32(iy));
			float32x4_t wx[4], wy[4], Q[4], cs[4], S[4];
			cr_weights(fx, wx);
			cr_weights(fy4, wy);
			transpose4(wy, Q);  /* pixel j's y weights in vector j */
			int32x4_t oa = vmlaq_s32(ix, iy, vwp), ow = vmlaq_s32(ix, iy, vw);
			const float *p0 = ap + vgetq_lane_s32(oa, 0), *p1 = ap + vgetq_lane_s32(oa, 1);
			const float *p2 = ap + vgetq_lane_s32(oa, 2), *p3 = ap + vgetq_lane_s32(oa, 3);
			cs[0] = cr_cols(p0, wp, Q[0]);
			cs[1] = cr_cols(p1, wp, Q[1]);
			cs[2] = cr_cols(p2, wp, Q[2]);
			cs[3] = cr_cols(p3, wp, Q[3]);
			transpose4(cs, S);  /* column i of the 4 pixels in vector i: the x weights apply as they are */
			float32x4_t va = vfmaq_f32(vfmaq_f32(vfmaq_f32(vfmaq_f32(vc, S[0], wx[0]), S[1], wx[1]), S[2], wx[2]), S[3], wx[3]);
			vst1q_f32(t->a + y * w + x, va);
			/* the weight: bilinear at the same clamped coordinate, 0 outside the estimate */
			const float *q0 = wt + vgetq_lane_s32(ow, 0), *q1 = wt + vgetq_lane_s32(ow, 1);
			const float *q2 = wt + vgetq_lane_s32(ow, 2), *q3 = wt + vgetq_lane_s32(ow, 3);
			float32x4x2_t top = vuzpq_f32(vcombine_f32(vld1_f32(q0), vld1_f32(q1)), vcombine_f32(vld1_f32(q2), vld1_f32(q3)));
			float32x4x2_t bot = vuzpq_f32(vcombine_f32(vld1_f32(q0 + w), vld1_f32(q1 + w)),
			                              vcombine_f32(vld1_f32(q2 + w), vld1_f32(q3 + w)));
			float32x4_t ofx = vsubq_f32(one, fx), ofy = vsubq_f32(one, fy4);
			float32x4_t l0 = vfmaq_f32(vmulq_f32(top.val[0], ofx), top.val[1], fx);
			float32x4_t l1 = vfmaq_f32(vmulq_f32(bot.val[0], ofx), bot.val[1], fx);
			uint32x4_t in = vandq_u32(vandq_u32(vcgeq_f32(u, zero), vcleq_f32(u, uin)), vandq_u32(vcgeq_f32(v, zero), vcleq_f32(v, vin)));
			vst1q_f32(t->wtw + y * w + x, vbslq_f32(in, vfmaq_f32(vmulq_f32(l0, ofy), l1, fy4), zero));
		}
		x = w;
#endif
		for (; x < w; x++)
			warp_px(t, ((float)x + tx) + udx[x], yy + vdy[x], c, y * w + x);
	}
}

/* ---- the blend --------------------------------------------------------------------------------------- */

/* acc = (w a + f) / (w + 1) with the residual test, in place; wt = the new weight.  Inputs: a (warped
 * estimate + c), f, r = f - a, box (its 3x3 mean, if zbox), wtw (warped weight), gx, gy (gradient of a).
 * With zv, also var and z (-1 outside) for the fixed-pattern update. */
static void blend(struct tnr *t, int zv)
{
	const struct tnr_params *p = &t->p;
	const int n = t->n, zbox = p->zbox;
	const float eps2 = p->eps * p->eps, sig2 = t->sigma * t->sigma, kk = p->k / (p->k + 1);
	const float k2 = p->k2, idk = 1.0f / (p->k2 - p->k), capm1 = p->cap - 1;
	const float *restrict A = t->a, *restrict F = t->f, *restrict R = t->r, *restrict B = t->box, *restrict W = t->wtw;
	const float *restrict GX = t->gx, *restrict GY = t->gy;
	float *restrict acc = t->acc, *restrict wt = t->wt, *restrict var_o = t->var, *restrict z_o = t->z;
	int i = 0;
#ifdef TNR_NEON
	if (!zv) {
		const float32x4_t one = vdupq_n_f32(1.0f), zero = vdupq_n_f32(0.0f), vsig2 = vdupq_n_f32(sig2), veps2 = vdupq_n_f32(eps2);
		const float32x4_t ninth = vdupq_n_f32(1.0f / 9.0f), vkk = vdupq_n_f32(kk), vk2 = vdupq_n_f32(k2), vidk = vdupq_n_f32(idk);
		const float32x4_t vcap = vdupq_n_f32(capm1);
		for (; i + 4 <= n; i += 4) {
			float32x4_t w = vld1q_f32(W + i), gx = vld1q_f32(GX + i), gy = vld1q_f32(GY + i);
			float32x4_t eg = vmulq_f32(veps2, vfmaq_f32(vmulq_f32(gx, gx), gy, gy));
			float32x4_t var = vfmaq_f32(eg, vsig2, vaddq_f32(one, vdivq_f32(one, vmaxq_f32(w, one))));
			float32x4_t z = vdivq_f32(vabsq_f32(vld1q_f32(R + i)), vsqrtq_f32(var));
			if (zbox) {
				float32x4_t zb = vdivq_f32(vabsq_f32(vld1q_f32(B + i)), vsqrtq_f32(vfmaq_f32(eg, var, ninth)));
				z = vmaxq_f32(z, vmulq_f32(zb, vkk));
			}
			float32x4_t g = vminq_f32(vmaxq_f32(vmulq_f32(vsubq_f32(vk2, z), vidk), zero), one);
			float32x4_t wp = vmulq_f32(vminq_f32(w, vcap), g);
			float32x4_t num = vfmaq_f32(vld1q_f32(F + i), wp, vld1q_f32(A + i));
			vst1q_f32(acc + i, vdivq_f32(num, vaddq_f32(wp, one)));
			vst1q_f32(wt + i, vaddq_f32(wp, one));
		}
	}
#endif
	for (; i < n; i++) {
		float w = W[i];
		float var = sig2 * (1 + 1 / (w > 1 ? w : 1)) + eps2 * (GX[i] * GX[i] + GY[i] * GY[i]);
		float z = fabsf(R[i]) / sqrtf(var);
		if (zbox) {
			float zb = fabsf(B[i]) / sqrtf(var / 9 + eps2 * (GX[i] * GX[i] + GY[i] * GY[i])) * kk;
			if (zb > z)
				z = zb;
		}
		float g = clampf((k2 - z) * idk, 0.0f, 1.0f);
		float wprev = (w < capm1 ? w : capm1) * g;
		acc[i] = (wprev * A[i] + F[i]) / (wprev + 1);
		wt[i] = wprev + 1;
		if (zv) {
			var_o[i] = var;
			z_o[i] = w > 0 ? z : -1.0f;
		}
	}
}

/* ---- per-frame column / row offsets (params.lines) ---------------------------------------------------- */

static inline float minmod(float u, float v) { return u * v > 0 ? (u > 0 ? (u < v ? u : v) : (u > v ? u : v)) : 0.0f; }

/* the sensor's column, then row, offsets of this frame: the clipped mean residual f - a of settled pixels
 * (wtw >= 2: inside), shrunk to 0 when few (+8); subtracted from f.  lines >= 2: only flat pixels
 * (|grad|^2 below its median) whose residual fits (z < k, also on the 3x3 mean), as a moving object leaves a
 * coherent residual the means would read as stripes; lines >= 3: the two halves of each line must agree
 * (minmod), as a stripe runs the whole line and an object does not.  Uses r, box, z (as the mask), sel. */
static void lines(struct tnr *t)
{
	const struct tnr_params *p = &t->p;
	const int w = t->w, h = t->h, n = t->n, h2 = h / 2, w2 = w / 2, halves = p->lines >= 3;
	const float s2 = 2.5f * t->sigma;
	float *restrict R = t->r, *restrict ok = t->z;
	for (int i = 0; i < n; i++)
		R[i] = t->f[i] - t->a[i];
	if (p->lines >= 2) {
		box3(R, w, h, t->tmp, t->box);
		int m = 0;
		for (int y = 0; y < h; y += 2)
			for (int x = 0; x < w; x += 2) {
				int i = y * w + x;
				t->sel[m++] = t->gx[i] * t->gx[i] + t->gy[i] * t->gy[i];
			}
		const float gmed = median(t->sel, m, t->hist), eps2 = p->eps * p->eps, sig2 = t->sigma * t->sigma;
		const float kk = p->k / (p->k + 1), k = p->k;
		for (int i = 0; i < n; i++) {
			float g2 = t->gx[i] * t->gx[i] + t->gy[i] * t->gy[i], wt = t->wtw[i];
			float var0 = sig2 * (1 + 1 / (wt > 1 ? wt : 1)) + eps2 * g2;
			float z0 = fabsf(R[i]) / sqrtf(var0), zb0 = fabsf(t->box[i]) / sqrtf(var0 / 9 + eps2 * g2) * kk;
			ok[i] = (float)(wt >= 2 && z0 < k && zb0 < k && g2 < gmed);
		}
	} else {
		for (int i = 0; i < n; i++)
			ok[i] = (float)(t->wtw[i] >= 2);
	}
	float *col = t->col, *row = t->row;
	const int wm = w > h ? w : h;
	float *sa = t->lscr, *ca = sa + wm, *sb = ca + wm, *cb = sb + wm;  /* per-line sums and counts (two halves) */
	memset(col, 0, sizeof(float) * w);
	memset(row, 0, sizeof(float) * h);
	for (int pass = 0; pass < 2; pass++) {
		/* columns: sums over the top (sa, ca) and bottom (sb, cb) halves */
		memset(sa, 0, sizeof(float) * w);
		memset(ca, 0, sizeof(float) * w);
		memset(sb, 0, sizeof(float) * w);
		memset(cb, 0, sizeof(float) * w);
		for (int y = 0; y < h; y++) {
			float *s_ = (halves && y >= h2) ? sb : sa, *c_ = (halves && y >= h2) ? cb : ca;
			const float *r = R + y * w, *o = ok + y * w, ry = row[y];
			for (int x = 0; x < w; x++) {
				s_[x] += clampf(r[x] - col[x] - ry, -s2, s2) * o[x];
				c_[x] += o[x];
			}
		}
		for (int x = 0; x < w; x++)
			col[x] += halves ? minmod(sa[x] / (ca[x] + 8), sb[x] / (cb[x] + 8)) : sa[x] / (ca[x] + 8);
		/* rows: left and right halves */
		for (int y = 0; y < h; y++) {
			const float *r = R + y * w, *o = ok + y * w, ry = row[y];
			float s0 = 0, c0 = 0, s1 = 0, c1 = 0;
			for (int x = 0; x < w; x++) {
				float q = clampf(r[x] - col[x] - ry, -s2, s2) * o[x];
				if (halves && x >= w2) {
					s1 += q;
					c1 += o[x];
				} else {
					s0 += q;
					c0 += o[x];
				}
			}
			row[y] += halves ? minmod(s0 / (c0 + 8), s1 / (c1 + 8)) : s0 / (c0 + 8);
		}
	}
	double cm = 0, rm = 0;
	for (int x = 0; x < w; x++)
		cm += col[x];
	for (int y = 0; y < h; y++)
		rm += row[y];
	cm /= w;
	rm /= h;
	for (int y = 0; y < h; y++)
		for (int x = 0; x < w; x++)
			t->f[y * w + x] -= (col[x] - (float)cm) + (row[y] - (float)rm);
}

/* ---- the strip at the buffer's right edge (the screen's left; params.edge) ------------------------------- */

/* each of the last K columns' offset over a line through the 4 columns before it, on the column medians (the
 * strip is a column offset; the scene's gradient is mostly linear over K + 4 columns), averaged over frames
 * (EMA, edge_rate) and subtracted from f.  Not learnable from motion: the border only ever sees the strip. */
static void edge_level(struct tnr *t)
{
	const int w = t->w, h = t->h, K = t->p.edge;
	if (K < 1 || K > TNR_EDGE_MAX || K + 4 > w || h <= 8)
		return;
	float cm[TNR_EDGE_MAX + 4];
	for (int j = 0; j < K + 4; j++) {
		int x = w - K - 4 + j, m = 0;
		for (int y = 4; y < h - 4; y++)
			t->sel[m++] = t->f[y * w + x];
		cm[j] = median(t->sel, m, t->hist);
	}
	float mean = (cm[0] + cm[1] + cm[2] + cm[3]) / 4;
	float sl = (-1.5f * (cm[0] - mean) - 0.5f * (cm[1] - mean) + 0.5f * (cm[2] - mean) + 1.5f * (cm[3] - mean)) / 5.0f;
	for (int j = 0; j < K; j++) {
		float d = cm[4 + j] - (mean + sl * ((float)(4 + j) - 1.5f));
		t->edge_off[j] = t->edge_have ? t->edge_off[j] + t->p.edge_rate * (d - t->edge_off[j]) : d;
	}
	t->edge_have = 1;
	for (int y = 0; y < h; y++)
		for (int j = 0; j < K; j++)
			t->f[y * w + w - K + j] -= t->edge_off[j];
}

/* ---- one frame ----------------------------------------------------------------------------------- */

static void emit(const struct tnr *t, const float *img, uint16_t *out, float *outf)
{
	if (outf)
		memcpy(outf, img, sizeof(float) * t->n);
	if (out)
		for (int i = 0; i < t->n; i++) {
			float v = img[i];
			out[i] = (uint16_t)(v <= 0 ? 0 : (v >= 65535.0f ? 65535 : (int)(v + 0.5f)));
		}
}

static void restart(struct tnr *t, uint16_t *out, float *outf)
{
	memcpy(t->acc, t->f, sizeof(float) * t->n);
	for (int i = 0; i < t->n; i++)
		t->wt[i] = 1.0f;
	t->have = 1;
	emit(t, t->acc, out, outf);
}

void tnr_process(struct tnr *t, const uint16_t *in, uint16_t *out, float *outf)
{
	const struct tnr_params *p = &t->p;
	int w = t->w, h = t->h, n = t->n;
	PROF_START();
	if (p->fpn)
		for (int i = 0; i < n; i++)
			t->f[i] = (float)in[i] - t->fpn[i];
	else
		for (int i = 0; i < n; i++)
			t->f[i] = (float)in[i];
	if (p->edge)
		edge_level(t);
	if (!t->have) {
		restart(t, out, outf);
		return;
	}
	float tx, ty, c, inl;
	PROF(0);
	align(t, &tx, &ty, &c, &inl);
	PROF(1);
	if (inl < p->reset_inliers || sqrtf(tx * tx + ty * ty) > 20.0f || !isfinite(tx) || !isfinite(ty) || !isfinite(c)) {
		restart(t, out, outf);
		return;
	}
	cubic_shift(t, tx, ty);
	PROF(2);
	if (p->local) {
		local_field(t, c);
		PROF(3);
		warp_local(t, tx, ty, c);
		PROF(4);
	} else {
		/* warped weight (0 where the estimate has no support) and the offset */
		for (int y = 0; y < h; y++)
			for (int x = 0; x < w; x++) {
				int i = y * w + x;
				float u = (float)x + tx, v = (float)y + ty;
				int inside = u >= 0 && u <= (float)(w - 1) && v >= 0 && v <= (float)(h - 1);
				t->wtw[i] = inside ? lin(t->wt, w, h, u, v) : 0.0f;
				t->a[i] += c;
			}
	}
	grad(t->a, w, h, t->gx, t->gy);
	if (p->lines)
		lines(t);
	{
		const float *restrict F = t->f, *restrict A = t->a;
		float *restrict R = t->r;
		for (int i = 0; i < n; i++)
			R[i] = F[i] - A[i];
	}
	if (p->zbox)
		box3(t->r, w, h, t->tmp, t->box);
	PROF(5);
	blend(t, p->fpn);  /* the new estimate goes straight into acc (the warp has read it) */
	PROF(6);
	/* noise: robust spread of the residual on settled, flat pixels */
	/* (on every other row and column: an estimate, smoothed over frames anyway) */
	int m = 0;
	for (int y = 0; y < h; y += 2)
		for (int x = 0; x < w; x += 2) {
			int i = y * w + x;
			t->sel[m++] = t->gx[i] * t->gx[i] + t->gy[i] * t->gy[i];
		}
	float gmed = median(t->sel, m, t->hist);
	double wsum = 0;
	m = 0;
	for (int y = 0; y < h; y += 2)
		for (int x = 0; x < w; x += 2) {
			int i = y * w + x;
			if (t->wtw[i] >= 2 && t->gx[i] * t->gx[i] + t->gy[i] * t->gy[i] < gmed) {
				t->sel[m++] = t->r[i];
				wsum += t->wtw[i] < p->cap ? t->wtw[i] : p->cap;
			}
		}
	float sigma_next = t->sigma;
	if (m > 125) {
		float mw = (float)(wsum / m);
		memcpy(t->sel2, t->sel, sizeof(float) * m);
		float rmed = median(t->sel2, m, t->hist);
		for (int i = 0; i < m; i++)
			t->sel2[i] = fabsf(t->sel[i] - rmed);
		float mad = median(t->sel2, m, t->hist);
		float s_now = 1.4826f * mad / sqrtf(1 + 1 / mw);
		sigma_next = clampf(0.9f * t->sigma + 0.1f * s_now, 1.0f, 50.0f);
	}
	if (p->fpn) {
		double s = 0;
		int cnt = 0;
		for (int i = 0; i < n; i++) {
			int ok = t->wtw[i] >= 2 && t->z[i] >= 0 && (p->fpn_clip || t->z[i] < p->k);
			float rr = 0;
			if (ok) {
				float lim = p->k * sqrtf(t->var[i]);
				rr = p->fpn_clip ? clampf(t->r[i], -lim, lim) : t->r[i];
				s += rr;
				cnt++;
			}
			t->box[i] = rr;
			t->sel[i] = (float)ok;
		}
		float mean = cnt ? (float)(s / cnt) : 0.0f;
		for (int i = 0; i < n; i++)
			if (t->sel[i] > 0)
				t->fpn[i] += p->fpn_rate * (t->box[i] - mean);
	}
	PROF(7);
	t->sigma = sigma_next;
	emit(t, t->acc, out, outf);
	PROF(8);
}
