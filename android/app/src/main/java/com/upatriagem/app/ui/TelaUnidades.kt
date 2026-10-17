package com.upatriagem.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.upatriagem.app.AppViewModel
import com.upatriagem.app.data.Ponto
import com.upatriagem.app.data.Unidade
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker

@Composable
fun TelaUnidades(vm: AppViewModel) {
    val resposta = vm.unidades
    val centro = vm.localizacao ?: vm.config?.centroMapa
    LazyColumn(
        Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Column {
                Row(Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Atendimentos agora", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        vm.config?.municipio?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    }
                    IconButton(onClick = { vm.atualizarUnidades() }) { Icon(Icons.Filled.Refresh, "Atualizar") }
                }
                if (vm.carregandoUnidades) LinearProgressIndicator(Modifier.fillMaxWidth())
            }
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("UPA", "PS", "UBS").forEach { tipo ->
                    Card(Modifier.weight(1f)) {
                        Column(Modifier.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(tipo, fontWeight = FontWeight.Bold)
                            Text(
                                "${resposta?.emAtendimentoPorTipo?.get(tipo) ?: "–"}",
                                style = MaterialTheme.typography.headlineMedium,
                            )
                            Text("em atendimento", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
        item {
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("UPA", "PS", "UBS").forEach { tipo ->
                    FilterChip(
                        selected = tipo in vm.filtroTipos,
                        onClick = { vm.alternarFiltro(tipo) },
                        label = { Text(tipo) },
                    )
                }
            }
        }
        if (centro != null) {
            item {
                Mapa(
                    centro = centro,
                    usuario = vm.localizacao,
                    unidades = resposta?.unidades.orEmpty(),
                    modifier = Modifier.fillMaxWidth().height(280.dp).padding(horizontal = 16.dp),
                )
            }
        }
        item {
            Text(
                "Ordenadas pelo menor tempo total (deslocamento + espera). Atualiza a cada 30 s.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }
        items(resposta?.unidades.orEmpty(), key = { it.id }) { u ->
            Column(Modifier.padding(horizontal = 16.dp)) { CartaoUnidade(u) }
        }
        item { Spacer(Modifier.height(16.dp)) }
    }
}

@Composable
private fun Mapa(centro: Ponto, usuario: Ponto?, unidades: List<Unidade>, modifier: Modifier) {
    val contexto = LocalContext.current
    val mapa = remember {
        MapView(contexto).apply {
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            controller.setZoom(13.5)
            controller.setCenter(GeoPoint(centro.lat, centro.lon))
        }
    }
    DisposableEffect(Unit) {
        mapa.onResume()
        onDispose {
            mapa.onPause()
            mapa.onDetach()
        }
    }
    AndroidView(factory = { mapa }, modifier = modifier, update = { m ->
        m.overlays.clear()
        unidades.forEach { u ->
            m.overlays.add(Marker(m).apply {
                position = GeoPoint(u.lat, u.lon)
                setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
                title = u.nome
                snippet = "${u.emAtendimento ?: "–"} em atendimento • ${u.aguardando ?: "–"} aguardando" +
                    (u.esperaMin?.let { " • espera ~$it min" } ?: "")
            })
        }
        usuario?.let {
            m.overlays.add(Marker(m).apply {
                position = GeoPoint(it.lat, it.lon)
                setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                title = "Você está aqui"
            })
        }
        m.invalidate()
    })
}

@Composable
fun CartaoUnidade(u: Unidade) {
    val contexto = LocalContext.current
    val fechada = u.funcionando == false
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (fechada) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(2.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(u.tipo, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.size(8.dp))
                Text(u.nome, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            }
            if (fechada) {
                Text("Fechada agora • ${u.horario}", color = MaterialTheme.colorScheme.error)
            } else {
                Text(
                    "${u.emAtendimento ?: "–"} em atendimento • ${u.aguardando ?: "–"} aguardando",
                    style = MaterialTheme.typography.titleMedium,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    u.esperaMin?.let { Text("Espera ~$it min") }
                    Text("Lotação ${u.lotacao}", color = corLotacao(u.lotacao), fontWeight = FontWeight.SemiBold)
                }
            }
            val local = listOfNotNull(
                u.distanciaKm?.let { "%.1f km".format(it) },
                u.deslocamentoMin?.let { "~$it min de carro" },
                u.bairro.ifBlank { null },
            )
            if (local.isNotEmpty()) Text(local.joinToString(" • "), style = MaterialTheme.typography.bodySmall)
            Text(u.endereco + (if (!u.dadosConfirmados) " (dados de demonstração)" else ""), style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(
                    onClick = { abrirRota(contexto, u.lat, u.lon, u.nome) },
                    label = { Text("Como chegar") },
                    leadingIcon = { Icon(Icons.Filled.Place, null, Modifier.size(18.dp)) },
                )
                if (u.telefone.isNotBlank()) {
                    AssistChip(
                        onClick = { ligar(contexto, u.telefone) },
                        label = { Text(u.telefone) },
                        leadingIcon = { Icon(Icons.Filled.Call, null, Modifier.size(18.dp)) },
                    )
                }
            }
        }
    }
}
