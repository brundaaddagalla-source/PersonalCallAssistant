package `in`.callassistant.telephony

enum class ContactStatus { SAVED, NOT_SAVED, PERMISSION_DENIED, NUMBER_UNAVAILABLE, LOOKUP_FAILED, TIMED_OUT }
data class ContactMatch(val status: ContactStatus, val displayName: String? = null)
enum class ScreeningAction { ALLOW, SILENCE }
data class ScreeningEvent(
 val id: String, val timestamp: Long, val number: String?, val match: ContactMatch,
 val action: ScreeningAction, val reason: String
)
object ScreeningPolicy {
 fun decide(enabled: Boolean, silenceUnknown: Boolean, status: ContactStatus): ScreeningAction =
  if (enabled && silenceUnknown && status == ContactStatus.NOT_SAVED) ScreeningAction.SILENCE else ScreeningAction.ALLOW
}
/** India-only mobile canonicalization. Other international numbers retain their country code. */
object PhoneNumbers {
 fun normalize(raw: String?): String? {
  if (raw.isNullOrBlank()) return null
  val input = raw.trim()
  if (input.any { !it.isDigit() && it !in "+-(). " }) return null
  val digits = input.filter { it in '0'..'9' }
  if (digits.isEmpty()) return null
  if (input.startsWith("+")) return "+$digits"
  if (digits.startsWith("00") && digits.length > 2) return "+" + digits.drop(2)
  if (digits.length == 12 && digits.startsWith("91")) return "+$digits"
  if (digits.length == 11 && digits.startsWith("0") && digits[1] in '6'..'9') return "+91" + digits.drop(1)
  if (digits.length == 10 && digits[0] in '6'..'9') return "+91$digits"
  return digits
 }
}
