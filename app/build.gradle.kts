plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// CI passes -PversionCode=<run number> so every build is newer than the last and installs over it.
val ciVersionCode = (project.findProperty("versionCode") as String?)?.toIntOrNull() ?: 1
val ciVersionName = (project.findProperty("versionName") as String?) ?: "1.0"

android {
    namespace = "com.jarvis.phone"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.jarvis.phone"
        minSdk = 26
        targetSdk = 34
        versionCode = ciVersionCode
        versionName = ciVersionName
    }

    // One fixed key for every build (local and GitHub), so a new APK updates the old one
    // without uninstalling. It is a debug key: fine for your own phone, not for the Play Store.
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
