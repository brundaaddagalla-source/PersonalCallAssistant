package `in`.callassistant.telephony

/** The existing Member 3/4 APIs accept a boolean, not an indeterminate contact status.
 * Return null when a lookup was inconclusive rather than misrepresenting it as NOT_SAVED.
 * This is a local adapter, not a contacts upload or an authenticated provider event.
 */
data class CallerContext(val number: String, val known: Boolean, val name: String?) {
 fun decisionCaller(): Map<String, Any?> = mapOf(
  "number" to number, "is_known_contact" to known, "contact_name" to name,
  "contact_group" to "none", "number_withheld" to false
 )
 fun voiceSession(): Map<String, Any?> = mapOf(
  "caller_number" to number, "is_known_contact" to known, "caller_name" to name,
  "contact_group" to "none", "number_withheld" to false, "language" to "English"
 )
 companion object {
  fun from(number: String?, match: ContactMatch): CallerContext? {
   val normalized = PhoneNumbers.normalize(number) ?: return null
   return when(match.status) {
    ContactStatus.SAVED -> CallerContext(normalized, true, match.displayName)
    ContactStatus.NOT_SAVED -> CallerContext(normalized, false, null)
    else -> null
   }
  }
 }
}
