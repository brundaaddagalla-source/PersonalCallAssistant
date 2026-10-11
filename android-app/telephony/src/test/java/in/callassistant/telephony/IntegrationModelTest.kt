package `in`.callassistant.telephony

import org.junit.Assert.*
import org.junit.Test

class IntegrationModelTest {

    @Test
    fun testScreeningEventDefaultsAndEnrichedFields() {
        val event = ScreeningEvent(
            id = "test-123",
            timestamp = 1700000000000L,
            number = "+919876543210",
            match = ContactMatch(ContactStatus.SAVED, "Alice"),
            action = ScreeningAction.ALLOW,
            reason = "Local rule allowed",
            decisionAction = "handle",
            intent = "personal",
            sessionRef = "sess-abc",
            assistantResponse = "Hello Alice, I can take a message.",
            escalationRequested = false,
            backendStatus = "synced",
            eventType = "screening"
        )

        assertEquals("test-123", event.id)
        assertEquals("+919876543210", event.number)
        assertEquals("Alice", event.match.displayName)
        assertEquals(ScreeningAction.ALLOW, event.action)
        assertEquals("handle", event.decisionAction)
        assertEquals("personal", event.intent)
        assertEquals("sess-abc", event.sessionRef)
        assertEquals("Hello Alice, I can take a message.", event.assistantResponse)
        assertFalse(event.escalationRequested)
        assertEquals("synced", event.backendStatus)
        assertEquals("screening", event.eventType)
    }

    @Test
    fun testScreeningEventBackwardCompatibilityDefaults() {
        val legacyStyleEvent = ScreeningEvent(
            id = "legacy-1",
            timestamp = 1700000000000L,
            number = "+919876543210",
            match = ContactMatch(ContactStatus.NOT_SAVED),
            action = ScreeningAction.SILENCE,
            reason = "Local rule silenced"
        )

        assertNull(legacyStyleEvent.decisionAction)
        assertNull(legacyStyleEvent.intent)
        assertNull(legacyStyleEvent.sessionRef)
        assertNull(legacyStyleEvent.assistantResponse)
        assertFalse(legacyStyleEvent.escalationRequested)
        assertNull(legacyStyleEvent.backendStatus)
        assertEquals("screening", legacyStyleEvent.eventType)
    }

    @Test
    fun testDecisionResultModel() {
        val result = DecisionResult(
            action = "transfer",
            intent = "emergency",
            speak = "This is urgent. Transferring you immediately.",
            endCall = false,
            shouldEscalate = true,
            riskLabel = "low_risk",
            reasons = listOf("Emergency keyword detected"),
            callerSummary = "Caller has a medical emergency",
            notificationTitle = "Urgent Call",
            notificationPriority = "high"
        )

        assertEquals("transfer", result.action)
        assertEquals("emergency", result.intent)
        assertTrue(result.shouldEscalate)
        assertEquals("high", result.notificationPriority)
    }

    @Test
    fun testVoiceTurnResultModel() {
        val turn = VoiceTurnResult(
            sessionId = "sess-xyz",
            turnNumber = 2,
            assistantText = "Tracking reference TRK123456 verified.",
            decisionAction = "handle",
            sessionStatus = "active",
            audioGenerated = true,
            audioUrl = "/api/voice/audio/response_123.mp3"
        )

        assertEquals("sess-xyz", turn.sessionId)
        assertEquals(2, turn.turnNumber)
        assertEquals("handle", turn.decisionAction)
        assertTrue(turn.audioGenerated)
        assertNotNull(turn.audioUrl)
    }
}
