package com.upatriagem.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.upatriagem.app.ui.AvisoConexao
import com.upatriagem.app.ui.TelaInfo
import com.upatriagem.app.ui.TelaPrevisoes
import com.upatriagem.app.ui.TelaTriagem
import com.upatriagem.app.ui.TelaUnidades
import com.upatriagem.app.ui.TemaUpa
import org.osmdroid.config.Configuration

class MainActivity : ComponentActivity() {
    private val vm: AppViewModel by viewModels()

    private val pedirLocalizacao = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { concedidas -> if (concedidas.values.any { it }) obterLocalizacao() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Configuration.getInstance().userAgentValue = packageName

        if (temPermissaoLocalizacao()) {
            obterLocalizacao()
        } else {
            pedirLocalizacao.launch(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            )
        }

        setContent {
            TemaUpa {
                var aba by rememberSaveable { mutableIntStateOf(0) }
                Scaffold(
                    bottomBar = {
                        NavigationBar {
                            ABAS.forEachIndexed { i, (rotulo, icone) ->
                                NavigationBarItem(
                                    selected = aba == i,
                                    onClick = { aba = i },
                                    icon = { Icon(icone, contentDescription = rotulo) },
                                    label = { Text(rotulo) },
                                )
                            }
                        }
                    },
                ) { padding ->
                    Column(Modifier.fillMaxSize().padding(padding)) {
                        vm.erroConexao?.let { AvisoConexao(it, onTentarNovamente = vm::carregarTudo) }
                        when (aba) {
                            0 -> TelaTriagem(vm, irParaUnidades = { aba = 1 })
                            1 -> TelaUnidades(vm)
                            2 -> TelaPrevisoes(vm)
                            else -> TelaInfo(vm)
                        }
                    }
                }
            }
        }
    }

    private fun temPermissaoLocalizacao() = listOf(
        Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION
    ).any { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }

    @SuppressLint("MissingPermission")
    private fun obterLocalizacao() {
        if (!temPermissaoLocalizacao()) return
        val lm = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val provedores = lm.getProviders(true)
        provedores.mapNotNull { lm.getLastKnownLocation(it) }
            .maxByOrNull { it.time }
            ?.let { vm.definirLocalizacao(it.latitude, it.longitude) }
        val provedor = when {
            LocationManager.GPS_PROVIDER in provedores -> LocationManager.GPS_PROVIDER
            LocationManager.NETWORK_PROVIDER in provedores -> LocationManager.NETWORK_PROVIDER
            else -> return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            lm.getCurrentLocation(provedor, null, ContextCompat.getMainExecutor(this)) { loc ->
                if (loc != null) vm.definirLocalizacao(loc.latitude, loc.longitude)
            }
        } else {
            @Suppress("DEPRECATION")
            lm.requestSingleUpdate(provedor, { loc -> vm.definirLocalizacao(loc.latitude, loc.longitude) }, Looper.getMainLooper())
        }
    }

    companion object {
        private val ABAS = listOf(
            "Triagem" to Icons.Filled.Favorite,
            "Unidades" to Icons.Filled.LocationOn,
            "Previsões" to Icons.Filled.Warning,
            "Info" to Icons.Filled.Info,
        )
    }
}
