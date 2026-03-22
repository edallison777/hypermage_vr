package com.hypermage.vrtest

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class ApiResult(val status: Int, val body: JSONObject, val ok: Boolean)

class ApiClient {

    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val JSON = "application/json; charset=utf-8".toMediaType()
    private val AMZN_JSON = "application/x-amz-json-1.1".toMediaType()

    var idToken: String? = null

    // ── Cognito ───────────────────────────────────────────────────────────────

    fun signUp(username: String, password: String): ApiResult {
        val body = JSONObject().apply {
            put("ClientId", BuildConfig.COGNITO_CLIENT_ID)
            put("Username", username)
            put("Password", password)
            put("UserAttributes", org.json.JSONArray().apply {
                put(JSONObject().apply {
                    put("Name", "email")
                    put("Value", username)
                })
            })
        }
        return cognitoPost("AWSCognitoIdentityProviderService.SignUp", body)
    }

    fun confirmSignUp(username: String, code: String): ApiResult {
        val body = JSONObject().apply {
            put("ClientId", BuildConfig.COGNITO_CLIENT_ID)
            put("Username", username)
            put("ConfirmationCode", code)
        }
        return cognitoPost("AWSCognitoIdentityProviderService.ConfirmSignUp", body)
    }

    fun login(username: String, password: String): ApiResult {
        val body = JSONObject().apply {
            put("AuthFlow", "USER_PASSWORD_AUTH")
            put("ClientId", BuildConfig.COGNITO_CLIENT_ID)
            put("AuthParameters", JSONObject().apply {
                put("USERNAME", username)
                put("PASSWORD", password)
            })
        }
        val result = cognitoPost("AWSCognitoIdentityProviderService.InitiateAuth", body)
        if (result.ok) {
            idToken = result.body
                .optJSONObject("AuthenticationResult")
                ?.optString("IdToken")
        }
        return result
    }

    private fun cognitoPost(target: String, body: JSONObject): ApiResult {
        val req = Request.Builder()
            .url(BuildConfig.COGNITO_ENDPOINT)
            .post(body.toString().toRequestBody(AMZN_JSON))
            .addHeader("X-Amz-Target", target)
            .build()
        return execute(req)
    }

    // ── Session API ───────────────────────────────────────────────────────────

    fun healthCheck(): ApiResult {
        val req = buildRequest("GET", "/health", null)
        return execute(req)
    }

    fun createSession(playerId: String): ApiResult {
        val body = JSONObject().apply {
            put("playerId", playerId)
            put("region", "eu-west-1")
            put("gameMode", "deathmatch")
            put("platform", "quest3")
        }
        val req = buildRequest("POST", "/sessions", body)
        return execute(req)
    }

    fun getSession(sessionId: String): ApiResult {
        val req = buildRequest("GET", "/sessions/$sessionId", null)
        return execute(req)
    }

    private fun buildRequest(method: String, path: String, body: JSONObject?): Request {
        val url = BuildConfig.SESSION_API_URL + path
        val builder = Request.Builder().url(url)
        idToken?.let { builder.addHeader("Authorization", "Bearer $it") }
        return when (method) {
            "GET"  -> builder.get().build()
            "POST" -> builder.post(
                (body?.toString() ?: "{}").toRequestBody(JSON)
            ).build()
            else   -> builder.get().build()
        }
    }

    private fun execute(req: Request): ApiResult {
        val resp = http.newCall(req).execute()
        val raw  = resp.body?.string() ?: "{}"
        val json = try { JSONObject(raw) } catch (_: Exception) { JSONObject().put("raw", raw) }
        return ApiResult(resp.code, json, resp.isSuccessful)
    }
}
