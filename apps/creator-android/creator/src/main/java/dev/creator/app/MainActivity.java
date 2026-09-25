package dev.creator.app;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
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
 * LEVI Platform on Android — Chauncey's entire project in one mega APK, on-device
 * via Chaquopy. One stable application ID; updates install over it in place.
 *
 * Sections (each backed by the real engine in levi_bridge.py, or an honest gate):
 *   Creators / Content / Dating / Chats / Safety / Pricing — AI track (default).
 *   SI / Listings / Plaiground — adult track, gate-locked: the Plaiground adult
 *     gate is OFF by default, minors hard-locked out. The PIN ceremony runs
 *     through the real gate (set_pin / enable_adult_mode / disable_adult_mode);
 *     the gate proves local opt-in, NOT verified age. No explicit content ships
 *     in the app, ever.
 *   Money — paper-only accounting; tier cuts read live from the confirmed
 *     delegated table (free 12 / pro 9 / hybrid 6 / elite 3, all under the 20%
 *     competitor ceiling). Cybrus fails closed: no live rail, no movement.
 *   Hicomb — the house code editor, driven by the real buffer engine.
 *   Legion — "for we are many": the umbrella roster over every agent family.
 *   Operators — Cybrus status, alerter laws, alerts inbox, DemandPulse status.
 *   Demand / Daemons / Organs / Neighborhood / Dispatch / Media — live surfaces.
 *   Systems — the full inventory map: all 200 core modules probed on-device,
 *     importable or honest about the gate.
 *
 * Local-only: no network permission is declared. Money never moves on-device.
 */
public class MainActivity extends Activity {

    private com.chaquo.python.PyObject bridge;

    private File workspace;
    private TextView statusView;
    private TextView gateView;
    private LinearLayout tabBar;
    private LinearLayout content;
    private final List<Button> tabButtons = new ArrayList<>();

    private static final String[] TABS = {
            "Creators", "Content", "Dating", "Chats", "Safety", "Pricing", "SI",
            "Listings", "Money", "Hicomb", "Legion", "Operators", "Demand",
            "Daemons", "Organs", "Neighborhood", "Dispatch", "Media",
            "Plaiground", "Systems"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        bridge = Python.getInstance().getModule("levi_bridge");

        workspace = new File(getFilesDir(), "levi-platform");
        bg(() -> {
            bridge.callAttr("set_workspace", workspace.getAbsolutePath());
            bridge.callAttr("seed_workspace");
            runOnUiThread(this::refreshGate);
        });

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);

        gateView = new TextView(this);
        gateView.setTextSize(13);
        root.addView(gateView);

        statusView = new TextView(this);
        statusView.setTextSize(13);
        root.addView(statusView);

        HorizontalScrollView tabScroll = new HorizontalScrollView(this);
        tabScroll.setHorizontalScrollBarEnabled(false);
        tabBar = new LinearLayout(this);
        tabBar.setOrientation(LinearLayout.HORIZONTAL);
        for (String t : TABS) {
            Button b = new Button(this);
            b.setText(t);
            b.setOnClickListener(v -> showTab(t));
            tabBar.addView(b);
            tabButtons.add(b);
        }
        tabScroll.addView(tabBar);
        root.addView(tabScroll);

        ScrollView scroll = new ScrollView(this);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(content);
        root.addView(scroll);

        setContentView(root);
        showTab("Creators");
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    private void bg(Runnable r) {
        new Thread(r).start();
    }

    private void setStatus(String s) {
        runOnUiThread(() -> statusView.setText(s));
    }

    private void refreshGate() {
        bg(() -> {
            try {
                String json = bridge.callAttr("adult_gate_status").toString();
                JSONObject o = new JSONObject(json);
                JSONObject st = o.optJSONObject("status");
                boolean enabled = st != null && st.optBoolean("enabled", false);
                runOnUiThread(() -> gateView.setText(
                        enabled ? "adult gate: ON (SI track open)"
                                : "adult gate: OFF — SI track locked (AI track active)"));
            } catch (Exception e) {
                runOnUiThread(() -> gateView.setText("adult gate: unknown"));
            }
        });
    }

    // ---------- small ui helpers ----------

    private EditText input(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        content.addView(e);
        return e;
    }

