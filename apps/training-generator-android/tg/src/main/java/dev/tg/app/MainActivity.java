package dev.tg.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.method.ScrollingMovementMethod;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Training Generator on Android — LEVI Boot Camp, on-device.
 *
 * Six tabs, front and center:
 *   Session  — the next session, run it through the battle rhythm
 *   Progress — completed/120, per-track mastery, streaks, gates
 *   Lessons  — browse the synthesized lessons (original, LEVI-authored)
 *   Photo    — photo training: generation SPECS (model-ready descriptions)
 *   Video    — video training: shot-list SPECS (scripts)
 *   Crucible — the path to session 120, the graduation crucible
 *
 * Photo/Video are specs only — model-ready descriptions and scripts, never
 * rendered media. The UI labels that boundary on every card.
 *
 * All engine work (core/levi/academy) runs in Python via Chaquopy; this
 * activity is the native shell around it. Local-only: no network
 * permission is declared, so TEACH synthesizes from local knowledge and
 * says so in the journal.
 */
public class MainActivity extends Activity {

    private com.chaquo.python.PyObject bridge;
    private File dataDir;

    private TextView statusView;
    private LinearLayout body;
    private int bg = Color.parseColor("#050508");
    private int panel = Color.parseColor("#0d0d14");
    private int fg = Color.parseColor("#e8e8f0");
    private int dim = Color.parseColor("#8a8a9a");
    private int accent = Color.parseColor("#7c5cff");

