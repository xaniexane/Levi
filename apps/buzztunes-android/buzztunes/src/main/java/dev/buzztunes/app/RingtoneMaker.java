package dev.buzztunes.app;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaMetadataRetriever;
import android.media.MediaMuxer;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.provider.MediaStore;
import android.provider.Settings;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.schabi.newpipe.extractor.NewPipe;
import org.schabi.newpipe.extractor.StreamingService;
import org.schabi.newpipe.extractor.downloader.Downloader;
import org.schabi.newpipe.extractor.downloader.Request;
import org.schabi.newpipe.extractor.downloader.Response;
import org.schabi.newpipe.extractor.exceptions.ExtractionException;
import org.schabi.newpipe.extractor.stream.AudioStream;
import org.schabi.newpipe.extractor.stream.StreamExtractor;

/**
 * YouTube-to-ringtone engine (phone side).
 *
 * <p>Chauncey's flagship spec (2026-09-29): "create ringtone from videos
 * being watched on YouTube as an option". The RULES live in the Python
 * module {@code levi.buzztunes.ringtone} — the single source of truth,
 * called here through Chaquopy so the law is declared once. This class
 * only does the phone work the Python side cannot: stream extraction,
 * download, trim, MediaStore export.
 *
 * <p>Laws (mirrored from ringtone.py):
 * L1 write boundary — files land only in the app cache dir or the
 *    MediaStore Ringtones collection. {@link #guardWrite} enforces.
 * L2 trim bounds — validated in Python ({@code validate_trim}) before
 *    any trim runs; this class refuses to trim without a valid plan.
 * L3 network consent — every method that touches the network is only
 *    ever called from the UI AFTER the user taps "Get audio".
 * L4 URL gate — {@code parse_video_id} runs in Python first.
 * L5 no fakes — unknown duration or empty downloads raise, never
 *    produce a silent file.
 * L6 receipt — the UI asks Python for {@code export_receipt} JSON.
 */
public final class RingtoneMaker {

    /** MediaStore relative path for exported ringtones (Law L1). */
    public static final String RINGTONE_RELATIVE_PATH = "Ringtones";

    private RingtoneMaker() {}

    // ------------------------------------------------------------------
    // Law guards (single source of truth: Python ringtone.py via Chaquopy)
    // ------------------------------------------------------------------

    private static PyObject ringtoneModule() {
        return Python.getInstance().getModule("levi.buzztunes.ringtone");
    }

    /** Law L4: returns the 11-char video id or throws RingtoneError. */
    public static String parseVideoId(String url) {
        PyObject mod = ringtoneModule();
        try {
            return mod.callAttr("parse_video_id", url).toString();
        } catch (Exception e) {
            throw new IllegalArgumentException(plainError(e));
        }
    }

    /**
     * Law L2: returns {startMs, endMs} clamped into the legal range.
     * Throws IllegalArgumentException when the trim cannot be legal.
     */
    public static long[] validateTrim(long startMs, long endMs, long durationMs) {
        PyObject mod = ringtoneModule();
        try {
            PyObject pair = mod.callAttr("validate_trim",
                    (int) startMs, (int) endMs, (int) durationMs);
            // validate_trim returns a tuple -> PyObject list-like
            java.util.List<PyObject> items = pair.asList();
            return new long[]{
                    items.get(0).toLong(), items.get(1).toLong()};
        } catch (Exception e) {
            throw new IllegalArgumentException(plainError(e));
        }
    }

    /** Law L1: refuse any path outside the app cache dir. */
    public static void guardWrite(File file, File cacheDir) {
        String want = file.getAbsolutePath();
        String cache = cacheDir.getAbsolutePath();
        if (!(want.equals(cache) || want.startsWith(cache + File.separator))) {
            throw new SecurityException(
                    "refusing to write outside app cache (L1): " + want);
        }
    }

    /** Law L6: JSON receipt for one export. */
    public static String exportReceipt(String videoId, String title,
            long startMs, long endMs, String outputUri, long durationMs) {
        return exportReceipt(videoId, title, startMs, endMs, outputUri,
                durationMs, new double[]{0, 0, 0, 0, 0}, 0, 0, false);
    }

