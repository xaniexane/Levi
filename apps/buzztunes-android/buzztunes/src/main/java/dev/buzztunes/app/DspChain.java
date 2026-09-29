package dev.buzztunes.app;

/**
 * Pure-Java DSP for the ringtone sound stage: 5-band EQ + fade in/out.
 *
 * <p>Deliberately free of Android imports so the math is provable on a
 * plain JVM (see DspChainTest). The phone path (RingtoneMaker) decodes
 * to PCM float, runs this, and re-encodes.
 *
 * <p>Law L8: 5 fixed bands (60/230/910/3600/14000 Hz), gains clamped to
 * [-15, +15] dB, fixed processing order: EQ -> fade-in -> fade-out.
 * Filters are RBJ cookbook biquads: low-shelf on the 60 Hz band,
 * peaking (Q=1) on 230/910/3600 Hz, high-shelf on the 14 kHz band.
 * Fades are linear ramps — first fade-in sample is exactly 0, last
 * fade-out sample is exactly 0.
 */
public final class DspChain {

    /** Fixed EQ bands in Hz (Law L8 — mirrors ringtone.py EQ_BAND_HZ). */
    public static final double[] BAND_HZ = {60.0, 230.0, 910.0, 3600.0,
            14000.0};
    public static final int BANDS = 5;
    public static final double MIN_DB = -15.0;
    public static final double MAX_DB = 15.0;

    // coeffs[band][b0,b1,b2,a1,a2] normalized (a0 = 1)
    private final double[][] coeffs = new double[BANDS][5];
    // state[channel][band][x1,x2,y1,y2]
    private final double[][][] state = new double[2][BANDS][4];

    public DspChain(double sampleRate, double[] gainsDb) {
        if (gainsDb == null || gainsDb.length != BANDS) {
            throw new IllegalArgumentException(
                    "EQ needs exactly " + BANDS + " band gains (L8)");
        }
        if (sampleRate <= 0) {
            throw new IllegalArgumentException("bad sample rate");
        }
        for (int i = 0; i < BANDS; i++) {
            double g = Math.max(MIN_DB, Math.min(MAX_DB, gainsDb[i]));
            if (i == 0) {
                coeffs[i] = lowShelf(sampleRate, BAND_HZ[i], g);
            } else if (i == BANDS - 1) {
                coeffs[i] = highShelf(sampleRate, BAND_HZ[i], g);
            } else {
                coeffs[i] = peaking(sampleRate, BAND_HZ[i], 1.0, g);
            }
        }
    }

    /** Process stereo PCM in place. */
    public void process(float[] left, float[] right) {
        if (left.length != right.length) {
            throw new IllegalArgumentException(
                    "channel length mismatch");
        }
        runBand(left, 0);
        runBand(right, 1);
    }

    private void runBand(float[] x, int ch) {
        for (int b = 0; b < BANDS; b++) {
            double[] c = coeffs[b];
            double[] s = state[ch][b];
            double x1 = s[0], x2 = s[1], y1 = s[2], y2 = s[3];
            double b0 = c[0], b1 = c[1], b2 = c[2], a1 = c[3], a2 = c[4];
            for (int n = 0; n < x.length; n++) {
                double xn = x[n];
                double yn = b0 * xn + b1 * x1 + b2 * x2
                        - a1 * y1 - a2 * y2;
                x2 = x1;
                x1 = xn;
                y2 = y1;
                y1 = yn;
                x[n] = (float) yn;
            }
            s[0] = x1;
            s[1] = x2;
            s[2] = y1;
            s[3] = y2;
        }
    }

    /** True when every band is 0 dB (nothing to do). */
    public static boolean isFlat(double[] gainsDb) {
        for (double g : gainsDb) {
            if (g != 0.0) return false;
        }
        return true;
    }

    /** Linear fade-in: first sample becomes exactly 0 (Law L8). */
    public static void applyFadeIn(float[] left, float[] right,
            double sampleRate, long fadeMs) {
        int n = (int) Math.min(left.length,
                Math.round(sampleRate * fadeMs / 1000.0));
        if (n <= 1) return;
        for (int i = 0; i < n; i++) {
            float g = (float) i / (float) (n - 1);
            left[i] *= g;
            right[i] *= g;
        }
    }

    /** Linear fade-out: last sample becomes exactly 0 (Law L8). */
    public static void applyFadeOut(float[] left, float[] right,
            double sampleRate, long fadeMs) {
        int total = left.length;
        int n = (int) Math.min(total,
                Math.round(sampleRate * fadeMs / 1000.0));
        if (n <= 1) return;
        int start = total - n;
        for (int i = 0; i < n; i++) {
            float g = (float) (n - 1 - i) / (float) (n - 1);
            left[start + i] *= g;
            right[start + i] *= g;
        }
    }

    // ------------------------------------------------------------------
    // RBJ cookbook biquads (S = 1 for shelves)
    // ------------------------------------------------------------------

    private static double[] peaking(double fs, double f0, double q,
            double dbGain) {
        double a = Math.pow(10.0, dbGain / 40.0);
        double w0 = 2.0 * Math.PI * f0 / fs;
        double alpha = Math.sin(w0) / (2.0 * q);
        double cw = Math.cos(w0);
        return norm(
                1 + alpha * a, -2 * cw, 1 - alpha * a,
                1 + alpha / a, -2 * cw, 1 - alpha / a);
    }

    private static double[] lowShelf(double fs, double f0, double dbGain) {
        double a = Math.pow(10.0, dbGain / 40.0);
        double w0 = 2.0 * Math.PI * f0 / fs;
        double alpha = Math.sin(w0) / 2.0 * Math.sqrt(2.0);
        double cw = Math.cos(w0);
        double sq = 2 * Math.sqrt(a) * alpha;
        return norm(
                a * ((a + 1) - (a - 1) * cw + sq),
                2 * a * ((a - 1) - (a + 1) * cw),
                a * ((a + 1) - (a - 1) * cw - sq),
                (a + 1) + (a - 1) * cw + sq,
                -2 * ((a - 1) + (a + 1) * cw),
                (a + 1) + (a - 1) * cw - sq);
    }

    private static double[] highShelf(double fs, double f0, double dbGain) {
        double a = Math.pow(10.0, dbGain / 40.0);
        double w0 = 2.0 * Math.PI * f0 / fs;
        double alpha = Math.sin(w0) / 2.0 * Math.sqrt(2.0);
        double cw = Math.cos(w0);
        double sq = 2 * Math.sqrt(a) * alpha;
        return norm(
                a * ((a + 1) + (a - 1) * cw + sq),
                -2 * a * ((a - 1) + (a + 1) * cw),
                a * ((a + 1) + (a - 1) * cw - sq),
                (a + 1) - (a - 1) * cw + sq,
                2 * ((a - 1) - (a + 1) * cw),
                (a + 1) - (a - 1) * cw - sq);
    }

    private static double[] norm(double b0, double b1, double b2,
            double a0, double a1, double a2) {
        return new double[]{b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0};
    }
}
