package dev.buzztunes.app;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.media.MediaPlayer;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Bundle;
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

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;

/**
 * Buzz Tunes on Android — Chauncey's music player, on-device.
 *
 * Bloome (agent-messaging listening threads) + Metrolist (native media
 * surface) MIX in one product — his 2026-09-18 spec. YouTube playback
 * seam (his 2026-09-27 ruling: YouTube, NOT Spotify): the app shows and
 * queues; it never fakes audio. Dark-first void theme.
 *
 * Connectivity (his 2026-09-28 ruling: online connection default, offline
 * capable with downloads): the app uses the online route whenever a
 * network is up — no manual toggle. Downloads are direct audio files
 * persisted on-device and play offline through the phone's audio sink.
 * The library always shows honestly what is offline-ready vs online-only.
 *
 * All engine work (play/queue/curate/dj/forge/m3u/thread, SI DJ,
 * REIM/RIEM loop, receipts, connectivity, downloads) runs in Python via
 * Chaquopy; this activity is the native shell around it.
 */
public class MainActivity extends Activity {

    // ---- python bridge ----
    private com.chaquo.python.PyObject bridge;

    // ---- state ----
    private File store;
    private int tab = 0; // 0 play, 1 dj, 2 threads, 3 forge, 4 stations

    // ---- station state (radio tab) ----
    private PyObject stationObj;
    private List<PyObject> stationCatalog;
    private int stationPos;
    private final List<String> stationIds = new ArrayList<>();
    private final List<String> stationRows = new ArrayList<>();
    private String activeThreadId = null;

    // ---- connectivity + local audio ----
    private MediaPlayer player;
    private TextView connView;
    private ConnectivityManager.NetworkCallback netCallback;
    private boolean online = true; // online is the default (2026-09-28)

    // ---- ui ----
    private TextView statusView;
    private LinearLayout content;
    private final Button[] tabBtns = new Button[5];

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
        bridge = Python.getInstance().getModule("buzztunes_bridge");

        store = new File(getFilesDir(), "buzztunes-store");
        registerConnectivity();
        bg(() -> {
            bridge.callAttr("set_store", store.getAbsolutePath());
            runOnUiThread(() -> {
                setStatus("engine ready \u2014 online default, offline-ready "
                        + "with downloads; YouTube not linked, "
                        + "showing + queueing");
                showTab(0);
            });
        });

