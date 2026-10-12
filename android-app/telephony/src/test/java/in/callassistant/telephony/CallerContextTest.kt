package `in`.callassistant.telephony
import org.junit.Assert.*
import org.junit.Test
class CallerContextTest {
 @Test fun savedCallerMapsToBothExistingApis() {
  val c = CallerContext.from("9876543210",ContactMatch(ContactStatus.SAVED,"Sam"))!!
  assertEquals("+919876543210",c.decisionCaller()["number"])
  assertEquals(true,c.decisionCaller()["is_known_contact"])
  assertEquals("Sam",c.decisionCaller()["contact_name"])
  assertEquals(c.decisionCaller()["number"],c.voiceSession()["caller_number"])
  assertEquals("Sam",c.voiceSession()["caller_name"])
  assertEquals("none",c.voiceSession()["contact_group"])
 }
 @Test fun unsavedCallerNeverLeaksAContactName() {
  val c = CallerContext.from("9876543210",ContactMatch(ContactStatus.NOT_SAVED,"stale name"))!!
  assertEquals(false,c.decisionCaller()["is_known_contact"])
  assertNull(c.voiceSession()["caller_name"])
 }
 @Test fun inconclusiveLookupCannotBecomeUnknownCaller() {
  for (s in ContactStatus.entries.filter { it !in listOf(ContactStatus.SAVED,ContactStatus.NOT_SAVED) })
   assertNull(CallerContext.from("9876543210",ContactMatch(s)))
  assertNull(CallerContext.from(null,ContactMatch(ContactStatus.SAVED,"Sam")))
 }
}