    /** Law L6 receipt, now carrying the sound stage (L7/L8). */
    public static String exportReceipt(String videoId, String title,
            long startMs, long endMs, String outputUri, long durationMs,
            double[] eqGainsDb, long fadeInMs, long fadeOutMs,
            boolean autoTrimmed) {
        PyObject mod = ringtoneModule();
        ArrayList<Double> gains = new ArrayList<>(eqGainsDb.length);
        for (double g : eqGainsDb) {
            gains.add(g);
        }
        PyObject receipt = mod.callAttr("export_receipt", videoId, title,
                (int) startMs, (int) endMs, outputUri, (int) durationMs,
                gains, (int) fadeInMs, (int) fadeOutMs, autoTrimmed);
        return mod.callAttr("receipt_json", receipt).toString();
    }

    /** Law L8: validate the 5 EQ band gains through Python. */
    public static double[] validateEq(double[] gainsDb) {
        try {
            ArrayList<Double> gains = new ArrayList<>(gainsDb.length);
            for (double g : gainsDb) {
                gains.add(g);
            }
            PyObject out = ringtoneModule()
                    .callAttr("validate_eq", gains);
            List<PyObject> items = out.asList();
            double[] ok = new double[items.size()];
            for (int i = 0; i < ok.length; i++) {
                ok[i] = items.get(i).toDouble();
            }
            return ok;
        } catch (Exception e) {
            throw new IllegalArgumentException(plainError(e), e);
        }
    }

    /** Law L8: validate fade in/out ms through Python. */
    public static long[] validateFade(long fadeInMs, long fadeOutMs,
            long lengthMs) {
        try {
            PyObject out = ringtoneModule().callAttr("validate_fade",
                    (int) fadeInMs, (int) fadeOutMs, (int) lengthMs);
            List<PyObject> pair = out.asList();
            return new long[]{pair.get(0).toLong(), pair.get(1).toLong()};
        } catch (Exception e) {
            throw new IllegalArgumentException(plainError(e), e);
        }
    }

    private static String plainError(Exception e) {
        String m = e.getMessage();
        if (m == null) return "ringtone rule refused the request";
        // Chaquopy wraps the Python message; keep the human part.
        int i = m.indexOf("RingtoneError:");
        if (i >= 0) m = m.substring(i + "RingtoneError:".length());
        return m.replace('\n', ' ').trim();
    }

    // ------------------------------------------------------------------
    // NewPipe stream extraction (Law L3: only after the user taps)
    // ------------------------------------------------------------------