    private Button action(String label, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(label);
        b.setOnClickListener(l);
        content.addView(b);
        return b;
    }

    private TextView out() {
        TextView t = new TextView(this);
        t.setTextSize(12);
        content.addView(t);
        return t;
    }

    private TextView blurb(String text) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(12);
        content.addView(t);
        return t;
    }

    private void showTab(String tab) {
        content.removeAllViews();
        for (Button b : tabButtons) {
            b.setEnabled(!b.getText().toString().equals(tab));
        }
        switch (tab) {
            case "Creators": tabCreators(); break;
            case "Content": tabContent(); break;
            case "Dating": tabDating(); break;
            case "Chats": tabChats(); break;
            case "Safety": tabSafety(); break;
            case "Pricing": tabPricing(); break;
            case "SI": tabSI(); break;
            case "Listings": tabListings(); break;
            case "Money": tabMoney(); break;
            case "Hicomb": tabHicomb(); break;
            case "Legion": tabLegion(); break;
            case "Operators": tabOperators(); break;
            case "Demand": tabDemand(); break;
            case "Daemons": tabDaemons(); break;
            case "Organs": tabOrgans(); break;
            case "Neighborhood": tabNeighborhood(); break;
            case "Dispatch": tabDispatch(); break;
            case "Media": tabMedia(); break;
            case "Plaiground": tabPlaiground(); break;
            case "Systems": tabSystems(); break;
        }
    }

    private void showJson(TextView t, String json) {
        try {
            JSONObject o = new JSONObject(json);
            if (!o.optBoolean("ok", false)) {
                t.setText("not ok: " + o.optString("error"));
                return;
            }
            t.setText(o.toString(1));
        } catch (Exception e) {
            t.setText("parse error: " + e.getMessage() + "\n" + json);
        }
    }

    /**
     * Generic section renderer. Each action is {button label, bridge verb,
     * input hint 1, input hint 2, ...}. Zero-input actions are status buttons.
     */
    private void tabSection(String note, String[][] actions) {
        if (note != null && !note.isEmpty()) blurb(note);
        TextView out = out();
        for (String[] a : actions) {
            final String verb = a[1];
            List<EditText> inputs = new ArrayList<>();
            for (int i = 2; i < a.length; i++) inputs.add(input(a[i]));
            action(a[0], v -> bg(() -> {
                try {
                    Object[] args = new Object[inputs.size()];
                    for (int i = 0; i < inputs.size(); i++) {
                        args[i] = inputs.get(i).getText().toString();
                    }
                    String json = bridge.callAttr(verb, args).toString();
                    String f = json;
                    runOnUiThread(() -> showJson(out, f));
                } catch (Exception e) {
                    setStatus("error: " + e.getMessage());
                }
            }));
        }
    }

    // ---------- the original seven ----------

    private void tabCreators() {
        TextView out = out();
        // list on open
        bg(() -> {
            try {
                String json = bridge.callAttr("ai_list_creators").toString();
                runOnUiThread(() -> showJson(out, json));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        });

        EditText handle = input("handle (3-24, a-z 0-9 _)");
        EditText name = input("display name");
        EditText bio = input("bio");
        EditText category = input("category");
        action("Create creator", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_create_creator",
                        handle.getText().toString(), name.getText().toString(),
                        bio.getText().toString(), category.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));

        EditText tierName = input("tier name");
        EditText tierPrice = input("price in cents (e.g. 499)");
        action("List tiers for handle above", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_list_tiers",
                        handle.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("Add tier", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_add_tier",
                        handle.getText().toString(), tierName.getText().toString(),
                        tierPrice.getText().toString().isEmpty() ? "0" : tierPrice.getText().toString(),
                        "[]").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));

        EditText subHandle = input("subscribe: creator handle");
        EditText subTier = input("tier id");
        EditText subUser = input("subscriber id");
        action("Subscribe (paper-only)", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_subscribe",
                        subHandle.getText().toString(), subTier.getText().toString(),
                        subUser.getText().toString(), "keeper").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));

        EditText dropTitle = input("drop title");
        EditText dropBody = input("drop body");
        action("Post drop", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_post_drop",
                        handle.getText().toString(), dropTitle.getText().toString(),
                        dropBody.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabContent() {
        TextView out = out();
        EditText creatorId = input("creator id (from Creators tab)");
        EditText title = input("title");
        EditText desc = input("description");
        EditText kind = input("kind: post | photo | video | audio");
        action("Publish PUBLIC (AI track)", v -> bg(() -> {
            try {
                String json = bridge.callAttr("publish_content",
                        creatorId.getText().toString(), title.getText().toString(),
                        desc.getText().toString(),
                        kind.getText().toString().isEmpty() ? "post" : kind.getText().toString(),
                        "ai", "{\"public\": true}").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText viewer = input("viewer id");
        action("List for viewer", v -> bg(() -> {
            try {
                String json = bridge.callAttr("list_for_viewer",
                        creatorId.getText().toString(), viewer.getText().toString(), "ai").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText contentId = input("content id");
        action("Revoke", v -> bg(() -> {
            try {
                String json = bridge.callAttr("revoke_content",
                        contentId.getText().toString(), creatorId.getText().toString(), "ai").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText subId = input("subscriber id (for grant)");
        action("Grant PPV access", v -> bg(() -> {
            try {
                String json = bridge.callAttr("grant_content",
                        contentId.getText().toString(), creatorId.getText().toString(),
                        subId.getText().toString(), "ai").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabDating() {
        TextView out = out();
        EditText handle = input("handle");
        EditText name = input("display name");
        EditText bio = input("bio");
        EditText interests = input("interests (comma separated)");
        action("Create dating profile", v -> bg(() -> {
            try {
                String[] parts = interests.getText().toString().split(",");
                JSONArray arr = new JSONArray();
                for (String p : parts) {
                    if (!p.trim().isEmpty()) arr.put(p.trim());
                }
                String json = bridge.callAttr("ai_dating_create_profile",
                        handle.getText().toString(), name.getText().toString(),
                        bio.getText().toString(), arr.toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("Find matches", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_dating_find_matches",
                        handle.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText to = input("message to (handle)");
        EditText body = input("message body");
        action("Send message", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_dating_message",
                        handle.getText().toString(), to.getText().toString(),
                        body.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("Inbox", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_dating_inbox",
                        handle.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabChats() {
        TextView out = out();
        EditText creatorHandle = input("creator handle");
        EditText otherId = input("other user id");
        action("Create chat", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_create_chat",
                        creatorHandle.getText().toString(), otherId.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText chatId = input("chat id");
        EditText sender = input("sender id");
        EditText body = input("message");
        action("Send", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_send_chat_message",
                        chatId.getText().toString(), sender.getText().toString(),
                        body.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("Thread", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_chat_thread",
                        chatId.getText().toString(), sender.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("My chats", v -> bg(() -> {
            try {
                String json = bridge.callAttr("ai_list_chats",
                        sender.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabSafety() {
        blurb("Meetup safety: everything OFF by default. Create a plan, check in; "
                + "silence past the deadline fires one sealed escalation to YOUR chosen contacts.");
        TextView out = out();
        EditText userId = input("your user id");
        EditText cName = input("trusted contact name");
        EditText cRef = input("trusted contact ref");
        action("Add trusted contact", v -> bg(() -> {
            try {
                String json = bridge.callAttr("safety_add_contact",
                        userId.getText().toString(), cName.getText().toString(),
                        cRef.getText().toString(), "ai").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText who = input("who are you meeting");
        EditText where = input("where");
        EditText when = input("when (ISO, e.g. 2026-09-23T19:00:00)");
        EditText minutes = input("check-in every N minutes");
        action("Create plan", v -> bg(() -> {
            try {
                String json = bridge.callAttr("safety_create_plan",
                        userId.getText().toString(), who.getText().toString(),
                        where.getText().toString(), when.getText().toString(),
                        minutes.getText().toString().isEmpty() ? "30" : minutes.getText().toString(),
                        "[]", "ai", "").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        EditText planId = input("plan id");
        action("Check in", v -> bg(() -> {
            try {
                String json = bridge.callAttr("safety_check_in",
                        planId.getText().toString(), userId.getText().toString(), "ai").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("End plan", v -> bg(() -> {
            try {
                String json = bridge.callAttr("safety_end_plan",
                        planId.getText().toString(), userId.getText().toString(), "ai").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabPricing() {
        TextView out = out();
        bg(() -> {
            try {
                String json = bridge.callAttr("pricing_tables").toString();
                runOnUiThread(() -> showJson(out, json));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        });
        EditText amount = input("amount in cents");
        action("Platform fee / creator split", v -> bg(() -> {
            try {
                String json = bridge.callAttr("pricing_split",
                        amount.getText().toString().isEmpty() ? "0" : amount.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("Suggested tiers (creator service)", v -> bg(() -> {
            try {
                String json = bridge.callAttr("pricing_suggested_tiers", "creator").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabSI() {
        blurb("SI track — adult dating + creator platform. Gate-locked: the adult "
                + "gate is OFF by default and minors are hard-locked out. Use the "
                + "Plaiground tab's PIN ceremony to enable it deliberately; disabling "
                + "is always allowed and needs no PIN.");
        tabSection(null, new String[][]{
                {"Try: list SI profiles (locked until gate opens)", "si_list_profiles"},
        });
        TextView out = out();
        EditText handle = input("handle");
        EditText name = input("display name");
        EditText bio = input("bio");
        action("Try: create SI profile", v -> bg(() -> {
            try {
                String json = bridge.callAttr("si_create_profile",
                        handle.getText().toString(), name.getText().toString(),
                        bio.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    // ---------- the new thirteen ----------

    private void tabListings() {
        tabSection("Skip-the-Games-style adult classifieds: post a price, sealed "
                + "messaging, nothing leaks beyond your authorization. Gate-locked "
                + "behind the Plaiground adult gate (default OFF).",
                new String[][]{
                        {"Search listings", "si_search_listings", "query"},
                        {"Post listing", "si_post_listing",
                                "poster id", "headline", "seeking", "terms"},
                        {"Respond (reveal: true/false)", "si_respond_listing",
                                "listing id", "responder id", "message", "reveal identity? true/false"},
                        {"Deactivate listing", "si_deactivate_listing", "listing id"},
                });
    }

    private void tabMoney() {
        tabSection("Paper-only accounting. Every sale splits by the live delegated "
                + "tier table (free 12 / pro 9 / hybrid 6 / elite 3 — all under the "
                + "20% competitor ceiling). No live rail exists: Cybrus fails closed, "
                + "subscriptions record as pending_payment, nothing moves.",
                new String[][]{
                        {"Tier table (live)", "money_tier_table"},
                        {"Cut calculator", "money_tier_cut",
                                "amount in cents", "tier: free/pro/hybrid/elite"},
                        {"Payout link", "money_payout_link",
                                "plugin (cashapp)", "handle", "amount in cents"},
                });
    }

    private void tabHicomb() {
        blurb("Hicomb — the house code editor. Open, edit, and save text files in "
                + "the on-device workspace, driven by the real Hicomb buffer engine "
                + "(undo/redo, large-file awareness). Offline, stdlib-only.");
        TextView out = out();
        action("Status", v -> bg(() -> {
            try {
                String json = bridge.callAttr("hicomb_status").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("List files", v -> bg(() -> {
            try {
                String json = bridge.callAttr("hicomb_list_files", "").toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));

        EditText path = input("file path (e.g. notes/todo.md)");
        EditText editor = new EditText(this);
        editor.setHint("file contents");
        editor.setMinLines(12);
        editor.setGravity(Gravity.TOP);
        editor.setTypeface(android.graphics.Typeface.MONOSPACE);
        content.addView(editor);

        action("Open", v -> bg(() -> {
            try {
                String json = bridge.callAttr("hicomb_read",
                        path.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> {
                    try {
                        JSONObject o = new JSONObject(f);
                        if (o.optBoolean("ok", false)) {
                            editor.setText(o.optString("text", ""));
                        }
                        showJson(out, f);
                    } catch (Exception e) {
                        out.setText("parse error: " + e.getMessage());
                    }
                });
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
        action("Save", v -> bg(() -> {
            try {
                String json = bridge.callAttr("hicomb_write",
                        path.getText().toString(), editor.getText().toString()).toString();
                String f = json;
                runOnUiThread(() -> showJson(out, f));
            } catch (Exception e) {
                setStatus("error: " + e.getMessage());
            }
        }));
    }

    private void tabLegion() {
        tabSection("Legion — \"for we are many\": the umbrella over every agent "
                + "family. One face the customer talks to, the legion behind it. "
                + "Money paths are paper-only (Cybrus fail-closed).",
                new String[][]{
                        {"Legion status", "legion_status"},
                        {"Specialist packs", "legion_packs"},
                        {"Operators + hive", "legion_operators"},
                });
    }

    private void tabOperators() {
        tabSection("Operator command view: what Cybrus sees, what the alerter "
                + "is allowed to send, what's in the alerts inbox, and what "
                + "DemandPulse is sensing.",
                new String[][]{
                        {"Cybrus status", "ops_cybrus_status"},
                        {"Alerter laws", "ops_alerter_laws"},
                        {"Alerts inbox", "ops_alerts_inbox"},
                        {"DemandPulse status", "ops_demand_status"},
                });
    }

    private void tabDemand() {
        tabSection("DemandPulse — the sensing engine. Inbound only: it reads "
                + "signals and scores them as hypotheses. It never posts, "
                + "publishes, replies, or acts.",
                new String[][]{
                        {"DemandPulse status", "ops_demand_status"},
                        {"Probe the demand engine", "system_detail", "system name (demand)"},
                });
    }

    private void tabDaemons() {
        tabSection("Daemon colony — the always-on background workers. Each one "
                + "reports whether it imports cleanly on this device.",
                new String[][]{
                        {"Daemon colony roster", "daemon_colony"},
                });
    }

    private void tabOrgans() {
        tabSection("Organs — the body systems of Levi, one registry. Probes the "
                + "live organ registry on this device.",
                new String[][]{
                        {"Probe the organ registry", "system_detail", "system name (organs)"},
                });
    }

    private void tabNeighborhood() {
        tabSection("Neighborhood / NeighborOS — the local layer. NeighborPay and "
                + "live money stay deferred (business/legal call); everything "
                + "here is paper and records.",
                new String[][]{
                        {"NeighborOS status", "hood_status"},
                        {"Neighbor nudges", "hood_nudges"},
                        {"Post a job", "hood_post_job", "title", "detail", "owner id"},
                });
    }

    private void tabDispatch() {
        tabSection("Dispatch — transportation. HOS co-pilot checks your plan "
                + "against hours-of-service clocks (fixture clock unless wired "
                + "to a real ELD); refusal rules screen requests; the load "
                + "shortlist needs real load offers to rank.",
                new String[][]{
                        {"HOS check", "dispatch_hos_check",
                                "drive hours planned", "on-duty hours planned"},
                        {"Refusal check", "dispatch_refusal_check", "request text"},
                        {"Load shortlist (what it needs)", "dispatch_shortlist_example"},
                });
    }

    private void tabMedia() {
        tabSection("Media — the shared media layer under listings, creators, "
                + "and chats. Private media is per-tier gated with per-subscriber "
                + "grants (see Content); sealed at rest on the SI track.",
                new String[][]{
                        {"Probe the media layer", "system_detail", "system name (media)"},
                });
    }

    private void tabPlaiground() {
        tabSection("Plaiground — the gate over everything adult. Adult/SI defaults "
                + "OFF. PIN required to enable (stored hashed, never plaintext); "
                + "disabling always works and needs no PIN; minors hard-locked out. "
                + "Honest law: this gate proves affirmative local opt-in on this "
                + "device — it is NOT verified age.",
                new String[][]{
                        {"Gate status", "adult_gate_status"},
                        {"Has PIN?", "plaiground_has_pin"},
                        {"Set PIN", "plaiground_set_pin", "new PIN"},
                        {"Enable adult mode", "plaiground_enable",
                                "confirmation phrase", "PIN"},
                        {"Disable adult mode", "plaiground_disable"},
                });
        bg(this::refreshGate);
    }

    private void tabSystems() {
        tabSection("The whole map: every one of the 200 core modules, probed live "
                + "on this device — importable or honest about the gate. Dynasty "
                + "never ships (eyes-only); the brain's weights and the knowledge "
                + "corpus are not on-device.",
                new String[][]{
                        {"Probe all 200 systems", "systems_status"},
                        {"Probe one system", "system_detail", "system name"},
                });
    }
}
