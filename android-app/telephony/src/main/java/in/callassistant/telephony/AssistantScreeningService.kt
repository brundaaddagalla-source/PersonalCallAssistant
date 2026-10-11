package `in`.callassistant.telephony

import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import android.telecom.Call
import android.telecom.CallScreeningService
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.Future

class AssistantScreeningService : CallScreeningService() {
 private val main = Handler(Looper.getMainLooper())
 private val workers = Executors.newFixedThreadPool(2)
 private val pending = mutableSetOf<Pending>()
 private class Pending(val details: Call.Details, val number: String?, val enabled: Boolean, val silence: Boolean) {
  val cancellation = CancellationSignal()
  var future: Future<*>? = null
  var done = false
  var timeout: Runnable? = null
 }
 override fun onScreenCall(details: Call.Details) {
  if (details.callDirection != Call.Details.DIRECTION_INCOMING) return
  val settings = TelephonyStore(this)
  val raw = details.handle?.takeIf { it.scheme == "tel" }?.schemeSpecificPart
  val p = Pending(details, PhoneNumbers.normalize(raw), settings.enabled, settings.silenceUnknown)
  pending.add(p)
  // Finish locally well before Android's five-second response deadline. Never call a backend here.
  p.timeout = Runnable { finish(p, ContactMatch(ContactStatus.TIMED_OUT), "Contact lookup timed out; call allowed") }
  main.postDelayed(p.timeout!!, 1200)
  p.future = workers.submit {
   val match = ContactLookup(this).lookup(p.number, p.cancellation)
   main.post { finish(p, match, if (p.enabled) "Local screening rule" else "Screening controls off; call allowed") }
  }
 }
 private fun finish(p: Pending, match: ContactMatch, reason: String) {
  if (p.done) return
  p.done = true
  p.timeout?.let(main::removeCallbacks)
  pending.remove(p)
  val action = ScreeningPolicy.decide(p.enabled, p.silence, match.status)
  try {
   respondToCall(p.details, CallResponse.Builder().setDisallowCall(false).setRejectCall(false)
    .setSilenceCall(action == ScreeningAction.SILENCE).setSkipCallLog(false).setSkipNotification(false).build())
   TelephonyStore(this).add(ScreeningEvent(UUID.randomUUID().toString(), System.currentTimeMillis(), p.number, match, action, reason))
  } finally {
   // Cancellation happens after the response, so provider cancellation cannot delay screening.
   p.future?.cancel(true)
   workers.execute { p.cancellation.cancel() }
  }
 }
 override fun onDestroy() {
  pending.toList().forEach { finish(it, ContactMatch(ContactStatus.LOOKUP_FAILED), "Service stopped; call allowed") }
  workers.shutdown()
  super.onDestroy()
 }
}
