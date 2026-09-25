package com.cybrus.vyve.auth

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import com.cybrus.vyve.ui.MainActivity
import timber.log.Timber

/**
 * Handles the OAuth2 redirect (vyve://callback?code=...&state=...) declared
 * in the manifest.
 *
 * This activity does NOT exchange the code itself. It extracts the
 * authorization code (or error) from the redirect URI and forwards it to
 * [MainActivity] via [Intent.ACTION_VIEW], which owns the PKCE token
 * exchange against POST /oauth/token. It then finishes immediately.
 */
class OAuthCallbackActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val uri: Uri? = intent?.data
        val code = uri?.getQueryParameter("code")
        val state = uri?.getQueryParameter("state")
        val error = uri?.getQueryParameter("error")

        when {
            error != null -> Timber.w("OAuth redirect error: %s", error)
            code != null -> Timber.i("OAuth authorization code received (state=%s)", state)
            else -> Timber.w("OAuth callback invoked without code or error")
        }

        // Hand the result back to the main task; singleTask launch mode
        // delivers it to MainActivity.onNewIntent().
        startActivity(
            Intent(this, MainActivity::class.java).apply {
                action = Intent.ACTION_VIEW
                data = uri
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            },
        )
        finish()
    }
}
