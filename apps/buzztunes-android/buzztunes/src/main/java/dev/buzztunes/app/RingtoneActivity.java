package dev.buzztunes.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;

/**
 * YouTube-to-ringtone screen — the flagship flow.
 *
 * <ol>
 *   <li>User pastes a YouTube link, taps "Get audio" (Law L3: nothing
 *       touches the network before this tap).</li>
 *   <li>The app extracts the audio stream (NewPipe), downloads it to the
 *       app cache, measures it, and proposes a trim (whole track, capped
 *       at 45s — Law L2).</li>
 *   <li>User adjusts start/end seconds, previews, then "Save ringtone"
 *       trims and exports to the MediaStore Ringtones collection
 *       (Law L1) with a JSON receipt (Law L6).</li>
 *   <li>"Set as default ringtone" applies it phone-wide after the user
 *       grants the system-settings permission.</li>
 * </ol>
 *
 * Every rule check runs through {@code levi.buzztunes.ringtone} via
 * Chaquopy (see RingtoneMaker) — failures show as plain-speech errors,
 * never silent no-ops (Law L5).
 */
public class RingtoneActivity extends Activity {

    private TextView statusView;
    private EditText urlInput;
    private EditText startInput;
    private EditText endInput;
    private EditText fadeInInput;
    private EditText fadeOutInput;
    private TextView trackInfo;
    private Button getAudioBtn;
    private Button autoTrimBtn;
    private Button previewBtn;
    private Button saveBtn;
    private Button defaultBtn;
    private Spinner eqPresetSpinner;
    private final SeekBar[] eqSeekBars = new SeekBar[5];
    private final TextView[] eqValueLabels = new TextView[5];
    private boolean autoTrimmed;

    /** 5 band centers in Hz (Law L8 — mirrors DspChain.BAND_HZ). */
    private static final int[] EQ_HZ = {60, 230, 910, 3600, 14000};
    private static final String[] EQ_PRESET_NAMES =
            {"flat", "bass_boost", "treble_boost", "vocal", "dance",
                    "custom"};
    private static final double[][] EQ_PRESET_GAINS = {
            {0, 0, 0, 0, 0},
            {6, 4, 0, 0, 0},
            {0, 0, 0, 4, 6},
            {-2, 0, 4, 3, -2},
            {5, 3, 0, 2, 4},
            {0, 0, 0, 0, 0}, // custom: whatever the sliders say
    };

