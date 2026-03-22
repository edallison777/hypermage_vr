package com.hypermage.vrtest

import android.os.Bundle
import android.text.Spannable
import android.text.SpannableString
import android.text.style.ForegroundColorSpan
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.hypermage.vrtest.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val client = ApiClient()
    private val ts = SimpleDateFormat("HH:mm:ss.SSS", Locale.UK)
    private var lastSessionId: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnSignUp.setOnClickListener { launch { doSignUp() } }
        binding.btnConfirm.setOnClickListener { launch { doConfirm() } }
        binding.btnLogin.setOnClickListener { launch { doLogin() } }
        binding.btnHealth.setOnClickListener { launch { doHealth() } }
        binding.btnCreateSession.setOnClickListener { launch { doCreateSession() } }
        binding.btnGetSession.setOnClickListener { launch { doGetSession() } }
        binding.btnFullFlow.setOnClickListener { launch { doFullFlow() } }
        binding.btnClear.setOnClickListener { binding.logView.text = "" }

        logInfo("Hypermage VR test harness ready.")
        logDim("Steps: Sign Up → Confirm → Login → Full Flow")
    }

    // ── Actions ───────────────────────────────────────────────────────────────

    private suspend fun doSignUp() {
        val u = binding.etUsername.text.toString().trim()
        val p = binding.etPassword.text.toString()
        if (u.isEmpty() || p.isEmpty()) { logErr("Enter username and password"); return }
        logInfo("Signing up $u…")
        val r = withContext(Dispatchers.IO) { client.signUp(u, p) }
        if (r.ok) logOk("✓ Sign up OK — check email for confirmation code")
        else {
            val type = r.body.optString("__type", "")
            if (type.contains("UsernameExists")) logWarn("User already exists — proceed to Login")
            else logErr("✗ Sign up failed: ${r.body.optString("message", r.body.toString())}")
        }
    }

    private suspend fun doConfirm() {
        val u = binding.etUsername.text.toString().trim()
        val c = binding.etConfirmCode.text.toString().trim()
        if (u.isEmpty() || c.isEmpty()) { logErr("Enter username and confirmation code"); return }
        logInfo("Confirming $u with code $c…")
        val r = withContext(Dispatchers.IO) { client.confirmSignUp(u, c) }
        if (r.ok) logOk("✓ Account confirmed — you can now Login")
        else logErr("✗ Confirm failed: ${r.body.optString("message", r.body.toString())}")
    }

    private suspend fun doLogin() {
        val u = binding.etUsername.text.toString().trim()
        val p = binding.etPassword.text.toString()
        if (u.isEmpty() || p.isEmpty()) { logErr("Enter username and password"); return }
        logInfo("Authenticating $u…")
        val r = withContext(Dispatchers.IO) { client.login(u, p) }
        if (r.ok) {
            val tokenSnippet = client.idToken?.take(40) ?: "?"
            logOk("✓ Login OK — token: ${tokenSnippet}…")
            binding.tvTokenHint.visibility = View.VISIBLE
        } else {
            val msg = r.body.optString("message", r.body.toString())
            if (msg.contains("USER_PASSWORD_AUTH")) {
                logErr("✗ USER_PASSWORD_AUTH not enabled on app client")
                logWarn("  Fix: Cognito Console → User Pools → App clients → enable USER_PASSWORD_AUTH")
            } else {
                logErr("✗ Login failed: $msg")
            }
        }
    }

    private suspend fun doHealth() {
        logInfo("Health check…")
        val r = withContext(Dispatchers.IO) { client.healthCheck() }
        if (r.ok) logOk("✓ Health OK (${r.status}): ${r.body}")
        else logErr("✗ Health ${r.status}: ${r.body}")
    }

    private suspend fun doCreateSession() {
        if (client.idToken == null) { logWarn("Login first"); return }
        val playerId = "quest3-${System.currentTimeMillis()}"
        logInfo("Creating session for $playerId…")
        val r = withContext(Dispatchers.IO) { client.createSession(playerId) }
        if (r.ok) {
            lastSessionId = r.body.optString("sessionId").ifEmpty {
                r.body.optString("id")
            }
            logOk("✓ Session created (${r.status}) — sessionId=$lastSessionId")
            logDim("  ${r.body}")
        } else {
            logErr("✗ Create session ${r.status}: ${r.body}")
        }
    }

    private suspend fun doGetSession() {
        val sid = lastSessionId ?: run { logWarn("Create a session first"); return }
        logInfo("Getting session $sid…")
        val r = withContext(Dispatchers.IO) { client.getSession(sid) }
        if (r.ok) logOk("✓ Session retrieved (${r.status}): ${r.body}")
        else logErr("✗ Get session ${r.status}: ${r.body}")
    }

    private suspend fun doFullFlow() {
        binding.logView.text = ""
        logInfo("=== FULL INTEGRATION FLOW ===")
        doHealth()
        if (client.idToken == null) {
            logWarn("Skipping auth-gated tests — Login first then re-run")
            return
        }
        doCreateSession()
        doGetSession()
        logOk("=== FLOW COMPLETE ===")
    }

    // ── Logging ───────────────────────────────────────────────────────────────

    private fun log(msg: String, colorRes: Int) {
        val time = ts.format(Date())
        val line = "[$time] $msg\n"
        val spannable = SpannableString(line)
        spannable.setSpan(
            ForegroundColorSpan(ContextCompat.getColor(this, colorRes)),
            0, line.length,
            Spannable.SPAN_EXCLUSIVE_EXCLUSIVE
        )
        binding.logView.append(spannable)
        binding.logScroll.post { binding.logScroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun logOk(msg: String)   = log(msg, R.color.log_ok)
    private fun logErr(msg: String)  = log(msg, R.color.log_err)
    private fun logInfo(msg: String) = log(msg, R.color.log_info)
    private fun logWarn(msg: String) = log(msg, R.color.log_warn)
    private fun logDim(msg: String)  = log(msg, R.color.log_dim)

    private fun launch(block: suspend () -> Unit) {
        lifecycleScope.launch { block() }
    }
}
