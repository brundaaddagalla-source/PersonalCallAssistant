package `in`.callassistant.demo

import android.graphics.Bitmap
import android.graphics.Canvas
import org.junit.Assert.assertTrue
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.core.app.ApplicationProvider
import android.content.Context
import `in`.callassistant.telephony.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[35], qualifiers="w411dp-h891dp-420dpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class PhoneUiTest {
 @get:Rule val compose=createAndroidComposeRule<MainActivity>()
 private fun snapshot(name:String) {
  compose.waitForIdle()
  val view=compose.activity.window.decorView
  val bitmap=Bitmap.createBitmap(view.width,view.height,Bitmap.Config.ARGB_8888)
  compose.runOnIdle { view.draw(Canvas(bitmap)) }
  val file=File("build/ui-previews/$name.png");file.parentFile?.mkdirs()
  file.outputStream().use {bitmap.compress(Bitmap.CompressFormat.PNG,100,it)}
 }
 @Test fun navigationPreferencesAndKeypad() {
  val context=ApplicationProvider.getApplicationContext<Context>()
  context.getSharedPreferences("assistant_ui",Context.MODE_PRIVATE).edit().clear().commit()
  context.getSharedPreferences("member2_telephony",Context.MODE_PRIVATE).edit().clear().commit()
  compose.activityRule.scenario.recreate()
  compose.onNodeWithText("Phone").assertIsDisplayed()
  snapshot("recents")
  compose.onNodeWithText("Keypad").performClick()
  compose.onNodeWithText("2",useUnmergedTree=true).performClick()
  compose.onNodeWithText("5",useUnmergedTree=true).performClick()
  compose.onNodeWithText("25",useUnmergedTree=true).assertIsDisplayed()
  compose.onNodeWithContentDescription("Delete last digit").performClick()
  snapshot("keypad")
  compose.onNodeWithText("Clear number").performClick()
  compose.onNodeWithText("Enter a number").assertIsDisplayed()
  compose.onNodeWithText("Assistant").performClick()
  compose.onNodeWithContentDescription("Assistant mode").performClick()
  assertTrue(TelephonyStore(context).enabled)
  snapshot("assistant")
  compose.onNodeWithText("Settings").performClick()
  compose.onNodeWithText("Dark").performClick()
  snapshot("settings-dark")
  compose.activityRule.scenario.recreate()
  assertTrue(AssistantPreferences(context).appearance=="Dark")
  assertTrue(TelephonyStore(context).enabled)
  compose.onNodeWithText("Light").performClick()
  compose.onNodeWithText("Contacts").performClick()
  compose.onNodeWithText("Allow contacts").assertIsDisplayed()
 }
}
