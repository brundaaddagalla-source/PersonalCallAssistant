package `in`.callassistant.telephony

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** App-private storage. No contacts or call data are uploaded. Retains at most 50 events. */
class TelephonyStore(context: Context) {
 private val prefs = context.applicationContext.getSharedPreferences("member2_telephony", Context.MODE_PRIVATE)
 var enabled: Boolean
  get() = prefs.getBoolean("enabled", false)
  set(value) { prefs.edit().putBoolean("enabled", value).apply() }
 var silenceUnknown: Boolean
  get() = prefs.getBoolean("silenceUnknown", false)
  set(value) { prefs.edit().putBoolean("silenceUnknown", value).apply() }
 var aiBackendUrl: String
  get() = prefs.getString("aiBackendUrl", "http://10.0.2.2:8000") ?: "http://10.0.2.2:8000"
  set(value) { prefs.edit().putString("aiBackendUrl", value).apply() }
 var voiceEngineUrl: String
  get() = prefs.getString("voiceEngineUrl", "http://10.0.2.2:8100") ?: "http://10.0.2.2:8100"
  set(value) { prefs.edit().putString("voiceEngineUrl", value).apply() }
 fun events(): List<ScreeningEvent> = synchronized(lock) {
  try {
   val a = JSONArray(prefs.getString("events", "[]"))
   (0 until a.length()).map { i ->
    val o = a.getJSONObject(i)
    ScreeningEvent(
     o.getString("id"),
     o.getLong("timestamp"),
     if(o.isNull("number")) null else o.getString("number"),
     ContactMatch(ContactStatus.valueOf(o.getString("status")), if(o.isNull("name")) null else o.getString("name")),
     ScreeningAction.valueOf(o.getString("action")),
     o.getString("reason"),
     if(o.has("decisionAction") && !o.isNull("decisionAction")) o.getString("decisionAction") else null,
     if(o.has("intent") && !o.isNull("intent")) o.getString("intent") else null,
     if(o.has("sessionRef") && !o.isNull("sessionRef")) o.getString("sessionRef") else null,
     if(o.has("assistantResponse") && !o.isNull("assistantResponse")) o.getString("assistantResponse") else null,
     if(o.has("escalationRequested")) o.getBoolean("escalationRequested") else false,
     if(o.has("backendStatus") && !o.isNull("backendStatus")) o.getString("backendStatus") else null,
     if(o.has("eventType")) o.getString("eventType") else "screening"
    )
   }
  } catch (_: Exception) { emptyList() }
 }
 fun add(event: ScreeningEvent) = synchronized(lock) {
  saveEvents((listOf(event) + events()).take(50))
 }
 fun updateEvent(id: String, transform: (ScreeningEvent) -> ScreeningEvent) = synchronized(lock) {
  val current = events()
  val updated = current.map { if (it.id == id) transform(it) else it }
  saveEvents(updated)
 }
 private fun saveEvents(list: List<ScreeningEvent>) {
  val array = JSONArray()
  list.forEach { e ->
   array.put(JSONObject().apply {
    put("id", e.id)
    put("timestamp", e.timestamp)
    put("number", e.number ?: JSONObject.NULL)
    put("status", e.match.status.name)
    put("name", e.match.displayName ?: JSONObject.NULL)
    put("action", e.action.name)
    put("reason", e.reason)
    put("decisionAction", e.decisionAction ?: JSONObject.NULL)
    put("intent", e.intent ?: JSONObject.NULL)
    put("sessionRef", e.sessionRef ?: JSONObject.NULL)
    put("assistantResponse", e.assistantResponse ?: JSONObject.NULL)
    put("escalationRequested", e.escalationRequested)
    put("backendStatus", e.backendStatus ?: JSONObject.NULL)
    put("eventType", e.eventType)
   })
  }
  prefs.edit().putString("events", array.toString()).apply()
 }
 fun clear() = synchronized(lock) { prefs.edit().remove("events").apply() }
 companion object { private val lock = Any() }
}
