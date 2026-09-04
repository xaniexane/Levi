package com.cybrus.vyve.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Button
import androidx.compose.material.Text
import androidx.compose.material.Surface
import androidx.compose.material.SurfaceDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.setContent

import com.cybrus.vyve.data.DatabaseHelper
import com.cybrus.vyve.net.ApiService
import com.cybrus.vyve.net.ApiService.Companion.createApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@Composable
fun VYVEHomeScreen(user: User? = null): Unit {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.sp)
    ) {
        Surface(
            modifier = Modifier
                .background(Color(0xFF161B22)
                .contentAlignment(SurfaceDefaults.ContentAlignment.Center)
        ) {
            Text(
                "VYVE Messenger — Private by Default",
                style = MaterialTheme.typography.headline
            )
            Button(
                onClick = { /* TODO: call OAuth flow */ }
                label = "Log In with Cybrus",
                modifier = Modifier.padding(16.sp),
                colors = MaterialTheme.buttonColors
            )
        }
    }
}

class MainActivity : ComponentActivity() {
    private val database = DatabaseHelper(this)
    private val apiService = createApiClient("https://api.vyve.local/v1")
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent({
            VYVEHomeScreen()
        }
        )
    }

    /**
     * Stub — replace with proper OAuth flow in production
     */
    private fun createApiClient(baseUrl: String): ApiService {
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
