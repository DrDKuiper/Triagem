package com.healthflow.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.webkit.GeolocationPermissions
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.widget.LinearLayout
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updateLayoutParams
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewClientCompat

/**
 * Abre o app (assets/site, gerado por scripts/construir_site.py --app) em tela cheia num WebView.
 * Os arquivos são servidos em https://appassets.androidplatform.net para que a página tenha
 * origem segura (Web Worker, geolocalização) sem precisar de servidor.
 */
class MainActivity : ComponentActivity() {

    private lateinit var web: WebView
    private var pedidoLocalizacao: Pair<String, GeolocationPermissions.Callback>? = null

    private val pedirPermissao =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { resultado ->
            pedidoLocalizacao?.let { (origem, callback) -> callback.invoke(origem, resultado.values.any { it }, false) }
            pedidoLocalizacao = null
        }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val carregador = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        // Barra de status na cor do app; embaixo, a cor da barra de navegação do app (claro/escuro).
        val noturno = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
        val corSuperficie = if (noturno) Color.parseColor("#1C2220") else Color.WHITE
        val barraStatus = View(this).apply { setBackgroundColor(Color.parseColor(COR_PRIMARIA)) }
        web = WebView(this).apply { setBackgroundColor(corSuperficie) }
        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(corSuperficie)
            addView(barraStatus, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0))
            addView(web, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(raiz)
        WindowCompat.getInsetsController(window, raiz).apply {
            isAppearanceLightStatusBars = false
            isAppearanceLightNavigationBars = !noturno
        }
        ViewCompat.setOnApplyWindowInsetsListener(raiz) { v, insets ->
            val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val teclado = insets.getInsets(WindowInsetsCompat.Type.ime())
            barraStatus.updateLayoutParams { height = barras.top }
            v.setPadding(barras.left, 0, barras.right, maxOf(barras.bottom, teclado.bottom))
            WindowInsetsCompat.CONSUMED
        }

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            setGeolocationEnabled(true)
        }
        web.webViewClient = object : WebViewClientCompat() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                carregador.shouldInterceptRequest(request.url)

            // Telefones (tel:) e rotas no mapa abrem nos apps do celular.
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (request.url.host == HOST) return false
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, request.url))
                } catch (_: ActivityNotFoundException) {
                }
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(origem: String, callback: GeolocationPermissions.Callback) {
                val concedida = ContextCompat.checkSelfPermission(
                    this@MainActivity, Manifest.permission.ACCESS_FINE_LOCATION,
                ) == PackageManager.PERMISSION_GRANTED
                if (concedida) {
                    callback.invoke(origem, true, false)
                } else {
                    pedidoLocalizacao = origem to callback
                    pedirPermissao.launch(
                        arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
                    )
                }
            }
        }

        onBackPressedDispatcher.addCallback(this) {
            if (web.canGoBack()) web.goBack() else finish()
        }

        if (savedInstanceState == null || web.restoreState(savedInstanceState) == null) {
            web.loadUrl("https://$HOST/assets/site/index.html")
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    private companion object {
        const val HOST = WebViewAssetLoader.DEFAULT_DOMAIN
        const val COR_PRIMARIA = "#0B6E4F"
    }
}
