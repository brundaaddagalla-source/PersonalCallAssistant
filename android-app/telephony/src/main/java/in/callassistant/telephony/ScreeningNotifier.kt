package `in`.callassistant.telephony

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build

object ScreeningNotifier {
 fun show(context: Context, event: ScreeningEvent) {
  if (!AssistantPreferences(context).notifyCalls) return
  if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
  val manager = context.getSystemService(NotificationManager::class.java)
  if (!manager.areNotificationsEnabled()) return
  manager.createNotificationChannel(NotificationChannel("screened_calls", "Screened calls", NotificationManager.IMPORTANCE_DEFAULT))
  val intent = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
  intent.putExtra("open_inbox", true)
  val pending = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

  val callerNameOrNumber = event.match.displayName ?: event.number ?: "Unavailable number"
  val title = when {
   event.escalationRequested -> "⚠️ Urgent Call: $callerNameOrNumber"
   event.decisionAction == "take_message" && event.assistantResponse != null -> "Message from $callerNameOrNumber"
   event.action == ScreeningAction.SILENCE -> "Call silenced: $callerNameOrNumber"
   else -> "Call allowed: $callerNameOrNumber"
  }

  val text = when {
   event.assistantResponse != null -> event.assistantResponse
   event.action == ScreeningAction.SILENCE -> "Silenced by your local screening rules"
   else -> "Allowed to ring normally"
  }

  val notification = Notification.Builder(context, "screened_calls").setSmallIcon(android.R.drawable.sym_call_incoming)
   .setContentTitle(title)
   .setContentText(text)
   .setVisibility(Notification.VISIBILITY_PRIVATE)
   .setPublicVersion(Notification.Builder(context, "screened_calls").setSmallIcon(android.R.drawable.sym_call_incoming).setContentTitle("Call activity").setContentText("Open Personal Call Assistant for details").build())
   .setContentIntent(pending).setAutoCancel(true).build()
  manager.notify(event.id.hashCode(), notification)
 }
}
