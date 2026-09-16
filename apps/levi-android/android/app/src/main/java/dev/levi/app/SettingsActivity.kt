package dev.levi.app

import android.os.Bundle
import android.view.MenuItem
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import dev.levi.app.databinding.ActivitySettingsBinding
import dev.levi.app.settings.AppLock
import dev.levi.app.settings.SettingsHomeFragment

/**
 * Host for the LEVI settings pages. [SettingsHomeFragment] is the root;
 * every row pushes a page with [open]. Back walks the page stack.
 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // App lock gates the whole settings surface.
        if (AppLock.requireUnlock(this)) {
            finish()
            return
        }
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        if (savedInstanceState == null) {
            supportFragmentManager.beginTransaction()
                .replace(R.id.settings_container, SettingsHomeFragment())
                .commit()
        }
        supportFragmentManager.addOnBackStackChangedListener { updateTitle() }
        updateTitle()
    }

    /** Push a settings page onto the stack. */
    fun open(fragment: Fragment, title: String) {
        supportFragmentManager.beginTransaction()
            .replace(R.id.settings_container, fragment)
            .addToBackStack(title)
            .commit()
    }

    private fun updateTitle() {
        val count = supportFragmentManager.backStackEntryCount
        supportActionBar?.title =
            if (count == 0) getString(R.string.settings_title)
            else supportFragmentManager.getBackStackEntryAt(count - 1).name
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == android.R.id.home) {
            if (supportFragmentManager.backStackEntryCount > 0) {
                supportFragmentManager.popBackStack()
            } else {
                finish()
            }
            return true
        }
        return super.onOptionsItemSelected(item)
    }
}
