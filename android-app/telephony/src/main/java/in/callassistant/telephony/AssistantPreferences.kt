package `in`.callassistant.telephony

import android.content.Context
import java.time.LocalDateTime
import org.json.JSONObject

enum class ContactRule { DEFAULT, ALWAYS_RING, SILENCE }
/** Overnight windows belong to the day on which they begin. End is exclusive. */
data class QuietSchedule(val enabled: Boolean = false, val start: Int = 9*60, val end: Int = 17*60,
 val days: Set<Int> = setOf(1,2,3,4,5)) {
 fun contains(now: LocalDateTime): Boolean {
  if (!enabled) return true
  val minute = now.hour*60 + now.minute
  val day = now.dayOfWeek.value
  return when {
   start == end -> day in days
   start < end -> day in days && minute >= start && minute < end
   else -> (day in days && minute >= start) || ((if(day==1) 7 else day-1) in days && minute < end)
  }
 }
}
object LocalCallRules {
 fun decide(active: Boolean, silenceUnknown: Boolean, status: ContactStatus, rule: ContactRule): ScreeningAction {
  if(!active || status !in setOf(ContactStatus.SAVED,ContactStatus.NOT_SAVED)) return ScreeningAction.ALLOW
  return when(rule) {
   ContactRule.ALWAYS_RING -> ScreeningAction.ALLOW
   ContactRule.SILENCE -> ScreeningAction.SILENCE
   ContactRule.DEFAULT -> ScreeningPolicy.decide(true,silenceUnknown,status)
  }
 }
}
class AssistantPreferences(context: Context) {
 private val prefs = context.applicationContext.getSharedPreferences("assistant_ui",Context.MODE_PRIVATE)
 var schedule: QuietSchedule
  get() = QuietSchedule(prefs.getBoolean("schedule",false),prefs.getInt("start",540).coerceIn(0,1439),prefs.getInt("end",1020).coerceIn(0,1439),
   prefs.getStringSet("days",setOf("1","2","3","4","5"))!!.mapNotNull { it.toIntOrNull()?.takeIf { d -> d in 1..7 } }.toSet())
  set(s) { prefs.edit().putBoolean("schedule",s.enabled).putInt("start",s.start).putInt("end",s.end).putStringSet("days",s.days.map { it.toString() }.toSet()).apply() }
 var appearance: String
  get()=prefs.getString("appearance","Dark")!!
  set(v) { prefs.edit().putString("appearance",v).apply() }
 var notifyCalls: Boolean
  get()=prefs.getBoolean("notify",false)
  set(v) { prefs.edit().putBoolean("notify",v).apply() }
 fun rule(number: String?): ContactRule {
  val n=PhoneNumbers.normalize(number) ?: return ContactRule.DEFAULT
  return runCatching { ContactRule.valueOf(JSONObject(prefs.getString("rules","{}")!!).optString(n,"DEFAULT")) }.getOrDefault(ContactRule.DEFAULT)
 }
 fun setRule(number: String,rule: ContactRule) {
  val n=PhoneNumbers.normalize(number) ?: return
  val json=runCatching { JSONObject(prefs.getString("rules","{}")!!) }.getOrDefault(JSONObject())
  if(rule==ContactRule.DEFAULT) json.remove(n) else json.put(n,rule.name)
  prefs.edit().putString("rules",json.toString()).apply()
 }
 fun favorites(): Set<String> = prefs.getStringSet("favorites",emptySet())!!.toSet()
 fun toggleFavorite(number: String) {
  val n=PhoneNumbers.normalize(number) ?: return
  val f=favorites().toMutableSet();if(!f.add(n)) f.remove(n)
  prefs.edit().putStringSet("favorites",f).apply()
 }
}
