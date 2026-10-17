pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "HealthFlow"
include(":app")
// App que empacota a versão web (o backend roda no próprio celular, sem servidor). Gera o APK publicado.
include(":web")
