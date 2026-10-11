plugins { id("com.android.application") }
android {
 namespace = "in.callassistant.demo"
 compileSdk = 36
 defaultConfig {
  minSdk = 29
  applicationId = "in.callassistant.member2"; targetSdk = 36; versionCode = 1; versionName = "0.1.0"
 }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
dependencies { implementation(project(":telephony")) }
