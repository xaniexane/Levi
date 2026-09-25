package dev.cybrus.app;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

/**
 * UI-preview shell: a full-screen WebView over the self-contained
 * {@code cybrus-ui-preview.html} asset. Local-only — the manifest declares
 * no network permissions.
 *
 * <p>Honest scope: the bundled HTML runs mock data. No real vault crypto
 * exists in this build; this APK is a UI preview, not the product.
 */
public class MainActivity extends Activity {

    private static final String VOID = "#050508";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Dark window chrome to match the void theme.
        getWindow().setStatusBarColor(Color.parseColor(VOID));
        getWindow().setNavigationBarColor(Color.parseColor(VOID));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor(VOID));
        webView.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);

        // Keep every navigation inside the WebView — never kick out to a browser.
        webView.setWebViewClient(new WebViewClient());

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor(VOID));
        root.addView(webView);
        setContentView(root);

        if (savedInstanceState == null) {
            webView.loadUrl("file:///android_asset/cybrus-ui-preview.html");
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
