package dev.quettapan.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Quetta-Pan standalone — point at code, dry-run, review, apply, iterate.
 *
 * The review gate is structural: dry-run never writes; every apply is an
 * explicit tap that goes through the engine's backup -> write ->
 * guard-evaluate flow. Nothing mutates silently.
 */
public class MainActivity extends Activity {

    private com.chaquo.python.PyObject bridge;
    private File workspace;

    private TextView targetView;
    private TextView statusView;
    private ListView resultsView;
    private TextView logView;
    private final List<String> rows = new ArrayList<>();
    private ArrayAdapter<String> adapter;
    private final List<JSONObject> scanData = new ArrayList<>();

    private float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        bridge = Python.getInstance().getModule("qp_bridge");

        workspace = new File(getFilesDir(), "qp-ws");
        bg(() -> {
            bridge.callAttr("set_workspace", workspace.getAbsolutePath());
            bridge.callAttr("seed_workspace");
            runOnUiThread(() -> setStatus("ready — tap Dry-run to scan"));
        });

        buildUi();
    }

    // ------------------------------------------------------------------
    private void buildUi() {
        LinearLayout root = vbox();
        root.setBackgroundColor(Color.parseColor("#0a0a10"));

        TextView brand = label("QUETTA-PAN");
        brand.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        brand.setTextSize(20);
        brand.setTextColor(Color.parseColor("#4fd18b"));
        root.addView(brand);

        TextView limb = label("a limb of levi — one organism");
        limb.setTextSize(11);
        limb.setTextColor(Color.parseColor("#8a9a8a"));
        root.addView(limb);

        TextView lawsView = label("laws: dry-run never writes · apply = backup→guard→prove · "
                + "nothing thrown away · applied vs held always reported");
        lawsView.setTextSize(10);
        lawsView.setTextColor(Color.parseColor("#8a9a8a"));
        root.addView(lawsView);

        targetView = label("target: " + workspace.getAbsolutePath());
        targetView.setTextSize(11);
        targetView.setTextColor(Color.parseColor("#8a9a8a"));
        root.addView(targetView);

        LinearLayout row1 = hbox();
        Button scanBtn = button("Dry-run");
        Button applyAllBtn = button("Apply all");
        scanBtn.setOnClickListener(v -> dryRun());
        applyAllBtn.setOnClickListener(v -> confirmApplyAll());
        row1.addView(scanBtn);
        row1.addView(applyAllBtn);
        root.addView(row1);

        LinearLayout row2 = hbox();
        TextView itLabel = label("iterate ×");
        EditText rounds = new EditText(this);
        rounds.setText("3");
        rounds.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        rounds.setLayoutParams(new LinearLayout.LayoutParams(
                (int) dp(64), ViewGroup.LayoutParams.WRAP_CONTENT));
        Button iterBtn = button("Iterate");
        iterBtn.setOnClickListener(v -> {
            int n;
            try {
                n = Integer.parseInt(rounds.getText().toString());
            } catch (Exception e) {
                n = 3;
            }
            iterate(n);
        });
        row2.addView(itLabel);
        row2.addView(rounds);
        row2.addView(iterBtn);
        root.addView(row2);

        TextView resLabel = label("improvements (tap for detail)");
        resLabel.setTextColor(Color.parseColor("#4fd18b"));
        root.addView(resLabel);

        adapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, rows);
        resultsView = new ListView(this);
        resultsView.setAdapter(adapter);
        resultsView.setOnItemClickListener((p, v, pos, id) -> {
            if (pos < scanData.size()) showDetail(scanData.get(pos));
        });
        resultsView.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        root.addView(resultsView);

        TextView logLabel = label("log");
        logLabel.setTextColor(Color.parseColor("#4fd18b"));
        root.addView(logLabel);
        logView = label("—");
        logView.setTextSize(11);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, (int) dp(120)));
        root.addView(logView);

        statusView = label("starting…");
        statusView.setTextSize(11);
        statusView.setTextColor(Color.parseColor("#8a9a8a"));
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
        l.setGravity(Gravity.CENTER_VERTICAL);
        l.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        return l;
    }

    private TextView label(String t) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextColor(Color.parseColor("#e8f0e8"));
        int p = (int) dp(6);
        v.setPadding(p, p, p, p);
        return v;
    }

    private Button button(String t) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        int m = (int) dp(2);
        lp.setMargins(m, m, m, m);
        b.setLayoutParams(lp);
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

    private void setLog(String s) {
        logView.setText(s);
    }

    // ------------------------------------------------------------------
    private void dryRun() {
        setStatus("scanning…");
        bg(() -> {
            try {
                String json = bridge.callAttr("scan").toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    rows.clear();
                    scanData.clear();
                    try {
                        JSONArray res = o.getJSONArray("results");
                        for (int i = 0; i < res.length(); i++) {
                            JSONObject r = res.getJSONObject(i);
                            scanData.add(r);
                            rows.add(r.getString("file") + " — "
                                    + r.getInt("count") + " improvement(s)");
                        }
                        if (rows.isEmpty()) rows.add("(no improvements found — code is clean)");
                        adapter.notifyDataSetChanged();
                        setStatus("dry-run: " + res.length() + " file(s) with suggestions");
                        setLog("dry-run complete — no files were changed");
                    } catch (Exception e) {
                        setStatus("parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("scan error: " + e.getMessage()));
            }
        });
    }

    private void showDetail(JSONObject r) {
        String file;
        try {
            file = r.getString("file");
        } catch (Exception e) {
            return;
        }
        setStatus("detail for " + file + "…");
        bg(() -> {
            try {
                String json = bridge.callAttr("detail", file).toString();
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
                                .setTitle(file)
                                .setMessage(sb.toString())
                                .setPositiveButton("Apply to this file", (d, w) -> applyOne(file))
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

    private void applyOne(String file) {
        setStatus("applying to " + file + "…");
        bg(() -> {
            try {
                String json = bridge.callAttr("apply_one", file).toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    boolean applied = o.optBoolean("applied", false);
                    setStatus(applied ? "applied: " + file
                            : "held: " + file + " (" + o.optString("detail", "guard") + ")");
                    setLog((applied ? "APPLIED " : "HELD ") + file
                            + (o.optString("detail", "").isEmpty() ? ""
                            : " — " + o.optString("detail")));
                    dryRun();
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("apply error: " + e.getMessage()));
            }
        });
    }

    private void confirmApplyAll() {
        new AlertDialog.Builder(this)
                .setTitle("Apply all improvements?")
                .setMessage("Quetta-Pan will apply every safe fix it found. "
                        + "Each file is backed up before writing, and guard-held "
                        + "changes are rolled back automatically.")
                .setPositiveButton("Apply all", (d, w) -> applyAll())
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void applyAll() {
        setStatus("applying all…");
        bg(() -> {
            try {
                String json = bridge.callAttr("apply_all").toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    setStatus("apply-all: " + o.optInt("applied") + " improved, "
                            + o.optInt("failed") + " held");
                    StringBuilder sb = new StringBuilder();
                    try {
                        JSONArray det = o.getJSONArray("details");
                        for (int i = 0; i < det.length(); i++) {
                            sb.append(det.getString(i)).append("\n");
                        }
                    } catch (Exception ignored) {}
                    setLog("applied " + o.optInt("applied") + ", held " + o.optInt("failed")
                            + (sb.length() > 0 ? "\n" + sb : ""));
                    dryRun();
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("apply-all error: " + e.getMessage()));
            }
        });
    }

    private void iterate(int rounds) {
        setStatus("iterating ×" + rounds + "…");
        bg(() -> {
            try {
                String json = bridge.callAttr("iterate", rounds).toString();
                JSONObject o = new JSONObject(json);
                runOnUiThread(() -> {
                    try {
                        StringBuilder sb = new StringBuilder();
                        sb.append("passes: ").append(o.getInt("passes"))
                                .append(", applied: ").append(o.getInt("applied")).append("\n");
                        JSONArray log = o.getJSONArray("log");
                        for (int i = 0; i < log.length(); i++) {
                            sb.append(log.getString(i)).append("\n");
                        }
                        setLog(sb.toString());
                        setStatus("iterate ×" + rounds + ": " + o.getInt("applied") + " applied");
                        dryRun();
                    } catch (Exception e) {
                        setStatus("iterate parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("iterate error: " + e.getMessage()));
            }
        });
    }
}
