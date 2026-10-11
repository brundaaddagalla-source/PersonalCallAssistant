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
 fun events(): List<ScreeningEvent> = synchronized(lock) {
  try {
   val a = JSONArray(prefs.getString("events", "[]"))
   (0 until a.length()).map { i ->
    val o = a.getJSONObject(i)
    ScreeningEvent(o.getString("id"), o.getLong("timestamp"), if(o.isNull("number")) null else o.getString("number"),
     ContactMatch(ContactStatus.valueOf(o.getString("status")), if(o.isNull("name")) null else o.getString("name")),
     ScreeningAction.valueOf(o.getString("action")), o.getString("reason"))
   }
  } catch (_: Exception) { emptyList() }
 }
 fun add(event: ScreeningEvent) = synchronized(lock) {
  val array = JSONArray()
  (listOf(event) + events()).take(50).forEach { e ->
   array.put(JSONObject().put("id",e.id).put("timestamp",e.timestamp).put("number",e.number ?: JSONObject.NULL)
    .put("status",e.match.status.name).put("name",e.match.displayName ?: JSONObject.NULL)
    .put("action",e.action.name).put("reason",e.reason))
  }
  prefs.edit().putString("events", array.toString()).apply()
 }
 fun clear() = synchronized(lock) { prefs.edit().remove("events").apply() }
 companion object { private val lock = Any() }
}
