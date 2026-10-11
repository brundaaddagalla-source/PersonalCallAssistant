@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
package `in`.callassistant.demo

import android.Manifest
import android.app.TimePickerDialog
import android.app.role.RoleManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.ContactsContract
import android.provider.Settings
import android.widget.Toast
import androidx.activity.SystemBarStyle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import `in`.callassistant.telephony.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.time.LocalDateTime
import java.util.Date

private val Blue=Color(0xFF1674ED)
private val Green=Color(0xFF148452)
private val Ink=Color(0xFF142137)
private val Muted=Color(0xFF59687D)
private val Shape=RoundedCornerShape(28.dp)
private data class Person(val name:String,val number:String)
private enum class Page(val label:String,val icon:ImageVector) {
 Calls("Recents",Icons.Outlined.History), Contacts("Contacts",Icons.Outlined.PeopleOutline),
 Keypad("Keypad",Icons.Outlined.Dialpad), Assistant("Assistant",Icons.Outlined.AutoAwesome), Settings("Settings",Icons.Outlined.Settings)
}
class MainActivity : ComponentActivity() {
 private var resumeVersion by mutableIntStateOf(0)
 override fun onCreate(savedInstanceState:Bundle?) {
  super.onCreate(savedInstanceState); enableEdgeToEdge()
  setContent { PhoneApp(resumeVersion,intent.getBooleanExtra("open_inbox",false)) }
 }
 override fun onResume() { super.onResume(); resumeVersion++ }
}