        buildUi();
    }

    // ------------------------------------------------------------------
    // Connectivity — online by default (2026-09-28). The real network
    // state is pushed to the engine; the engine treats ONLINE as the
    // default until the first report arrives.
    // ------------------------------------------------------------------
    private void registerConnectivity() {
        ConnectivityManager cm =
                (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkRequest req = new NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .build();
        netCallback = new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network network) { pushOnline(true); }
            @Override public void onLost(Network network) {
                pushOnline(hasInternet(cm)); // another network may still be up
            }
        };
        try {
            cm.registerNetworkCallback(req, netCallback);
        } catch (Exception ignored) { /* older/no-op environments */ }
        pushOnline(hasInternet(cm));
    }

    private boolean hasInternet(ConnectivityManager cm) {
        try {
            Network n = cm.getActiveNetwork();
            if (n == null) return false;
            NetworkCapabilities c = cm.getNetworkCapabilities(n);
            return c != null
                    && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        } catch (Exception e) {
            return true; // can't tell — stay on the online default, don't flap
        }
    }

    private void pushOnline(boolean up) {
        online = up;
        bg(() -> {
            try {
                if (bridge != null) bridge.callAttr("set_online", up ? "1" : "0");
            } catch (Exception ignored) { /* engine not up yet — default is online */ }
            runOnUiThread(this::renderConn);
        });
    }

    private void renderConn() {
        if (connView == null) return;
        connView.setText(online ? "\u25CF ONLINE" : "\u25CF OFFLINE");
        connView.setTextColor(Color.parseColor(online ? "#35d07f" : "#e0a63c"));
    }

    /** Play a real on-device download through the phone's audio sink. */
    private void playLocalFile(String path, String label) {
        bg(() -> {
            try {
                if (player == null) player = new MediaPlayer();
                else player.reset();
                player.setDataSource(path);
                player.prepare();
                player.start();
                runOnUiThread(() -> setStatus("playing download: " + label));
            } catch (Exception e) {
                runOnUiThread(() -> setStatus("local play failed: " + e.getMessage()));
            }
        });
    }

    @Override
    protected void onDestroy() {
        if (netCallback != null) {
            try {
                ConnectivityManager cm =
                        (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
                cm.unregisterNetworkCallback(netCallback);
            } catch (Exception ignored) {}
            netCallback = null;
        }
        if (player != null) {
            try { player.release(); } catch (Exception ignored) {}
            player = null;
        }
        super.onDestroy();
    }

    // ------------------------------------------------------------------
    // UI construction
    // ------------------------------------------------------------------
    private void buildUi() {
        LinearLayout root = vbox();
        root.setBackgroundColor(Color.parseColor("#050508"));

        // -- top bar --
        LinearLayout top = hbox();
        TextView brand = label("BUZZ TUNES");
        brand.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        brand.setTextColor(Color.parseColor("#7c5cff"));
        brand.setTextSize(16);
        top.addView(brand);
        TextView mix = label("bloome \u00d7 metrolist");
        mix.setTextSize(11);
        mix.setTextColor(Color.parseColor("#8a8a9a"));
        top.addView(mix);
        View spacer = new View(this);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        spacer.setLayoutParams(sp);
        top.addView(spacer);
        connView = label("\u25CF \u2026");
        connView.setTextSize(11);
        connView.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        top.addView(connView);
        root.addView(top);
        renderConn();

        // -- tab bar --
        LinearLayout tabs = hbox();
        String[] names = {"\u25b6 Play", "\uD83C\uDFA7 DJ", "\uD83D\uDC65 Threads", "\u2692 Forge", "\uD83D\uDCFB Stations"};
        for (int i = 0; i < 5; i++) {
            final int idx = i;
            Button b = button(names[i]);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            int m = (int) dp(2);
            lp.setMargins(m, m, m, m);
            b.setLayoutParams(lp);
            b.setOnClickListener(v -> showTab(idx));
            tabBtns[i] = b;
            tabs.addView(b);
        }
        root.addView(tabs);

        // -- content --
        ScrollView sv = new ScrollView(this);
        content = vbox();
        sv.addView(content);
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        sv.setLayoutParams(cp);
        root.addView(sv);

        // -- status bar --
        statusView = label("\u2026");
        statusView.setTextSize(11);
        statusView.setTextColor(Color.parseColor("#8a8a9a"));
        root.addView(statusView);

        setContentView(root);
    }

    private void showTab(int idx) {
        tab = idx;
        for (int i = 0; i < 5; i++) {
            tabBtns[i].setTextColor(i == idx
                    ? Color.parseColor("#7c5cff")
                    : Color.parseColor("#e8e8f0"));
        }
        content.removeAllViews();
        if (idx == 0) buildPlayTab();
        else if (idx == 1) buildDjTab();
        else if (idx == 2) buildThreadsTab();
        else if (idx == 3) buildForgeTab();
        else buildStationsTab();
    }

    // ------------------------------------------------------------------
    // PLAY tab — now playing + YouTube honesty + catalog + queue
    // ------------------------------------------------------------------
    private void buildPlayTab() {
        TextView np = label("now playing: \u2014");
        np.setTextSize(15);
        np.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        content.addView(np);

        TextView yt = label("");
        yt.setTextSize(11);
        yt.setTextColor(Color.parseColor("#8a8a9a"));
        content.addView(yt);

        bg(() -> {
            JSONObject s = jcall("youtube_status");
            final String note = s.optBoolean("ok", false)
                    ? "YouTube: " + s.optJSONObject("status").optString("note",
                            "not linked")
                    : "seam error";
            runOnUiThread(() -> yt.setText(note));
        });

        // YouTube-to-ringtone entry (2026-09-29, Chauncey flagship spec).
        // Launches RingtoneActivity; all rules live in
        // levi.buzztunes.ringtone (Python) via RingtoneMaker.
        Button ringtoneBtn = button("\ud83d\udd14 make ringtone from YouTube");
        ringtoneBtn.setOnClickListener(v ->
                startActivity(new android.content.Intent(
                        MainActivity.this, RingtoneActivity.class)));
        content.addView(ringtoneBtn);

        content.addView(sectionLabel(
                "catalog \u2014 tap to queue \u00b7 \u2b07 downloaded "
                + "\u00b7 \ud83c\udf10 online-only"));
        ListView cat = new ListView(this);
        final List<String> catIds = new ArrayList<>();
        final List<String> catRows = new ArrayList<>();
        final ArrayAdapter<String> catAdapter = darkAdapter(catRows);
        cat.setAdapter(catAdapter);
        cat.setOnItemClickListener((AdapterView<?> p, View v, int pos, long id) ->
                bg(() -> {
                    JSONObject r = jcall("queue_add", catIds.get(pos));
                    runOnUiThread(() -> {
                        setStatus(r.optBoolean("ok", false)
                                ? "queued" : "queue failed: "
                                + r.optString("error"));
                        refreshQueue();
                    });
                }));
        content.addView(sized(cat, 220));

        content.addView(sectionLabel("queue"));
        ListView q = new ListView(this);
        final List<String> qRows = new ArrayList<>();
        final ArrayAdapter<String> qAdapter = darkAdapter(qRows);
        q.setAdapter(qAdapter);
        q.setOnItemClickListener((AdapterView<?> p, View v, int pos, long id) ->
                bg(() -> {
                    String tid = (String) q.getTag(pos);
                    if (tid == null) return;
                    JSONObject r = jcall("play", tid);
                    runOnUiThread(() -> {
                        if (r.optBoolean("ok", false)) {
                            JSONObject t = r.optJSONObject("now_playing");
                            JSONObject route = r.optJSONObject("route");
                            String mode = route != null
                                    ? route.optString("mode") : "";
                            String label = t != null
                                    ? t.optString("artist") + " \u2014 "
                                        + t.optString("title") : "?";
                            if ("local".equals(mode)) {
                                np.setText("now playing: " + label + " \u2b07");
                                playLocalFile(route.optString("path"), label);
                            } else if ("unavailable".equals(mode)) {
                                np.setText("now playing: \u2014");
                                setStatus(route.optString("reason",
                                        "unavailable offline"));
                            } else {
                                np.setText("now playing: " + label);
                                setStatus("ordered \u00b7 "
                                        + r.optString("note"));
                            }
                        } else {
                            setStatus("play failed: " + r.optString("error"));
                        }
                    });
                }));
        q.setTag(new ArrayList<String>());
        content.addView(sized(q, 180));

        LinearLayout row = hbox();
        Button refresh = button("refresh");
        refresh.setOnClickListener(v -> {
            refreshCatalog(catIds, catRows, catAdapter);
            refreshQueueInto(q, qRows, qAdapter);
        });
        Button clear = button("clear queue");
        clear.setOnClickListener(v -> bg(() -> {
            jcall("queue_clear");
            runOnUiThread(() -> {
                setStatus("queue cleared");
                refreshQueueInto(q, qRows, qAdapter);
            });
        }));
        row.addView(refresh);
        row.addView(clear);
        content.addView(row);

        // -- downloads: direct audio files, persisted on-device, play offline --
        content.addView(sectionLabel(
                "downloads \u2014 direct audio file URL "
                + "(mp3/wav/ogg/flac/m4a/opus/aac)"));
        EditText dlUrl = input("https://\u2026/track.mp3");
        content.addView(dlUrl);
        EditText dlTitle = input("title (optional)");
        content.addView(dlTitle);
        ListView dl = new ListView(this);
        final List<String> dlIds = new ArrayList<>();
        final List<String> dlRows = new ArrayList<>();
        final ArrayAdapter<String> dlAdapter = darkAdapter(dlRows);
        dl.setAdapter(dlAdapter);
        dl.setOnItemClickListener((AdapterView<?> p, View v, int pos, long id) ->
                bg(() -> {
                    JSONObject r = jcall("play", dlIds.get(pos));
                    runOnUiThread(() -> {
                        if (r.optBoolean("ok", false)) {
                            JSONObject route = r.optJSONObject("route");
                            JSONObject t = r.optJSONObject("now_playing");
                            String label = t != null
                                    ? t.optString("artist") + " \u2014 "
                                        + t.optString("title") : "?";
                            np.setText("now playing: " + label + " \u2b07");
                            if (route != null
                                    && "local".equals(route.optString("mode"))) {
                                playLocalFile(route.optString("path"), label);
                            } else {
                                setStatus("download play: "
                                        + (route != null
                                            ? route.optString("reason",
                                                route.optString("note", "?"))
                                            : "?"));
                            }
                        } else {
                            setStatus("play failed: " + r.optString("error"));
                        }
                    });
                }));
        // No delete affordance: Chauncey's no-deletion law — downloads stay
        // on the device once fetched. Storage management is his call.
        content.addView(sized(dl, 140));
        Button dlBtn = button("download for offline");
        dlBtn.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("download_add",
                    dlUrl.getText().toString(),
                    dlTitle.getText().toString(), "");
            runOnUiThread(() -> {
                if (r.optBoolean("ok", false)) {
                    JSONObject d = r.optJSONObject("download");
                    setStatus("downloaded: " + d.optString("title")
                            + " (" + d.optLong("bytes") + " bytes, "
                            + "sha256 " + d.optString("sha256").substring(0, 12)
                            + "\u2026)");
                    dlUrl.setText("");
                    dlTitle.setText("");
                    refreshDownloads(dlIds, dlRows, dlAdapter);
                    refreshCatalog(catIds, catRows, catAdapter);
                } else {
                    setStatus("download refused: " + r.optString("error"));
                }
            });
        }));
        content.addView(dlBtn);

        refreshCatalog(catIds, catRows, catAdapter);
        refreshQueueInto(q, qRows, qAdapter);
        refreshDownloads(dlIds, dlRows, dlAdapter);
    }

    private void refreshDownloads(List<String> ids, List<String> rows,
                                  ArrayAdapter<String> adapter) {
        bg(() -> {
            JSONObject r = jcall("downloads_list");
            final List<String> nids = new ArrayList<>();
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONArray ds = r.optJSONArray("downloads");
                for (int i = 0; i < ds.length(); i++) {
                    JSONObject d = ds.optJSONObject(i);
                    nids.add(d.optString("id"));
                    String row = d.optString("artist") + " \u2014 "
                            + d.optString("title") + " \u2b07";
                    if (d.optBoolean("missing", false)) row += " (file missing)";
                    nrows.add(row);
                }
            }
            runOnUiThread(() -> {
                ids.clear(); ids.addAll(nids);
                rows.clear(); rows.addAll(nrows);
                adapter.notifyDataSetChanged();
            });
        });
    }

    @SuppressWarnings("unchecked")
    private void refreshQueue() {
        // re-render the queue list on the play tab if visible
        if (tab == 0) showTab(0);
    }

    /** Availability mark: ⬇ downloaded (offline-ready), 🌐 online-only. */
    private static String markFor(JSONObject t) {
        if (t.optBoolean("downloaded", false)) return " \u2b07";
        String a = t.optString("availability", "");
        if ("online-only".equals(a)) return " \ud83c\udf10";
        return "";
    }

    private void refreshCatalog(List<String> ids, List<String> rows,
                                ArrayAdapter<String> adapter) {
        bg(() -> {
            JSONObject r = jcall("catalog");
            final List<String> nids = new ArrayList<>();
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONArray ts = r.optJSONArray("tracks");
                for (int i = 0; i < ts.length(); i++) {
                    JSONObject t = ts.optJSONObject(i);
                    nids.add(t.optString("id"));
                    nrows.add(t.optString("artist") + " \u2014 "
                            + t.optString("title") + markFor(t));
                }
            }
            runOnUiThread(() -> {
                ids.clear(); ids.addAll(nids);
                rows.clear(); rows.addAll(nrows);
                adapter.notifyDataSetChanged();
                setStatus(nrows.size() + " tracks in catalog");
            });
        });
    }

    private void refreshQueueInto(ListView q, List<String> rows,
                                  ArrayAdapter<String> adapter) {
        bg(() -> {
            JSONObject r = jcall("queue_list");
            final List<String> nids = new ArrayList<>();
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONArray ts = r.optJSONArray("tracks");
                for (int i = 0; i < ts.length(); i++) {
                    JSONObject t = ts.optJSONObject(i);
                    nids.add(t.optString("id"));
                    nrows.add(t.optString("artist") + " \u2014 "
                            + t.optString("title") + markFor(t));
                }
            }
            runOnUiThread(() -> {
                ((ArrayList<String>) q.getTag()).clear();
                ((ArrayList<String>) q.getTag()).addAll(nids);
                rows.clear(); rows.addAll(nrows);
                adapter.notifyDataSetChanged();
            });
        });
    }

    // ------------------------------------------------------------------
    // DJ tab — the SI DJ: mood/activity -> pick + why-line
    // ------------------------------------------------------------------
    private void buildDjTab() {
        content.addView(sectionLabel("ask the SI DJ"));
        EditText mood = input("mood (e.g. late-night)");
        EditText activity = input("activity (e.g. drive)");
        EditText energy = input("energy (optional)");
        EditText era = input("era (optional)");
        content.addView(mood);
        content.addView(activity);
        content.addView(energy);
        content.addView(era);

        TextView pick = label("");
        pick.setTextSize(14);
        TextView why = label("");
        why.setTextSize(12);
        why.setTextColor(Color.parseColor("#8a8a9a"));
        TextView path = label("");
        path.setTextSize(11);
        path.setTextColor(Color.parseColor("#8a8a9a"));
        Button ask = button("ask the DJ");
        ask.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("dj_pick",
                    mood.getText().toString(),
                    activity.getText().toString(),
                    energy.getText().toString(),
                    era.getText().toString());
            runOnUiThread(() -> {
                if (r.optBoolean("ok", false)) {
                    JSONObject t = r.optJSONObject("track");
                    pick.setText("\u266a " + t.optString("artist") + " \u2014 "
                            + t.optString("title"));
                    why.setText("why: " + r.optString("reason")
                            + "\n\u201c" + r.optString("voice_line") + "\u201d");
                    path.setText("voice: " + r.optString("voice_path")
                            + " \u00b7 concept: " + r.optString("concept"));
                    setStatus("dj picked from the real catalog");
                } else {
                    pick.setText("");
                    why.setText("");
                    path.setText("");
                    setStatus("dj failed: " + r.optString("error"));
                }
            });
        }));
        content.addView(ask);
        content.addView(pick);
        content.addView(why);
        content.addView(path);

        content.addView(sectionLabel("curate a vibe"));
        EditText query = input("vibe / search seed");
        content.addView(query);
        ListView res = new ListView(this);
        final List<String> rrows = new ArrayList<>();
        final ArrayAdapter<String> radapter = darkAdapter(rrows);
        res.setAdapter(radapter);
        content.addView(sized(res, 200));
        Button go = button("curate");
        go.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("curate", query.getText().toString());
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONObject q2 = r.optJSONObject("result");
                JSONArray qq = q2 != null ? q2.optJSONArray("queue") : null;
                if (qq != null) for (int i = 0; i < qq.length(); i++) {
                    JSONObject t = qq.optJSONObject(i);
                    nrows.add(t.optString("artist") + " \u2014 "
                            + t.optString("title"));
                }
            }
            runOnUiThread(() -> {
                rrows.clear(); rrows.addAll(nrows);
                radapter.notifyDataSetChanged();
                setStatus(r.optBoolean("ok", false)
                        ? nrows.size() + " curated" : "curate: "
                                + r.optString("error"));
            });
        }));
        content.addView(go);
    }

    // ------------------------------------------------------------------
    // THREADS tab — Bloome listening threads: agents curate, members share
    // ------------------------------------------------------------------
    private void buildThreadsTab() {
        content.addView(sectionLabel("listening threads"));
        ListView tl = new ListView(this);
        final List<String> tids = new ArrayList<>();
        final List<String> trows = new ArrayList<>();
        final ArrayAdapter<String> tadapter = darkAdapter(trows);
        tl.setAdapter(tadapter);
        tl.setOnItemClickListener((AdapterView<?> p, View v, int pos, long id) -> {
            activeThreadId = tids.get(pos);
            setStatus("thread: " + trows.get(pos));
            showThreadDetail();
        });
        content.addView(sized(tl, 160));

        EditText name = input("new thread name");
        content.addView(name);
        Button create = button("create thread");
        create.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("thread_create", name.getText().toString());
            runOnUiThread(() -> {
                setStatus(r.optBoolean("ok", false) ? "thread created"
                        : "create failed: " + r.optString("error"));
                refreshThreads(tids, trows, tadapter);
            });
        }));
        content.addView(create);
        refreshThreads(tids, trows, tadapter);
    }

    private void refreshThreads(List<String> ids, List<String> rows,
                                ArrayAdapter<String> adapter) {
        bg(() -> {
            JSONObject r = jcall("threads_list");
            final List<String> nids = new ArrayList<>();
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONArray ts = r.optJSONArray("threads");
                for (int i = 0; i < ts.length(); i++) {
                    JSONObject t = ts.optJSONObject(i);
                    nids.add(t.optString("id"));
                    nrows.add(t.optString("name") + " ["
                            + t.optString("id") + "] \u00b7 "
                            + t.optJSONArray("members").length()
                            + " members \u00b7 "
                            + t.optInt("curations") + " curations");
                }
            }
            runOnUiThread(() -> {
                ids.clear(); ids.addAll(nids);
                rows.clear(); rows.addAll(nrows);
                adapter.notifyDataSetChanged();
            });
        });
    }

    private void showThreadDetail() {
        content.removeAllViews();
        content.addView(sectionLabel("thread " + activeThreadId));
        Button back = button("\u2190 all threads");
        back.setOnClickListener(v -> showTab(2));
        content.addView(back);

        LinearLayout row = hbox();
        EditText member = input("member name");
        Button join = button("join");
        join.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("thread_join", activeThreadId,
                    member.getText().toString());
            runOnUiThread(() -> setStatus(r.optBoolean("ok", false)
                    ? "joined" : "join failed: " + r.optString("error")));
        }));
        row.addView(member);
        row.addView(join);
        content.addView(row);

        content.addView(sectionLabel("agent curation into this thread"));
        EditText agent = input("agent name");
        EditText vibe = input("vibe seed");
        content.addView(agent);
        content.addView(vibe);
        Button curateBtn = button("agent curates");
        curateBtn.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("thread_curate", activeThreadId,
                    agent.getText().toString(), vibe.getText().toString());
            runOnUiThread(() -> {
                setStatus(r.optBoolean("ok", false)
                        ? "curated into thread" : "curate failed: "
                                + r.optString("error"));
                refreshThreadQueue();
            });
        }));
        content.addView(curateBtn);

        content.addView(sectionLabel("shared queue"));
        ListView sq = new ListView(this);
        final List<String> srows = new ArrayList<>();
        final ArrayAdapter<String> sadapter = darkAdapter(srows);
        sq.setAdapter(sadapter);
        content.addView(sized(sq, 220));
        refreshThreadQueueInto(srows, sadapter);
    }

    private void refreshThreadQueue() {
        if (tab == 2 && activeThreadId != null) showThreadDetail();
    }

    private void refreshThreadQueueInto(List<String> rows,
                                        ArrayAdapter<String> adapter) {
        bg(() -> {
            JSONObject r = jcall("thread_queue", activeThreadId);
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONArray qq = r.optJSONArray("queue");
                for (int i = 0; i < qq.length(); i++) {
                    JSONObject e = qq.optJSONObject(i);
                    nrows.add(e.optString("agent", "?") + ": "
                            + e.optString("title", e.toString()));
                }
            }
            runOnUiThread(() -> {
                rows.clear(); rows.addAll(nrows);
                adapter.notifyDataSetChanged();
            });
        });
    }

    // ------------------------------------------------------------------
    // FORGE tab — deterministic playlist forging
    // ------------------------------------------------------------------
    private void buildForgeTab() {
        content.addView(sectionLabel("forge playlists"));
        EditText count = input("count (1\u201320)");
        EditText seed = input("seed");
        content.addView(count);
        content.addView(seed);
        ListView fl = new ListView(this);
        final List<String> frows = new ArrayList<>();
        final ArrayAdapter<String> fadapter = darkAdapter(frows);
        fl.setAdapter(fadapter);
        Button go = button("forge");
        go.setOnClickListener(v -> bg(() -> {
            int n;
            try {
                n = Integer.parseInt(count.getText().toString().trim());
            } catch (NumberFormatException e) {
                n = 2;
            }
            JSONObject r = jcall("forge", String.valueOf(n),
                    seed.getText().toString());
            final List<String> nrows = new ArrayList<>();
            if (r.optBoolean("ok", false)) {
                JSONArray ps = r.optJSONArray("playlists");
                for (int i = 0; i < ps.length(); i++) {
                    JSONObject p = ps.optJSONObject(i);
                    nrows.add("#" + p.optInt("index") + " "
                            + p.optString("concept") + " ["
                            + p.optString("content_hash").substring(0,
                                    Math.min(8, p.optString("content_hash")
                                            .length()))
                            + "]");
                }
            }
            final boolean ok = r.optBoolean("ok", false);
            final String err = r.optString("error");
            runOnUiThread(() -> {
                frows.clear(); frows.addAll(nrows);
                fadapter.notifyDataSetChanged();
                setStatus(ok ? nrows.size() + " playlists forged"
                        : "forge failed: " + err);
            });
        }));
        content.addView(go);
        content.addView(sized(fl, 260));

        content.addView(sectionLabel("engine"));
        LinearLayout row = hbox();
        Button stackBtn = button("stack report");
        stackBtn.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("stack");
            runOnUiThread(() -> setStatus(r.optBoolean("ok", false)
                    ? "stack: " + r.optString("report").substring(0,
                            Math.min(120, r.optString("report").length()))
                            + "\u2026"
                    : "stack failed"));
        }));
        Button lawsBtn = button("laws");
        lawsBtn.setOnClickListener(v -> bg(() -> {
            JSONObject r = jcall("laws");
            StringBuilder sb = new StringBuilder();
            if (r.optBoolean("ok", false)) {
                JSONArray ls = r.optJSONArray("laws");
                for (int i = 0; i < ls.length(); i++)
                    sb.append("\u2022 ").append(ls.optString(i))
                            .append("\n");
            }
            final String txt = sb.toString();
            runOnUiThread(() -> showLaws(txt));
        }));
        row.addView(stackBtn);
        row.addView(lawsBtn);
        content.addView(row);
    }

    private void showLaws(String txt) {
        content.removeAllViews();
        content.addView(sectionLabel("the laws"));
        TextView tv = label(txt);
        tv.setTextSize(12);
        content.addView(tv);
        Button back = button("\u2190 forge");
        back.setOnClickListener(v -> showTab(3));
        content.addView(back);
    }

    // ------------------------------------------------------------------
    // STATIONS tab — radio by artist / genre / song (Chauncey 2026-09-29).
    // Endless, deterministic, seed-transparent (stations.py laws S-L1..S-L4).
    // ------------------------------------------------------------------
    private void buildStationsTab() {
        content.addView(sectionLabel("\uD83D\uDCFB Stations \u2014 endless radio"));
        content.addView(label("Pick an artist, a genre, or a song. The "
                + "station builds from the real catalog, shows its seed, "
                + "and never repeats a track until the whole pool has played."));

        Spinner kindSpin = new Spinner(this);
        ArrayAdapter<String> kindAd = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item,
                new String[]{"artist", "genre", "song"});
        kindAd.setDropDownViewResource(
                android.R.layout.simple_spinner_dropdown_item);
        kindSpin.setAdapter(kindAd);
        content.addView(kindSpin);

        EditText seedInput = input("artist, genre, or song\u2026");
        content.addView(seedInput);

        Button startBtn = button("Start station");
        content.addView(startBtn);

        TextView seedView = label("");
        seedView.setTextSize(11);
        seedView.setTypeface(Typeface.MONOSPACE);
        seedView.setTextColor(Color.parseColor("#8a8a9a"));
        content.addView(seedView);

        ListView list = new ListView(this);
        ArrayAdapter<String> ad = new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_1, stationRows);
        list.setAdapter(ad);
        content.addView(list, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, (int) dp(320)));
        list.setOnItemClickListener((p, v, pos, id) -> {
            if (pos < stationIds.size()) {
                bg(() -> {
                    JSONObject r = jcall("queue_add", stationIds.get(pos));
                    runOnUiThread(() -> setStatus(r.optBoolean("ok", false)
                            ? "queued from the station"
                            : "queue failed: "
                                    + r.optString("error", "?")));
                });
            }
        });

        Button moreBtn = button("More tracks \u2192");
        moreBtn.setEnabled(false);
        content.addView(moreBtn);

        startBtn.setOnClickListener(v -> {
            final String kind =
                    kindSpin.getSelectedItem().toString();
            final String seed = seedInput.getText().toString().trim();
            if (seed.isEmpty()) {
                setStatus("name an artist, genre, or song first");
                return;
            }
            startBtn.setEnabled(false);
            moreBtn.setEnabled(false);
            setStatus("tuning the station\u2026");
            bg(() -> {
                try {
                    startStation(kind, seed);
                    final String seedLine = "seed: "
                            + stationObj.get("seed").toString()
                            + " \u00b7 " + stationObj.get("size").toString()
                            + " tracks in the pool \u2014 endless";
                    stationPos = 0;
                    final int n = appendStationTracks(10);
                    runOnUiThread(() -> {
                        seedView.setText(seedLine);
                        ad.notifyDataSetChanged();
                        setStatus(n > 0 ? "station live \u2014 tap a track "
                                + "to queue it" : "station is empty?!");
                        startBtn.setEnabled(true);
                        moreBtn.setEnabled(n > 0);
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> {
                        setStatus(stationErr(e));
                        startBtn.setEnabled(true);
                    });
                }
            });
        });

        moreBtn.setOnClickListener(v -> {
            moreBtn.setEnabled(false);
            bg(() -> {
                try {
                    final int n = appendStationTracks(10);
                    runOnUiThread(() -> {
                        ad.notifyDataSetChanged();
                        setStatus(n > 0 ? "station rolls on"
                                : "station pool exhausted?!");
                        moreBtn.setEnabled(true);
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> {
                        setStatus(stationErr(e));
                        moreBtn.setEnabled(true);
                    });
                }
            });
        });
    }

    /** Build the station from the bridge catalog (S-L1: catalog only). */
    private void startStation(String kind, String seed) throws Exception {
        JSONObject r = jcall("catalog");
        if (!r.optBoolean("ok", false)) {
            throw new IllegalStateException("couldn't read the catalog: "
                    + r.optString("error", "?"));
        }
        Python py = Python.getInstance();
        PyObject trackCls =
                py.getModule("levi.buzztunes.providers").get("Track");
        List<PyObject> pyTracks = new ArrayList<>();
        JSONArray ts = r.optJSONArray("tracks");
        for (int i = 0; i < ts.length(); i++) {
            JSONObject t = ts.optJSONObject(i);
            HashMap<String, Object> meta = new HashMap<>();
            JSONObject m = t.optJSONObject("meta");
            if (m != null) {
                Iterator<String> keys = m.keys();
                while (keys.hasNext()) {
                    String k = keys.next();
                    meta.put(k, m.optString(k));
                }
            }
            Object dur = t.isNull("duration") ? null
                    : (Object) Double.valueOf(t.optDouble("duration"));
            pyTracks.add(trackCls.call(
                    t.optString("id"), t.optString("title"),
                    t.optString("artist"), dur,
                    t.optString("provider"), t.optString("ref"), meta));
        }
        PyObject stations = py.getModule("levi.buzztunes.stations");
        stationObj = stations.callAttr("make_station", kind, seed, pyTracks);
        stationCatalog = pyTracks;
        stationIds.clear();
        stationRows.clear();
    }

    /** Append the next ``count`` station tracks to the list. S-L2/S-L4. */
    private int appendStationTracks(int count) {
        Python py = Python.getInstance();
        PyObject stations = py.getModule("levi.buzztunes.stations");
        List<PyObject> got = stations
                .callAttr("next_tracks", stationObj, stationCatalog,
                        count, stationPos)
                .asList();
        for (PyObject entry : got) {
            PyObject t = entry.get("track");
            stationIds.add(t.get("id").toString());
            stationRows.add(t.get("artist").toString() + " \u2014 "
                    + t.get("title").toString() + "\n"
                    + entry.get("reason").toString());
        }
        stationPos += got.size();
        return got.size();
    }

    private static String stationErr(Exception e) {
        String m = e.getMessage();
        if (m == null) return "the station couldn't start";
        int i = m.indexOf("StationError:");
        if (i >= 0) m = m.substring(i + "StationError:".length());
        return m.replace('\n', ' ').trim();
    }

    // ------------------------------------------------------------------
    // helpers
    // ------------------------------------------------------------------
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

    private JSONObject jcall(String fn, String... args) {
        try {
            com.chaquo.python.PyObject[] pyArgs =
                    new com.chaquo.python.PyObject[args.length];
            for (int i = 0; i < args.length; i++)
                pyArgs[i] = com.chaquo.python.PyObject.fromJava(args[i]);
            String out = bridge.callAttr(fn, (Object[]) pyArgs).toString();
            return new JSONObject(out);
        } catch (Exception e) {
            try {
                return new JSONObject("{\"ok\":false,\"error\":\""
                        + e.getMessage().replace("\"", "'") + "\"}");
            } catch (Exception e2) {
                return new JSONObject();
            }
        }
    }

    private void setStatus(String s) {
        statusView.setText(s);
    }

    private LinearLayout vbox() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        int p = (int) dp(8);
        l.setPadding(p, p, p, p);
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
        return t;
    }

    private TextView sectionLabel(String s) {
        TextView t = label(s.toUpperCase());
        t.setTextSize(11);
        t.setTextColor(Color.parseColor("#7c5cff"));
        t.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        t.setPadding(0, (int) dp(10), 0, (int) dp(4));
        return t;
    }

    private Button button(String s) {
        Button b = new Button(this);
        b.setText(s);
        b.setTextColor(Color.parseColor("#e8e8f0"));
        b.setBackgroundColor(Color.parseColor("#1a1a28"));
        return b;
    }

    private EditText input(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(Color.parseColor("#8a8a9a"));
        e.setTextColor(Color.parseColor("#e8e8f0"));
        e.setBackgroundColor(Color.parseColor("#0d0d14"));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        int m = (int) dp(4);
        lp.setMargins(0, m, 0, m);
        e.setLayoutParams(lp);
        return e;
    }

    private ArrayAdapter<String> darkAdapter(List<String> rows) {
        return new ArrayAdapter<String>(this,
                android.R.layout.simple_list_item_1, rows) {
            @Override
            public View getView(int position, View cv, ViewGroup parent) {
                View v = super.getView(position, cv, parent);
                ((TextView) v).setTextColor(
                        Color.parseColor("#e8e8f0"));
                v.setBackgroundColor(Color.parseColor("#0d0d14"));
                return v;
            }
        };
    }

    private ListView sized(ListView v, int dpH) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, (int) dp(dpH));
        v.setLayoutParams(lp);
        v.setBackgroundColor(Color.parseColor("#0d0d14"));
        return v;
    }
}
