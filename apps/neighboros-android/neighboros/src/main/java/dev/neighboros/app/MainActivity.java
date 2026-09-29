package dev.neighboros.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * NeighborOS on Android — gig dispatch (Uber-for-gigs), on-device.
 *
 * Chauncey's plan (docs/NEIGHBOROS_SPEC.md; master DNA 2026-07-27
 * "NeighborOS = gig dispatch"): customers post jobs, workers claim them,
 * dispatch matches the two — trades (plumbing, HVAC, electrical),
 * tech support, general gigs. Proof-of-work ledger, NeighborPay
 * settlement ledger, activation gates.
 *
 * All engine work runs in Python via Chaquopy; this activity is the
 * native shell. Local-only: no network permission is declared.
 *
 * Bloodline law: the founder build runs the original source at full
 * capability; bloodline builds are limited (no gate moves, no dispute
 * resolution) and metered. The flavor comes from the Gradle build.
 *
 * Honest boundaries: NeighborPay is a settlement ledger only — real money
 * moves on labeled external rails, never in core. Disputes freeze
 * settlement and route to a human. Credentials are claims with provenance.
 */
public class MainActivity extends Activity {

    private com.chaquo.python.PyObject bridge;

    private File workspace;
    private int bg = Color.parseColor("#0a0a10");
    private int panel = Color.parseColor("#12121a");
    private int fg = Color.parseColor("#e8e8f0");
    private int dim = Color.parseColor("#8a8a9a");
    private int accent = Color.parseColor("#ffb020");
    private int green = Color.parseColor("#3ddc84");
    private int red = Color.parseColor("#ff6b6b");

