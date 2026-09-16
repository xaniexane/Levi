package dev.levi.app

import android.os.Bundle
import android.view.MenuItem
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import dev.levi.app.databinding.ActivitySettingsBinding

/**
 * Server URL configuration. The URL is the address of the machine
 * serving the LEVI web client (see docs/ANDROID_APP.md).
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.title = getString(R.string.settings_title)

        binding.urlInput.setText(ServerConfig.getUrl(this))

        binding.saveButton.setOnClickListener {
            val raw = binding.urlInput.text.toString()
            if (ServerConfig.isInsecureHttp(raw)) {
                binding.urlLayout.error = getString(R.string.error_url_insecure)
                return@setOnClickListener
            }
            val normalized = ServerConfig.normalize(raw)
            if (normalized == null) {
                binding.urlLayout.error = getString(R.string.error_url_invalid)
                return@setOnClickListener
            }
            binding.urlLayout.error = null
            ServerConfig.setUrl(this, normalized)
            Toast.makeText(
                this,
                if (normalized.isEmpty()) getString(R.string.url_cleared)
                else getString(R.string.url_saved, normalized),
                Toast.LENGTH_SHORT,
            ).show()
            finish()
        }
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) {
            finish()
            return true
        }
        return super.onOptionsItemSelected(item)
    }
}