@Composable private fun PhoneApp(resumeVersion:Int,openInbox:Boolean) {
 val context=LocalContext.current
 val store=remember { TelephonyStore(context) };val prefs=remember { AssistantPreferences(context) }
 var pageName by rememberSaveable { mutableStateOf(Page.Calls.name) };val page=Page.valueOf(pageName)
 var appearance by remember { mutableStateOf(prefs.appearance) }
 val dark=appearance=="Dark" || (appearance=="System" && isSystemInDarkTheme())
 val scheme=if(dark) darkColorScheme(primary=Color(0xFF83B7FF),background=Color(0xFF0D1525),surface=Color(0xFF1D2A40),onSurface=Color(0xFFF0F4FF),onSurfaceVariant=Color(0xFFB9C6DB))
 else lightColorScheme(primary=Blue,background=Color(0xFFF4F6FC),surface=Color.White,onSurface=Ink,onSurfaceVariant=Muted)
 LaunchedEffect(dark) {
  (context as? ComponentActivity)?.enableEdgeToEdge(
   statusBarStyle=if(dark) SystemBarStyle.dark(android.graphics.Color.TRANSPARENT) else SystemBarStyle.light(android.graphics.Color.TRANSPARENT,android.graphics.Color.TRANSPARENT),
   navigationBarStyle=if(dark) SystemBarStyle.dark(android.graphics.Color.TRANSPARENT) else SystemBarStyle.light(android.graphics.Color.TRANSPARENT,android.graphics.Color.TRANSPARENT))
 }
 MaterialTheme(colorScheme=scheme) {
 CompositionLocalProvider(LocalContentColor provides scheme.onSurface) {
  var enabled by remember { mutableStateOf(store.enabled) }
  var silence by remember { mutableStateOf(store.silenceUnknown) }
  var schedule by remember { mutableStateOf(prefs.schedule) }
  var notify by remember { mutableStateOf(prefs.notifyCalls) }
  var events by remember { mutableStateOf(store.events()) }
  var contacts by remember { mutableStateOf(emptyList<Person>()) }
  var contactMessage by remember { mutableStateOf<String?>(null) }
  var loading by remember { mutableStateOf(false) }
  var permissionTick by remember { mutableIntStateOf(0) }
  var favorites by remember { mutableStateOf(prefs.favorites()) }
  var selectedPerson by remember { mutableStateOf<Person?>(null) }
  var selectedEvent by remember { mutableStateOf<ScreeningEvent?>(null) }
  var inbox by remember { mutableStateOf(openInbox) }
  var confirmClear by remember { mutableStateOf(false) }
  var rulesVersion by remember { mutableIntStateOf(0) }
  var now by remember { mutableStateOf(LocalDateTime.now()) }
  val roleManager=context.getSystemService(RoleManager::class.java)
  val hasContacts=remember(resumeVersion,permissionTick) { context.checkSelfPermission(Manifest.permission.READ_CONTACTS)==PackageManager.PERMISSION_GRANTED }
  val hasRole=remember(resumeVersion,permissionTick) { roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING) }
  val hasNotifications=remember(resumeVersion,permissionTick) { Build.VERSION.SDK_INT<33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED }
  val requestContacts=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permissionTick++ }
  val requestRole=rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { permissionTick++ }
  val requestNotifications=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { allowed -> notify=allowed;prefs.notifyCalls=allowed;permissionTick++ }
  val lifecycle=LocalLifecycleOwner.current.lifecycle
  LaunchedEffect(resumeVersion,permissionTick,hasContacts) {
   enabled=store.enabled;silence=store.silenceUnknown
   contacts=emptyList();contactMessage=null
   if(hasContacts) {
    loading=true
    val result=withContext(Dispatchers.IO) { runCatching {
     val rows=mutableListOf<Person>()
     context.contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
      arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,ContactsContract.CommonDataKinds.Phone.NUMBER),null,null,
      ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME+" COLLATE LOCALIZED ASC")?.use { c ->
       while(c.moveToNext()) { val number=PhoneNumbers.normalize(c.getString(1));if(number!=null) rows.add(Person(c.getString(0)?:number,number)) }
      } ?: error("Contacts are temporarily unavailable")
     rows.distinctBy { it.number }
    } }
    result.onSuccess { contacts=it }.onFailure { contactMessage="Could not load contacts. Check permission in Settings and try again." }
    loading=false
   } else loading=false
  }
  LaunchedEffect(lifecycle) {
   lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
    while(true) { events=store.events(); now=LocalDateTime.now();delay(2000) }
   }
  }
  fun dial(number:String) {
   try { context.startActivity(Intent(Intent.ACTION_DIAL,Uri.fromParts("tel",number,null))) }
   catch(_:android.content.ActivityNotFoundException) { Toast.makeText(context,"No phone app is available",Toast.LENGTH_SHORT).show() }
  }
  val askRole:()->Unit={ if(roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) requestRole.launch(roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING))
    else Toast.makeText(context,"Call screening is unavailable on this device",Toast.LENGTH_LONG).show() }
  val active=enabled && schedule.contains(now) && hasRole
  Box(Modifier.fillMaxSize()) {
   GlassBackground(dark)
   Column(Modifier.fillMaxSize().statusBarsPadding()) {
    Row(Modifier.fillMaxWidth().padding(horizontal=24.dp,vertical=8.dp),verticalAlignment=Alignment.CenterVertically) {
     Column(Modifier.weight(1f)) {
      Text("PERSONAL CALL ASSISTANT",fontSize=10.sp,letterSpacing=1.6.sp,fontWeight=FontWeight.SemiBold,color=MaterialTheme.colorScheme.onSurfaceVariant)
      Text(if(page==Page.Calls) "Phone" else page.label,fontSize=35.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1).sp,color=MaterialTheme.colorScheme.onSurface)
     }
     CircleButton(Icons.Outlined.NotificationsNone,"Open call notifications") { inbox=true }
    }
    Box(Modifier.weight(1f).fillMaxWidth()) {
     when(page) {
      Page.Calls -> CallsPage(events,contacts.filter { it.number in favorites },active,enabled,hasRole,
       {pageName=Page.Assistant.name},{selectedEvent=it},{selectedPerson=it},{dial(it)})
      Page.Contacts -> ContactsPage(contacts,hasContacts,loading,contactMessage,favorites,
       {requestContacts.launch(Manifest.permission.READ_CONTACTS)},{permissionTick++; /* contacts reloads after resume or permission change */
        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:${context.packageName}"))) },{selectedPerson=it})
      Page.Keypad -> KeypadPage { dial(it) }
      Page.Assistant -> AssistantPage(enabled,active,silence,schedule,hasRole,hasContacts,now,
       {enabled=it;store.enabled=it},{silence=it;store.silenceUnknown=it}, {schedule=it;prefs.schedule=it},askRole,
       {requestContacts.launch(Manifest.permission.READ_CONTACTS)},{pageName=Page.Contacts.name})
      Page.Settings -> SettingsPage(appearance,{appearance=it;prefs.appearance=it},notify,hasNotifications,
       { wanted -> if(wanted && Build.VERSION.SDK_INT>=33 && !hasNotifications) requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        else {notify=wanted;prefs.notifyCalls=wanted}},hasRole,hasContacts,askRole,
       {requestContacts.launch(Manifest.permission.READ_CONTACTS)}, {confirmClear=true},
       { context.startActivity(Intent(context,DiagnosticsActivity::class.java)) })
     }
    }
    GlassNavigation(page,{pageName=it.name},dark)
   }
  }
  if(selectedPerson!=null) {
   val person=selectedPerson!!
   val currentRule=remember(person,rulesVersion) { prefs.rule(person.number) }
   ModalBottomSheet(onDismissRequest={selectedPerson=null},containerColor=MaterialTheme.colorScheme.surface) {
    Column(Modifier.fillMaxWidth().padding(horizontal=24.dp).padding(bottom=28.dp),horizontalAlignment=Alignment.CenterHorizontally) {
     Avatar(person.name,68)
     Spacer(Modifier.height(12.dp));Text(person.name,fontSize=25.sp,fontWeight=FontWeight.Bold)
     Text(person.number,color=MaterialTheme.colorScheme.onSurfaceVariant)
     Row(Modifier.padding(vertical=20.dp),horizontalArrangement=Arrangement.spacedBy(12.dp)) {
      Button(onClick={dial(person.number)},shape=CircleShape) { Icon(Icons.Outlined.Call,null);Spacer(Modifier.width(8.dp));Text("Call") }
      OutlinedButton(onClick={prefs.toggleFavorite(person.number);favorites=prefs.favorites()}) {
       Icon(if(person.number in favorites) Icons.Outlined.Star else Icons.Outlined.StarBorder,null)
       Spacer(Modifier.width(6.dp));Text(if(person.number in favorites) "Favorited" else "Favorite")
      }
     }
     Text("WHEN ASSISTANT RULES ARE ACTIVE",Modifier.fillMaxWidth(),fontSize=11.sp,letterSpacing=1.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
     listOf(ContactRule.DEFAULT to "Use default rules",ContactRule.ALWAYS_RING to "Always ring",ContactRule.SILENCE to "Silence this contact").forEach { (rule,label) ->
      Row(Modifier.fillMaxWidth().clickable(role=Role.RadioButton) {prefs.setRule(person.number,rule);rulesVersion++}.padding(vertical=8.dp),verticalAlignment=Alignment.CenterVertically) {
       RadioButton(currentRule==rule,{prefs.setRule(person.number,rule);rulesVersion++});Text(label)
      }
     }
     Hint("Rules apply only during your active schedule. Silencing does not answer or forward a call.")
    }
   }
  }
  if(selectedEvent!=null) {
   val e=selectedEvent!!
   AlertDialog(onDismissRequest={selectedEvent=null},icon={Icon(Icons.Outlined.CallReceived,null)},
    title={Text(e.match.displayName?:e.number?:"Private caller")},
    text={Column(verticalArrangement=Arrangement.spacedBy(10.dp)) {
     Text(if(e.action==ScreeningAction.SILENCE) "Silenced by your local rules" else "Allowed to ring")
     Text(statusLabel(e.match.status));Text(DateFormat.getDateTimeInstance().format(Date(e.timestamp)))
     Hint("This is a screening event, not an AI conversation summary. No recording or transcript is available.")
    }},confirmButton={TextButton(onClick={selectedEvent=null}) {Text("Done")}},dismissButton={e.number?.let { number -> TextButton(onClick={dial(number)}) {Text("Call back")} }})
  }
  if(inbox) ModalBottomSheet(onDismissRequest={inbox=false},containerColor=MaterialTheme.colorScheme.surface) {
   Column(Modifier.fillMaxWidth().padding(horizontal=24.dp).padding(bottom=16.dp)) {
    Text("Notifications",fontSize=28.sp,fontWeight=FontWeight.Bold)
    Hint("Your latest local call activity. AI alerts will appear once the voice service is connected.")
    LazyColumn(Modifier.heightIn(max=420.dp)) {
     if(events.isEmpty()) item { EmptyState(Icons.Outlined.NotificationsNone,"You're all caught up","Screened calls will appear here.") }
     items(events.take(20),key={it.id}) { e -> EventRow(e,{inbox=false;selectedEvent=e}) }
    }
   }
  }
  if(confirmClear) AlertDialog(onDismissRequest={confirmClear=false},title={Text("Clear recent activity?")},text={Text("This removes this app's local screening history. Your phone's call log is not changed.")},confirmButton={TextButton(onClick={store.clear();events=emptyList();confirmClear=false}){Text("Clear")}},dismissButton={TextButton(onClick={confirmClear=false}){Text("Cancel")}})
 }
}
}

