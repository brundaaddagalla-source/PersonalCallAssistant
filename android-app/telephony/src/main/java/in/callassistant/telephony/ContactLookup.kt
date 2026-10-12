package `in`.callassistant.telephony

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.CancellationSignal
import android.os.OperationCanceledException
import android.provider.ContactsContract

class ContactLookup(context: Context) {
 private val app = context.applicationContext
 fun lookup(number: String?, cancellation: CancellationSignal = CancellationSignal()): ContactMatch {
  val normalized = PhoneNumbers.normalize(number) ?: return ContactMatch(ContactStatus.NUMBER_UNAVAILABLE)
  if (app.checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED)
   return ContactMatch(ContactStatus.PERMISSION_DENIED)
  return try {
   val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(normalized))
   app.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null, cancellation)?.use {
    if (it.moveToFirst()) ContactMatch(ContactStatus.SAVED, it.getString(0)) else ContactMatch(ContactStatus.NOT_SAVED)
   } ?: ContactMatch(ContactStatus.LOOKUP_FAILED)
  } catch (_: SecurityException) { ContactMatch(ContactStatus.PERMISSION_DENIED)
  } catch (_: OperationCanceledException) { ContactMatch(ContactStatus.TIMED_OUT)
  } catch (_: RuntimeException) { ContactMatch(ContactStatus.LOOKUP_FAILED) }
 }
}
