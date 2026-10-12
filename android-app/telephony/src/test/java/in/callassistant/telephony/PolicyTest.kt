package `in`.callassistant.telephony
import org.junit.Assert.*
import org.junit.Test
class PolicyTest {
 @Test fun failuresNeverSilence() {
  for (status in ContactStatus.entries.filter { it != ContactStatus.NOT_SAVED })
   assertEquals(ScreeningAction.ALLOW, ScreeningPolicy.decide(true,true,status))
 }
 @Test fun silencingRequiresBothExplicitSwitches() {
  assertEquals(ScreeningAction.SILENCE, ScreeningPolicy.decide(true,true,ContactStatus.NOT_SAVED))
  assertEquals(ScreeningAction.ALLOW, ScreeningPolicy.decide(false,true,ContactStatus.NOT_SAVED))
  assertEquals(ScreeningAction.ALLOW, ScreeningPolicy.decide(true,false,ContactStatus.NOT_SAVED))
 }
 @Test fun indianMobileFormatsMatch() {
  for (number in listOf("9876543210", "+91 98765 43210", "00919876543210", "09876543210", "919876543210"))
   assertEquals("+919876543210",PhoneNumbers.normalize(number))
 }
 @Test fun internationalNumbersKeepCountryCode() {
  assertEquals("+14155552671",PhoneNumbers.normalize("+1 (415) 555-2671"))
  assertEquals("+449876543210",PhoneNumbers.normalize("+44 9876543210"))
 }
 @Test fun missingAndNonPhoneInputIsNotAContact() {
  for (number in listOf(null,"","   ","private","sip:hello@example.com","*123#")) assertNull(PhoneNumbers.normalize(number))
 }
}