    private TextView statusView;
    private LinearLayout content;
    private String currentTab = "post";
    private String jobFilter = "";
    private String selectedWorkerId = "";
    private List<String> categories = new ArrayList<>();
    private Map<String, String> workerNames = new HashMap<>();

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
        bridge = Python.getInstance().getModule("neighboros_bridge");
        workspace = new File(getFilesDir(), "neighboros-ws");
        bg(() -> {
            bridge.callAttr("set_workspace", workspace.getAbsolutePath());
            try {
                bridge.callAttr("set_flavor", BuildConfig.NOS_FLAVOR);
            } catch (Exception ignored) { }
            bridge.callAttr("seed_workspace");
            refreshCategories();
            refreshWorkers();
            runOnUiThread(() -> showTab("post"));
        });
        buildUi();
    }

    private void bg(Runnable r) {
        new Thread(r).start();
    }

    private JSONObject call(String fn, Object... args) {
        try {
            String raw = bridge.callAttr(fn, args).toString();
            return new JSONObject(raw);
        } catch (Exception e) {
            try {
                return new JSONObject("{\"ok\":false,\"error\":\"" +
                        e.toString().replace("\"", "'") + "\"}");
            } catch (Exception ex) {
                return null;
            }
        }
    }

    private void refreshCategories() {
        JSONObject r = call("categories");
        categories.clear();
        if (r != null && r.optBoolean("ok")) {
            JSONArray arr = r.optJSONArray("categories");
            for (int i = 0; i < arr.length(); i++)
                categories.add(arr.optString(i));
        }
        if (categories.isEmpty()) categories.add("general");
    }

    private void refreshWorkers() {
        workerNames.clear();
        JSONObject r = call("workers_list");
        if (r != null && r.optBoolean("ok")) {
            JSONArray arr = r.optJSONArray("workers");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject w = arr.optJSONObject(i);
                workerNames.put(w.optString("id"), w.optString("name"));
            }
        }
    }

    private String workerName(String id) {
        String n = workerNames.get(id);
        return n == null ? id : n;
    }

    // ------------------------------------------------------------------
    // UI construction
    // ------------------------------------------------------------------
    private void buildUi() {
        LinearLayout root = vbox();
        root.setBackgroundColor(bg);

        TextView title = tv("NeighborOS", 22, true, accent);
        root.addView(title);
        TextView sub = tv("gig dispatch · uber-for-gigs · on-device", 12, false, dim);
        root.addView(sub);

        statusView = tv("", 12, false, dim);
        root.addView(statusView);

        LinearLayout tabs = hbox();
        String[] names = {"post", "work", "dispatch", "jobs", "pay", "more"};
        for (String t : names) {
            Button b = btn(t.toUpperCase());
            b.setOnClickListener(v -> showTab(t));
            tabs.addView(b);
        }
        root.addView(tabs);

        content = vbox();
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        content.setLayoutParams(lp);
        root.addView(content);

        setContentView(root);
    }

    private void showTab(String tab) {
        currentTab = tab;
        content.removeAllViews();
        status("loading " + tab + "…");
        bg(() -> runOnUiThread(() -> {
            try {
                if (tab.equals("post")) buildPostTab();
                else if (tab.equals("work")) buildWorkTab();
                else if (tab.equals("dispatch")) buildDispatchTab();
                else if (tab.equals("jobs")) buildJobsTab();
                else if (tab.equals("pay")) buildPayTab();
                else buildMoreTab();
            } catch (Exception e) {
                status("error: " + e);
            }
        }));
    }

    private void status(String s) {
        runOnUiThread(() -> statusView.setText(s));
    }

    // ------------------------------------------------------------------
    // POST tab — customer posts a gig (Plan -> Preview -> Publish)
    // ------------------------------------------------------------------
    private void buildPostTab() {
        content.addView(tv("Post a gig — customers describe the work.",
                13, false, dim));
        LinearLayout f = vbox();
        EditText title = field("title — e.g. fix leaky faucet");
        Spinner cat = new Spinner(this);
        cat.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, categories));
        EditText desc = field("description");
        EditText req = field("your name");
        EditText contact = field("contact (phone/email)");
        EditText cell = field("neighborhood cell — e.g. springfield-test");
        EditText est = field("estimate $ (optional)");
        f.addView(title); f.addView(cat); f.addView(desc);
        f.addView(req); f.addView(contact); f.addView(cell); f.addView(est);
        content.addView(f);
        Button preview = btn("PREVIEW");
        preview.setOnClickListener(v -> bg(() -> {
            JSONObject r = call("gig_draft",
                    title.getText().toString(),
                    categories.get(cat.getSelectedItemPosition()),
                    desc.getText().toString(),
                    req.getText().toString(),
                    contact.getText().toString(),
                    cell.getText().toString(),
                    est.getText().toString());
            runOnUiThread(() -> {
                if (r == null || !r.optBoolean("ok")) {
                    status("draft failed: " + (r == null ? "?" : r.optString("error")));
                    return;
                }
                try {
                    String draftJson = r.getJSONObject("draft").toString();
                    JSONObject p = call("gig_preview", draftJson);
                    String text = (p != null && p.optBoolean("ok"))
                            ? p.optString("preview") : "preview failed";
                    new AlertDialog.Builder(this)
                            .setTitle("Gig preview")
                            .setMessage(text)
                            .setPositiveButton("Publish", (d, w) -> bg(() -> {
                                JSONObject pub = call("gig_publish", draftJson, true);
                                runOnUiThread(() -> {
                                    if (pub != null && pub.optBoolean("ok")) {
                                        JSONObject g = pub.optJSONObject("gig");
                                        status("posted: " + g.optString("id")
                                                + " · DNA " + g.optString("dna"));
                                        showTab("dispatch");
                                    } else {
                                        status("publish failed: " + (pub == null
                                                ? "?" : pub.optString("error")));
                                    }
                                });
                            }))
                            .setNegativeButton("Edit", null).show();
                } catch (Exception e) {
                    status("error: " + e);
                }
            });
        }));
        content.addView(preview);
        status("post tab ready");
    }

    // ------------------------------------------------------------------
    // WORK tab — worker: register, availability, claim + proof-of-work
    // ------------------------------------------------------------------
    private void buildWorkTab() {
        refreshWorkers();
        LinearLayout bar = hbox();
        Button reg = btn("+ REGISTER");
        reg.setOnClickListener(v -> registerWorkerDialog());
        bar.addView(reg);
        content.addView(bar);

        JSONObject wl = call("workers_list");
        List<String> ids = new ArrayList<>();
        List<String> names = new ArrayList<>();
        if (wl != null && wl.optBoolean("ok")) {
            JSONArray arr = wl.optJSONArray("workers");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject w = arr.optJSONObject(i);
                ids.add(w.optString("id"));
                names.add(w.optString("name") + " [" + w.optString("status")
                        + (w.optBoolean("available") ? "" : " · off") + "]");
            }
        }
        if (ids.isEmpty()) {
            content.addView(tv("No workers yet — register one to start.",
                    13, false, dim));
            status("work tab ready");
            return;
        }
        if (selectedWorkerId.isEmpty() || !ids.contains(selectedWorkerId))
            selectedWorkerId = ids.get(0);
        content.addView(tv("Acting as worker:", 12, false, dim));
        Spinner sp = new Spinner(this);
        sp.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, names));
        sp.setSelection(ids.indexOf(selectedWorkerId));
        final List<String> fids = ids;
        sp.setOnItemSelectedListener(new SimpleSelected() {
            @Override public void onPick(int pos) {
                selectedWorkerId = fids.get(pos);
                showTab("work");
            }
        });
        content.addView(sp);

        final String wid = selectedWorkerId;
        LinearLayout acts = hbox();
        Button avail = btn("TOGGLE AVAILABILITY");
        avail.setOnClickListener(v -> bg(() -> {
            JSONObject wj = findWorker(wid);
            boolean cur = wj != null && wj.optBoolean("available", true);
            JSONObject r = call("worker_set_available", wid, !cur);
            runOnUiThread(() -> showTab("work"));
        }));
        acts.addView(avail);
        content.addView(acts);

        content.addView(tv("My gigs:", 14, true, fg));
        JSONObject gl = call("gigs_list", "", "");
        ListView list = new ListView(this);
        List<String> rows = new ArrayList<>();
        final List<JSONObject> data = new ArrayList<>();
        if (gl != null && gl.optBoolean("ok")) {
            JSONArray arr = gl.optJSONArray("gigs");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject g = arr.optJSONObject(i);
                if (!wid.equals(g.optString("worker_id"))) continue;
                data.add(g);
                rows.add(g.optString("id") + " " + g.optString("title")
                        + "  [" + g.optString("status") + "]");
            }
        }
        list.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_1, rows));
        list.setOnItemClickListener((p, v, pos, id) ->
                workerGigDialog(data.get(pos), wid));
        content.addView(list);
        status(rows.size() + " gigs for " + workerName(wid));
    }

    private JSONObject findWorker(String wid) {
        JSONObject wl = call("workers_list");
        if (wl != null && wl.optBoolean("ok")) {
            JSONArray arr = wl.optJSONArray("workers");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject w = arr.optJSONObject(i);
                if (wid.equals(w.optString("id"))) return w;
            }
        }
        return null;
    }

    private void registerWorkerDialog() {
        LinearLayout f = vbox();
        EditText name = field("name");
        EditText contact = field("contact (phone/email)");
        EditText cats = field("verticals — e.g. plumbing,hvac");
        EditText cell = field("home cell — e.g. springfield-test");
        f.addView(name); f.addView(contact); f.addView(cats); f.addView(cell);
        new AlertDialog.Builder(this).setTitle("Register worker").setView(f)
                .setPositiveButton("Register", (d, w) -> bg(() -> {
                    JSONObject r = call("worker_register",
                            name.getText().toString(),
                            contact.getText().toString(),
                            cats.getText().toString(),
                            cell.getText().toString());
                    runOnUiThread(() -> {
                        if (r != null && r.optBoolean("ok")) {
                            refreshWorkers();
                            selectedWorkerId = r.optJSONObject("worker").optString("id");
                            showTab("work");
                        } else {
                            status("register failed: " + (r == null
                                    ? "?" : r.optString("error")));
                        }
                    });
                }))
                .setNegativeButton("Cancel", null).show();
    }

    private void workerGigDialog(JSONObject g, String wid) {
        String gid = g.optString("id");
        String st = g.optString("status");
        StringBuilder sb = new StringBuilder();
        sb.append(gid).append(" ").append(g.optString("title")).append("\n");
        sb.append("status: ").append(st).append(" · ")
                .append(g.optString("category")).append("\n");
        sb.append("customer: ").append(g.optString("requester"))
                .append(" <").append(g.optString("requester_contact")).append(">\n");
        sb.append("cell: ").append(g.optString("cell")).append("\n");
        TextView body = tv(sb.toString(), 13, false, fg);
        AlertDialog.Builder b = new AlertDialog.Builder(this)
                .setTitle("My gig").setView(body)
                .setNegativeButton("Close", null);
        if (st.equals("offered")) {
            b.setPositiveButton("Accept", (d, w) -> bg(() -> {
                JSONObject r = call("offer_accept", gid, wid);
                runOnUiThread(() -> {
                    if (r != null && r.optBoolean("ok")) showTab("work");
                    else status("accept failed: " + (r == null
                            ? "?" : r.optString("error")));
                });
            }));
        } else if (st.equals("accepted")) {
            b.setPositiveButton("Check in", (d, w) -> bg(() -> {
                call("proof_checkin", gid, wid);
                runOnUiThread(() -> showTab("work"));
            }));
        } else if (st.equals("in_progress")) {
            b.setPositiveButton("Check out", (d, w) -> bg(() -> {
                call("proof_checkout", gid, wid);
                runOnUiThread(() -> showTab("work"));
            }));
            b.setNeutralButton("Note", (d, w) -> {
                EditText e = field("progress note");
                new AlertDialog.Builder(this).setTitle("Progress note").setView(e)
                        .setPositiveButton("Save", (dd, ww) -> bg(() -> {
                            call("proof_note", gid, wid, e.getText().toString());
                            runOnUiThread(() -> showTab("work"));
                        }))
                        .setNegativeButton("Cancel", null).show();
            });
        }
        b.show();
    }

    // ------------------------------------------------------------------
    // DISPATCH tab — match open gigs to workers (explainable dispatch)
    // ------------------------------------------------------------------
    private void buildDispatchTab() {
        content.addView(tv("Dispatch — explainable matching. Every score " +
                "shows its rules; no black box.", 13, false, dim));
        JSONObject gl = call("gigs_list", "open", "");
        List<String> ids = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        if (gl != null && gl.optBoolean("ok")) {
            JSONArray arr = gl.optJSONArray("gigs");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject g = arr.optJSONObject(i);
                ids.add(g.optString("id"));
                labels.add(g.optString("id") + " " + g.optString("title")
                        + " [" + g.optString("category") + "]");
            }
        }
        if (ids.isEmpty()) {
            content.addView(tv("No open gigs — post one from the POST tab.",
                    13, false, dim));
            status("dispatch tab ready");
            return;
        }
        Spinner sp = new Spinner(this);
        sp.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, labels));
        content.addView(sp);
        Button match = btn("FIND WORKERS");
        match.setOnClickListener(v -> {
            String gid = ids.get(sp.getSelectedItemPosition());
            bg(() -> {
                JSONObject r = call("dispatch_candidates", gid, 5);
                runOnUiThread(() -> showCandidates(gid, r));
            });
        });
        content.addView(match);
        status(ids.size() + " open gigs");
    }

    private void showCandidates(String gid, JSONObject r) {
        content.removeAllViews();
        Button back = btn("← BACK");
        back.setOnClickListener(v -> showTab("dispatch"));
        content.addView(back);
        if (r == null || !r.optBoolean("ok")) {
            content.addView(tv("match failed: " + (r == null ? "?"
                    : r.optString("error")), 13, false, red));
            return;
        }
        JSONArray arr = r.optJSONArray("candidates");
        if (arr == null || arr.length() == 0) {
            content.addView(tv("No eligible workers for " + gid + ".",
                    13, false, dim));
            return;
        }
        for (int i = 0; i < arr.length(); i++) {
            JSONObject c = arr.optJSONObject(i);
            StringBuilder sb = new StringBuilder();
            sb.append(c.optString("worker_name"))
                    .append("  ").append(c.optInt("score"))
                    .append("/").append(c.optInt("max_score")).append("\n");
            JSONArray bd = c.optJSONArray("breakdown");
            for (int k = 0; k < bd.length(); k++) {
                JSONObject b = bd.optJSONObject(k);
                sb.append(b.optBoolean("matched") ? "+ " : "· ")
                        .append(b.optString("rule")).append(": ")
                        .append(b.optString("explanation")).append("\n");
            }
            sb.append("contact: ").append(c.optString("contact"));
            TextView t = tv(sb.toString(), 12, false, fg);
            t.setBackgroundColor(panel);
            content.addView(t);
            final String wid = c.optString("worker_id");
            Button offer = btn("OFFER → " + c.optString("worker_name"));
            offer.setOnClickListener(v -> offerDialog(gid, wid,
                    c.optString("worker_name")));
            content.addView(offer);
        }
        status(arr.length() + " candidates for " + gid);
    }

    private void offerDialog(String gid, String wid, String wname) {
        EditText op = field("operator name");
        new AlertDialog.Builder(this)
                .setTitle("Offer " + gid + " → " + wname)
                .setMessage("Dispatch is gate-enforced. Confirm to send the offer.")
                .setView(op)
                .setPositiveButton("Send offer", (d, w) -> bg(() -> {
                    JSONObject r = call("offer_make", gid, wid,
                            op.getText().toString(), true);
                    runOnUiThread(() -> {
                        if (r != null && r.optBoolean("ok")) {
                            status("offer sent · verified: "
                                    + r.optBoolean("verified")
                                    + " · gate: " + r.optString("gate"));
                            showTab("jobs");
                        } else {
                            status("offer failed: " + (r == null
                                    ? "?" : r.optString("error")));
                        }
                    });
                }))
                .setNegativeButton("Cancel", null).show();
    }

    // ------------------------------------------------------------------
    // JOBS tab — track every gig, proof ledger, sign-off, disputes
    // ------------------------------------------------------------------
    private void buildJobsTab() {
        String[] f = {"", "open", "offered", "accepted", "in_progress",
                "done", "paid", "disputed"};
        LinearLayout bar = hbox();
        Spinner filter = new Spinner(this);
        List<String> opts = new ArrayList<>();
        opts.add("all");
        for (String s : f) if (!s.isEmpty()) opts.add(s);
        filter.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, opts));
        filter.setSelection(opts.indexOf(jobFilter.isEmpty() ? "all" : jobFilter));
        filter.setOnItemSelectedListener(new SimpleSelected() {
            @Override public void onPick(int pos) {
                jobFilter = pos == 0 ? "" : opts.get(pos);
                showTab("jobs");
            }
        });
        bar.addView(filter);
        content.addView(bar);

        JSONObject res = call("gigs_list", jobFilter, "");
        ListView list = new ListView(this);
        List<String> rows = new ArrayList<>();
        final List<JSONObject> data = new ArrayList<>();
        if (res != null && res.optBoolean("ok")) {
            JSONArray arr = res.optJSONArray("gigs");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject g = arr.optJSONObject(i);
                data.add(g);
                rows.add(g.optString("id") + " " + g.optString("title")
                        + "  [" + g.optString("status") + "]"
                        + (g.optString("worker_id").isEmpty() ? ""
                        : " → " + workerName(g.optString("worker_id"))));
            }
        }
        list.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_1, rows));
        list.setOnItemClickListener((p, v, pos, id) ->
                jobDetailDialog(data.get(pos)));
        content.addView(list);
        status(rows.size() + " gigs" + (jobFilter.isEmpty() ? "" : " · " + jobFilter));
    }

    private void jobDetailDialog(JSONObject g) {
        String gid = g.optString("id");
        JSONObject full = call("gig_get", gid);
        final JSONObject job = (full != null && full.optBoolean("ok"))
                ? full.optJSONObject("gig") : g;
        StringBuilder sb = new StringBuilder();
        sb.append(job.optString("id")).append(" ")
                .append(job.optString("title")).append("\n");
        sb.append("status: ").append(job.optString("status"))
                .append(" · ").append(job.optString("category")).append("\n");
        sb.append("customer: ").append(job.optString("requester"))
                .append(" <").append(job.optString("requester_contact")).append(">\n");
        sb.append("worker: ").append(workerName(job.optString("worker_id"))).append("\n");
        sb.append("cell: ").append(job.optString("cell"))
                .append(" · DNA: ").append(job.optString("dna")).append("\n");
        if (!job.optString("description").isEmpty())
            sb.append(job.optString("description")).append("\n");
        JSONObject pl = call("proof_ledger", gid);
        if (pl != null && pl.optBoolean("ok")) {
            JSONArray arr = pl.optJSONArray("entries");
            if (arr.length() > 0) {
                sb.append("--- proof of work ---\n");
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject e = arr.optJSONObject(i);
                    sb.append("· ").append(e.optString("kind"));
                    if (!e.optString("note").isEmpty())
                        sb.append(": ").append(e.optString("note"));
                    if (e.optInt("rating", 0) > 0)
                        sb.append(" (rating ").append(e.optInt("rating")).append("/5)");
                    sb.append("\n");
                }
            }
        }
        TextView body = tv(sb.toString(), 13, false, fg);
        ScrollView sv = new ScrollView(this);
        sv.addView(body);
        AlertDialog.Builder b = new AlertDialog.Builder(this)
                .setTitle("Gig " + gid).setView(sv)
                .setNegativeButton("Close", null);
        if (job.optString("status").equals("done")) {
            b.setPositiveButton("Customer sign-off", (d, w) ->
                    signoffDialog(gid, job.optString("requester")));
        }
        if (!job.optString("status").equals("disputed")) {
            b.setNeutralButton("Raise dispute", (d, w) ->
                    disputeDialog(gid));
        }
        b.show();
    }

    private void signoffDialog(String gid, String requester) {
        LinearLayout f = vbox();
        EditText who = field("requester name");
        who.setText(requester);
        EditText rating = field("rating 1-5");
        f.addView(who); f.addView(rating);
        new AlertDialog.Builder(this).setTitle("Customer sign-off").setView(f)
                .setPositiveButton("Sign off", (d, w) -> bg(() -> {
                    JSONObject r = call("proof_signoff", gid,
                            who.getText().toString(), rating.getText().toString());
                    runOnUiThread(() -> {
                        if (r != null && r.optBoolean("ok")) {
                            status("signed off — ready to settle (PAY tab)");
                            showTab("pay");
                        } else {
                            status("sign-off failed: " + (r == null
                                    ? "?" : r.optString("error")));
                        }
                    });
                }))
                .setNegativeButton("Cancel", null).show();
    }

    private void disputeDialog(String gid) {
        LinearLayout f = vbox();
        EditText who = field("raised by");
        EditText reason = field("reason");
        f.addView(who); f.addView(reason);
        new AlertDialog.Builder(this).setTitle("Raise dispute").setView(f)
                .setPositiveButton("Raise", (d, w) -> bg(() -> {
                    JSONObject r = call("dispute_raise", gid,
                            who.getText().toString(), reason.getText().toString());
                    runOnUiThread(() -> {
                        status((r != null && r.optBoolean("ok"))
                                ? "dispute raised — settlement frozen"
                                : "failed: " + (r == null ? "?" : r.optString("error")));
                        showTab("jobs");
                    });
                }))
                .setNegativeButton("Cancel", null).show();
    }

    // ------------------------------------------------------------------
    // PAY tab — NeighborPay settlement ledger (records, never moves money)
    // ------------------------------------------------------------------
    private void buildPayTab() {
        content.addView(tv("NeighborPay — settlement ledger. The worker " +
                "keeps 90%+. Real money moves on labeled external rails only.",
                13, false, dim));
        JSONObject gl = call("gigs_list", "done", "");
        List<String> ids = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        if (gl != null && gl.optBoolean("ok")) {
            JSONArray arr = gl.optJSONArray("gigs");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject g = arr.optJSONObject(i);
                ids.add(g.optString("id"));
                labels.add(g.optString("id") + " " + g.optString("title")
                        + " → " + workerName(g.optString("worker_id")));
            }
        }
        if (ids.isEmpty()) {
            content.addView(tv("No signed-off gigs awaiting settlement.",
                    13, false, dim));
            status("pay tab ready");
            return;
        }
        Spinner sp = new Spinner(this);
        sp.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, labels));
        content.addView(sp);
        EditText amount = field("amount paid $");
        content.addView(amount);
        Button plan = btn("PLAN SETTLEMENT");
        plan.setOnClickListener(v -> {
            String gid = ids.get(sp.getSelectedItemPosition());
            bg(() -> {
                JSONObject r = call("settle_plan", gid,
                        amount.getText().toString());
                runOnUiThread(() -> {
                    if (r == null || !r.optBoolean("ok")) {
                        status("plan failed: " + (r == null ? "?"
                                : r.optString("error")));
                        return;
                    }
                    JSONObject p = r.optJSONObject("plan");
                    String msg = r.optString("preview")
                            + "\n\nworker keeps $" + p.optDouble("worker_keep")
                            + " (" + (int) (p.optDouble("keep_rate") * 100)
                            + "%) — floor 90%";
                    new AlertDialog.Builder(this)
                            .setTitle("Settlement plan").setMessage(msg)
                            .setPositiveButton("Execute", (d, w) ->
                                    settleExecuteDialog(gid,
                                            amount.getText().toString()))
                            .setNegativeButton("Cancel", null).show();
                });
            });
        });
        content.addView(plan);
        status(ids.size() + " gigs ready to settle");
    }

    private void settleExecuteDialog(String gid, String amount) {
        LinearLayout f = vbox();
        EditText rail = field("rail — e.g. cash, stripe, bank-transfer");
        EditText ref = field("rail reference");
        f.addView(rail); f.addView(ref);
        new AlertDialog.Builder(this)
                .setTitle("Execute settlement")
                .setMessage("The ledger records the rail + reference. " +
                        "It never moves money itself.")
                .setView(f)
                .setPositiveButton("Settle", (d, w) -> bg(() -> {
                    JSONObject r = call("settle_execute", gid, amount,
                            rail.getText().toString(),
                            ref.getText().toString(), true);
                    runOnUiThread(() -> {
                        if (r != null && r.optBoolean("ok")) {
                            JSONObject s = r.optJSONObject("settlement");
                            JSONObject rc = call("settle_receipt",
                                    s.optString("id"));
                            String receipt = (rc != null && rc.optBoolean("ok"))
                                    ? rc.optString("receipt") : "receipt failed";
                            new AlertDialog.Builder(this)
                                    .setTitle("Receipt")
                                    .setMessage(receipt)
                                    .setPositiveButton("Done", null).show();
                            status("settled ✓ verified: "
                                    + s.optBoolean("verified"));
                        } else {
                            status("settle failed: " + (r == null
                                    ? "?" : r.optString("error")));
                        }
                    });
                }))
                .setNegativeButton("Cancel", null).show();
    }

    // ------------------------------------------------------------------
    // MORE tab — gates, waitlist, disputes, metering (founder-gated)
    // ------------------------------------------------------------------
    private void buildMoreTab() {
        JSONObject fl = call("flavor");
        String flavorNote = (fl != null && fl.optBoolean("ok"))
                ? ("build: " + fl.optString("flavor")
                + (fl.optBoolean("limited") ? " · LIMITED" : " · FULL"))
                : "build: ?";
        content.addView(tv(flavorNote, 13, true, accent));

        content.addView(tv("Activation gates", 15, true, fg));
        JSONObject gs = call("gate_stage");
        if (gs != null && gs.optBoolean("ok")) {
            content.addView(tv("stage: " + gs.optString("stage"), 13, false, fg));
            JSONObject cl = gs.optJSONObject("checklist");
            if (cl != null) {
                JSONArray items = cl.optJSONArray("items");
                StringBuilder sb = new StringBuilder("next checklist:\n");
                if (items != null) for (int i = 0; i < items.length(); i++) {
                    JSONObject it = items.optJSONObject(i);
                    sb.append(it.optBoolean("done") ? "[x] " : "[ ] ")
                            .append(it.optString("id")).append(" — ")
                            .append(it.optString("note")).append("\n");
                }
                content.addView(tv(sb.toString(), 12, false, dim));
            }
        }
        LinearLayout grow = hbox();
        Button adv = btn("ADVANCE GATE");
        adv.setOnClickListener(v -> {
            EditText op = field("operator name");
            new AlertDialog.Builder(this).setTitle("Advance gate").setView(op)
                    .setPositiveButton("Advance", (d, w) -> bg(() -> {
                        JSONObject r = call("gate_advance",
                                op.getText().toString(), true);
                        runOnUiThread(() -> {
                            status((r != null && r.optBoolean("ok"))
                                    ? "gate advanced"
                                    : "advance failed: " + (r == null ? "?"
                                    : r.optString("error")));
                            showTab("more");
                        });
                    }))
                    .setNegativeButton("Cancel", null).show();
        });
        grow.addView(adv);
        content.addView(grow);

        content.addView(tv("Waitlist", 15, true, fg));
        LinearLayout wrow = hbox();
        Button wadd = btn("+ WAITLIST");
        wadd.setOnClickListener(v -> waitlistDialog());
        wrow.addView(wadd);
        content.addView(wrow);

        content.addView(tv("Disputes", 15, true, fg));
        JSONObject dq = call("disputes_list");
        ListView dl = new ListView(this);
        List<String> drows = new ArrayList<>();
        final List<JSONObject> ddata = new ArrayList<>();
        if (dq != null && dq.optBoolean("ok")) {
            JSONArray arr = dq.optJSONArray("disputes");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject x = arr.optJSONObject(i);
                ddata.add(x);
                drows.add(x.optString("id") + " gig " + x.optString("gig_id")
                        + " — " + x.optString("reason"));
            }
        }
        dl.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_1, drows));
        dl.setOnItemClickListener((p, v, pos, id) ->
                resolveDisputeDialog(ddata.get(pos)));
        content.addView(dl);

        JSONObject ml = call("metering_log");
        if (ml != null && ml.optBoolean("ok")) {
            content.addView(tv("Metering events: " + ml.optInt("count"),
                    13, false, dim));
        }
        status("more tab ready");
    }

    private void waitlistDialog() {
        LinearLayout f = vbox();
        EditText name = field("name");
        EditText contact = field("contact");
        EditText role = field("role — customer/worker");
        EditText cell = field("neighborhood cell");
        f.addView(name); f.addView(contact); f.addView(role); f.addView(cell);
        new AlertDialog.Builder(this).setTitle("Join waitlist").setView(f)
                .setPositiveButton("Join", (d, w) -> bg(() -> {
                    JSONObject r = call("waitlist_add",
                            name.getText().toString(),
                            contact.getText().toString(),
                            role.getText().toString(),
                            cell.getText().toString());
                    runOnUiThread(() -> status((r != null && r.optBoolean("ok"))
                            ? "waitlisted ✓" : "failed: " + (r == null ? "?"
                            : r.optString("error"))));
                }))
                .setNegativeButton("Cancel", null).show();
    }

    private void resolveDisputeDialog(JSONObject x) {
        LinearLayout f = vbox();
        EditText op = field("decided by (human)");
        EditText note = field("note");
        f.addView(op); f.addView(note);
        Spinner oc = new Spinner(this);
        oc.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item,
                new String[]{"release", "void"}));
        f.addView(oc);
        new AlertDialog.Builder(this)
                .setTitle("Resolve " + x.optString("id"))
                .setMessage("Human decision only. Release → payable; void → no settlement.")
                .setView(f)
                .setPositiveButton("Resolve", (d, w) -> bg(() -> {
                    JSONObject r = call("dispute_resolve", x.optString("id"),
                            op.getText().toString(),
                            oc.getSelectedItem().toString(),
                            note.getText().toString());
                    runOnUiThread(() -> {
                        status((r != null && r.optBoolean("ok"))
                                ? "dispute resolved"
                                : "resolve failed: " + (r == null ? "?"
                                : r.optString("error")));
                        showTab("more");
                    });
                }))
                .setNegativeButton("Cancel", null).show();
    }

    // ------------------------------------------------------------------
    // widget helpers
    // ------------------------------------------------------------------
    private LinearLayout vbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        int p = (int) dp(8);
        l.setPadding(p, p, p, p);
        return l;
    }

    private LinearLayout hbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        return l;
    }

    private TextView tv(String s, int sp, boolean bold, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding((int) dp(4), (int) dp(4), (int) dp(4), (int) dp(4));
        return t;
    }

    private Button btn(String s) {
        Button b = new Button(this);
        b.setText(s);
        b.setTextColor(fg);
        b.setBackgroundColor(panel);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        lp.setMargins((int) dp(2), (int) dp(2), (int) dp(2), (int) dp(2));
        b.setLayoutParams(lp);
        return b;
    }

    private EditText field(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(dim);
        e.setTextColor(fg);
        e.setBackgroundColor(panel);
        return e;
    }

    private abstract static class SimpleSelected
            implements android.widget.AdapterView.OnItemSelectedListener {
        public abstract void onPick(int pos);
        @Override public void onItemSelected(
                android.widget.AdapterView<?> p, View v, int pos, long id) {
            onPick(pos);
        }
        @Override public void onNothingSelected(
                android.widget.AdapterView<?> p) { }
    }
}
