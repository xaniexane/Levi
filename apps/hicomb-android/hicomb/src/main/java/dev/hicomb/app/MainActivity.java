package dev.hicomb.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.Editable;
import android.text.Spanned;
import android.text.TextWatcher;
import android.text.style.ForegroundColorSpan;
import android.text.style.BackgroundColorSpan;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.text.SpannableStringBuilder;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Hicomb on Android — the from-scratch code editor, on-device.
 *
 * The main screen carries the loop FRONT AND CENTER:
 *   Alpha builds -> Surgeon repairs -> Quetta-Pan improves
 * Quetta-Pan is a primary, always-visible panel (point at code, dry-run,
 * apply, iterate) — not a buried menu item.
 *
 * All engine work (hicomb / quetta_pan / surgeon / builder) runs in Python
 * via Chaquopy; this activity is the native shell around it. Local-only:
 * no network permission is declared.
 */
public class MainActivity extends Activity {

    private static final int DP = 1; // scaled at runtime

    // ---- python bridge ----
    private com.chaquo.python.PyObject bridge;

    // ---- state ----
    private File workspace;
    private String currentFile = null;
    private String themeName = "void";
    private boolean qpTargetProject = false;
    private final Deque<String> undoStack = new ArrayDeque<>();
    private final Deque<String> redoStack = new ArrayDeque<>();
    private boolean programmaticEdit = false;

    // ---- ui ----
    private TextView titleFileView;
    private TextView statusView;
    private TextView loopStatusView;
    private LinearLayout qpPanel;
    private Button qpTargetButton;
    private ListView qpResultsView;
    private ListView fileListView;
    private EditText editor;
    private final List<String> fileNames = new ArrayList<>();
    private ArrayAdapter<String> fileAdapter;
    private final List<String> qpRows = new ArrayList<>();
    private ArrayAdapter<String> qpAdapter;
    private final List<JSONObject> qpScanData = new ArrayList<>();
    private Map<String, String> syntaxColors = new HashMap<>();
    private int editorBg = Color.parseColor("#050508");
    private int editorFg = Color.parseColor("#e8e8f0");

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
        bridge = Python.getInstance().getModule("hicomb_bridge");

        workspace = new File(getFilesDir(), "hicomb-ws");
        bg(() -> {
            bridge.callAttr("set_workspace", workspace.getAbsolutePath());
            bridge.callAttr("seed_workspace");
            runOnUiThread(() -> {
                loadTheme(themeName);
                refreshFiles();
            });
        });

