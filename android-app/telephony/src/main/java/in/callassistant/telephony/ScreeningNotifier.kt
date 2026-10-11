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
 fun show(context: Context,event: ScreeningEvent) {
  if(!AssistantPreferences(context).notifyCalls) return
  if(Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
  val manager=context.getSystemService(NotificationManager::class.java)
  if(!manager.areNotificationsEnabled()) return
  manager.createNotificationChannel(NotificationChannel("screened_calls","Screened calls",NotificationManager.IMPORTANCE_DEFAULT))
  val intent=context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
  intent.putExtra("open_inbox",true)
  val pending=PendingIntent.getActivity(context,0,intent,PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
  val notification=Notification.Builder(context,"screened_calls").setSmallIcon(android.R.drawable.sym_call_incoming)
   .setContentTitle(if(event.action==ScreeningAction.SILENCE) "Call silenced" else "Call allowed")
   .setContentText(event.match.displayName ?: event.number ?: "Number unavailable")
   .setVisibility(Notification.VISIBILITY_PRIVATE)
   .setPublicVersion(Notification.Builder(context,"screened_calls").setSmallIcon(android.R.drawable.sym_call_incoming).setContentTitle("Call activity").setContentText("Open Personal Call Assistant for details").build())
   .setContentIntent(pending).setAutoCancel(true).build()
  manager.notify(event.id.hashCode(),notification)
 }
}