@Composable private fun GlassBackground(dark:Boolean) {
 Canvas(Modifier.fillMaxSize().background(if(dark) Color(0xFF0D1525) else Color(0xFFF4F6FB))) {
  drawCircle(Brush.radialGradient(listOf((if(dark) Color(0xFF244D79) else Color(0xFFCAE4FF)).copy(alpha=.75f),Color.Transparent),Offset(size.width*.95f,size.height*.10f),size.width*.95f),size.width*.95f,Offset(size.width*.95f,size.height*.10f))
  drawCircle(Brush.radialGradient(listOf((if(dark) Color(0xFF48326F) else Color(0xFFE2D8FB)).copy(alpha=.70f),Color.Transparent),Offset(0f,size.height*.58f),size.width*.95f),size.width*.95f,Offset(0f,size.height*.58f))
  drawCircle(Brush.radialGradient(listOf((if(dark) Color(0xFF1C5A59) else Color(0xFFD6F1EA)).copy(alpha=.55f),Color.Transparent),Offset(size.width,size.height),size.width),size.width,Offset(size.width,size.height))
 }
}
@Composable private fun GlassCard(modifier:Modifier=Modifier,content:@Composable ColumnScope.()->Unit) {
 val dark=MaterialTheme.colorScheme.background==Color(0xFF0D1525)
 Column(modifier.fillMaxWidth().shadow(8.dp,Shape,ambientColor=Blue.copy(alpha=.05f),spotColor=Blue.copy(alpha=.06f))
  .clip(Shape).background(Brush.verticalGradient(if(dark) listOf(Color(0xCC25344B),Color(0xA51B263B)) else listOf(Color(0xEFFFFFFF),Color(0xADFFFFFF))))
  .border(1.dp,if(dark) Color.White.copy(alpha=.16f) else Color.White.copy(alpha=.95f),Shape).padding(18.dp),content=content)
}
@Composable private fun GlassNavigation(page:Page,onSelect:(Page)->Unit,dark:Boolean) {
 Row(Modifier.navigationBarsPadding().padding(horizontal=14.dp,vertical=10.dp).fillMaxWidth()
  .shadow(18.dp,CircleShape,spotColor=Color(0x33264678)).clip(CircleShape)
  .background(if(dark) Color(0xEC26354B) else Color(0xECFFFFFF)).border(1.dp,Color.White.copy(alpha=.55f),CircleShape).padding(6.dp),horizontalArrangement=Arrangement.SpaceEvenly) {
  Page.entries.forEach { p ->
   val selected=page==p
   Column(Modifier.weight(1f).clip(CircleShape).background(if(selected) MaterialTheme.colorScheme.primary.copy(alpha=.12f) else Color.Transparent)
    .clickable(role=Role.Tab,onClick={onSelect(p)}).padding(vertical=10.dp),horizontalAlignment=Alignment.CenterHorizontally) {
    Icon(p.icon,p.label,tint=if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,modifier=Modifier.size(23.dp))
    Spacer(Modifier.height(4.dp));Text(p.label,fontSize=10.sp,fontWeight=if(selected) FontWeight.Bold else FontWeight.Medium,maxLines=1)
   }
  }
 }
}
@Composable private fun CircleButton(icon:ImageVector,label:String,onClick:()->Unit) {
 IconButton(onClick,Modifier.size(48.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surface.copy(alpha=.65f)).border(1.dp,Color.White.copy(alpha=.45f),CircleShape)) {Icon(icon,label,tint=MaterialTheme.colorScheme.primary)}
}
@Composable private fun Hint(text:String) { Text(text,fontSize=13.sp,lineHeight=19.sp,color=MaterialTheme.colorScheme.onSurfaceVariant,modifier=Modifier.padding(vertical=6.dp)) }
@Composable private fun Section(text:String) { Text(text,fontSize=19.sp,fontWeight=FontWeight.SemiBold,modifier=Modifier.padding(top=8.dp,bottom=10.dp)) }
@Composable private fun Avatar(name:String,size:Int=44) {
 val palettes=listOf(Color(0xFFDEE9FF),Color(0xFFE9DFF9),Color(0xFFD7EEE6),Color(0xFFFCE5D8))
 Box(Modifier.size(size.dp).clip(CircleShape).background(palettes[(name.hashCode() and Int.MAX_VALUE)%palettes.size]),contentAlignment=Alignment.Center) {
  Text(name.trim().split(" ").filter { it.isNotEmpty() }.take(2).map {it.first().uppercaseChar()}.joinToString(""),fontSize=(size*.32).sp,fontWeight=FontWeight.SemiBold,color=Ink)
 }
}
@Composable private fun EmptyState(icon:ImageVector,title:String,detail:String) {
 Column(Modifier.fillMaxWidth().padding(vertical=32.dp,horizontal=14.dp),horizontalAlignment=Alignment.CenterHorizontally) {
  Box(Modifier.size(66.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary.copy(alpha=.08f)),contentAlignment=Alignment.Center) {Icon(icon,null,tint=MaterialTheme.colorScheme.primary,modifier=Modifier.size(30.dp))}
  Spacer(Modifier.height(16.dp));Text(title,fontSize=19.sp,fontWeight=FontWeight.SemiBold,textAlign=TextAlign.Center)
  Spacer(Modifier.height(6.dp));Text(detail,fontSize=14.sp,lineHeight=21.sp,textAlign=TextAlign.Center,color=MaterialTheme.colorScheme.onSurfaceVariant)
 }
}
@Composable private fun Search(value:String,onChange:(String)->Unit,placeholder:String) {
 OutlinedTextField(value,onChange,Modifier.fillMaxWidth(),singleLine=true,shape=CircleShape,placeholder={Text(placeholder)},leadingIcon={Icon(Icons.Outlined.Search,null)},
  colors=OutlinedTextFieldDefaults.colors(unfocusedContainerColor=MaterialTheme.colorScheme.surface.copy(alpha=.60f),focusedContainerColor=MaterialTheme.colorScheme.surface.copy(alpha=.8f),unfocusedBorderColor=Color.Transparent,focusedBorderColor=MaterialTheme.colorScheme.primary.copy(alpha=.4f)))
}
@Composable private fun EventRow(e:ScreeningEvent,onClick:()->Unit) {
 Row(Modifier.fillMaxWidth().clickable(onClick=onClick).padding(vertical=13.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
  Avatar(e.match.displayName?:"?")
  Column(Modifier.weight(1f)) {
   Text(e.match.displayName?:e.number?:"Unavailable number",fontWeight=FontWeight.SemiBold,maxLines=1,overflow=TextOverflow.Ellipsis)
   Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(4.dp)) {
    Icon(if(e.action==ScreeningAction.SILENCE) Icons.Outlined.VolumeOff else Icons.Outlined.CallReceived,null,modifier=Modifier.size(13.dp),tint=MaterialTheme.colorScheme.onSurfaceVariant)
    Text(if(e.action==ScreeningAction.SILENCE) "Silenced" else "Allowed to ring",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
   }
  }
  Text(DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(e.timestamp)),fontSize=11.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
  Icon(Icons.Outlined.Info,"Call details",tint=MaterialTheme.colorScheme.primary,modifier=Modifier.size(21.dp))
 }
}
@Composable private fun CallsPage(events:List<ScreeningEvent>,favorites:List<Person>,active:Boolean,enabled:Boolean,role:Boolean,onAssistant:()->Unit,onEvent:(ScreeningEvent)->Unit,onPerson:(Person)->Unit,onDial:(String)->Unit) {
 var query by rememberSaveable { mutableStateOf("") };var onlySilenced by rememberSaveable {mutableStateOf(false)}
 val shown=events.filter { (!onlySilenced || it.action==ScreeningAction.SILENCE) && (it.number.orEmpty()+it.match.displayName.orEmpty()).contains(query,true) }
 LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(start=22.dp,end=22.dp,bottom=20.dp),verticalArrangement=Arrangement.spacedBy(14.dp)) {
  item {GlassCard(Modifier.clickable(onClick=onAssistant)) {
   Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
    Box(Modifier.size(42.dp).clip(CircleShape).background(Color(0xFFD9F3E6)),contentAlignment=Alignment.Center) {Icon(Icons.Outlined.AutoAwesome,null,tint=Green)}
    Column(Modifier.weight(1f)) {Text(if(active) "A little less interruption" else "Make room for your day",fontWeight=FontWeight.SemiBold,fontSize=16.sp)
     Text(if(active) "Local screening rules are active" else if(enabled && role) "Waiting for your next schedule" else "Set up your assistant",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
    Icon(Icons.Outlined.ChevronRight,null,tint=MaterialTheme.colorScheme.onSurfaceVariant)
   }
  }}
  if(favorites.isNotEmpty()) item {Section("Favorites");Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(18.dp)) {
   favorites.take(4).forEach {person -> Column(Modifier.weight(1f).clickable {onPerson(person)},horizontalAlignment=Alignment.CenterHorizontally) {
    Avatar(person.name,52);Spacer(Modifier.height(7.dp));Text(person.name.substringBefore(" "),fontSize=12.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
   }}
  }}
  item {Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {Text("Recents",Modifier.weight(1f),fontSize=24.sp,fontWeight=FontWeight.Bold)
   FilterChip(!onlySilenced,{onlySilenced=false},label={Text("All")});Spacer(Modifier.width(8.dp));FilterChip(onlySilenced,{onlySilenced=true},label={Text("Silenced")})}}
  item {Search(query,{query=it},"Search recent calls")}
  if(shown.isEmpty()) item {GlassCard {EmptyState(Icons.Outlined.History,if(events.isEmpty()) "Your next call starts here" else "No matching calls",if(events.isEmpty()) "Once screening is enabled, your call activity will appear here." else "Try another search or filter.")}}
  else items(shown,key={it.id}) { e -> GlassCard {EventRow(e,{onEvent(e)})} }
  item {Hint("Shows calls screened by this app, not your phone's full call history.")}
 }
}
@Composable private fun ContactsPage(contacts:List<Person>,permission:Boolean,loading:Boolean,error:String?,favorites:Set<String>,request:()->Unit,retry:()->Unit,select:(Person)->Unit) {
 var query by rememberSaveable {mutableStateOf("")};val shown=contacts.filter {(it.name+it.number).contains(query,true)}
 LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(22.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
  item {Search(query,{query=it},"Search contacts")}
  if(!permission) item {GlassCard {EmptyState(Icons.Outlined.PeopleOutline,"Keep your people close","Allow contact access to see your address book and set personal call rules.");Button(request,Modifier.fillMaxWidth(),shape=CircleShape){Text("Allow contacts")};Hint("Contacts stay on your phone. Nothing is uploaded.")}}
  else if(loading) item {Box(Modifier.fillMaxWidth().padding(40.dp),contentAlignment=Alignment.Center){CircularProgressIndicator()}}
  else if(error!=null) item {GlassCard {Text(error);TextButton(retry){Text("Open app settings")}}}
  else if(shown.isEmpty()) item {GlassCard {EmptyState(Icons.Outlined.PersonOutline,"No contacts found",if(query.isBlank()) "Add a contact in your phone's Contacts app, then return here." else "Try a name or phone number.")}}
  else {
   item {Hint("${shown.size} numbers · tap a contact to set a rule")}
   items(shown,key={it.number}) { p ->
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(MaterialTheme.colorScheme.surface.copy(alpha=.6f)).clickable {select(p)}.padding(14.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
     Avatar(p.name);Column(Modifier.weight(1f)){Text(p.name,fontWeight=FontWeight.SemiBold);Text(p.number,fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
     if(p.number in favorites) Icon(Icons.Outlined.Star,"Favorite",tint=Color(0xFFB37E13),modifier=Modifier.size(18.dp))
     Icon(Icons.Outlined.ChevronRight,null,tint=MaterialTheme.colorScheme.onSurfaceVariant)
    }
   }
  }
 }
}
@Composable private fun KeypadPage(dial:(String)->Unit) {
 var number by rememberSaveable {mutableStateOf("")}
 Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal=34.dp,vertical=10.dp),horizontalAlignment=Alignment.CenterHorizontally) {
  Spacer(Modifier.height(14.dp))
  Text(number.ifEmpty {"Enter a number"},fontSize=if(number.length>15) 24.sp else 30.sp,fontWeight=FontWeight.Normal,color=if(number.isEmpty()) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,textAlign=TextAlign.Center,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp),maxLines=2)
  Text("Call with your phone app",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant,modifier=Modifier.padding(bottom=24.dp))
  val keys=listOf("1" to "", "2" to "ABC", "3" to "DEF", "4" to "GHI", "5" to "JKL", "6" to "MNO", "7" to "PQRS", "8" to "TUV", "9" to "WXYZ", "*" to "", "0" to "+", "#" to "")
  keys.chunked(3).forEach { row ->
   Row(Modifier.fillMaxWidth().padding(vertical=7.dp),horizontalArrangement=Arrangement.SpaceEvenly) {
    row.forEach { (digit,letters) ->
     Column(Modifier.size(76.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surface.copy(alpha=.75f)).border(1.dp,Color.White.copy(alpha=.45f),CircleShape)
      .combinedClickable(role=Role.Button,onClick={if(number.length<30) number+=digit},onLongClick={if(digit=="0" && number.isEmpty())number="+"}),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Center) {
      Text(digit,fontSize=32.sp,fontWeight=FontWeight.Normal);if(letters.isNotEmpty())Text(letters,fontSize=10.sp,letterSpacing=2.sp,fontWeight=FontWeight.Medium)
     }
    }
   }
  }
  Row(Modifier.fillMaxWidth().padding(top=18.dp),horizontalArrangement=Arrangement.SpaceEvenly,verticalAlignment=Alignment.CenterVertically) {
   Spacer(Modifier.size(64.dp))
   FilledIconButton(onClick={dial(number)},enabled=number.isNotEmpty(),modifier=Modifier.size(76.dp),colors=IconButtonDefaults.filledIconButtonColors(containerColor=Color(0xFF22AC63),contentColor=Color.White)) {Icon(Icons.Outlined.Call,"Call number",Modifier.size(33.dp))}
   IconButton(onClick={number=number.dropLast(1)},Modifier.size(64.dp),enabled=number.isNotEmpty()) {Icon(Icons.Outlined.Backspace,"Delete last digit")}
  }
  Spacer(Modifier.height(12.dp));TextButton(onClick={number=""},enabled=number.isNotEmpty()) {Text("Clear number")}
 }
}
@Composable private fun ToggleRow(title:String,subtitle:String,checked:Boolean,onChange:(Boolean)->Unit) {
 Row(Modifier.fillMaxWidth().padding(vertical=8.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
  Column(Modifier.weight(1f)) {Text(title,fontWeight=FontWeight.SemiBold,fontSize=16.sp);if(subtitle.isNotEmpty())Text(subtitle,fontSize=12.sp,lineHeight=17.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
  Switch(checked,onChange,modifier=Modifier.semantics {contentDescription=title},colors=SwitchDefaults.colors(checkedTrackColor=Green,checkedThumbColor=Color.White))
 }
}
@Composable private fun AssistantPage(enabled:Boolean,active:Boolean,silence:Boolean,schedule:QuietSchedule,role:Boolean,contacts:Boolean,now:LocalDateTime,
 setEnabled:(Boolean)->Unit,setSilence:(Boolean)->Unit,setSchedule:(QuietSchedule)->Unit,askRole:()->Unit,askContacts:()->Unit,openContacts:()->Unit) {
 val context=LocalContext.current
 fun pick(start:Boolean) {val t=if(start)schedule.start else schedule.end; TimePickerDialog(context,{_,h,m ->setSchedule(if(start)schedule.copy(start=h*60+m) else schedule.copy(end=h*60+m))},t/60,t%60,true).show()}
 LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(start=22.dp,end=22.dp,bottom=20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
  item {
   Box(Modifier.fillMaxWidth().clip(Shape).background(Brush.linearGradient(listOf(Color(0xFF143C65),Color(0xFF354674),Color(0xFF4C4275)))).border(1.dp,Color.White.copy(alpha=.4f),Shape)) {
    Canvas(Modifier.matchParentSize()) {
     drawCircle(Brush.radialGradient(listOf(Color(0xBB83DEF1),Color(0x507C9EFF),Color.Transparent),Offset(size.width*.85f,size.height*.30f),size.width*.47f),size.width*.47f,Offset(size.width*.85f,size.height*.30f))
     drawCircle(Color.White.copy(alpha=.14f),size.width*.18f,Offset(size.width*.84f,size.height*.33f))
     drawCircle(Color.White.copy(alpha=.12f),size.width*.13f,Offset(size.width*.84f,size.height*.33f),style=androidx.compose.ui.graphics.drawscope.Stroke(2.dp.toPx()))
    }
    Column(Modifier.padding(24.dp)) {
     Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(6.dp)){Icon(Icons.Outlined.AutoAwesome,null,tint=Color(0xFFA5F1DD),modifier=Modifier.size(17.dp));Text("YOUR TIME, PROTECTED",fontSize=10.sp,letterSpacing=1.2.sp,color=Color(0xFFE0EDFF),fontWeight=FontWeight.SemiBold)}
     Spacer(Modifier.height(23.dp));Text("A little more\nquiet time.",fontSize=33.sp,lineHeight=37.sp,fontWeight=FontWeight.SemiBold,color=Color.White,letterSpacing=(-.7).sp)
     Spacer(Modifier.height(18.dp));Text(if(active) "Local rules are active" else if(enabled && role) "Outside your quiet hours" else "Choose how calls reach you",color=Color(0xFFD6E9F5),fontSize=13.sp)
    }
   }
  }
  item {GlassCard {
   ToggleRow("Assistant mode","Applies your local screening rules",enabled,setEnabled)
   HorizontalDivider(color=MaterialTheme.colorScheme.onSurface.copy(alpha=.08f))
   ToggleRow("Silence unknown callers","Only numbers confirmed absent from contacts",silence,setSilence)
   Hint("AI answering isn't connected yet. These controls do not turn Airtel forwarding on or off.")
  }}
  if(!role || !contacts) item {GlassCard {
   Text("Finish your setup",fontSize=18.sp,fontWeight=FontWeight.SemiBold)
   if(!role) ActionRow(Icons.Outlined.VerifiedUser,"Enable call screening","Choose this app in Android settings",askRole)
   if(!contacts) ActionRow(Icons.Outlined.Contacts,"Allow contacts","Recognize saved callers on this phone",askContacts)
  }}
  item {GlassCard {
   ToggleRow("Quiet hours","Run rules only during your schedule",schedule.enabled,{setSchedule(schedule.copy(enabled=it))})
   AnimatedVisibility(schedule.enabled) {Column {
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(12.dp)) {
     TimeTile("FROM",schedule.start,Modifier.weight(1f)){pick(true)}
     TimeTile("UNTIL",schedule.end,Modifier.weight(1f)){pick(false)}
    }
    Spacer(Modifier.height(16.dp))
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
     listOf("M","T","W","T","F","S","S").forEachIndexed {i,label ->
      val selected=i+1 in schedule.days
      Box(Modifier.sizeIn(minWidth=38.dp,minHeight=48.dp).clip(CircleShape).background(if(selected) MaterialTheme.colorScheme.primary.copy(alpha=.14f) else Color.Transparent)
       .semantics {contentDescription=listOf("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")[i];stateDescription=if(selected) "Selected" else "Not selected"}.clickable(role=Role.Checkbox) {setSchedule(schedule.copy(days=if(selected) schedule.days-(i+1) else schedule.days+(i+1)))},contentAlignment=Alignment.Center) {
       Text(label,fontWeight=FontWeight.SemiBold,color=if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
      }
     }
    }
    Hint(if(schedule.days.isEmpty()) "Choose at least one day. Rules will stay off until you do." else if(schedule.start==schedule.end) "Same start and end means all day on selected days." else if(schedule.start>schedule.end) "Ends the next morning. Days refer to when quiet hours start." else "Uses your phone's local time. Assistant mode must also be on.")
   }}
  }}
  item {GlassCard {ActionRow(Icons.Outlined.Tune,"Contact rules","Always ring, silence, or use your default",openContacts)}}
 }
}
@Composable private fun TimeTile(label:String,minutes:Int,modifier:Modifier,onClick:()->Unit) {
 Column(modifier.clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.primary.copy(alpha=.06f)).clickable(onClick=onClick).padding(16.dp)) {
  Text(label,fontSize=10.sp,letterSpacing=1.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
  Text("%02d:%02d".format(minutes/60,minutes%60),fontSize=25.sp,fontWeight=FontWeight.Medium)
 }
}
@Composable private fun ActionRow(icon:ImageVector,title:String,detail:String,action:()->Unit) {
 Row(Modifier.fillMaxWidth().clickable(onClick=action).padding(vertical=13.dp),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
  Icon(icon,null,tint=MaterialTheme.colorScheme.primary,modifier=Modifier.size(22.dp))
  Column(Modifier.weight(1f)) {Text(title,fontSize=15.sp,fontWeight=FontWeight.Medium);if(detail.isNotEmpty())Text(detail,fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
  Icon(Icons.Outlined.ChevronRight,null,tint=MaterialTheme.colorScheme.onSurfaceVariant)
 }
}
@Composable private fun SettingsPage(appearance:String,setAppearance:(String)->Unit,notify:Boolean,notificationPermission:Boolean,setNotify:(Boolean)->Unit,role:Boolean,contacts:Boolean,askRole:()->Unit,askContacts:()->Unit,clear:()->Unit,diagnostics:()->Unit) {
 val context=LocalContext.current
 LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(start=22.dp,end=22.dp,bottom=20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
  item {GlassCard {Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(14.dp)) {
   Box(Modifier.size(54.dp).clip(CircleShape).background(Brush.linearGradient(listOf(Blue,Color(0xFF8975E4)))),contentAlignment=Alignment.Center){Icon(Icons.Outlined.AutoAwesome,null,tint=Color.White,modifier=Modifier.size(26.dp))}
   Column {Text("Personal Call Assistant",fontWeight=FontWeight.SemiBold,fontSize=17.sp);Text("Your phone. Your pace.",fontSize=13.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
  }}}
  item {GlassCard {
   Text("Appearance",fontSize=17.sp,fontWeight=FontWeight.SemiBold)
   Row(Modifier.fillMaxWidth().padding(top=10.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
    listOf("System","Light","Dark").forEach {v -> FilterChip(appearance==v,{setAppearance(v)},label={Text(v)},modifier=Modifier.weight(1f))}
   }
   Hint("Glass-inspired surfaces adapt to your chosen theme.")
  }}
  item {GlassCard {
   ToggleRow("Call notifications",if(notificationPermission) "Alerts after local screening" else "Requires Android notification permission",notify && notificationPermission,setNotify)
   ActionRow(Icons.Outlined.NotificationsNone,"Notification settings","Manage sound and visibility") {context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,context.packageName))}
  }}
  item {GlassCard {
   Text("Permissions & privacy",fontSize=17.sp,fontWeight=FontWeight.SemiBold)
   ActionRow(Icons.Outlined.VerifiedUser,"Call screening",if(role) "Enabled" else "Not enabled",askRole)
   ActionRow(Icons.Outlined.Contacts,"Contact access",if(contacts) "Allowed · stays on this device" else "Not allowed",askContacts)
   ActionRow(Icons.Outlined.Settings,"Android app settings","Manage or revoke permissions") {context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:${context.packageName}")))}
   ActionRow(Icons.Outlined.DeleteOutline,"Clear recent activity","Remove this app's local history",clear)
  }}
  item {GlassCard {
   Text("Connection status",fontSize=17.sp,fontWeight=FontWeight.SemiBold)
   Hint("Airtel forwarding: not verified\nAI voice service: not connected\nCall takeover: not connected")
   Hint("Turning Assistant mode off or uninstalling this app does not disable carrier forwarding. Manage forwarding separately with your carrier.")
  }}
  item {GlassCard {ActionRow(Icons.Outlined.Code,"Developer diagnostics","Member 2 contact lookup and payload preview",diagnostics)}}
  item {Text("PERSONAL CALL ASSISTANT  ·  0.2.0",Modifier.fillMaxWidth().padding(8.dp),textAlign=TextAlign.Center,fontSize=10.sp,letterSpacing=1.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
 }
}
private fun statusLabel(status:ContactStatus)=when(status) {
 ContactStatus.SAVED -> "Saved contact"
 ContactStatus.NOT_SAVED -> "Number not saved in contacts"
 ContactStatus.PERMISSION_DENIED -> "Contacts permission unavailable"
 ContactStatus.NUMBER_UNAVAILABLE -> "Caller number unavailable"
 ContactStatus.LOOKUP_FAILED -> "Contact lookup failed; call allowed"
 ContactStatus.TIMED_OUT -> "Contact lookup timed out; call allowed"
}
