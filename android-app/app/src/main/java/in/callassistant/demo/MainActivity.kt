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
import java.util.concurrent.Executors

/** Minimal native test harness. Member 1 can replace this screen with Compose. */
class MainActivity : Activity() {
 private lateinit var body: LinearLayout
 private lateinit var status: TextView
 private lateinit var history: TextView
 private lateinit var result: TextView
 private lateinit var input: EditText
 private lateinit var contract: TextView
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
  text("Contact matching and call screening for your team's assistant. Calls ring normally by default.",16)
  status = text("",14)
  button("1 · Enable caller screening") {
   val roles = getSystemService(RoleManager::class.java)
   if (roles.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
    if (roles.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) toast("Already enabled")
    else startActivityForResult(roles.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING),10)
   } else toast("Call screening role is unavailable on this device")
  }
  button("2 · Allow contact matching") {
   if (checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) toast("Contacts permission already granted")
   else requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS),11)
  }
  button("App permissions / settings") { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName"))) }
  text("Screening controls",21,true)
  toggle("Enable local screening rules",store.enabled) { store.enabled = it }
  toggle("Silence numbers not saved in contacts",store.silenceUnknown) { store.silenceUnknown = it }
  text("Silencing leaves the call unanswered; it does not answer, reject, or forward it. Missing permission, errors, and lookup timeouts always allow ringing.",14)
  text("Try a contact lookup",21,true)
  input = EditText(this).apply { hint = "+91 mobile number"; inputType = android.text.InputType.TYPE_CLASS_PHONE; importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO }
  body.addView(input)
  button("Check number locally") { lookup() }
  result = text("No lookup yet. This test never places a call.",15)
  text("Team API preview",21,true)
  contract = text("Check a number to preview Member 3 and Member 4 payloads. Nothing is sent to a server.",14)
  text("Recent screening events",21,true)
  text("Only calls delivered to this screening service appear here. This is not your phone's complete call history.",14)
  button("Refresh events") { refreshState() }
  history = text("No calls screened yet.",15)
  button("Delete local event history") { store.clear(); refreshState() }
  text("Airtel forwarding is separate",21,true)
  text("This app does not activate or verify forwarding, answer with AI, record audio, or upload contacts. The phone-service integration must receive forwarded calls. Turning these controls off or uninstalling does not cancel carrier forwarding.",14)
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
   val match = ContactLookup(this).lookup(number,cancellation)
   main.post { if(token == generation) { generation++; result.text = "${label(match.status)}${match.displayName?.let { " · $it" } ?: ""}\n${PhoneNumbers.normalize(number) ?: "No usable phone number"}"
    val context = CallerContext.from(number, match)
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
   "${it.match.displayName ?: it.number ?: "Unavailable number"}\n${label(it.match.status)} · ${it.action.name.lowercase()}\n${DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT).format(Date(it.timestamp))} · ${it.reason}"
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
 private fun text(value: String,size: Int,bold: Boolean=false): TextView = TextView(this).apply {
  text=value;textSize=size.toFloat();setTextColor(Color.rgb(26,42,61));setPadding(0,dp(9),0,dp(9))
  if(bold) setTypeface(typeface,Typeface.BOLD)
  body.addView(this)
 }
 private fun button(value:String, action:()->Unit) { body.addView(Button(this).apply { text=value; isAllCaps=false; setOnClickListener { action() } }) }
 private fun toggle(value:String, checked:Boolean, change:(Boolean)->Unit) { body.addView(Switch(this).apply { text=value;isChecked=checked;setPadding(0,dp(12),0,dp(12));setOnCheckedChangeListener { _,v -> change(v) } }) }
 private fun toast(s:String) { Toast.makeText(this,s,Toast.LENGTH_LONG).show() }
 override fun onResume() { super.onResume(); main.post(refresh) }
 override fun onPause() { main.removeCallbacks(refresh);super.onPause() }
 override fun onDestroy() { generation++; main.removeCallbacksAndMessages(null); lookupCancellation?.cancel(); worker.shutdownNow(); super.onDestroy() }
}