    private String videoId;
    private String videoTitle;
    private long durationMs;
    private File cachedAudio;
    private Uri ringtoneUri;
    private MediaPlayer previewPlayer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }

        ScrollView scroll = new ScrollView(this);
        LinearLayout root = vbox();
        root.setPadding(dp(16), dp(16), dp(16), dp(32));
        scroll.addView(root);
        setContentView(scroll);

        TextView head = label("\ud83d\udd14 YouTube \u2192 ringtone");
        head.setTextSize(20);
        head.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        root.addView(head);
        root.addView(label(
                "Paste a YouTube link, trim the best part, save it as your "
                + "ringtone. Max 45 seconds."));

        root.addView(section("1 \u00b7 the video"));
        urlInput = input("youtube.com/watch?v=\u2026 or youtu.be/\u2026");
        root.addView(urlInput);
        getAudioBtn = button("Get audio");
        root.addView(getAudioBtn);
        trackInfo = label("");
        trackInfo.setTextSize(12);
        trackInfo.setTextColor(Color.parseColor("#8a8a9a"));
        root.addView(trackInfo);

        root.addView(section("2 \u00b7 trim (seconds)"));
        LinearLayout row = hbox();
        startInput = input("start");
        startInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        startInput.setText("0");
        endInput = input("end");
        endInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        endInput.setText("45");
        row.addView(startInput,
                new LinearLayout.LayoutParams(0,
                        ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        row.addView(endInput,
                new LinearLayout.LayoutParams(0,
                        ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(row);
        autoTrimBtn = button("\u2728 Auto-trim by DJ SI");
        autoTrimBtn.setEnabled(false);
        root.addView(autoTrimBtn);
        previewBtn = button("Preview trim");
        previewBtn.setEnabled(false);
        root.addView(previewBtn);
        root.addView(label("Preview plays the raw segment; the EQ and "
                + "fades below are baked in at export."));

        root.addView(section("3 \u00b7 sound stage (equalizer + fades)"));
        root.addView(label("EQ preset (\u00b115 dB per band):"));
        eqPresetSpinner = new Spinner(this);
        ArrayAdapter<String> eqAdapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, EQ_PRESET_NAMES);
        eqAdapter.setDropDownViewResource(
                android.R.layout.simple_spinner_dropdown_item);
        eqPresetSpinner.setAdapter(eqAdapter);
        root.addView(eqPresetSpinner);
        for (int b = 0; b < 5; b++) {
            final int band = b;
            LinearLayout brow = hbox();
            TextView blabel = label(EQ_HZ[b] >= 1000
                    ? (EQ_HZ[b] / 1000) + "k Hz" : EQ_HZ[b] + " Hz");
            blabel.setTextSize(11);
            brow.addView(blabel, new LinearLayout.LayoutParams(
                    dp(52), ViewGroup.LayoutParams.WRAP_CONTENT));
            SeekBar sb = new SeekBar(this);
            sb.setMax(30); // -15..+15 dB
            sb.setProgress(15);
            brow.addView(sb, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            TextView vlab = label("+0 dB");
            vlab.setTextSize(11);
            vlab.setTypeface(Typeface.MONOSPACE);
            brow.addView(vlab, new LinearLayout.LayoutParams(
                    dp(56), ViewGroup.LayoutParams.WRAP_CONTENT));
            eqSeekBars[b] = sb;
            eqValueLabels[b] = vlab;
            sb.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                @Override public void onProgressChanged(SeekBar s, int p,
                        boolean fromUser) {
                    int db = p - 15;
                    eqValueLabels[band].setText(
                            (db >= 0 ? "+" : "") + db + " dB");
                    if (fromUser) {
                        // Hand-touched sliders mean a custom curve.
                        eqPresetSpinner.setSelection(5, false);
                    }
                }
                @Override public void onStartTrackingTouch(SeekBar s) {}
                @Override public void onStopTrackingTouch(SeekBar s) {}
            });
            root.addView(brow);
        }
        root.addView(label("Fade in / fade out (milliseconds):"));
        LinearLayout frow = hbox();
        fadeInInput = input("fade in ms");
        fadeInInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        fadeInInput.setText("0");
        fadeOutInput = input("fade out ms");
        fadeOutInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        fadeOutInput.setText("2000");
        frow.addView(fadeInInput,
                new LinearLayout.LayoutParams(0,
                        ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        frow.addView(fadeOutInput,
                new LinearLayout.LayoutParams(0,
                        ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(frow);

        root.addView(section("4 \u00b7 save"));
        saveBtn = button("Save ringtone");
        saveBtn.setEnabled(false);
        root.addView(saveBtn);
        defaultBtn = button("Set as default ringtone");
        defaultBtn.setEnabled(false);
        root.addView(defaultBtn);

        statusView = label("");
        statusView.setTextSize(12);
        statusView.setTextColor(Color.parseColor("#8a8a9a"));
        root.addView(statusView);

        getAudioBtn.setOnClickListener(v -> onGetAudio());
        autoTrimBtn.setOnClickListener(v -> onAutoTrim());
        previewBtn.setOnClickListener(v -> onPreview());
        saveBtn.setOnClickListener(v -> onSave());
        defaultBtn.setOnClickListener(v -> onSetDefault());
        eqPresetSpinner.setOnItemSelectedListener(
                new AdapterView.OnItemSelectedListener() {
                    @Override public void onItemSelected(AdapterView<?> p,
                            View v, int pos, long id) {
                        if (pos < 5) applyEqPreset(pos);
                    }
                    @Override public void onNothingSelected(
                            AdapterView<?> p) {}
                });
    }

    // ------------------------------------------------------------------
    // Flow
    // ------------------------------------------------------------------

    private void onGetAudio() {
        final String url = urlInput.getText().toString().trim();
        if (url.isEmpty()) {
            setStatus("paste a YouTube link first");
            return;
        }
        setStatus("reading the video\u2026");
        getAudioBtn.setEnabled(false);
        bg(() -> {
            try {
                // Law L4: the Python gate parses or refuses.
                videoId = RingtoneMaker.parseVideoId(url);
                // Law L3: first network touch happens here, on the tap.
                RingtoneMaker.AudioSource src =
                        RingtoneMaker.extractAudio(videoId);
                videoTitle = src.title;
                File dl = RingtoneMaker.downloadToCache(
                        RingtoneActivity.this, src.streamUrl, videoId);
                long probed = RingtoneMaker.probeDurationMs(dl);
                durationMs = probed;
                cachedAudio = dl;
                final long defEnd =
                        Math.min(probed, 45_000L) / 1000L;
                runOnUiThread(() -> {
                    trackInfo.setText("\u266a " + videoTitle + "\n"
                            + fmtDur(probed) + " \u00b7 tap Preview, "
                            + "adjust the trim, then Save.");
                    startInput.setText("0");
                    endInput.setText(String.valueOf(defEnd));
                    autoTrimBtn.setEnabled(true);
                    previewBtn.setEnabled(true);
                    saveBtn.setEnabled(true);
                    setStatus("audio ready \u2014 pick your trim");
                    getAudioBtn.setEnabled(true);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setStatus("couldn't get the audio: "
                            + shortMsg(e));
                    getAudioBtn.setEnabled(true);
                });
            }
        });
    }

    /**
     * Law L7: the DJ SI reads the track's energy and picks the hottest
     * run. The pick fills the trim boxes; the user previews and confirms
     * before anything exports.
     */
    private void onAutoTrim() {
        if (cachedAudio == null) return;
        autoTrimBtn.setEnabled(false);
        setStatus("the DJ SI is listening to the track\u2026");
        bg(() -> {
            try {
                float[] energies =
                        RingtoneMaker.analyzeEnergy(cachedAudio, 500);
                long[] seg = RingtoneMaker.djAutoTrim(
                        videoTitle, durationMs, energies);
                autoTrimmed = true;
                runOnUiThread(() -> {
                    startInput.setText(String.valueOf(seg[0] / 1000));
                    endInput.setText(String.valueOf(seg[1] / 1000));
                    setStatus("the DJ SI picked " + seg[0] / 1000 + "s"
                            + "\u2013" + seg[1] / 1000 + "s \u2014 preview "
                            + "it, nudge it if you like, then save.");
                    autoTrimBtn.setEnabled(true);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    setStatus("auto-trim couldn't hear it: "
                            + shortMsg(e));
                    autoTrimBtn.setEnabled(true);
                });
            }
        });
    }

    private void onPreview() {
        if (cachedAudio == null) return;
        long[] trim = readTrim();
        if (trim == null) return;
        stopPreview();
        try {
            previewPlayer = new MediaPlayer();
            previewPlayer.setDataSource(cachedAudio.getAbsolutePath());
            previewPlayer.prepare();
            previewPlayer.seekTo((int) trim[0]);
            final long stopAt = trim[1];
            previewPlayer.setOnSeekCompleteListener(mp -> mp.start());
            // Stop at the trim end: poll on a light thread.
            new Thread(() -> {
                try {
                    while (previewPlayer != null
                            && previewPlayer.isPlaying()) {
                        if (previewPlayer.getCurrentPosition() >= stopAt) {
                            runOnUiThread(this::stopPreview);
                            break;
                        }
                        Thread.sleep(200);
                    }
                } catch (Exception ignored) {}
            }).start();
            previewPlayer.start();
            setStatus("previewing " + trim[0] / 1000 + "s\u2013"
                    + trim[1] / 1000 + "s\u2026");
        } catch (Exception e) {
            setStatus("preview failed: " + shortMsg(e));
        }
    }

    private void onSave() {
        if (cachedAudio == null) return;
        long[] trim = readTrim();
        if (trim == null) return;
        double[] gains = readEqGains();
        if (gains == null) return;
        long[] fades = readFades(trim[1] - trim[0]);
        if (fades == null) return;
        final long s = trim[0], e = trim[1];
        final long fi = fades[0], fo = fades[1];
        setStatus("rendering your ringtone\u2026");
        saveBtn.setEnabled(false);
        bg(() -> {
            try {
                // Law L2 (again, at the point of work): Python validates.
                long[] ok = RingtoneMaker.validateTrim(s, e, durationMs);
                File cache = getCacheDir();
                File dst = new File(cache,
                        "ringtone-" + videoId + "-" + ok[0]
                                + "-" + ok[1] + ".m4a");
                RingtoneMaker.guardWrite(dst, cache); // L1
                // Law L8: trim + EQ + fades, rendered on the phone.
                RingtoneMaker.renderRingtone(cachedAudio, ok[0], ok[1],
                        gains, fi, fo, dst);
                String fname = trimmedName();
                File named = new File(cache, fname);
                if (!dst.renameTo(named)) named = dst;
                final Uri uri = RingtoneMaker.insertRingtone(
                        RingtoneActivity.this, named, videoTitle);
                ringtoneUri = uri;
                // Law L6: receipt (now carries EQ, fades, auto-trim).
                final String receipt = RingtoneMaker.exportReceipt(
                        videoId, videoTitle, ok[0], ok[1],
                        uri.toString(), durationMs,
                        gains, fi, fo, autoTrimmed);
                android.util.Log.i("BuzzTunesRingtone", receipt);
                runOnUiThread(() -> {
                    setStatus("\u2705 ringtone saved \u2014 find it in "
                            + "Settings > Sound > Phone ringtone");
                    defaultBtn.setEnabled(true);
                    saveBtn.setEnabled(true);
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    setStatus("save failed: " + shortMsg(ex));
                    saveBtn.setEnabled(true);
                });
            }
        });
    }

    private void onSetDefault() {
        if (ringtoneUri == null) return;
        if (!RingtoneMaker.canSetDefaultRingtone(this)) {
            setStatus("the phone needs your OK first \u2014 opening "
                    + "Settings; enable 'Modify system settings' for "
                    + "Buzz Tunes, then come back and tap again.");
            startActivity(new Intent(
                    Settings.ACTION_MANAGE_WRITE_SETTINGS,
                    Uri.parse("package:" + getPackageName())));
            return;
        }
        try {
            RingtoneMaker.setDefaultRingtone(this, ringtoneUri);
            setStatus("\u2705 that's your ringtone now");
        } catch (Exception e) {
            setStatus("couldn't set it: " + shortMsg(e));
        }
    }

    /** Read + Python-validate the trim fields. Null = error already shown. */
    private long[] readTrim() {
        long s, e;
        try {
            s = Long.parseLong(startInput.getText().toString().trim())
                    * 1000L;
            e = Long.parseLong(endInput.getText().toString().trim())
                    * 1000L;
        } catch (NumberFormatException ex) {
            setStatus("trim needs whole seconds in both boxes");
            return null;
        }
        try {
            return RingtoneMaker.validateTrim(s, e, durationMs);
        } catch (IllegalArgumentException ex) {
            setStatus(ex.getMessage());
            return null;
        }
    }

    /** Apply an EQ preset to the five sliders (Law L8). */
    private void applyEqPreset(int pos) {
        double[] gains = EQ_PRESET_GAINS[pos];
        for (int b = 0; b < 5; b++) {
            eqSeekBars[b].setProgress((int) gains[b] + 15);
        }
    }

    /** Read the five EQ sliders, validated through Python (Law L8). */
    private double[] readEqGains() {
        double[] gains = new double[5];
        for (int b = 0; b < 5; b++) {
            gains[b] = eqSeekBars[b].getProgress() - 15;
        }
        try {
            return RingtoneMaker.validateEq(gains);
        } catch (IllegalArgumentException ex) {
            setStatus(ex.getMessage());
            return null;
        }
    }

    /** Read fade in/out ms, validated through Python (Law L8). */
    private long[] readFades(long lengthMs) {
        long fi, fo;
        try {
            String a = fadeInInput.getText().toString().trim();
            String b = fadeOutInput.getText().toString().trim();
            fi = a.isEmpty() ? 0 : Long.parseLong(a);
            fo = b.isEmpty() ? 0 : Long.parseLong(b);
        } catch (NumberFormatException ex) {
            setStatus("fades need whole milliseconds (or 0)");
            return null;
        }
        try {
            return RingtoneMaker.validateFade(fi, fo, lengthMs);
        } catch (IllegalArgumentException ex) {
            setStatus(ex.getMessage());
            return null;
        }
    }

    private String trimmedName() {
        String safe = videoTitle == null ? "buzz-tunes"
                : videoTitle.replaceAll("[^A-Za-z0-9 _.-]", "")
                        .replaceAll("\\s+", " ").trim();
        if (safe.isEmpty()) safe = "buzz-tunes";
        if (safe.length() > 60) safe = safe.substring(0, 60);
        return safe + " [" + videoId + "].m4a";
    }

    private void stopPreview() {
        if (previewPlayer != null) {
            try {
                if (previewPlayer.isPlaying()) previewPlayer.stop();
                previewPlayer.release();
            } catch (Exception ignored) {}
            previewPlayer = null;
        }
    }

    @Override
    protected void onDestroy() {
        stopPreview();
        super.onDestroy();
    }

    // ------------------------------------------------------------------
    // Small helpers (dark theme matches MainActivity)
    // ------------------------------------------------------------------

    private void bg(Runnable r) {
        new Thread(() -> {
            try {
                r.run();
            } catch (Exception e) {
                final String m = shortMsg(e);
                runOnUiThread(() -> setStatus("error: " + m));
            }
        }).start();
    }

    private void setStatus(String s) {
        statusView.setText(s);
    }

    private static String shortMsg(Exception e) {
        String m = e.getMessage();
        if (m == null) m = e.toString();
        m = m.replace('\n', ' ').trim();
        return m.length() > 220 ? m.substring(0, 220) + "\u2026" : m;
    }

    private static String fmtDur(long ms) {
        long s = ms / 1000;
        return (s / 60) + ":" + String.format("%02d", s % 60);
    }

    private int dp(float v) {
        return (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, v, getResources()
                        .getDisplayMetrics());
    }

    private LinearLayout vbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setBackgroundColor(Color.parseColor("#0b0b10"));
        return l;
    }

    private LinearLayout hbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        return l;
    }

    private TextView label(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(Color.parseColor("#e8e8f0"));
        t.setTextSize(14);
        t.setPadding(0, dp(6), 0, dp(6));
        return t;
    }

    private TextView section(String s) {
        TextView t = label(s);
        t.setTextSize(12);
        t.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        t.setTextColor(Color.parseColor("#9d7bff"));
        t.setPadding(0, dp(14), 0, dp(2));
        return t;
    }

    private Button button(String s) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextColor(Color.parseColor("#0b0b10"));
        b.setBackgroundColor(Color.parseColor("#9d7bff"));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(6), 0, dp(6));
        b.setLayoutParams(lp);
        return b;
    }

    private EditText input(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(Color.parseColor("#5a5a6a"));
        e.setTextColor(Color.parseColor("#e8e8f0"));
        e.setBackgroundColor(Color.parseColor("#17171f"));
        e.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(4), 0, dp(4));
        e.setLayoutParams(lp);
        return e;
    }
}
