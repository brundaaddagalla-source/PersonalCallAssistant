package `in`.callassistant.demo

import org.json.JSONObject
import android.Manifest
import android.app.Activity
import android.app.role.RoleManager
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.net.Uri
import android.view.View
import android.widget.*
import `in`.callassistant.telephony.*
import java.text.DateFormat
import java.util.Date
import java.util.UUID
import java.util.concurrent.Executors

/** Minimal native test harness. Member 1 can replace this screen with Compose. */
class DiagnosticsActivity : Activity() {
 private lateinit var body: LinearLayout
 private lateinit var status: TextView
 private lateinit var history: TextView
 private lateinit var result: TextView
 private lateinit var input: EditText
 private lateinit var contract: TextView
 private lateinit var serverStatus: TextView
 private var lastMatch: ContactMatch? = null
 private var lastResolvedContext: CallerContext? = null
 private val worker = Executors.newSingleThreadExecutor()
 private val main = Handler(Looper.getMainLooper())
 private var lookupCancellation: CancellationSignal? = null
 private var generation = 0
 private val store by lazy { TelephonyStore(this) }
 private val refresh = object : Runnable {
  override fun run() { refreshState(); main.postDelayed(this, 2000) }
 }
 private fun dp(n: Int) = (n * resources.displayMetrics.density).toInt()
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  window.statusBarColor = Color.rgb(17, 30, 47)
  val scroll = ScrollView(this).apply { setBackgroundColor(Color.rgb(245,247,250)); isFillViewport = true }
  body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(22),dp(32),dp(22),dp(32)) }
  scroll.addView(body)
  body.setOnApplyWindowInsetsListener { v, insets ->
   v.setPadding(dp(22), insets.systemWindowInsetTop + dp(20), dp(22), insets.systemWindowInsetBottom + dp(20)); insets
  }
  setContentView(scroll)
  text("MEMBER 2 / ANDROID LAB", 12, true)
  text("Know who is calling.", 29, true)
  text("Contact matching and call screening for your team's assistant. Calls ring normally by default.", 16)
  status = text("", 14)
  button("1 · Enable caller screening") {
   val roles = getSystemService(RoleManager::class.java)
   if (roles.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
    if (roles.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) toast("Already enabled")
    else startActivityForResult(roles.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), 10)
   } else toast("Call screening role is unavailable on this device")
  }
  button("2 · Allow contact matching") {
   if (checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) toast("Contacts permission already granted")
   else requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 11)
  }
  button("App permissions / settings") { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) }

  text("Backend servers", 21, true)
  serverStatus = text("AI Backend: ${store.aiBackendUrl}\nVoice Engine: ${store.voiceEngineUrl}\nStatus: Not checked yet.", 14)
  button("Test server connections") { testConnections() }

  text("Screening controls", 21, true)
  toggle("Enable local screening rules", store.enabled) { store.enabled = it }
  toggle("Silence numbers not saved in contacts", store.silenceUnknown) { store.silenceUnknown = it }
  text("Silencing leaves the call unanswered; it does not answer, reject, or forward it. Missing permission, errors, and lookup timeouts always allow ringing.", 14)
  text("Try a contact lookup", 21, true)
  input = EditText(this).apply { hint = "+91 mobile number"; inputType = android.text.InputType.TYPE_CLASS_PHONE; importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO }
  body.addView(input)
  button("Check number locally") { lookup() }
  result = text("No lookup yet. This test never places a call.", 15)
  text("Team API preview & live tests", 21, true)
  contract = text("Check a number to preview Member 3 and Member 4 payloads.", 14)
  button("Query AI Decision (Member 3)") { testAiDecision() }
  button("Test Voice Turn (Member 4)") { testVoiceSession() }
  text("Recent screening events", 21, true)
  text("Only calls delivered to this screening service appear here. This is not your phone's complete call history.", 14)
  button("Refresh events") { refreshState() }
  history = text("No calls screened yet.", 15)
  button("Delete local event history") { store.clear(); refreshState() }
  text("Airtel forwarding is separate", 21, true)
  text("This app does not activate or verify forwarding, answer with AI, record audio, or upload contacts. The phone-service integration must receive forwarded calls. Turning these controls off or uninstalling does not cancel carrier forwarding.", 14)
 }
 private fun testConnections() {
  serverStatus.text = "Testing connectivity to backends..."
  worker.execute {
   val client = AssistantApiClient()
   val (aiOk, aiMsg) = client.checkHealth(store.aiBackendUrl, "/health")
   val (voiceOk, voiceMsg) = client.checkHealth(store.voiceEngineUrl, "/health")
   val statusStr = "AI Backend (${store.aiBackendUrl}): ${if (aiOk) "ONLINE (HTTP 200)" else "OFFLINE ($aiMsg)"}\n" +
     "Voice Engine (${store.voiceEngineUrl}): ${if (voiceOk) "ONLINE (HTTP 200)" else "OFFLINE ($voiceMsg)"}"
   main.post { serverStatus.text = statusStr }
  }
 }
 private fun testAiDecision() {
  val context = lastResolvedContext
  if (context == null) {
   toast("Check a valid number first")
   return
  }
  contract.text = "Querying Member 3 AI Backend (${store.aiBackendUrl})..."
  worker.execute {
   val client = AssistantApiClient()
   val result = client.decide(store.aiBackendUrl, context)
   main.post {
    result.onSuccess { res ->
     contract.text = "=== Member 3 Decision Result ===\n" +
       "Action: ${res.action}\n" +
       "Intent: ${res.intent} (Risk: ${res.riskLabel})\n" +
       "Spoken Response: \"${res.speak}\"\n" +
       "Escalate to user: ${res.shouldEscalate}\n" +
       "End call: ${res.endCall}\n" +
       "Notification: ${res.notificationTitle ?: "None"}"
     val eventId = UUID.randomUUID().toString()
     store.add(
      ScreeningEvent(
       id = eventId,
       timestamp = System.currentTimeMillis(),
       number = context.number,
       match = lastMatch ?: ContactMatch(ContactStatus.SAVED, context.name),
       action = ScreeningAction.ALLOW,
       reason = "Manual AI Decision test",
       decisionAction = res.action,
       intent = res.intent,
       assistantResponse = res.speak,
       escalationRequested = res.shouldEscalate,
       backendStatus = "synced",
       eventType = "test_decision"
      )
     )
     refreshState()
    }.onFailure { err ->
     contract.text = "AI Decision Error: ${err.message}"
     toast("Failed to connect to Member 3 AI Backend")
    }
   }
  }
 }
 private fun testVoiceSession() {
  val context = lastResolvedContext
  if (context == null) {
   toast("Check a valid number first")
   return
  }
  contract.text = "Creating session on Member 4 Voice Engine (${store.voiceEngineUrl})..."
  worker.execute {
   val client = AssistantApiClient()
   val sessionRes = client.createVoiceSession(store.voiceEngineUrl, context)
   sessionRes.onSuccess { sessionId ->
    val turnRes = client.sendVoiceTurn(
     store.voiceEngineUrl,
     sessionId,
     "Hello, I need help checking my delivery status.",
     false
    )
    main.post {
     turnRes.onSuccess { turn ->
      contract.text = "=== Member 4 Voice Turn Result ===\n" +
        "Session ID: ${turn.sessionId}\n" +
        "Turn Number: ${turn.turnNumber}\n" +
        "Session Status: ${turn.sessionStatus}\n" +
        "Decision Action: ${turn.decisionAction}\n" +
        "Assistant Text: \"${turn.assistantText}\"\n" +
        "Audio Generated: ${turn.audioGenerated}"
      val eventId = UUID.randomUUID().toString()
      store.add(
       ScreeningEvent(
        id = eventId,
        timestamp = System.currentTimeMillis(),
        number = context.number,
        match = lastMatch ?: ContactMatch(ContactStatus.SAVED, context.name),
        action = ScreeningAction.ALLOW,
        reason = "Manual Voice Turn test",
        decisionAction = turn.decisionAction,
        sessionRef = turn.sessionId,
        assistantResponse = turn.assistantText,
        backendStatus = "synced",
        eventType = "voice_session"
       )
      )
      refreshState()
     }.onFailure { turnErr ->
      contract.text = "Session created ($sessionId), but turn failed: ${turnErr.message}"
     }
    }
   }.onFailure { sessErr ->
    main.post {
     contract.text = "Voice Session Error: ${sessErr.message}"
     toast("Failed to connect to Member 4 Voice Engine")
    }
   }
  }
 }
 private fun lookup() {
  val token = ++generation
  lookupCancellation?.cancel()
  val cancellation = CancellationSignal().also { lookupCancellation = it }
  val number = input.text.toString()
  result.text = "Checking…"
  contract.text = "Waiting for contact lookup…"
  main.postDelayed({ if(token == generation) { generation++; result.text = "Lookup timed out. Try again."; contract.text = "No payload: lookup was inconclusive."; worker.execute { cancellation.cancel() } } }, 1500)
  worker.submit {
   val match = ContactLookup(this).lookup(number, cancellation)
   main.post { if(token == generation) { generation++; result.text = "${label(match.status)}${match.displayName?.let { " · $it" } ?: ""}\n${PhoneNumbers.normalize(number) ?: "No usable phone number"}"
    val context = CallerContext.from(number, match)
    lastMatch = match
    lastResolvedContext = context
    contract.text = if(context == null) "No payload: contact status is inconclusive. Keep the call ringing; do not send is_known_contact=false."
     else "Member 3 / caller:\n${JSONObject(context.decisionCaller()).toString(2)}\n\nMember 4 / session:\n${JSONObject(context.voiceSession()).toString(2)}"
   } }
  }
 }
 private fun refreshState() {
  val role = getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
  val contacts = checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
  status.text = "Screening role: ${if(role) "Enabled" else "Not enabled"}  •  Contacts: ${if(contacts) "Allowed" else "Not allowed"}"
  history.text = store.events().take(12).joinToString("\n\n") {
   val header = "${it.match.displayName ?: it.number ?: "Unavailable number"} [${it.eventType}]"
   val basic = "${label(it.match.status)} · Local: ${it.action.name.lowercase()}\n${DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT).format(Date(it.timestamp))} · ${it.reason}"
   val ai = if (it.decisionAction != null) {
    "\nAI Action: ${it.decisionAction} (Intent: ${it.intent ?: "unknown"})\nResponse: \"${it.assistantResponse ?: ""}\"" +
      if (it.escalationRequested) "\n⚠️ ESCALATION / NOTIFY USER" else ""
   } else ""
   val session = if (it.sessionRef != null) "\nSession ID: ${it.sessionRef}" else ""
   val statusStr = if (it.backendStatus != null) "\nBackend status: ${it.backendStatus}" else ""
   "$header\n$basic$ai$session$statusStr"
  }.ifEmpty { "No calls screened yet. Call this phone from another phone after granting the screening role." }
 }
 private fun label(s: ContactStatus) = when(s) {
  ContactStatus.SAVED -> "Saved contact"
  ContactStatus.NOT_SAVED -> "Not in contacts"
  ContactStatus.PERMISSION_DENIED -> "Unable to check — contacts permission needed"
  ContactStatus.NUMBER_UNAVAILABLE -> "Number unavailable"
  ContactStatus.LOOKUP_FAILED -> "Unable to check — lookup failed"
  ContactStatus.TIMED_OUT -> "Unable to check — lookup timed out"
 }
 private fun text(value: String, size: Int, bold: Boolean=false): TextView = TextView(this).apply {
  text=value; textSize=size.toFloat(); setTextColor(Color.rgb(26,42,61)); setPadding(0,dp(9),0,dp(9))
  if(bold) setTypeface(typeface, Typeface.BOLD)
  body.addView(this)
 }
 private fun button(value: String, action: ()->Unit) { body.addView(Button(this).apply { text=value; isAllCaps=false; setOnClickListener { action() } }) }
 private fun toggle(value: String, checked: Boolean, change: (Boolean)->Unit) { body.addView(Switch(this).apply { text=value; isChecked=checked; setPadding(0,dp(12),0,dp(12)); setOnCheckedChangeListener { _,v -> change(v) } }) }
 private fun toast(s: String) { Toast.makeText(this, s, Toast.LENGTH_LONG).show() }
 override fun onResume() { super.onResume(); main.post(refresh) }
 override fun onPause() { main.removeCallbacks(refresh); super.onPause() }
 override fun onDestroy() { generation++; main.removeCallbacksAndMessages(null); lookupCancellation?.cancel(); worker.shutdownNow(); super.onDestroy() }
}