    private float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }

    // ------------------------------------------------------------------
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        bridge = Python.getInstance().getModule("academy_bridge");
        dataDir = new File(getFilesDir(), "tg-academy");

        buildUi();

        bg(() -> {
            bridge.callAttr("set_data_dir", dataDir.getAbsolutePath());
            runOnUiThread(() -> showSession());
        });
    }

    // ------------------------------------------------------------------
    // UI construction
    // ------------------------------------------------------------------
    private void buildUi() {
        LinearLayout root = vbox();
        root.setBackgroundColor(bg);

        LinearLayout top = hbox();
        TextView brand = label("TRAINING GENERATOR");
        brand.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        brand.setTextColor(accent);
        brand.setOnClickListener(v -> showAbout());
        top.addView(brand);
        TextView sub = label("levi boot camp · on-device");
        sub.setTextSize(11);
        sub.setTextColor(dim);
        top.addView(sub);
        root.addView(top);

        LinearLayout tabs = hbox();
        String[] names = {"Session", "Progress", "Lessons", "Photo", "Video", "Crucible"};
        for (String n : names) {
            Button b = button(n);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            int m = (int) dp(2);
            lp.setMargins(m, m, m, m);
            b.setLayoutParams(lp);
            final String tab = n;
            b.setOnClickListener(v -> {
                if (tab.equals("Session")) showSession();
                else if (tab.equals("Progress")) showProgress();
                else if (tab.equals("Lessons")) showLessons();
                else if (tab.equals("Photo")) showPhoto();
                else if (tab.equals("Video")) showVideo();
                else showCrucible();
            });
            tabs.addView(b);
        }
        root.addView(tabs);

        ScrollView sv = new ScrollView(this);
        body = vbox();
        sv.addView(body);
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        sv.setLayoutParams(blp);
        root.addView(sv);

        statusView = label("training generator · ready");
        statusView.setTextSize(11);
        statusView.setTextColor(dim);
        root.addView(statusView);

        setContentView(root);
    }

    private LinearLayout vbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        return l;
    }

    private LinearLayout hbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        return l;
    }

    private TextView label(String t) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextColor(fg);
        int p = (int) dp(6);
        v.setPadding(p, p, p, p);
        return v;
    }

    private TextView card() {
        TextView v = label("");
        v.setBackgroundColor(panel);
        v.setMovementMethod(new ScrollingMovementMethod());
        return v;
    }

    private Button button(String t) {
        Button b = new Button(this);
        b.setText(t);
        b.setTextSize(12);
        b.setAllCaps(false);
        int p = (int) dp(2);
        b.setPadding(p, p, p, p);
        return b;
    }

    private void bg(Runnable r) {
        new Thread(() -> {
            try {
                r.run();
            } catch (Exception e) {
                String msg = e.getMessage();
                runOnUiThread(() -> setStatus("error: " + msg));
            }
        }).start();
    }

    private void setStatus(String s) {
        statusView.setText(s);
    }

    // ------------------------------------------------------------------
    // Shared corpus tools (photo + video training pairs)
    // ------------------------------------------------------------------
    private TextView corpusLine;

    private void showCorpusTools() {
        TextView head = label("TRAINING CORPUS");
        head.setTextColor(accent);
        body.addView(head);
        corpusLine = label("counting pairs…");
        corpusLine.setTextSize(11);
        corpusLine.setTextColor(dim);
        body.addView(corpusLine);
        Button export = button("Export corpus (.jsonl)");
        export.setOnClickListener(v -> {
            setStatus("exporting…");
            bg(() -> {
                try {
                    JSONObject r = new JSONObject(
                            bridge.callAttr("corpus_export").toString());
                    runOnUiThread(() -> {
                        if (r.optBoolean("ok", false)) {
                            setStatus("exported " + r.optInt("pairs")
                                    + " pairs → " + r.optString("file"));
                        } else {
                            setStatus("export error: " + r.optString("error"));
                        }
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> setStatus("export error: " + e.getMessage()));
                }
            });
        });
        body.addView(export);
        refreshCorpusLine();
    }

    private void refreshCorpusLine() {
        if (corpusLine == null) return;
        bg(() -> {
            try {
                JSONObject r = new JSONObject(
                        bridge.callAttr("corpus_stats").toString());
                JSONObject c = r.optJSONObject("corpus");
                int ph = c != null ? c.optInt("photo", 0) : 0;
                int vi = c != null ? c.optInt("video", 0) : 0;
                runOnUiThread(() -> corpusLine.setText(
                        ph + " photo pairs · " + vi + " video pairs — "
                                + "paired prompt↔response examples, synthetic original"));
            } catch (Exception e) {
                runOnUiThread(() -> corpusLine.setText("corpus stats unavailable"));
            }
        });
    }

    private void showAbout() {
        String about = "Training Generator is LEVI Boot Camp on your phone — "
                + "a limb of LEVI, one organism.\n\n"
                + "120 sessions / 30 days. Battle rhythm: BRIEF → TEACH → "
                + "REVIEW → DRILL → TEST → DEBRIEF.\n\n"
                + "The bar: 80% on the lesson, 70% on the drill — or no "
                + "advance. A failed gate persists a remediation; the next "
                + "run executes it first. The standard does not move.\n\n"
                + "Session 120 is the graduation crucible: every prior "
                + "concept, weakest first, graded A/B/C.\n\n"
                + "Lessons are synthesized original — LEVI-authored, never "
                + "copied. Track A is defensive only: detection, analysis, "
                + "hardening. Never offensive instruction.\n\n"
                + "Everything runs on-device. No network, no account, no cloud.";
        new AlertDialog.Builder(this)
                .setTitle("Training Generator")
                .setMessage(about)
                .setPositiveButton("OK", null)
                .show();
    }

    // ------------------------------------------------------------------
    // Session tab
    // ------------------------------------------------------------------
    private void showSession() {
        body.removeAllViews();
        setStatus("loading session…");
        bg(() -> {
            try {
                JSONObject o = new JSONObject(bridge.callAttr("status").toString());
                runOnUiThread(() -> {
                    try {
                        if (!o.optBoolean("ok", false)) {
                            setStatus("status error: " + o.optString("error"));
                            return;
                        }
                        TextView head = card();
                        head.setText(o.getInt("completed") + " / " + o.getInt("total")
                                + " sessions complete"
                                + (o.getBoolean("graduated") ? " — GRADUATED" : ""));
                        head.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
                        head.setTextColor(accent);
                        body.addView(head);

                        if (o.getBoolean("graduated")) {
                            TextView g = card();
                            g.setText("All 120 sessions complete. The crucible is behind you — "
                                    + "post-graduation drills continue on the Crucible tab.");
                            body.addView(g);
                        } else {
                            JSONObject n = o.getJSONObject("next");
                            TextView nx = card();
                            StringBuilder sb = new StringBuilder();
                            sb.append("NEXT — session ").append(n.getInt("n")).append(" / 120\n");
                            sb.append(n.getString("session_id")).append(" · day ")
                                    .append(n.getInt("day")).append(" block ")
                                    .append(n.getInt("block")).append(" · track ")
                                    .append(n.getString("track")).append("\n\n");
                            sb.append(n.getString("title")).append("\n");
                            sb.append(n.getString("phase")).append("\n\nObjectives:\n");
                            JSONArray objs = n.getJSONArray("objectives");
                            for (int i = 0; i < objs.length(); i++) {
                                sb.append("• ").append(objs.getString(i)).append("\n");
                            }
                            if (!o.isNull("pending_remedial")) {
                                sb.append("\n⚠ pending remediation runs first — "
                                        + "a failed gate never advances.");
                            }
                            nx.setText(sb.toString());
                            body.addView(nx);

                            Button run = button("Run session (≈20 min)");
                            run.setOnClickListener(v -> runSession());
                            body.addView(run);
                        }
                        setStatus("session loaded");
                    } catch (Exception e) {
                        setStatus("parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("session error: " + e.getMessage()));
            }
        });
    }

    private void runSession() {
        setStatus("session running — battle rhythm in progress…");
        bg(() -> {
            try {
                JSONObject o = new JSONObject(
                        bridge.callAttr("run_session", 20.0).toString());
                runOnUiThread(() -> {
                    try {
                        if (!o.optBoolean("ok", false)) {
                            new AlertDialog.Builder(this)
                                    .setTitle("Session error")
                                    .setMessage(o.optString("error"))
                                    .setPositiveButton("OK", null)
                                    .show();
                            setStatus("session failed — see journal");
                            return;
                        }
                        StringBuilder sb = new StringBuilder();
                        sb.append("kind: ").append(o.optString("kind")).append("\n");
                        sb.append("session: ").append(o.optString("session_id")).append("\n");
                        sb.append("mastery: ").append(o.optDouble("mastery_score", -1)).append("\n");
                        sb.append("exercise: ").append(o.optDouble("exercise_score", -1)).append("\n");
                        sb.append("gate: ").append(o.optString("gate")).append("\n");
                        sb.append("passed: ").append(o.optBoolean("passed", false)).append("\n");
                        if (!o.isNull("remediation")) {
                            sb.append("\nremediation: ").append(o.optString("remediation"));
                        }
                        if (!o.isNull("journal_note")) {
                            String jn = o.optString("journal_note");
                            sb.append("\n\njournal: ").append(
                                    jn.length() > 800 ? jn.substring(0, 800) + "…" : jn);
                        }
                        new AlertDialog.Builder(this)
                                .setTitle("Session debrief")
                                .setMessage(sb.toString())
                                .setPositiveButton("OK", (d, w) -> showSession())
                                .show();
                        setStatus("session complete — debrief shown");
                    } catch (Exception e) {
                        setStatus("result parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("run error: " + e.getMessage()));
            }
        });
    }

    // ------------------------------------------------------------------
    // Progress tab
    // ------------------------------------------------------------------
    private void showProgress() {
        body.removeAllViews();
        setStatus("loading progress…");
        bg(() -> {
            try {
                JSONObject m = new JSONObject(bridge.callAttr("track_mastery").toString());
                JSONObject s = new JSONObject(bridge.callAttr("status").toString());
                runOnUiThread(() -> {
                    try {
                        JSONObject tracks = m.getJSONObject("tracks");
                        String[] order = {"A", "B", "C", "S"};
                        for (String t : order) {
                            if (!tracks.has(t)) continue;
                            JSONObject tr = tracks.getJSONObject(t);
                            TextView c = card();
                            StringBuilder sb = new StringBuilder();
                            sb.append("Track ").append(t).append(" — ")
                                    .append(tr.optString("name")).append("\n");
                            sb.append("completed: ").append(tr.optInt("completed")).append("\n");
                            double am = tr.optDouble("avg_mastery", -1);
                            double ae = tr.optDouble("avg_exercise", -1);
                            sb.append("avg mastery: ").append(am < 0 ? "—" : bar(am) + " " + am)
                                    .append(" (bar 0.80)").append("\n");
                            sb.append("avg exercise: ").append(ae < 0 ? "—" : bar(ae) + " " + ae)
                                    .append(" (bar 0.70)");
                            c.setText(sb.toString());
                            body.addView(c);
                        }
                        JSONObject streaks = s.optJSONObject("streaks");
                        if (streaks != null) {
                            TextView st = card();
                            StringBuilder sb = new StringBuilder("Streaks\n");
                            java.util.Iterator<String> it = streaks.keys();
                            while (it.hasNext()) {
                                String k = it.next();
                                sb.append(k).append(": ").append(streaks.optInt(k)).append("  ");
                            }
                            st.setText(sb.toString());
                            body.addView(st);
                        }
                        TextView note = label("Failed gates persist a remediation — "
                                + "the next run executes it before any new session. "
                                + "The standard does not move.");
                        note.setTextSize(11);
                        note.setTextColor(dim);
                        body.addView(note);
                        setStatus("progress loaded");
                    } catch (Exception e) {
                        setStatus("parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("progress error: " + e.getMessage()));
            }
        });
    }

    private String bar(double v) {
        int n = (int) Math.round(v * 10);
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < 10; i++) sb.append(i < n ? "█" : "░");
        return sb.append("]").toString();
    }

    // ------------------------------------------------------------------
    // Lessons tab
    // ------------------------------------------------------------------
    private void showLessons() {
        body.removeAllViews();
        setStatus("loading lessons…");
        bg(() -> {
            try {
                JSONObject o = new JSONObject(bridge.callAttr("lessons").toString());
                runOnUiThread(() -> {
                    try {
                        TextView note = label(o.optString("note", ""));
                        note.setTextSize(11);
                        note.setTextColor(dim);
                        body.addView(note);
                        JSONArray arr = o.getJSONArray("lessons");
                        List<String> ids = new ArrayList<>();
                        List<String> titles = new ArrayList<>();
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject l = arr.getJSONObject(i);
                            ids.add(l.getString("id"));
                            titles.add(l.getString("id") + " — " + l.getString("title"));
                        }
                        if (titles.isEmpty()) {
                            TextView empty = card();
                            empty.setText("No synthesized lessons on this device yet — "
                                    + "run sessions to generate them.");
                            body.addView(empty);
                        } else {
                            ListView lv = new ListView(this);
                            ArrayAdapter<String> ad = new ArrayAdapter<>(this,
                                    android.R.layout.simple_list_item_1, titles);
                            lv.setAdapter(ad);
                            lv.setOnItemClickListener((p, v, pos, id) -> showLesson(ids.get(pos)));
                            lv.setLayoutParams(new LinearLayout.LayoutParams(
                                    ViewGroup.LayoutParams.MATCH_PARENT, (int) dp(420)));
                            body.addView(lv);
                        }
                        setStatus(o.getInt("count") + " lessons");
                    } catch (Exception e) {
                        setStatus("parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("lessons error: " + e.getMessage()));
            }
        });
    }

    private void showLesson(String sid) {
        setStatus("opening " + sid + "…");
        bg(() -> {
            try {
                JSONObject o = new JSONObject(
                        bridge.callAttr("lesson_detail", sid).toString());
                runOnUiThread(() -> {
                    try {
                        if (!o.optBoolean("ok", false)) {
                            setStatus("lesson error: " + o.optString("error"));
                            return;
                        }
                        String md = o.getString("markdown");
                        if (o.optBoolean("truncated", false)) md += "\n\n[truncated for display]";
                        TextView tv = card();
                        tv.setText(md);
                        tv.setTypeface(Typeface.MONOSPACE);
                        tv.setTextSize(12);
                        new AlertDialog.Builder(this)
                                .setTitle(sid)
                                .setMessage(md.length() > 4000
                                        ? md.substring(0, 4000) + "\n\n[truncated for display]"
                                        : md)
                                .setPositiveButton("Close", null)
                                .show();
                        setStatus("lesson " + sid + " opened");
                    } catch (Exception e) {
                        setStatus("lesson parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("lesson error: " + e.getMessage()));
            }
        });
    }

    // ------------------------------------------------------------------
    // Photo tab — generation SPECS (model-ready descriptions, not renders)
    // ------------------------------------------------------------------
    private void showPhoto() {
        body.removeAllViews();
        setStatus("loading photo training…");
        TextView banner = card();
        banner.setText("TRAINING-FOR photo generation.\n"
                + "Each generation makes a PAIRED TRAINING EXAMPLE: prompt <-> photo spec, "
                + "with provenance and quality gates, saved to the on-device training corpus. "
                + "This produces training DATA for generative models — spec only, never rendered. "
                + "Training actual photo diffusion models is GPU-heavy and is NOT in this build.");
        body.addView(banner);

        final int[] idx = {0};
        final android.widget.EditText subj = new android.widget.EditText(this);
        subj.setHint("photo subject — or tap ↻ for a suggestion");
        subj.setTextColor(fg);
        subj.setHintTextColor(dim);
        body.addView(subj);

        LinearLayout row = hbox();
        Button sugg = button("↻ suggest");
        Button gen = button("Generate spec");
        row.addView(sugg);
        row.addView(gen);
        body.addView(row);

        bg(() -> {
            try {
                JSONObject o = new JSONObject(bridge.callAttr("photo_subjects").toString());
                JSONArray arr = o.getJSONArray("subjects");
                List<String> list = new ArrayList<>();
                for (int i = 0; i < arr.length(); i++) list.add(arr.getString(i));
                runOnUiThread(() -> {
                    if (!list.isEmpty()) subj.setText(list.get(0));
                    sugg.setOnClickListener(v -> {
                        idx[0] = (idx[0] + 1) % list.size();
                        subj.setText(list.get(idx[0]));
                    });
                    gen.setOnClickListener(v -> {
                        String s = subj.getText().toString().trim();
                        if (s.isEmpty()) { setStatus("enter a subject first"); return; }
                        setStatus("generating pair…");
                        bg(() -> {
                            try {
                                JSONObject p = new JSONObject(
                                        bridge.callAttr("photo_pair", s).toString());
                                runOnUiThread(() -> {
                                    if (!p.optBoolean("ok", false)) {
                                        setStatus("pair error: " + p.optString("error"));
                                        return;
                                    }
                                    if (p.optBoolean("duplicate", false)) {
                                        setStatus("pair already in corpus — skipped");
                                        return;
                                    }
                                    JSONObject pair = p.optJSONObject("pair");
                                    if (pair == null) {
                                        setStatus("pair error: empty result");
                                        return;
                                    }
                                    TextView c = card();
                                    StringBuilder sb = new StringBuilder();
                                    sb.append("TRAINING PAIR — photo\n\n");
                                    sb.append("PROMPT\n").append(pair.optString("prompt")).append("\n\n");
                                    JSONObject r = pair.optJSONObject("response");
                                    if (r != null) {
                                        sb.append("RESPONSE (spec)\n");
                                        sb.append("Subject: ").append(r.optString("subject")).append("\n");
                                        sb.append("Composition: ").append(r.optString("composition")).append("\n");
                                        sb.append("Lighting: ").append(r.optString("lighting")).append("\n");
                                        sb.append("Style: ").append(r.optString("style")).append("\n");
                                        sb.append("Mood: ").append(r.optString("mood")).append("\n");
                                    }
                                    sb.append("\nProvenance: ").append(
                                            pair.optJSONObject("provenance") != null
                                                    ? pair.optJSONObject("provenance").optString("generator")
                                                    : "?")
                                            .append(" · synthetic original · not ground truth\n");
                                    sb.append("Saved: ").append(pair.optString("saved"));
                                    c.setText(sb.toString());
                                    body.addView(c);
                                    refreshCorpusLine();
                                    setStatus("pair saved to corpus");
                                });
                            } catch (Exception e) {
                                runOnUiThread(() -> setStatus("pair error: " + e.getMessage()));
                            }
                        });
                    });
                    setStatus("photo training ready");
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("photo error: " + e.getMessage()));
            }
        });
        showCorpusTools();
    }

    // ------------------------------------------------------------------
    // Video tab — shot-list SPECS (scripts, not rendered footage)
    // ------------------------------------------------------------------
    private void showVideo() {
        body.removeAllViews();
        setStatus("loading video training…");
        TextView banner = card();
        banner.setText("TRAINING-FOR video generation.\n"
                + "Each generation makes a PAIRED TRAINING EXAMPLE: prompt <-> shot-list, "
                + "with provenance and quality gates, saved to the on-device training corpus. "
                + "This produces training DATA for generative models — shot-list only, never rendered. "
                + "Training actual video diffusion models is GPU-heavy and is NOT in this build.");
        body.addView(banner);

        final int[] idx = {0};
        final android.widget.EditText subj = new android.widget.EditText(this);
        subj.setHint("video subject — or tap ↻ for a suggestion");
        subj.setTextColor(fg);
        subj.setHintTextColor(dim);
        body.addView(subj);

        LinearLayout row = hbox();
        Button sugg = button("↻ suggest");
        Button gen = button("Generate shot-list");
        row.addView(sugg);
        row.addView(gen);
        body.addView(row);

        bg(() -> {
            try {
                JSONObject o = new JSONObject(bridge.callAttr("video_subjects").toString());
                JSONArray arr = o.getJSONArray("subjects");
                List<String> list = new ArrayList<>();
                for (int i = 0; i < arr.length(); i++) list.add(arr.getString(i));
                runOnUiThread(() -> {
                    if (!list.isEmpty()) subj.setText(list.get(0));
                    sugg.setOnClickListener(v -> {
                        idx[0] = (idx[0] + 1) % list.size();
                        subj.setText(list.get(idx[0]));
                    });
                    gen.setOnClickListener(v -> {
                        String s = subj.getText().toString().trim();
                        if (s.isEmpty()) { setStatus("enter a subject first"); return; }
                        setStatus("generating pair…");
                        bg(() -> {
                            try {
                                JSONObject sp = new JSONObject(
                                        bridge.callAttr("video_pair", s).toString());
                                runOnUiThread(() -> {
                                    if (!sp.optBoolean("ok", false)) {
                                        setStatus("pair error: " + sp.optString("error"));
                                        return;
                                    }
                                    if (sp.optBoolean("duplicate", false)) {
                                        setStatus("pair already in corpus — skipped");
                                        return;
                                    }
                                    JSONObject pair = sp.optJSONObject("pair");
                                    if (pair == null) {
                                        setStatus("pair error: empty result");
                                        return;
                                    }
                                    TextView c = card();
                                    StringBuilder sb = new StringBuilder();
                                    sb.append("TRAINING PAIR — video\n\n");
                                    sb.append("PROMPT\n").append(pair.optString("prompt")).append("\n\n");
                                    JSONObject r = pair.optJSONObject("response");
                                    if (r != null) {
                                        sb.append("RESPONSE (shot-list)\n");
                                        JSONArray shots = r.optJSONArray("shots");
                                        if (shots != null) {
                                            for (int i = 0; i < shots.length(); i++) {
                                                JSONObject sh = shots.optJSONObject(i);
                                                if (sh != null) sb.append("  [")
                                                        .append(sh.optString("t")).append("] ")
                                                        .append(sh.optString("shot")).append("\n");
                                            }
                                        }
                                        sb.append("Caption: ").append(r.optString("caption")).append("\n");
                                        sb.append("Audio: ").append(r.optString("audio")).append("\n");
                                    }
                                    sb.append("\nProvenance: ").append(
                                            pair.optJSONObject("provenance") != null
                                                    ? pair.optJSONObject("provenance").optString("generator")
                                                    : "?")
                                            .append(" · synthetic original · not ground truth\n");
                                    sb.append("Saved: ").append(pair.optString("saved"));
                                    c.setText(sb.toString());
                                    body.addView(c);
                                    refreshCorpusLine();
                                    setStatus("pair saved to corpus");
                                });
                            } catch (Exception e) {
                                runOnUiThread(() -> setStatus("pair error: " + e.getMessage()));
                            }
                        });
                    });
                    setStatus("video training ready");
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("video error: " + e.getMessage()));
            }
        });

        // Video-ingest: refined analyses feed the training corpus as text
        // entries labeled heuristics — never ground truth.
        TextView ingestHead = label("VIDEO → TRAINING PIPELINE");
        ingestHead.setTextColor(accent);
        body.addView(ingestHead);
        TextView ingestNote = label("Paste a refined video analysis. It is stored as a "
                + "text corpus entry labeled HEURISTICS — it never trains as ground truth.");
        ingestNote.setTextSize(11);
        ingestNote.setTextColor(dim);
        body.addView(ingestNote);
        final android.widget.EditText analysis = new android.widget.EditText(this);
        analysis.setHint("refined video analysis text…");
        analysis.setTextColor(fg);
        analysis.setHintTextColor(dim);
        analysis.setMinLines(3);
        body.addView(analysis);
        Button ingest = button("Ingest as training entry");
        ingest.setOnClickListener(v -> {
            String t = analysis.getText().toString().trim();
            if (t.isEmpty()) { setStatus("paste an analysis first"); return; }
            setStatus("ingesting…");
            bg(() -> {
                try {
                    JSONObject r = new JSONObject(
                            bridge.callAttr("video_ingest", t, "android-ui").toString());
                    runOnUiThread(() -> {
                        if (r.optBoolean("ok", false)) {
                            analysis.setText("");
                            setStatus("stored " + r.optString("stored")
                                    + " — " + r.optString("label"));
                        } else {
                            setStatus("ingest error: " + r.optString("error"));
                        }
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> setStatus("ingest error: " + e.getMessage()));
                }
            });
        });
        body.addView(ingest);
        showCorpusTools();
    }

    // ------------------------------------------------------------------
    // Crucible tab
    // ------------------------------------------------------------------
    private void showCrucible() {
        body.removeAllViews();
        setStatus("loading crucible path…");
        bg(() -> {
            try {
                JSONObject o = new JSONObject(bridge.callAttr("crucible").toString());
                runOnUiThread(() -> {
                    try {
                        TextView c = card();
                        StringBuilder sb = new StringBuilder();
                        sb.append("THE CRUCIBLE — session 120\n\n");
                        if (o.getBoolean("graduated")) {
                            sb.append("Graduated. The crucible is behind you.\n");
                        } else {
                            sb.append(o.getInt("remaining")).append(" sessions to go.\n\n");
                        }
                        sb.append(o.getString("crucible")).append("\n\n");
                        if (!o.isNull("weakest_track")) {
                            JSONObject w = o.getJSONObject("weakest_track");
                            sb.append("Weakest track: ").append(w.optString("id"))
                                    .append(" — ").append(w.optString("name"))
                                    .append("\n(post-graduation drill focus)");
                        }
                        c.setText(sb.toString());
                        c.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
                        c.setTextColor(accent);
                        body.addView(c);

                        TextView g = card();
                        g.setText(o.getString("guarantee"));
                        g.setTextColor(dim);
                        body.addView(g);
                        setStatus("crucible path loaded");
                    } catch (Exception e) {
                        setStatus("parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("crucible error: " + e.getMessage()));
            }
        });
    }
}