        buildUi();
    }

    // ------------------------------------------------------------------
    // UI construction
    // ------------------------------------------------------------------
    private void buildUi() {
        LinearLayout root = vbox();
        root.setBackgroundColor(editorBg);

        // -- top bar --
        LinearLayout top = hbox();
        TextView brand = label("HICOMB");
        brand.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        brand.setTextColor(Color.parseColor("#7c5cff"));
        brand.setOnClickListener(v -> showAbout());
        top.addView(brand);
        titleFileView = label("—");
        titleFileView.setTypeface(Typeface.MONOSPACE);
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        titleFileView.setLayoutParams(tp);
        top.addView(titleFileView);
        Button saveBtn = button("Save");
        saveBtn.setOnClickListener(v -> saveCurrent());
        top.addView(saveBtn);
        root.addView(top);

        // -- THE LOOP BAR: front and center --
        LinearLayout loop = hbox();
        Button alphaBtn = button("\uD83C\uDFD7 Alpha");
        Button surgeonBtn = button("\u2695 Surgeon");
        Button qpBtn = button("\u267B\uFE0F Quetta-Pan");
        for (Button b : new Button[]{alphaBtn, surgeonBtn, qpBtn}) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            int m = (int) dp(2);
            lp.setMargins(m, m, m, m);
            b.setLayoutParams(lp);
        }
        alphaBtn.setOnClickListener(v -> showAlphaDialog());
        surgeonBtn.setOnClickListener(v -> runSurgeon());
        qpBtn.setOnClickListener(v -> toggleQpPanel());
        loop.addView(alphaBtn);
        loop.addView(surgeonBtn);
        loop.addView(qpBtn);
        root.addView(loop);

        loopStatusView = label("loop: Alpha builds \u2192 Surgeon repairs \u2192 Quetta-Pan improves");
        loopStatusView.setTextSize(11);
        loopStatusView.setTextColor(Color.parseColor("#8a8a9a"));
        root.addView(loopStatusView);

        // -- Quetta-Pan panel (primary feature, one tap away) --
        qpPanel = vbox();
        qpPanel.setVisibility(View.GONE);
        qpPanel.setBackgroundColor(Color.parseColor("#0d0d14"));
        TextView qpLaws = label("laws: dry-run never writes · apply = backup→guard→prove · "
                + "originals never overwritten · nothing thrown away");
        qpLaws.setTextSize(10);
        qpLaws.setTextColor(Color.parseColor("#8a8a9a"));
        qpPanel.addView(qpLaws);
        LinearLayout qpRow1 = hbox();
        TextView qpTitle = label("Quetta-Pan");
        qpTitle.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        qpTitle.setTextColor(Color.parseColor("#7c5cff"));
        qpRow1.addView(qpTitle);
        qpTargetButton = button("target: file");
        qpTargetButton.setOnClickListener(v -> {
            qpTargetProject = !qpTargetProject;
            qpTargetButton.setText(qpTargetProject ? "target: project" : "target: file");
            bg(() -> bridge.callAttr("qp_set_target", qpTargetProject));
            setStatus("quetta-pan target: " + (qpTargetProject ? "project" : "current file"));
        });
        qpRow1.addView(qpTargetButton);
        qpPanel.addView(qpRow1);

        LinearLayout qpRow2 = hbox();
        Button dryBtn = button("Dry-run");
        Button applyAllBtn = button("Apply all");
        Button iterBtn = button("Iterate \u00D73");
        dryBtn.setOnClickListener(v -> qpDryRun());
        applyAllBtn.setOnClickListener(v -> qpApplyAll());
        iterBtn.setOnClickListener(v -> qpIterate(3));
        qpRow2.addView(dryBtn);
        qpRow2.addView(applyAllBtn);
        qpRow2.addView(iterBtn);
        qpPanel.addView(qpRow2);

        qpAdapter = new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_1, qpRows);
        qpResultsView = new ListView(this);
        qpResultsView.setAdapter(qpAdapter);
        qpResultsView.setOnItemClickListener((p, v, pos, id) -> {
            if (pos < qpScanData.size()) showQpDetail(qpScanData.get(pos));
        });
        qpResultsView.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, (int) dp(140)));
        qpPanel.addView(qpResultsView);
        root.addView(qpPanel);

        // -- editor row --
        LinearLayout edRow = hbox();
        LinearLayout.LayoutParams edLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        edRow.setLayoutParams(edLp);

        fileAdapter = new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_1, fileNames);
        fileListView = new ListView(this);
        fileListView.setAdapter(fileAdapter);
        fileListView.setOnItemClickListener((p, v, pos, id) -> openFile(fileNames.get(pos)));
        LinearLayout.LayoutParams flLp = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 0.35f);
        fileListView.setLayoutParams(flLp);
        edRow.addView(fileListView);

        LinearLayout edCol = vbox();
        LinearLayout.LayoutParams ecLp = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 0.65f);
        edCol.setLayoutParams(ecLp);
        editor = new EditText(this);
        editor.setTypeface(Typeface.MONOSPACE);
        editor.setTextSize(13);
        editor.setGravity(Gravity.TOP | Gravity.START);
        editor.setBackgroundColor(editorBg);
        editor.setTextColor(editorFg);
        editor.setHorizontallyScrolling(true);
        LinearLayout.LayoutParams eLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        editor.setLayoutParams(eLp);
        editor.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int a) {
                if (!programmaticEdit && undoStack.size() < 50) {
                    undoStack.push(s.toString());
                    redoStack.clear();
                }
            }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) {}
            @Override public void afterTextChanged(Editable s) {}
        });
        edCol.addView(editor);
        edRow.addView(edCol);
        root.addView(edRow);

        // -- bottom bar --
        LinearLayout bottom = hbox();
        Button undoBtn = button("Undo");
        Button redoBtn = button("Redo");
        Button searchBtn = button("Search");
        Button themeBtn = button("Theme");
        Button newBtn = button("New");
        undoBtn.setOnClickListener(v -> doUndo());
        redoBtn.setOnClickListener(v -> doRedo());
        searchBtn.setOnClickListener(v -> showSearchDialog());
        themeBtn.setOnClickListener(v -> cycleTheme());
        newBtn.setOnClickListener(v -> showNewFileDialog());
        bottom.addView(undoBtn);
        bottom.addView(redoBtn);
        bottom.addView(searchBtn);
        bottom.addView(themeBtn);
        bottom.addView(newBtn);
        root.addView(bottom);

        statusView = label("hicomb · a limb of levi · ready");
        statusView.setTextSize(11);
        statusView.setTextColor(Color.parseColor("#8a8a9a"));
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
        v.setTextColor(editorFg);
        int p = (int) dp(6);
        v.setPadding(p, p, p, p);
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

    private void setLoopStatus(String s) {
        loopStatusView.setText("loop: " + s);
    }

    // ------------------------------------------------------------------
    // Files + editor
    // ------------------------------------------------------------------
    private void refreshFiles() {
        bg(() -> {
            String json = bridge.callAttr("list_files").toString();
            runOnUiThread(() -> {
                try {
                    JSONArray arr = new JSONArray(json);
                    fileNames.clear();
                    for (int i = 0; i < arr.length(); i++) {
                        fileNames.add(arr.getString(i));
                    }
                    fileAdapter.notifyDataSetChanged();
                    if (currentFile == null && !fileNames.isEmpty()) {
                        openFile(fileNames.get(0));
                    }
                } catch (Exception e) {
                    setStatus("file list error: " + e.getMessage());
                }
            });
        });
    }

    private void openFile(String rel) {
        currentFile = rel;
        titleFileView.setText(rel);
        bg(() -> {
            String json = bridge.callAttr("read_file", rel).toString();
            runOnUiThread(() -> {
                try {
                    JSONObject o = new JSONObject(json);
                    if (!o.optBoolean("ok", false)) {
                        setStatus("open failed: " + o.optString("error"));
                        return;
                    }
                    programmaticEdit = true;
                    editor.setText(o.getString("text"));
                    programmaticEdit = false;
                    undoStack.clear();
                    redoStack.clear();
                    applyHighlight();
                } catch (Exception e) {
                    setStatus("open error: " + e.getMessage());
                }
            });
        });
    }

    private void saveCurrent() {
        if (currentFile == null) return;
        String text = editor.getText().toString();
        String rel = currentFile;
        bg(() -> {
            String json = bridge.callAttr("write_file", rel, text).toString();
            runOnUiThread(() -> {
                setStatus("saved " + rel);
                applyHighlight();
            });
        });
    }

    private void doUndo() {
        if (undoStack.isEmpty()) return;
        programmaticEdit = true;
        redoStack.push(editor.getText().toString());
        editor.setText(undoStack.pop());
        programmaticEdit = false;
    }

    private void doRedo() {
        if (redoStack.isEmpty()) return;
        programmaticEdit = true;
        undoStack.push(editor.getText().toString());
        editor.setText(redoStack.pop());
        programmaticEdit = false;
    }

    private void showNewFileDialog() {
        EditText input = new EditText(this);
        input.setHint("name.py");
        new AlertDialog.Builder(this)
                .setTitle("New file")
                .setView(input)
                .setPositiveButton("Create", (d, w) -> {
                    String name = input.getText().toString().trim();
                    if (name.isEmpty()) return;
                    bg(() -> {
                        bridge.callAttr("write_file", name, "");
                        runOnUiThread(() -> {
                            refreshFiles();
                            openFile(name);
                        });
                    });
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showSearchDialog() {
        if (currentFile == null) return;
        EditText input = new EditText(this);
        input.setHint("search…");
        new AlertDialog.Builder(this)
                .setTitle("Search in " + currentFile)
                .setView(input)
                .setPositiveButton("Find", (d, w) -> {
                    String q = input.getText().toString();
                    if (q.isEmpty()) return;
                    String rel = currentFile;
                    bg(() -> {
                        try {
                            String json = bridge.callAttr("search_in_file", rel, q).toString();
                            JSONArray hits = new JSONArray(json);
                            runOnUiThread(() -> {
                                if (hits.length() == 0) {
                                    setStatus("no hits for '" + q + "'");
                                    return;
                                }
                                try {
                                    JSONArray h = hits.getJSONArray(0);
                                    int line = h.getInt(0), col = h.getInt(1);
                                    String text = editor.getText().toString();
                                    String[] lines = text.split("\n", -1);
                                    int off = 0;
                                    for (int i = 0; i < Math.min(line, lines.length); i++) {
                                        off += lines[i].length() + 1;
                                    }
                                    off += Math.min(col, lines[Math.min(line, lines.length - 1)].length());
                                    editor.requestFocus();
                                    editor.setSelection(Math.min(off, text.length()));
                                    setStatus(hits.length() + " hit(s) for '" + q + "'");
                                } catch (Exception e) {
                                    setStatus("jump error: " + e.getMessage());
                                }
                            });
                        } catch (Exception e) {
                            runOnUiThread(() -> setStatus("search error: " + e.getMessage()));
                        }
                    });
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    // ------------------------------------------------------------------
    // Themes + highlight
    // ------------------------------------------------------------------
    private void loadTheme(String name) {
        bg(() -> {
            try {
                String json = bridge.callAttr("theme_get", name).toString();
                JSONObject o = new JSONObject(json);
                JSONObject ui = o.getJSONObject("ui");
                JSONObject syn = o.getJSONObject("syntax");
                Map<String, String> colors = new HashMap<>();
                for (java.util.Iterator<String> it = syn.keys(); it.hasNext(); ) {
                    String k = it.next();
                    colors.put(k, syn.getString(k));
                }
                runOnUiThread(() -> {
                    syntaxColors = colors;
                    try {
                        editorBg = Color.parseColor(ui.optString("bg", "#050508"));
                        editorFg = Color.parseColor(ui.optString("fg", "#e8e8f0"));
                    } catch (Exception ignored) {}
                    editor.setBackgroundColor(editorBg);
                    editor.setTextColor(editorFg);
                    applyHighlight();
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("theme error: " + e.getMessage()));
            }
        });
    }

    private void cycleTheme() {
        bg(() -> {
            try {
                String json = bridge.callAttr("theme_list").toString();
                JSONArray arr = new JSONArray(json);
                List<String> names = new ArrayList<>();
                for (int i = 0; i < arr.length(); i++) names.add(arr.getString(i));
                int next = (names.indexOf(themeName) + 1) % names.size();
                themeName = names.get(next);
                runOnUiThread(() -> {
                    loadTheme(themeName);
                    setStatus("theme: " + themeName);
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("theme error: " + e.getMessage()));
            }
        });
    }

    private void applyHighlight() {
        if (currentFile == null) return;
        String rel = currentFile;
        String text = editor.getText().toString();
        if (text.length() > 200_000) return; // keep the phone happy
        bg(() -> {
            try {
                String json = bridge.callAttr("highlight_spans", rel, text).toString();
                JSONArray spans = new JSONArray(json);
                runOnUiThread(() -> {
                    try {
                        SpannableStringBuilder ssb = new SpannableStringBuilder(text);
                        for (int i = 0; i < spans.length(); i++) {
                            JSONArray s = spans.getJSONArray(i);
                            int st = s.getInt(0), en = s.getInt(1);
                            String kind = s.getString(2);
                            String hex = syntaxColors.get(kind);
                            if (hex == null) continue;
                            ssb.setSpan(new ForegroundColorSpan(Color.parseColor(hex)),
                                    Math.min(st, text.length()), Math.min(en, text.length()),
                                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                        }
                        int cursor = editor.getSelectionStart();
                        programmaticEdit = true;
                        editor.setText(ssb);
                        editor.setSelection(Math.min(cursor, text.length()));
                        programmaticEdit = false;
                    } catch (Exception e) {
                        setStatus("highlight error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("highlight error: " + e.getMessage()));
            }
        });
    }

    // ------------------------------------------------------------------
    // THE LOOP — Alpha builds -> Surgeon repairs -> Quetta-Pan improves
    // ------------------------------------------------------------------
    private void showAbout() {
        bg(() -> {
            String lawsText;
            try {
                String json = bridge.callAttr("laws").toString();
                JSONArray arr = new JSONArray(json);
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject l = arr.getJSONObject(i);
                    sb.append("• ").append(l.getString("name")).append("\n");
                    sb.append("  ").append(l.getString("text")).append("\n\n");
                }
                lawsText = sb.toString();
            } catch (Exception e) {
                lawsText = "laws unavailable: " + e.getMessage();
            }
            String body = "Hicomb is a limb of LEVI — all of Legion is Levi, "
                    + "one organism.\n\nThe laws this app runs on:\n\n" + lawsText
                    + "Honest limits:\n"
                    + "• Alpha scaffolds are offline heuristic templates, not AI generation.\n"
                    + "• Quetta-Pan applies only safe, guarded fixes — held changes say why.\n"
                    + "• Surgeon repairs Python files.\n"
                    + "• Everything runs on-device. No network, no account, no cloud.";
            runOnUiThread(() -> new AlertDialog.Builder(this)
                    .setTitle("Hicomb — a limb of LEVI")
                    .setMessage(body)
                    .setPositiveButton("OK", null)
                    .show());
        });
    }

    private void toggleQpPanel() {
        qpPanel.setVisibility(
                qpPanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
        if (qpPanel.getVisibility() == View.VISIBLE) {
            setStatus("quetta-pan ready — dry-run, apply, iterate");
        }
    }

    private void qpDryRun() {
        setStatus("quetta-pan: scanning…");
        bg(() -> {
            try {
                String json = bridge.callAttr("qp_scan").toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    qpRows.clear();
                    qpScanData.clear();
                    try {
                        JSONArray res = o.getJSONArray("results");
                        for (int i = 0; i < res.length(); i++) {
                            JSONObject r = res.getJSONObject(i);
                            qpScanData.add(r);
                            qpRows.add(r.getString("file") + " — "
                                    + r.getInt("count") + " improvement(s)");
                        }
                        if (qpRows.isEmpty()) qpRows.add("(no improvements found)");
                        qpAdapter.notifyDataSetChanged();
                        setStatus("quetta-pan dry-run: " + res.length() + " file(s) with suggestions");
                    } catch (Exception e) {
                        setStatus("dry-run parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("dry-run error: " + e.getMessage()));
            }
        });
    }

    private void showQpDetail(JSONObject r) {
        String file;
        try {
            file = r.getString("file");
        } catch (Exception e) {
            return;
        }
        setStatus("quetta-pan: detail for " + file + "…");
        bg(() -> {
            try {
                String json = bridge.callAttr("qp_suggest", file).toString();
                JSONObject o = new JSONObject(json);
                JSONObject sug = o.getJSONObject("suggestion");
                runOnUiThread(() -> {
                    try {
                        StringBuilder sb = new StringBuilder();
                        JSONArray arr = sug.getJSONArray("suggestions");
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject s = arr.getJSONObject(i);
                            sb.append("• ").append(s.optString("title")).append("\n");
                            sb.append("  ").append(s.optString("desc")).append("\n\n");
                        }
                        String diff = sug.optString("diff", "");
                        if (!diff.isEmpty()) {
                            sb.append("--- diff ---\n").append(
                                    diff.length() > 3000 ? diff.substring(0, 3000) + "…" : diff);
                        }
                        new AlertDialog.Builder(this)
                                .setTitle("Improve " + file)
                                .setMessage(sb.toString())
                                .setPositiveButton("Apply", (d, w) -> qpApplyFile(file))
                                .setNegativeButton("Close", null)
                                .show();
                    } catch (Exception e) {
                        setStatus("detail error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("detail error: " + e.getMessage()));
            }
        });
    }

    private void qpApplyFile(String file) {
        setStatus("quetta-pan: applying to " + file + "…");
        bg(() -> {
            try {
                String json = bridge.callAttr("qp_apply", file).toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    boolean applied = o.optBoolean("applied", false);
                    setLoopStatus("Quetta-Pan " + (applied ? "improved " + file : "held " + file)
                            + (o.optString("detail", "").isEmpty() ? "" : " — " + o.optString("detail")));
                    setStatus(applied ? "applied improvements to " + file
                            : "no changes applied (" + o.optString("detail", "guard-held") + ")");
                    if (file.equals(currentFile)) openFile(file);
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("apply error: " + e.getMessage()));
            }
        });
    }

    private void qpApplyAll() {
        setStatus("quetta-pan: applying all…");
        bg(() -> {
            try {
                String json = bridge.callAttr("qp_apply_all").toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    setLoopStatus("Quetta-Pan applied " + o.optInt("applied")
                            + ", held " + o.optInt("failed"));
                    setStatus("apply-all: " + o.optInt("applied") + " improved, "
                            + o.optInt("failed") + " held");
                    if (currentFile != null) openFile(currentFile);
                    refreshFiles();
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("apply-all error: " + e.getMessage()));
            }
        });
    }

    private void qpIterate(int rounds) {
        setStatus("quetta-pan: iterating ×" + rounds + "…");
        bg(() -> {
            try {
                String json = bridge.callAttr("qp_iterate", rounds).toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    try {
                        StringBuilder sb = new StringBuilder();
                        sb.append("passes: ").append(o.getInt("passes"))
                                .append(", applied: ").append(o.getInt("applied")).append("\n\n");
                        JSONArray log = o.getJSONArray("log");
                        for (int i = 0; i < log.length(); i++) {
                            sb.append(log.getString(i)).append("\n");
                        }
                        setLoopStatus("Quetta-Pan iterated ×" + o.getInt("passes")
                                + " — " + o.getInt("applied") + " improvements applied");
                        new AlertDialog.Builder(this)
                                .setTitle("Quetta-Pan iterate ×" + rounds)
                                .setMessage(sb.toString())
                                .setPositiveButton("OK", null)
                                .show();
                        if (currentFile != null) openFile(currentFile);
                        refreshFiles();
                    } catch (Exception e) {
                        setStatus("iterate parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("iterate error: " + e.getMessage()));
            }
        });
    }

    private void runSurgeon() {
        if (currentFile == null) {
            setStatus("surgeon: no file open");
            return;
        }
        String rel = currentFile;
        String text = editor.getText().toString();
        setStatus("surgeon: checking " + rel + "…");
        bg(() -> {
            try {
                String checkJson = bridge.callAttr("surgeon_check_text", text).toString();
                JSONObject check = new JSONObject(checkJson);
                String err = check.optString("error", "");
                if (err.isEmpty() || check.isNull("error")) {
                    runOnUiThread(() -> {
                        setLoopStatus("Surgeon: " + rel + " parses clean — nothing to repair");
                        setStatus("surgeon: clean");
                    });
                    return;
                }
                runOnUiThread(() -> new AlertDialog.Builder(this)
                        .setTitle("Surgeon found a problem")
                        .setMessage(err + "\n\nRun multi-pass repair? (snapshot-first, revertible)")
                        .setPositiveButton("Repair", (d, w) -> bg(() -> {
                            try {
                                String rjson = bridge.callAttr("surgeon_repair", rel).toString();
                                JSONObject r = new JSONObject(rjson);
                                runOnUiThread(() -> {
                                    try {
                                        StringBuilder sb = new StringBuilder();
                                        sb.append("passes: ").append(r.getInt("passes")).append("\n");
                                        sb.append("clean: ").append(r.getBoolean("clean")).append("\n");
                                        JSONArray fixes = r.getJSONArray("fixes");
                                        for (int i = 0; i < fixes.length(); i++) {
                                            sb.append("• ").append(fixes.getString(i)).append("\n");
                                        }
                                        setLoopStatus("Surgeon repaired " + rel
                                                + " — " + fixes.length() + " fix(es), clean=" + r.getBoolean("clean"));
                                        new AlertDialog.Builder(this)
                                                .setTitle("Surgeon report")
                                                .setMessage(sb.toString())
                                                .setPositiveButton("OK", null)
                                                .show();
                                        openFile(rel);
                                    } catch (Exception e) {
                                        setStatus("surgeon parse error: " + e.getMessage());
                                    }
                                });
                            } catch (Exception e) {
                                runOnUiThread(() -> setStatus("repair error: " + e.getMessage()));
                            }
                        }))
                        .setNegativeButton("Cancel", null)
                        .show());
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("surgeon error: " + e.getMessage()));
            }
        });
    }

    private void showAlphaDialog() {
        LinearLayout form = vbox();
        EditText desc = new EditText(this);
        desc.setHint("what should Alpha build?");
        form.addView(desc);
        EditText name = new EditText(this);
        name.setHint("project name");
        form.addView(name);
        Spinner stack = new Spinner(this);
        ArrayAdapter<String> sa = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item,
                new String[]{"static", "fullstack"});
        stack.setAdapter(sa);
        form.addView(stack);
        int p = (int) dp(12);
        form.setPadding(p, p, p, p);
        new AlertDialog.Builder(this)
                .setTitle("Alpha — build")
                .setView(form)
                .setPositiveButton("Plan", (d, w) -> {
                    String dsc = desc.getText().toString();
                    String nm = name.getText().toString();
                    String stk = (String) stack.getSelectedItem();
                    bg(() -> {
                        String plan = bridge.callAttr("alpha_plan", dsc, stk, nm).toString();
                        runOnUiThread(() -> new AlertDialog.Builder(this)
                                .setTitle("Build plan")
                                .setMessage(plan)
                                .setPositiveButton("Build it", (d2, w2) -> alphaBuild(dsc, stk, nm))
                                .setNegativeButton("Cancel", null)
                                .show());
                    });
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void alphaBuild(String desc, String stack, String name) {
        setStatus("alpha: building…");
        bg(() -> {
            try {
                String json = bridge.callAttr("alpha_build", desc, stack, name).toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    if (!o.optBoolean("ok", false)) {
                        if ("original exists".equals(o.optString("error"))) {
                            // ORIGINALS-FIRST: refuse loudly, redirect to the improver.
                            new AlertDialog.Builder(this)
                                    .setTitle("Original exists — not overwritten")
                                    .setMessage(o.optString("detail"))
                                    .setPositiveButton("Open Quetta-Pan", (d, w) -> {
                                        qpTargetProject = true;
                                        qpTargetButton.setText("target: project");
                                        bg(() -> bridge.callAttr("qp_set_target", true));
                                        qpPanel.setVisibility(View.VISIBLE);
                                        setStatus("iterate on the original — dry-run first");
                                    })
                                    .setNegativeButton("Cancel", null)
                                    .show();
                        } else {
                            setStatus("alpha build failed: " + o.optString("error"));
                        }
                        return;
                    }
                    setLoopStatus("Alpha built " + o.optString("dest")
                            + " (" + o.optJSONArray("files").length() + " files)"
                            + " → tap Surgeon, then Quetta-Pan");
                    setStatus("alpha: built " + o.optString("dest"));
                    refreshFiles();
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("alpha error: " + e.getMessage()));
            }
        });
    }
}