    /** Minimal Downloader so NewPipe can fetch pages on Android. */
    private static final class AndroidDownloader extends Downloader {
        @Override
        public Response execute(Request request) throws java.io.IOException {
            HttpURLConnection conn =
                    (HttpURLConnection) new URL(request.url()).openConnection();
            conn.setRequestMethod(request.httpMethod());
            for (Map.Entry<String, List<String>> h
                    : request.headers().entrySet()) {
                for (String v : h.getValue()) {
                    conn.addRequestProperty(h.getKey(), v);
                }
            }
            if (request.dataToSend() != null) {
                conn.setDoOutput(true);
                byte[] body = request.dataToSend();
                conn.getOutputStream().write(body);
            }
            int code = conn.getResponseCode();
            String message = conn.getResponseMessage();
            Map<String, List<String>> headers = conn.getHeaderFields();
            InputStream in = code >= 400
                    ? conn.getErrorStream() : conn.getInputStream();
            StringBuilder sb = new StringBuilder();
            if (in != null) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) != -1) {
                    sb.append(new String(buf, 0, n, "UTF-8"));
                }
                in.close();
            }
            return new Response(code, message, headers, sb.toString(),
                    request.url());
        }
    }

    private static boolean newPipeReady = false;

    private static synchronized void ensureNewPipe() {
        if (!newPipeReady) {
            NewPipe.init(new AndroidDownloader());
            newPipeReady = true;
        }
    }

    /** Result of extraction: stream URL + metadata. */
    public static final class AudioSource {
        public final String streamUrl;
        public final String title;
        public final long durationMs;

        AudioSource(String streamUrl, String title, long durationMs) {
            this.streamUrl = streamUrl;
            this.title = title;
            this.durationMs = durationMs;
        }
    }

    /**
     * Law L3/L4/L5: fetch the best audio-only stream for a YouTube video.
     * Call only from a background thread after the user taps "Get audio".
     */
    public static AudioSource extractAudio(String videoId)
            throws ExtractionException, java.io.IOException {
        ensureNewPipe();
        StreamingService yt = NewPipe.getService(0); // YouTube
        String watchUrl = "https://www.youtube.com/watch?v=" + videoId;
        StreamExtractor ex = yt.getStreamExtractor(watchUrl);
        ex.fetchPage();
        String title = ex.getName();
        long durationS = ex.getLength();
        if (durationS <= 0) {
            throw new ExtractionException(
                    "audio length unknown — can't trim what we can't measure (L5)");
        }
        List<AudioStream> audios = ex.getAudioStreams();
        if (audios == null || audios.isEmpty()) {
            throw new ExtractionException(
                    "no audio streams found for this video (L5)");
        }
        AudioStream best = audios.get(0);
        for (AudioStream a : audios) {
            if (a.getAverageBitrate() > best.getAverageBitrate()) {
                best = a;
            }
        }
        return new AudioSource(best.getContent(), title, durationS * 1000L);
    }

    // ------------------------------------------------------------------
    // Download / probe / trim (Law L1, L2, L5)
    // ------------------------------------------------------------------

    /**
     * Download the audio stream into the app cache dir.
     * Law L1: the destination is always inside cacheDir.
     */
    public static File downloadToCache(Context ctx, String streamUrl,
            String videoId) throws java.io.IOException {
        File cache = ctx.getCacheDir();
        File dst = new File(cache, "ringtone-src-" + videoId + ".bin");
        guardWrite(dst, cache); // L1
        HttpURLConnection conn =
                (HttpURLConnection) new URL(streamUrl).openConnection();
        conn.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Linux; Android 10) BuzzTunes/1.0");
        conn.connect();
        long expected = conn.getContentLengthLong();
        try (InputStream in = conn.getInputStream();
             OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[32768];
            int n;
            long total = 0;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
                total += n;
            }
            out.flush();
            // Law L5: refuse empty or truncated downloads.
            if (total == 0) {
                dst.delete();
                throw new java.io.IOException(
                        "download came back empty — nothing to trim (L5)");
            }
            if (expected > 0 && total < expected) {
                dst.delete();
                throw new java.io.IOException(
                        "download truncated (" + total + " of " + expected
                        + " bytes) — refusing a partial ringtone (L5)");
            }
        } finally {
            conn.disconnect();
        }
        return dst;
    }

    /** Measure the audio length in ms. Law L5: unknown duration refuses. */
    public static long probeDurationMs(File src) throws java.io.IOException {
        MediaMetadataRetriever mmr = new MediaMetadataRetriever();
        try {
            mmr.setDataSource(src.getAbsolutePath());
            String d = mmr.extractMetadata(
                    MediaMetadataRetriever.METADATA_KEY_DURATION);
            if (d == null) {
                throw new java.io.IOException(
                        "could not measure audio length (L5)");
            }
            long ms = Long.parseLong(d);
            if (ms <= 0) {
                throw new java.io.IOException(
                        "audio length is zero — nothing to trim (L5)");
            }
            return ms;
        } finally {
            try { mmr.release(); } catch (Exception ignored) {}
        }
    }

    /**
     * Cut [startMs, endMs) from the audio track into a new .m4a file.
     * Law L2: bounds must come from {@link #validateTrim} first.
     * Law L1: dst must sit inside cacheDir.
     */
    public static File trimAudio(File src, long startMs, long endMs,
            File dst, File cacheDir) throws java.io.IOException {
        guardWrite(dst, cacheDir); // L1
        if (!(0 <= startMs && startMs < endMs)) {
            throw new IllegalArgumentException(
                    "trim bounds illegal — run validate_trim first (L2)");
        }
        MediaExtractor ex = new MediaExtractor();
        ex.setDataSource(src.getAbsolutePath());
        int track = -1;
        MediaFormat fmt = null;
        for (int i = 0; i < ex.getTrackCount(); i++) {
            MediaFormat f = ex.getTrackFormat(i);
            String mime = f.getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.startsWith("audio/")) {
                track = i;
                fmt = f;
                break;
            }
        }
        if (track < 0) {
            ex.release();
            throw new java.io.IOException("no audio track found (L5)");
        }
        ex.selectTrack(track);
        ex.seekTo(startMs * 1000L, MediaExtractor.SEEK_TO_CLOSEST_SYNC);
        MediaMuxer mux = new MediaMuxer(dst.getAbsolutePath(),
                MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
        int outTrack = mux.addTrack(fmt);
        mux.start();
        ByteBuffer buf = ByteBuffer.allocate(512 * 1024);
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        long endUs = endMs * 1000L;
        while (true) {
            int n = ex.readSampleData(buf, 0);
            if (n < 0) break;
            long t = ex.getSampleTime();
            if (t > endUs) break;
            info.offset = 0;
            info.size = n;
            info.presentationTimeUs = t;
            info.flags = ex.getSampleFlags();
            mux.writeSampleData(outTrack, buf, info);
            if (!ex.advance()) break;
        }
        try { mux.stop(); } catch (Exception ignored) {}
        mux.release();
        ex.release();
        if (!dst.exists() || dst.length() == 0) {
            dst.delete();
            throw new java.io.IOException(
                    "trim produced nothing — refusing an empty ringtone (L5)");
        }
        return dst;
    }

    // ------------------------------------------------------------------
    // MediaStore export + default ringtone (Law L1, L6)
    // ------------------------------------------------------------------

    /**
     * Copy the trimmed file into the MediaStore Ringtones collection.
     * Law L1: the only non-cache destination allowed.
     * Returns the content Uri of the new ringtone.
     */
    public static Uri insertRingtone(Context ctx, File trimmed, String title)
            throws java.io.IOException {
        ContentResolver cr = ctx.getContentResolver();
        ContentValues v = new ContentValues();
        v.put(MediaStore.Audio.Media.DISPLAY_NAME, trimmed.getName());
        v.put(MediaStore.Audio.Media.TITLE, title);
        v.put(MediaStore.Audio.Media.MIME_TYPE, "audio/mp4");
        v.put(MediaStore.Audio.Media.IS_RINGTONE, 1);
        v.put(MediaStore.Audio.Media.IS_NOTIFICATION, 0);
        v.put(MediaStore.Audio.Media.IS_ALARM, 0);
        if (Build.VERSION.SDK_INT >= 29) {
            v.put(MediaStore.Audio.Media.RELATIVE_PATH,
                    RINGTONE_RELATIVE_PATH);
            v.put(MediaStore.Audio.Media.IS_PENDING, 1);
        }
        Uri collection = MediaStore.Audio.Media.getContentUri(
                MediaStore.VOLUME_EXTERNAL_PRIMARY);
        Uri uri = cr.insert(collection, v);
        if (uri == null) {
            throw new java.io.IOException(
                    "MediaStore refused the ringtone insert");
        }
        try (InputStream in = new java.io.FileInputStream(trimmed);
             OutputStream out = cr.openOutputStream(uri)) {
            if (out == null) {
                throw new java.io.IOException(
                        "could not open MediaStore output");
            }
            byte[] buf = new byte[32768];
            int n;
            while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
            out.flush();
        }
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues done = new ContentValues();
            done.put(MediaStore.Audio.Media.IS_PENDING, 0);
            cr.update(uri, done, null, null);
        }
        return uri;
    }

    /** True when the app may set the default ringtone (needs user grant). */
    public static boolean canSetDefaultRingtone(Context ctx) {
        return Settings.System.canWrite(ctx);
    }

    /** Set the exported ringtone as the phone's default. User-confirmed. */
    public static void setDefaultRingtone(Context ctx, Uri ringtoneUri) {
        if (!canSetDefaultRingtone(ctx)) {
            throw new SecurityException(
                    "the phone hasn't granted 'modify system settings' yet — "
                    + "approve it in Settings first");
        }
        RingtoneManager.setActualDefaultRingtoneUri(ctx,
                RingtoneManager.TYPE_RINGTONE, ringtoneUri);
    }

    // ------------------------------------------------------------------
    // DJ auto-trim (Law L7): energy analysis + the DJ SI's segment pick.
    // ------------------------------------------------------------------

    /** Decoded PCM: stereo float, one buffer per channel. */
    public static final class Pcm {
        public final float[] left;
        public final float[] right;
        public final int sampleRate;

        Pcm(float[] left, float[] right, int sampleRate) {
            this.left = left;
            this.right = right;
            this.sampleRate = sampleRate;
        }

        public int frames() {
            return left.length;
        }
    }

    /**
     * Measure the track's energy envelope: RMS per window, mono mix.
     * Runs fully on the phone; feeds {@link #djAutoTrim}.
     */
    public static float[] analyzeEnergy(File src, int windowMs)
            throws Exception {
        Pcm pcm = decodeSegment(src, 0, Long.MAX_VALUE);
        int windowSamples = Math.max(1,
                (int) (pcm.sampleRate * (long) windowMs / 1000L));
        int nWin = (pcm.frames() + windowSamples - 1) / windowSamples;
        float[] energies = new float[nWin];
        for (int w = 0; w < nWin; w++) {
            int from = w * windowSamples;
            int to = Math.min(pcm.frames(), from + windowSamples);
            double sum = 0;
            for (int i = from; i < to; i++) {
                double m = (pcm.left[i] + pcm.right[i]) * 0.5;
                sum += m * m;
            }
            energies[w] = (float) Math.sqrt(sum / Math.max(1, to - from));
        }
        return energies;
    }

    /**
     * The DJ AI/SI auto-trim: the hottest contiguous run of the energy
     * envelope, picked through ``levi.buzztunes.dj.suggest_ringtone_segment``
     * (Law L7 — deterministic, trim-law-checked). Returns [startMs, endMs].
     * The caller shows it for preview/confirmation before export.
     */
    public static long[] djAutoTrim(String title, long durationMs,
            float[] energies) {
        ArrayList<Float> list = new ArrayList<>(energies.length);
        for (float e : energies) {
            list.add(e);
        }
        PyObject dj = Python.getInstance()
                .getModule("levi.buzztunes.dj");
        PyObject res = dj.callAttr("suggest_ringtone_segment",
                title == null ? "" : title, durationMs, list);
        List<PyObject> pair = res.asList();
        return new long[]{pair.get(0).toLong(), pair.get(1).toLong()};
    }

    // ------------------------------------------------------------------
    // Full render (Law L8): trim + 5-band EQ + fade in/out -> AAC/M4A.
    // Fixed order: EQ -> fade-in -> fade-out.
    // ------------------------------------------------------------------

    /**
     * Render the ringtone: decode the [startMs, endMs) segment, apply the
     * 5-band EQ and fades via {@link DspChain}, encode AAC-LC, mux to M4A.
     *
     * @param eqGainsDb 5 band gains in dB, clamped to [-15, +15] (Law L8)
     */
    public static File renderRingtone(File src, long startMs, long endMs,
            double[] eqGainsDb, long fadeInMs, long fadeOutMs,
            File dst) throws Exception {
        Pcm pcm = decodeSegment(src, startMs, endMs);
        DspChain dsp = new DspChain(pcm.sampleRate, eqGainsDb);
        if (!DspChain.isFlat(eqGainsDb)) {
            dsp.process(pcm.left, pcm.right);
        }
        DspChain.applyFadeIn(pcm.left, pcm.right, pcm.sampleRate, fadeInMs);
        DspChain.applyFadeOut(pcm.left, pcm.right, pcm.sampleRate, fadeOutMs);
        encodeAac(pcm, dst);
        return dst;
    }

    /** Decode [startMs, endMs) of the audio track to stereo float PCM. */
    static Pcm decodeSegment(File src, long startMs, long endMs)
            throws Exception {
        MediaExtractor ex = new MediaExtractor();
        try {
            ex.setDataSource(src.getAbsolutePath());
            int track = -1;
            MediaFormat fmt = null;
            for (int i = 0; i < ex.getTrackCount(); i++) {
                MediaFormat f = ex.getTrackFormat(i);
                String mime = f.getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("audio/")) {
                    track = i;
                    fmt = f;
                    break;
                }
            }
            if (track < 0) {
                throw new IllegalStateException(
                        "no audio track in " + src.getName());
            }
            ex.selectTrack(track);
            String mime = fmt.getString(MediaFormat.KEY_MIME);
            long startUs = startMs * 1000L;
            long endUs = endMs == Long.MAX_VALUE
                    ? Long.MAX_VALUE : endMs * 1000L;
            if (startUs > 0) {
                ex.seekTo(startUs, MediaExtractor.SEEK_TO_CLOSEST_SYNC);
            }

            MediaCodec dec = MediaCodec.createDecoderByType(mime);
            try {
                dec.configure(fmt, null, null, 0);
                dec.start();
                ArrayList<Float> l = new ArrayList<>();
                ArrayList<Float> r = new ArrayList<>();
                int sampleRate = 44100;
                int channels = 2;
                boolean sawFormat = false;
                boolean inputEos = false;
                boolean outputEos = false;
                MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
                long deadlineNs =
                        System.nanoTime() + 120_000_000_000L; // 2 min cap

                while (!outputEos) {
                    if (System.nanoTime() > deadlineNs) {
                        throw new IllegalStateException(
                                "decode timed out — file may be corrupt");
                    }
                    if (!inputEos) {
                        int inIdx = dec.dequeueInputBuffer(10_000);
                        if (inIdx >= 0) {
                            ByteBuffer inBuf = dec.getInputBuffer(inIdx);
                            int n = ex.readSampleData(inBuf, 0);
                            if (n < 0) {
                                dec.queueInputBuffer(inIdx, 0, 0, 0,
                                        MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                                inputEos = true;
                            } else {
                                long t = ex.getSampleTime();
                                if (t >= endUs) {
                                    dec.queueInputBuffer(inIdx, 0, 0, 0,
                                            MediaCodec
                                                    .BUFFER_FLAG_END_OF_STREAM);
                                    inputEos = true;
                                } else if (t < startUs) {
                                    dec.queueInputBuffer(inIdx, 0, 0, 0, 0);
                                } else {
                                    dec.queueInputBuffer(inIdx, 0, n, t, 0);
                                }
                                ex.advance();
                            }
                        }
                    }
                    int outIdx = dec.dequeueOutputBuffer(info, 10_000);
                    if (outIdx >= 0) {
                        if ((info.flags
                                & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                            outputEos = true;
                        }
                        if (info.size > 0 && !sawFormat) {
                            // format arrives via INFO_OUTPUT_FORMAT_CHANGED
                        }
                        if (info.size > 0) {
                            ByteBuffer outBuf =
                                    dec.getOutputBuffer(outIdx);
                            appendPcm(outBuf, info, l, r);
                        }
                        dec.releaseOutputBuffer(outIdx, false);
                    } else if (outIdx
                            == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                        MediaFormat of = dec.getOutputFormat();
                        sampleRate = of.getInteger(
                                MediaFormat.KEY_SAMPLE_RATE);
                        channels = of.getInteger(
                                MediaFormat.KEY_CHANNEL_COUNT);
                        sawFormat = true;
                    }
                }
                float[] left = toArray(l);
                float[] right = channels == 1 ? left.clone() : toArray(r);
                return new Pcm(left, right, sampleRate);
            } finally {
                dec.stop();
                dec.release();
            }
        } finally {
            ex.release();
        }
    }

    private static void appendPcm(ByteBuffer buf,
            MediaCodec.BufferInfo info, ArrayList<Float> l,
            ArrayList<Float> r) {
        buf.order(ByteOrder.nativeOrder());
        int pos = info.offset;
        int end = info.offset + info.size;
        // 16-bit signed PCM (what Android AAC decoders emit).
        while (pos + 4 <= end) {
            short sL = buf.getShort(pos);
            pos += 2;
            short sR = buf.getShort(pos);
            pos += 2;
            l.add(sL / 32768f);
            r.add(sR / 32768f);
        }
        // Odd trailing bytes (shouldn't happen) are dropped, not guessed.
    }

    private static float[] toArray(ArrayList<Float> list) {
        float[] a = new float[list.size()];
        for (int i = 0; i < a.length; i++) {
            a[i] = list.get(i);
        }
        return a;
    }

    /** Encode stereo float PCM to AAC-LC and mux into an M4A file. */
    static void encodeAac(Pcm pcm, File dst) throws Exception {
        MediaFormat fmt = MediaFormat.createAudioFormat(
                MediaFormat.MIMETYPE_AUDIO_AAC,
                pcm.sampleRate, 2);
        fmt.setInteger(MediaFormat.KEY_BIT_RATE, 128_000);
        fmt.setInteger(MediaFormat.KEY_AAC_PROFILE,
                MediaCodecInfo.CodecProfileLevel.AACObjectLC);
        fmt.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 65536);

        MediaCodec enc = MediaCodec.createEncoderByType(
                MediaFormat.MIMETYPE_AUDIO_AAC);
        MediaMuxer muxer = null;
        try {
            enc.configure(fmt, null, null,
                    MediaCodec.CONFIGURE_FLAG_ENCODE);
            enc.start();

            // float -> 16-bit interleaved
            int frames = pcm.frames();
            byte[] interleaved = new byte[frames * 4];
            ByteBuffer tmp = ByteBuffer.wrap(interleaved)
                    .order(ByteOrder.nativeOrder());
            for (int i = 0; i < frames; i++) {
                tmp.putShort((short) Math.max(-32768, Math.min(32767,
                        Math.round(pcm.left[i] * 32767f))));
                tmp.putShort((short) Math.max(-32768, Math.min(32767,
                        Math.round(pcm.right[i] * 32767f))));
            }

            boolean inputEos = false;
            boolean outputEos = false;
            int trackIdx = -1;
            int offset = 0;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            while (!outputEos) {
                if (!inputEos) {
                    int inIdx = enc.dequeueInputBuffer(10_000);
                    if (inIdx >= 0) {
                        ByteBuffer inBuf = enc.getInputBuffer(inIdx);
                        inBuf.clear();
                        int chunk = Math.min(inBuf.remaining(),
                                interleaved.length - offset);
                        inBuf.put(interleaved, offset, chunk);
                        offset += chunk;
                        int flags = offset >= interleaved.length
                                ? MediaCodec.BUFFER_FLAG_END_OF_STREAM : 0;
                        long pts = (long) ((offset / 4.0)
                                / pcm.sampleRate * 1_000_000L);
                        enc.queueInputBuffer(inIdx, 0, chunk, pts, flags);
                        if (flags != 0) {
                            inputEos = true;
                        }
                    }
                }
                int outIdx = enc.dequeueOutputBuffer(info, 10_000);
                if (outIdx >= 0) {
                    if ((info.flags
                            & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                        outputEos = true;
                    }
                    if (info.size > 0 && trackIdx >= 0) {
                        ByteBuffer outBuf = enc.getOutputBuffer(outIdx);
                        muxer.writeSampleData(trackIdx, outBuf, info);
                    }
                    enc.releaseOutputBuffer(outIdx, false);
                } else if (outIdx
                        == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    MediaFormat of = enc.getOutputFormat();
                    muxer = new MediaMuxer(dst.getAbsolutePath(),
                            MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
                    trackIdx = muxer.addTrack(of);
                    muxer.start();
                }
            }
        } finally {
            try {
                enc.stop();
            } catch (Exception ignored) {
            }
            enc.release();
            if (muxer != null) {
                try {
                    muxer.stop();
                } catch (Exception ignored) {
                }
                muxer.release();
            }
        }
    }
}
