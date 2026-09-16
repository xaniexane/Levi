package dev.levi.app

import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import dev.levi.app.databinding.ActivityMainBinding
import dev.levi.app.settings.AppLock

/**
 * WebView shell hosting the LEVI web client (the Talk UI from web/).
 *
 * No server URL configured -> empty state with a button to Settings.
 * WebView keeps navigation in-app; the back button walks WebView history.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var currentUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // App lock gates the whole app. If the lock screen shows, this
        // activity finishes; reopening the app lands past the lock.
        if (AppLock.requireUnlock(this)) {
            finish()
            return
        }
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)

        binding.settingsButton.setOnClickListener { openSettings() }
        binding.retryButton.setOnClickListener { loadConfigured() }

        val webSettings: WebSettings = binding.webView.settings
        webSettings.javaScriptEnabled = true
        webSettings.domStorageEnabled = true // the web UI persists theme/persona in localStorage
        webSettings.mediaPlaybackRequiresUserGesture = false
        webSettings.loadWithOverviewMode = true
        webSettings.useWideViewPort = true
        // Hardening: the WebView only ever shows the user's configured
        // server, so it needs no local file/content access at all.
        webSettings.allowFileAccess = false
        webSettings.allowContentAccess = false

        binding.webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?,
            ): Boolean {
                val uri = request?.url ?: return false
                val target = uri.toString()
                // Stay in-app only for the configured server. External
                // https links (docs, etc.) open in the user's browser;
                // anything else (custom schemes, file://) is blocked.
                return if (isConfiguredHost(target)) {
                    false // let the WebView load it
                } else if (target.startsWith("https://")) {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                    true
                } else {
                    true // swallow: no file://, intent://, or other schemes
                }
            }
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                binding.progress.visibility = View.VISIBLE
                binding.errorView.visibility = View.GONE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                binding.progress.visibility = View.GONE
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?,
            ) {
                if (request?.isForMainFrame == true) {
                    binding.progress.visibility = View.GONE
                    binding.webView.visibility = View.GONE
                    binding.errorView.visibility = View.VISIBLE
                    binding.errorText.text = getString(
                        R.string.error_load,
                        error?.description ?: getString(R.string.error_unknown),
                    )
                }
            }
        }
        binding.webView.webChromeClient = WebChromeClient()
    }

    override fun onResume() {
        super.onResume()
        // Pick up URL changes made in Settings.
        loadConfigured()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_settings -> {
                openSettings()
                true
            }
            R.id.action_reload -> {
                binding.webView.reload()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    override fun onBackPressed() {
        // Kept as a plain override (not the dispatcher) so the WebView
        // history check stays in one obvious place.
        if (binding.webView.visibility == View.VISIBLE && binding.webView.canGoBack()) {
            binding.webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        binding.webView.destroy()
        super.onDestroy()
    }

    private fun openSettings() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    /**
     * True when [url] targets the configured LEVI server (same scheme +
     * host). Navigation anywhere else is not the app's content.
     */
    private fun isConfiguredHost(url: String): Boolean {
        val configured = currentUrl ?: ServerConfig.getUrl(this)
        if (configured.isBlank()) return false
        fun hostOf(u: String): String =
            u.substringAfter("://").substringBefore('/').lowercase()
        fun schemeOf(u: String): String =
            u.substringBefore("://").lowercase()
        return schemeOf(url) == schemeOf(configured) &&
            hostOf(url) == hostOf(configured)
    }

    private fun loadConfigured() {
        val url = ServerConfig.getUrl(this)
        if (url.isBlank()) {
            // Empty state.
            currentUrl = null
            binding.webView.visibility = View.GONE
            binding.errorView.visibility = View.GONE
            binding.emptyView.visibility = View.VISIBLE
            return
        }
        binding.emptyView.visibility = View.GONE
        binding.errorView.visibility = View.GONE
        binding.webView.visibility = View.VISIBLE
        if (url != currentUrl) {
            currentUrl = url
            binding.webView.loadUrl(url)
        }
    }
}
