package `in`.callassistant.telephony

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

data class DecisionResult(
    val action: String,
    val intent: String,
    val speak: String,
    val endCall: Boolean,
    val shouldEscalate: Boolean,
    val riskLabel: String,
    val reasons: List<String>,
    val callerSummary: String? = null,
    val notificationTitle: String? = null,
    val notificationPriority: String? = null
)

data class VoiceTurnResult(
    val sessionId: String,
    val turnNumber: Int,
    val assistantText: String,
    val decisionAction: String,
    val sessionStatus: String,
    val audioGenerated: Boolean,
    val audioUrl: String?
)

/**
 * Clean HTTP client for Member 3 (AI Decision API) and Member 4 (Voice Engine).
 * Uses standard HttpURLConnection without external library overhead.
 */
class AssistantApiClient(private val timeoutMs: Int = 3500) {

    /**
     * Checks service health via GET <baseUrl><path>.
     * Returns (isHealthy, statusOrErrorMessage).
     */
    fun checkHealth(baseUrl: String, path: String = "/health"): Pair<Boolean, String> {
        return try {
            val fullUrl = "${baseUrl.trimEnd('/')}${if (path.startsWith("/")) path else "/$path"}"
            val conn = (URL(fullUrl).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                setRequestProperty("Accept", "application/json")
            }
            val code = conn.responseCode
            if (code in 200..299) {
                val body = conn.inputStream.bufferedReader().use { it.readText() }
                conn.disconnect()
                Pair(true, "HTTP $code: $body")
            } else {
                conn.disconnect()
                Pair(false, "HTTP $code")
            }
        } catch (e: Exception) {
            Pair(false, e.message ?: "Connection failed")
        }
    }

    /**
     * Calls Member 3's POST /v1/decide with mapped caller context and transcript.
     */
    fun decide(
        aiBackendUrl: String,
        callerContext: CallerContext,
        transcript: List<Map<String, String>> = emptyList(),
        userName: String = "Alex"
    ): Result<DecisionResult> = runCatching {
        val endpoint = "${aiBackendUrl.trimEnd('/')}/v1/decide"
        val payload = JSONObject().apply {
            put("call_id", UUID.randomUUID().toString())
            put("caller", JSONObject(callerContext.decisionCaller()))
            val transcriptArray = JSONArray()
            transcript.forEach { turn ->
                transcriptArray.put(JSONObject().apply {
                    put("speaker", turn["speaker"] ?: "caller")
                    put("text", turn["text"] ?: "")
                })
            }
            put("transcript", transcriptArray)
            put("preferences", JSONObject().apply {
                put("user_name", userName)
                put("do_not_disturb", false)
                put("max_clarification_turns", 3)
                put("rules", JSONArray())
            })
        }

        val responseJson = postJson(endpoint, payload.toString())
        val action = responseJson.optString("action", "handle")
        val speak = responseJson.optString("speak", "")
        val endCall = responseJson.optBoolean("end_call", false)

        val intentObj = responseJson.optJSONObject("intent")
        val intentName = intentObj?.optString("intent") ?: responseJson.optString("intent", "unknown")

        val riskObj = responseJson.optJSONObject("risk")
        val riskLabel = riskObj?.optString("label") ?: "low_risk"

        val reasonsList = mutableListOf<String>()
        val reasonsArr = responseJson.optJSONArray("reasons")
        if (reasonsArr != null) {
            for (i in 0 until reasonsArr.length()) {
                reasonsList.add(reasonsArr.getString(i))
            }
        }

        val notifObj = responseJson.optJSONObject("notification")
        val notifTitle = notifObj?.optString("title")
        val notifPriority = notifObj?.optString("priority")

        val shouldEscalate = action in listOf("transfer", "escalate") ||
                intentName == "emergency" ||
                notifPriority == "high" ||
                responseJson.optBoolean("should_escalate", false)

        DecisionResult(
            action = action,
            intent = intentName,
            speak = speak,
            endCall = endCall,
            shouldEscalate = shouldEscalate,
            riskLabel = riskLabel,
            reasons = reasonsList,
            callerSummary = if (responseJson.isNull("caller_summary")) null else responseJson.optString("caller_summary"),
            notificationTitle = notifTitle,
            notificationPriority = notifPriority
        )
    }

    /**
     * Calls Member 4's POST /api/sessions to initiate a voice conversation session.
     */
    fun createVoiceSession(
        voiceEngineUrl: String,
        callerContext: CallerContext
    ): Result<String> = runCatching {
        val endpoint = "${voiceEngineUrl.trimEnd('/')}/api/sessions"
        val payload = JSONObject(callerContext.voiceSession())
        val responseJson = postJson(endpoint, payload.toString())
        responseJson.getString("session_id")
    }

    /**
     * Calls Member 4's POST /api/sessions/{sessionId}/turn to submit a conversation turn.
     */
    fun sendVoiceTurn(
        voiceEngineUrl: String,
        sessionId: String,
        callerText: String,
        generateAudio: Boolean = false
    ): Result<VoiceTurnResult> = runCatching {
        val endpoint = "${voiceEngineUrl.trimEnd('/')}/api/sessions/$sessionId/turn"
        val payload = JSONObject().apply {
            put("caller_text", callerText)
            put("generate_audio", generateAudio)
        }
        val responseJson = postJson(endpoint, payload.toString())
        val decisionObj = responseJson.optJSONObject("decision")

        VoiceTurnResult(
            sessionId = responseJson.optString("session_id", sessionId),
            turnNumber = responseJson.optInt("turn_number", 1),
            assistantText = responseJson.optString("assistant_text", ""),
            decisionAction = decisionObj?.optString("action") ?: "continue",
            sessionStatus = responseJson.optString("session_status", "active"),
            audioGenerated = responseJson.optBoolean("audio_generated", false),
            audioUrl = if (responseJson.isNull("audio_url")) null else responseJson.optString("audio_url")
        )
    }

    private fun postJson(endpoint: String, jsonBody: String): JSONObject {
        val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=UTF-8")
            setRequestProperty("Accept", "application/json")
        }

        OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
            writer.write(jsonBody)
            writer.flush()
        }

        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val responseText = stream?.bufferedReader()?.use { it.readText() } ?: ""
        conn.disconnect()

        if (code !in 200..299) {
            throw RuntimeException("HTTP $code: $responseText")
        }
        return JSONObject(responseText)
    }
}
