package dev.buzztunes.app;

/**
 * Proof for DspChain (Law L8) — runs on a plain JVM, no Android needed.
 * Run: javac DspChain.java DspChainTest.java && java dev.buzztunes.app.DspChainTest
 */
public final class DspChainTest {

    static int checks = 0;

    static void check(boolean cond, String name) {
        checks++;
        if (!cond) {
            System.out.println("FAIL: " + name);
            System.exit(1);
        }
        System.out.println("ok: " + name);
    }

    static float[] sine(double freq, double sr, int n) {
        float[] x = new float[n];
        for (int i = 0; i < n; i++) {
            x[i] = (float) Math.sin(2 * Math.PI * freq * i / sr);
        }
        return x;
    }

    static double rms(float[] x, int skip) {
        double s = 0;
        for (int i = skip; i < x.length; i++) s += x[i] * x[i];
        return Math.sqrt(s / (x.length - skip));
    }

    public static void main(String[] a) {
        double sr = 44100.0;
        int n = (int) sr; // 1 second

        // 1. Flat EQ is transparent (steady state).
        {
            float[] l = sine(440, sr, n);
            float[] r = sine(440, sr, n);
            new DspChain(sr, new double[]{0, 0, 0, 0, 0}).process(l, r);
            double inRms = rms(sine(440, sr, n), 4096);
            double outRms = rms(l, 4096);
            check(Math.abs(inRms - outRms) / inRms < 1e-3,
                    "flat EQ transparent (rms drift < 0.1%)");
        }

        // 2. Bass boost lifts deep bass ~+6dB (2x amplitude). Note: a
        // low-shelf reaches full boost below its corner, so we probe
        // at 30Hz (the 60Hz corner itself gets +3dB by design).
        {
            float[] l = sine(30, sr, n);
            float[] r = sine(30, sr, n);
            new DspChain(sr, new double[]{6, 0, 0, 0, 0}).process(l, r);
            double ratio = rms(l, 4096) / rms(sine(30, sr, n), 4096);
            check(ratio > 1.8 && ratio < 2.2,
                    "bass +6dB doubles 30Hz (ratio=" + ratio + ")");
        }

        // 3. Bass boost leaves 14 kHz alone.
        {
            float[] l = sine(14000, sr, n);
            float[] r = sine(14000, sr, n);
            new DspChain(sr, new double[]{6, 0, 0, 0, 0}).process(l, r);
            double ratio = rms(l, 4096) / rms(sine(14000, sr, n), 4096);
            check(ratio > 0.9 && ratio < 1.1,
                    "bass boost ignores 14kHz (ratio=" + ratio + ")");
        }

        // 4. Treble boost lifts highs (probe above the 14kHz corner,
        // where the high-shelf reaches full boost).
        {
            float[] l = sine(18000, sr, n);
            float[] r = sine(18000, sr, n);
            new DspChain(sr, new double[]{0, 0, 0, 0, 6}).process(l, r);
            double ratio = rms(l, 4096) / rms(sine(18000, sr, n), 4096);
            check(ratio > 1.8 && ratio < 2.2,
                    "treble +6dB doubles 18kHz (ratio=" + ratio + ")");
        }

        // 5. Gain clamp: +99dB behaves like +15dB, not infinity.
        {
            float[] l = sine(60, sr, n);
            float[] r = sine(60, sr, n);
            new DspChain(sr, new double[]{99, 0, 0, 0, 0}).process(l, r);
            double ratio = rms(l, 4096) / rms(sine(60, sr, n), 4096);
            check(ratio < 6.5, "+99dB clamped to +15dB (ratio=" + ratio + ")");
        }

        // 6. Fade-in: first sample exactly 0, ramps up.
        {
            float[] l = new float[n];
            float[] r = new float[n];
            for (int i = 0; i < n; i++) { l[i] = 1.0f; r[i] = 1.0f; }
            DspChain.applyFadeIn(l, r, sr, 1000);
            check(l[0] == 0.0f && r[0] == 0.0f, "fade-in starts at 0");
            check(l[n - 1] == 1.0f, "fade-in ends at full level");
            boolean mono = true;
            for (int i = 1; i < n; i++) {
                if (l[i] < l[i - 1] - 1e-6) { mono = false; break; }
            }
            check(mono, "fade-in ramp is monotonic");
        }

        // 7. Fade-out: last sample exactly 0, ramps down.
        {
            float[] l = new float[n];
            float[] r = new float[n];
            for (int i = 0; i < n; i++) { l[i] = 1.0f; r[i] = 1.0f; }
            DspChain.applyFadeOut(l, r, sr, 1000);
            check(l[n - 1] == 0.0f && r[n - 1] == 0.0f,
                    "fade-out ends at 0");
            check(l[0] == 1.0f, "fade-out starts at full level");
        }

        // 8. Deterministic: same input -> same output.
        {
            float[] p = sine(440, sr, n);
            float[] q = sine(440, sr, n);
            double[] g = {3, -2, 4, 0, -5};
            new DspChain(sr, g).process(p, p.clone());
            DspChain c2 = new DspChain(sr, g);
            float[] q2 = q.clone();
            c2.process(q, q2);
            boolean same = true;
            for (int i = 0; i < n; i++) {
                if (p[i] != q[i]) { same = false; break; }
            }
            check(same, "DSP deterministic across instances");
        }

        // 9. isFlat.
        check(DspChain.isFlat(new double[]{0, 0, 0, 0, 0}), "isFlat true");
        check(!DspChain.isFlat(new double[]{0, 0, 1, 0, 0}),
                "isFlat false on +1dB");

        System.out.println("ALL " + checks + " DSP CHECKS PASSED");
    }
}
