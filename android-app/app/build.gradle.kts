plugins { id("com.android.application"); id("org.jetbrains.kotlin.plugin.compose") }
android {
 namespace = "in.callassistant.demo"
 compileSdk = 36
 buildFeatures { compose = true }
 testOptions { unitTests.isIncludeAndroidResources = true }
 defaultConfig {
  minSdk = 29
  applicationId = "in.callassistant.member2"; targetSdk = 36; versionCode = 2; versionName = "0.2.0"
 }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
dependencies {
 implementation(project(":telephony"))
 implementation(platform("androidx.compose:compose-bom:2025.08.00"))
 implementation("androidx.activity:activity-compose:1.10.1")
 implementation("androidx.compose.ui:ui")
 implementation("androidx.compose.ui:ui-tooling-preview")
 implementation("androidx.compose.material3:material3")
 implementation("androidx.compose.material:material-icons-extended")
 implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.3")
 debugImplementation("androidx.compose.ui:ui-tooling")
 debugImplementation("androidx.compose.ui:ui-test-manifest")
 testImplementation("androidx.compose.ui:ui-test-junit4")
 testImplementation("junit:junit:4.13.2")
 testImplementation("org.robolectric:robolectric:4.15.1")
}

// Resolve the test SDK through Gradle instead of writing into the user's home directory.
val robolectricSdk by configurations.creating
 dependencies { robolectricSdk("org.robolectric:android-all-instrumented:15-robolectric-12650502-i7") }
val prepareRobolectricSdk by tasks.registering(Copy::class) {
 from(robolectricSdk)
 into(layout.buildDirectory.dir("robolectric-sdk"))
}
tasks.withType<Test>().configureEach {
 dependsOn(prepareRobolectricSdk)
 systemProperty("robolectric.offline", "true")
 systemProperty("robolectric.dependency.dir", layout.buildDirectory.dir("robolectric-sdk").get().asFile.absolutePath)
}
