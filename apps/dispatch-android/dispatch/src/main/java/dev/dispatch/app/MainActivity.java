package dev.dispatch.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;

/**
 * Dispatch on Android — the LEVI truck-dispatch board, on-device.
 *
 * Driver-first UX: big touch targets, glanceable week board, one-tap
 * lifecycle moves. Every mutation goes through the DispatcherTwin /
 * VerifierTwin pair and lands a receipt. Local-only: no network
 * permission is declared.
 *
 * Hard boundaries (surfaced, not buried):
 *   - This app is NOT an ELD and makes NO FMCSA/DOT compliance claim.
 *   - LEVI advises; the dispatcher decides. Nothing dispatches itself.
 */
public class MainActivity extends Activity {

    private com.chaquo.python.PyObject bridge;

    private LinearLayout root;
    private LinearLayout tabBar;
    private LinearLayout content;
    private TextView statusView;

    private int cBg, cPanel, cAccent, cGreen, cDanger, cText, cDim;

    private float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }

    // ------------------------------------------------------------------
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        cBg = Color.parseColor("#050508");
        cPanel = Color.parseColor("#0d0d14");
        cAccent = Color.parseColor("#ffb020");
        cGreen = Color.parseColor("#35d07f");
        cDanger = Color.parseColor("#ff5a5a");
        cText = Color.parseColor("#e8e8f0");
        cDim = Color.parseColor("#8a8a9a");

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        bridge = Python.getInstance().getModule("dispatch_bridge");

        File ws = new File(getFilesDir(), "dispatch_ws");
        call("set_workspace", ws.getAbsolutePath());
        JSONObject seed = call("seed_demo");
        String note = (seed.optBoolean("seeded", false)) ? "demo fleet seeded" : "board loaded";

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(cBg);

        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        content.setLayoutParams(cp);
        root.addView(content);

        statusView = text("", 13, cDim);
        statusView.setPadding((int) dp(16), (int) dp(6), (int) dp(16), (int) dp(4));
        root.addView(statusView);

        tabBar = new LinearLayout(this);
        tabBar.setOrientation(LinearLayout.HORIZONTAL);
        tabBar.setBackgroundColor(cPanel);
        tabBar.setPadding((int) dp(6), (int) dp(6), (int) dp(6), (int) dp(10));
        String[] tabs = {"BOARD", "LOADS", "+ LOAD", "FLEET", "LIMITS"};
        for (String t : tabs) {
            Button b = bigButton(t, cPanel, cAccent);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            lp.setMargins((int) dp(3), 0, (int) dp(3), 0);
            b.setLayoutParams(lp);
            final String tab = t;
            b.setOnClickListener(v -> showTab(tab));
            tabBar.addView(b);
        }
        root.addView(tabBar);

        setContentView(root);
        setStatus(note);
        showTab("BOARD");
    }

    // ------------------------------------------------------------------ ui kit
    private TextView text(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        return t;
    }

    private Button bigButton(String label, int bg, int fg) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(15);
        b.setTextColor(fg);
        b.setBackgroundColor(bg);
        b.setMinHeight((int) dp(56));
        b.setAllCaps(false);
        b.setPadding((int) dp(10), (int) dp(12), (int) dp(10), (int) dp(12));
        return b;
    }

    private EditText field(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setHintTextColor(cDim);
        e.setTextColor(cText);
        e.setTextSize(16);
        e.setBackgroundColor(cPanel);
        e.setPadding((int) dp(14), (int) dp(14), (int) dp(14), (int) dp(14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, (int) dp(10));
        e.setLayoutParams(lp);
        return e;
    }

    private ScrollView scrollOf(View v) {
        ScrollView s = new ScrollView(this);
        s.addView(v);
        return s;
    }

    private void setStatus(String s) {
        statusView.setText(s);
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    private void show(View v) {
        content.removeAllViews();
        content.addView(v);
    }

    // ------------------------------------------------------------------ bridge
    private JSONObject call(String fn, String... args) {
        try {
            Object[] oargs = new Object[args.length];
            for (int i = 0; i < args.length; i++) oargs[i] = args[i];
            String raw = bridge.callAttr(fn, oargs).toString();
            return new JSONObject(raw);
        } catch (Exception e) {
            JSONObject err = new JSONObject();
            try { err.put("ok", false); err.put("error", e.toString()); } catch (Exception ignored) {}
            return err;
        }
    }

    private boolean checkOk(JSONObject r, String action) {
        if (r.optBoolean("ok", false)) return true;
        String err = r.optString("error", "failed");
        setStatus(action + " — " + err);
        toast(err);
        return false;
    }

    private String mondayIso() {
        Calendar c = Calendar.getInstance();
        c.set(Calendar.DAY_OF_WEEK, Calendar.MONDAY);
        return String.format("%04d-%02d-%02d",
                c.get(Calendar.YEAR), c.get(Calendar.MONTH) + 1,
                c.get(Calendar.DAY_OF_MONTH));
    }

    // ------------------------------------------------------------------ tabs
    private void showTab(String tab) {
        switch (tab) {
            case "BOARD": showBoard(); break;
            case "LOADS": showLoads(); break;
            case "+ LOAD": showBookLoad(); break;
            case "FLEET": showFleet(); break;
            case "LIMITS": showLimits(); break;
        }
    }

    private void showBoard() {
        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setPadding((int) dp(16), (int) dp(16), (int) dp(16), (int) dp(16));

        TextView title = text("WEEK BOARD", 20, cAccent);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        lay.addView(title);

        JSONObject r = call("board_text", mondayIso());
        TextView board = text(r.optString("text", "—"), 12, cText);
        board.setTypeface(Typeface.MONOSPACE);
        board.setPadding(0, (int) dp(12), 0, (int) dp(12));
        lay.addView(board);

        JSONObject c = call("conflicts");
        JSONArray arr = c.optJSONArray("conflicts");
        if (arr != null && arr.length() > 0) {
            TextView warn = text("⚠ " + arr.length() + " scheduling conflict(s) — see LOADS", 15, cDanger);
            lay.addView(warn);
        } else {
            lay.addView(text("no scheduling conflicts", 14, cGreen));
        }

        TextView eld = text("Not an ELD. No FMCSA/DOT compliance claim.", 12, cDim);
        eld.setPadding(0, (int) dp(16), 0, 0);
        lay.addView(eld);

        Button refresh = bigButton("REFRESH", cPanel, cAccent);
        refresh.setOnClickListener(v -> showBoard());
        lay.addView(refresh);

        show(scrollOf(lay));
        setStatus("board — week of " + mondayIso());
    }

    private void showLoads() {
        JSONObject r = call("list_loads");
        if (!checkOk(r, "loads")) { showBoard(); return; }
        JSONArray loads = r.optJSONArray("loads");

        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setPadding((int) dp(12), (int) dp(12), (int) dp(12), (int) dp(12));

        TextView title = text("LOADS (" + (loads == null ? 0 : loads.length()) + ")", 20, cAccent);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding((int) dp(4), 0, (int) dp(4), (int) dp(10));
        lay.addView(title);

        ListView list = new ListView(this);
        List<String> rows = new ArrayList<>();
        final List<JSONObject> data = new ArrayList<>();
        if (loads != null) {
            for (int i = 0; i < loads.length(); i++) {
                JSONObject l = loads.optJSONObject(i);
                data.add(l);
                rows.add(l.optString("reference", "?") + "  ·  " + l.optString("status", "?")
                        + "\n" + l.optString("origin", "") + " → " + l.optString("destination", ""));
            }
        }
        ArrayAdapter<String> ad = new ArrayAdapter<>(this,
                android.R.layout.simple_list_item_2, android.R.id.text1, rows) {
            @Override
            public View getView(int position, View cv, ViewGroup parent) {
                View v = super.getView(position, cv, parent);
                TextView t1 = v.findViewById(android.R.id.text1);
                t1.setTextColor(cText);
                t1.setTextSize(17);
                t1.setMinHeight((int) dp(64));
                return v;
            }
        };
        list.setAdapter(ad);
        list.setOnItemClickListener((p, v, pos, id) -> showLoadDetail(data.get(pos)));
        lay.addView(list);
        show(lay);
        setStatus("loads — tap one to work it");
    }

    private void showLoadDetail(JSONObject load) {
        String id = load.optString("id");
        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setPadding((int) dp(16), (int) dp(16), (int) dp(16), (int) dp(16));

        TextView title = text(load.optString("reference", ""), 22, cText);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        lay.addView(title);
        lay.addView(text(load.optString("origin", "") + " → " + load.optString("destination", ""), 16, cDim));
        lay.addView(text("status: " + load.optString("status", "")
                + "   offer: " + load.optString("offer_state", ""), 15, cAccent));
        lay.addView(text("pickup " + load.optString("pickup_date", "—")
                + "   deliver " + load.optString("delivery_date", "—"), 14, cDim));
        int cents = load.optInt("rate_cents", 0);
        lay.addView(text(String.format("rate $%,.2f", cents / 100.0), 16, cGreen));

        // offer accept (needed before dispatch)
        if ("negotiating".equals(load.optString("offer_state", ""))) {
            Button accept = bigButton("ACCEPT OFFER @ $" + String.format("%,.2f", cents / 100.0), cGreen, Color.BLACK);
            accept.setOnClickListener(v -> {
                JSONObject rr = call("accept_offer", id, String.format("%.2f", cents / 100.0));
                if (checkOk(rr, "accept")) { setStatus("offer accepted — receipt #" + rr.optInt("receipt_seq")); reloadLoad(id); }
            });
            lay.addView(spaced(accept));
        }

        // lifecycle moves
        JSONObject moves = call("allowed_moves", id);
        JSONArray next = moves.optJSONArray("next");
        if (next != null) {
            for (int i = 0; i < next.length(); i++) {
                final String to = next.optString(i);
                Button b = bigButton(labelFor(to), cPanel, cAccent);
                b.setOnClickListener(v -> {
                    JSONObject rr = call("advance_load", id, to);
                    if (checkOk(rr, to)) { setStatus(moved + " → " + to + " — receipt #" + rr.optInt("receipt_seq")); reloadLoad(id); }
                });
                lay.addView(spaced(b));
            }
        }

        // driver + truck assignment (required before dispatch)
        TextView asTitle = text("ASSIGNMENT", 14, cDim);
        asTitle.setPadding(0, (int) dp(14), 0, (int) dp(6));
        lay.addView(asTitle);
        String curDrv = load.optString("driver_id", "");
        lay.addView(text(curDrv.isEmpty() ? "driver: — unassigned" : "driver: " + curDrv, 14,
                curDrv.isEmpty() ? cDanger : cGreen));
        Button assign = bigButton("ASSIGN DRIVER + TRUCK", cPanel, cAccent);
        assign.setOnClickListener(v -> pickDriver(id, null));
        lay.addView(spaced(assign));

        // checkcalls
        TextView ccTitle = text("CHECKCALLS", 14, cDim);
        ccTitle.setPadding(0, (int) dp(14), 0, (int) dp(6));
        lay.addView(ccTitle);
        String[][] ccs = {{"PICKED UP ✓", "picked_up"}, {"DEPART PICKUP", "depart_pickup"}};
        for (String[] cc : ccs) {
            Button b = bigButton(cc[0], cPanel, cText);
            b.setOnClickListener(v -> {
                JSONObject rr = call("checkcall", id, cc[1]);
                if (checkOk(rr, "checkcall")) setStatus("checkcall → " + rr.optString("sent_to", "?"));
                else setStatus("checkcall refused — " + rr.optString("error", ""));
            });
            lay.addView(spaced(b));
        }

        Button back = bigButton("← BACK", cPanel, cDim);
        back.setOnClickListener(v -> showLoads());
        lay.addView(spaced(back));

        show(scrollOf(lay));
    }

    private String moved = "moved";

    private String labelFor(String to) {
        switch (to) {
            case "dispatched": return "DISPATCH LOAD";
            case "picked_up": return "RECORD PICKUP";
            case "in_transit": return "RECORD DEPARTURE";
            case "delivered": return "RECORD DELIVERY";
            case "invoiced": return "RECORD INVOICE";
            case "cancelled": return "CANCEL LOAD";
            default: return to.toUpperCase();
        }
    }

    private View spaced(View v) {
        LinearLayout wrap = new LinearLayout(this);
        wrap.setPadding(0, (int) dp(5), 0, (int) dp(5));
        wrap.addView(v, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return wrap;
    }

    private void reloadLoad(String id) {
        JSONObject r = call("list_loads");
        JSONArray loads = r.optJSONArray("loads");
        if (loads != null) {
            for (int i = 0; i < loads.length(); i++) {
                JSONObject l = loads.optJSONObject(i);
                if (id.equals(l.optString("id"))) { showLoadDetail(l); return; }
            }
        }
        showLoads();
    }

    private void showBookLoad() {
        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setPadding((int) dp(16), (int) dp(16), (int) dp(16), (int) dp(16));

        TextView title = text("BOOK A LOAD", 20, cAccent);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, 0, 0, (int) dp(12));
        lay.addView(title);

        EditText ref = field("reference (e.g. LD-1042)");
        EditText origin = field("origin (e.g. Springfield, IL)");
        EditText dest = field("destination (e.g. Chicago, IL)");
        EditText pickup = field("pickup date (YYYY-MM-DD)");
        EditText delivery = field("delivery date (YYYY-MM-DD)");
        EditText rate = field("rate $ (e.g. 850)");
        rate.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        EditText notes = field("notes (optional)");
        lay.addView(ref); lay.addView(origin); lay.addView(dest);
        lay.addView(pickup); lay.addView(delivery); lay.addView(rate); lay.addView(notes);

        Button book = bigButton("BOOK LOAD", cAccent, Color.BLACK);
        book.setOnClickListener(v -> {
            JSONObject r = call("book_load",
                    ref.getText().toString(), origin.getText().toString(),
                    dest.getText().toString(), pickup.getText().toString(),
                    delivery.getText().toString(), rate.getText().toString(),
                    notes.getText().toString());
            if (checkOk(r, "book")) {
                setStatus("booked — receipt #" + r.optInt("receipt_seq"));
                toast("load booked");
                showLoads();
            }
        });
        lay.addView(spaced(book));
        show(scrollOf(lay));
        setStatus("book a load — twin pair countersigns");
    }

    private void showFleet() {
        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setPadding((int) dp(16), (int) dp(16), (int) dp(16), (int) dp(16));

        TextView dt = text("DRIVERS", 18, cAccent);
        dt.setTypeface(Typeface.DEFAULT_BOLD);
        lay.addView(dt);
        JSONObject dr = call("list_drivers");
        JSONArray drivers = dr.optJSONArray("drivers");
        if (drivers != null) for (int i = 0; i < drivers.length(); i++) {
            JSONObject d = drivers.optJSONObject(i);
            lay.addView(text("• " + d.optString("name", "?")
                    + (d.optString("home_base", "").isEmpty() ? "" : " — " + d.optString("home_base")), 16, cText));
        }
        EditText dName = field("driver name");
        EditText dPhone = field("phone (optional)");
        dPhone.setInputType(InputType.TYPE_CLASS_PHONE);
        EditText dHome = field("home base (optional)");
        Button addD = bigButton("ADD DRIVER", cPanel, cGreen);
        addD.setOnClickListener(v -> {
            JSONObject r = call("register_driver", dName.getText().toString(),
                    dPhone.getText().toString(), dHome.getText().toString());
            if (checkOk(r, "driver")) { setStatus("driver registered"); showFleet(); }
        });
        lay.addView(dName); lay.addView(dPhone); lay.addView(dHome); lay.addView(spaced(addD));

        TextView tt = text("TRUCKS", 18, cAccent);
        tt.setTypeface(Typeface.DEFAULT_BOLD);
        tt.setPadding(0, (int) dp(18), 0, 0);
        lay.addView(tt);
        JSONObject tr = call("list_trucks");
        JSONArray trucks = tr.optJSONArray("trucks");
        if (trucks != null) for (int i = 0; i < trucks.length(); i++) {
            JSONObject t = trucks.optJSONObject(i);
            lay.addView(text("• " + t.optString("unit_number", "?")
                    + " — " + t.optString("equipment", ""), 16, cText));
        }
        EditText tUnit = field("unit number (e.g. UNIT-02)");
        EditText tEquip = field("equipment (dry_van, reefer, flatbed)");
        Button addT = bigButton("ADD TRUCK", cPanel, cGreen);
        addT.setOnClickListener(v -> {
            JSONObject r = call("register_truck", tUnit.getText().toString(),
                    tEquip.getText().toString());
            if (checkOk(r, "truck")) { setStatus("truck registered"); showFleet(); }
        });
        lay.addView(tUnit); lay.addView(tEquip); lay.addView(spaced(addT));

        show(scrollOf(lay));
        setStatus("fleet — drivers & trucks");
    }

    private void pickDriver(final String loadId, final String truckId) {
        JSONObject r = call("list_drivers");
        final JSONArray drivers = r.optJSONArray("drivers");
        if (drivers == null || drivers.length() == 0) { toast("no drivers — add one in FLEET"); return; }
        String[] names = new String[drivers.length()];
        for (int i = 0; i < drivers.length(); i++) names[i] = drivers.optJSONObject(i).optString("name", "?");
        new AlertDialog.Builder(this)
                .setTitle("Pick driver")
                .setItems(names, (d, which) -> {
                    String did = drivers.optJSONObject(which).optString("id");
                    if (truckId == null) pickTruck(loadId, did);
                    else doAssign(loadId, did, truckId);
                })
                .setNegativeButton("cancel", null)
                .show();
    }

    private void pickTruck(final String loadId, final String driverId) {
        JSONObject r = call("list_trucks");
        final JSONArray trucks = r.optJSONArray("trucks");
        if (trucks == null || trucks.length() == 0) { toast("no trucks — add one in FLEET"); return; }
        String[] names = new String[trucks.length()];
        for (int i = 0; i < trucks.length(); i++) names[i] = trucks.optJSONObject(i).optString("unit_number", "?");
        new AlertDialog.Builder(this)
                .setTitle("Pick truck")
                .setItems(names, (d, which) -> {
                    String tid = trucks.optJSONObject(which).optString("id");
                    doAssign(loadId, driverId, tid);
                })
                .setNegativeButton("cancel", null)
                .show();
    }

    private void doAssign(String loadId, String driverId, String truckId) {
        JSONObject r = call("assign_load", loadId, driverId, truckId);
        if (checkOk(r, "assign")) {
            String fit = r.optString("schedule_fit", "");
            setStatus("assigned" + ("tight".equals(fit) ? " — TIGHT fit flagged" : ""));
            reloadLoad(loadId);
        }
    }

    private void showLimits() {
        JSONObject r = call("honest_limits");
        LinearLayout lay = new LinearLayout(this);
        lay.setOrientation(LinearLayout.VERTICAL);
        lay.setPadding((int) dp(16), (int) dp(16), (int) dp(16), (int) dp(16));

        TextView title = text("HONEST LIMITS", 20, cAccent);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, 0, 0, (int) dp(12));
        lay.addView(title);

        JSONArray lim = r.optJSONArray("limits");
        if (lim != null) for (int i = 0; i < lim.length(); i++) {
            TextView t = text("• " + lim.optString(i), 15, cText);
            t.setPadding(0, 0, 0, (int) dp(10));
            lay.addView(t);
        }
        TextView eld = text(r.optString("eld", ""), 15, cDanger);
        eld.setPadding(0, (int) dp(12), 0, 0);
        lay.addView(eld);

        show(scrollOf(lay));
        setStatus("honest limits — read before you rely");
    }
}
