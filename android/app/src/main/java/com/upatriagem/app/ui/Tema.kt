package com.upatriagem.app.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val Verde = Color(0xFF0B6E4F)

@Composable
fun TemaUpa(conteudo: @Composable () -> Unit) {
    val cores = if (isSystemInDarkTheme()) {
        darkColorScheme(primary = Color(0xFF6FD3A8), secondary = Color(0xFF8BC7FF))
    } else {
        lightColorScheme(primary = Verde, secondary = Color(0xFF1565C0))
    }
    MaterialTheme(colorScheme = cores, content = conteudo)
}

/** Cores da classificação de risco (Protocolo de Manchester). */
fun corPrioridade(prioridade: String): Color = when (prioridade) {
    "vermelho" -> Color(0xFFD32F2F)
    "laranja" -> Color(0xFFF57C00)
    "amarelo" -> Color(0xFFFBC02D)
    "verde" -> Color(0xFF388E3C)
    else -> Color(0xFF1976D2)
}

fun corNivel(nivel: String): Color = when (nivel) {
    "epidemia" -> Color(0xFFD32F2F)
    "alerta" -> Color(0xFFF57C00)
    "esperado" -> Color(0xFFFBC02D)
    else -> Color(0xFF388E3C)
}

fun corLotacao(lotacao: String): Color = when (lotacao) {
    "alta" -> Color(0xFFD32F2F)
    "moderada" -> Color(0xFFF57C00)
    "baixa" -> Color(0xFF388E3C)
    else -> Color.Gray
}

fun textoSobre(fundo: Color): Color =
    if (fundo.red * 0.299f + fundo.green * 0.587f + fundo.blue * 0.114f > 0.6f) Color.Black else Color.White

fun ligar(contexto: Context, numero: String) {
    runCatching { contexto.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + numero.filter { it.isDigit() }))) }
}

fun abrirRota(contexto: Context, lat: Double, lon: Double, nome: String) {
    val uri = Uri.parse("geo:$lat,$lon?q=$lat,$lon(${Uri.encode(nome)})")
    // Sem app de mapas instalado (comum no emulador), abre o OpenStreetMap no navegador.
    runCatching { contexto.startActivity(Intent(Intent.ACTION_VIEW, uri)) }.onFailure {
        val web = Uri.parse("https://www.openstreetmap.org/?mlat=$lat&mlon=$lon#map=17/$lat/$lon")
        runCatching { contexto.startActivity(Intent(Intent.ACTION_VIEW, web)) }
    }
}

@Composable
fun AvisoConexao(mensagem: String, onTentarNovamente: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(mensagem, style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onTentarNovamente) { Text("Tentar novamente") }
        }
    }
}
