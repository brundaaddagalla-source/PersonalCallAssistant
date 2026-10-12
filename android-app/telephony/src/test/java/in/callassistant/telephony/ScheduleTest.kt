package `in`.callassistant.telephony
import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDateTime
class ScheduleTest {
 @Test fun overnightBelongsToStartDay() {
  val s=QuietSchedule(true,22*60,7*60,setOf(5))
  assertTrue(s.contains(LocalDateTime.of(2026,10,9,23,0)))
  assertTrue(s.contains(LocalDateTime.of(2026,10,10,6,59)))
  assertFalse(s.contains(LocalDateTime.of(2026,10,10,7,0)))
  assertFalse(s.contains(LocalDateTime.of(2026,10,10,23,0)))
 }
 @Test fun boundariesAndDisabledSchedule() {
  val s=QuietSchedule(true,540,1020,setOf(1))
  assertTrue(s.contains(LocalDateTime.of(2026,10,12,9,0)))
  assertFalse(s.contains(LocalDateTime.of(2026,10,12,17,0)))
  assertFalse(s.copy(days=emptySet()).contains(LocalDateTime.of(2026,10,12,10,0)))
  assertTrue(s.copy(enabled=false).contains(LocalDateTime.of(2026,10,11,23,0)))
 }
 @Test fun explicitRulesRespectMasterAndFailOpen() {
  assertEquals(ScreeningAction.ALLOW,LocalCallRules.decide(true,true,ContactStatus.NOT_SAVED,ContactRule.ALWAYS_RING))
  assertEquals(ScreeningAction.SILENCE,LocalCallRules.decide(true,false,ContactStatus.SAVED,ContactRule.SILENCE))
  assertEquals(ScreeningAction.ALLOW,LocalCallRules.decide(false,true,ContactStatus.SAVED,ContactRule.SILENCE))
  for(s in ContactStatus.entries.filter { it !in setOf(ContactStatus.SAVED,ContactStatus.NOT_SAVED) })
   assertEquals(ScreeningAction.ALLOW,LocalCallRules.decide(true,true,s,ContactRule.SILENCE))
 }
 @Test fun fullDayAndSundayOvernight() {
  assertTrue(QuietSchedule(true,0,0,setOf(1)).contains(LocalDateTime.of(2026,10,12,23,59)))
  assertTrue(QuietSchedule(true,1380,60,setOf(7)).contains(LocalDateTime.of(2026,10,12,0,30)))
 }
}
