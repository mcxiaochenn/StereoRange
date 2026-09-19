plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "io.github.mcxiaochenn.stereorange"
    compileSdk = (System.getenv("ANDROID_COMPILE_SDK") ?: "37").toInt()
    ndkVersion = "28.2.13676358"

    if (System.getenv("STEREORANGE_PUBLIC_RELEASE") == "true") {
        // 公开产物使用隔离目录，绝不扫描本机 assets/private 中的个人标定。
        sourceSets.getByName("main").assets.setSrcDirs(listOf(rootProject.file("../.native/public-assets")))
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "io.github.mcxiaochenn.stereorange"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 33
        targetSdk = 37
        ndk { abiFilters += if (providers.gradleProperty("target-platform").orNull == "android-x64") "x86_64" else "arm64-v8a" }
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // 正式发布由仓库外的个人密钥签名，不使用调试密钥冒充 Release。
            val keyPath = System.getenv("STEREORANGE_KEYSTORE")
            if (!keyPath.isNullOrBlank()) {
                signingConfig = signingConfigs.create("personalRelease") {
                    storeFile = file(keyPath)
                    storePassword = System.getenv("STEREORANGE_STORE_PASSWORD")
                    keyAlias = System.getenv("STEREORANGE_KEY_ALIAS")
                    keyPassword = System.getenv("STEREORANGE_KEY_PASSWORD")
                }
            }
        }
    }
}

dependencies {
    implementation("com.herohan:UVCAndroid:1.0.13")
}

tasks.register("verifyNativeLibraries") {
    doLast {
        val abi = if (providers.gradleProperty("target-platform").orNull == "android-x64") "x86_64" else "arm64-v8a"
        check(file("src/main/jniLibs/$abi/libstereorange_native.so").isFile) {
            "请先运行 mobile/tool/build-native.ps1 构建 Rust 原生库。"
        }
    }
}
tasks.named("preBuild") { dependsOn("verifyNativeLibraries") }

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
