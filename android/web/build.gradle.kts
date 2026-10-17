import javax.inject.Inject

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// App Android da versão web: empacota o site estático (scripts/construir_site.py) e o abre
// num WebView. O backend Python roda no próprio celular (Pyodide), sem servidor.
android {
    namespace = "com.healthflow.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.healthflow.app"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("VERSAO_CODIGO") ?: "1").toInt()
        versionName = System.getenv("VERSAO_NOME") ?: "1.0"
    }

    signingConfigs {
        // No GitHub Actions a chave vem dos secrets; sem ela, o release usa a chave de debug.
        val keystore = System.getenv("ANDROID_KEYSTORE")
        if (keystore != null) {
            create("release") {
                storeFile = file(keystore)
                storePassword = System.getenv("ANDROID_KEYSTORE_SENHA")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS") ?: "healthflow"
                keyPassword = System.getenv("ANDROID_KEYSTORE_SENHA")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

/** Gera o site estático (index.html, JS, CSS e backend.zip) dentro dos assets do APK, em tela cheia. */
abstract class ConstruirSite @Inject constructor(private val exec: ExecOperations) : DefaultTask() {
    @get:InputDirectory @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val codigo: DirectoryProperty

    @get:InputFile @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val script: RegularFileProperty

    @get:OutputDirectory
    abstract val saida: DirectoryProperty

    @TaskAction
    fun construir() {
        val python = if (System.getProperty("os.name").lowercase().contains("windows")) "python" else "python3"
        exec.exec { commandLine(python, script.get().asFile.path, saida.get().dir("site").asFile.path, "--app") }
    }
}

val construirSite = tasks.register<ConstruirSite>("construirSite") {
    codigo.set(rootProject.layout.projectDirectory.dir("../app"))
    script.set(rootProject.layout.projectDirectory.file("../scripts/construir_site.py"))
    saida.set(layout.buildDirectory.dir("generated/site"))
}

androidComponents {
    onVariants { variante ->
        variante.sources.assets?.addGeneratedSourceDirectory(construirSite, ConstruirSite::saida)
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.webkit:webkit:1.12.1")
}
