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

        binding.webView.webViewClient = object : WebViewClient() {
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
